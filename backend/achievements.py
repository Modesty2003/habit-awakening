from datetime import date, timedelta
from typing import List


def check_and_unlock(conn, logs: list, habits: list, user: dict) -> List[dict]:
    cursor = conn.cursor()
    cursor.execute("SELECT key, is_unlocked FROM achievements")
    ach_map = {r["key"]: r["is_unlocked"] for r in cursor.fetchall()}

    today = date.today()
    today_str = str(today)
    ids = {h["id"] for h in habits}
    total_exp = user["total_exp"]
    newly = []

    def unlock(key: str):
        if not ach_map.get(key):
            cursor.execute(
                "UPDATE achievements SET is_unlocked=1, unlocked_at=? WHERE key=?",
                (today_str, key),
            )
            cursor.execute("SELECT * FROM achievements WHERE key=?", (key,))
            row = cursor.fetchone()
            if row:
                newly.append(dict(row))

    # ── 累计数据 ──────────────────────────────────────────────────────────────
    total_actions = sum(1 for l in logs if l["completed"])
    active_days = len({l["date"] for l in logs if l["completed"]})
    day_counts: dict = {}
    for l in logs:
        if l["completed"]:
            day_counts[l["date"]] = day_counts.get(l["date"], 0) + 1
    max_day = max(day_counts.values(), default=0)

    # ── 全局连击 ──────────────────────────────────────────────────────────────
    def all_done(ds: str) -> bool:
        done = {l["habit_id"] for l in logs if l["date"] == ds and l["completed"]}
        return ids.issubset(done) if ids else False

    streak = 0
    if all_done(today_str):
        streak = 1
    d = today - timedelta(days=1)
    while all_done(str(d)):
        streak += 1
        d -= timedelta(days=1)

    # ── 等级 ──────────────────────────────────────────────────────────────────
    from .analytics import get_level_info
    level = get_level_info(total_exp)["level"]

    # ── 行动累计 ──────────────────────────────────────────────────────────────
    if total_actions >= 1:    unlock("act_1")
    if total_actions >= 10:   unlock("act_10")
    if total_actions >= 50:   unlock("act_50")
    if total_actions >= 100:  unlock("act_100")
    if total_actions >= 200:  unlock("act_200")
    if total_actions >= 500:  unlock("act_500")
    if total_actions >= 1000: unlock("act_1000")
    if total_actions >= 2000: unlock("act_2000")

    # ── 连续 ──────────────────────────────────────────────────────────────────
    if streak >= 3:   unlock("streak_3")
    if streak >= 7:   unlock("streak_7")
    if streak >= 14:  unlock("streak_14")
    if streak >= 21:  unlock("streak_21")
    if streak >= 30:  unlock("streak_30")
    if streak >= 60:  unlock("streak_60")
    if streak >= 100: unlock("streak_100")
    if streak >= 200: unlock("streak_200")
    if streak >= 365: unlock("streak_365")

    # ── 等级 ──────────────────────────────────────────────────────────────────
    if level >= 5:   unlock("level_5")
    if level >= 10:  unlock("level_10")
    if level >= 20:  unlock("level_20")
    if level >= 30:  unlock("level_30")
    if level >= 50:  unlock("level_50")
    if level >= 75:  unlock("level_75")
    if level >= 100: unlock("level_100")

    # ── 坚持天数 ──────────────────────────────────────────────────────────────
    if active_days >= 7:   unlock("days_7")
    if active_days >= 30:  unlock("days_30")
    if active_days >= 60:  unlock("days_60")
    if active_days >= 100: unlock("days_100")
    if active_days >= 200: unlock("days_200")
    if active_days >= 365: unlock("days_365")

    # ── 经验 ──────────────────────────────────────────────────────────────────
    if total_exp >= 1000:   unlock("exp_1k")
    if total_exp >= 5000:   unlock("exp_5k")
    if total_exp >= 10000:  unlock("exp_10k")
    if total_exp >= 50000:  unlock("exp_50k")
    if total_exp >= 100000: unlock("exp_100k")

    # ── 特殊 ──────────────────────────────────────────────────────────────────
    if total_actions >= 1:
        unlock("first_checkin")

    if ids and all_done(today_str):
        unlock("perfect_day")

    # 完美一周
    if ids:
        week_start = today - timedelta(days=today.weekday())
        if all(all_done(str(week_start + timedelta(days=i))) for i in range(today.weekday() + 1)):
            unlock("perfect_week")

    if max_day >= 5:  unlock("burst_5")
    if max_day >= 10: unlock("burst_10")

    # 浴火重生：有历史 + 今天有打 + 昨天前天都没打
    if total_actions > 0:
        yd = str(today - timedelta(days=1))
        d2 = str(today - timedelta(days=2))
        today_done = any(l["date"] == today_str and l["completed"] for l in logs)
        yd_done = any(l["date"] == yd and l["completed"] for l in logs)
        d2_done = any(l["date"] == d2 and l["completed"] for l in logs)
        old_done = any(l["date"] < d2 and l["completed"] for l in logs)
        if today_done and not yd_done and not d2_done and old_done:
            unlock("comeback")

    conn.commit()
    return newly
