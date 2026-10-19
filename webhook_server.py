import json
import logging
from datetime import datetime
from typing import Optional, Any, Dict
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from telegram import Bot
import pytz

import database as db
from egx_stocks import normalize_ticker, normalize_timeframe
from config import WEBHOOK_SECRET, TIMEZONE

logger = logging.getLogger(__name__)

# إنشاء تطبيق FastAPI
app = FastAPI(title="EGX TradingView Webhook Server", version="1.0.0")

# متغير لتخزين كائن بوت التليجرام
telegram_bot: Optional[Bot] = None

def set_bot_instance(bot: Bot):
    global telegram_bot
    telegram_bot = bot

class SignalPayload(BaseModel):
    secret: Optional[str] = None
    ticker: Optional[str] = None
    symbol: Optional[str] = None
    action: Optional[str] = "BUY"
    timeframe: Optional[str] = "15m"
    interval: Optional[str] = None
    price: Optional[float] = None
    target1: Optional[float] = None
    target2: Optional[float] = None
    stop_loss: Optional[float] = None
    indicator: Optional[str] = None
    message: Optional[str] = None

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "EGX TradingView Webhook Signal Router",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/webhook")
async def receive_tradingview_signal(request: Request):
    """
    استقبال تنبيهات الويب هوك من TradingView وتوزيعها على المستخدمين المهتمين
    """
    global telegram_bot
    if not telegram_bot:
        raise HTTPException(status_code=503, detail="Telegram Bot is not initialized yet")

    # قراءة البيانات المرسلة سواء كانت JSON أو Raw Text
    try:
        raw_body = await request.body()
        body_str = raw_body.decode("utf-8", errors="ignore").strip()
        if not body_str:
            raise HTTPException(status_code=400, detail="Empty request body")
        
        # محاولة تحليل البيانات كـ JSON
        try:
            data = json.loads(body_str)
        except json.JSONDecodeError:
            # إذا أرسل TradingView نصاً وليس JSON
            data = {"message": body_str}
    except Exception as e:
        logger.error(f"خطأ في قراءة بيانات الويب هوك: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    # التحقق من كلمة السر إذا كانت مفعلة
    req_secret = data.get("secret")
    if WEBHOOK_SECRET and WEBHOOK_SECRET != "egx_secret_token_123":
        if req_secret != WEBHOOK_SECRET:
            logger.warning("محاولة اتصال بكلمة سر ويب هوك غير صحيحة")
            raise HTTPException(status_code=403, detail="Unauthorized: Invalid secret")

    # استخراج الرمز والفريم
    raw_ticker = data.get("ticker") or data.get("symbol") or ""
    raw_timeframe = data.get("timeframe") or data.get("interval") or "15m"
    action = str(data.get("action", "BUY")).strip().upper()
    
    clean_ticker = normalize_ticker(raw_ticker)
    clean_tf = normalize_timeframe(raw_timeframe)
    
    if not clean_ticker:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": "Ticker/Symbol is required in payload"}
        )

    # جلب معلومات السهم
    stock_info = db.get_stock(clean_ticker)
    stock_name_ar = stock_info["name_ar"] if stock_info else clean_ticker
    
    price = data.get("price")
    target1 = data.get("target1")
    target2 = data.get("target2")
    stop_loss = data.get("stop_loss")
    indicator = data.get("indicator") or "TradingView Strategy"
    user_msg = data.get("message") or ""

    # الوقت الحالي بتوقيت القاهرة
    try:
        cairo_tz = pytz.timezone(TIMEZONE)
        cairo_time = datetime.now(cairo_tz).strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        cairo_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    # تحديد الأيقونة واللون حسب نوع الإشارة
    is_buy = any(b in action for b in ["BUY", "شراء", "LONG"])
    action_title = "🟢 إشارة شراء (BUY)" if is_buy else "🔴 إشارة بيع (SELL)"

    # بناء نص الرسالة المنسقة للتليجرام
    msg_lines = [
        f"🚨 **{action_title}**",
        "",
        f"📈 **السهم:** `{clean_ticker}` - {stock_name_ar}",
        f"⏱️ **الفريم الزمني:** `{clean_tf}`",
    ]
    
    if price:
        msg_lines.append(f"💰 **سعر الدخول:** `{price:.2f}` ج.م")
    if target1:
        msg_lines.append(f"🎯 **الهدف الأول:** `{target1:.2f}` ج.م")
    if target2:
        msg_lines.append(f"🎯 **الهدف الثاني:** `{target2:.2f}` ج.م")
    if stop_loss:
        msg_lines.append(f"🛑 **وقف الخسارة:** `{stop_loss:.2f}` ج.م")
    if indicator:
        msg_lines.append(f"📊 **المؤشر:** {indicator}")
    if user_msg:
        msg_lines.append(f"📝 **تفاصيل:** {user_msg}")
        
    msg_lines.append(f"⏰ **التوقيت:** {cairo_time}")
    
    telegram_message = "\n".join(msg_lines)

    # البحث عن المستخدمين المطابقين لهذا السهم وهذا الفريم
    matching_users = db.get_users_for_signal(clean_ticker, clean_tf)
    
    # إرسال الرسالة لكل مستخدم مهتم
    sent_count = 0
    for uid in matching_users:
        try:
            await telegram_bot.send_message(
                chat_id=uid,
                text=telegram_message,
                parse_mode="Markdown"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"فشل إرسال الإشارة للمستخدم {uid}: {e}")

    # تسجيل الإشارة في قاعدة البيانات
    try:
        db.log_signal(
            symbol=clean_ticker,
            action="BUY" if is_buy else "SELL",
            timeframe=clean_tf,
            price=float(price) if price else None,
            target1=float(target1) if target1 else None,
            target2=float(target2) if target2 else None,
            stop_loss=float(stop_loss) if stop_loss else None,
            indicator=str(indicator) if indicator else None,
            raw_message=user_msg or body_str,
            notified_count=sent_count
        )
    except Exception as e:
        logger.error(f"خطأ في حفظ سجل الإشارة: {e}")

    return {
        "status": "success",
        "ticker": clean_ticker,
        "timeframe": clean_tf,
        "action": "BUY" if is_buy else "SELL",
        "matched_users": len(matching_users),
        "sent_count": sent_count
    }
