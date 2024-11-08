import os
import telebot
from openai import OpenAI
import logging
from datetime import datetime
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENAI_TOKEN = os.getenv('OPENAI_API_KEY')
COLLECTIVAT_TOKEN = os.getenv('COLLECTIVAT_TOKEN')

# Validate required environment variables
required_vars = ['BOT_TOKEN', 'OPENAI_TOKEN', 'COLLECTIVAT_TOKEN']
missing_vars = [var for var in required_vars if not globals()[var]]

if missing_vars:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")


# Set up logging
logging.basicConfig(
    filename='bot_log.log',
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OPENAI_TOKEN = os.environ.get('OPENAI_TOKEN')

# Initialize the clients
bot = telebot.TeleBot(BOT_TOKEN)
# openai.api_key = OPENAI_TOKEN
client = OpenAI()

# Store conversation history for each user
conversation_histories = {}

# Load system prompt from file
def load_system_prompt(file_path: str = "system_prompt.md") -> str:
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
    SYSTEM_PROMPT = load_system_prompt()
except Exception as e:
    raise RuntimeError(f"Failed to initialize bot: {str(e)}")


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

def get_openai_response(user_id, user_message):
    """Get response from OpenAI"""
    try:
        # Retrieve conversation history and create a message payload
        history = get_conversation_history(user_id)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": user_message}
        ]
        
        # Call OpenAI's chat completion API
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Replace with your preferred model
            messages=messages,
            max_tokens=2048,
            temperature=1,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            response_format={
             "type": "text"
            }
        )
        
        # Directly access the message attribute from the response
        return response.choices[0].message.content
    
    except AttributeError as e:
        logging.error(f"Attribute error while parsing OpenAI response: {e}")
        return "Lo siento, akontesyo un falta. Por favor, intentalo de muevo."
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        return "Lo siento, akontesyo un falta. Por favor, intentalo de muevo."

def translate(text: str, src_lang:str) -> str:
    """
    Translates Spanish text to Ladino using the Collectivat API.
    
    Args:
        text (str): The Spanish text to translate
        
    Returns:
        str: The translated Ladino text, or original text if translation fails
    """
    API_URL = "http://api.collectivat.cat/translate/"
    API_TOKEN = os.environ.get('COLLECTIVAT_TOKEN')  # Add this to your environment variables

    if src_lang=='es':
        tgt_lang = 'lad'
    elif src_lang == 'lad':
        tgt_lang = 'es'
    else:
        logging.error("Unknown language id")
        return text
    
    if not API_TOKEN:
        logging.error("Missing COLLECTIVAT_TOKEN environment variable")
        return text
    
    try:
        payload = {
            "src": src_lang,  
            "tgt": tgt_lang,
            "text": text,
            "token": API_TOKEN
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        
        data = response.json()
        translated_text = data.get("translation")
        
        if translated_text:
            logging.info(f"Successfully translated text. Usage: {data.get('usage', 'N/A')}")
            return translated_text
        else:
            logging.warning("Translation response missing 'translation' field")
            return text
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Translation API request failed: {str(e)}")
        return text
    except ValueError as e:
        logging.error(f"Failed to parse translation API response: {str(e)}")
        return text
    except Exception as e:
        logging.error(f"Unexpected error during translation: {str(e)}")
        return text

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """¡Ola! 
    
So Estreya Perez, su giador de la aluenga Ladino i la kultura sefaradi de el siglo XIX Estanbol.

Como puedo ayudole oy? Puedes demandarme aserka de :
- Lengaje i ekspresiones Ladino
- Las kostumbres i tradisiones sefaradies
- La vida en Estanbol de el siglo XIX
- Mi famiya i komunidad

En ke puedo ayudole?
"""
    
    bot.reply_to(message, welcome_text)
    logging.info(f"New user started conversation: {message.from_user.id}")

@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    try:
        user_id = message.from_user.id
        user_message = message.text
        
        # Log incoming message
        logging.info(f"Received message from {user_id}: {user_message}")

        # Translate to spanish
        user_message_es = translate(text = user_message, src_lang='lad')
        logging.info(f"Translated to es: {user_message_es}")
        
        # Get OpenAI response
        openai_response = get_openai_response(user_id, user_message_es)
        logging.info(f"OpenAI response: {openai_response}")
        
        # Update conversation history
        update_conversation_history(user_id, "user", user_message_es)
        update_conversation_history(user_id, "assistant", openai_response)
        
        # Translate to Ladino
        response_lad = translate(text=openai_response, src_lang='es')
        logging.info(f"Translated to lad: {response_lad}")

        # Send response
        bot.reply_to(message, response_lad)
        
        # Log success
        logging.info(f"Sent response to {user_id}")
        
    except Exception as e:
        error_message = f"Error processing message: {str(e)}"
        logging.error(error_message)
        bot.reply_to(message, "Lo siento, akontesyo un falta. Por favor, intentalo de muevo.")

def main():
    logging.info("Bot started")
    try:
        bot.infinity_polling()
    except Exception as e:
        logging.error(f"Bot stopped due to error: {str(e)}")

if __name__ == "__main__":
    main()