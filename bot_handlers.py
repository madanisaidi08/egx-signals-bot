import logging
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import database as db
from egx_stocks import SUPPORTED_TIMEFRAMES, normalize_ticker
from config import ADMIN_USER_ID, WEBHOOK_PORT, WEBHOOK_SECRET

logger = logging.getLogger(__name__)

PAGE_SIZE = 8  # عدد الأسهم في كل صفحة في القائمة التفاعلية

def get_main_menu_keyboard(is_admin: bool = False, alerts_enabled: bool = True) -> InlineKeyboardMarkup:
    alert_icon = "🟢" if alerts_enabled else "🔴"
    alert_text = f"{alert_icon} حالة التنبيهات: {'مفعلة' if alerts_enabled else 'معطلة'}"
    
    keyboard = [
        [
            InlineKeyboardButton("📌 أسهمي المفضلة", callback_data="menu_stocks_hub"),
            InlineKeyboardButton("⏱️ الأطر الزمنية", callback_data="menu_timeframes")
        ],
        [
            InlineKeyboardButton(alert_text, callback_data="toggle_alerts"),
            InlineKeyboardButton("📊 آخر الإشارات", callback_data="menu_recent")
        ],
        [
            InlineKeyboardButton("ℹ️ حسابي واشتراكي", callback_data="menu_info")
        ]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 لوحة تحكم الإدارة (Admin)", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_stocks_hub_keyboard(user_id: int) -> InlineKeyboardMarkup:
    favs = db.get_user_stocks(user_id)
    keyboard = [
        [
            InlineKeyboardButton("🔥 أشهر 30 سهم (EGX 30)", callback_data="menu_egx30_0"),
            InlineKeyboardButton("📂 تصفح حسب القطاع", callback_data="menu_sectors")
        ],
        [
            InlineKeyboardButton(f"⭐ أسهمي المختارة ({len(favs)})", callback_data="menu_myfavs_0"),
            InlineKeyboardButton("🔍 بحث عن سهم", callback_data="prompt_search")
        ],
        [
            InlineKeyboardButton("📑 تصفح كافة الأسهم (300+ سهم)", callback_data="menu_stocks_0")
        ],
        [
            InlineKeyboardButton("➕ تفعيل كافة أسهم EGX 30 دفعة واحدة", callback_data="add_all_egx30")
        ],
        [
            InlineKeyboardButton("🧹 مسح كافة الأسهم المختارة", callback_data="clear_all_stocks"),
            InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_sectors_keyboard() -> InlineKeyboardMarkup:
    sectors = db.get_all_sectors()
    keyboard = []
    row = []
    for sec in sectors:
        row.append(InlineKeyboardButton(sec, callback_data=f"sec_{sec[:20]}_0"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 العودة لقائمة الأسهم", callback_data="menu_stocks_hub")])
    return InlineKeyboardMarkup(keyboard)

def get_stocks_keyboard(user_id: int, page: int = 0, sector: Optional[str] = None, my_favs_only: bool = False, egx30_only: bool = False, search: Optional[str] = None) -> InlineKeyboardMarkup:
    user_favs = set(db.get_user_stocks(user_id))
    
    if my_favs_only:
        all_stocks = [s for s in db.get_all_stocks() if s["symbol"] in user_favs]
        prefix = "myfavs"
    elif egx30_only:
        # أهم أسهم EGX30
        egx30_symbols = {"COMI", "TMGH", "HRHO", "SWDY", "FWRY", "ETEL", "EAST", "EKHO", "EKHOA", "ESRS",
                         "ABUK", "MFPC", "SKPC", "AMOC", "EGAL", "ORAS", "OCDI", "PHDC", "HELI", "MASR",
                         "MNHD", "EMFD", "ORHD", "ORWE", "ISPH", "CCAP", "BTFH", "AUTO", "EFIH", "JUFO",
                         "ADIB", "CIEB", "HDBK", "QNBA", "SAUD", "TAQA"}
        all_stocks = [s for s in db.get_all_stocks() if s["symbol"] in egx30_symbols]
        prefix = "egx30"
    elif sector:
        all_stocks = db.get_all_stocks(sector=sector)
        prefix = f"sec_{sector[:20]}"
    elif search:
        all_stocks = db.get_all_stocks(search=search)
        prefix = f"srch_{search[:15]}"
    else:
        all_stocks = db.get_all_stocks()
        prefix = "stocks"
    
    total_stocks = len(all_stocks)
    total_pages = max(1, (total_stocks + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_stocks)
    stocks_slice = all_stocks[start_idx:end_idx]
    
    keyboard = []
    row = []
    for stock in stocks_slice:
        sym = stock["symbol"]
        is_fav = sym in user_favs
        mark = "✅" if is_fav else "⬜"
        btn_text = f"{mark} {sym}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"stk_{sym}_{prefix}_{page}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"nav_{prefix}_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"📄 {page+1} / {total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"nav_{prefix}_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([
        InlineKeyboardButton("🔍 بحث آخر", callback_data="prompt_search"),
        InlineKeyboardButton("🔙 قائمة الأسهم", callback_data="menu_stocks_hub")
    ])
    return InlineKeyboardMarkup(keyboard)

def get_timeframes_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user_tfs = set(db.get_user_timeframes(user_id))
    keyboard = []
    row = []
    for tf in SUPPORTED_TIMEFRAMES:
        code = tf["code"]
        is_sel = code in user_tfs
        mark = "✅" if is_sel else "⬜"
        label_suffix = " (جلسة)" if code == "270m" else ""
        btn_text = f"{mark} {code}{label_suffix}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"tf_{code}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

# --- معالجة الأوامر الأساسية ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
        
    db_user = db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        auto_admin_id=ADMIN_USER_ID
    )
    
    sub_info = db.get_user_subscription_status(user.id)
    is_admin = bool(db_user["is_admin"])
    
    if not is_admin and not sub_info["is_active"]:
        if not db_user["is_approved"] and not sub_info.get("expires_at"):
            # مستخدم جديد بانتظار المراجعة
            await update.message.reply_text(
                f"👋 مرحباً بك يا {user.first_name} في بوت إشارات البورصة المصرية (EGX)!\n\n"
                f"⏳ **حسابك قيد المراجعة حالياً من قبل الإدارة.**\n"
                f"سيتم إشعارك فور تفعيل اشتراكك لتتمكن من اختيار أسهمك المفضلة والفريمات الزمنية.",
                parse_mode="Markdown"
            )
            
            # إشعار المدير مع خيارات مدة الاشتراك
            if ADMIN_USER_ID and ADMIN_USER_ID != user.id:
                try:
                    admin_kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("⚡ تفعيل شهر (30 يوم)", callback_data=f"adm_appr_{user.id}_30"),
                            InlineKeyboardButton("🗓️ 3 أشهر (90 يوم)", callback_data=f"adm_appr_{user.id}_90")
                        ],
                        [
                            InlineKeyboardButton("🌟 سنة (365 يوم)", callback_data=f"adm_appr_{user.id}_365"),
                            InlineKeyboardButton("♾️ اشتراك دائم", callback_data=f"adm_appr_{user.id}_0")
                        ],
                        [
                            InlineKeyboardButton("❌ رفض الطلب", callback_data=f"adm_deny_{user.id}")
                        ]
                    ])
                    username_str = f"@{user.username}" if user.username else "بدون معرف"
                    await context.bot.send_message(
                        chat_id=ADMIN_USER_ID,
                        text=(
                            f"🔔 **طلب انضمام جديد للبوت!**\n\n"
                            f"👤 الاسم: {user.full_name}\n"
                            f"🔗 المعرف: {username_str}\n"
                            f"🆔 ID: `{user.id}`\n\n"
                            f"اختر مدة الاشتراك لتفعيل حسابه:"
                        ),
                        reply_markup=admin_kb,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطأ في إشعار المدير: {e}")
            return
        else:
            # اشتراك منتهي الصلاحية أو تم إيقافه
            await update.message.reply_text(
                f"⚠️ **عذراً {user.first_name}!**\n\n"
                f"حالة اشتراكك: **{sub_info['status_text']}**\n\n"
                f"لتجديد اشتراكك ومتابعة إشارات البورصة، يرجى التواصل مع إدارة البوت.",
                parse_mode="Markdown"
            )
            return

    # المستخدم مفعل أو مسؤول
    alerts_on = bool(db_user["alerts_enabled"])
    is_admin = bool(db_user["is_admin"])
    
    fav_stocks = db.get_user_stocks(user.id)
    fav_tfs = db.get_user_timeframes(user.id)
    
    text = (
        f"👋 **مرحباً بك {user.first_name}!**\n\n"
        f"📊 **نظام إشارات البورصة المصرية (EGX)** المربوط مع TradingView.\n\n"
        f"🔹 **الأسهم المختارة:** {len(fav_stocks)} سهم\n"
        f"🔹 **الأطر الزمنية:** {', '.join(fav_tfs) if fav_tfs else 'لم تختر بعد'}\n"
        f"🔹 **حالة التنبيهات:** {'🟢 شغال' if alerts_on else '🔴 متوقف'}\n\n"
        f"يرجى استخدام الأزرار أدناه لتحديد مفضلتك والفريمات:"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=get_main_menu_keyboard(is_admin, alerts_on),
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "💡 **دليل استخدام البوت:**\n\n"
        "1️⃣ اضغط على **📌 أسهمي المفضلة** لاختيار الأسهم التي ترغب بمتابعتها من البورصة المصرية.\n"
        "2️⃣ اضغط على **⏱️ الأطر الزمنية** لتحديد الفريمات التي تهمك (مثل 15m, 1h, 1D).\n"
        "3️⃣ بمجرد وصول إشارة من TradingView مطابقة لأسهمك وفريماتك، ستصلك رسالة فورية مع كامل التفاصيل.\n"
        "4️⃣ يمكنك إيقاف واستئناف التنبيهات مؤقتاً بأي وقت عبر زر حالة التنبيهات.\n\n"
        "⚙️ الأوامر المتاحة:\n"
        "/start - القائمة الرئيسية\n"
        "/stocks - ضبط قائمة الأسهم المفضلة\n"
        "/timeframes - ضبط الفريمات الزمنية\n"
        "/recent - عرض آخر الإشارات الواردة\n"
        "/alerts - تشغيل / تعطيل التنبيهات\n"
        "/help - المساعدة"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- معالجة الأزرار التفاعلية (Callback Queries) ---

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    db_user = db.get_or_create_user(
        user_id=user_id,
        username=query.from_user.username,
        full_name=query.from_user.full_name,
        auto_admin_id=ADMIN_USER_ID
    )
    
    if not db_user["is_approved"] and not db_user["is_admin"]:
        await query.edit_message_text("⏳ حسابك قيد المراجعة حالياً من قبل الإدارة.")
        return

    is_admin = bool(db_user["is_admin"])
    alerts_on = bool(db_user["alerts_enabled"])

    # 1. القائمة الرئيسية
    if data == "main_menu":
        fav_stocks = db.get_user_stocks(user_id)
        fav_tfs = db.get_user_timeframes(user_id)
        text = (
            f"👋 **القائمة الرئيسية**\n\n"
            f"🔹 **الأسهم المختارة:** {len(fav_stocks)} سهم\n"
            f"🔹 **الأطر الزمنية:** {', '.join(fav_tfs) if fav_tfs else 'لم تختر بعد'}\n"
            f"🔹 **حالة التنبيهات:** {'🟢 شغال' if alerts_on else '🔴 متوقف'}\n\n"
            f"اختر من القائمة أدناه:"
        )
        await query.edit_message_text(text, reply_markup=get_main_menu_keyboard(is_admin, alerts_on), parse_mode="Markdown")
        return

    # --- إدارة واستعراض الأسهم ومحور الاختيارات ---
    if data == "menu_stocks_hub":
        favs = db.get_user_stocks(user_id)
        text = (
            f"📌 **إدارة ومتابعة أسهم البورصة المصرية (EGX)**\n\n"
            f"تم تزويد البوت بقاعدة بيانات كاملة تضم **أكثر من 300 شركة مصرية**.\n\n"
            f"🔹 عدد الأسهم في مفضلتك حالياً: `{len(favs)}` سهم\n"
            f"🔹 الأسهم المحددة: {', '.join(favs) if favs else 'لم تختر بعد'}\n\n"
            f"اختر الطريقة الأنسب لك لتحديد الأسهم التي ترغب بمراقبتها:"
        )
        await query.edit_message_text(text, reply_markup=get_stocks_hub_keyboard(user_id), parse_mode="Markdown")
        return

    if data == "menu_sectors":
        text = "📂 **اختر القطاع لعرض أسهمه وتحديد المفضلة:**"
        await query.edit_message_text(text, reply_markup=get_sectors_keyboard(), parse_mode="Markdown")
        return

    if data.startswith("sec_") and not data.startswith("sec_nav_"):
        parts = data.split("_")
        sec_name = parts[1]
        page = int(parts[2]) if len(parts) > 2 else 0
        favs = db.get_user_stocks(user_id)
        text = (
            f"📂 **قطاع: {sec_name}**\n\n"
            f"اضغط على رمز السهم لإضافته أو حذفه من مفضلتك.\n"
            f"✅ = سيصلك تنبيهاته | ⬜ = متجاهل\n\n"
            f"الأسهم المختارة ({len(favs)}): {', '.join(favs) if favs else 'لا يوجد'}"
        )
        await query.edit_message_text(text, reply_markup=get_stocks_keyboard(user_id, page, sector=sec_name), parse_mode="Markdown")
        return

    if data.startswith("menu_egx30_"):
        page = int(data.split("_")[2])
        favs = db.get_user_stocks(user_id)
        text = (
            f"🔥 **أهم 30 سهم في البورصة المصرية (EGX 30)**\n\n"
            f"اضغط على رمز السهم لإضافته أو حذفه من مفضلتك.\n"
            f"الأسهم المختارة ({len(favs)}): {', '.join(favs) if favs else 'لا يوجد'}"
        )
        await query.edit_message_text(text, reply_markup=get_stocks_keyboard(user_id, page, egx30_only=True), parse_mode="Markdown")
        return

    if data.startswith("menu_myfavs_"):
        page = int(data.split("_")[2])
        favs = db.get_user_stocks(user_id)
        if not favs:
            text = "⭐ **لم تقم باختيار أي أسهم مفضلة بعد!**\n\nيمكنك الاختيار من قائمة EGX 30 أو تصفح القطاعات أو استخدام البحث."
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة لقائمة الأسهم", callback_data="menu_stocks_hub")]])
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        text = f"⭐ **أسهمك المفضلة المختارة ({len(favs)} سهم):**\nاضغط على أي سهم لحذفه من المفضلة:"
        await query.edit_message_text(text, reply_markup=get_stocks_keyboard(user_id, page, my_favs_only=True), parse_mode="Markdown")
        return

    if data.startswith("menu_stocks_"):
        page = int(data.split("_")[2])
        favs = db.get_user_stocks(user_id)
        text = (
            f"📑 **كافة أسهم البورصة المصرية (300+ سهم)**\n\n"
            f"اضغط على رمز السهم للتبديل بين التفعيل والإلغاء:\n"
            f"الأسهم المختارة ({len(favs)}): {', '.join(favs) if favs else 'لا يوجد'}"
        )
        await query.edit_message_text(text, reply_markup=get_stocks_keyboard(user_id, page), parse_mode="Markdown")
        return

    # الضغط على سهم لتغيير حالته (Toggle Stock)
    if data.startswith("stk_"):
        # stk_{sym}_{prefix}_{page}
        parts = data.split("_")
        sym = parts[1]
        prefix = parts[2]
        page = int(parts[3])
        db.toggle_user_stock(user_id, sym)
        favs = db.get_user_stocks(user_id)
        
        if prefix == "egx30":
            text = f"🔥 **أهم 30 سهم في البورصة المصرية (EGX 30)**\n\nالأسهم المختارة ({len(favs)}): {', '.join(favs) if favs else 'لا يوجد'}"
            kb = get_stocks_keyboard(user_id, page, egx30_only=True)
        elif prefix == "myfavs":
            text = f"⭐ **أسهمك المفضلة المختارة ({len(favs)} سهم):**\nاضغط على أي سهم لتعديله:"
            kb = get_stocks_keyboard(user_id, page, my_favs_only=True)
        elif prefix.startswith("sec"):
            sec_name = parts[3] if len(parts) > 4 else parts[2].replace("sec", "").strip()
            # استخراج القطاع
            text = f"📂 **قطاع الأسهم**\n\nالأسهم المختارة ({len(favs)}): {', '.join(favs) if favs else 'لا يوجد'}"
            kb = get_stocks_keyboard(user_id, page, sector=sec_name if sec_name else None)
        elif prefix.startswith("srch"):
            search_query = parts[3] if len(parts) > 4 else parts[2].replace("srch", "").strip()
            text = f"🔍 **نتائج البحث عن:** `{search_query}`\n\nالأسهم المختارة ({len(favs)}): {', '.join(favs) if favs else 'لا يوجد'}"
            kb = get_stocks_keyboard(user_id, page, search=search_query)
        else:
            text = f"📑 **كافة أسهم البورصة المصرية**\n\nالأسهم المختارة ({len(favs)}): {', '.join(favs) if favs else 'لا يوجد'}"
            kb = get_stocks_keyboard(user_id, page)
            
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # التنقل بين الصفحات (Navigation)
    if data.startswith("nav_"):
        # nav_{prefix}_{page}
        parts = data.split("_")
        prefix = parts[1]
        page = int(parts[2])
        favs = db.get_user_stocks(user_id)
        
        if prefix == "egx30":
            text = f"🔥 **أهم 30 سهم في البورصة المصرية (EGX 30)**\n\nالأسهم المختارة ({len(favs)}): {', '.join(favs) if favs else 'لا يوجد'}"
            kb = get_stocks_keyboard(user_id, page, egx30_only=True)
        elif prefix == "myfavs":
            text = f"⭐ **أسهمك المفضلة المختارة ({len(favs)}):**"
            kb = get_stocks_keyboard(user_id, page, my_favs_only=True)
        elif prefix.startswith("sec"):
            text = f"📂 **تصفح قطاع الأسهم:**"
            kb = get_stocks_keyboard(user_id, page)
        else:
            text = f"📑 **كافة أسهم البورصة المصرية:**"
            kb = get_stocks_keyboard(user_id, page)
            
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # تفعيل كافة أسهم EGX30 دفعة واحدة
    if data == "add_all_egx30":
        egx30_symbols = ["COMI", "TMGH", "HRHO", "SWDY", "FWRY", "ETEL", "EAST", "EKHO", "EKHOA", "ESRS",
                         "ABUK", "MFPC", "SKPC", "AMOC", "EGAL", "ORAS", "OCDI", "PHDC", "HELI", "MASR",
                         "MNHD", "EMFD", "ORHD", "ORWE", "ISPH", "CCAP", "BTFH", "AUTO", "EFIH", "JUFO",
                         "ADIB", "CIEB", "HDBK", "QNBA", "SAUD", "TAQA"]
        db.add_multiple_user_stocks(user_id, egx30_symbols)
        favs = db.get_user_stocks(user_id)
        text = f"✅ **تمت إضافة كافة أسهم مؤشر EGX 30 إلى مفضلتك بنجاح!**\n\nإجمالي أسهمك المختارة الآن: **{len(favs)} سهم**."
        await query.answer("✅ تم تفعيل كافة أسهم EGX 30!")
        await query.edit_message_text(text, reply_markup=get_stocks_hub_keyboard(user_id), parse_mode="Markdown")
        return

    # مسح كافة الأسهم
    if data == "clear_all_stocks":
        for s in db.get_user_stocks(user_id):
            db.toggle_user_stock(user_id, s)
        text = "🧹 **تم إفراغ قائمة أسهمك المفضلة بالكامل.**"
        await query.edit_message_text(text, reply_markup=get_stocks_hub_keyboard(user_id), parse_mode="Markdown")
        return

    # طلب البحث
    if data == "prompt_search":
        context.user_data["awaiting_search"] = True
        text = (
            "🔍 **بحث سريع في أسهم البورصة المصرية:**\n\n"
            "أرسل اسم السهم أو كوده الآن في رسالة.\n"
            "أمثلة للبحث:\n"
            "• `COMI` أو `البنك التجاري`\n"
            "• `TMGH` أو `طلعت مصطفى`\n"
            "• `فوري` أو `FWRY`\n"
            "• `حديد` أو `السويدي` أو `طاقة`"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة لقائمة الأسهم", callback_data="menu_stocks_hub")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # 5. استعراض واختيار الفريمات الزمنية
    if data == "menu_timeframes":
        fav_tfs = db.get_user_timeframes(user_id)
        text = (
            f"⏱️ **الأطر الزمنية (Timeframes)**\n\n"
            f"حدد الفريمات التي ترغب باستلام إشاراتها فقط.\n"
            f"لن تصلك أي إشارة لفريم لم تقم بتحديده.\n\n"
            f"الفريمات المحددة: {', '.join(fav_tfs) if fav_tfs else 'لا يوجد'}"
        )
        await query.edit_message_text(text, reply_markup=get_timeframes_keyboard(user_id), parse_mode="Markdown")
        return

    # 6. الضغط على فريم زمني لتغيير حالته
    if data.startswith("tf_"):
        tf_code = data.split("_")[1]
        db.toggle_user_timeframe(user_id, tf_code)
        fav_tfs = db.get_user_timeframes(user_id)
        text = (
            f"⏱️ **الأطر الزمنية (Timeframes)**\n\n"
            f"حدد الفريمات التي ترغب باستلام إشاراتها فقط.\n"
            f"لن تصلك أي إشارة لفريم لم تقم بتحديده.\n\n"
            f"الفريمات المحددة: {', '.join(fav_tfs) if fav_tfs else 'لا يوجد'}"
        )
        await query.edit_message_text(text, reply_markup=get_timeframes_keyboard(user_id), parse_mode="Markdown")
        return

    # 7. تشغيل / إيقاف التنبيهات
    if data == "toggle_alerts":
        new_status = db.toggle_user_alerts(user_id)
        status_txt = "🟢 تم تفعيل التنبيهات بنجاح!" if new_status else "🔴 تم إيقاف التنبيهات مؤقتاً."
        await query.answer(status_txt, show_alert=True)
        # تحديث القائمة الرئيسية
        fav_stocks = db.get_user_stocks(user_id)
        fav_tfs = db.get_user_timeframes(user_id)
        text = (
            f"👋 **القائمة الرئيسية**\n\n"
            f"🔹 **الأسهم المختارة:** {len(fav_stocks)} سهم\n"
            f"🔹 **الأطر الزمنية:** {', '.join(fav_tfs) if fav_tfs else 'لم تختر بعد'}\n"
            f"🔹 **حالة التنبيهات:** {'🟢 شغال' if new_status else '🔴 متوقف'}\n\n"
            f"اختر من القائمة أدناه:"
        )
        await query.edit_message_text(text, reply_markup=get_main_menu_keyboard(is_admin, new_status), parse_mode="Markdown")
        return

    # 8. استعراض آخر الإشارات
    if data == "menu_recent":
        signals = db.get_recent_signals(user_id, limit=5)
        if not signals:
            text = "📊 **لا توجد إشارات سابقة مسجلة لأسهمك المفضلة حتى الآن.**"
        else:
            text = "📊 **آخر الإشارات الواردة لأسهمك:**\n\n"
            for s in signals:
                act_icon = "🟢 شراء (BUY)" if s["action"] == "BUY" else "🔴 بيع (SELL)"
                text += (
                    f"▫️ **{s['symbol']}** ({s['name_ar'] or ''})\n"
                    f"• النوع: {act_icon} | الفريم: `{s['timeframe']}`\n"
                    f"• السعر: `{s['price'] or '-'}`\n"
                    f"• الوقت: `{s['timestamp']}`\n"
                    f"------------------------\n"
                )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # 9. معلومات المستخدم واشتراكه
    if data == "menu_info":
        favs = db.get_user_stocks(user_id)
        tfs = db.get_user_timeframes(user_id)
        sub_info = db.get_user_subscription_status(user_id)
        
        status_line = sub_info.get("status_text", "ساري")
        exp_txt = f"• تاريخ الانتهاء: `{sub_info['expires_at']}`\n" if sub_info.get("expires_at") else ""
        
        text = (
            f"ℹ️ **بيانات الحساب والاشتراك:**\n\n"
            f"👤 الاسم: {query.from_user.full_name}\n"
            f"🆔 رقم المعرف (ID): `{user_id}`\n"
            f"🛡️ الصلاحية: `{'مسؤول (Admin)' if is_admin else 'مشترك'}`\n"
            f"⏳ حالة الاشتراك: **{status_line}**\n"
            f"{exp_txt}"
            f"📊 عدد الأسهم في المفضلة: `{len(favs)}` سهم\n"
            f"⏱️ الفريمات المختارة: `{', '.join(tfs) if tfs else 'لا يوجد'}`\n"
            f"🔔 استقبال التنبيهات: `{'مفعّل 🟢' if alerts_on else 'متوقف 🔴'}`"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # 10. مطالبة المستخدم بكتابة كود سهم لإضافته
    if data == "prompt_add_custom_stock":
        context.user_data["awaiting_stock_input"] = True
        text = (
            "📝 **إضافة سهم جديد لمفضلتك:**\n\n"
            "يرجى إرسال رمز السهم بالإنجليزية في رسالة الآن.\n"
            "مثال: `ORAS` أو `COMI` أو `EKHO`"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="menu_stocks_hub")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # --- لوحة تحكم المسؤول (Admin Panel) ---
    if data == "admin_panel" and is_admin:
        users = db.get_all_users()
        total_u = len(users)
        active_u = sum(1 for u in users if db.get_user_subscription_status(u["user_id"])["is_active"])
        pending_u = sum(1 for u in users if not u["is_approved"])
        expired_u = total_u - active_u - pending_u
        all_stocks = db.get_all_stocks()
        
        text = (
            f"👑 **لوحة تحكم المدير (Admin Dashboard)**\n\n"
            f"👥 إجمالي المستخدمين: `{total_u}`\n"
            f"🟢 المشتركون النشطون: `{active_u}`\n"
            f"⏳ طلبات معلقة: `{pending_u}`\n"
            f"🔴 اشتراكات منتهية / متوقفة: `{expired_u}`\n"
            f"📈 إجمالي أسهم البورصة المعرفة: `{len(all_stocks)}` سهم\n\n"
            f"اختر الإجراء المطلوب:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 إدارة المشتركين وتحديد الاشتراكات", callback_data="adm_subs_0")],
            [InlineKeyboardButton("⏳ طلبات الانضمام المعلقة", callback_data="adm_users_list")],
            [InlineKeyboardButton("➕ إضافة سهم جديد لقاعدة البيانات", callback_data="adm_add_stock")],
            [InlineKeyboardButton("🔗 رابط وتفاصيل الويب هوك", callback_data="adm_webhook_info")],
            [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # استعراض قائمة المشتركين للتحكم فيهم (صفحات)
    if data.startswith("adm_subs_") and is_admin:
        page = int(data.split("_")[2])
        users = db.get_all_users()
        SUB_PAGE_SIZE = 6
        total_pages = max(1, (len(users) + SUB_PAGE_SIZE - 1) // SUB_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        
        slice_users = users[page * SUB_PAGE_SIZE : (page + 1) * SUB_PAGE_SIZE]
        kb_rows = []
        for u in slice_users:
            st = db.get_user_subscription_status(u["user_id"])
            if st["is_admin"] or st.get("is_lifetime"):
                icon = "♾️"
            elif st["is_active"]:
                icon = "🟢"
            elif not u["is_approved"]:
                icon = "⏳"
            else:
                icon = "🔴"
            uname = f"@{u['username']}" if u['username'] else u['full_name'][:10]
            btn_txt = f"{icon} {u['full_name'][:12]} ({uname})"
            kb_rows.append([InlineKeyboardButton(btn_txt, callback_data=f"adm_usr_view_{u['user_id']}_{page}")])
            
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"adm_subs_{page-1}"))
        nav.append(InlineKeyboardButton(f"📄 {page+1} / {total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"adm_subs_{page+1}"))
        if nav:
            kb_rows.append(nav)
            
        kb_rows.append([InlineKeyboardButton("🔙 لوحة التحكم", callback_data="admin_panel")])
        text = (
            "👥 **إدارة المشتركين والتحكم في المدد الزمنية:**\n\n"
            "اضغط على أي مشترك لعرض ملفه، تمديد اشتراكه، أو إيقافه/إلغائه:\n"
            "🟢 نشط | 🔴 منتهي | ⏳ معلق | ♾️ دائم"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="Markdown")
        return

    # عرض تفاصيل مشترك محدد والتحكم باشتراكه
    if data.startswith("adm_usr_view_") and is_admin:
        parts = data.split("_")
        target_uid = int(parts[3])
        page = int(parts[4]) if len(parts) > 4 else 0
        
        target_user = None
        for u in db.get_all_users():
            if u["user_id"] == target_uid:
                target_user = u
                break
                
        if not target_user:
            await query.answer("المستخدم غير موجود!", show_alert=True)
            return
            
        st = db.get_user_subscription_status(target_uid)
        favs = db.get_user_stocks(target_uid)
        tfs = db.get_user_timeframes(target_uid)
        uname = f"@{target_user['username']}" if target_user['username'] else "بدون معرف"
        exp_txt = st.get("expires_at") or "دائم / غير محدد"
        
        text = (
            f"👤 **بيانات المشترك:**\n\n"
            f"• الاسم: {target_user['full_name']}\n"
            f"• المعرف: {uname}\n"
            f"• المعرف الرقمي (ID): `{target_uid}`\n"
            f"• حالة الاشتراك: **{st['status_text']}**\n"
            f"• تاريخ الانتهاء: `{exp_txt}`\n"
            f"• تاريخ التسجيل: `{target_user['created_at']}`\n"
            f"• الأسهم المفضلة: `{len(favs)}` سهم\n"
            f"• الفريمات: `{', '.join(tfs) if tfs else 'لا يوجد'}`\n\n"
            f"⚡ **خيارات التحكم في اشتراك هذا المستخدم:**"
        )
        
        actions_kb = [
            [
                InlineKeyboardButton("➕ تمديد 30 يوماً", callback_data=f"sub_ext_{target_uid}_30_{page}"),
                InlineKeyboardButton("➕ تمديد 90 يوماً", callback_data=f"sub_ext_{target_uid}_90_{page}")
            ],
            [
                InlineKeyboardButton("🌟 تمديد سنة (365)", callback_data=f"sub_ext_{target_uid}_365_{page}"),
                InlineKeyboardButton("♾️ تحويل لاشتراك دائم", callback_data=f"sub_set_{target_uid}_0_{page}")
            ],
            [
                InlineKeyboardButton("⏸️ إلغاء / إيقاف الاشتراك", callback_data=f"sub_cancel_{target_uid}_{page}"),
                InlineKeyboardButton("✅ إعادة تفعيل (شهر)", callback_data=f"sub_set_{target_uid}_30_{page}")
            ],
            [
                InlineKeyboardButton("🔙 عودة لقائمة المشتركين", callback_data=f"adm_subs_{page}")
            ]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(actions_kb), parse_mode="Markdown")
        return

    # تنفيذ عمليات التمديد والتعديل
    if data.startswith("sub_ext_") and is_admin:
        parts = data.split("_")
        target_uid = int(parts[2])
        days = int(parts[3])
        page = int(parts[4]) if len(parts) > 4 else 0
        
        new_exp = db.extend_user_subscription(target_uid, days)
        await query.answer(f"✅ تم تمديد الاشتراك بمقدار {days} يوماً بنجاح!", show_alert=True)
        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text=f"🎉 **تم تمديد اشتراكك في البوت بمقدار {days} يوماً إضافياً!**\n📅 موعد الانتهاء الجديد: `{new_exp}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        # تحديث الشاشة
        query.data = f"adm_usr_view_{target_uid}_{page}"
        return await callback_handler(update, context)

    if data.startswith("sub_set_") and is_admin:
        parts = data.split("_")
        target_uid = int(parts[2])
        days = int(parts[3])
        page = int(parts[4]) if len(parts) > 4 else 0
        
        db.set_user_subscription(target_uid, days if days > 0 else None)
        msg_alert = "✅ تم تحويل المشترك لاشتراك دائم بنجاح!" if days == 0 else f"✅ تم تفعيل الاشتراك لمدة {days} يوماً!"
        await query.answer(msg_alert, show_alert=True)
        try:
            dur_txt = "اشتراك دائم (Lifetime) ♾️" if days == 0 else f"{days} يوماً"
            await context.bot.send_message(
                chat_id=target_uid,
                text=f"🎉 **تم تحديث وتفعيل اشتراكك في البوت بنجاح!**\n⏳ المدة: **{dur_txt}**\nاضغط /start لضبط إعداداتك.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        query.data = f"adm_usr_view_{target_uid}_{page}"
        return await callback_handler(update, context)

    if data.startswith("sub_cancel_") and is_admin:
        parts = data.split("_")
        target_uid = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
        
        db.revoke_user(target_uid)
        await query.answer("❌ تم إلغاء / إيقاف اشتراك هذا المستخدم.", show_alert=True)
        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text="⚠️ **تم إيقاف اشتراكك في البوت.**\nيرجى التواصل مع الإدارة لمزيد من التفاصيل.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        query.data = f"adm_usr_view_{target_uid}_{page}"
        return await callback_handler(update, context)

    # قبول مستخدم مع تحديد المدة (من إشعار الأدمن)
    if data.startswith("adm_appr_") and is_admin:
        parts = data.split("_")
        target_uid = int(parts[2])
        days = int(parts[3]) if len(parts) > 3 else 30
        
        db.set_user_subscription(target_uid, days if days > 0 else None)
        dur_name = "اشتراك دائم ♾️" if days == 0 else f"{days} يوماً"
        await query.edit_message_text(f"✅ تم تفعيل حساب المستخدم `{target_uid}` لمدة **{dur_name}** بنجاح!", parse_mode="Markdown")
        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text=(
                    f"🎉 **تهانينا! تمت الموافقة على حسابك وتفعيله بنجاح.**\n\n"
                    f"⏳ **مدة اشتراكك:** {dur_name}\n\n"
                    f"اضغط /start لضبط أسهمك المفضلة والفريمات الزمنية."
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"فشل إشعار المستخدم بالتفعيل: {e}")
        return

    if data.startswith("adm_deny_") and is_admin:
        target_uid = int(data.split("_")[2])
        db.revoke_user(target_uid)
        await query.edit_message_text(f"❌ تم رفض المستخدم `{target_uid}`.")
        return

    # قائمة المستخدمين المعلقين
    if data == "adm_users_list" and is_admin:
        pending = db.get_pending_users()
        if not pending:
            text = "✅ **لا توجد أي طلبات مستخدمين معلقة حالياً.**"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="admin_panel")]])
        else:
            text = "⏳ **المستخدمون بانتظار التفعيل:**\n\nاختر مدة التفعيل لكل مستخدم:"
            kb_rows = []
            for u in pending[:5]:
                uname = f"@{u['username']}" if u['username'] else "بدون معرف"
                text += f"• {u['full_name']} ({uname}) - ID: `{u['user_id']}`\n"
                kb_rows.append([
                    InlineKeyboardButton(f"⚡ شهر لـ {u['full_name'][:8]}", callback_data=f"adm_appr_{u['user_id']}_30"),
                    InlineKeyboardButton(f"♾️ دائم", callback_data=f"adm_appr_{u['user_id']}_0"),
                    InlineKeyboardButton(f"❌ رفض", callback_data=f"adm_deny_{u['user_id']}")
                ])
            kb_rows.append([InlineKeyboardButton("🔙 لوحة التحكم", callback_data="admin_panel")])
            kb = InlineKeyboardMarkup(kb_rows)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # إضافة سهم لقاعدة البيانات كأدمن
    if data == "adm_add_stock" and is_admin:
        context.user_data["awaiting_admin_stock"] = True
        text = (
            "📈 **إضافة سهم جديد للنظام بالكامل:**\n\n"
            "أرسل رمز السهم واسمه بالعربي مفصولين بشرطة (-)\n"
            "مثال: `ETEL - المصرية للاتصالات`"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_panel")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # تفاصيل الويب هوك
    if data == "adm_webhook_info" and is_admin:
        text = (
            "🔗 **إعدادات الويب هوك لـ TradingView:**\n\n"
            f"▫️ **البورت (Port):** `{WEBHOOK_PORT}`\n"
            f"▫️ **المسار (Endpoint):** `/webhook`\n"
            f"▫️ **كلمة السر (Secret Token):** `{WEBHOOK_SECRET}`\n\n"
            "💡 ضع في خانة الـ Webhook URL داخل TradingView:\n"
            "`https://your-domain-or-ngrok.app/webhook`\n\n"
            "وتأكد أن رسالة التنبيه بصيغة JSON تحتوي على رمز السهم والفريم."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="admin_panel")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

# --- معالجة الرسائل النصية المباشرة (إدخال رمز سهم جديد) ---

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message or not update.message.text:
        return
        
    text = update.message.text.strip()
    
    # 1. حالة انتظار إدخال سهم للمفضلة من المستخدم
    if context.user_data.get("awaiting_stock_input"):
        context.user_data["awaiting_stock_input"] = False
        ticker = normalize_ticker(text)
        if not ticker:
            await update.message.reply_text("❌ رمز السهم غير صالح. يرجى المحاولة مجدداً.")
            return
            
        # التأكد من وجود السهم في قاعدة البيانات أو إضافته
        stock = db.get_stock(ticker)
        if not stock:
            db.add_stock(ticker, ticker, "أسهم مخصصة")
            
        db.toggle_user_stock(user.id, ticker)
        await update.message.reply_text(
            f"✅ تم إضافة السهم `{ticker}` إلى قائمة مفضلتك بنجاح!\n\nاضغط /stocks لمشاهدة القائمة.",
            parse_mode="Markdown"
        )
        return

    # 2. حالة انتظار إدخال سهم جديد للنظام من الأدمن
    if context.user_data.get("awaiting_admin_stock") and user.id == ADMIN_USER_ID:
        context.user_data["awaiting_admin_stock"] = False
        if "-" in text:
            parts = text.split("-", 1)
            sym = normalize_ticker(parts[0].strip())
            name_ar = parts[1].strip()
        else:
            sym = normalize_ticker(text)
            name_ar = sym
            
        success = db.add_stock(sym, name_ar)
        if success:
            await update.message.reply_text(f"✅ تم إضافة السهم `{sym}` ({name_ar}) إلى النظام بنجاح!")
        else:
            await update.message.reply_text(f"⚠️ السهم `{sym}` موجود مسبقاً في النظام.")
        return

    # 3. البحث التلقائي عند إرسال المستخدم لأي نص أو كود سهم
    results = db.get_all_stocks(search=text)
    if results:
        favs = db.get_user_stocks(user.id)
        msg_text = (
            f"🔍 **نتائج البحث عن:** `{text}` ({len(results)} نتيجة)\n\n"
            f"اضغط على السهم لإضافته أو حذفه من مفضلتك:\n"
            f"الأسهم المختارة ({len(favs)}): {', '.join(favs) if favs else 'لا يوجد'}"
        )
        kb = get_stocks_keyboard(user.id, 0, search=text)
        await update.message.reply_text(msg_text, reply_markup=kb, parse_mode="Markdown")
        return
    else:
        await update.message.reply_text(
            f"❌ لم يتم العثور على أي سهم يطابق: `{text}`\n\n"
            "💡 يمكنك البحث برمز السهم (مثل `COMI`) أو جزء من الاسم بالعربي (مثل `طلعت` أو `السويدي` أو `فوري`).",
            parse_mode="Markdown"
        )
        return

def setup_bot_handlers(application: Application):
    """تسجيل جميع الأوامر والمعالجات في تطبيق التليجرام"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stocks", lambda u, c: u.message.reply_text("📌 أسهمي المفضلة:", reply_markup=get_stocks_keyboard(u.effective_user.id, 0))))
    application.add_handler(CommandHandler("timeframes", lambda u, c: u.message.reply_text("⏱️ الأطر الزمنية:", reply_markup=get_timeframes_keyboard(u.effective_user.id))))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
