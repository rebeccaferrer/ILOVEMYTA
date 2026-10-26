"""Tools the shop assistant agent can call.

Every fact the assistant states about products, prices or stock must come from one of
these tools, which read campus_customs.db live (read-only). The tools can only see the
catalogue and stock: never accounts, passwords, sessions or chat history. The one exception
is request_restock_alert, which saves a "notify me" request for the logged-in shopper only.

The tools also note unmet demand (searches with no results, sold-out sizes checked) in
ctx.deps; agent.py saves it to demand_signals after the turn, without the shopper's identity.

Each tool records the prices and product ids it returned in ctx.deps, so agent.py can
check the final reply against them.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
from collections import defaultdict
from contextlib import closing

from pydantic_ai import ModelRetry, RunContext

from catalog import SUMMARY_SQL, format_price
from db import connect
import insights
from models import (CategoryInfo, ProductDetails, ProductMatch, RestockRequestResult, SearchResults, ShopDeps,
                    StockCheck)

MAX_RESULTS = 12

# Opening lines for "that size is sold out". They are jokes only: none promises a restock date,
# a hold, a discount or anything else the database doesn't say, so the humor can't mislead.
SOLD_OUT_QUIPS = [
    "Handsome Dan got to that size first. He has excellent taste and zero patience.",
    "That size graduated early: summa cum sold out.",
    "Boola boola... gone-a gone-a. That size has left the shelf.",
    "That size vanished faster than a first-year leaving a 9 a.m. lecture.",
    "Even Sterling Library's best researchers couldn't find one of those in that size.",
    "That size must have gotten into Yale too, because it's officially moved out.",
    "Our shelves checked twice, and that size is still playing hide-and-seek (and winning).",
]

SIZE_WORDS = {
    "xs": "XS", "x-small": "XS", "extra small": "XS",
    "s": "S", "small": "S",
    "m": "M", "medium": "M", "med": "M",
    "l": "L", "large": "L",
    "xl": "XL", "x-large": "XL", "extra large": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL",
}
COLOR_WORDS = {"grey": "gray", "navy blue": "navy", "ivory": "cream", "off-white": "cream", "pink": "coral"}
STOP_WORDS = {
    "a", "an", "the", "and", "or", "for", "with", "in", "of", "on", "to", "do", "you", "have", "any",
    "some", "show", "me", "i", "want", "looking", "something", "that", "is", "are", "my", "yale",
}


def _record(ctx: RunContext[ShopDeps], product_id: str, price_cents: int) -> None:
    ctx.deps.seen_products.add(product_id)
    ctx.deps.quoted_prices.add(price_cents)


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def _words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9&]+", text.lower())}


def _resolve_garment_type(db: sqlite3.Connection, value: str) -> str:
    wanted = _stem(value.strip().lower())
    for row in db.execute("SELECT garment_type, display_name FROM garment_types"):
        if wanted in {_stem(row["garment_type"]), _stem(row["display_name"].lower())}:
            return row["garment_type"]
    options = ", ".join(r["garment_type"] for r in db.execute(
        "SELECT DISTINCT garment_type FROM catalogue JOIN garment_types USING (garment_type) ORDER BY sort_order"))
    raise ModelRetry(f"Unknown garment_type {value!r}. Use one of: {options}.")


def _resolve_size(value: str) -> str:
    size = SIZE_WORDS.get(value.strip().lower())
    if size is None:
        raise ModelRetry(f"Unknown size {value!r}. Sizes are XS, S, M, L, XL and XXL.")
    return size


def _stock_by_product(db: sqlite3.Connection) -> dict[str, dict[str, int]]:
    stock: dict[str, dict[str, int]] = defaultdict(dict)
    for r in db.execute("SELECT i.product_id, i.size, i.quantity FROM inventory i JOIN sizes s USING (size) ORDER BY s.sort_order"):
        stock[r["product_id"]][r["size"]] = r["quantity"]
    return stock


def search_products(
    ctx: RunContext[ShopDeps],
    query: str = "",
    garment_type: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = True,
) -> SearchResults:
    """Search the catalogue. Use it for any question about what the shop sells.

    Args:
        query: Words describing what the shopper wants, e.g. 'hockey', 'Saybrook crest', 'mom', 'bulldog'.
        garment_type: Optional category, e.g. 'hooded sweatshirt', 't-shirt', 'quarter-zip pullover'
            (see list_categories).
        color: Optional garment color, e.g. 'navy', 'gray', 'cream'. Matches the garment or its print.
        max_price: Optional highest price in dollars.
        size: Optional size that must be in stock: XS, S, M, L, XL or XXL.
        in_stock_only: Leave True to hide products that are completely sold out.
    """
    with closing(connect(read_only=True)) as db:
        where, params = "", []
        if garment_type:
            where, params = "WHERE c.garment_type = ?", [_resolve_garment_type(db, garment_type)]
        rows = db.execute(f"{SUMMARY_SQL} {where} GROUP BY c.product_id", params).fetchall()
        stock = _stock_by_product(db)
    if max_price is not None:
        ctx.deps.quoted_prices.add(round(max_price * 100))  # "items under $40" may mention the budget
    wanted_size = _resolve_size(size) if size else None
    wanted_color = COLOR_WORDS.get(color.strip().lower(), color.strip().lower()) if color else None
    terms = _words(query) - STOP_WORDS

    scored = []
    for row in rows:
        sizes = stock.get(row["product_id"], {})
        accents = json.loads(row["accent_colors"])
        if max_price is not None and row["price_cents"] > round(max_price * 100):
            continue
        if wanted_size and sizes.get(wanted_size, 0) == 0:
            continue
        if in_stock_only and row["total_stock"] == 0:
            continue
        if wanted_color and not any(wanted_color in c for c in [row["primary_color"], *accents]):
            continue
        score = 0
        if terms:
            name, tags = _words(row["name"]), _words(" ".join(json.loads(row["search_tags"])))
            other = _words(" ".join([row["description"], row["short_description"] or "", row["garment_label"],
                                     row["primary_color"], *accents]))
            score = sum(3 * (t in name) + 2 * (t in tags) + (t in other) for t in terms)
            if score == 0:
                continue
        if wanted_color and wanted_color in row["primary_color"]:
            score += 1  # garment color beats print color
        scored.append((score, row, sizes))

    ctx.deps.searches.append((_describe_search(query, garment_type, wanted_color, max_price, wanted_size), len(scored)))
    scored.sort(key=lambda s: (-s[0], s[1]["name"]))
    results = []
    for _, row, sizes in scored[:MAX_RESULTS]:
        _record(ctx, row["product_id"], row["price_cents"])
        results.append(ProductMatch(
            product_id=row["product_id"],
            name=row["name"],
            category=row["garment_label"],
            short_description=row["short_description"] or "",
            primary_color=row["primary_color"],
            accent_colors=json.loads(row["accent_colors"]),
            price=format_price(row["price_cents"]),
            sizes_in_stock=[s for s, q in sizes.items() if q > 0],
            sold_out_sizes=[s for s, q in sizes.items() if q == 0],
        ))
    return SearchResults(total_matches=len(scored), results=results)


def _describe_search(query: str, garment_type: str | None, color: str | None, max_price: float | None,
                     size: str | None) -> str:
    """A short, readable summary of a search for the missed-demand report, e.g. 'umbrella · navy · under $40'."""
    parts = [" ".join(query.split())[:60], color, garment_type, f"under ${max_price:g}" if max_price else None,
             f"size {size}" if size else None]
    return " · ".join(p for p in parts if p) or "anything"


def get_product_details(ctx: RunContext[ShopDeps], product_id: str) -> ProductDetails:
    """Full description, colors, price and stock for every size of one product.

    Args:
        product_id: The id from search_products, e.g. 'basic-hoodie-big-yale'.
    """
    with closing(connect(read_only=True)) as db:
        row = db.execute(f"{SUMMARY_SQL} WHERE c.product_id = ? GROUP BY c.product_id", [product_id]).fetchone()
        if row is None:
            raise ModelRetry(f"No product has id {product_id!r}. Use search_products to find the right id.")
        sizes = _stock_by_product(db).get(product_id, {})
    _record(ctx, product_id, row["price_cents"])
    return ProductDetails(
        product_id=product_id,
        name=row["name"],
        category=row["garment_label"],
        description=row["description"],
        primary_color=row["primary_color"],
        accent_colors=json.loads(row["accent_colors"]),
        price=format_price(row["price_cents"]),
        stock_by_size=sizes,
        total_in_stock=row["total_stock"],
    )


def check_stock(ctx: RunContext[ShopDeps], product_id: str, size: str) -> StockCheck:
    """How many of one product are on the shelf in one size. Use it for every "do you have it in M?".

    Args:
        product_id: The id from search_products.
        size: XS, S, M, L, XL or XXL (words like 'medium' also work).
    """
    wanted = _resolve_size(size)
    with closing(connect(read_only=True)) as db:
        row = db.execute("SELECT name, price_cents FROM catalogue WHERE product_id = ?", [product_id]).fetchone()
        if row is None:
            raise ModelRetry(f"No product has id {product_id!r}. Use search_products to find the right id.")
        sizes = _stock_by_product(db).get(product_id, {})
    _record(ctx, product_id, row["price_cents"])
    quantity = sizes.get(wanted, 0)
    if quantity == 0:
        ctx.deps.sold_out_asks.add((product_id, wanted))  # missed demand
    return StockCheck(
        product_id=product_id,
        name=row["name"],
        price=format_price(row["price_cents"]),
        size=wanted,
        quantity=quantity,
        in_stock=quantity > 0,
        other_sizes_in_stock=[s for s, q in sizes.items() if q > 0 and s != wanted],
        sold_out_quip=None if quantity > 0 else random.choice(SOLD_OUT_QUIPS),
    )


def list_categories(ctx: RunContext[ShopDeps]) -> list[CategoryInfo]:
    """The shop's categories, how many products each has, and their price range."""
    with closing(connect(read_only=True)) as db:
        rows = db.execute("""
            SELECT g.display_name, g.garment_type, COUNT(*) AS n, MIN(c.price_cents) AS lo, MAX(c.price_cents) AS hi
            FROM catalogue c JOIN garment_types g USING (garment_type)
            GROUP BY g.garment_type ORDER BY g.sort_order
        """).fetchall()
    result = []
    for r in rows:
        ctx.deps.quoted_prices.update({r["lo"], r["hi"]})
        price_range = format_price(r["lo"]) if r["lo"] == r["hi"] else f"{format_price(r['lo'])} to {format_price(r['hi'])}"
        result.append(CategoryInfo(category=r["display_name"], garment_type=r["garment_type"],
                                   product_count=r["n"], price_range=price_range))
    return result


def request_restock_alert(ctx: RunContext[ShopDeps], product_id: str, size: str) -> RestockRequestResult:
    """Ask to tell the shopper when a sold-out size is back in stock. Only call it after the shopper
    says yes to your offer. It is the only tool that saves anything, and only for this shopper.

    Args:
        product_id: The id from search_products or the page the shopper is on.
        size: The sold-out size, XS to XXL.
    """
    wanted = _resolve_size(size)
    with closing(connect(read_only=False)) as db:
        row = db.execute("SELECT name FROM catalogue WHERE product_id = ?", [product_id]).fetchone()
        if row is None:
            raise ModelRetry(f"No product has id {product_id!r}. Use search_products to find the right id.")
        if ctx.deps.user_id is None:
            result = "needs_account"
        else:
            result = insights.save_restock_request(db, ctx.deps.user_id, product_id, wanted)
    return RestockRequestResult(product_id=product_id, name=row["name"], size=wanted, result=result)


ALL_TOOLS = [search_products, get_product_details, check_stock, list_categories, request_restock_alert]
