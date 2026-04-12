import os
import sys
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ── 路径修正（打包后也能找到 frontend）───────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# ── 导入本地模块 ─────────────────────────────────────────────────────────────
sys.path.insert(0, BASE_DIR)
from backend.database import init_db, get_db
from backend.analytics import (
    get_level_info,
    calculate_streak_for_habit,
    calculate_global_streak,
    calculate_exp_with_streak,
    calculate_dynamic_exp,
    calculate_momentum,
    calculate_consistency,
    calculate_category_stats,
    calculate_weekly_boss,
    generate_system_message,
    detect_weak_habits,
    calculate_heatmap_data,
    calculate_checkin_time_distribution,
)
from backend.achievements import check_and_unlock

app = FastAPI(title="觉醒系统 API", docs_url="/api/docs")


@app.on_event("startup")
def startup():
    init_db()


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class UserUpdate(BaseModel):
    name: str


class HabitCreate(BaseModel):
    name: str
    category: str
    icon: str = "⚡"
    base_exp: int = 100


class HabitUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    base_exp: Optional[int] = None
    is_active: Optional[int] = None


class ChallengeCreate(BaseModel):
    habit_id: int
    name: str
    target_days: int = 21


# ── 辅助 ─────────────────────────────────────────────────────────────────────

def _fetch_all_logs(conn, days: int = 90):
    cutoff = str(date.today() - timedelta(days=days))
    rows = conn.execute(
        """SELECT habit_id, date, completed, exp_earned, streak_count, completed_at
           FROM habit_logs WHERE date >= ?""",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_habits(conn):
    rows = conn.execute(
        "SELECT id, name, category, icon, base_exp, is_active FROM habits WHERE is_active=1 ORDER BY sort_order, id"
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_user(conn):
    row = conn.execute(
        "SELECT id, name, total_exp, shields FROM users WHERE id=1"
    ).fetchone()
    return dict(row)


def _fetch_shield_dates(conn):
    rows = conn.execute("SELECT date FROM shield_days").fetchall()
    return {r["date"] for r in rows}


def _maybe_use_shield(conn, habits, logs, today) -> bool:
    """
    If yesterday was a missed day but day-before-yesterday wasn't,
    auto-spend one shield to protect the streak.
    Only fires once per missed day.
    """
    if not habits:
        return False

    yesterday = str(today - timedelta(days=1))
    day_before = str(today - timedelta(days=2))

    # Already shielded today?
    if conn.execute("SELECT date FROM shield_days WHERE date=?", (yesterday,)).fetchone():
        return False

    ids = {h["id"] for h in habits}

    def all_done_in_logs(ds):
        done = {l["habit_id"] for l in logs if l["date"] == ds and l["completed"]}
        return ids.issubset(done)

    if not all_done_in_logs(yesterday) and all_done_in_logs(day_before):
        user = conn.execute("SELECT shields FROM users WHERE id=1").fetchone()
        if user and user["shields"] > 0:
            conn.execute("INSERT OR IGNORE INTO shield_days (date) VALUES (?)", (yesterday,))
            conn.execute("UPDATE users SET shields = shields - 1 WHERE id=1")
            conn.commit()
            return True

    return False


def _maybe_earn_shield(conn, global_streak) -> bool:
    """Award a shield each time streak hits a new multiple-of-7 milestone (max 3)."""
    if global_streak <= 0 or global_streak % 7 != 0:
        return False
    user = conn.execute(
        "SELECT shields, last_shield_milestone FROM users WHERE id=1"
    ).fetchone()
    if not user:
        return False
    if global_streak > user["last_shield_milestone"] and user["shields"] < 3:
        conn.execute(
            "UPDATE users SET shields=shields+1, last_shield_milestone=? WHERE id=1",
            (global_streak,),
        )
        conn.commit()
        return True
    return False


# ── API: 用户 ─────────────────────────────────────────────────────────────────

@app.get("/api/user")
def get_user():
    conn = get_db()
    try:
        user = _fetch_user(conn)
        habits = _fetch_habits(conn)
        logs = _fetch_all_logs(conn)
        shield_dates = _fetch_shield_dates(conn)
        level_info = get_level_info(user["total_exp"])
        global_streak = calculate_global_streak(habits, logs, date.today(), shield_dates)
        return {**user, **level_info, "global_streak": global_streak}
    finally:
        conn.close()


@app.put("/api/user")
def update_user(body: UserUpdate):
    conn = get_db()
    try:
        conn.execute("UPDATE users SET name=? WHERE id=1", (body.name.strip(),))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ── API: 习惯 ─────────────────────────────────────────────────────────────────

@app.get("/api/habits")
def get_habits():
    conn = get_db()
    try:
        return _fetch_habits(conn)
    finally:
        conn.close()


@app.post("/api/habits")
def create_habit(body: HabitCreate):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO habits (name, category, icon, base_exp) VALUES (?, ?, ?, ?)",
            (body.name.strip(), body.category, body.icon, body.base_exp),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.patch("/api/habits/{habit_id}")
def update_habit(habit_id: int, body: HabitUpdate):
    conn = get_db()
    try:
        if body.name is not None:
            conn.execute("UPDATE habits SET name=? WHERE id=?", (body.name.strip(), habit_id))
        if body.icon is not None:
            conn.execute("UPDATE habits SET icon=? WHERE id=?", (body.icon, habit_id))
        if body.base_exp is not None:
            conn.execute("UPDATE habits SET base_exp=? WHERE id=?", (body.base_exp, habit_id))
        if body.is_active is not None:
            conn.execute("UPDATE habits SET is_active=? WHERE id=?", (body.is_active, habit_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.delete("/api/habits/{habit_id}")
def delete_habit(habit_id: int):
    conn = get_db()
    try:
        conn.execute("UPDATE habits SET is_active=0 WHERE id=?", (habit_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ── API: 今日任务 ─────────────────────────────────────────────────────────────

@app.get("/api/today")
def get_today():
    conn = get_db()
    try:
        today_str = str(date.today())
        today = date.today()
        habits = _fetch_habits(conn)
        logs = _fetch_all_logs(conn)

        # Auto-use shield if streak would break (first request of a new missed day)
        shield_auto_used = _maybe_use_shield(conn, habits, logs, today)
        if shield_auto_used:
            logs = _fetch_all_logs(conn)  # refresh after shield insertion

        shield_dates = _fetch_shield_dates(conn)
        user = _fetch_user(conn)

        today_logs = {
            row["habit_id"]: dict(row)
            for row in conn.execute(
                "SELECT habit_id, completed, exp_earned, streak_count FROM habit_logs WHERE date=?",
                (today_str,),
            ).fetchall()
        }

        result = []
        for h in habits:
            log = today_logs.get(h["id"], {})
            streak = calculate_streak_for_habit(h["id"], logs, today)
            dyn_exp = calculate_dynamic_exp(h["base_exp"], h["id"], logs)
            exp_preview = calculate_exp_with_streak(dyn_exp, streak)
            result.append({
                **h,
                "completed": bool(log.get("completed", 0)),
                "exp_earned": log.get("exp_earned", 0),
                "streak": streak,
                "exp_preview": exp_preview,
                "dynamic_exp": dyn_exp,
            })

        return {
            "date": today_str,
            "habits": result,
            "shields": user["shields"],
            "shield_auto_used": shield_auto_used,
        }
    finally:
        conn.close()


@app.post("/api/checkin/{habit_id}")
def toggle_checkin(habit_id: int):
    conn = get_db()
    try:
        today_str = str(date.today())
        today = date.today()
        habits = _fetch_habits(conn)
        habit = next((h for h in habits if h["id"] == habit_id), None)
        if not habit:
            raise HTTPException(status_code=404, detail="Habit not found")

        logs = _fetch_all_logs(conn)
        existing = conn.execute(
            "SELECT completed FROM habit_logs WHERE habit_id=? AND date=?",
            (habit_id, today_str),
        ).fetchone()

        if existing and existing["completed"]:
            # ── 取消打卡 ───────────────────────────────────────────────────────
            exp_row = conn.execute(
                "SELECT exp_earned FROM habit_logs WHERE habit_id=? AND date=?",
                (habit_id, today_str),
            ).fetchone()
            exp_to_remove = exp_row["exp_earned"] if exp_row else 0
            conn.execute(
                "UPDATE habit_logs SET completed=0, exp_earned=0 WHERE habit_id=? AND date=?",
                (habit_id, today_str),
            )
            conn.execute(
                "UPDATE users SET total_exp = MAX(0, total_exp - ?) WHERE id=1",
                (exp_to_remove,),
            )
            conn.commit()
            user = _fetch_user(conn)
            return {
                "completed": False,
                "exp_earned": 0,
                "exp_delta": -exp_to_remove,
                "shields": user["shields"],
            }
        else:
            # ── 打卡 ──────────────────────────────────────────────────────────
            # Try auto-use shield before calculating streak
            shield_used = _maybe_use_shield(conn, habits, logs, today)
            if shield_used:
                logs = _fetch_all_logs(conn)

            shield_dates = _fetch_shield_dates(conn)
            streak = calculate_streak_for_habit(habit_id, logs, today)
            dyn_exp = calculate_dynamic_exp(habit["base_exp"], habit_id, logs)
            exp_earned = calculate_exp_with_streak(dyn_exp, streak)

            conn.execute(
                """INSERT INTO habit_logs (habit_id, date, completed, exp_earned, streak_count, completed_at)
                   VALUES (?, ?, 1, ?, ?, datetime('now'))
                   ON CONFLICT(habit_id, date) DO UPDATE
                   SET completed=1, exp_earned=?, streak_count=?, completed_at=datetime('now')""",
                (habit_id, today_str, exp_earned, streak + 1, exp_earned, streak + 1),
            )
            conn.execute(
                "UPDATE users SET total_exp = total_exp + ? WHERE id=1",
                (exp_earned,),
            )
            conn.commit()

            # Check if today all habits done → award shield if streak milestone hit
            logs_fresh = _fetch_all_logs(conn)
            habits_fresh = _fetch_habits(conn)
            user = _fetch_user(conn)
            global_streak = calculate_global_streak(habits_fresh, logs_fresh, today, shield_dates)
            shield_earned = _maybe_earn_shield(conn, global_streak)

            new_achievements = check_and_unlock(conn, logs_fresh, habits_fresh, user)

            user = _fetch_user(conn)  # re-fetch after possible shield update
            return {
                "completed": True,
                "exp_earned": exp_earned,
                "exp_delta": exp_earned,
                "streak": streak + 1,
                "new_achievements": new_achievements,
                "shield_used": shield_used,
                "shield_earned": shield_earned,
                "shields": user["shields"],
            }
    finally:
        conn.close()


# ── API: 分析 ─────────────────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics():
    conn = get_db()
    try:
        habits = _fetch_habits(conn)
        logs = _fetch_all_logs(conn, days=366)  # 365 days + buffer for heatmap
        user = _fetch_user(conn)
        shield_dates = _fetch_shield_dates(conn)

        momentum = calculate_momentum(logs, habits, days=14)
        consistency = calculate_consistency(logs, habits, days=30)
        cat_stats = calculate_category_stats(logs, habits, days=30)
        weekly_boss = calculate_weekly_boss(logs, habits, week_offset=0)
        last_boss = calculate_weekly_boss(logs, habits, week_offset=1)
        weak = detect_weak_habits(cat_stats)
        level_info = get_level_info(user["total_exp"])
        global_streak = calculate_global_streak(habits, logs, date.today(), shield_dates)
        msg = generate_system_message(momentum, consistency, global_streak, level_info["level"])
        heatmap = calculate_heatmap_data(logs, habits, date.today())
        time_dist = calculate_checkin_time_distribution(logs)

        # 最近 30 天每日完成数（给折线图用）
        today = date.today()
        daily_history = []
        habit_ids = {h["id"] for h in habits}
        for i in range(29, -1, -1):
            d = today - timedelta(days=i)
            done = sum(
                1 for log in logs
                if log["date"] == str(d) and log["habit_id"] in habit_ids and log["completed"]
            )
            daily_history.append({"date": str(d), "done": done, "total": len(habits)})

        return {
            "momentum": momentum,
            "consistency": consistency,
            "category_stats": cat_stats,
            "weekly_boss": weekly_boss,
            "last_boss": last_boss,
            "weak_habits": weak,
            "system_message": msg,
            "daily_history": daily_history,
            "global_streak": global_streak,
            "heatmap": heatmap,
            "time_distribution": time_dist,
        }
    finally:
        conn.close()


# ── API: 成就 ─────────────────────────────────────────────────────────────────

@app.get("/api/achievements")
def get_achievements():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT key, name, description, icon, cat, is_unlocked, unlocked_at FROM achievements ORDER BY is_unlocked DESC, id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── API: 历史记录 ─────────────────────────────────────────────────────────────

@app.get("/api/history")
def get_history(days: int = 60):
    conn = get_db()
    try:
        cutoff = str(date.today() - timedelta(days=days))
        rows = conn.execute(
            """SELECT hl.habit_id, hl.date, hl.completed, hl.exp_earned, hl.streak_count,
                      COALESCE(h.name, '[已删除]') AS name,
                      COALESCE(h.category, 'unknown') AS category,
                      COALESCE(h.icon, '🗑️') AS icon,
                      CASE WHEN h.id IS NULL THEN 1 ELSE 0 END AS is_deleted
               FROM habit_logs hl
               LEFT JOIN habits h ON h.id = hl.habit_id
               WHERE hl.date >= ? ORDER BY hl.date DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── API: 挑战模式 ─────────────────────────────────────────────────────────────

@app.get("/api/challenges")
def get_challenges():
    conn = get_db()
    try:
        challenges = conn.execute(
            "SELECT * FROM challenges WHERE status != 'abandoned' ORDER BY created_at DESC"
        ).fetchall()
        all_habits = {
            h["id"]: dict(h)
            for h in conn.execute("SELECT id, name, category, icon, base_exp, is_active FROM habits").fetchall()
        }
        logs = _fetch_all_logs(conn, days=366)
        today = date.today()

        result = []
        for c in [dict(c) for c in challenges]:
            habit = all_habits.get(c["habit_id"], {})
            start = date.fromisoformat(c["start_date"])
            end = start + timedelta(days=c["target_days"] - 1)

            done_days = len({
                l["date"] for l in logs
                if l["habit_id"] == c["habit_id"]
                and l["completed"]
                and start <= date.fromisoformat(l["date"]) <= end
            })

            progress_pct = round(done_days / c["target_days"] * 100)

            # Auto-update status
            if done_days >= c["target_days"] and c["status"] == "active":
                conn.execute("UPDATE challenges SET status='completed' WHERE id=?", (c["id"],))
                conn.commit()
                c["status"] = "completed"
            elif today > end and c["status"] == "active":
                conn.execute("UPDATE challenges SET status='failed' WHERE id=?", (c["id"],))
                conn.commit()
                c["status"] = "failed"

            c["habit_name"] = habit.get("name", "[已删除]")
            c["habit_icon"] = habit.get("icon", "❓")
            c["days_done"] = done_days
            c["days_remaining"] = max(0, (end - today).days)
            c["progress_pct"] = progress_pct
            c["end_date"] = str(end)
            result.append(c)

        return result
    finally:
        conn.close()


@app.post("/api/challenges")
def create_challenge(body: ChallengeCreate):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO challenges (habit_id, name, target_days, start_date) VALUES (?, ?, ?, ?)",
            (body.habit_id, body.name.strip(), body.target_days, str(date.today())),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.delete("/api/challenges/{challenge_id}")
def delete_challenge(challenge_id: int):
    conn = get_db()
    try:
        conn.execute("UPDATE challenges SET status='abandoned' WHERE id=?", (challenge_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/assets/{filename}", include_in_schema=False)
def serve_asset(filename: str):
    path = os.path.join(FRONTEND_DIR, "assets", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


# ── 静态文件 & SPA 兜底 ───────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str = ""):
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ── 入口 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=7788, reload=False)
