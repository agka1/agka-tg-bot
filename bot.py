import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask
import logging
import sys
import time
from telebot import types
from telebot.types import BotCommand # <-- 1. Добавляем импорт для команд
import re
from google.api_core import exceptions as google_exceptions

# --- ЯВНАЯ НАСТРОЙКА ЛОГИРОВАНИЯ ДЛЯ AZURE ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MAX_HISTORY_LENGTH = 30

# --- КОНСТАНТЫ МОДЕЛЕЙ ---
MODEL_FLASH = 'gemini-1.5-flash'
MODEL_PRO = 'gemini-2.5-pro'
DEFAULT_MODEL_NAME = 'flash'

# --- ХРАНИЛИЩА ДАННЫХ В ПАМЯТИ ---
user_histories = {}
user_model_choices = {}

# --- ФУНКЦИЯ ДЛЯ КОНВЕРТАЦИИ MARKDOWN ---
def to_telegram_markdown(text):
    text = text.replace('**', '*')
    special_chars = r"([.>#+-=|{!}])"
    return re.sub(special_chars, r'\\\1', text)

# --- ВЕБ-СЕРВЕР ДЛЯ AZURE ---
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
        logger.info("Скрипт запускается...")

        if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
            raise ValueError("ОШИБКА: Один или оба API-ключа не найдены в переменных окружения.")
        
        logger.info("API ключи успешно загружены.")

        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        genai.configure(api_key=GEMINI_API_KEY)
        
        logger.info("Инициализация бота прошла успешно.")

        # --- 2. УСТАНОВКА КОМАНД-ПОДСКАЗОК ДЛЯ TELEGRAM ---
        try:
            logger.info("Установка команд бота...")
            bot.set_my_commands([
                BotCommand('start', 'Запустить бота и показать приветствие'),
                BotCommand('reset', 'Сбросить историю диалога'),
                BotCommand('model', 'Выбрать модель Gemini (Flash/Pro)')
            ])
            logger.info("Команды бота успешно установлены.")
        except Exception as e:
            logger.error(f"Не удалось установить команды бота: {e}")

        # --- ОБРАБОТЧИКИ КОМАНД ---
        @bot.message_handler(commands=['start', 'reset', 'model'])
        def handle_commands(message):
            # ... (этот блок без изменений) ...
            if message.text == '/start':
                bot.reply_to(message, "Привет! Я ассистент на базе Google Gemini.\n\n"
                                      "Я запоминаю контекст нашего диалога.\n"
                                      "Чтобы начать заново, используй /reset.\n"
                                      "Чтобы выбрать модель (быструю или мощную), используй /model.")
            elif message.text == '/reset':
                user_id = message.chat.id
                if user_id in user_histories:
                    user_histories.pop(user_id)
                bot.reply_to(message, "История диалога сброшена. Начинаем с чистого листа!")
            elif message.text == '/model':
                markup = types.InlineKeyboardMarkup(row_width=2)
                btn_flash = types.InlineKeyboardButton("⚡️ Flash (Быстрый)", callback_data='select_flash')
                btn_pro = types.InlineKeyboardButton("💎 Pro (Мощный)", callback_data='select_pro')
                markup.add(btn_flash, btn_pro)
                user_id = message.chat.id
                current_model_name = user_model_choices.get(user_id, DEFAULT_MODEL_NAME)
                text_to_send = f"Текущая модель: *{current_model_name.capitalize()}*.\n\nВыберите новую модель для диалога:"
                bot.send_message(user_id, to_telegram_markdown(text_to_send), 
                                 reply_markup=markup, parse_mode='MarkdownV2')

        @bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
        def handle_model_selection(call):
            # ... (этот блок без изменений) ...
            user_id = call.message.chat.id
            model_text = ""
            if call.data == 'select_flash':
                user_model_choices[user_id] = 'flash'
                model_text = "⚡️ Flash"
            elif call.data == 'select_pro':
                user_model_choices[user_id] = 'pro'
                model_text = "💎 Pro"
            bot.answer_callback_query(call.id, text=f"Выбрана модель {model_text}")
            text_to_send = f"Отлично! Теперь мы используем модель: *{model_text}*"
            bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, 
                                  text=to_telegram_markdown(text_to_send), parse_mode='MarkdownV2')

        @bot.message_handler(func=lambda message: True)
        def get_gemini_response(message):
            # ... (этот блок без изменений) ...
            user_id = message.chat.id
            thinking_message = bot.reply_to(message, "⏳ Думаю с учетом контекста...")
            try:
                chosen_model_name = user_model_choices.get(user_id, DEFAULT_MODEL_NAME)
                model = genai.GenerativeModel(MODEL_PRO if chosen_model_name == 'pro' else MODEL_FLASH)
                history = user_histories.get(user_id, [])
                history.append({'role': 'user', 'parts': [message.text]})
                response = model.generate_content(history)
                if response.parts:
                    bot_response_text = response.parts[0].text
                    history.append({'role': 'model', 'parts': [bot_response_text]})
                else:
                    bot_response_text = "Я не могу ответить на это. Попробуй переформулировать."
                while len(history) > MAX_HISTORY_LENGTH:
                    history.pop(0)
                user_histories[user_id] = history
                formatted_text = to_telegram_markdown(bot_response_text)
                bot.edit_message_text(chat_id=user_id, message_id=thinking_message.message_id, 
                                      text=formatted_text, parse_mode='MarkdownV2')
            except google_exceptions.ResourceExhausted as e:
                logger.warning(f"Достигнут лимит запросов к Gemini API: {e}")
                response_text = "Слишком много запросов! 🌪️ Пожалуйста, подождите минуту и попробуйте снова."
                bot.edit_message_text(chat_id=user_id, message_id=thinking_message.message_id, text=response_text)
            except Exception as e:
                logger.error(f"Непредвиденная ошибка при генерации ответа Gemini: {e}", exc_info=True)
                response_text = "Произошла непредвиденная ошибка при обращении к Gemini. Попробуйте позже."
                bot.edit_message_text(chat_id=user_id, message_id=thinking_message.message_id, text=response_text)

        # --- ЗАПУСК ---
        web_thread = threading.Thread(target=run_web_server)
        web_thread.daemon = True
        web_thread.start()
        logger.info("Веб-сервер для Azure запущен в фоновом потоке.")

        logger.info("Запускаем бота (polling)...")
        bot.polling(none_stop=True)

    except Exception as e:
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ БОТА: {e}", exc_info=True)
        time.sleep(60)