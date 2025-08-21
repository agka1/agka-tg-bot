import telebot
import google.generativeai as genai
import os
import threading
from flask import Flask
import logging
import sys
import time

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
MAX_HISTORY_LENGTH = 30  # Максимальное количество сообщений в истории (пользователь + бот)

# --- ХРАНИЛИЩЕ ИСТОРИИ ДИАЛОГОВ ---
# Используем словарь, где ключ - это ID чата, а значение - список сообщений
user_histories = {}

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
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        logger.info("Инициализация бота и модели Gemini прошла успешно.")

        # --- ОБРАБОТЧИКИ КОМАНД ---

        @bot.message_handler(commands=['start'])
        def send_welcome(message):
            bot.reply_to(message, "Привет! Я твой ассистент на базе Google Gemini. Я запоминаю контекст нашего диалога. Чтобы начать заново, используй команду /reset.")

        @bot.message_handler(commands=['reset'])
        def reset_history(message):
            user_id = message.chat.id
            if user_id in user_histories:
                user_histories.pop(user_id)
                bot.reply_to(message, "История диалога сброшена. Начинаем с чистого листа!")
            else:
                bot.reply_to(message, "У нас еще не было диалога. Просто напиши мне что-нибудь.")

        @bot.message_handler(func=lambda message: True)
        def get_gemini_response(message):
            user_id = message.chat.id
            thinking_message = bot.reply_to(message, "🧠 Думаю с учетом контекста...")

            try:
                # 1. Получаем или создаем историю для пользователя
                history = user_histories.get(user_id, [])

                # 2. Добавляем новое сообщение пользователя в историю
                # Формат Gemini: {'role': 'user'/'model', 'parts': [текст]}
                history.append({'role': 'user', 'parts': [message.text]})

                # 3. Отправляем всю историю в Gemini
                response = model.generate_content(history)
                
                # 4. Добавляем ответ модели в историю
                # Важно: нужно проверить, что у ответа есть текст, чтобы избежать ошибок
                if response.parts:
                    bot_response_text = response.parts[0].text
                    history.append({'role': 'model', 'parts': [bot_response_text]})
                else:
                    # Если Gemini вернул пустой ответ (например, из-за фильтров безопасности)
                    bot_response_text = "Я не могу ответить на это. Попробуй переформулировать."
                    # Не добавляем пустой ответ в историю, чтобы не портить контекст
                
                # 5. Обрезаем историю, если она стала слишком длинной
                while len(history) > MAX_HISTORY_LENGTH:
                    history.pop(0) # Удаляем самое старое сообщение

                # 6. Сохраняем обновленную историю
                user_histories[user_id] = history

                # 7. Отправляем ответ пользователю
                bot.edit_message_text(chat_id=user_id, message_id=thinking_message.message_id, text=bot_response_text)

            except Exception as e:
                logger.error(f"Ошибка при генерации ответа Gemini: {e}", exc_info=True)
                bot.edit_message_text(chat_id=user_id, message_id=thinking_message.message_id, text=f"Произошла ошибка при обращении к Gemini.")

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