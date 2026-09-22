import os
import time
import json
import secrets
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import bcrypt
import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "547dsj"),
    "database": os.getenv("DB_NAME", "cs2_events"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError("请在 .env 中设置 ADMIN_PASSWORD")
ADMIN_PASSWORD_HASH = bcrypt.hashpw(ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

app = FastAPI(title="CS2 赛事全景")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="cs2_admin_session",
    max_age=7 * 24 * 3600,
    same_site="lax",
)


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self.hits = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        dq = self.hits[key]
        while dq and now - dq[0] > self.window_seconds:
            dq.popleft()
        if len(dq) >= self.limit:
            return False
        dq.append(now)
        return True


api_limiter = SlidingWindowLimiter(limit=240, window_seconds=60)
login_limiter = SlidingWindowLimiter(limit=5, window_seconds=900)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        if not api_limiter.allow(get_client_ip(request)):
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})
    return await call_next(request)


def get_db_connection():
    return pymysql.connect(**DB_CONFIG)


def get_last_modified():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM site_settings WHERE setting_key = 'last_modified'")
            row = cur.fetchone()
    finally:
        conn.close()
    return row["setting_value"] if row else None


def touch_last_modified():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO site_settings (setting_key, setting_value)
                VALUES ('last_modified', %s)
                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                """,
                (now,),
            )
            conn.commit()
    finally:
        conn.close()


class AdminLogin(BaseModel):
    password: str


class EventBase(BaseModel):
    name: str
    org: str
    level: str
    start_date: str
    end_date: str
    location: str
    prize: int
    champion: Optional[str] = None
    runnerup: Optional[str] = None
    mvp: Optional[str] = None
    score: Optional[str] = None
    champion_roster: Optional[List[str]] = None
    runnerup_roster: Optional[List[str]] = None


class EventCreate(EventBase):
    pass


class EventUpdate(EventBase):
    pass


class EventResponse(EventBase):
    id: int


def row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "org": row["org"],
        "level": row["level"],
        "start_date": row["start_date"].isoformat() if isinstance(row["start_date"], date) else str(row["start_date"]),
        "end_date": row["end_date"].isoformat() if isinstance(row["end_date"], date) else str(row["end_date"]),
        "location": row["location"],
        "prize": row["prize"],
        "champion": row["champion"],
        "runnerup": row["runnerup"],
        "mvp": row["mvp"],
        "score": row["score"],
        "champion_roster": json.loads(row["champion_roster"]) if row.get("champion_roster") else [],
        "runnerup_roster": json.loads(row["runnerup_roster"]) if row.get("runnerup_roster") else [],
    }


def get_event_or_404(event_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM events WHERE id = %s", (event_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="赛事不存在")
    return row_to_dict(row)


def require_admin(request: Request):
    if not request.session.get("admin"):
        raise HTTPException(status_code=401, detail="请先登录")


@app.post("/api/admin/login")
async def admin_login(request: Request, payload: AdminLogin):
    ip = get_client_ip(request)
    if not login_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="尝试次数过多，请稍后再试")
    if not bcrypt.checkpw(payload.password.encode("utf-8"), ADMIN_PASSWORD_HASH.encode("utf-8")):
        raise HTTPException(status_code=401, detail="密码错误")
    request.session["admin"] = True
    return {"authenticated": True}


@app.post("/api/admin/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return {"authenticated": False}


@app.get("/api/admin/check")
async def admin_check(request: Request):
    return {"authenticated": bool(request.session.get("admin"))}


@app.get("/api/settings")
async def get_settings():
    return {"last_modified": get_last_modified()}


@app.get("/api/events", response_model=List[EventResponse])
async def get_events():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM events ORDER BY start_date ASC, id ASC")
            rows = cur.fetchall()
        return [row_to_dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: int):
    return get_event_or_404(event_id)


@app.post("/api/events", response_model=EventResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_event(event: EventCreate):
    champion_roster_json = json.dumps(event.champion_roster or [], ensure_ascii=False)
    runnerup_roster_json = json.dumps(event.runnerup_roster or [], ensure_ascii=False)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events
                    (name, org, level, start_date, end_date, location, prize,
                     champion, runnerup, mvp, score, champion_roster, runnerup_roster)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event.name, event.org, event.level,
                    event.start_date, event.end_date, event.location, event.prize,
                    event.champion, event.runnerup, event.mvp, event.score,
                    champion_roster_json, runnerup_roster_json,
                ),
            )
            new_id = cur.lastrowid
            conn.commit()
    finally:
        conn.close()
    touch_last_modified()
    return get_event_or_404(new_id)


@app.put("/api/events/{event_id}", response_model=EventResponse, dependencies=[Depends(require_admin)])
async def update_event(event_id: int, event: EventUpdate):
    get_event_or_404(event_id)
    champion_roster_json = json.dumps(event.champion_roster or [], ensure_ascii=False)
    runnerup_roster_json = json.dumps(event.runnerup_roster or [], ensure_ascii=False)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE events
                SET name=%s, org=%s, level=%s, start_date=%s, end_date=%s,
                    location=%s, prize=%s, champion=%s, runnerup=%s, mvp=%s,
                    score=%s, champion_roster=%s, runnerup_roster=%s
                WHERE id=%s
                """,
                (
                    event.name, event.org, event.level,
                    event.start_date, event.end_date, event.location, event.prize,
                    event.champion, event.runnerup, event.mvp, event.score,
                    champion_roster_json, runnerup_roster_json, event_id,
                ),
            )
            conn.commit()
    finally:
        conn.close()
    touch_last_modified()
    return get_event_or_404(event_id)


@app.delete("/api/events/{event_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_event(event_id: int):
    get_event_or_404(event_id)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE id = %s", (event_id,))
            conn.commit()
    finally:
        conn.close()
    touch_last_modified()
    return None


@app.get("/", include_in_schema=False)
async def user_page():
    return FileResponse(PUBLIC_DIR / "user.html")


@app.get("/admin", include_in_schema=False)
async def admin_page():
    return FileResponse(PUBLIC_DIR / "admin.html")


@app.get("/cs2bisai", include_in_schema=False)
async def user_page_alias():
    return FileResponse(PUBLIC_DIR / "user.html")


@app.get("/cs2bisai/admin", include_in_schema=False)
async def admin_page_alias():
    return FileResponse(PUBLIC_DIR / "admin.html")


app.mount("/static", StaticFiles(directory=PUBLIC_DIR / "static"), name="static")