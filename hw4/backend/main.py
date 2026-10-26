"""Campus Customs shop API: products, stock, product photos, accounts and the shop assistant chat.

Run from the backend/ folder, as in the assignment (uvicorn from the hw4 virtual environment):
    ../.venv/Scripts/uvicorn main:app --reload --port 8000
or without auto-reload:
    ../.venv/Scripts/python main.py
Either serves http://127.0.0.1:8000. The Vite dev server forwards /api and /images here
(port 8000 by default; set API_PORT for both if 8000 is taken by another app).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import agent as assistant
import auth
import guest_chat
import insights
from catalog import SUMMARY_SQL, product_detail, product_summaries, to_summary
from db import HW_DIR, connect, get_db, get_db_rw
from models import (CHAT_PREVIEW_CARDS, CatalogSearch, ChatIn, ChatMessageOut, GarmentTypeOut, PageContext,
                    ProductDetail, ProductSummary)

log = logging.getLogger("campus_customs")

PRODUCT_IMAGES = HW_DIR / "data" / "data" / "products"
PORT = int(os.getenv("API_PORT", "8000"))  # same setting the Vite forwarding reads

# Browser pages allowed to send changes (log in, sign up...). A request from any other site
# is refused, so another website can't act on a shopper's behalf (cross-site request forgery).
ALLOWED_ORIGINS = set(os.getenv("CC_ALLOWED_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174").split(","))


def ensure_chat_columns(conn: sqlite3.Connection) -> None:
    # Chat tables made before the chat search (Problem 7) lack the search heading.
    if "search_title" not in {row[1] for row in conn.execute("PRAGMA table_info(chat_messages)")}:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN search_title TEXT "
                     "CHECK (search_title IS NULL OR length(search_title) BETWEEN 1 AND 60)")
        conn.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = connect(read_only=False)
    try:
        auth.ensure_auth_tables(conn)
        ensure_chat_columns(conn)
        insights.ensure_insight_tables(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="Campus Customs API", lifespan=lifespan)
app.mount("/images/products", StaticFiles(directory=PRODUCT_IMAGES), name="product-images")
app.include_router(auth.router)
app.include_router(insights.router)


@app.middleware("http")
async def security(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin not in ALLOWED_ORIGINS:
        return JSONResponse({"detail": "Request from an unknown site was refused."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/auth"):
        response.headers["Cache-Control"] = "no-store"
    return response


# --- Product routes --------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/garment-types", response_model=list[GarmentTypeOut])
def list_garment_types(db: sqlite3.Connection = Depends(get_db)) -> list[GarmentTypeOut]:
    """Types that have at least one product, in browse-menu order."""
    rows = db.execute("""
        SELECT g.garment_type, g.display_name, COUNT(c.product_id) AS n
        FROM garment_types g JOIN catalogue c USING (garment_type)
        GROUP BY g.garment_type ORDER BY g.sort_order
    """).fetchall()
    return [GarmentTypeOut(garment_type=r["garment_type"], label=r["display_name"], product_count=r["n"]) for r in rows]


@app.get("/api/products", response_model=list[ProductSummary])
def list_products(type: str | None = None, db: sqlite3.Connection = Depends(get_db)) -> list[ProductSummary]:
    where, params = ("WHERE c.garment_type = ?", [type]) if type else ("", [])
    rows = db.execute(f"{SUMMARY_SQL} {where} GROUP BY c.product_id ORDER BY g.sort_order, c.name", params).fetchall()
    return [to_summary(r) for r in rows]


@app.get("/api/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str, db: sqlite3.Connection = Depends(get_db)) -> ProductDetail:
    detail = product_detail(db, product_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return detail


# --- Shop assistant chat ---------------------------------------------------------------------
# Anyone can chat. Logged-in shoppers' chats are saved in chat_messages and reloaded on every
# visit; guests' chats live only in memory for one visit (guest_chat.py). A session that must
# change its password is still blocked. The agent gets a first name (shoppers only), their own
# earlier messages and the page they're on, nothing else.

CHAT_WINDOW_MIN = 10
CHAT_MAX_MESSAGES = 20  # per shopper per window: keeps a script from running up AI costs
HISTORY_SHOWN = 50


def page_for_agent(db: sqlite3.Connection, page: PageContext | None) -> tuple[str | None, tuple[str, str] | None]:
    """The shopper's page, reduced to facts the agent can trust: (page path, (product id, name)).

    Page context comes from the browser, so nothing in it reaches the agent's instructions
    unchecked: a product id is kept only if that product exists, a category filter only if it
    names a real category, and a search-results page only by its number.
    """
    if page is None:
        return None, None
    viewing = None
    if page.product_id:
        row = db.execute("SELECT product_id, name FROM catalogue WHERE product_id = ?", (page.product_id,)).fetchone()
        viewing = (row["product_id"], row["name"]) if row else None
    parts = urlsplit(page.path)
    query = parse_qs(parts.query)
    path = parts.path
    if path == "/products" and query.get("chat", [""])[0].isdigit():
        path = f"/products?chat={query['chat'][0]}"
    elif path == "/products" and "type" in query:
        row = db.execute("SELECT display_name FROM garment_types WHERE garment_type = ?", (query["type"][0],)).fetchone()
        path = f"/products?type={row['display_name']}" if row else path
    elif path.startswith("/products/"):
        path = "/products/" if viewing is None else f"/products/{viewing[0]}"
    elif path not in ("/", "/products", "/about"):
        path = "/other"
    return path, viewing


MESSAGE_COLUMNS = "id, role, content, product_ids, search_title, created_at"


def message_out(db: sqlite3.Connection, row: sqlite3.Row) -> ChatMessageOut:
    """A saved message, with its product cards looked up fresh so prices and stock are current.

    A search reply's cards go on the Product page (`search`); the chat panel previews the first few.
    """
    ids = row["product_ids"] or []
    ids = json.loads(ids) if isinstance(ids, str) else ids  # saved rows hold JSON; guest chats hold lists
    cards = product_summaries(db, ids)
    search = CatalogSearch(title=row["search_title"], products=cards) if row["search_title"] and cards else None
    return ChatMessageOut(id=row["id"], role=row["role"], content=row["content"],
                          products=cards[:CHAT_PREVIEW_CARDS] if search else cards,
                          search=search, created_at=row["created_at"])


def chat_user(user: sqlite3.Row | None = Depends(auth.current_user)) -> sqlite3.Row | None:
    """The logged-in shopper, or None for a guest. A session that must change its password is blocked."""
    if user is not None and user["must_change_password"]:
        return auth.require_user(user)  # raises the usual 403
    return user


def end_guest_chat(request: Request, response: Response) -> None:
    """After logging in, a shopper uses their saved history, so any guest chat is dropped."""
    guest_id = request.cookies.get(guest_chat.GUEST_COOKIE)
    if guest_id:
        guest_chat.store.forget(guest_id)
        response.delete_cookie(guest_chat.GUEST_COOKIE, path="/", secure=auth.COOKIE_SECURE, httponly=True,
                               samesite="lax")


def too_many_messages() -> HTTPException:
    return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                         detail="You're sending messages very quickly. Please wait a few minutes and try again.",
                         headers={"Retry-After": str(CHAT_WINDOW_MIN * 60)})


@app.get("/api/chat/history", response_model=list[ChatMessageOut])
def chat_history(request: Request, response: Response, user: sqlite3.Row | None = Depends(chat_user),
                 db: sqlite3.Connection = Depends(get_db_rw)) -> list[ChatMessageOut]:
    if user is None:  # a guest: this visit's messages only
        rows = guest_chat.store.messages(request.cookies.get(guest_chat.GUEST_COOKIE))
        return [message_out(db, r) for r in rows[-HISTORY_SHOWN:]]
    end_guest_chat(request, response)
    rows = db.execute(f"""
        SELECT {MESSAGE_COLUMNS} FROM chat_messages
        WHERE user_id = ? ORDER BY id DESC LIMIT ?
    """, (user["id"], HISTORY_SHOWN)).fetchall()
    return [message_out(db, r) for r in reversed(rows)]


async def ask_agent(body: ChatIn, db: sqlite3.Connection, user: sqlite3.Row | None, turns: list,
                    saved: int = 0, last_chat_at: datetime | None = None):
    page_path, viewing = page_for_agent(db, body.page)
    first_name, user_id = (user["first_name"], user["id"]) if user else (None, None)
    back = insights.back_in_stock(db, user_id) if user_id else []
    try:
        return await assistant.reply_to(body.message, first_name, turns, saved, last_chat_at, page_path, viewing,
                                        user_id, back)
    except Exception:
        log.exception("Shop assistant failed")  # the shopper's message isn't logged
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="The shop assistant couldn't answer just now. Please try again in a moment.")


@app.post("/api/chat", response_model=ChatMessageOut)
async def chat(body: ChatIn, request: Request, response: Response, user: sqlite3.Row | None = Depends(chat_user),
               db: sqlite3.Connection = Depends(get_db_rw)) -> ChatMessageOut:
    if user is None:
        return await guest_reply(body, request, response, db)
    end_guest_chat(request, response)

    recent = db.execute("""
        SELECT COUNT(*) FROM chat_messages
        WHERE user_id = ? AND role = 'user' AND created_at >= datetime('now', ?)
    """, (user["id"], f"-{CHAT_WINDOW_MIN} minutes")).fetchone()[0]
    if recent >= CHAT_MAX_MESSAGES:
        raise too_many_messages()

    history = db.execute("""
        SELECT role, content, product_ids, search_title FROM (
            SELECT id, role, content, product_ids, search_title FROM chat_messages
            WHERE user_id = ? ORDER BY id DESC LIMIT ?
        ) ORDER BY id
    """, (user["id"], assistant.HISTORY_MESSAGES)).fetchall()
    turns = [(r["role"], r["content"], json.loads(r["product_ids"]) if r["product_ids"] else [], r["search_title"])
             for r in history]
    # The shopper comes from the login session, never from the chat text.
    saved, last_at = db.execute("SELECT COUNT(*), MAX(created_at) FROM chat_messages WHERE user_id = ?",
                                (user["id"],)).fetchone()
    last_chat_at = datetime.fromisoformat(last_at).replace(tzinfo=timezone.utc) if last_at else None
    reply = await ask_agent(body, db, user, turns, saved, last_chat_at)

    db.execute("INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)", (user["id"], body.message))
    cur = db.execute("INSERT INTO chat_messages (user_id, role, content, product_ids, search_title) "
                     "VALUES (?, 'assistant', ?, ?, ?)",
                     (user["id"], reply.message, json.dumps(reply.product_ids), reply.search_title))
    db.commit()
    row = db.execute(f"SELECT {MESSAGE_COLUMNS} FROM chat_messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    return message_out(db, row)


async def guest_reply(body: ChatIn, request: Request, response: Response, db: sqlite3.Connection) -> ChatMessageOut:
    """A guest's turn: same agent and truth checks, but nothing is written to the database."""
    guest_id = request.cookies.get(guest_chat.GUEST_COOKIE)
    if not guest_id or len(guest_id) > 64:
        guest_id = guest_chat.GuestStore.new_id()
    if not guest_chat.store.allow(guest_id, auth.client_ip(request)):
        raise too_many_messages()
    rows = guest_chat.store.messages(guest_id)[-assistant.HISTORY_MESSAGES:]
    turns = [(r["role"], r["content"], r["product_ids"], r["search_title"]) for r in rows]
    reply = await ask_agent(body, db, None, turns)
    saved = guest_chat.store.add_turn(guest_id, body.message, reply.message, reply.product_ids, reply.search_title)
    response.set_cookie(guest_chat.GUEST_COOKIE, guest_id, max_age=guest_chat.GUEST_TTL_SECONDS, httponly=True,
                        secure=auth.COOKIE_SECURE, samesite="lax", path="/")
    return message_out(db, saved)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, reload=False)
