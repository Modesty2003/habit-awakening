from datetime import date, timedelta
from typing import List, Dict, Any
import random


# ── 等级系统 ────────────────────────────────────────────────────────────────

def level_threshold(level: int) -> int:
    """到达 level 级所需的累计 EXP"""
    if level <= 1:
        return 0
    return int(250 * (level - 1) ** 1.65)


def get_level_title(level: int) -> str:
    milestones = [
        (30, "传说者"), (20, "王者"), (15, "精英"),
        (10, "觉醒完成"), (7, "强化者"), (5, "实力者"),
        (3, "进化者"), (2, "觉醒者"), (1, "普通人"),
    ]
    for threshold, title in milestones:
        if level >= threshold:
            return title
    return "普通人"


def get_level_info(total_exp: int) -> Dict:
    level = 1
    while total_exp >= level_threshold(level + 1):
        level += 1

    current_threshold = level_threshold(level)
    next_threshold = level_threshold(level + 1)
    current_exp = total_exp - current_threshold
    exp_needed = next_threshold - current_threshold

    return {
        "level": level,
        "current_exp": current_exp,
        "exp_needed": exp_needed,
        "progress": round(current_exp / max(exp_needed, 1) * 100, 1),
        "total_exp": total_exp,
        "title": get_level_title(level),
    }


# ── 连击与 EXP ──────────────────────────────────────────────────────────────

def calculate_streak_for_habit(habit_id: int, logs: list, today: date) -> int:
    """计算某个习惯的当前连击天数"""
    completed_dates = {
        log["date"] for log in logs
        if log["habit_id"] == habit_id and log["completed"]
    }
    streak = 0
    check = today - timedelta(days=1)  # 从昨天往前算
    while str(check) in completed_dates:
        streak += 1
        check -= timedelta(days=1)
    # 如果今天已完成，也算入连击
    if str(today) in completed_dates:
        streak += 1
    return streak


def calculate_global_streak(habits: list, logs: list, today: date) -> int:
    """全局连击：当天完成所有习惯才算"""
    if not habits:
        return 0
    habit_ids = {h["id"] for h in habits}

    def all_done_on(d: date) -> bool:
        done = {log["habit_id"] for log in logs
                if log["date"] == str(d) and log["completed"]}
        return habit_ids.issubset(done)

    streak = 0
    check = today - timedelta(days=1)
    while all_done_on(check):
        streak += 1
        check -= timedelta(days=1)
    if all_done_on(today):
        streak += 1
    return streak


def calculate_exp_with_streak(base_exp: int, streak: int) -> int:
    """连击加成，最高 2.5 倍"""
    multiplier = 1.0 + min(streak * 0.08, 1.5)
    return int(base_exp * multiplier)


# ── 动量（势头）── EMA ───────────────────────────────────────────────────────

def calculate_momentum(logs: list, habits: list, days: int = 14) -> float:
    """
    用指数移动平均（α=0.35）计算最近 days 天的完成率势头。
    返回 0-100 的分数。
    """
    if not habits:
        return 0.0
    habit_ids = {h["id"] for h in habits}
    today = date.today()

    daily_rates = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        done = sum(
            1 for log in logs
            if log["date"] == str(d) and log["habit_id"] in habit_ids and log["completed"]
        )
        rate = done / len(habit_ids) if habit_ids else 0
        daily_rates.append(rate)

    if not daily_rates:
        return 0.0

    alpha = 0.35
    ema = daily_rates[0]
    for rate in daily_rates[1:]:
        ema = alpha * rate + (1 - alpha) * ema

    return round(ema * 100, 1)


# ── 坚持指数 ─────────────────────────────────────────────────────────────────

def calculate_consistency(logs: list, habits: list, days: int = 30) -> float:
    """30 天滚动完成率"""
    if not habits:
        return 0.0
    habit_ids = {h["id"] for h in habits}
    today = date.today()
    total_possible = len(habit_ids) * days
    completed_set = {
        (log["habit_id"], log["date"])
        for log in logs if log["completed"]
    }
    total_done = sum(
        1 for i in range(days)
        for hid in habit_ids
        if (hid, str(today - timedelta(days=i))) in completed_set
    )
    return round(total_done / max(total_possible, 1) * 100, 1)


# ── 分类属性 ─────────────────────────────────────────────────────────────────

CATEGORY_META = {
    "study":      {"name": "智慧", "color": "#4A9EFF", "icon": "📚"},
    "exercise":   {"name": "体能", "color": "#FF6B35", "icon": "🏃"},
    "focus":      {"name": "专注", "color": "#FFD700", "icon": "⚡"},
    "reflection": {"name": "意志", "color": "#34C759", "icon": "✍️"},
}


