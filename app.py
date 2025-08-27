import logging
import sys
import os
from flask import Flask
import time

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("--- SMOKE TEST SCRIPT STARTED ---")
logger.info("This is a test log to see if the script can run at all.")
logger.info("If you see this message, the platform is working.")

# --- ВЕБ-СЕРВЕР ДЛЯ ПРОВЕРКИ ---
app = Flask(__name__)
@app.route('/')
def hello_world():
    logger.info("Flask endpoint '/' was hit by Azure health check.")
    return 'Smoke test is alive and responding!'

if __name__ == "__main__":
    try:
        # Azure передает порт через переменную окружения PORT
        port = int(os.environ.get("PORT", 8000))
        logger.info(f"Attempting to start Flask web server on port {port}...")
        
        # Запускаем только веб-сервер, чтобы Azure был доволен
        app.run(host='0.0.0.0', port=port)
        
        logger.info("Flask web server should be running now.")

    except Exception as e:
        logger.error(f"CRITICAL ERROR during smoke test startup: {e}", exc_info=True)
        # Даем время, чтобы лог успел записаться
        time.sleep(60)