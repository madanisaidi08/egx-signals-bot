import asyncio
import logging
import sys
import uvicorn
import httpx
from telegram import Update
from telegram.ext import Application
from bot_handlers import setup_bot_handlers
from webhook_server import app, set_bot_instance
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_PROXY_URL,
    TELEGRAM_BASE_URL,
    WEBHOOK_HOST,
    WEBHOOK_PORT,
    WEBHOOK_BASE_URL
)
import database as db

# إعداد التسجيل (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("EGX_BOT_MAIN")

async def keep_alive_task(base_url: str, interval_seconds: int = 420):
    """
    مهمة دورية لإرسال فحص صحة خارجي كل 7 دقائق لإبقاء الخادم مستيقظاً 24/7 على رندر
    """
    if not base_url:
        return
    ping_url = f"{base_url.rstrip('/')}/health"
    await asyncio.sleep(30)
    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            try:
                resp = await client.get(ping_url)
                logger.info(f"Keep-alive ping sent to {ping_url} (HTTP {resp.status_code})")
            except Exception as e:
                logger.debug(f"Keep-alive ping note: {e}")
            await asyncio.sleep(interval_seconds)

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
    set_bot_instance(telegram_app.bot, telegram_app)

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
    await telegram_app.initialize()
    await telegram_app.start()

    keep_alive_fut = None

    if WEBHOOK_BASE_URL:
        # وضع الويب هوك السحابي لتليجرام (Render Cloud Mode)
        tg_webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}/telegram-webhook"
        logger.info(f"Configuring Telegram Webhook at: {tg_webhook_url}")
        try:
            await telegram_app.bot.set_webhook(
                url=tg_webhook_url,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False
            )
            logger.info(f"✅ Telegram Webhook registered successfully at {tg_webhook_url}")
        except Exception as e:
            logger.error(f"❌ Failed to set Telegram Webhook: {e}")

        # بدء مهمة إبقاء السيرفر مستيقظاً تلقائياً
        keep_alive_fut = asyncio.create_task(keep_alive_task(WEBHOOK_BASE_URL, interval_seconds=420))
    else:
        # وضع الاستطلاع المحلي (Local Polling) إذا لم يتم توفير رابط ويب هوك
        if telegram_app.updater:
            await telegram_app.updater.start_polling(drop_pending_updates=False)
            logger.info("🚀 Telegram Bot is polling...")

    logger.info(f"🌐 FastAPI Webhook Server running at http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook")

    try:
        await server.serve()
    except asyncio.CancelledError:
        logger.info("Services stopping...")
    finally:
        logger.info("Stopping Telegram Bot & Services...")
        if keep_alive_fut and not keep_alive_fut.done():
            keep_alive_fut.cancel()
        if telegram_app.updater and telegram_app.updater.running:
            await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()


def main():
    try:
        asyncio.run(run_services())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application shut down gracefully.")

if __name__ == "__main__":
    main()
