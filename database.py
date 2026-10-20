import sqlite3
import datetime
from typing import List, Dict, Optional, Tuple
from egx_stocks import DEFAULT_EGX_STOCKS, normalize_ticker, normalize_timeframe

DB_FILE = "egx_bot.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول وإدخال الأسهم الافتراضية"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # جدول المستخدمين
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            is_admin BOOLEAN DEFAULT 0,
            is_approved BOOLEAN DEFAULT 0,
            alerts_enabled BOOLEAN DEFAULT 1,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # إضافة عمود expires_at في حال كان الجدول موجوداً مسبقاً
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN expires_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        
        # جدول الأسهم
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            name_ar TEXT NOT NULL,
            sector TEXT DEFAULT 'عام',
            is_active BOOLEAN DEFAULT 1
        )
        """)
        
        # جدول مفضلة الأسهم لكل مستخدم
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_stocks (
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            PRIMARY KEY (user_id, symbol),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)
        
        # جدول الفريمات الزمنية المفضلة لكل مستخدم
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_timeframes (
            user_id INTEGER NOT NULL,
            timeframe TEXT NOT NULL,
            PRIMARY KEY (user_id, timeframe),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)
        
        # سجل الإشارات الواردة
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            price REAL,
            target1 REAL,
            target2 REAL,
            stop_loss REAL,
            indicator TEXT,
            raw_message TEXT,
            notified_count INTEGER DEFAULT 0
        )
        """)
        
        conn.commit()
        
        # تعبئة الأسهم الافتراضية إذا كان الجدول فارغاً
        cursor.execute("SELECT COUNT(*) as count FROM stocks")
        if cursor.fetchone()["count"] == 0:
            for s in DEFAULT_EGX_STOCKS:
                cursor.execute(
                    "INSERT OR IGNORE INTO stocks (symbol, name_ar, sector) VALUES (?, ?, ?)",
                    (s["symbol"].upper(), s["name_ar"], s.get("sector", "عام"))
                )
            conn.commit()

# --- إدارة المستخدمين ---

def get_or_create_user(user_id: int, username: Optional[str], full_name: Optional[str], auto_admin_id: Optional[int] = None) -> sqlite3.Row:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        is_admin = 1 if auto_admin_id and user_id == auto_admin_id else 0
        is_approved = 1 if is_admin else 0
        
        if not row:
            cursor.execute("""
            INSERT INTO users (user_id, username, full_name, is_admin, is_approved, alerts_enabled)
            VALUES (?, ?, ?, ?, ?, 1)
            """, (user_id, username or "", full_name or "", is_admin, is_approved))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone()
        else:
            # تحديث الاسم والمعرف إذا تغير
            if auto_admin_id and user_id == auto_admin_id and not row["is_admin"]:
                cursor.execute("UPDATE users SET is_admin = 1, is_approved = 1 WHERE user_id = ?", (user_id,))
                conn.commit()
            return row

def get_user_subscription_status(user_id: int) -> dict:
    """فحص حالة اشتراك المستخدم وموعد الانتهاء"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return {"exists": False, "is_active": False, "status_text": "غير مسجل"}
            
        is_admin = bool(row["is_admin"])
        is_approved = bool(row["is_approved"])
        expires_at = row["expires_at"]
        
        if not is_approved:
            return {
                "exists": True,
                "is_active": False,
                "is_admin": is_admin,
                "is_lifetime": False,
                "status_text": "معلق / بانتظار التفعيل ⏳",
                "days_left": 0,
                "expires_at": expires_at
            }
            
        if is_admin or expires_at is None:
            return {
                "exists": True,
                "is_active": True,
                "is_admin": is_admin,
                "is_lifetime": True,
                "status_text": "اشتراك دائم (Lifetime) ♾️",
                "days_left": None,
                "expires_at": None
            }
            
        try:
            exp_dt = datetime.datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
            now = datetime.datetime.now()
            if exp_dt > now:
                diff = exp_dt - now
                days = diff.days
                hours = diff.seconds // 3600
                return {
                    "exists": True,
                    "is_active": True,
                    "is_admin": False,
                    "is_lifetime": False,
                    "status_text": f"ساري 🟢 (متبقي {days} يوم و {hours} ساعة)",
                    "days_left": days,
                    "expires_at": expires_at
                }
            else:
                return {
                    "exists": True,
                    "is_active": False,
                    "is_admin": False,
                    "is_lifetime": False,
                    "status_text": f"منتهي الصلاحية 🔴 (انتهى في {expires_at[:10]})",
                    "days_left": 0,
                    "expires_at": expires_at
                }
        except Exception:
            return {
                "exists": True,
                "is_active": True,
                "is_admin": is_admin,
                "is_lifetime": False,
                "status_text": "ساري 🟢",
                "days_left": 30,
                "expires_at": expires_at
            }

def is_user_approved(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم مفعلاً واشتراكه ساري المفعول"""
    status = get_user_subscription_status(user_id)
    return status.get("is_active", False)

