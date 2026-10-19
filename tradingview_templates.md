# دليل إعداد تنبيهات TradingView وربطها بالبوت

لتوصيل مؤشراتك أو استراتيجياتك في TradingView ببوت التليجرام الخاص بك، اتبع الخطوات التالية:

---

### 1. رابط الويب هوك (Webhook URL)
عند إنشاء تنبيه جديد في TradingView (Create Alert):
1. انتقل إلى تبويب **Notifications**.
2. فعّل خيار **Webhook URL**.
3. ضع الرابط العام الخاص بك (باستخدام Cloudflare Tunnel أو Ngrok أو رابط خادمك):
   ```text
   https://your-public-url.ngrok-free.app/webhook
   ```

---

### 2. صيغة الرسالة (Message) لتنبيهات المؤشرات العادية (Indicators)

في خانة **Message** داخل التنبيه، ضع كود الـ JSON التالي:

#### إشارة شراء (BUY):
```json
{
  "secret": "egx_secret_token_123",
  "ticker": "{{ticker}}",
  "action": "BUY",
  "timeframe": "{{interval}}",
  "price": {{close}},
  "indicator": "مؤشر السوبر تريند / الماكد",
  "message": "إشارة شراء جديدة ومؤكدة على سهم {{ticker}}"
}
```

#### إشارة بيع (SELL):
```json
{
  "secret": "egx_secret_token_123",
  "ticker": "{{ticker}}",
  "action": "SELL",
  "timeframe": "{{interval}}",
  "price": {{close}},
  "indicator": "مؤشر السوبر تريند / الماكد",
  "message": "إشارة خروج / بيع على سهم {{ticker}}"
}
```

---

### 3. صيغة الرسالة للاستراتيجيات التلقائية (Pine Script Strategies)

إذا كنت تستخدم استراتيجية بها أوامر `strategy.entry`:
```json
{
  "secret": "egx_secret_token_123",
  "ticker": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "timeframe": "{{interval}}",
  "price": {{strategy.order.price}},
  "indicator": "استراتيجيتي الخاصة",
  "message": "{{strategy.order.comment}}"
}
```

---

### المتغيرات المدعومة تلقائياً:
- `{{ticker}}`: يرسل رمز السهم (مثل `COMI` أو `TMGH`).
- `{{interval}}`: يرسل الفريم الزمني (مثل `15`, `60`, `D`). يقوم البوت تلقائياً بتحويله إلى `15m`, `1h`, `1D`.
- `{{close}}`: سعر الإغلاق الحالي للبارة.
- `secret`: كلمة السر المحددة في ملف `.env` لحماية الويب هوك.
