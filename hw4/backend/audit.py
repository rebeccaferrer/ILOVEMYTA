"""Append-only audit trail of the shop assistant's agent loop: output/audit_trail.json.

One record per chat turn: who was chatting (account id or guest), the page, every model request,
tool call and tool result, truth-check retries, the reply's cards, token usage and how the turn
ended. Shoppers' typed messages are NOT copied here (only their length): guests were promised
their chats aren't saved, and the trail is about what the agent did.

The file is a JSON list, like the course's Lecture 5 audit log, but it is never rewritten:
- A new record is added by replacing only the closing "]" at the end of the file, so earlier
  records are never touched, and nothing ever empties or resets the file between runs.
- If the file can't be appended to safely (e.g. someone damaged its end), the record goes to
  audit_trail.rescue.json next to it instead, and the original is left exactly as it was.
- Each record carries seq (1, 2, 3...), prev_hash and hash (SHA-256), chaining it to the one
  before. Editing, deleting or reordering any earlier record breaks the chain; check with:
      .venv/Scripts/python backend/audit.py verify        (from the hw4 folder)

CC_AUDIT_PATH points the tests at a throwaway file, so they never write to the real trail.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

from db import HW_DIR

AUDIT_PATH = Path(os.getenv("CC_AUDIT_PATH", HW_DIR / "output" / "audit_trail.json"))
GENESIS = "0" * 64  # prev_hash of the very first record
_LOCK = threading.Lock()
_last: tuple[int, str] | None = None  # (seq, hash) of the newest record, read once from the file

log = logging.getLogger("campus_customs")


def _digest(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _read_last(path: Path) -> tuple[int, str]:
    """(seq, hash) of the newest record in the file; (0, GENESIS) if there are none yet."""
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return 0, GENESIS
    if not isinstance(records, list) or not records:
        return 0, GENESIS
    last = records[-1]
    return int(last.get("seq", len(records))), str(last.get("hash", GENESIS))


def _append_to(path: Path, text: str) -> None:
    """Add one JSON-encoded record to the list in `path`, changing nothing before the closing ']'."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("x" if not path.exists() else "a", encoding="utf-8") as f:
            f.write(f"[\n{text}\n]\n")
        return
    with path.open("r+b") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - 64))
        tail = f.read()
        end = tail.rstrip()
        if not end.endswith(b"]"):
            raise ValueError(f"{path.name} doesn't end with ']'")
        bracket = size - len(tail) + len(end) - 1  # position of the closing ']'
        before = end[:-1].rstrip()
        separator = b"\n" if before.endswith(b"[") else b",\n"
        f.seek(bracket)
        f.truncate()  # only the closing bracket (and trailing whitespace) is replaced
        f.write(separator + text.encode("utf-8") + b"\n]\n")


def record(entry: dict[str, Any]) -> None:
    """Append one record to the audit trail. Never raises: auditing must not break a chat."""
    global _last
    try:
        with _LOCK:
            if _last is None:
                try:
                    _last = _read_last(AUDIT_PATH)
                except (OSError, ValueError) as error:  # unreadable: don't touch it, start a rescue chain
                    log.error("Audit trail unreadable (%s); left as is", error)
                    _last = (0, GENESIS)
            seq, prev_hash = _last
            full = {"seq": seq + 1, **entry, "prev_hash": prev_hash}
            full["hash"] = _digest(full)
            text = "  " + json.dumps(full, ensure_ascii=False, separators=(", ", ": "))
            try:
                _append_to(AUDIT_PATH, text)
            except (OSError, ValueError) as error:
                log.error("Couldn't append to %s (%s); wrote to the rescue file instead", AUDIT_PATH.name, error)
                _append_to(AUDIT_PATH.with_suffix(".rescue.json"), text)
            _last = (full["seq"], full["hash"])
    except Exception:
        log.exception("Couldn't write the audit trail")


def verify(path: Path = AUDIT_PATH) -> list[str]:
    """Problems found in the trail (an empty list means it's intact)."""
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{path} doesn't exist yet"]
    except json.JSONDecodeError as error:
        return [f"{path.name} isn't valid JSON: {error}"]
    if not isinstance(records, list):
        return [f"{path.name} should hold a JSON list"]
    problems, prev = [], GENESIS
    for i, rec in enumerate(records, start=1):
        if rec.get("seq") != i:
            problems.append(f"record {i}: seq is {rec.get('seq')}, expected {i} (a record was removed or moved)")
        if rec.get("prev_hash") != prev:
            problems.append(f"record {i}: prev_hash doesn't match record {i - 1} (chain broken)")
        if rec.get("hash") != _digest(rec):
            problems.append(f"record {i}: contents were changed after it was written")
        prev = rec.get("hash", "")
    return problems


if __name__ == "__main__":
    if sys.argv[1:] != ["verify"]:
        raise SystemExit("Usage: python backend/audit.py verify")
    found = verify()
    if found:
        print("\n".join(found))
        raise SystemExit(1)
    count = len(json.loads(AUDIT_PATH.read_text(encoding="utf-8")))
    print(f"{AUDIT_PATH.name}: {count} records, chain intact.")
