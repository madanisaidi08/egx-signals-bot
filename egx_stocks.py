"""
قائمة الأسهم المصرية الأولية (EGX)
تحتوي على أشهر أسهم EGX30 و EGX70 مع رموزها وأسمائها باللغة العربية والإنجليزية.
يمكن للمدير إضافة أي أسهم جديدة لاحقاً من خلال البوت.
"""

DEFAULT_EGX_STOCKS = [
    {"symbol": "COMI", "name_ar": "البنك التجاري الدولي (CIB)", "sector": "بنوك"},
    {"symbol": "TMGH", "name_ar": "مجموعة طلعت مصطفى القابضة", "sector": "عقارات"},
    {"symbol": "HRHO", "name_ar": "إي إف جي القابضة (هيرميس)", "sector": "خدمات مالية"},
    {"symbol": "SWDY", "name_ar": "السويدي إليكتريك", "sector": "صناعة"},
    {"symbol": "FWRY", "name_ar": "فوري للمدفوعات الإلكترونية", "sector": "تكنولوجيا"},
    {"symbol": "ETEL", "name_ar": "المصرية للاتصالات", "sector": "اتصالات"},
    {"symbol": "EKHO", "name_ar": "المصرية الكويتية القابضة", "sector": "استثمار"},
    {"symbol": "ESRS", "name_ar": "حديد عز", "sector": "مواد أساسية"},
    {"symbol": "ABUK", "name_ar": "أبو قير للأسمدة", "sector": "بتروكيماويات"},
    {"symbol": "MFPC", "name_ar": "مصر لإنتاج الأسمدة (موبكو)", "sector": "بتروكيماويات"},
    {"symbol": "SKPC", "name_ar": "سيدي كرير للبتروكيماويات", "sector": "بتروكيماويات"},
    {"symbol": "AMOC", "name_ar": "الإسكندرية للزيوت المعدنية (أموك)", "sector": "بتروكيماويات"},
    {"symbol": "EGAL", "name_ar": "مصر للألومنيوم", "sector": "مواد أساسية"},
    {"symbol": "ORAS", "name_ar": "أوراسكوم للإنشاءات", "sector": "مقاولات"},
    {"symbol": "OCDI", "name_ar": "سوديك - السادس من أكتوبر للتنمية", "sector": "عقارات"},
    {"symbol": "PHDC", "name_ar": "بالم هيلز للتعمير", "sector": "عقارات"},
    {"symbol": "HELI", "name_ar": "مصر الجديدة للإسكان والتعمير", "sector": "عقارات"},
    {"symbol": "MNHD", "name_ar": "مدينة مصر للإسكان والتعمير", "sector": "عقارات"},
    {"symbol": "EMFD", "name_ar": "إعمار مصر للتنمية", "sector": "عقارات"},
    {"symbol": "ORHD", "name_ar": "أوراسكوم للتنمية مصر", "sector": "عقارات"},
    {"symbol": "ORWE", "name_ar": "النساجون الشرقيون", "sector": "منسوجات"},
    {"symbol": "ISPH", "name_ar": "ابن سينا فارما", "sector": "رعاية صحية وأدوية"},
    {"symbol": "CCAP", "name_ar": "القلعة للاستثمارات المالية", "sector": "خدمات مالية"},
    {"symbol": "BTFH", "name_ar": "بلتون المالية القابضة", "sector": "خدمات مالية"},
    {"symbol": "AUTO", "name_ar": "جي بي كوربوريشن (غبور)", "sector": "سيارات"},
    {"symbol": "EFIH", "name_ar": "إي فاينانس للاستثمارات الرقمية", "sector": "تكنولوجيا"},
    {"symbol": "JUFO", "name_ar": "جهينة للصناعات الغذائية", "sector": "أغذية ومشروبات"},
    {"symbol": "ADIB", "name_ar": "مصرف أبوظبي الإسلامي - مصر", "sector": "بنوك"},
    {"symbol": "CIEB", "name_ar": "بنك كريدي أجريكول مصر", "sector": "بنوك"},
    {"symbol": "HDBK", "name_ar": "بنك التعمير والإسكان", "sector": "بنوك"},
    {"symbol": "QNBA", "name_ar": "بنك قطر الوطني الأهلي (QNB)", "sector": "بنوك"},
    {"symbol": "SAUD", "name_ar": "بنك فيصل الإسلامي المصري", "sector": "بنوك"},
    {"symbol": "ALCN", "name_ar": "الإسكندرية لتداول الحاويات", "sector": "شحن ونقل"},
    {"symbol": "ARAB", "name_ar": "المطورون العرب القابضة", "sector": "عقارات"},
    {"symbol": "RAYA", "name_ar": "راية القابضة", "sector": "تكنولوجيا"},
    {"symbol": "DSCW", "name_ar": "دايس للملابس الجاهزة", "sector": "منسوجات"},
    {"symbol": "CNFN", "name_ar": "كونتكت المالية القابضة", "sector": "خدمات مالية"},
    {"symbol": "POUL", "name_ar": "القاهرة للدواجن", "sector": "أغذية ومشروبات"},
    {"symbol": "BINV", "name_ar": "بي إنفستمنتس القابضة", "sector": "خدمات مالية"},
    {"symbol": "ASCM", "name_ar": "أسيك للتعدين (أسكوم)", "sector": "تعدين"}
]

# قائمة الفريمات المدعومة
SUPPORTED_TIMEFRAMES = [
    {"code": "15m", "label": "⏱️ 15 دقيقة (15m)", "aliases": ["15", "15m", "15M"]},
    {"code": "30m", "label": "⏱️ 30 دقيقة (30m)", "aliases": ["30", "30m", "30M"]},
    {"code": "1h", "label": "🕐 1 ساعة (1h)", "aliases": ["60", "1h", "1H", "60m"]},
    {"code": "4h", "label": "🕓 4 ساعات (4h)", "aliases": ["240", "4h", "4H", "240m"]},
    {"code": "1D", "label": "📅 يومي (1D)", "aliases": ["1D", "D", "1d", "d", "day", "daily"]},
    {"code": "1W", "label": "📆 أسبوعي (1W)", "aliases": ["1W", "W", "1w", "w", "week", "weekly"]}
]

def normalize_timeframe(tf_input: str) -> str:
    """تحويل أي صيغة فريم تأتي من TradingView للصيغة الموحدة"""
    if not tf_input:
        return ""
    clean_tf = str(tf_input).strip().lower()
    for tf in SUPPORTED_TIMEFRAMES:
        for alias in tf["aliases"]:
            if clean_tf == alias.lower():
                return tf["code"]
    return tf_input.upper()

def normalize_ticker(ticker_input: str) -> str:
    """
    استخراج رمز السهم النقي من TradingView
    مثال: EGX:COMI -> COMI
          COMI.CA -> COMI
          COMI -> COMI
    """
    if not ticker_input:
        return ""
    ticker = str(ticker_input).strip().upper()
    if ":" in ticker:
        ticker = ticker.split(":")[-1]
    if "." in ticker:
        ticker = ticker.split(".")[0]
    return ticker
