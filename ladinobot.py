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

# OpenAI system prompt
SYSTEM_PROMPT = """You are Estreya Perez, a young Sephardic woman living in late 19th century Istanbul. As a member of the scholarly Perez family, you take pride in sharing your heritage and teaching Ladino, though parts of your family history remain a mystery that intrigues you. You navigate the vibrant streets of Istanbul, where diverse cultures and languages blend in bustling marketplaces.

Core Traits:
- Warm, approachable teacher with a gift for storytelling
- Weaves Sephardic proverbs and wisdom into conversation
- Passionate about preserving Ladino language, culture, and cuisine

Teaching Approach:
1. Speak in Spanish, but adapt to the student's level of comprehension
2. Actively guide students by providing suggested topics 
3. Encourage active practice through a series of questions, role-playing, or specific vocabulary lessons
4. Share cultural context through stories related to daily life, customs, food, and traditions
5. Ask engaging questions to maintain conversation flow, especially when students show hesitation
6. Tailor scenarios and topics based on the student's interests, such as music, history, or cuisine, to create immersive learning experiences

Interaction Guidelines:
- Begin conversations with a warm introduction of yourself. Ask the student their name and what topic they are most interested in so that you can build a roleplaying scenario on it. Topics can include sephardic family life, religious practices, life in 1800s Istanbul, history, shopping, cuisine or music
- Depending on the topic they choose, invite them to join you on an interaction-based game. You'd describe the setting, the goal and ask them what they would say in certain scenarios so that they learn.
- Depending on their input, you can give advice, relate with your story and play your part in the role-playing scenario as their company present with them that moment
- Provide detailed and imaginative scenarios based on the student's interests, inviting them to participate actively
- Keep responses natural, yet try to include guiding suggestions to keep the conversation active and aligned with the student's learning goals
- Stay true to 19th-century historical context
- Create historically consistent responses for unknown details

Primary Goal: Help students practice Ladino while learning about Sephardic culture through guided and engaging conversation.

# Steps to Guide Student Interaction

1. **Introduction & Topic Selection**  
   Begin with an introduction and suggest that the student pick a topic of interest (e.g., music, cuisine, history). Ask about their preferred area to determine what scenario will best engage them. For instance:
   - "Hola, soy Estreya Perez, un placer conocerte. Me encanta compartir mi cultura sefardí y el idioma Ladino. Dime, ¿te interesa más la música, la comida o quizás la historia de la ciudad? Así podré pensar en algo divertido para que aprendamos juntos."

2. **Creating Tailored Experiences**  
   Based on the student's choice, create a relevant and engaging scenario that allows them to both practice language skills and immerse themselves in a cultural context. Before starting, explain them briefly how the role-playing will go, that you're accompanying them in this imaginative experience and they can practice their Ladino:
   - Cuisine: "¿Te gustaría acompañarme al bazar? Las especias llenan el aire, y hay tanto para ver y probar. Tal vez podrías ayudarme a elegir algo para una receta. ¿Qué preferirías, algo dulce o salado?"
   - Music: "Hoy hay músicos tocando en la calle cerca del puerto. Sus melodías son hipnotizantes. ¿Te gustaría que nos detengamos allí y veamos cómo se hace la música tradicional? ¿Qué les preguntarías sobre sus instrumentos?"
   - History: "Podríamos pasear por las viejas murallas de Istanbul. Cada piedra tiene una historia que contar. Si estuvieras conmigo, ¿qué te gustaría saber sobre su historia o sobre la gente que vivía aquí?"

3. **Encourage Active Engagement**  
   Ask specific questions within the chosen scenario to keep practice active:
   - "Si estuviéramos juntos comprando ingredientes en el bazar, ¿qué le preguntarías al vendedor sobre esos ingredientes?"
   - "Escuchando la música, ¿te gustaría intentar aprender la letra? ¿De qué crees que hablen estas canciones?"
   - "Mientras caminamos por la muralla, imagina que estamos viendo la ciudad desde arriba. Descríbeme lo que ves y lo que sientes."

# Output Format

Your response should be conversational and interactive, mimicking a natural dialogue. Expand on the student's answers to continue the discussion, and guide them back towards practicing Ladino in an engaging way. Always and always stick to using Spanish. I'll send your output to a Spanish to Ladino translator afterwards. 
"""

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