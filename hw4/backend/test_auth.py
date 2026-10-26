"""Security tests for create-account and login. They run against a throwaway copy of
the database, so the real one is never touched.

Run from the hw4 folder:  .venv/Scripts/python -m pytest backend -q
"""

from __future__ import annotations

import sqlite3
import time

from conftest import TMP_DB as _tmp  # throwaway database copy

import pytest  # noqa: E402
from fastapi import Depends  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from auth import require_user  # noqa: E402

STRONG = "violet-teapot-glacier-41"
STRONG_2 = "mossy-kettle-orbit-73"
SEED_EMAIL = "test@campuscustoms.yale.edu"  # seed account from the course database
SEED_PASSWORD = "password"                   # its known test password (seed data)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(_tmp)
    conn.row_factory = sqlite3.Row
    return conn


with db() as _conn:
    SEED_HASH = _conn.execute("SELECT password_hash FROM users WHERE email = ?", (SEED_EMAIL,)).fetchone()[0]


# A stand-in for shopper features (like the coming chat) that use require_user.
@main.app.get("/api/test-only/shopper-feature")
def _shopper_feature(user=Depends(require_user)):
    return {"ok": True}


@pytest.fixture()
def client():
    with TestClient(main.app, base_url="https://testserver") as c:
        with db() as conn:
            conn.execute("DELETE FROM auth_attempts")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM users WHERE email LIKE '%@example.com'")
            conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (SEED_HASH, SEED_EMAIL))
        yield c


def signup(client, email="ada@example.com", password=STRONG, first="Ada", last="Byron", **kw):
    return client.post("/api/auth/signup", json={"first_name": first, "last_name": last, "email": email, "password": password}, **kw)


# --- Create account --------------------------------------------------------------------------


def test_signup_logs_in_and_me_returns_user(client):
    r = signup(client)
    assert r.status_code == 201
    assert r.json()["email"] == "ada@example.com"
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["first_name"] == "Ada"


@pytest.mark.parametrize("password", [
    "short",                    # too short
    "Password123!",             # common pattern
    "qwertyuiop123",            # keyboard run
    "yalebulldogs2026",         # Yale words + year
    "AdaByron2026!!",           # the person's own name
    "ada@example.com1",        # the person's own email
])
def test_signup_refuses_guessable_passwords(client, password):
    r = signup(client, password=password)
    assert r.status_code == 400
    assert r.json()["detail"]["field"] == "password"


def test_signup_refuses_duplicate_email_ignoring_case(client):
    assert signup(client).status_code == 201
    r = signup(client, email="ADA@Example.COM")
    assert r.status_code == 409 and r.json()["detail"]["field"] == "email"


def test_password_is_never_stored_or_returned_in_plain_text(client):
    r = signup(client)
    assert STRONG not in r.text
    with db() as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE email = 'ada@example.com'").fetchone()[0]
        dump = "\n".join(conn.iterdump())
    assert stored.startswith("pbkdf2_sha256$600000$")
    assert len(stored.split("$")[2]) == 32  # 16-byte random salt
    assert STRONG not in dump


@pytest.mark.parametrize("body", [
    {"first_name": "Ada", "last_name": "Byron", "email": "not-an-email", "password": STRONG},
    {"first_name": "<script>", "last_name": "Byron", "email": "x@example.com", "password": STRONG},
    {"first_name": "", "last_name": "Byron", "email": "x@example.com", "password": STRONG},
    {"first_name": "Ada", "last_name": "Byron", "email": "x@example.com", "password": "x" * 2000},
])
def test_signup_rejects_bad_input(client, body):
    assert client.post("/api/auth/signup", json=body).status_code == 422


# --- Log in ----------------------------------------------------------------------------------


def test_login_and_logout(client):
    signup(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/login", json={"email": "Ada@Example.com", "password": STRONG})
    assert r.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "ada@example.com"


def test_wrong_password_and_unknown_email_look_identical(client):
    signup(client)
    client.post("/api/auth/logout")
    t0 = time.perf_counter()
    wrong = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "nope-nope-nope"})
    t1 = time.perf_counter()
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "nope-nope-nope"})
    t2 = time.perf_counter()
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert (t2 - t1) > 0.5 * (t1 - t0)  # unknown email still pays for a full hash check


def test_account_locks_after_five_wrong_passwords(client):
    signup(client)
    client.post("/api/auth/logout")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "ada@example.com", "password": "guess-guess-guess"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "ada@example.com", "password": STRONG})
    assert r.status_code == 429  # even the right password is refused while locked
    assert int(r.headers["retry-after"]) > 0


