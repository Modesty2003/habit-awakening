import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "habit.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '觉醒者',
            total_exp INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            icon TEXT DEFAULT '⚡',
            base_exp INTEGER DEFAULT 100,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            exp_earned INTEGER DEFAULT 0,
            streak_count INTEGER DEFAULT 0,
            completed_at TEXT,
            UNIQUE(habit_id, date),
            FOREIGN KEY (habit_id) REFERENCES habits(id)
        );

        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT DEFAULT '🏆',
            cat TEXT DEFAULT '特殊',
            unlocked_at TEXT,
            is_unlocked INTEGER DEFAULT 0
        );
    """)

    # 迁移：旧表可能没有 cat 列
    try:
        cursor.execute("ALTER TABLE achievements ADD COLUMN cat TEXT DEFAULT '特殊'")
        conn.commit()
    except Exception:
        pass

    # Default user
    cursor.execute("INSERT OR IGNORE INTO users (id, name) VALUES (1, '觉醒者')")

    # Default habits
    cursor.execute("SELECT COUNT(*) FROM habits")
    if cursor.fetchone()[0] == 0:
        default_habits = [
            ("读书 / 学习",   "study",      "📚", 100, 0),
            ("运动 / 健身",   "exercise",   "🏃", 120, 1),
            ("深度专注工作",  "focus",      "⚡", 150, 2),
            ("自我反思写作",  "reflection", "✍️",  80, 3),
        ]
        cursor.executemany(
            "INSERT INTO habits (name, category, icon, base_exp, sort_order) VALUES (?, ?, ?, ?, ?)",
            default_habits,
        )

    # ── 完整成就列表（合并自习惯传说）────────────────────────────────────────
    ALL_ACHIEVEMENTS = [
        # 行动累计
        ("act_1",    "第一步",        "累计完成 1 次打卡",               "⚡",   "行动"),
        ("act_10",   "初见成效",      "累计完成 10 次打卡",              "🔟",   "行动"),
        ("act_50",   "五十践行",      "累计完成 50 次打卡",              "🎯",   "行动"),
        ("act_100",  "百次突破",      "累计完成 100 次打卡",             "💯",   "行动"),
        ("act_200",  "全力投球",      "累计 200 次·「投出灵魂的一球」",   "⚾",   "行动"),
        ("act_500",  "行动传说",      "累计完成 500 次打卡",             "🚀",   "行动"),
        ("act_1000", "Plus Ultra",   "累计 1000 次·「更进一步！」",      "👊",   "行动"),
        ("act_2000", "龙珠觉醒",      "累计 2000 次·超越极限",           "🐉",   "行动"),
        # 连续
        ("streak_3",   "三日之约",      "连续 3 天完成打卡",             "🔥",   "连续"),
        ("streak_7",   "周而复始",      "连续 7 天完成打卡",             "🔥",   "连续"),
        ("streak_14",  "排球少年",      "连续 14 天·再投一球",           "⚾",   "连续"),
        ("streak_21",  "王牌投手",      "连续 21 天·稳定登板的王牌！",   "🏐",   "连续"),
        ("streak_30",  "月度坚持",      "连续 30 天完成打卡",            "🌊",   "连续"),
        ("streak_60",  "不屈斗志",      "连续 60 天·越挫越勇",           "🗡️",  "连续"),
        ("streak_100", "百日传奇",      "连续 100 天完成打卡",           "👑",   "连续"),
        ("streak_200", "海贼王的意志",  "连续 200 天·追逐大秘宝",        "🏴‍☠️", "连续"),
        ("streak_365", "一整年的约定",  "连续 365 天·封神之路",          "☀️",   "连续"),
        # 等级
        ("level_5",   "初露锋芒",  "达到 Lv.5",                  "⭐",  "等级"),
        ("level_10",  "身份觉醒",  "达到 Lv.10",                 "🌟",  "等级"),
        ("level_20",  "身份大师",  "达到 Lv.20",                 "👑",  "等级"),
        ("level_30",  "超级赛亚人","Lv.30·突破战斗力极限",        "🔱",  "等级"),
        ("level_50",  "传奇存在",  "达到 Lv.50",                 "🏆",  "等级"),
        ("level_75",  "压力！！！","Lv.75·忍者最高境界",          "🉐",  "等级"),
        ("level_100", "钻石王牌",  "Lv.100·坚忍淡定有毅力的投球！","💎", "等级"),
        # 坚持天数
        ("days_7",   "周周确认", "累计打卡 7 天",   "📋", "坚持"),
        ("days_30",  "月月不落", "累计打卡 30 天",  "📅", "坚持"),
        ("days_60",  "两个月！", "累计打卡 60 天",  "🚀", "坚持"),
        ("days_100", "百日筑基", "累计打卡 100 天", "🏅", "坚持"),
        ("days_200", "二百之数", "累计打卡 200 天", "📜", "坚持"),
        ("days_365", "365的1%",  "累计打卡 365 天", "🌸", "坚持"),
        # 经验
        ("exp_1k",   "1%复利",   "总经验达到 1,000",   "📈", "经验"),
        ("exp_5k",   "原子蜕变", "总经验达到 5,000",   "💪", "经验"),
        ("exp_10k",  "身份革命", "总经验达到 10,000",  "🧬", "经验"),
        ("exp_50k",  "系统之力", "总经验达到 50,000",  "🔮", "经验"),
        ("exp_100k", "改变世界", "总经验达到 100,000", "🌍", "经验"),
        # 特殊
        ("first_checkin", "觉醒者",   "完成第一次打卡，踏上征途",   "🌱", "特殊"),
        ("perfect_day",   "完美一天", "单日完成全部习惯",           "✨", "特殊"),
        ("perfect_week",  "全垒打",   "一周内每天完成全部习惯",     "💫", "特殊"),
        ("burst_5",       "爆发日",   "单日完成 ≥5 个打卡",        "🌋", "特殊"),
        ("burst_10",      "极限突破", "单日完成 ≥10 个打卡",       "💥", "特殊"),
        ("comeback",      "浴火重生", "中断后重新开始连击",         "🔄", "特殊"),
    ]
    for key, name, desc, icon, cat in ALL_ACHIEVEMENTS:
        cursor.execute(
            """INSERT OR IGNORE INTO achievements (key, name, description, icon, cat)
               VALUES (?, ?, ?, ?, ?)""",
            (key, name, desc, icon, cat),
        )
        # 始终同步 name/description/icon/cat（支持旧数据迁移）
        cursor.execute(
            "UPDATE achievements SET name=?, description=?, icon=?, cat=? WHERE key=?",
            (name, desc, icon, cat, key),
        )

    # ── 护盾系统迁移 ──────────────────────────────────────────────────────────
    for col, default in [("shields", 0), ("last_shield_milestone", 0)]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT {default}")
            conn.commit()
        except Exception:
            pass

    # ── 护盾天数 & 挑战模式表 ──────────────────────────────────────────────────
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS shield_days (
            date TEXT PRIMARY KEY,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            target_days INTEGER DEFAULT 21,
            start_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (habit_id) REFERENCES habits(id)
        );
    """)

    conn.commit()
    conn.close()
