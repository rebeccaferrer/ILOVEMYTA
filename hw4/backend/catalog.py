"""Catalogue queries shared by the shop API and the agent's tools, so both always read the
same live prices and stock from campus_customs.db."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from models import ProductDetail, ProductSummary, SizeStock

SUMMARY_SQL = """
    SELECT c.product_id, c.name, c.garment_type, g.display_name AS garment_label,
           c.short_description, c.price_cents, c.image_file_path,
           c.description, c.primary_color, c.accent_colors, c.search_tags,
           COALESCE(SUM(i.quantity), 0) AS total_stock
    FROM catalogue c
    JOIN garment_types g USING (garment_type)
    LEFT JOIN inventory i USING (product_id)
"""


def image_url(image_file_path: str) -> str:
    # catalogue paths look like "products/<id>.jpg"
    return f"/images/products/{Path(image_file_path).name}"


def format_price(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def to_summary(row: sqlite3.Row) -> ProductSummary:
    return ProductSummary(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        garment_label=row["garment_label"],
        short_description=row["short_description"] or "",
        price_cents=row["price_cents"],
        image_url=image_url(row["image_file_path"]),
        in_stock=row["total_stock"] > 0,
    )


def sizes_for(db: sqlite3.Connection, product_id: str) -> list[SizeStock]:
    rows = db.execute("""
        SELECT i.size, i.quantity FROM inventory i JOIN sizes s USING (size)
        WHERE i.product_id = ? ORDER BY s.sort_order
    """, [product_id]).fetchall()
    return [SizeStock(size=r["size"], quantity=r["quantity"]) for r in rows]


def product_row(db: sqlite3.Connection, product_id: str) -> sqlite3.Row | None:
    return db.execute(f"{SUMMARY_SQL} WHERE c.product_id = ? GROUP BY c.product_id", [product_id]).fetchone()


def product_detail(db: sqlite3.Connection, product_id: str) -> ProductDetail | None:
    row = product_row(db, product_id)
    if row is None:
        return None
    return ProductDetail(
        **to_summary(row).model_dump(),
        description=row["description"],
        primary_color=row["primary_color"],
        accent_colors=json.loads(row["accent_colors"]),
        sizes=sizes_for(db, product_id),
        total_stock=row["total_stock"],
    )


def product_summaries(db: sqlite3.Connection, product_ids: list[str]) -> list[ProductSummary]:
    """Cards for the given ids, in the same order, skipping any that no longer exist."""
    if not product_ids:
        return []
    marks = ",".join("?" * len(product_ids))
    rows = {r["product_id"]: r for r in db.execute(
        f"{SUMMARY_SQL} WHERE c.product_id IN ({marks}) GROUP BY c.product_id", product_ids)}
    return [to_summary(rows[pid]) for pid in product_ids if pid in rows]
