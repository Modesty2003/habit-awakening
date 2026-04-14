from datetime import date, timedelta
from typing import List, Dict, Any, Optional
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


def calculate_global_streak(habits: list, logs: list, today: date, shield_dates=None) -> int:
    if not habits:
        return 0
    ids = {h["id"] for h in habits}
    _shields = set(shield_dates) if shield_dates else set()

    def all_done(ds: str) -> bool:
        if ds in _shields:
            return True
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


# ── 每周 BOSS 战（旧版，保留给 analytics 端点）───────────────────────────────

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


# ── 卡牌 BOSS 战（新版）────────────────────────────────────────────────────────

# 各 BOSS 对应的相位台词
BOSS_PHASES = {
    "拖延魔君": {
        1: "「时间还多得很…」",
        2: "「你…怎么还在坚持！」",
        3: "「不可能！这不应该发生！」",
    },
    "惰性之鬼": {
        1: "「等一下再做就好了…」",
        2: "「你破了我的咒语？！」",
        3: "「我的力量…正在消散…」",
    },
    "懒散之王": {
        1: "「舒适区之外，一片虚无。」",
        2: "「你…居然走出来了？！」",
        3: "「我的王座…正在崩塌！」",
    },
    "荒废之神": {
        1: "「虚度的时光让我愈发强大。」",
        2: "「你的行动，正在灼烧我！」",
        3: "「不…不要！我不愿消散！」",
    },
    "借口之主": {
        1: "「你肯定有一千个理由放弃。」",
        2: "「我的借口…失灵了？！」",
        3: "「你不讲道理…！我服了！」",
    },
    "舒适恶魔": {
        1: "「安逸是最美的牢笼，享受吧。」",
        2: "「你…打破了我的结界？！」",
        3: "「温暖的笼子…正在燃烧…」",
    },
}

# 卡牌定义：分类 → (卡名, 类型, 效果描述, 基础威力系数)
CARD_TEMPLATES = {
    "study":      ("智识·爆发",  "attack",  "爆发伤害，INT驱动",    6),
    "exercise":   ("力量·冲刺",  "attack",  "物理强攻，STR驱动",    8),
    "focus":      ("时间·掌控",  "skill",   "能量聚焦，AGI驱动，暴击级输出", 7),
    "reflection": ("意志·防壁",  "defense", "削弱BOSS回血，WIS驱动", 5),
}

RARITY_MULT = {"common": 1.0, "rare": 1.5, "epic": 2.0}
RARITY_LABELS = {"common": "普通", "rare": "稀有", "epic": "传说"}


def get_card_rarity(streak: int) -> str:
    if streak >= 7:
        return "epic"
    if streak >= 3:
        return "rare"
    return "common"


def earn_card_data(habit: dict, streak: int, player_stats: dict) -> dict:
    """生成打卡奖励卡牌的数据（不写DB，仅计算）"""
    cat = habit["category"]
    template = CARD_TEMPLATES.get(cat, ("通用卡", "attack", "基础伤害", 5))
    card_name, card_type, card_effect, power_coeff = template
    rarity = get_card_rarity(streak)
    mult = RARITY_MULT[rarity]

    # 属性加成：按分类使用对应属性
    stat_key = {"study": "int", "exercise": "str", "focus": "agi", "reflection": "wis"}.get(cat, "str")
    stat_val = player_stats.get(stat_key, 50)

    power = round((habit["base_exp"] / 20) * power_coeff * mult * (1 + stat_val / 200))
    return {
        "card_name":   card_name,
        "card_type":   card_type,
        "card_effect": card_effect,
        "power":       power,
        "rarity":      rarity,
        "rarity_label": RARITY_LABELS[rarity],
        "category":    cat,
    }


