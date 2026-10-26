"""Accounts: create account, log in, log out, and "who am I".

Security measures (see output/harness.md for the reasoning):
- Passwords: PBKDF2-SHA256 with 600,000 rounds and a 16-byte salt. Guessable passwords
  are refused at sign-up, including ones built from the person's name or Yale words.
  Older hashes are upgraded the next time that person logs in.
- Guessing attacks: an email is locked for 15 minutes after 5 wrong passwords, and an
  address (IP) after 20; sign-ups are limited per address.
- No account discovery at login: unknown emails and wrong passwords get the same
  message and take the same time.
- Sessions: a random 256-bit token in an HttpOnly, SameSite=Lax, Secure cookie. Only
  its SHA-256 is stored, so a leaked database can't be used to log in. Sessions end
  after 7 days or at log out.
- Older accounts: if a password that predates the rules breaks them, the login still
  works but the session is marked "must change password". Such a session can only
  change the password or log out (see require_user) until a strong one is chosen.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, StringConstraints

from db import HW_DIR, get_db_rw

# passwords.py lives in hw4/, shared with the data scripts. Appended (not prepended) so that
# backend/models.py, not hw4/models.py, is the "models" module here.
if str(HW_DIR) not in sys.path:
    sys.path.append(str(HW_DIR))
from passwords import (  # noqa: E402
    DUMMY_HASH,
    MAX_LENGTH,
    hash_password,
    needs_rehash,
    password_problems,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "cc_session"
SESSION_DAYS = 7
COOKIE_SECURE = os.getenv("CC_COOKIE_SECURE", "1") == "1"  # browsers treat localhost as secure

LOGIN_WINDOW_MIN = 15
MAX_FAILS_PER_EMAIL = 5
MAX_FAILS_PER_IP = 20
SIGNUP_WINDOW_MIN = 60
MAX_SIGNUP_ATTEMPTS_PER_IP = 10

LOGIN_FAILED = "Email or password is incorrect."

AUTH_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS auth_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('login', 'signup')),
    email TEXT NOT NULL COLLATE NOCASE,
    ip TEXT NOT NULL,
    success INTEGER NOT NULL CHECK (success IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_auth_attempts_email ON auth_attempts(email, created_at);
CREATE INDEX IF NOT EXISTS idx_auth_attempts_ip ON auth_attempts(ip, created_at);
"""


def ensure_auth_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(AUTH_TABLES_SQL)
    # Sessions tables made before the change-password step lack this column.
    if "must_change_password" not in {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}:
        conn.execute("ALTER TABLE sessions ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0 "
                     "CHECK (must_change_password IN (0, 1))")
    conn.execute("DELETE FROM auth_attempts WHERE created_at < datetime('now', '-1 day')")
    conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
    conn.commit()


# --- Request / response models ---------------------------------------------------------------

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50, pattern=r"^[^\x00-\x1f<>]+$")]


class SignupIn(BaseModel):
    first_name: Name
    last_name: Name
    email: EmailStr
    password: str = Field(max_length=1024)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=1024)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(max_length=1024)


class UserOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    must_change_password: bool = False
    is_manager: bool = False  # can see the missed-demand report (insights.py)


def field_error(code: int, field: str, messages: list[str]) -> HTTPException:
    return HTTPException(status_code=code, detail={"field": field, "messages": messages})


# --- Helpers ---------------------------------------------------------------------------------


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def record_attempt(db: sqlite3.Connection, kind: str, email: str, ip: str, success: bool) -> int:
    cur = db.execute("INSERT INTO auth_attempts (kind, email, ip, success) VALUES (?, ?, ?, ?)", (kind, email, ip, int(success)))
    db.commit()
    return cur.lastrowid


def too_many(retry_after_min: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many attempts. Please wait {retry_after_min} minutes and try again.",
        headers={"Retry-After": str(retry_after_min * 60)},
    )


def check_login_limits(db: sqlite3.Connection, email: str, ip: str) -> None:
    window = f"-{LOGIN_WINDOW_MIN} minutes"
    # Failures for this email since its last successful login, within the window.
    email_fails = db.execute("""
        SELECT COUNT(*) FROM auth_attempts
        WHERE kind = 'login' AND email = ? AND success = 0 AND created_at >= datetime('now', ?)
          AND created_at > COALESCE((SELECT MAX(created_at) FROM auth_attempts
                                     WHERE kind = 'login' AND email = ? AND success = 1), '')
    """, (email, window, email)).fetchone()[0]
    ip_fails = db.execute("""
        SELECT COUNT(*) FROM auth_attempts
        WHERE kind = 'login' AND ip = ? AND success = 0 AND created_at >= datetime('now', ?)
    """, (ip, window)).fetchone()[0]
    if email_fails >= MAX_FAILS_PER_EMAIL or ip_fails >= MAX_FAILS_PER_IP:
        raise too_many(LOGIN_WINDOW_MIN)


def check_signup_limits(db: sqlite3.Connection, ip: str) -> None:
    attempts = db.execute("""
        SELECT COUNT(*) FROM auth_attempts
        WHERE kind = 'signup' AND ip = ? AND created_at >= datetime('now', ?)
    """, (ip, f"-{SIGNUP_WINDOW_MIN} minutes")).fetchone()[0]
    if attempts >= MAX_SIGNUP_ATTEMPTS_PER_IP:
        raise too_many(SIGNUP_WINDOW_MIN)


