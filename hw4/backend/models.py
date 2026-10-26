"""Pydantic / PydanticAI structured types for the shop API and the shop assistant agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

# --- Shop API --------------------------------------------------------------------------------


class GarmentTypeOut(BaseModel):
    garment_type: str
    label: str
    product_count: int


class ProductSummary(BaseModel):
    """A product card: what the Product page and the chat show for each item."""

    product_id: str
    name: str
    garment_type: str
    garment_label: str
    short_description: str
    price_cents: int
    image_url: str
    in_stock: bool


class SizeStock(BaseModel):
    size: str
    quantity: int


class ProductDetail(ProductSummary):
    description: str
    primary_color: str
    accent_colors: list[str]
    sizes: list[SizeStock]
    total_stock: int


# --- Agent tool results ----------------------------------------------------------------------
# Tools return these instead of raw rows, so the model sees exactly the fields it may quote.
# The model receives each result as JSON (field names and values, not these descriptions), so
# the names themselves say what a field means: `price` is ready to quote, `sold_out_sizes` is
# explicit. Raw columns it shouldn't quote or reason about (price_cents, image paths, search
# tags) are left out.


class ProductMatch(BaseModel):
    """One search result."""

    product_id: str
    name: str
    category: str = Field(description="Shopper-facing category, e.g. 'Hoodies'.")
    short_description: str
    primary_color: str
    accent_colors: list[str]
    price: str = Field(description="Exact price to quote, e.g. '$68.00'.")
    sizes_in_stock: list[str] = Field(description="Sizes with at least one in stock, smallest first.")
    sold_out_sizes: list[str] = Field(description="Sizes at 0, smallest first.")


class SearchResults(BaseModel):
    total_matches: int = Field(description="How many products matched; results may show fewer.")
    results: list[ProductMatch]


class ProductDetails(BaseModel):
    """Everything known about one product, with live stock."""

    product_id: str
    name: str
    category: str
    description: str = Field(description="Full description; the only source for details about the item.")
    primary_color: str
    accent_colors: list[str]
    price: str
    stock_by_size: dict[str, int] = Field(description="Units on the shelf per size, XS to XXL. 0 = sold out.")
    total_in_stock: int = Field(description="Units across all sizes. 0 = the whole product is sold out.")


class StockCheck(BaseModel):
    """Live stock for one product in one size: the answer to "do you have it in M?"."""

    product_id: str
    name: str
    price: str = Field(description="Exact price to quote, so 'how much, and is it in M?' takes one call.")
    size: str = Field(description="The size checked, normalized to XS, S, M, L, XL or XXL.")
    quantity: int = Field(description="Units on the shelf in this size.")
    in_stock: bool
    other_sizes_in_stock: list[str] = Field(description="Other sizes with stock, to suggest when this one is out.")
    sold_out_quip: str | None = Field(
        default=None,
        description="Only when this size is sold out: a short joke to open the reply with. It states no facts.")


class RestockRequestResult(BaseModel):
    """What happened when the agent asked to notify the shopper about a sold-out size."""

    product_id: str
    name: str
    size: str
    result: Literal["saved", "already_saved", "in_stock", "needs_account", "unknown", "too_many"] = Field(
        description="saved / already_saved: they'll see it on the site when it's back. in_stock: it's available now. "
                    "needs_account: guests must log in or create an account first.")


class CategoryInfo(BaseModel):
    """One kind of garment the shop sells."""

    category: str = Field(description="Shopper-facing name, e.g. 'Hoodies'.")
    garment_type: str = Field(description="Value to pass to search_products(garment_type=...).")
    product_count: int
    price_range: str = Field(description="Lowest to highest listed price, e.g. '$38.00 to $72.00'.")


# --- Agent run state and output --------------------------------------------------------------


@dataclass
class ShopDeps:
    """Per-chat-turn state. The agent never sees the shopper's email or id, only a first name and
    a summary of their saved chat (how many messages, and when the last one was sent).

    The tools record every price and product they returned, so the output validator can check
    that the reply only quotes prices and shows products that really came from the catalogue.
    """

    first_name: str | None = None           # None for a guest (not logged in)
    saved_messages: int = 0                 # this shopper's messages already in chat_messages
    last_chat_at: datetime | None = None    # UTC time of the newest of them
    page_path: str | None = None            # the page they're on, e.g. "/products?type=t-shirt"
    user_id: int | None = None              # for request_restock_alert only; never shown to the model
    back_in_stock: list[tuple[str, str, str]] = field(default_factory=list)  # (id, name, size) they asked about
    searches: list[tuple[str, int]] = field(default_factory=list)  # (what was searched, matches) this turn
    sold_out_asks: set[tuple[str, str]] = field(default_factory=set)  # (product_id, size) found at 0 this turn
    viewing_product: tuple[str, str] | None = None  # (product_id, name) on a single-item page, checked to exist
    quoted_prices: set[int] = field(default_factory=set)   # cents
    seen_products: set[str] = field(default_factory=set)


MAX_CHAT_CARDS = 6      # cards under an ordinary reply
MAX_SEARCH_CARDS = 12   # cards a catalogue search puts on the Product page (search_products' limit)
CHAT_PREVIEW_CARDS = 3  # of those, how many the chat panel previews


class ShopReply(BaseModel):
    """The shop assistant's answer."""

    message: str = Field(description="Reply to the shopper in friendly, concise Markdown.")
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_SEARCH_CARDS,
        description="Products to show as cards, best match first. Only ids returned by a tool during this "
                    "reply. At most 6 for an ordinary reply; for a catalogue search (search_title set), every "
                    "match search_products returned, up to 12. Empty if none fit.",
    )
    search_title: str | None = Field(
        default=None,
        max_length=60,
        description="Set only when the shopper asked to see a type of item and you searched the catalogue: a "
                    "short heading for the Product page, e.g. 'Navy hoodies' or 'Hockey T-shirts'. "
                    "The website then shows product_ids there as product cards. Leave null otherwise.",
    )
    unmet_request: str | None = Field(
        default=None,
        max_length=60,
        description="Set only when the shopper asked for something the shop doesn't carry and search_products "
                    "found nothing for it: 2 to 5 words naming what they wanted, e.g. 'Yale umbrellas' or "
                    "'pink hoodies'. Never names or personal details. Saved anonymously for the manager report.",
    )


