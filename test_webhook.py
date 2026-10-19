"""
سكريبت لاختبار إرسال إشارات وهمية من TradingView إلى خادم الويب هوك
"""
import requests
import json
import sys
from config import WEBHOOK_PORT, WEBHOOK_SECRET

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

URL = f"http://127.0.0.1:{WEBHOOK_PORT}/webhook"

def send_test_signal(ticker="COMI", action="BUY", timeframe="15m", price=86.50):
    payload = {
        "secret": WEBHOOK_SECRET,
        "ticker": ticker,
        "action": action,
        "timeframe": timeframe,
        "price": price,
        "target1": round(price * 1.03, 2),
        "target2": round(price * 1.06, 2),
        "stop_loss": round(price * 0.97, 2),
        "indicator": "SuperTrend Indicator",
        "message": f"إشارة تجريبية لاختبار وصول التنبيه لسهم {ticker}"
    }
    
    print(f"🚀 جاري إرسال إشارة تجريبية لسهم {ticker} على فريم {timeframe}...")
    try:
        response = requests.post(URL, json=payload, timeout=5)
        print(f"الحالة: {response.status_code}")
        print("الرد:", response.json())
    except requests.exceptions.ConnectionError:
        print("❌ لم يتم الاتصال بالخادم. تأكد من تشغيل main.py أولاً!")

if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "COMI"
    tf = sys.argv[2] if len(sys.argv) > 2 else "15m"
    send_test_signal(ticker=ticker, timeframe=tf)
