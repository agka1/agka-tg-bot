import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask
import logging

# Настраиваем логирование, чтобы видеть все сообщения
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        # Используем 8080 порт, стандартный для Web Apps, чтобы избежать конфликтов
        app.run(host='0.0.0.0', port=8000)
    except Exception as e:
        logging.error(f"Ошибка в веб-сервере: {e}", exc_info=True)

# --- ОСНОВНАЯ ЧАСТЬ БОТА ---
# --- ЗАПУСК ВСЕГО ВМЕСТЕ ---
if __name__ == "__main__":
    try:
        logging.info("Скрипт запускается...")

        if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
            raise ValueError("ОШИБКА: Один или оба API-ключа не найдены в переменных окружения.")
        
        logging.info("API ключи успешно загружены.")

        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        logging.info("Инициализация бота и модели Gemini прошла успешно.")

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
                logging.error(f"Ошибка при генерации ответа Gemini: {e}", exc_info=True)
                bot.edit_message_text(chat_id=message.chat.id, message_id=thinking_message.message_id, text=f"Произошла ошибка при обращении к Gemini.")

        # Запускаем веб-сервер в отдельном фоновом потоке
        web_thread = threading.Thread(target=run_web_server)
        web_thread.daemon = True
        web_thread.start()
        logging.info("Веб-сервер для Azure запущен в фоновом потоке.")

        # Запускаем бота в основном потоке
        logging.info("Запускаем бота (polling)...")
        bot.polling(none_stop=True)

    except Exception as e:
        # ЭТОТ БЛОК ПОЙМАЕТ ЛЮБУЮ ОШИБКУ ПРИ ЗАПУСКЕ И ВЫВЕДЕТ ЕЕ
        logging.error(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ БОТА: {e}", exc_info=True)
        # Добавляем задержку, чтобы лог успел записаться
        import time
        time.sleep(60)
