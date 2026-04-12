from datetime import date, timedelta
from typing import List, Dict, Any
import random


# ── 等级系统 ─────────────────────────────────────────────────────────────────

def level_threshold(level: int) -> int:
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
    cur = level_threshold(level)
    nxt = level_threshold(level + 1)
    cur_exp = total_exp - cur
    needed = nxt - cur
    return {
        "level": level,
        "current_exp": cur_exp,
        "exp_needed": needed,
        "progress": round(cur_exp / max(needed, 1) * 100, 1),
        "total_exp": total_exp,
        "title": get_level_title(level),
    }


# ── 连击 ─────────────────────────────────────────────────────────────────────

def calculate_streak_for_habit(habit_id: int, logs: list, today: date) -> int:
    done = {l["date"] for l in logs if l["habit_id"] == habit_id and l["completed"]}
    s = 0
    if str(today) in done:
        s = 1
    d = today - timedelta(days=1)
    while str(d) in done:
        s += 1
        d -= timedelta(days=1)
    return s


def calculate_global_streak(habits: list, logs: list, today: date) -> int:
    if not habits:
        return 0
    ids = {h["id"] for h in habits}

    def all_done(ds: str) -> bool:
        done = {l["habit_id"] for l in logs if l["date"] == ds and l["completed"]}
        return ids.issubset(done)

    s = 0
    if all_done(str(today)):
        s = 1
    d = today - timedelta(days=1)
    while all_done(str(d)):
        s += 1
        d -= timedelta(days=1)
    return s


# ── 动态 EXP ─────────────────────────────────────────────────────────────────

def calculate_dynamic_exp(base_exp: int, habit_id: int, logs: list, days: int = 30) -> int:
    """
    根据近 days 天该习惯的完成率动态调整 EXP。

    完成率 0%   → 1.5x（对你来说很难，多给激励）
    完成率 50%  → 1.0x（正常难度）
    完成率 100% → 0.5x（对你来说已经很容易了）

    数据少于 7 天时不调整，直接返回 base_exp。
    """
    today = date.today()
    cutoff = today - timedelta(days=days)
    habit_logs = [
        l for l in logs
        if l["habit_id"] == habit_id and date.fromisoformat(l["date"]) >= cutoff
    ]
    if len(habit_logs) < 7:
        return base_exp

    completed = sum(1 for l in habit_logs if l["completed"])
    rate = completed / days  # 分母固定用 days，未记录的天算 0
    multiplier = max(0.5, min(1.5, 1.5 - rate))
    return int(base_exp * multiplier)


def calculate_exp_with_streak(dynamic_exp: int, streak: int) -> int:
    """连击加成叠加在动态 EXP 上，最高 2.5x 基础"""
    multiplier = 1.0 + min(streak * 0.08, 1.5)
    return int(dynamic_exp * multiplier)


# ── 动量（EMA）───────────────────────────────────────────────────────────────

def calculate_momentum(logs: list, habits: list, days: int = 14) -> float:
    if not habits:
        return 0.0
    ids = {h["id"] for h in habits}
    today = date.today()
    alpha = 0.35
    ema = 0.0
    first = True
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        done = sum(1 for l in logs if l["date"] == str(d) and l["habit_id"] in ids and l["completed"])
        rate = done / len(ids)
        if first:
            ema = rate
            first = False
        else:
            ema = alpha * rate + (1 - alpha) * ema
    return round(ema * 100, 1)


# ── 坚持指数 ─────────────────────────────────────────────────────────────────

def calculate_consistency(logs: list, habits: list, days: int = 30) -> float:
    if not habits:
        return 0.0
    ids = {h["id"] for h in habits}
    today = date.today()
    done_set = {(l["habit_id"], l["date"]) for l in logs if l["completed"]}
    total = sum(
        1 for i in range(days) for hid in ids
        if (hid, str(today - timedelta(days=i))) in done_set
    )
    return round(total / max(len(ids) * days, 1) * 100, 1)


# ── 分类属性 ─────────────────────────────────────────────────────────────────

CATEGORY_META = {
    "study":      {"name": "智慧", "color": "#4A9EFF", "icon": "📚"},
    "exercise":   {"name": "体能", "color": "#FF6B35", "icon": "🏃"},
    "focus":      {"name": "专注", "color": "#FFD700", "icon": "⚡"},
    "reflection": {"name": "意志", "color": "#34C759", "icon": "✍️"},
}


