"""Problem 2 cleanup of campus_customs.db (run after normalize_garment_types.py).

catalogue
  - readable product names (from the HW3 catalogue, with hand fixes)
  - real descriptions, colors and tags for the 3 "vision blocked" placeholder products
  - `colors` split into `primary_color` (garment) + `accent_colors` (print), standard names only
  - search tags de-duplicated ignoring case; the noise tag "Campus Customs" removed
  - `price` (decimal dollars) replaced by `price_cents` (whole cents)
inventory
  - `sizes` lookup table so sizes sort XS -> XXL; quantity can't go below 0
users
  - password hashes record their iteration count; emails lowercased and unique ignoring case
  - the duplicated `name` column dropped; first and last names required
chat_messages
  - stored product snapshots (stale prices and stock) replaced by a list of product ids
  - role limited to 'user' / 'assistant'

Backs up the database first. Runs once: it stops if the database is already cleaned.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from models import SIZES, Color
from passwords import SEED_ITERATIONS, verify_password

HERE = Path(__file__).parent
DB_PATH = HERE / "data" / "data" / "campus_customs.db"
HW3_CATALOGUE = HERE / "data" / "hw3_catalogue.json"  # copy of hw3/output/catalogue.json

# Product names: HW3's names, except where they were wrong or inconsistent.
NAME_FIXES = {
    "baseball-left-chest-crewneck": "Yale Baseball Left-Chest Crewneck",  # HW3 name clashed with the sports crewneck
    "benjamin-franklin-fleece-jacket": "Benjamin Franklin College Fleece Jacket",
    "berkeley-1-4-zip": "Berkeley College Quarter-Zip",
    "champion-full-zip-hood": "Yale Champion Full-Zip Hoodie",
    "district-tri-blend-t-shirt-vintage-shield": "Yale Vintage Shield Tri-Blend T-Shirt",
    "district-vit-crewneck-vintage-standing-bulldog": "Yale Vintage Standing Bulldog Crewneck",
    "district-vit-hoodie-vintage-bulldog": "Yale Vintage Bulldog Hoodie",
    "saybrook-sweater-fleece-jacket": "Saybrook College Fleece Jacket",
    "squash-left-chest-tennis": "Yale Squash Left-Chest Crewneck",  # it's a crewneck, not a shirt
    "the-forest-school-hoodie": "Yale Forest School Hoodie",
    "ua-gameday-double-knit-hood": "Yale Under Armour Gameday Double-Knit Hoodie",
    "yale-maplehouse-diana-mockneck": "Yale Maple House Diana Mockneck",
}
# Wording made consistent across all names.
NAME_REPLACEMENTS = [(" Quarter-Zip Pullover", " Quarter-Zip"), (" Crewneck Sweatshirt", " Crewneck")]

# Every color spelling in the data -> a standard Color.
COLOR_MAP = {
    "navy blue": Color.navy, "royal blue": Color.blue,
    "heather grey": Color.heather_gray, "dark heather gray": Color.charcoal_gray,
    "dark heather charcoal": Color.charcoal_gray, "heather charcoal gray": Color.charcoal_gray,
    "ivory": Color.cream, "dusty coral": Color.coral,
}
# Garment color where the first listed color is too vague.
PRIMARY_FIXES = {"benjamin-franklin-fleece-jacket": Color.heather_gray}  # listed as plain "gray"

PLACEHOLDER_TAGS = {"campus customs"}
STUB_MARKER = "Vision blocked; filename-based stub."


def std_color(raw: str) -> Color:
    raw = raw.strip().lower()
    return COLOR_MAP.get(raw) or Color(raw)  # Color(raw) raises on anything unknown


def dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        if item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


def clean_catalogue(conn: sqlite3.Connection) -> None:
    hw3 = {p["id"]: p for p in json.loads(HW3_CATALOGUE.read_text(encoding="utf-8"))["products"]}
    conn.execute("CREATE TABLE color_names (color TEXT PRIMARY KEY, sort_order INTEGER NOT NULL)")
    conn.executemany("INSERT INTO color_names VALUES (?, ?)", [(c.value, i) for i, c in enumerate(Color, 1)])
    conn.execute("""
        CREATE TABLE catalogue_new (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            garment_type TEXT NOT NULL REFERENCES garment_types(garment_type),
            description TEXT NOT NULL,
            primary_color TEXT NOT NULL REFERENCES color_names(color),
            accent_colors TEXT NOT NULL CHECK (json_valid(accent_colors)),
            search_tags TEXT NOT NULL CHECK (json_valid(search_tags)),
            image_file_path TEXT NOT NULL,
            price_cents INTEGER NOT NULL CHECK (price_cents > 0)
        )""")

    rows = conn.execute("SELECT product_id, garment_type, description, colors, search_tags, "
                        "image_file_path, price FROM catalogue").fetchall()
    # One spelling per tag across the whole catalogue: the most common capitalization wins.
    tag_counts = Counter(t.strip() for row in rows for t in json.loads(row[4]))
    tag_spelling = {}
    for tag, _ in tag_counts.most_common():
        tag_spelling.setdefault(tag.lower(), tag)

    for pid, gtype, description, colors_json, tags_json, image, price in rows:
        ref = hw3[pid]
        name = NAME_FIXES.get(pid, ref["product_name"])
        for old, new in NAME_REPLACEMENTS:
            name = name.replace(old, new)
        colors = json.loads(colors_json)
        tags = json.loads(tags_json)

        if description.endswith(STUB_MARKER):
            description = ref["short_description"]
            colors = [ref["primary_color"], *ref["secondary_colors"]]
            tags = ["Yale", ref["affiliation"], gtype, *ref["style_tags"], f"{std_color(colors[0]).value} {gtype}"]
            print(f"  filled placeholder product {pid}")

        standard = [std_color(c) for c in colors]
        primary = PRIMARY_FIXES.get(pid, standard[0])
        accents = dedupe([c.value for c in standard if c != primary])
        tags = [t.strip() for t in tags if t.strip().lower() not in PLACEHOLDER_TAGS]
        tags = dedupe([tag_spelling.get(t.lower(), t) for t in tags])

        conn.execute("INSERT INTO catalogue_new VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (pid, name, gtype, description, primary.value, json.dumps(accents),
                      json.dumps(tags), image, round(price * 100)))

    conn.execute("DROP TABLE catalogue")
    conn.execute("ALTER TABLE catalogue_new RENAME TO catalogue")
    conn.execute("CREATE INDEX idx_catalogue_garment_type ON catalogue(garment_type)")
    conn.execute("CREATE INDEX idx_catalogue_primary_color ON catalogue(primary_color)")


def clean_inventory(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE sizes (size TEXT PRIMARY KEY, sort_order INTEGER NOT NULL)")
    conn.executemany("INSERT INTO sizes VALUES (?, ?)", [(s, i) for i, s in enumerate(SIZES, 1)])
    conn.execute("""
        CREATE TABLE inventory_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL REFERENCES catalogue(product_id),
            size TEXT NOT NULL REFERENCES sizes(size),
            quantity INTEGER NOT NULL CHECK (quantity >= 0),
            UNIQUE (product_id, size)
        )""")
    conn.execute("INSERT INTO inventory_new SELECT id, product_id, size, quantity FROM inventory")
    conn.execute("DROP TABLE inventory")
    conn.execute("ALTER TABLE inventory_new RENAME TO inventory")


def clean_users(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL CHECK (trim(first_name) <> ''),
            last_name TEXT NOT NULL CHECK (trim(last_name) <> ''),
            email TEXT NOT NULL UNIQUE COLLATE NOCASE
                CHECK (email = lower(trim(email)) AND email LIKE '_%@_%._%'),
            password_hash TEXT NOT NULL CHECK (password_hash LIKE 'pbkdf2_sha256$%$%$%'),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""")
    for uid, name, first, last, email, pw_hash, created in conn.execute(
            "SELECT id, name, first_name, last_name, email, password_hash, created_at FROM users").fetchall():
        if not (first and last):
            first, _, last = name.partition(" ")
        algorithm, salt, digest = pw_hash.split("$")
        conn.execute("INSERT INTO users_new VALUES (?, ?, ?, ?, ?, ?)",
                     (uid, first.strip(), last.strip(), email.strip().lower(),
                      f"{algorithm}${SEED_ITERATIONS}${salt}${digest}", created))
    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_new RENAME TO users")