def calculate_boss_state(
    logs: list,
    habits: list,
    cat_stats: dict,
    cards_in_hand: list,
    cards_played: list,
    week_offset: int = 0,
) -> dict:
    """
    完整 BOSS 战状态计算。
    cards_in_hand / cards_played: 从 DB 查出的 battle_cards 记录列表。
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7 * week_offset)
    week_end = week_start + timedelta(days=6)
    is_week_over = today > week_end

    # ── BOSS 身份 ───────────────────────────────────────────────────────────────
    wk = (today - date(2024, 1, 1)).days // 7 - week_offset
    boss_name, boss_desc = BOSS_NAMES[wk % len(BOSS_NAMES)]

    # ── 玩家属性（30日分类得分）─────────────────────────────────────────────────
    player_stats = {
        "str": cat_stats.get("exercise",   {}).get("score", 0),
        "int": cat_stats.get("study",      {}).get("score", 0),
        "agi": cat_stats.get("focus",      {}).get("score", 0),
        "wis": cat_stats.get("reflection", {}).get("score", 0),
    }
    avg_stat = sum(player_stats.values()) / 4

    # ── BOSS HP 校准（65%完成率=破防线，约55开）────────────────────────────────
    if not habits:
        return _empty_boss_state(boss_name, boss_desc, week_start, week_end)

    avg_base_exp = sum(h["base_exp"] for h in habits) / len(habits)
    stat_mult_avg = 1 + avg_stat / 200          # 平均属性加成
    boss_hp_max = max(
        50,
        round(len(habits) * 7 * (avg_base_exp / 20) * stat_mult_avg * 0.65),
    )

    # ── 本周 logs ───────────────────────────────────────────────────────────────
    days_passed = min((today - week_start).days + 1, 7)
    habit_map = {h["id"]: h for h in habits}
    habit_ids = {h["id"] for h in habits}

    week_logs = [
        l for l in logs
        if week_start <= date.fromisoformat(l["date"]) <= week_end
        and l["habit_id"] in habit_ids
    ]

    # ── 防御卡效果：削减 BOSS 回血系数 ─────────────────────────────────────────
    defense_played = sum(1 for c in cards_played if c["card_type"] == "defense")
    regen_mult = max(0.1, 1.0 - defense_played * 0.25)   # 每张防御卡削 25%，最低 10%

    # ── 逐日伤害 & 回血计算 ─────────────────────────────────────────────────────
    battle_log = []
    total_auto_damage = 0
    total_regen = 0
    total_completed = 0
    total_possible = len(habits) * days_passed

    for i in range(days_passed):
        d = week_start + timedelta(days=i)
        date_str = str(d)
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d.weekday()]

        day_logs = [l for l in week_logs if l["date"] == date_str]
        completed_ids = {l["habit_id"] for l in day_logs if l["completed"]}
        missed_ids = habit_ids - completed_ids

        # 伤害：每个完成的习惯
        day_damage = 0.0
        for hid in completed_ids:
            h = habit_map.get(hid)
            if not h:
                continue
            base = h["base_exp"] / 20
            cat = h["category"]
            s = player_stats.get(
                {"exercise": "str", "study": "int", "focus": "agi", "reflection": "wis"}.get(cat, "str"), 0
            )
            day_damage += base * (1 + s / 200)

        # 回血：每个未完成的习惯
        day_regen = 0.0
        for hid in missed_ids:
            h = habit_map.get(hid)
            if h:
                day_regen += (h["base_exp"] / 40) * regen_mult

        total_auto_damage += day_damage
        total_regen += day_regen
        total_completed += len(completed_ids)

        battle_log.append({
            "date": date_str,
            "weekday": weekday,
            "damage": round(day_damage),
            "boss_regen": round(day_regen),
            "completed": len(completed_ids),
            "total": len(habits),
            "all_done": len(completed_ids) == len(habits) and len(habits) > 0,
        })

    # ── 手牌伤害 ────────────────────────────────────────────────────────────────
    card_damage = sum(c["power"] for c in cards_played)

    total_damage = round(total_auto_damage) + card_damage
    hp_remaining = max(0, boss_hp_max - total_damage + round(total_regen))

    # ── 完成率 & 相位 ───────────────────────────────────────────────────────────
    completion_rate = round(total_completed / max(total_possible, 1) * 100)

    phase_pct = hp_remaining / boss_hp_max if boss_hp_max > 0 else 1.0
    boss_phase = 1 if phase_pct > 0.60 else 2 if phase_pct > 0.25 else 3
    phase_quote = BOSS_PHASES.get(boss_name, {}).get(boss_phase, "")

    # ── 胜负判断 ────────────────────────────────────────────────────────────────
    won: Optional[bool] = None
    if is_week_over or hp_remaining == 0:
        won = hp_remaining == 0 or total_damage >= boss_hp_max

    # ── 胜利奖励 ────────────────────────────────────────────────────────────────
    exp_bonus = 0
    title_earned = None
    if won:
        rate = completion_rate
        bonus_mult = 1.0 if rate >= 95 else 0.8 if rate >= 85 else 0.6 if rate >= 75 else 0.4
        exp_bonus = round(boss_hp_max * bonus_mult)
        title_earned = (
            "无下限的觉醒者" if rate >= 95 else
            "精英BOSS猎手"   if rate >= 85 else
            "顽强觉醒者"     if rate >= 75 else
            "BOSS猎手"
        )

    return {
        "boss_name":       boss_name,
        "boss_desc":       boss_desc,
        "boss_hp_max":     boss_hp_max,
        "auto_damage":     round(total_auto_damage),
        "card_damage":     card_damage,
        "total_damage":    total_damage,
        "boss_regen":      round(total_regen),
        "hp_remaining":    hp_remaining,
        "boss_phase":      boss_phase,
        "phase_quote":     phase_quote,
        "player_stats":    player_stats,
        "cards_in_hand":   cards_in_hand,
        "cards_played":    cards_played,
        "completion_rate": completion_rate,
        "is_week_over":    is_week_over,
        "won":             won,
        "exp_bonus":       exp_bonus,
        "title_earned":    title_earned,
        "week_start":      str(week_start),
        "week_end":        str(week_end),
        "days_passed":     days_passed,
        "battle_log":      battle_log,
        "defense_stacks":  defense_played,
    }


def _empty_boss_state(boss_name, boss_desc, week_start, week_end) -> dict:
    return {
        "boss_name": boss_name, "boss_desc": boss_desc,
        "boss_hp_max": 0, "auto_damage": 0, "card_damage": 0,
        "total_damage": 0, "boss_regen": 0, "hp_remaining": 0,
        "boss_phase": 1, "phase_quote": "",
        "player_stats": {"str": 0, "int": 0, "agi": 0, "wis": 0},
        "cards_in_hand": [], "cards_played": [],
        "completion_rate": 0, "is_week_over": False,
        "won": None, "exp_bonus": 0, "title_earned": None,
        "week_start": str(week_start), "week_end": str(week_end),
        "days_passed": 0, "battle_log": [], "defense_stacks": 0,
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


# ── 热图 ─────────────────────────────────────────────────────────────────────

def calculate_heatmap_data(logs: list, habits: list, today: date) -> list:
    """
    Return list of {date, level 0-4, done, total} for last 365 days, oldest first.
    level 0=none, 1=≤25%, 2=≤50%, 3=<100%, 4=100%
    """
    ids = {h["id"] for h in habits}
    total = len(ids)

    done_by_date: Dict[str, int] = {}
    for l in logs:
        if l["completed"] and l["habit_id"] in ids:
            done_by_date[l["date"]] = done_by_date.get(l["date"], 0) + 1

    result = []
    for i in range(364, -1, -1):
        d = today - timedelta(days=i)
        ds = str(d)
        done = done_by_date.get(ds, 0)
        if total == 0 or done == 0:
            level = 0
        elif done / total <= 0.25:
            level = 1
        elif done / total <= 0.5:
            level = 2
        elif done / total < 1.0:
            level = 3
        else:
            level = 4
        result.append({"date": ds, "level": level, "done": done, "total": total})

    return result


# ── 打卡时间分布 ──────────────────────────────────────────────────────────────

def calculate_checkin_time_distribution(logs: list) -> Dict:
    """
    Analyse check-in hour distribution from completed_at field.
    Returns hourly counts (0-23) and best 2-hour peak window.
    """
    hours = [0] * 24
    for l in logs:
        if l.get("completed") and l.get("completed_at"):
            try:
                hour = int(str(l["completed_at"])[11:13])
                if 0 <= hour <= 23:
                    hours[hour] += 1
            except (IndexError, ValueError, TypeError):
                pass

    total = sum(hours)
    if total == 0:
        return {"hourly": hours, "total": 0, "peak_start": -1, "peak_end": -1}

    best_start = max(range(23), key=lambda h: hours[h] + hours[h + 1])
    return {
        "hourly": hours,
        "total": total,
        "peak_start": best_start,
        "peak_end": best_start + 2,
    }


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
