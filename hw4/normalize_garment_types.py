"""Turn the free-text catalogue.garment_type column into structured data.

- Adds a `garment_types` lookup table (the GarmentType vocabulary from models.py).
- Maps every raw garment_type value to one of those types.
- Rebuilds `catalogue` so garment_type is a foreign key into `garment_types`,
  so the database itself rejects any new free-text value.

Backs up the database first. Run before clean_database.py; it stops if that
cleanup has already rebuilt the catalogue.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from models import GARMENT_TYPE_LABELS, GarmentType

DB_PATH = Path(__file__).parent / "data" / "data" / "campus_customs.db"

# Every raw value seen in the catalogue -> its canonical type.
RAW_TO_TYPE: dict[str, GarmentType] = {
    "short-sleeve T-shirt": GarmentType.t_shirt,
    "short-sleeve t-shirt": GarmentType.t_shirt,
    "short-sleeve crew-neck t-shirt": GarmentType.t_shirt,
    "heavyweight short-sleeve t-shirt": GarmentType.t_shirt,
    "long-sleeve performance shirt": GarmentType.long_sleeve_shirt,
    "men's long-sleeve performance shirt": GarmentType.long_sleeve_shirt,
    "crewneck": GarmentType.crewneck_sweatshirt,
    "raglan crewneck sweatshirt": GarmentType.crewneck_sweatshirt,
    "hoodie": GarmentType.hooded_sweatshirt,
    "pullover hoodie": GarmentType.hooded_sweatshirt,
    "hooded pullover sweatshirt": GarmentType.hooded_sweatshirt,
    "quarter-zip pullover sweatshirt": GarmentType.quarter_zip_pullover,
    "mockneck sweatshirt": GarmentType.mock_neck_pullover,
    "full-zip fleece jacket": GarmentType.fleece_jacket,
    "bomber jacket": GarmentType.jacket,
}
# Per-product fixes where the raw label alone is too vague.
PRODUCT_OVERRIDES: dict[str, GarmentType] = {
    "berkeley-sweater-fleece-jacket": GarmentType.fleece_jacket,  # raw "jacket"; vision was blocked
}

CATALOGUE_DDL = """
CREATE TABLE catalogue (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    garment_type TEXT NOT NULL REFERENCES garment_types(garment_type),
    description TEXT NOT NULL,
    colors TEXT NOT NULL,
    search_tags TEXT NOT NULL,
    image_file_path TEXT NOT NULL,
    price REAL NOT NULL
)"""


def canonical_type(product_id: str, raw: str) -> GarmentType:
    if product_id in PRODUCT_OVERRIDES:
        return PRODUCT_OVERRIDES[product_id]
    if raw in RAW_TO_TYPE:
        return RAW_TO_TYPE[raw]
    try:
        return GarmentType(raw)
    except ValueError:
        raise SystemExit(f"Unmapped garment_type {raw!r} for {product_id}; add it to RAW_TO_TYPE.")


def main() -> None:
    with sqlite3.connect(DB_PATH) as check:
        if "price" not in {row[1] for row in check.execute("PRAGMA table_info(catalogue)")}:
            raise SystemExit("clean_database.py has already run; garment types are already normalized.")
    backup = DB_PATH.with_name(f"campus_customs.backup-{datetime.now():%Y%m%d-%H%M%S}.db")
    shutil.copy2(DB_PATH, backup)
    print(f"Backed up database to {backup.name}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS garment_types (
                garment_type TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                sort_order INTEGER NOT NULL
            )""")
        conn.executemany(
            "INSERT OR REPLACE INTO garment_types VALUES (?, ?, ?)",
            [(t.value, GARMENT_TYPE_LABELS[t], i) for i, t in enumerate(GarmentType, start=1)],
        )

        changes = {}
        for product_id, raw in conn.execute("SELECT product_id, garment_type FROM catalogue").fetchall():
            new = canonical_type(product_id, raw).value
            if new != raw:
                changes[(raw, new)] = changes.get((raw, new), 0) + 1
            conn.execute("UPDATE catalogue SET garment_type = ? WHERE product_id = ?", (new, product_id))

        # SQLite can't add a foreign key to an existing column, so rebuild the table
        # (create-copy-drop-rename keeps inventory's foreign key pointing at "catalogue").
        conn.execute(CATALOGUE_DDL.replace("CREATE TABLE catalogue", "CREATE TABLE catalogue_new"))
        conn.execute("INSERT INTO catalogue_new SELECT product_id, name, garment_type, description, colors, "
                     "search_tags, image_file_path, price FROM catalogue")
        conn.execute("DROP TABLE catalogue")
        conn.execute("ALTER TABLE catalogue_new RENAME TO catalogue")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_catalogue_garment_type ON catalogue(garment_type)")

        bad = conn.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            raise SystemExit(f"Foreign key problems, rolled back: {bad}")
    conn.execute("PRAGMA foreign_keys = ON")

    for (raw, new), n in sorted(changes.items()):
        print(f"  {raw!r:40} -> {new!r}  ({n})")
    print("\nProducts per garment type:")
    for label, gtype, n in conn.execute("""
            SELECT g.display_name, g.garment_type, COUNT(c.product_id)
            FROM garment_types g LEFT JOIN catalogue c USING (garment_type)
            GROUP BY g.garment_type ORDER BY g.sort_order"""):
        print(f"  {label:22} {gtype:28} {n}")
    conn.close()


if __name__ == "__main__":
    main()