# --- Chat API --------------------------------------------------------------------------------

ChatText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class PageContext(BaseModel):
    """The page the shopper is on when they send a chat message, so "this" can be resolved.

    Sent by the website, so it is never trusted as is: the API keeps the product id only if
    that product exists, and the agent still looks the item up with its tools.
    """

    path: str = Field(default="/", max_length=200, pattern=r"^/[A-Za-z0-9/_.?=&%+-]*$",
                      description="The site address after the domain, e.g. '/products/basic-hoodie-big-yale'.")
    product_id: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9-]+$",
                                   description="The product shown on a single-item page, if any.")


class ChatIn(BaseModel):
    message: ChatText
    page: PageContext | None = Field(default=None, description="Where the shopper is on the site, if known.")


class CatalogSearch(BaseModel):
    """A chat reply's catalogue search, which the website shows on the Product page."""

    title: str = Field(description="Heading for the results, written by the assistant, e.g. 'Navy hoodies'.")
    products: list[ProductSummary] = Field(
        description="Every matching product card (up to 12), best match first, with live prices and stock.")


class ChatMessageOut(BaseModel):
    """One chat message: the contract between POST /api/chat, GET /api/chat/history and the website."""

    id: int
    role: Literal["user", "assistant"]
    content: str = Field(description="Message text; Markdown for assistant replies.")
    products: list[ProductSummary] = Field(
        default_factory=list,
        description="Cards to show inside the chat panel. For a search reply, the first 3 search results.")
    search: CatalogSearch | None = Field(
        default=None,
        description="Set when the reply is a catalogue search: the website opens the Product page with these "
                    "cards. Null for every other message.")
    created_at: str
