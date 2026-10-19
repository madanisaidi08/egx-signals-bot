import asyncio
import logging
import sys
import uvicorn
from telegram.ext import Application
from bot_handlers import setup_bot_handlers
from webhook_server import app, set_bot_instance
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_PROXY_URL,
    TELEGRAM_BASE_URL,
    WEBHOOK_HOST,
    WEBHOOK_PORT
)
import database as db

# إعداد التسجيل (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("EGX_BOT_MAIN")

async def run_services():
    # 1. تهيئة قاعدة البيانات
    logger.info("Initializing database...")
    db.init_db()
    logger.info("Database initialized successfully.")

    # 2. التحقق من وجود توكن البوت
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("=" * 60)
        logger.error("❌ خطأ: يرجى وضع TELEGRAM_BOT_TOKEN الخاص بك داخل ملف .env أولاً!")
        logger.error("=" * 60)
        sys.exit(1)

    # 3. إعداد تطبيق تليجرام
    logger.info("Building Telegram application...")
    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    builder = builder.connect_timeout(30.0).read_timeout(30.0).write_timeout(30.0)

    if TELEGRAM_BASE_URL:
        logger.info(f"Using Telegram Base URL: {TELEGRAM_BASE_URL}")
        builder = builder.base_url(TELEGRAM_BASE_URL)

    if TELEGRAM_PROXY_URL:
        logger.info(f"Using Telegram Proxy: {TELEGRAM_PROXY_URL}")
        builder = builder.proxy(TELEGRAM_PROXY_URL).get_updates_proxy(TELEGRAM_PROXY_URL)

    telegram_app = builder.build()
    setup_bot_handlers(telegram_app)
    set_bot_instance(telegram_app.bot)

    # 4. إعداد خادم Uvicorn (FastAPI)
    uvicorn_config = uvicorn.Config(
        app=app,
        host=WEBHOOK_HOST,
        port=WEBHOOK_PORT,
        log_level="info"
    )
    server = uvicorn.Server(uvicorn_config)

    # 5. تشغيل البوت وخادم الويب هوك بالتزامن
    logger.info("Starting Telegram Bot & Webhook Server...")
    async with telegram_app:
        await telegram_app.start()
        await telegram_app.updater.start_polling(drop_pending_updates=True)
        logger.info(f"🚀 Telegram Bot is polling...")
        logger.info(f"🌐 FastAPI Webhook Server running at http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook")
        
        try:
            await server.serve()
        except asyncio.CancelledError:
            logger.info("Services stopping...")
        finally:
            logger.info("Stopping Telegram Bot...")
            await telegram_app.updater.stop()
            await telegram_app.stop()

def main():
    try:
        asyncio.run(run_services())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application shut down gracefully.")

if __name__ == "__main__":
    main()
