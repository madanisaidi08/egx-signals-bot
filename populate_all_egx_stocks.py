"""
سكريبت لجلب وتحديث كافة أسهم البورصة المصرية (EGX) من سكنر TradingView
وتضمينها بأسماء عربية وقطاعات واضحة داخل قاعدة بيانات البوت.
"""
import httpx
import sqlite3
import sys
import database as db

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SECTOR_MAP_AR = {
    'Finance': 'بنوك وخدمات مالية',
    'Process Industries': 'بتروكيماويات وصناعات كيماوية',
    'Producer Manufacturing': 'صناعة ومقاولات',
    'Non-Energy Minerals': 'حديد ومعادن ومواد بناء',
    'Health Technology': 'أدوية وصناعات دوائية',
    'Health Services': 'مستشفيات ورعاية صحية',
    'Consumer Non-Durables': 'أغذية ومشروبات وسلع استهلاكية',
    'Consumer Durables': 'منسوجات وسلع معمرة',
    'Consumer Services': 'سياحة وفنادق وترفيه',
    'Retail Trade': 'تجارة تجزئة وتوزيع',
    'Distribution Services': 'توزيع وخدمات لوجستية',
    'Transportation': 'شحن ونقل بحري ولوجستيات',
    'Communications': 'اتصالات',
    'Technology Services': 'تكنولوجيا ومدفوعات رقمية',
    'Electronic Technology': 'أجهزة إلكترونية وتكنولوجيا',
    'Utilities': 'مرافق وطاقة وكهرباء',
    'Energy Minerals': 'بترول وتعدين وطاقة',
    'Industrial Services': 'خدمات هندسية ومقاولات',
    'Commercial Services': 'خدمات تجارية واستثمار',
    'Miscellaneous': 'قطاعات أخرى'
}

# قاموس مخصص بالأسماء العربية المعتمدة في البورصة المصرية
KNOWN_ARABIC_NAMES = {
    "COMI": "البنك التجاري الدولي (CIB)",
    "TMGH": "مجموعة طلعت مصطفى القابضة",
    "HRHO": "إي إف جي القابضة (هيرميس)",
    "SWDY": "السويدي إليكتريك",
    "FWRY": "فوري للمدفوعات الإلكترونية",
    "ETEL": "المصرية للاتصالات (WE)",
    "EAST": "الشرقية - إيسترن كومباني",
    "EKHO": "المصرية الكويتية القابضة (دولار)",
    "EKHOA": "المصرية الكويتية القابضة (جنيه)",
    "ESRS": "حديد عز",
    "ABUK": "أبو قير للأسمدة والصناعات الكيماوية",
    "MFPC": "مصر لإنتاج الأسمدة (موبكو)",
    "SKPC": "سيدي كرير للبتروكيماويات (سيدبك)",
    "AMOC": "الإسكندرية للزيوت المعدنية (أموك)",
    "EGAL": "مصر للألومنيوم",
    "ORAS": "أوراسكوم للإنشاءات",
    "OCDI": "سوديك - السادس من أكتوبر للتنمية",
    "PHDC": "بالم هيلز للتعمير",
    "HELI": "مصر الجديدة للإسكان والتعمير",
    "MASR": "مدينة مصر للإسكان والتعمير",
    "MNHD": "مدينة مصر (مدينة نصر للإسكان)",
    "EMFD": "إعمار مصر للتنمية",
    "ORHD": "أوراسكوم للتنمية مصر",
    "ORWE": "النساجون الشرقيون",
    "ISPH": "ابن سينا فارما",
    "CCAP": "القلعة للاستشارات المالية",
    "BTFH": "بلتون المالية القابضة",
    "AUTO": "جي بي كوربوريشن (غبور)",
    "GBCO": "جي بي كوربوريشن (غبور أوتو)",
    "EFIH": "إي فاينانس للاستثمارات الرقمية",
    "JUFO": "جهينة للصناعات الغذائية",
    "ADIB": "مصرف أبوظبي الإسلامي - مصر",
    "CIEB": "بنك كريدي أجريكول مصر",
    "HDBK": "بنك التعمير والإسكان",
    "QNBA": "بنك قطر الوطني الأهلي (QNB)",
    "SAUD": "بنك فيصل الإسلامي المصري (جنيه)",
    "FAIT": "بنك فيصل الإسلامي المصري (دولار)",
    "EGBE": "البنك المصري الخليجي",
    "EBEK": "البنك المصري لتنمية الصادرات",
    "BBEK": "بنك البركة مصر",
    "CANA": "بنك قناة السويس",
    "ALCN": "الإسكندرية لتداول الحاويات",
    "CSAG": "القناة للتوكيلات الملاحية",
    "ARAB": "المطورون العرب القابضة",
    "RAYA": "راية القابضة للاستثمارات",
    "RACC": "راية لخدمات مراكز الاتصالات",
    "DSCW": "دايس للملابس الجاهزة",
    "CNFN": "كونتكت المالية القابضة",
    "POUL": "القاهرة للدواجن",
    "ISMA": "الإسماعيلية مصر للدواجن",
    "MAAL": "المنصورة للدواجن",
    "BINV": "بي إنفستمنتس القابضة",
    "ASCM": "أسيك للتعدين (أسكوم)",
    "TAQA": "طاقة عربية",
    "DOMT": "دومتي - الصناعات الغذائية العربية",
    "EFID": "إيديتا للصناعات الغذائية",
    "RMDA": "العاشر من رمضان للأدوية (راميدا)",
    "PHAR": "المصرية الدولية للصناعات الدوائية (إيبيكو)",
    "KIMA": "الصناعات الكيماوية المصرية (كيما)",
    "PRDC": "بايونيرز بروبرتيز للتنمية العمرانية",
    "AMER": "مجموعة عامر القابضة",
    "UNIT": "المتحدة للإسكان والتعمير",
    "ZMID": "زهراء المعادي للاستثمار والتعمير",
    "ELKA": "القاهرة للإسكان والتعمير",
    "ARCC": "العربية للأسمنت",
    "SCEM": "أسمنت سيناء",
    "MCQE": "مصر لأسمنت قنا",
    "SVCE": "جنوب الوادي للأسمنت",
    "ACGC": "العربية لحليج الأقطان",
    "RREI": "رواد السياحة - الرواد",
    "EGTS": "المصرية للمنتجعات السياحية",
    "CIRA": "القاهرة للخدمات التعليمية",
    "TALM": "تعليم لخدمات الإدارة",
    "CLHO": "مستشفيات كليوباترا",
    "MCRO": "ماكرو جروب للمستحضرات الطبية",
    "SPMD": "سبيد ميديكال",
    "MOIL": "الخدمات الملاحية والبترولية (ماريديف)",
    "ETRS": "إيجيترانس - المصرية لخدمات النقل",
    "VALU": "ڤاليو لخدمات التمويل",
    "ALUM": "العربية للألومنيوم",
    "ECAP": "العز للسيراميك والبورسلين (الجوهرة)",
    "PRCL": "العامة لصناعة الورق (راكتا)",
    "RAKT": "العامة لصناعة الورق (راكتا)",
    "KABO": "النصر للملابس والمنسوجات (كابو)",
    "ACRO": "أكرو مصر للشدات والسقالات المعدنية",
    "MIKC": "مطاحن مصر الوسطى",
    "WCDF": "مطاحن وسط وغرب الدلتا",
    "UEDA": "مطاحن مصر العليا",
    "EDLM": "مطاحن شرق الدلتا",
    "AFMC": "مطاحن الإسكندرية",
    "OLFI": "القاهرة للزيوت والصابون",
    "ZEOT": "الإسكندرية للزيوت والصابون",
    "SUGR": "الدلتا للسكر",
    "PACH": "البويات والصناعات الكيماوية (باكين)",
    "GDWA": "جدوى للتنمية الصناعية",
    "OFH": "أوراسكوم المالية القابضة",
    "OIH": "أوراسكوم للاستثمار القابضة",
    "AIH": "أرابية انفستمنتس هولدنج",
    "ODIN": "أودن للاستثمار والتنمية",
    "SMPP": "سماد مصر (إيجيفيرت)",
    "VERT": "فيركيم مصر للأسمدة",
    "DCRC": "الدلتا للإنشاء والتعمير",
    "GGCC": "الجيزة العامة للمقاولات",
    "UEGC": "الصعيد العامة للمقاولات",
    "NCCW": "النصر للأعمال المدنية",
    "SPIN": "الإسكندرية للغزل والنسيج (سبينالكس)"
}

