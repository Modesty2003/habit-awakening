from datetime import date, timedelta
from typing import List


def check_and_unlock(conn, logs: list, habits: list, user: dict) -> List[dict]:
    """
    检查所有成就条件，解锁未达成的成就，返回新解锁列表
    """
    cursor = conn.cursor()
    cursor.execute("SELECT key, is_unlocked FROM achievements")
    achievement_map = {row["key"]: row["is_unlocked"] for row in cursor.fetchall()}

    today = date.today()
    habit_ids = {h["id"] for h in habits}
    total_exp = user["total_exp"]
    newly_unlocked = []

    def unlock(key: str):
        if not achievement_map.get(key):
            cursor.execute(
                "UPDATE achievements SET is_unlocked=1, unlocked_at=? WHERE key=?",
                (str(today), key),
            )
            cursor.execute("SELECT * FROM achievements WHERE key=?", (key,))
            row = cursor.fetchone()
            if row:
                newly_unlocked.append(dict(row))

    completed_set = {
        (log["habit_id"], log["date"])
        for log in logs if log["completed"]
    }
    all_logs_completed = [log for log in logs if log["completed"]]

    # 首次打卡
    if all_logs_completed:
        unlock("first_checkin")

    # 连击（全局：所有习惯都完成才算）
    if habit_ids:
        def all_done_on(d: date) -> bool:
            return habit_ids.issubset(
                {log["habit_id"] for log in logs
                 if log["date"] == str(d) and log["completed"]}
            )

        streak = 0
        check = today - timedelta(days=1)
        while all_done_on(check):
            streak += 1
            check -= timedelta(days=1)
        if all_done_on(today):
            streak += 1

        if streak >= 3:
            unlock("streak_3")
        if streak >= 7:
            unlock("streak_7")
        if streak >= 14:
            unlock("streak_14")
        if streak >= 30:
            unlock("streak_30")

        # 完美一天
        if all_done_on(today):
            unlock("perfect_day")

        # 完美一周
        week_start = today - timedelta(days=today.weekday())
        perfect_week = all(
            all_done_on(week_start + timedelta(days=i))
            for i in range(today.weekday() + 1)
        )
        if perfect_week and today.weekday() >= 0:
            unlock("perfect_week")

    # 等级成就
    from .analytics import get_level_info
    level_info = get_level_info(total_exp)
    level = level_info["level"]
    if level >= 5:
        unlock("level_5")
    if level >= 10:
        unlock("level_10")
    if level >= 20:
        unlock("level_20")

    # EXP 累计
    if total_exp >= 500:
        unlock("exp_500")
    if total_exp >= 2000:
        unlock("exp_2000")

    # 浴火重生：之前有记录，中断后今天重新开始
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    if habit_ids and all_logs_completed:
        today_done = any(
            log["date"] == str(today) and log["completed"] for log in logs
        )
        yesterday_any = any(
            log["date"] == str(yesterday) and log["completed"] for log in logs
        )
        two_ago_any = any(
            log["date"] == str(two_days_ago) and log["completed"] for log in logs
        )
        # 有历史记录 + 今天有打 + 昨天和前天都没打 → 浴火重生
        has_old_history = any(
            log["date"] < str(two_days_ago) and log["completed"] for log in logs
        )
        if today_done and not yesterday_any and not two_ago_any and has_old_history:
            unlock("comeback")

    conn.commit()
    return newly_unlocked
