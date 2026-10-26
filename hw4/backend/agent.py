"""Shop assistant agent: PydanticAI + gpt-5.6-luna (via Portkey).

- Instructions: prompts/prompt.md, re-read on every turn so it can be edited live, plus
  today's date and the shopper's first name.
- Tools: tools.py (catalogue and stock only, read-only).
- Output: models.ShopReply, a Markdown message plus up to 6 product ids for the site to show as
  cards. An output validator sends the reply back to the model if it quotes a price or
  shows a product that no tool returned during this reply, so prices and stock stay true.

main.py exposes it as POST /api/chat. To try it from the command line (from the hw4 folder;
--trace also prints each tool call):
    .venv/Scripts/python backend/agent.py "Do you have navy hoodies in medium?" "How much is the first one?"
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import os
import re
import sys
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext, UsageLimits, capture_run_messages
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import (ModelMessage, ModelRequest, ModelResponse, RetryPromptPart, TextPart, ToolCallPart,
                                  ToolReturnPart, UserPromptPart)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

import audit
import insights
import tools
from db import HW_DIR
from models import MAX_CHAT_CARDS, ShopDeps, ShopReply

MODEL = "gpt-5.6-luna"
PROMPT_PATH = Path(__file__).parent / "prompts" / "prompt.md"
HISTORY_MESSAGES = 20  # earlier chat messages sent as context
NEW_VISIT_GAP = timedelta(hours=2)  # a longer pause than this means the shopper has come back
USAGE_LIMITS = UsageLimits(request_limit=8, tool_calls_limit=15)  # caps cost if a turn goes in circles
OUTPUT_TOOLS = {"final_result"}  # PydanticAI's tool for the structured reply (ShopReply)
PRICE_PATTERN = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)")

log = logging.getLogger("campus_customs")

# PORTKEY_API_KEY: hw4/.env (this repo, see .env.example), or else the course folder's root .env.
load_dotenv(HW_DIR / ".env")
load_dotenv(HW_DIR.parent / ".env")  # never overrides a value already set


def _model() -> OpenAIChatModel | None:
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        return None  # tests swap in a fake model; real chats report a clear error
    client = AsyncOpenAI(api_key=key, base_url="https://api.portkey.ai/v1", default_headers={"x-portkey-api-key": key})
    return OpenAIChatModel(MODEL, provider=OpenAIProvider(openai_client=client))


agent = Agent(
    _model(),
    name="campus_customs_shop_assistant",
    deps_type=ShopDeps,
    output_type=ShopReply,
    tools=tools.ALL_TOOLS,
    retries=2,
    defer_model_check=True,
)


def memory_note(saved_messages: int, last_chat_at: datetime | None, now: datetime | None = None) -> str:
    """One or two sentences telling the agent whether this shopper is new, mid-chat or returning."""
    if not saved_messages or last_chat_at is None:
        return "This is the shopper's first conversation with you; there is no saved history."
    now = now or datetime.now(timezone.utc)
    days = (now.date() - last_chat_at.date()).days
    when = "earlier today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"
    note = (f"The shopper has chatted with you before: {saved_messages} saved messages, the most recent "
            f"{when} ({last_chat_at:%B %d, %Y}). The last {min(saved_messages, HISTORY_MESSAGES)} are "
            "reloaded above as this conversation's history.")
    if now - last_chat_at > NEW_VISIT_GAP:
        note += " They're returning after a break (see Memory)."
    return note


def page_note(page_path: str | None, viewing_product: tuple[str, str] | None) -> str:
    """One sentence telling the agent which page the shopper is looking at (see Page context).

    main.page_for_agent has already checked everything here against the database."""
    if viewing_product:
        product_id, name = viewing_product
        return (f'The shopper is on the product page for "{name}" (product_id: {product_id}). '
                'Words like "this", "it" or "this one" mean that item unless they say otherwise.')
    if not page_path:
        return "The page the shopper is on is unknown."
    path, _, query = page_path.partition("?")
    if path == "/products" and query.startswith("chat="):
        return "The shopper is looking at search results you put on the Product page (listed in the history)."
    if path == "/products" and query.startswith("type="):
        return f"The shopper is browsing the Product page filtered to {query[5:]}."
    pages = {"/": "the home page", "/products": "the Product page (all products)", "/about": "the About Us page"}
    return f"The shopper is on {pages.get(path, 'a page with no product on it')}."


def shopper_note(deps: ShopDeps) -> str:
    """Who is chatting: a logged-in shopper (name and saved history) or a guest."""
    if deps.first_name is None:
        return ("The shopper is a guest (not logged in), so you don't know their name. This visit's messages "
                "are above, but nothing is saved after they leave (see Memory).")
    note = f"The shopper's first name is {deps.first_name}. {memory_note(deps.saved_messages, deps.last_chat_at)}"
    if deps.back_in_stock:
        items = "; ".join(f'"{name}" in {size} (product_id: {pid})' for pid, name, size in deps.back_in_stock)
        note += (f" Good news to share: these sizes they asked to hear about are back in stock: {items}. "
                 "Tell them once in this conversation (see Restock alerts).")
    return note


@agent.instructions
def system_prompt(ctx: RunContext[ShopDeps]) -> str:
    return (
        f"{PROMPT_PATH.read_text(encoding='utf-8')}\n\n"
        f"## This conversation\n\nToday is {date.today():%A, %B %d, %Y}. "
        f"{shopper_note(ctx.deps)} "
        f"{page_note(ctx.deps.page_path, ctx.deps.viewing_product)}"
    )


@agent.output_validator
def check_reply(ctx: RunContext[ShopDeps], reply: ShopReply) -> ShopReply:
    """Send the reply back for another try if it shows or prices anything no tool returned."""
    reply.product_ids = list(dict.fromkeys(reply.product_ids))  # drop repeats, keep order
    if reply.search_title is not None:
        reply.search_title = " ".join(reply.search_title.split()) or None
    if not reply.product_ids:
        reply.search_title = None  # nothing to show, so the page isn't changed
    if reply.search_title is None:
        reply.product_ids = reply.product_ids[:MAX_CHAT_CARDS]
    if reply.unmet_request is not None:
        reply.unmet_request = " ".join(reply.unmet_request.split()) or None
        if not any(matches == 0 for _, matches in ctx.deps.searches):
            reply.unmet_request = None  # only real misses: a search this turn must have found nothing
    unknown = [pid for pid in reply.product_ids if pid not in ctx.deps.seen_products]
    if unknown:
        raise ModelRetry(f"product_ids {unknown} weren't returned by a tool during this reply. "
                         "Look them up with a tool first, or remove them.")
    for amount in PRICE_PATTERN.findall(f"{reply.message} {reply.search_title or ''}"):
        cents = round(float(amount.replace(",", "")) * 100)
        if cents not in ctx.deps.quoted_prices:
            raise ModelRetry(f"The reply says ${amount}, but no tool returned that price during this reply. "
                             "Rewrite it without that amount: quote only prices a tool returned, exactly. "
                             "If the shopper suggested that amount, don't repeat it; just state the listed price.")
    return reply


Turn = tuple[str, str, Sequence[str], str | None]  # (role, content, product ids shown, search title)


def to_history(rows: Sequence[Turn]) -> list[ModelMessage]:
    """Saved chat turns, oldest first, as PydanticAI message history.

    Earlier replies keep a note of the product cards shown with them, so "how many are left
    in XL?" can be looked up for the right product. Prices and stock are never carried over;
    the model has to call a tool again for those.
    """
    history: list[ModelMessage] = []
    for role, content, product_ids, search_title in rows:
        if role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        else:
            if product_ids and search_title:
                content += (f"\n\n(Search results shown on the Product page as \"{search_title}\", "
                            f"in order: {', '.join(product_ids)})")
            elif product_ids:
                content += f"\n\n(Product cards shown with this reply, in order: {', '.join(product_ids)})"
            history.append(ModelResponse(parts=[TextPart(content=content)]))
    return history


FILTERED_REPLY = ShopReply(message="Sorry, I can't help with that request. I'm happy to help you find Campus Customs "
                                   "apparel, compare items, or check prices and sizes.")
# When the model keeps failing the truth checks, say so rather than show an unchecked answer.
UNVERIFIED_REPLY = ShopReply(message="Sorry, I couldn't put together an answer I could double-check just now. "
                                     "Could you try asking another way?")


def _content_filtered(error: ModelHTTPError) -> bool:
    body = error.body if isinstance(error.body, dict) else {}
    return body.get("code") == "content_filter" or "content_filter" in str(error.body)


async def reply_to(message: str, first_name: str | None, history: Sequence[Turn] = (),
                   saved_messages: int = 0, last_chat_at: datetime | None = None,
                   page_path: str | None = None, viewing_product: tuple[str, str] | None = None,
                   user_id: int | None = None, back_in_stock: Sequence[tuple[str, str, str]] = ()) -> ShopReply:
    """Run one chat turn and return the validated reply. first_name is None for a guest.

    history is that shopper's saved chat, oldest first; saved_messages and last_chat_at describe
    all of it, so the agent knows whether they're new, mid-conversation or coming back.
    page_path and viewing_product say which page they're on, so "this" can be resolved.
    user_id (never shown to the model) lets request_restock_alert save for this shopper;
    back_in_stock lists their requests that are available again.
    Afterwards, any unmet demand the tools noticed is saved for the manager report, and the
    whole turn (tool calls, retries, outcome) is appended to the audit trail (audit.py).
    """
    deps = ShopDeps(first_name=first_name, saved_messages=saved_messages, last_chat_at=last_chat_at,
                    page_path=page_path, viewing_product=viewing_product, user_id=user_id,
                    back_in_stock=list(back_in_stock))
    earlier = to_history(history[-HISTORY_MESSAGES:])
    turn = {"started": datetime.now(timezone.utc), "clock": time.monotonic(), "message_chars": len(message),
            "history_messages": len(earlier)}
    reply, usage, outcome, error = None, None, "error", None
    with capture_run_messages() as messages:
        try:
            result = await agent.run(message, deps=deps, message_history=earlier, usage_limits=USAGE_LIMITS)
            reply, usage, outcome = result.output, result.usage, "answered"
        except ModelHTTPError as exc:
            # Azure's content filter (including its jailbreak / prompt-injection shield) refused the
            # message. That's a refusal, not an outage, so answer politely instead of failing.
            if not _content_filtered(exc):
                error = exc
                raise
            reply, outcome = FILTERED_REPLY.model_copy(), "refused_by_content_filter"
        except UnexpectedModelBehavior:
            log.warning("Shop assistant reply kept failing its truth checks; sent the fallback reply")
            reply, outcome = UNVERIFIED_REPLY.model_copy(), "fallback_unverified"
        except Exception as exc:
            error = exc
            raise
        finally:
            audit.record(audit_entry(turn, deps, messages[len(earlier):], reply, usage, outcome, error))
    if outcome == "answered":
        record_missed_demand(deps, reply.unmet_request)
    return reply


# --- Audit trail -------------------------------------------------------------------------------

AUDIT_TEXT_LIMIT = 300  # characters kept from a retry reason or an unusual tool result


def _tool_result(name: str, content: object) -> object:
    """A short, readable summary of what a tool returned (the facts the model was given)."""
    data = content.model_dump() if hasattr(content, "model_dump") else content
    if name == "search_products" and isinstance(data, dict):
        return {"total_matches": data["total_matches"], "result_ids": [r["product_id"] for r in data["results"]]}
    if name == "get_product_details" and isinstance(data, dict):
        return {k: data[k] for k in ("product_id", "price", "stock_by_size", "total_in_stock")}
    if name == "check_stock" and isinstance(data, dict):
        return {k: data[k] for k in ("product_id", "size", "quantity", "in_stock", "other_sizes_in_stock")}
    if name == "request_restock_alert" and isinstance(data, dict):
        return {k: data[k] for k in ("product_id", "size", "result")}
    if name == "list_categories" and isinstance(data, list):
        return {"categories": len(data)}
    return str(data)[:AUDIT_TEXT_LIMIT]


def audit_entry(turn: dict, deps: ShopDeps, messages: Sequence[ModelMessage], reply: ShopReply | None,
                usage, outcome: str, error: BaseException | None) -> dict:
    """One audit-trail record for a chat turn: every step of the agent loop, in order.

    The shopper's message text is deliberately left out (only its length); tool arguments are the
    agent's own search terms and ids, and tool results are summarized.
    """
    steps: list[dict] = []
    for msg in messages:
        if isinstance(msg, ModelResponse):
            steps.append({"step": "model_response", "model": msg.model_name})
        for part in msg.parts:
            if isinstance(part, ToolCallPart) and part.tool_name not in OUTPUT_TOOLS:
                steps.append({"step": "tool_call", "tool": part.tool_name, "args": part.args_as_dict()})
            elif isinstance(part, ToolReturnPart) and part.tool_name not in OUTPUT_TOOLS:
                steps.append({"step": "tool_result", "tool": part.tool_name,
                              "result": _tool_result(part.tool_name, part.content)})
            elif isinstance(part, RetryPromptPart):
                reason = part.content if isinstance(part.content, str) else json.dumps(part.content, default=str)
                checked = "reply truth check" if part.tool_name in OUTPUT_TOOLS or part.tool_name is None else part.tool_name
                steps.append({"step": "retry", "checked_by": checked, "reason": reason[:AUDIT_TEXT_LIMIT]})
    tool_results = [s for s in steps if s["step"] == "tool_result"]
    writes = [f"restock alert {r['result']['result']}: {r['result']['product_id']} {r['result']['size']}"
              for r in tool_results if r["tool"] == "request_restock_alert"
              and isinstance(r["result"], dict) and r["result"]["result"] == "saved"]
    return {
        "time": turn["started"].isoformat(timespec="seconds"),
        "duration_ms": round((time.monotonic() - turn["clock"]) * 1000),
        "event": "chat_turn",
        "agent": agent.name,
        "model": MODEL,
        "shopper": {"type": "guest" if deps.user_id is None else "account", "user_id": deps.user_id},
        "page": deps.page_path,
        "viewing_product": deps.viewing_product[0] if deps.viewing_product else None,
        "message_chars": turn["message_chars"],
        "history_messages": turn["history_messages"],
        "steps": steps,
        "model_requests": sum(isinstance(m, ModelResponse) for m in messages),
        "tool_calls": sum(s["step"] == "tool_call" for s in steps),
        "retries": sum(s["step"] == "retry" for s in steps),
        "writes": writes,
        "outcome": outcome,
        "error": type(error).__name__ if error else None,
        "reply": None if reply is None else {
            "chars": len(reply.message), "product_ids": reply.product_ids,
            "search_title": reply.search_title, "unmet_request": reply.unmet_request},
        "usage": None if usage is None else {
            "requests": usage.requests, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
    }


def record_missed_demand(deps: ShopDeps, unmet_request: str | None = None) -> None:
    """Save a turn's unmet demand for the manager report; never breaks the chat.

    No results: the agent's own summary of what the shopper wanted (unmet_request, which the
    validator only allows after a search that found nothing), or, if it didn't give one but every
    search found nothing, the first search. Sold-out sizes it checked: one entry each.
    """
    no_results = unmet_request
    if no_results is None and deps.searches and all(n == 0 for _, n in deps.searches):
        no_results = deps.searches[0][0]
    try:
        insights.record_demand(no_results, deps.sold_out_asks)
    except Exception:
        log.exception("Couldn't record missed demand")


async def _cli(questions: list[str], trace: bool) -> None:
    history: list[Turn] = []
    for question in questions:
        if trace:  # run the agent directly so the tool calls can be shown
            result = await agent.run(question, deps=ShopDeps(), message_history=to_history(history),
                                     usage_limits=USAGE_LIMITS)
            reply = result.output
            for message in result.new_messages():
                for part in message.parts:
                    if part.part_kind == "tool-call" and part.tool_name in {t.__name__ for t in tools.ALL_TOOLS}:
                        print(f"  [tool] {part.tool_name}({part.args})")
        else:
            reply = await reply_to(question, None, history)
        print(f"\nShopper: {question}\nAssistant: {reply.message}\nProducts: {reply.product_ids}"
              + (f"\nPage search: {reply.search_title!r}" if reply.search_title else ""))
        history += [("user", question, [], None), ("assistant", reply.message, reply.product_ids, reply.search_title)]


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--trace"]
    if not args:
        raise SystemExit('Usage: python backend/agent.py [--trace] "question" ["follow-up" ...]')
    asyncio.run(_cli(args, trace="--trace" in sys.argv))