def clean_chat_messages(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE chat_messages_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            product_ids TEXT CHECK (product_ids IS NULL OR json_valid(product_ids)),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""")
    for mid, uid, role, content, products_json, created in conn.execute(
            "SELECT id, user_id, role, content, products_json, created_at FROM chat_messages").fetchall():
        ids = json.dumps([p["product_id"] for p in json.loads(products_json)]) if products_json else None
        conn.execute("INSERT INTO chat_messages_new VALUES (?, ?, ?, ?, ?, ?)",
                     (mid, uid, role, content, ids, created))
    conn.execute("DROP TABLE chat_messages")
    conn.execute("ALTER TABLE chat_messages_new RENAME TO chat_messages")
    conn.execute("CREATE INDEX idx_chat_messages_user ON chat_messages(user_id, id)")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(catalogue)")}
    if "price_cents" in columns:
        raise SystemExit("Database is already cleaned; nothing to do.")

    backup = DB_PATH.with_name(f"campus_customs.backup-{datetime.now():%Y%m%d-%H%M%S}.db")
    conn.close()
    shutil.copy2(DB_PATH, backup)
    print(f"Backed up database to {backup.name}")

    conn = sqlite3.connect(DB_PATH, isolation_level=None)  # manage the transaction by hand
    conn.execute("PRAGMA foreign_keys = OFF")  # tables are rebuilt one at a time
    conn.execute("BEGIN")
    try:
        clean_catalogue(conn)
        clean_inventory(conn)
        clean_users(conn)
        clean_chat_messages(conn)
        problems = conn.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise RuntimeError(f"Foreign key problems: {problems}")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("VACUUM")

    test_user = conn.execute("SELECT password_hash FROM users WHERE id = 1").fetchone()[0]
    print("Test User password still verifies:", verify_password("password", test_user))
    conn.close()


if __name__ == "__main__":
    main()
