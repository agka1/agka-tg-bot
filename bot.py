import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask

# --- ЗАГРУЗКА КЛЮЧЕЙ ---
# Безопасно получаем ключи из переменных окружения
# Для локального теста можно временно раскомментировать и вставить ключи сюда:
# TELEGRAM_BOT_TOKEN = '8343640201:AAHHnOj4eJr5kkCyawmBhpN9l4cQ6Y_NYBs'
# GEMINI_API_KEY = 'AIzaSyAH2g3J-R8QVF7Z0cT4ENS15nUhSpUJ2IY'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')


# --- ИНИЦИАЛИЗАЦИЯ ---
# Проверяем, что ключи загружены
if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Необходимо установить переменные окружения TELEGRAM_BOT_TOKEN и GEMINI_API_KEY")


# --- ЧАСТЬ С МИНИ-ВЕБ-СЕРВЕРОМ (ДЛЯ AZURE) ---

# Создаем экземпляр веб-приложения Flask

app = Flask(__name__)

@app.route('/')

def hello_world():
    # Этот маршрут будет отвечать на HTTP-пинги от Azure
    return 'Bot is alive!'


def run_web_server():
    # Запускаем веб-сервер на порту, который слушает Azure
    # Используем 0.0.0.0, чтобы он был доступен извне контейнера
    app.run(host='0.0.0.0', port=8000)

# Инициализация бота и модели Gemini
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')


# --- ОБРАБОТЧИКИ ---
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
        bot.edit_message_text(chat_id=message.chat.id, message_id=thinking_message.message_id, text=f"Произошла ошибка: {e}")


# --- ЗАПУСК ВСЕГО ВМЕСТЕ ---
if __name__ == "__main__":
    # Запускаем веб-сервер в отдельном фоновом потоке
    # daemon=True означает, что поток закроется вместе с основной программой
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()

    # Запускаем бота в основном потоке
    print("Бот и веб-сервер для Azure запущены...")
    bot.polling(none_stop=True)