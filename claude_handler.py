import os
from pathlib import Path
from typing import Dict, List, Tuple
import logging
import time
from anthropic import Anthropic

class ClaudeHandler:
    """
    Handles interactions with Claude API with optimized caching strategy.
    This implementation maintains a single cached knowledge base that's shared
    across all user interactions, significantly reducing API costs.
    """
    
    def __init__(self, anthropic_client: Anthropic, system_prompt: str, 
                 history_window: int = 10, knowledge_dir: str = "knowledge"):
        """
        Initialize the Claude handler and prepare the cached knowledge base.
        
        Args:
            anthropic_client: An initialized Anthropic client instance
            system_prompt: The base system prompt to use
            history_window: Number of previous messages to maintain in context
            knowledge_dir: Path to directory containing knowledge resources
        """
        self.client = anthropic_client
        self.system_prompt = system_prompt
        self.knowledge_dir = Path(knowledge_dir)
        self.history_window = history_window
        
        # Load knowledge resources once during initialization
        self.knowledge_resources = self._load_knowledge_resources()
        
        # Prepare the cached knowledge content
        self.cached_knowledge = self._prepare_knowledge_content()
        
        # Initialize the cache with first API call
        self._initialize_cache()
        
        logging.info(f"Initialized ClaudeHandler with {len(self.knowledge_resources)} knowledge resources")

    def _prepare_knowledge_content(self) -> dict:
        """
        Prepare the knowledge content in the format needed for Claude API.
        This formatted content will be cached and reused across all interactions.
        """
        # Combine all knowledge resources with semantic XML tags
        knowledge_content = "<knowledge_base>\n"
        for resource_name, content in self.knowledge_resources.items():
            knowledge_content += f"<{resource_name}>\n{content}\n</{resource_name}>\n"
        knowledge_content += "</knowledge_base>"
        
        # Format the message for Claude API
        return {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": knowledge_content,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        }

    def _initialize_cache(self):
        """
        Initialize the cache by making a simple API call.
        This ensures our knowledge base is cached before handling real user messages.
        """
        try:
            # Make a simple API call to cache the knowledge base
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1,  # Minimize token usage for initialization
                temperature=1,
                system=[{"type": "text", "text": self.system_prompt}],
                messages=[self.cached_knowledge],
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
            )
            
            logging.info("Successfully initialized knowledge base cache")
            
        except Exception as e:
            logging.error(f"Failed to initialize cache: {str(e)}")
            raise

    def get_response(self, user_id: str, user_message: str, 
                    conversation_history: List[Dict]) -> Tuple[str, Dict]:
        """
        Generate a response using the Claude API with shared cache.
        
        Args:
            user_id: Unique identifier for the user
            user_message: Current message from the user
            conversation_history: List of previous conversation messages
            
        Returns:
            Tuple containing (response_text, usage_statistics)
        """
        try:
            # Start with our cached knowledge message
            formatted_messages = [self.cached_knowledge]
            
            # Add conversation history
            if conversation_history:
                for msg in conversation_history[-(self.history_window - 1):]:
                    formatted_messages.append({
                        "role": msg["role"],
                        "content": [
                            {
                                "type": "text",
                                "text": msg["content"]
                            }
                        ]
                    })
            
            # Add current message
            formatted_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Current message: {user_message}"
                    }
                ]
            })
            
            # Make API call
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                temperature=1,
                system=[{"type": "text", "text": self.system_prompt}],
                messages=formatted_messages,
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
            )
            
            # Collect usage statistics
            usage_stats = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read": getattr(response.usage, "cache_read_input_tokens", 0),
                "cache_created": getattr(response.usage, "cache_creation_input_tokens", 0)
            }
            
            logging.info(
                f"API call stats for user {user_id} - "
                f"Input tokens: {usage_stats['input_tokens']}, "
                f"Cache read: {usage_stats['cache_read']}, "
                f"Cache created: {usage_stats['cache_created']}, "
                f"Output tokens: {usage_stats['output_tokens']}"
            )
            
            if response.content and len(response.content) > 0:
                return response.content[0].text, usage_stats
            else:
                logging.error("Empty response content from Claude API")
                return "Te rogo diskulpas, no esta kaminando bueno. Aprova otruna vez.", usage_stats
            
        except Exception as e:
            logging.error(f"Claude API error: {str(e)}", exc_info=True)
            return "Te rogo diskulpas, no esta kaminando bueno. Aprova otruna vez.", {}

    def _load_knowledge_resources(self) -> Dict[str, str]:
        """Load and prepare knowledge resources from the specified directory."""
        resources = {}
        try:
            if not self.knowledge_dir.exists():
                logging.warning(f"Knowledge directory not found: {self.knowledge_dir}")
                return resources
                
            for file_path in self.knowledge_dir.glob("*.txt"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        resources[file_path.stem] = content
                        logging.info(f"Loaded knowledge resource: {file_path.name}")
                except Exception as e:
                    logging.error(f"Failed to load {file_path.name}: {e}")
                    
            return resources
            
        except Exception as e:
            logging.error(f"Error loading knowledge resources: {e}")
            return resources