def calculate_category_stats(logs: list, habits: list, days: int = 30) -> Dict:
    today = date.today()
    habit_category = {h["id"]: h["category"] for h in habits}
    stats = {cat: {"done": 0, "total": 0} for cat in CATEGORY_META}

    for log in logs:
        log_date = date.fromisoformat(log["date"])
        if (today - log_date).days > days:
            continue
        cat = habit_category.get(log["habit_id"])
        if cat in stats:
            stats[cat]["total"] += 1
            if log["completed"]:
                stats[cat]["done"] += 1

    result = {}
    for cat, meta in CATEGORY_META.items():
        d = stats[cat]
        score = round(d["done"] / max(d["total"], 1) * 100)
        result[cat] = {**meta, "score": score, "done": d["done"], "total": d["total"]}
    return result


# ── 每周 BOSS 战 ─────────────────────────────────────────────────────────────

BOSS_NAMES = [
    ("拖延魔君", "时间总在手机屏幕里悄悄流逝"),
    ("惰性之鬼", "「等一下再做」是它最爱说的咒语"),
    ("懒散之王", "舒适区是它的王座，你能推翻它吗？"),
    ("荒废之神", "虚度的每一天都在壮大它的力量"),
    ("借口之主", "它用一千个理由阻止你行动"),
    ("舒适恶魔", "安逸是它编织的美丽牢笼"),
]


def calculate_weekly_boss(logs: list, habits: list, week_offset: int = 0) -> Dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7 * week_offset)
    week_end = week_start + timedelta(days=6)
    habit_ids = [h["id"] for h in habits]

    if not habit_ids:
        return {"won": False, "rate": 0, "boss_name": "?", "boss_desc": ""}

    days_passed = min((today - week_start).days + 1, 7)
    total_possible = len(habit_ids) * days_passed
    total_done = sum(
        1 for log in logs
        if log["completed"] and week_start <= date.fromisoformat(log["date"]) <= week_end
    )
    rate = total_done / max(total_possible, 1)

    week_num = (today - date(2024, 1, 1)).days // 7
    boss_name, boss_desc = BOSS_NAMES[week_num % len(BOSS_NAMES)]

    return {
        "won": rate >= 0.8,
        "rate": round(rate * 100),
        "boss_name": boss_name,
        "boss_desc": boss_desc,
        "week_start": str(week_start),
        "week_end": str(week_end),
        "target": 80,
        "days_passed": days_passed,
    }


# ── 系统消息生成 ─────────────────────────────────────────────────────────────

def generate_system_message(
    momentum: float, consistency: float, streak: int, level: int
) -> str:
    if momentum >= 80:
        msgs = [
            f"【系统】势头指数 {momentum}，宿主处于【巅峰】状态！现在的你如同冲向终点的飞行员！",
            f"【系统】连击 {streak} 天！每一次打卡都是你突破自己的证明，继续！",
            f"【系统】坚持指数 {consistency}%，表现卓越。系统检测到宿主正在觉醒！",
        ]
    elif momentum >= 60:
        msgs = [
            f"【系统】势头指数 {momentum}，宿主处于【上升】状态。不要停下！",
            f"【系统】坚持指数 {consistency}%，你正走在正确的道路上，脚步再稳一些！",
            f"【系统】检测到稳定成长。Lv.{level} 的宿主，实力正在积累中！",
        ]
    elif momentum >= 40:
        msgs = [
            f"【系统】势头指数 {momentum}，状态【平稳】。突破平稳，才能冲破极限！",
            f"【系统】平稳不等于退步，但你需要点燃那股热血——今天多做一件事！",
            f"【系统警告】坚持指数 {consistency}%，有提升空间。宿主，是时候发力了！",
        ]
    elif streak == 0:
        msgs = [
            "【系统警告】连击中断！但这不是终点，每个王者都曾经跌倒过。重新出发！",
            "【系统】势头跌入低谷，但谷底正是反弹的起点。今天完成一件事，重新点燃！",
            "【系统】检测到宿主状态低迷。提示：最困难的一步，永远是从零到一。",
        ]
    else:
        msgs = [
            f"【系统】势头指数 {momentum}，需要提振。宿主！现在就行动，不是明天！",
            f"【系统警告】坚持指数 {consistency}%，低于警戒线。你的潜力远不止于此！",
        ]
    return random.choice(msgs)


# ── 弱项检测 ─────────────────────────────────────────────────────────────────

def detect_weak_habits(category_stats: dict) -> list:
    sorted_cats = sorted(category_stats.items(), key=lambda x: x[1]["score"])
    return [
        {"category": k, **v}
        for k, v in sorted_cats
        if v["score"] < 60
    ][:2]
