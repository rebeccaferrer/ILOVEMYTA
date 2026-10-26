"""Problem 9 back-end improvements: restock alerts and the missed-demand report.

1. Restock alerts ("notify me when it's back"): a logged-in shopper asks to hear when a sold-out
   size returns. Requests live in restock_requests. "Back in stock" is worked out live from
   inventory, so it works however stock gets updated. The website shows a banner and the agent
   mentions it; the shopper dismisses it, which deletes the request.
2. Missed demand: what shoppers asked for that the store couldn't supply (chat searches with no
   results, sold-out sizes they checked). Saved in demand_signals with no user id or chat text,
   only the search terms the agent used. Managers (users.is_manager) see a ranked report.

Make an account a manager from the hw4 folder:
    .venv/Scripts/python backend/insights.py make-manager someone@yale.edu
"""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

import auth
from catalog import image_url
from db import connect, get_db_rw

INSIGHT_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS restock_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES catalogue(product_id) ON DELETE CASCADE,
    size TEXT NOT NULL REFERENCES sizes(size),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, product_id, size)
);
CREATE INDEX IF NOT EXISTS idx_restock_requests_product ON restock_requests(product_id, size);

CREATE TABLE IF NOT EXISTS demand_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('no_results', 'sold_out_size')),
    request TEXT CHECK (request IS NULL OR length(request) <= 120),
    product_id TEXT REFERENCES catalogue(product_id) ON DELETE CASCADE,
    size TEXT REFERENCES sizes(size),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((kind = 'no_results' AND request IS NOT NULL AND product_id IS NULL)
        OR (kind = 'sold_out_size' AND product_id IS NOT NULL AND size IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_demand_signals_kind ON demand_signals(kind, created_at);
"""

MAX_OPEN_REQUESTS = 50  # per shopper, so a script can't fill the table


def ensure_insight_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(INSIGHT_TABLES_SQL)
    if "is_manager" not in {row[1] for row in conn.execute("PRAGMA table_info(users)")}:
        conn.execute("ALTER TABLE users ADD COLUMN is_manager INTEGER NOT NULL DEFAULT 0 CHECK (is_manager IN (0, 1))")
    conn.commit()


# --- Restock alerts --------------------------------------------------------------------------


class RestockIn(BaseModel):
    product_id: str = Field(max_length=100, pattern=r"^[a-z0-9-]+$")
    size: str = Field(max_length=4)


class RestockAlert(BaseModel):
    id: int
    product_id: str
    name: str
    size: str
    image_url: str
    status: str = Field(description="'waiting' while the size is sold out; 'back' once it's in stock again.")
    created_at: str


def save_restock_request(db: sqlite3.Connection, user_id: int, product_id: str, size: str) -> str:
    """Save one request. Returns 'saved', 'already_saved', 'in_stock', 'unknown' or 'too_many'.

    Shared by the website (POST /api/restock-alerts) and the agent's request_restock_alert tool.
    """
    row = db.execute("SELECT quantity FROM inventory WHERE product_id = ? AND size = ?", (product_id, size)).fetchone()
    if row is None:
        return "unknown"
    if row["quantity"] > 0:
        return "in_stock"
    if db.execute("SELECT 1 FROM restock_requests WHERE user_id = ? AND product_id = ? AND size = ?",
                  (user_id, product_id, size)).fetchone():
        return "already_saved"
    if db.execute("SELECT COUNT(*) FROM restock_requests WHERE user_id = ?", (user_id,)).fetchone()[0] >= MAX_OPEN_REQUESTS:
        return "too_many"
    db.execute("INSERT INTO restock_requests (user_id, product_id, size) VALUES (?, ?, ?)", (user_id, product_id, size))
    db.commit()
    return "saved"


def restock_alerts(db: sqlite3.Connection, user_id: int) -> list[RestockAlert]:
    rows = db.execute("""
        SELECT r.id, r.product_id, c.name, r.size, c.image_file_path, r.created_at, i.quantity
        FROM restock_requests r
        JOIN catalogue c USING (product_id)
        JOIN inventory i ON i.product_id = r.product_id AND i.size = r.size
        JOIN sizes s ON s.size = r.size
        WHERE r.user_id = ?
        ORDER BY i.quantity > 0 DESC, r.created_at DESC, s.sort_order
    """, (user_id,)).fetchall()
    return [RestockAlert(id=r["id"], product_id=r["product_id"], name=r["name"], size=r["size"],
                         image_url=image_url(r["image_file_path"]), status="back" if r["quantity"] > 0 else "waiting",
                         created_at=r["created_at"]) for r in rows]


def back_in_stock(db: sqlite3.Connection, user_id: int) -> list[tuple[str, str, str]]:
    """(product_id, name, size) for this shopper's requests that are in stock again (for the agent)."""
    return [(a.product_id, a.name, a.size) for a in restock_alerts(db, user_id) if a.status == "back"]


router = APIRouter(prefix="/api")


@router.get("/restock-alerts", response_model=list[RestockAlert])
def list_restock_alerts(user: sqlite3.Row = Depends(auth.require_user),
                        db: sqlite3.Connection = Depends(get_db_rw)) -> list[RestockAlert]:
    """The shopper's requests: 'back' ones first (the website shows those as good news)."""
    return restock_alerts(db, user["id"])


@router.post("/restock-alerts", response_model=list[RestockAlert], status_code=status.HTTP_201_CREATED)
def create_restock_alert(body: RestockIn, user: sqlite3.Row = Depends(auth.require_user),
                         db: sqlite3.Connection = Depends(get_db_rw)) -> list[RestockAlert]:
    result = save_restock_request(db, user["id"], body.product_id, body.size)
    if result == "unknown":
        raise HTTPException(status_code=404, detail="That product and size don't exist.")
    if result == "in_stock":
        raise HTTPException(status_code=409, detail="Good news: that size is in stock right now.")
    if result == "too_many":
        raise HTTPException(status_code=429, detail="You have the most alerts allowed. Remove some first.")
    return restock_alerts(db, user["id"])


@router.delete("/restock-alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_restock_alert(alert_id: int, user: sqlite3.Row = Depends(auth.require_user),
                         db: sqlite3.Connection = Depends(get_db_rw)) -> None:
    """Cancel a waiting alert, or dismiss a 'back in stock' one. Only the shopper's own."""
    db.execute("DELETE FROM restock_requests WHERE id = ? AND user_id = ?", (alert_id, user["id"]))
    db.commit()


# --- Missed demand ---------------------------------------------------------------------------


def record_demand(no_results: str | None, sold_out: set[tuple[str, str]]) -> None:
    """Save one chat turn's unmet demand. No user id, no chat text: only search terms and products."""
    if not no_results and not sold_out:
        return
    with closing(connect(read_only=False)) as db:
        if no_results:
            db.execute("INSERT INTO demand_signals (kind, request) VALUES ('no_results', ?)", (no_results[:120],))
        db.executemany("INSERT INTO demand_signals (kind, product_id, size) VALUES ('sold_out_size', ?, ?)",
                       sorted(sold_out))
        db.commit()


class UnmetSearch(BaseModel):
    request: str = Field(description="What was searched for, e.g. 'umbrella' or 'coral · Hoodies'.")
    times: int
    last_asked: str


class SoldOutAsk(BaseModel):
    product_id: str
    name: str
    size: str
    times_asked: int = Field(description="Chat stock checks that found this size sold out.")
    shoppers_waiting: int = Field(description="Open 'notify me' requests for this size.")
    in_stock_now: int
    last_asked: str | None


class DemandReport(BaseModel):
    days: int
    unmet_searches: list[UnmetSearch]
    sold_out_sizes: list[SoldOutAsk]


def require_manager(user: sqlite3.Row = Depends(auth.require_user)) -> sqlite3.Row:
    if not user["is_manager"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This report is for Campus Customs managers.")
    return user


@router.get("/manager/demand-report", response_model=DemandReport)
def demand_report(days: int = 30, _: sqlite3.Row = Depends(require_manager),
                  db: sqlite3.Connection = Depends(get_db_rw)) -> DemandReport:
    """Top unmet requests over the last `days` days (1–365): searches with no results, and sold-out
    sizes shoppers asked about or are waiting for, most wanted first."""
    days = max(1, min(days, 365))
    since = f"-{days} days"
    searches = db.execute("""
        SELECT lower(request) AS request, COUNT(*) AS times, MAX(created_at) AS last_asked
        FROM demand_signals WHERE kind = 'no_results' AND created_at >= datetime('now', ?)
        GROUP BY lower(request) ORDER BY times DESC, last_asked DESC LIMIT 25
    """, (since,)).fetchall()
    sizes = db.execute("""
        WITH asks AS (
            SELECT product_id, size, COUNT(*) AS times, MAX(created_at) AS last_asked FROM demand_signals
            WHERE kind = 'sold_out_size' AND created_at >= datetime('now', ?) GROUP BY product_id, size
        ), waiting AS (
            SELECT product_id, size, COUNT(*) AS shoppers FROM restock_requests GROUP BY product_id, size
        ), wanted AS (
            SELECT product_id, size FROM asks UNION SELECT product_id, size FROM waiting
        )
        SELECT w.product_id, c.name, w.size, COALESCE(a.times, 0) AS times, COALESCE(r.shoppers, 0) AS shoppers,
               i.quantity, a.last_asked
        FROM wanted w
        JOIN catalogue c USING (product_id)
        JOIN inventory i ON i.product_id = w.product_id AND i.size = w.size
        LEFT JOIN asks a ON a.product_id = w.product_id AND a.size = w.size
        LEFT JOIN waiting r ON r.product_id = w.product_id AND r.size = w.size
        ORDER BY shoppers * 3 + times DESC, c.name, w.size LIMIT 25
    """, (since,)).fetchall()
    return DemandReport(
        days=days,
        unmet_searches=[UnmetSearch(request=r["request"], times=r["times"], last_asked=r["last_asked"]) for r in searches],
        sold_out_sizes=[SoldOutAsk(product_id=r["product_id"], name=r["name"], size=r["size"], times_asked=r["times"],
                                   shoppers_waiting=r["shoppers"], in_stock_now=r["quantity"], last_asked=r["last_asked"])
                        for r in sizes],
    )


def _make_manager(email: str) -> None:
    with closing(connect(read_only=False)) as db:
        ensure_insight_tables(db)
        changed = db.execute("UPDATE users SET is_manager = 1 WHERE email = ?", (email.strip().lower(),)).rowcount
        db.commit()
    print(f"{email} is now a manager." if changed else f"No account uses {email}.")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "make-manager":
        raise SystemExit("Usage: python backend/insights.py make-manager someone@yale.edu")
    _make_manager(sys.argv[2])
