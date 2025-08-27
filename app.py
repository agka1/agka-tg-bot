import telebot
import google.generativeai as genai
from google.generativeai import types as genai_types
import os
import threading
from flask import Flask
import logging
import sys
import time
from telebot import types
from telebot.types import BotCommand
import re
from google.api_core import exceptions as google_exceptions

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- КОНСТАНТЫ МОДЕЛЕЙ (оставлены как в вашем коде) ---
MODEL_FLASH = 'gemini-2.5-flash'
MODEL_PRO = 'gemini-2.5-pro'
DEFAULT_MODEL_NAME = 'flash'

# --- ХРАНИЛИЩА ДАННЫХ ---
user_histories = {}
user_model_choices = {}

def to_telegram_markdown(text):
    text = text.replace('**', '*')
    special_chars = r"([.>#+-=|{!}()])"
    return re.sub(special_chars, r'\\\1', text)

# --- ВЕБ-СЕРВЕР ---
app = Flask(__name__)
@app.route('/')
def hello_world():
    return 'Bot is alive!'

def run_web_server():
    try:
        app.run(host='0.0.0.0', port=8000)
    except Exception as e:
        logger.error(f"Ошибка в веб-сервере: {e}", exc_info=True)

# --- ОСНОВНАЯ ЧАСТЬ БОТА ---
if __name__ == "__main__":
    try:
        logger.info("--- ЗАПУСК СКРИПТА ---")

        # --- НОВЫЙ ЛОГ: Проверяем наличие ключей ---
        TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
        GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
        
        logger.info(f"Переменная TELEGRAM_BOT_TOKEN найдена: {TELEGRAM_BOT_TOKEN is not None}")
        logger.info(f"Переменная GEMINI_API_KEY найдена: {GEMINI_API_KEY is not None}")

        if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
            logger.error("КРИТИЧЕСКАЯ ОШИБКА: Один или оба API-ключа не найдены. Завершение работы.")
            raise ValueError("ОШИБКА: API-ключи не найдены в переменных окружения.")
        
        logger.info("API ключи успешно прочитаны.")

        # --- НОВЫЙ ЛОГ: Перед инициализацией TeleBot ---
        logger.info("Инициализация TeleBot...")
        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        logger.info("TeleBot успешно инициализирован.")

        # --- НОВЫЙ ЛОГ: Перед конфигурацией Gemini ---
        logger.info("Конфигурация Google Generative AI...")
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Google Generative AI успешно сконфигурирован.")
        
        try:
            # --- НОВЫЙ ЛОГ: Перед установкой команд ---
            logger.info("Попытка установить команды бота...")
            bot.set_my_commands([
                BotCommand('start', 'Запустить бота'),
                BotCommand('reset', 'Сбросить историю диалога'),
                BotCommand('model', 'Выбрать модель Gemini')
            ])
            logger.info("Команды бота успешно установлены.")
        except Exception as e:
            logger.error(f"Не удалось установить команды бота: {e}", exc_info=True)
            # Не прерываем работу, если команды не установились, это не критично

        # ОБРАБОТЧИКИ КОМАНД (без изменений)
        @bot.message_handler(commands=['start', 'reset', 'model'])
        def handle_commands(message):
            if message.text == '/start':
                bot.reply_to(message, "Привет! Я ассистент на базе Google Gemini с доступом в интернет.\n\n"
                                      "Используйте /reset, чтобы сбросить диалог, и /model для выбора модели.")
            elif message.text == '/reset':
                user_id = message.chat.id
                if user_id in user_histories:
                    user_histories.pop(user_id)
                bot.reply_to(message, "История диалога сброшена.")
            elif message.text == '/model':
                markup = types.InlineKeyboardMarkup(row_width=2)
                btn_flash = types.InlineKeyboardButton("⚡️ Flash (Быстрый)", callback_data='select_flash')
                btn_pro = types.InlineKeyboardButton("💎 Pro (Мощный)", callback_data='select_pro')
                markup.add(btn_flash, btn_pro)
                user_id = message.chat.id
                current_model_name = user_model_choices.get(user_id, DEFAULT_MODEL_NAME)
                text_to_send = f"Текущая модель: *{current_model_name.capitalize()}*.\n\nВыберите новую модель:"
                bot.send_message(user_id, to_telegram_markdown(text_to_send), 
                                 reply_markup=markup, parse_mode='MarkdownV2')

        @bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
        def handle_model_selection(call):
            user_id = call.message.chat.id
            model_text = ""
            if call.data == 'select_flash':
                user_model_choices[user_id] = 'flash'
                model_text = "⚡️ Flash"
            elif call.data == 'select_pro':
                user_model_choices[user_id] = 'pro'
                model_text = "💎 Pro"
            
            bot.answer_callback_query(call.id, text=f"Выбрана модель {model_text}")
            text_to_send = f"Отлично! Теперь используется модель: *{model_text}*"
            bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, 
                                  text=to_telegram_markdown(text_to_send), parse_mode='MarkdownV2')

        @bot.message_handler(func=lambda message: True)
        def get_gemini_response(message):
            user_id = message.chat.id
            thinking_message = bot.reply_to(message, "⏳ Думаю и ищу в интернете...")
            try:
                chosen_model_name = user_model_choices.get(user_id, DEFAULT_MODEL_NAME)
                model_name = MODEL_PRO if chosen_model_name == 'pro' else MODEL_FLASH
                model = genai.GenerativeModel(model_name)
                history = user_histories.get(user_id, [])
                history.append({'role': 'user', 'parts': [message.text]})
                tool = genai_types.Tool(google_search=genai_types.GoogleSearch())
                response = model.generate_content(history, tools=[tool])
                bot_response_text = response.text if response.parts else "Я не могу ответить на это. Попробуйте переформулировать."
                history.append({'role': 'model', 'parts': [bot_response_text]})
                if len(history) > MAX_HISTORY_LENGTH:
                    history = history[-MAX_HISTORY_LENGTH:]
                user_histories[user_id] = history
                formatted_text = to_telegram_markdown(bot_response_text)
                if len(formatted_text) > 4096:
                    formatted_text = formatted_text[:4093] + '...'
                bot.edit_message_text(chat_id=user_id, message_id=thinking_message.message_id, 
                                      text=formatted_text, parse_mode='MarkdownV2')
            except google_exceptions.ResourceExhausted as e:
                logger.warning(f"Достигнут лимит запросов к Gemini API: {e}")
                bot.edit_message_text(chat_id=user_id, message_id=thinking_message.message_id, text="Слишком много запросов! Пожалуйста, подождите минуту.")
            except Exception as e:
                logger.error(f"Непредвиденная ошибка при генерации ответа Gemini: {e}", exc_info=True)
                bot.edit_message_text(chat_id=user_id, message_id=thinking_message.message_id, text="Произошла ошибка. Попробуйте позже.")

        # --- НОВЫЙ ЛОГ: Перед запуском потоков ---
        logger.info("Запуск веб-сервера в фоновом потоке...")
        web_thread = threading.Thread(target=run_web_server)
        web_thread.daemon = True
        web_thread.start()
        logger.info("Веб-сервер запущен.")

        logger.info("--- ЗАПУСК БОТА (POLLING) ---")
        bot.polling(none_stop=True)

    except Exception as e:
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА НА ВНЕШНЕМ УРОВНЕ: {e}", exc_info=True)
        time.sleep(60) # Даем время, чтобы лог успел записаться перед перезапуском контейнера