def start_session(db: sqlite3.Connection, response: Response, user_id: int, must_change_password: bool = False) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    db.execute("INSERT INTO sessions (token_hash, user_id, expires_at, must_change_password) VALUES (?, ?, ?, ?)",
               (token_hash(token), user_id, expires.strftime("%Y-%m-%d %H:%M:%S"), int(must_change_password)))
    db.commit()
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=COOKIE_SECURE, samesite="lax", path="/")


def user_out(row: sqlite3.Row, must_change_password: bool = False) -> UserOut:
    return UserOut(id=row["id"], first_name=row["first_name"], last_name=row["last_name"], email=row["email"],
                   must_change_password=must_change_password,
                   is_manager=bool(row["is_manager"]) if "is_manager" in row.keys() else False)


def current_user(request: Request, db: sqlite3.Connection = Depends(get_db_rw)) -> sqlite3.Row | None:
    """The logged-in shopper (with their session's must_change_password flag), or None."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return db.execute("""
        SELECT u.id, u.first_name, u.last_name, u.email, u.is_manager, s.must_change_password
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ? AND s.expires_at > datetime('now')
    """, (token_hash(token),)).fetchone()


def require_user(user: sqlite3.Row | None = Depends(current_user)) -> sqlite3.Row:
    """For shopper features (like the chat): a logged-in shopper whose password is up to standard."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in.")
    if user["must_change_password"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"code": "password_change_required", "messages": ["Please choose a new password first."]})
    return user


# --- Routes ----------------------------------------------------------------------------------


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, request: Request, response: Response, db: sqlite3.Connection = Depends(get_db_rw)) -> UserOut:
    ip = client_ip(request)
    email = body.email.strip().lower()
    check_signup_limits(db, ip)
    attempt_id = record_attempt(db, "signup", email, ip, success=False)  # counts toward the limit either way

    problems = password_problems(body.password, body.first_name, body.last_name, email)
    if problems:
        raise field_error(400, "password", problems)
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise field_error(409, "email", ["An account with this email already exists. Try logging in instead."])

    try:
        cur = db.execute(
            "INSERT INTO users (first_name, last_name, email, password_hash) VALUES (?, ?, ?, ?)",
            (body.first_name, body.last_name, email, hash_password(body.password)),
        )
    except sqlite3.IntegrityError:  # two sign-ups for the same email at the same moment
        raise field_error(409, "email", ["An account with this email already exists. Try logging in instead."])
    db.execute("UPDATE auth_attempts SET success = 1 WHERE id = ?", (attempt_id,))
    db.commit()
    start_session(db, response, cur.lastrowid)
    return UserOut(id=cur.lastrowid, first_name=body.first_name, last_name=body.last_name, email=email)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: sqlite3.Connection = Depends(get_db_rw)) -> UserOut:
    ip = client_ip(request)
    email = body.email.strip().lower()
    check_login_limits(db, email, ip)

    row = db.execute("SELECT id, first_name, last_name, email, is_manager, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    # Always run one full hash check, so a missing account takes as long as a wrong password.
    ok = verify_password(body.password, row["password_hash"] if row else DUMMY_HASH) and row is not None
    record_attempt(db, "login", email, ip, success=ok)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILED)

    if needs_rehash(row["password_hash"]) and len(body.password) <= MAX_LENGTH:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.password), row["id"]))
        db.commit()
    # Passwords set before today's rules may break them; this is the only moment we can tell.
    must_change = bool(password_problems(body.password, row["first_name"], row["last_name"], row["email"]))
    start_session(db, response, row["id"], must_change_password=must_change)
    return user_out(row, must_change)


@router.post("/change-password", response_model=UserOut)
def change_password(body: ChangePasswordIn, request: Request, response: Response,
                    user: sqlite3.Row | None = Depends(current_user),
                    db: sqlite3.Connection = Depends(get_db_rw)) -> UserOut:
    """Works for any logged-in shopper; required before anything else when the session is flagged."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in.")
    ip = client_ip(request)
    # A stolen session alone can't take over the account: the current password is required,
    # and wrong guesses count toward the same lockout as the login page.
    check_login_limits(db, user["email"], ip)
    stored = db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()[0]
    if not verify_password(body.current_password, stored):
        record_attempt(db, "login", user["email"], ip, success=False)
        raise field_error(401, "current_password", ["Your current password is incorrect."])
    record_attempt(db, "login", user["email"], ip, success=True)

    if body.new_password == body.current_password:
        raise field_error(400, "new_password", ["Choose a password different from your current one."])
    problems = password_problems(body.new_password, user["first_name"], user["last_name"], user["email"])
    if problems:
        raise field_error(400, "new_password", problems)

    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.new_password), user["id"]))
    db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))  # log out every other device too
    db.commit()
    start_session(db, response, user["id"])
    return user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: sqlite3.Connection = Depends(get_db_rw)) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax")


@router.get("/me", response_model=UserOut)
def me(user: sqlite3.Row | None = Depends(current_user)) -> UserOut:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in.")
    return user_out(user, bool(user["must_change_password"]))
