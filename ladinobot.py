import os
import telebot
import logging
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic
from claude_handler import ClaudeHandler


# Load environment variables from .env file
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENAI_TOKEN = os.getenv('OPENAI_API_KEY')
COLLECTIVAT_TOKEN = os.getenv('COLLECTIVAT_TOKEN')
SYSTEM_PROMPT_PATH = os.getenv('PROMPT_PATH')
ANTHROPIC_KEY = os.getenv('ANTHROPIC_KEY')
KNOWLEDGE_DIR = os.getenv('KNOWLEDGE_DIR')

# Validate required environment variables
required_vars = ['BOT_TOKEN', 'ANTHROPIC_KEY', 'COLLECTIVAT_TOKEN', 'SYSTEM_PROMPT_PATH']
missing_vars = [var for var in required_vars if not globals()[var]]

if missing_vars:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Set up logging
logging.basicConfig(
    filename='bot_log.log',
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

# Initialize the clients
bot = telebot.TeleBot(BOT_TOKEN)

#Initialize LLM backend
# client = OpenAI()
anthropic = Anthropic(api_key=ANTHROPIC_KEY)

# Store conversation history for each user
conversation_histories = {}

# Load system prompt from file
def load_system_prompt(file_path: str = SYSTEM_PROMPT_PATH) -> str:
    """
    Load system prompt from a text file.
    
    Args:
        file_path (str): Path to the system prompt file
        
    Returns:
        str: The system prompt text, or a default error message if file cannot be read
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            prompt = file.read().strip()
            logging.info(f"Successfully loaded system prompt from {file_path}")
            return prompt
    except FileNotFoundError:
        error_msg = f"System prompt file not found at {file_path}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)
    except Exception as e:
        error_msg = f"Error reading system prompt file: {str(e)}"
        logging.error(error_msg)
        raise Exception(error_msg)

# Replace the existing SYSTEM_PROMPT definition with:
try:
    system_prompt = load_system_prompt()
except Exception as e:
    raise RuntimeError(f"Failed to initialize bot: {str(e)}")

# Initialize Claude handler
claude_handler = ClaudeHandler(anthropic, system_prompt = system_prompt, knowledge_dir=KNOWLEDGE_DIR)

def get_conversation_history(user_id):
    """Get or initialize conversation history for a user"""
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []
    return conversation_histories[user_id]

def update_conversation_history(user_id, role, content):
    """Update a user's conversation history"""
    history = get_conversation_history(user_id)
    history.append({"role": role, "content": content})
    
    # Keep only last 10 messages to manage context length
    if len(history) > 10:
        history.pop(0)
    
    conversation_histories[user_id] = history


def get_claude_response(user_id: str, user_message: str) -> str:
    """Get response from Claude API with knowledge integration"""
    history = get_conversation_history(user_id)
    response_text, usage_stats = claude_handler.get_response(
        user_id=user_id,
        user_message=user_message,
        conversation_history=history
    )
    
    # Log the usage stats
    logging.info(f"Claude API usage stats: {usage_stats}")
    
    return response_text

@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    try:
        user_id = message.from_user.id
        user_message = message.text
        
        # Log incoming message
        logging.info(f"Received message from {user_id}: {user_message}")
        
        # Get LLM response
        # llm_response = get_openai_response(user_id, user_message_es)
        # llm_response = "FAKE"
        llm_response = get_claude_response(user_id, user_message)
        logging.info(f"LLM response: {llm_response}")
        
        # Update conversation history
        update_conversation_history(user_id, "user", user_message)
        update_conversation_history(user_id, "assistant", llm_response)
    
        response = llm_response

        # Send response
        bot.reply_to(message, response)
        
        # Log success
        logging.info(f"Sent response to {user_id}")
        
    except Exception as e:
        error_message = f"Error processing message: {str(e)}"
        logging.error(error_message)
        bot.reply_to(message, "Te rogo diskulpas, no esta kaminando bueno. Aprova otruna vez.")

def main():
    logging.info("Bot started")
    try:
        bot.infinity_polling()
    except Exception as e:
        logging.error(f"Bot stopped due to error: {str(e)}")

if __name__ == "__main__":
    main()