import telebot
import google.generativeai as genai
import os

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


# --- ЗАПУСК ---
print("Бот запущен...")
bot.polling(none_stop=True)