def test_one_address_cannot_spray_many_accounts(client):
    for i in range(20):
        client.post("/api/auth/login", json={"email": f"victim{i}@example.com", "password": "Spring2026!!"})
    assert client.post("/api/auth/login", json={"email": "other@example.com", "password": "x"}).status_code == 429


def test_signups_are_rate_limited_per_address(client):
    codes = [signup(client, email=f"bot{i}@example.com").status_code for i in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


def test_seed_account_hash_is_upgraded_on_login(client):
    with db() as conn:
        before = conn.execute("SELECT password_hash FROM users WHERE email = ?", (SEED_EMAIL,)).fetchone()[0]
    assert before.startswith("pbkdf2_sha256$120000$")
    assert client.post("/api/auth/login", json={"email": SEED_EMAIL, "password": SEED_PASSWORD}).status_code == 200
    with db() as conn:
        after = conn.execute("SELECT password_hash FROM users WHERE email = ?", (SEED_EMAIL,)).fetchone()[0]
    assert after.startswith("pbkdf2_sha256$600000$")


# --- Sessions --------------------------------------------------------------------------------


def test_session_cookie_is_locked_down(client):
    r = signup(client)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    token = r.cookies.get("cc_session")
    with db() as conn:
        stored = [row[0] for row in conn.execute("SELECT token_hash FROM sessions")]
    assert token and token not in stored  # only a hash of the token is kept


def test_logged_out_token_cannot_be_reused(client):
    r = signup(client)
    token = r.cookies.get("cc_session")
    client.post("/api/auth/logout")
    client.cookies.set("cc_session", token)
    assert client.get("/api/auth/me").status_code == 401


def test_requests_from_other_websites_are_refused(client):
    r = signup(client, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


# --- Forced password change for older, weak passwords ----------------------------------------


def change(client, current, new):
    return client.post("/api/auth/change-password", json={"current_password": current, "new_password": new})


def test_weak_old_password_must_be_changed_before_anything_else(client):
    r = client.post("/api/auth/login", json={"email": SEED_EMAIL, "password": SEED_PASSWORD})
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    assert client.get("/api/auth/me").json()["must_change_password"] is True
    blocked = client.get("/api/test-only/shopper-feature")
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "password_change_required"

    assert change(client, "not-my-password", STRONG).json()["detail"]["field"] == "current_password"
    assert change(client, SEED_PASSWORD, "Password123!").json()["detail"]["field"] == "new_password"
    assert change(client, SEED_PASSWORD, "TestUser2026!").status_code == 400  # built from their own name

    ok = change(client, SEED_PASSWORD, STRONG)
    assert ok.status_code == 200 and ok.json()["must_change_password"] is False
    assert client.get("/api/auth/me").json()["must_change_password"] is False
    assert client.get("/api/test-only/shopper-feature").status_code == 200

    with db() as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE email = ?", (SEED_EMAIL,)).fetchone()[0]
    assert stored.startswith("pbkdf2_sha256$600000$")
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": SEED_EMAIL, "password": SEED_PASSWORD}).status_code == 401
    again = client.post("/api/auth/login", json={"email": SEED_EMAIL, "password": STRONG})
    assert again.status_code == 200 and again.json()["must_change_password"] is False


def test_strong_password_is_not_flagged(client):
    signup(client)
    client.post("/api/auth/logout")
    r = client.post("/api/auth/login", json={"email": "ada@example.com", "password": STRONG})
    assert r.json()["must_change_password"] is False
    assert client.get("/api/test-only/shopper-feature").status_code == 200


def test_new_password_must_differ_from_current(client):
    signup(client)
    r = change(client, STRONG, STRONG)
    assert r.status_code == 400 and r.json()["detail"]["field"] == "new_password"


def test_change_password_needs_a_login(client):
    assert change(client, STRONG, STRONG_2).status_code == 401


def test_changing_password_logs_out_other_devices(client):
    signup(client)
    with TestClient(main.app, base_url="https://testserver") as other_device:
        assert other_device.post("/api/auth/login", json={"email": "ada@example.com", "password": STRONG}).status_code == 200
        assert change(client, STRONG, STRONG_2).status_code == 200
        assert other_device.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me").status_code == 200  # this device gets a fresh session


def test_wrong_current_passwords_count_toward_lockout(client):
    signup(client)
    for _ in range(5):
        assert change(client, "guess-guess-guess", STRONG_2).status_code == 401
    assert change(client, STRONG, STRONG_2).status_code == 429
