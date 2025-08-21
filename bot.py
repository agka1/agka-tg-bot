import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask
import logging
import sys
import time

# --- ЯВНАЯ НАСТРОЙКА ЛОГИРОВАНИЯ ДЛЯ AZURE ---
# Создаем логгер
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Создаем обработчик, который будет писать логи в стандартный вывод (stdout)
# Это то, что Azure Log Stream читает по умолчанию
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Добавляем обработчик к логгеру
logger.addHandler(handler)


# --- ЗАГРУЗКА КЛЮЧЕЙ ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- ЧАСТЬ С МИНИ-ВЕБ-СЕРВЕРОМ (ДЛЯ AZURE) ---
app = Flask(__name__)
@app.route('/')
def hello_world():
    return 'Bot is alive!'

def run_web_server():
    try:
        # Используем порт 8000, так как мы его настроили в Azure
        app.run(host='0.0.0.0', port=8000)
    except Exception as e:
        logger.error(f"Ошибка в веб-сервере: {e}", exc_info=True)

# --- ОСНОВНАЯ ЧАСТЬ БОТА ---
# --- ЗАПУСК ВСЕГО ВМЕСТЕ ---
if __name__ == "__main__":
    try:
        logger.info("Скрипт запускается...")

        if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
            raise ValueError("ОШИБКА: Один или оба API-ключа не найдены в переменных окружения.")
        
        logger.info("API ключи успешно загружены.")

        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        logger.info("Инициализация бота и модели Gemini прошла успешно.")

        @bot.message_handler(commands=['start'])
        def send_welcome(message):
            bot.reply_to(message, "Привет! Я твой ассистент на базе Google Gemini. Задай мне любой вопрос.")

        @bot.message_handler(func=lambda message: True)
        def get_gemini_response(message):
            thinking_message = bot.reply_to(message, "🧠 Думаю...")
            try:
                response = model.generate_content(message.text)
                bot.edit_message_text(chat_id=message.chat.id, message_id=thinking_message.message_id, text=response.text)
            except Exception as e:
                logger.error(f"Ошибка при генерации ответа Gemini: {e}", exc_info=True)
                bot.edit_message_text(chat_id=message.chat.id, message_id=thinking_message.message_id, text=f"Произошла ошибка при обращении к Gemini.")

        # Запускаем веб-сервер в отдельном фоновом потоке
        web_thread = threading.Thread(target=run_web_server)
        web_thread.daemon = True
        web_thread.start()
        logger.info("Веб-сервер для Azure запущен в фоновом потоке.")

        # Запускаем бота в основном потоке
        logger.info("Запускаем бота (polling)...")
        bot.polling(none_stop=True)

    except Exception as e:
        # ЭТОТ БЛОК ПОЙМАЕТ ЛЮБУЮ ОШИБКУ ПРИ ЗАПУСКЕ И ВЫВЕДЕТ ЕЕ
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ БОТА: {e}", exc_info=True)
        # Добавляем задержку, чтобы лог успел записаться
        time.sleep(60)