def calculate_category_stats(logs: list, habits: list, days: int = 30) -> Dict:
    today = date.today()
    habit_cat = {h["id"]: h["category"] for h in habits}
    stats = {cat: {"done": 0, "total": 0} for cat in CATEGORY_META}
    for l in logs:
        if (today - date.fromisoformat(l["date"])).days > days:
            continue
        cat = habit_cat.get(l["habit_id"])
        if cat in stats:
            stats[cat]["total"] += 1
            if l["completed"]:
                stats[cat]["done"] += 1
    result = {}
    for cat, meta in CATEGORY_META.items():
        d = stats[cat]
        score = round(d["done"] / max(d["total"], 1) * 100)
        result[cat] = {**meta, "score": score, "done": d["done"], "total": d["total"]}
    return result


# ── 每周 BOSS 战 ─────────────────────────────────────────────────────────────

BOSS_NAMES = [
    ("拖延魔君",    "时间总在手机屏幕里悄悄流逝"),
    ("惰性之鬼",    "「等一下再做」是它最爱说的咒语"),
    ("懒散之王",    "舒适区是它的王座，你能推翻它吗？"),
    ("荒废之神",    "虚度的每一天都在壮大它的力量"),
    ("借口之主",    "它用一千个理由阻止你行动"),
    ("舒适恶魔",    "安逸是它编织的美丽牢笼"),
]


def calculate_weekly_boss(logs: list, habits: list, week_offset: int = 0) -> Dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7 * week_offset)
    week_end = week_start + timedelta(days=6)
    ids = [h["id"] for h in habits]
    if not ids:
        return {"won": False, "rate": 0, "boss_name": "?", "boss_desc": ""}
    days_passed = min((today - week_start).days + 1, 7)
    total_possible = len(ids) * days_passed
    done = sum(
        1 for l in logs
        if l["completed"] and week_start <= date.fromisoformat(l["date"]) <= week_end
    )
    rate = done / max(total_possible, 1)
    wk = (today - date(2024, 1, 1)).days // 7
    boss_name, boss_desc = BOSS_NAMES[wk % len(BOSS_NAMES)]
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


# ── 系统消息 ─────────────────────────────────────────────────────────────────

def generate_system_message(momentum: float, consistency: float, streak: int, level: int) -> str:
    if momentum >= 80:
        msgs = [
            f"【系统】势头指数 {momentum}，宿主处于【巅峰】状态！你正在燃烧！",
            f"【系统】连击 {streak} 天！每次打卡都是突破自我的证明，继续！",
        ]
    elif momentum >= 60:
        msgs = [
            f"【系统】势头指数 {momentum}，宿主处于【上升】状态。不要停下！",
            f"【系统】坚持指数 {consistency}%，你走在正确的路上！",
        ]
    elif momentum >= 40:
        msgs = [
            f"【系统】势头指数 {momentum}，状态【平稳】。突破平稳，才能冲破极限！",
            f"【系统】今天不想做，所以才去做——这才叫自律。",
        ]
    elif streak == 0:
        msgs = [
            "【系统警告】连击中断！但这不是终点，每个强者都曾跌倒过。重新出发！",
            "【系统】不管被打倒多少次，都要再站起来。——《钻石王牌》",
        ]
    else:
        msgs = [
            f"【系统】势头低迷，但谷底是反弹的起点。今天完成一件事，重新点燃！",
            "【系统】所谓天才，就是不断努力的人。——《钻石王牌》",
        ]
    return random.choice(msgs)


# ── 弱项检测 ─────────────────────────────────────────────────────────────────

def detect_weak_habits(cat_stats: dict) -> list:
    sorted_cats = sorted(cat_stats.items(), key=lambda x: x[1]["score"])
    return [{"category": k, **v} for k, v in sorted_cats if v["score"] < 60][:2]


# ── 累计统计（成就用）────────────────────────────────────────────────────────

def calculate_cumulative_stats(logs: list, habits: list, today: date) -> Dict:
    """计算成就检测所需的累计数据"""
    total_actions = sum(1 for l in logs if l["completed"])
    active_days = len({l["date"] for l in logs if l["completed"]})

    # 单日最多完成次数
    day_counts: Dict[str, int] = {}
    for l in logs:
        if l["completed"]:
            day_counts[l["date"]] = day_counts.get(l["date"], 0) + 1
    max_day = max(day_counts.values(), default=0)

    return {
        "total_actions": total_actions,
        "active_days": active_days,
        "max_day_completions": max_day,
    }
