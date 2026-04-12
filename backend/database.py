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
            unlocked_at TEXT,
            is_unlocked INTEGER DEFAULT 0
        );
    """)

    # Default user
    cursor.execute("INSERT OR IGNORE INTO users (id, name) VALUES (1, '觉醒者')")

    # Default habits
    cursor.execute("SELECT COUNT(*) FROM habits")
    if cursor.fetchone()[0] == 0:
        default_habits = [
            ("读书 / 学习", "study", "📚", 100, 0),
            ("运动 / 健身", "exercise", "🏃", 120, 1),
            ("深度专注工作", "focus", "⚡", 150, 2),
            ("自我反思写作", "reflection", "✍️", 80, 3),
        ]
        cursor.executemany(
            "INSERT INTO habits (name, category, icon, base_exp, sort_order) VALUES (?, ?, ?, ?, ?)",
            default_habits,
        )

    # Achievements
    achievements = [
        ("first_checkin", "觉醒者", "完成第一次打卡，踏上了征途", "🌟"),
        ("streak_3", "初显锋芒", "连续打卡3天，习惯开始生根", "🔥"),
        ("streak_7", "燃烧的意志", "连续打卡7天，七天不灭之火", "🔥🔥"),
        ("streak_14", "钢铁意志", "连续打卡14天，两周的坚持", "💪"),
        ("streak_30", "永不放弃的少年", "连续打卡30天，你就是传说", "👑"),
        ("perfect_day", "完美一天", "单日完成全部习惯，超越自我", "⚡"),
        ("perfect_week", "完美一周", "一周内每天完成全部习惯", "🌈"),
        ("level_5", "实力初现", "达到5级，觉醒已开始", "🦅"),
        ("level_10", "觉醒完成", "达到10级，脱胎换骨", "🏆"),
        ("level_20", "传说境界", "达到20级，你已超越常人", "👑"),
        ("boss_first_win", "初战告捷", "首次赢得每周BOSS战", "⚔️"),
        ("boss_streak_3", "连续击破", "连续3周赢得BOSS战", "🗡️"),
        ("exp_500", "百战余生", "累计获得500 EXP", "💫"),
        ("exp_2000", "千锤百炼", "累计获得2000 EXP", "💎"),
        ("comeback", "浴火重生", "中断后重新连击超过3天", "🔄"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO achievements (key, name, description, icon) VALUES (?, ?, ?, ?)",
        achievements,
    )

    conn.commit()
    conn.close()