def fetch_and_populate():
    print("⏳ جاري جلب قائمة كافة الأسهم المصرية من سكنر TradingView...")
    try:
        url = "https://scanner.tradingview.com/egypt/scan"
        payload = {
            "filter": [{"left": "exchange", "operation": "equal", "right": "EGX"}],
            "columns": ["name", "description", "sector", "industry"],
            "range": [0, 500]
        }
        res = httpx.post(url, json=payload, timeout=20)
        res.raise_for_status()
        items = res.json().get("data", [])
        print(f"✅ تم استلام {len(items)} سهماً من TradingView!")
    except Exception as e:
        print(f"❌ تعذر الاتصال بـ TradingView Scanner: {e}")
        return

    conn = db.get_connection()
    cursor = conn.cursor()
    
    added_count = 0
    updated_count = 0

    for item in items:
        # مثال: s='EGX:COMI', d=['COMI', 'Commercial International Bank', 'Finance', 'Banks']
        d = item.get("d", [])
        if not d:
            continue
        symbol = str(d[0]).strip().upper()
        desc = d[1] if len(d) > 1 and d[1] else symbol
        raw_sector = d[2] if len(d) > 2 and d[2] else "Miscellaneous"
        
        sector_ar = SECTOR_MAP_AR.get(raw_sector, raw_sector)
        
        # الاسم العربي
        if symbol in KNOWN_ARABIC_NAMES:
            name_ar = KNOWN_ARABIC_NAMES[symbol]
        else:
            # دمج الوصف بالإنجليزية مع القطاع
            name_ar = f"{desc}"

        cursor.execute("SELECT id FROM stocks WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE stocks SET name_ar = ?, sector = ?, is_active = 1 WHERE symbol = ?",
                (name_ar, sector_ar, symbol)
            )
            updated_count += 1
        else:
            cursor.execute(
                "INSERT INTO stocks (symbol, name_ar, sector, is_active) VALUES (?, ?, ?, 1)",
                (symbol, name_ar, sector_ar)
            )
            added_count += 1

    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM stocks")
    total_in_db = cursor.fetchone()[0]
    conn.close()

    print(f"🎉 تم تحديث قاعدة البيانات بنجاح:")
    print(f"🔹 الأسهم الجديدة المضافة: {added_count}")
    print(f"🔹 الأسهم المحدثة: {updated_count}")
    print(f"📊 إجمالي أسهم البورصة المصرية في النظام الآن: {total_in_db} سهم!")

if __name__ == "__main__":
    fetch_and_populate()
