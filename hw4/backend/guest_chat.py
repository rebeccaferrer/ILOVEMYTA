"""Chat for guests (not logged in): kept in the server's memory for one visit, never in the database.

A guest gets a random id in an HttpOnly cookie. Their messages live here so the agent can follow
the conversation, until 2 hours after their last message, a server restart, or logging in
(after which the shopper's saved history is used instead). Only logged-in shoppers' chats are
saved in chat_messages.

Because anyone can reach the chat as a guest, guests also have their own rate limits, per guest
and per network address, so a script can't run up AI costs.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

GUEST_COOKIE = "cc_guest"
GUEST_TTL_SECONDS = 2 * 60 * 60   # a guest chat is forgotten 2 hours after its last message
MAX_GUESTS = 2000                 # oldest guest chats are dropped beyond this, so memory stays small
MAX_MESSAGES = 40                 # per guest chat; the agent only reads the last 20 anyway

RATE_WINDOW_SECONDS = 10 * 60
MAX_PER_GUEST = 10                # messages per guest per 10 minutes (logged-in shoppers get 20)
MAX_PER_ADDRESS = 30              # messages from one network address per 10 minutes (e.g. a dorm)


@dataclass
class GuestChat:
    messages: list[dict] = field(default_factory=list)  # same columns as chat_messages rows
    next_id: int = 1
    last_used: float = field(default_factory=time.monotonic)


class GuestStore:
    """Thread-safe, in-memory guest chats with expiry and rate limits."""

    def __init__(self) -> None:
        self._chats: OrderedDict[str, GuestChat] = OrderedDict()  # least recently used first
        self._sent: dict[str, deque[float]] = {}                   # rate-limit key -> send times
        self._lock = threading.Lock()

    @staticmethod
    def new_id() -> str:
        return secrets.token_urlsafe(24)

    def _prune(self, now: float) -> None:
        while self._chats:
            oldest_id, oldest = next(iter(self._chats.items()))
            if now - oldest.last_used > GUEST_TTL_SECONDS or len(self._chats) > MAX_GUESTS:
                del self._chats[oldest_id]
            else:
                break
        for key in [k for k, times in self._sent.items() if not times or now - times[-1] > RATE_WINDOW_SECONDS]:
            del self._sent[key]

    def messages(self, guest_id: str | None) -> list[dict]:
        """This guest's messages, oldest first ([] for an unknown or expired guest)."""
        with self._lock:
            self._prune(time.monotonic())
            chat = self._chats.get(guest_id) if guest_id else None
            return list(chat.messages) if chat else []

    def allow(self, guest_id: str, address: str) -> bool:
        """Count one message against the guest's and the address's limits; False if either is used up."""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            keys = [(f"guest:{guest_id}", MAX_PER_GUEST), (f"ip:{address}", MAX_PER_ADDRESS)]
            windows = []
            for key, limit in keys:
                times = self._sent.setdefault(key, deque())
                while times and now - times[0] > RATE_WINDOW_SECONDS:
                    times.popleft()
                if len(times) >= limit:
                    return False
                windows.append(times)
            for times in windows:
                times.append(now)
            return True

    def add_turn(self, guest_id: str, message: str, reply: str, product_ids: list[str],
                 search_title: str | None) -> dict:
        """Store the guest's message and the reply; returns the stored reply."""
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            now = time.monotonic()
            chat = self._chats.pop(guest_id, None) or GuestChat()
            chat.last_used = now
            self._chats[guest_id] = chat  # move to the most recently used end
            for role, content, ids, title in (("user", message, [], None),
                                              ("assistant", reply, product_ids, search_title)):
                chat.messages.append({"id": chat.next_id, "role": role, "content": content,
                                      "product_ids": ids, "search_title": title, "created_at": stamp})
                chat.next_id += 1
            del chat.messages[:-MAX_MESSAGES]
            self._prune(now)
            return chat.messages[-1]

    def forget(self, guest_id: str | None) -> None:
        with self._lock:
            if guest_id:
                self._chats.pop(guest_id, None)


store = GuestStore()