def is_user_admin(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return bool(row["is_admin"]) if row else False

def set_user_subscription(user_id: int, days: Optional[int] = 30) -> bool:
    """
    تحديد مدة اشتراك المستخدم:
    - days = None: اشتراك دائم
    - days > 0: اشتراك محدد بعدد الأيام
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if days is None or days <= 0:
            cursor.execute("UPDATE users SET is_approved = 1, expires_at = NULL WHERE user_id = ?", (user_id,))
        else:
            exp_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE users SET is_approved = 1, expires_at = ? WHERE user_id = ?", (exp_date, user_id))
        conn.commit()
        return cursor.rowcount > 0

def extend_user_subscription(user_id: int, days: int) -> Optional[str]:
    """تمديد اشتراك المستخدم بإضافة أيام"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT expires_at FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        current_exp = row["expires_at"]
        now = datetime.datetime.now()
        base_dt = now
        if current_exp:
            try:
                exp_dt = datetime.datetime.strptime(current_exp, "%Y-%m-%d %H:%M:%S")
                if exp_dt > now:
                    base_dt = exp_dt
            except ValueError:
                pass
                
        new_exp = (base_dt + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE users SET is_approved = 1, expires_at = ? WHERE user_id = ?", (new_exp, user_id))
        conn.commit()
        return new_exp

def approve_user(user_id: int, days: Optional[int] = 30) -> bool:
    """تفعيل اشتراك المستخدم بمدة معينة (افتراضياً شهر = 30 يوم)"""
    return set_user_subscription(user_id, days)

def revoke_user(user_id: int) -> bool:
    """إلغاء اشتراك المستخدم فوراً"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_approved = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_all_users() -> List[sqlite3.Row]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        return cursor.fetchall()

def get_pending_users() -> List[sqlite3.Row]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE is_approved = 0 ORDER BY created_at DESC")
        return cursor.fetchall()

def toggle_user_alerts(user_id: int) -> bool:
    """تبديل تشغيل/إيقاف استقبال التنبيهات للمستخدم"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT alerts_enabled FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False
        new_val = 0 if row["alerts_enabled"] else 1
        cursor.execute("UPDATE users SET alerts_enabled = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        return bool(new_val)

def is_alerts_enabled(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT alerts_enabled FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return bool(row["alerts_enabled"]) if row else False

# --- إدارة الأسهم والفريمات ---

def get_all_stocks(search: Optional[str] = None, sector: Optional[str] = None) -> List[sqlite3.Row]:
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM stocks WHERE 1=1"
        params = []
        if sector and sector != "ALL":
            query += " AND sector = ?"
            params.append(sector)
        if search:
            s = f"%{search.strip()}%"
            query += " AND (symbol LIKE ? OR name_ar LIKE ?)"
            params.extend([s, s])
        query += " ORDER BY symbol ASC"
        cursor.execute(query, params)
        return cursor.fetchall()

def get_all_sectors() -> List[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT sector FROM stocks WHERE sector IS NOT NULL AND sector != '' ORDER BY sector ASC")
        return [r["sector"] for r in cursor.fetchall()]

def add_stock(symbol: str, name_ar: str, sector: str = "عام") -> bool:
    clean_symbol = normalize_ticker(symbol)
    if not clean_symbol:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO stocks (symbol, name_ar, sector) VALUES (?, ?, ?)",
                           (clean_symbol, name_ar.strip(), sector.strip()))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def get_stock(symbol: str) -> Optional[sqlite3.Row]:
    clean_symbol = normalize_ticker(symbol)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stocks WHERE symbol = ?", (clean_symbol,))
        return cursor.fetchone()

def get_user_stocks(user_id: int) -> List[str]:
    """جلب قائمة رموز الأسهم المفضلة لمستخدم معين"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM user_stocks WHERE user_id = ? ORDER BY symbol ASC", (user_id,))
        return [r["symbol"] for r in cursor.fetchall()]

def toggle_user_stock(user_id: int, symbol: str) -> bool:
    """إضافة سهم للمفضلة إذا لم يكن موجوداً، أو حذفه إذا كان موجوداً. يرجع الحالة الجديدة (True=مضاف, False=محذوف)"""
    clean_symbol = normalize_ticker(symbol)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM user_stocks WHERE user_id = ? AND symbol = ?", (user_id, clean_symbol))
        exists = cursor.fetchone()
        if exists:
            cursor.execute("DELETE FROM user_stocks WHERE user_id = ? AND symbol = ?", (user_id, clean_symbol))
            conn.commit()
            return False
        else:
            cursor.execute("INSERT INTO user_stocks (user_id, symbol) VALUES (?, ?)", (user_id, clean_symbol))
            conn.commit()
            return True

def add_multiple_user_stocks(user_id: int, symbols: List[str]) -> int:
    """إضافة مجموعة أسهم للمستخدم دفعة واحدة"""
    with get_connection() as conn:
        cursor = conn.cursor()
        added = 0
        for s in symbols:
            clean = normalize_ticker(s)
            cursor.execute("INSERT OR IGNORE INTO user_stocks (user_id, symbol) VALUES (?, ?)", (user_id, clean))
            added += cursor.rowcount
        conn.commit()
        return added

def get_user_timeframes(user_id: int) -> List[str]:
    """جلب قائمة الفريمات الزمنية المفضلة لمستخدم معين"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timeframe FROM user_timeframes WHERE user_id = ?", (user_id,))
        return [r["timeframe"] for r in cursor.fetchall()]

def toggle_user_timeframe(user_id: int, timeframe: str) -> bool:
    """إضافة أو إزالة فريم من تفضيلات المستخدم. يرجع الحالة الجديدة (True=مضاف, False=محذوف)"""
    clean_tf = normalize_timeframe(timeframe)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM user_timeframes WHERE user_id = ? AND timeframe = ?", (user_id, clean_tf))
        exists = cursor.fetchone()
        if exists:
            cursor.execute("DELETE FROM user_timeframes WHERE user_id = ? AND timeframe = ?", (user_id, clean_tf))
            conn.commit()
            return False
        else:
            cursor.execute("INSERT INTO user_timeframes (user_id, timeframe) VALUES (?, ?)", (user_id, clean_tf))
            conn.commit()
            return True

# --- توجيه الإشارات (Signal Routing) ---

def get_users_for_signal(symbol: str, timeframe: str) -> List[int]:
    """
    إيجاد كافة المستخدمين المطابقين للإشارة:
    1. السهم في مفضلتهم.
    2. الفريم الزمني في مفضلتهم.
    3. المستخدم مفعل واشتراكه ساري المفعول (غير منتهي الصلاحية).
    4. التنبيهات مفعّلة لدى المستخدم (alerts_enabled = 1).
    """
    clean_symbol = normalize_ticker(symbol)
    clean_tf = normalize_timeframe(timeframe)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
        SELECT DISTINCT u.user_id, u.is_admin, u.expires_at
        FROM users u
        INNER JOIN user_stocks us ON u.user_id = us.user_id
        INNER JOIN user_timeframes ut ON u.user_id = ut.user_id
        WHERE u.is_approved = 1 
          AND u.alerts_enabled = 1
          AND us.symbol = ?
          AND ut.timeframe = ?
        """
        cursor.execute(query, (clean_symbol, clean_tf))
        rows = cursor.fetchall()
        
        valid_uids = []
        for r in rows:
            if r["is_admin"] or r["expires_at"] is None or str(r["expires_at"]) > now_str:
                valid_uids.append(r["user_id"])
        return valid_uids

# --- تسجيل واستعراض الإشارات ---

def log_signal(symbol: str, action: str, timeframe: str, price: Optional[float],
               target1: Optional[float], target2: Optional[float], stop_loss: Optional[float],
               indicator: Optional[str], raw_message: Optional[str], notified_count: int) -> int:
    clean_symbol = normalize_ticker(symbol)
    clean_tf = normalize_timeframe(timeframe)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO signals_log (symbol, action, timeframe, price, target1, target2, stop_loss, indicator, raw_message, notified_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (clean_symbol, action.upper(), clean_tf, price, target1, target2, stop_loss, indicator, raw_message, notified_count))
        conn.commit()
        return cursor.lastrowid

def get_recent_signals(user_id: Optional[int] = None, limit: int = 5) -> List[sqlite3.Row]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if user_id:
            # إشارات الأسهم المفضلة للمستخدم فقط
            query = """
            SELECT sl.*, s.name_ar FROM signals_log sl
            LEFT JOIN stocks s ON sl.symbol = s.symbol
            INNER JOIN user_stocks us ON sl.symbol = us.symbol
            WHERE us.user_id = ?
            ORDER BY sl.timestamp DESC
            LIMIT ?
            """
            cursor.execute(query, (user_id, limit))
        else:
            query = """
            SELECT sl.*, s.name_ar FROM signals_log sl
            LEFT JOIN stocks s ON sl.symbol = s.symbol
            ORDER BY sl.timestamp DESC
            LIMIT ?
            """
            cursor.execute(query, (limit,))
        return cursor.fetchall()
