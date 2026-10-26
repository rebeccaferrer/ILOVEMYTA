"""Add a one-line `short_description` to every catalogue product.

The shop's product cards need a short line; the product page shows the full
`description`. gpt-5.6-luna (via Portkey) rewrites each existing description as a
short line, using only facts already in it, so nothing new is invented.

Only fills products that don't have one yet; pass --force to redo all.
Run with the hw4 virtual environment:  .venv/Scripts/python add_short_descriptions.py
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

HERE = Path(__file__).parent
DB_PATH = HERE / "data" / "data" / "campus_customs.db"
MODEL = "gpt-5.6-luna"
BATCH_SIZE = 20
MAX_CHARS = 70
MAX_RETRIES = 3

INSTRUCTIONS = f"""You write one-line product summaries for a Yale apparel shop's product cards.

For each product, rewrite its description as a short line of at most {MAX_CHARS} characters.
- Use ONLY facts stated in the description. Never add fabric, fit, sizing or other claims.
- Lead with what makes this item different from similar ones: its graphic, lettering,
  college, school or sport. Keep the garment color.
- Plain sentence case, no ending period, no quotation marks, no product name repeats.
Return one entry per product_id you were given."""


class Summary(BaseModel):
    product_id: str
    short_description: str = Field(description=f"At most {MAX_CHARS} characters.")


class Summaries(BaseModel):
    items: list[Summary]


async def summarize(client: AsyncOpenAI, batch: list[tuple[str, str, str]]) -> dict[str, str]:
    listing = "\n".join(f"- product_id: {pid}\n  name: {name}\n  description: {desc}" for pid, name, desc in batch)
    wanted = {pid for pid, _, _ in batch}
    response_format = {"type": "json_schema", "json_schema": {"name": "Summaries", "schema": Summaries.model_json_schema()}}
    for attempt in range(1, MAX_RETRIES + 1):
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": listing}],
            response_format=response_format,
        )
        result = {s.product_id: s.short_description.strip().rstrip(".")
                  for s in Summaries.model_validate_json(response.choices[0].message.content or "").items}
        too_long = [pid for pid, text in result.items() if len(text) > MAX_CHARS]
        if wanted <= result.keys() and not too_long:
            return {pid: result[pid] for pid in wanted}
        print(f"  batch retry {attempt}: missing {sorted(wanted - result.keys())}, too long {too_long}")
    raise RuntimeError("Model kept returning incomplete or over-long summaries.")


async def main() -> None:
    load_dotenv(HERE / ".env")         # hw4/.env (see .env.example)
    load_dotenv(HERE.parent / ".env")  # or the course folder's root .env
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise SystemExit("Set PORTKEY_API_KEY in hw4/.env (copy .env.example) or the course folder's .env.")
    client = AsyncOpenAI(api_key=key, base_url="https://api.portkey.ai/v1", default_headers={"x-portkey-api-key": key})

    conn = sqlite3.connect(DB_PATH)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(catalogue)")}
    if "short_description" not in columns:
        conn.execute("ALTER TABLE catalogue ADD COLUMN short_description TEXT")
    where = "" if "--force" in sys.argv else "WHERE short_description IS NULL OR short_description = ''"
    todo = conn.execute(f"SELECT product_id, name, description FROM catalogue {where} ORDER BY product_id").fetchall()
    print(f"Writing short descriptions for {len(todo)} products...")

    batches = [todo[i:i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
    results = await asyncio.gather(*(summarize(client, batch) for batch in batches))
    with conn:
        for summaries in results:
            conn.executemany("UPDATE catalogue SET short_description = ? WHERE product_id = ?",
                             [(text, pid) for pid, text in summaries.items()])
    missing = conn.execute("SELECT COUNT(*) FROM catalogue WHERE short_description IS NULL OR short_description = ''").fetchone()[0]
    print(f"Done. Products still missing a short description: {missing}")
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
