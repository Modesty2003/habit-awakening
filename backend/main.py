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
    calculate_momentum,
    calculate_consistency,
    calculate_category_stats,
    calculate_weekly_boss,
    generate_system_message,
    detect_weak_habits,
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


# ── 辅助 ─────────────────────────────────────────────────────────────────────

def _fetch_all_logs(conn, days: int = 90):
    cutoff = str(date.today() - timedelta(days=days))
    rows = conn.execute(
        "SELECT habit_id, date, completed, exp_earned, streak_count FROM habit_logs WHERE date >= ?",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_habits(conn):
    rows = conn.execute(
        "SELECT id, name, category, icon, base_exp, is_active FROM habits WHERE is_active=1 ORDER BY sort_order, id"
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_user(conn):
    row = conn.execute("SELECT id, name, total_exp FROM users WHERE id=1").fetchone()
    return dict(row)


# ── API: 用户 ─────────────────────────────────────────────────────────────────

@app.get("/api/user")
def get_user():
    conn = get_db()
    try:
        user = _fetch_user(conn)
        habits = _fetch_habits(conn)
        logs = _fetch_all_logs(conn)
        level_info = get_level_info(user["total_exp"])
        global_streak = calculate_global_streak(habits, logs, date.today())
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
        habits = _fetch_habits(conn)
        logs = _fetch_all_logs(conn)

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
            streak = calculate_streak_for_habit(h["id"], logs, date.today())
            exp_preview = calculate_exp_with_streak(h["base_exp"], streak)
            result.append({
                **h,
                "completed": bool(log.get("completed", 0)),
                "exp_earned": log.get("exp_earned", 0),
                "streak": streak,
                "exp_preview": exp_preview,
            })
        return {"date": today_str, "habits": result}
    finally:
        conn.close()


@app.post("/api/checkin/{habit_id}")
def toggle_checkin(habit_id: int):
    conn = get_db()
    try:
        today_str = str(date.today())
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
            # 取消打卡，回收 EXP
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
            return {"completed": False, "exp_earned": 0, "exp_delta": -exp_to_remove}
        else:
            # 完成打卡
            streak = calculate_streak_for_habit(habit_id, logs, date.today())
            exp_earned = calculate_exp_with_streak(habit["base_exp"], streak)
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

            # 成就检测
            logs_fresh = _fetch_all_logs(conn)
            user = _fetch_user(conn)
            habits_fresh = _fetch_habits(conn)
            new_achievements = check_and_unlock(conn, logs_fresh, habits_fresh, user)

            return {
                "completed": True,
                "exp_earned": exp_earned,
                "exp_delta": exp_earned,
                "streak": streak + 1,
                "new_achievements": new_achievements,
            }
    finally:
        conn.close()


# ── API: 分析 ─────────────────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics():
    conn = get_db()
    try:
        habits = _fetch_habits(conn)
        logs = _fetch_all_logs(conn, days=90)
        user = _fetch_user(conn)

        momentum = calculate_momentum(logs, habits, days=14)
        consistency = calculate_consistency(logs, habits, days=30)
        cat_stats = calculate_category_stats(logs, habits, days=30)
        weekly_boss = calculate_weekly_boss(logs, habits, week_offset=0)
        last_boss = calculate_weekly_boss(logs, habits, week_offset=1)
        weak = detect_weak_habits(cat_stats)
        level_info = get_level_info(user["total_exp"])
        global_streak = calculate_global_streak(habits, logs, date.today())
        msg = generate_system_message(momentum, consistency, global_streak, level_info["level"])

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
        }
    finally:
        conn.close()


# ── API: 成就 ─────────────────────────────────────────────────────────────────

@app.get("/api/achievements")
def get_achievements():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT key, name, description, icon, is_unlocked, unlocked_at FROM achievements ORDER BY is_unlocked DESC, id"
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
                      h.name, h.category, h.icon
               FROM habit_logs hl
               JOIN habits h ON h.id = hl.habit_id
               WHERE hl.date >= ? ORDER BY hl.date DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── 静态文件 & SPA 兜底 ───────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str = ""):
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ── 入口 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=7788, reload=False)
