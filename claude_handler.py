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
    
    def __init__(self, anthropic_client: Anthropic, system_prompt: str, history_window: int = 10, knowledge_dir: str = "knowledge"):
        """
        Initialize the Claude handler with necessary components.
        
        Args:
            anthropic_client: An initialized Anthropic client instance
            knowledge_dir: Path to directory containing knowledge resources
        """
        self.client = anthropic_client
        self.knowledge_dir = Path(knowledge_dir)
        self.system_prompt = system_prompt
        self.history_window = history_window
        self.knowledge_resources = self._load_knowledge_resources()
        logging.info(f"Initialized ClaudeHandler with {len(self.knowledge_resources)} knowledge resources")

    def get_response(self, user_id: str, user_message: str, 
                 conversation_history: List[Dict]) -> Tuple[str, Dict]:
        """
        Generate a response using the Claude API with optimized prompt caching.
        This method carefully structures the conversation to ensure proper handling of:
        1. Knowledge base caching
        2. Conversation history
        3. Current message context
        
        Args:
            user_id: Unique identifier for the user
            user_message: Current message from the user
            conversation_history: List of previous conversation messages
            
        Returns:
            Tuple containing (response_text, usage_statistics)
        """
        try:
            # First, combine all knowledge resources into a single cacheable block.
            # We wrap each resource in semantic XML tags to help Claude understand its context.
            knowledge_content = "<knowledge_base>\n"
            for resource_name, content in self.knowledge_resources.items():
                knowledge_content += f"<{resource_name}>\n{content}\n</{resource_name}>\n"
            knowledge_content += "</knowledge_base>"
            
            # Initialize our messages array. The order of messages is crucial for proper conversation flow.
            formatted_messages = []
            
            # Add the knowledge base as our first message with caching enabled.
            # This large content will be cached and reused in subsequent calls.
            formatted_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": knowledge_content,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            })
            
            # Add historical context from previous conversations.
            # We limit this to maintain relevant context without overwhelming.
            if conversation_history:
                # Leave room for the current message by using history_window - 1
                history_slice = conversation_history[-(self.history_window - 1):]
                for msg in history_slice:
                    formatted_messages.append({
                        "role": msg["role"],
                        "content": [
                            {
                                "type": "text",
                                "text": msg["content"]
                            }
                        ]
                    })
            
            # Add the current user message as the final message.
            # We clearly mark this as the current question to ensure Claude responds to it.
            formatted_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Current message requiring response: {user_message}",
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            })
            
            # Make the API call with our carefully structured message array
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                temperature=1,
                system=[
                    {
                        "type": "text",
                        "text": self.system_prompt
                    }
                ],
                messages=formatted_messages,
                extra_headers={
                    "anthropic-beta": "prompt-caching-2024-07-31"
                }
            )
            
            # Collect detailed usage statistics to monitor caching effectiveness
            usage_stats = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read": getattr(response.usage, "cache_read_input_tokens", 0),
                "cache_created": getattr(response.usage, "cache_creation_input_tokens", 0)
            }
            
            # Log comprehensive statistics about the API call
            logging.info(
                f"API call stats - Input tokens: {usage_stats['input_tokens']}, "
                f"Cache read: {usage_stats['cache_read']}, "
                f"Cache created: {usage_stats['cache_created']}, "
                f"Output tokens: {usage_stats['output_tokens']}"
            )
            
            # Safely handle the response content
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

