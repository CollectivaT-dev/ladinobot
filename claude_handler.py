import os
from pathlib import Path
from typing import Dict, List, Tuple
import logging
import time
from anthropic import Anthropic

class ClaudeHandler:
    """
    Handles interactions with Claude API, including knowledge management and response generation.
    This class centralizes all Claude-specific logic and manages conversation formatting and 
    knowledge resource integration with appropriate caching controls.
    """
    
    def __init__(self, anthropic_client: Anthropic, knowledge_dir: str = "knowledge"):
        """
        Initialize the Claude handler with necessary components.
        
        Args:
            anthropic_client: An initialized Anthropic client instance
            knowledge_dir: Path to directory containing knowledge resources
        """
        self.client = anthropic_client
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_resources = self._load_knowledge_resources()
        logging.info(f"Initialized ClaudeHandler with {len(self.knowledge_resources)} knowledge resources")

    def get_response(self, user_id: str, user_message: str, system_prompt: str,
                 conversation_history: List[Dict]) -> Tuple[str, Dict]:
        """
        Generate a response using the Claude API with optimized prompt caching.
        
        This implementation follows Anthropic's example by bundling all cacheable content
        into a single large message with cache control, which has been shown to be more
        effective than caching multiple smaller pieces.
        
        Args:
            user_id: Unique identifier for the user
            user_message: Current message from the user
            system_prompt: Base system prompt to use
            conversation_history: List of previous conversation messages
            
        Returns:
            Tuple containing (response_text, usage_statistics)
        """
        try:
            # First, we bundle all our knowledge resources into one large chunk of text
            # This is more efficient for caching than splitting into multiple pieces
            knowledge_content = "<knowledge>\n"
            for resource_name, content in self.knowledge_resources.items():
                knowledge_content += f"<{resource_name}>\n{content}\n</{resource_name}>\n"
            knowledge_content += "</knowledge>"
            
            # Start building our messages array with the knowledge content
            # We put this first so it can be cached and reused effectively
            initial_message = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": knowledge_content,
                        "cache_control": {"type": "ephemeral"}
                    },
                    {
                        "type": "text",
                        "text": user_message
                    }
                ]
            }
            
            # Format conversation history following Claude's expected structure
            formatted_messages = [initial_message]
            
            # Add recent conversation history if it exists
            # We limit to last 4 messages to maintain context without overwhelming
            if conversation_history:
                for msg in conversation_history[-4:]:
                    formatted_messages.append({
                        "role": msg["role"],
                        "content": [
                            {
                                "type": "text",
                                "text": msg["content"]
                            }
                        ]
                    })
            
            # Make the API call with all our formatting in place
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                temperature=1,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt
                    }
                ],
                messages=formatted_messages,
                extra_headers={
                    "anthropic-beta": "prompt-caching-2024-07-31"
                }
            )
            
            # Collect usage statistics
            usage_stats = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read": getattr(response.usage, "cache_read_input_tokens", 0),
                "cache_created": getattr(response.usage, "cache_creation_input_tokens", 0)
            }
            
            # Log API call statistics
            logging.info(
                f"API call stats - Input tokens: {usage_stats['input_tokens']}, "
                f"Cache read: {usage_stats['cache_read']}, "
                f"Cache created: {usage_stats['cache_created']}"
            )
            
            # Safely access the response content
            if response.content and len(response.content) > 0:
                return response.content[0].text, usage_stats
            else:
                logging.error("Empty response content from Claude API")
                return "Te rogo diskulpas, no esta kaminando bueno. Aprova otruna vez.", usage_stats
            
        except Exception as e:
            logging.error(f"Claude API error: {str(e)}", exc_info=True)
            return "Te rogo diskulpas, no esta kaminando bueno. Aprova otruna vez.", {}

    def _load_knowledge_resources(self) -> Dict[str, str]:
        """
        Load and prepare knowledge resources from the specified directory.
        
        Returns:
            Dictionary mapping resource names to their content
        """
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

