# API Contract — Chat Search That Updates the Page

When a shopper asks the chat about a **type of item** ("show me navy hoodies", "any hockey T-shirts?"), the agent searches the catalogue and the website shows the matches on the **Product page** as product cards (image, name, price, short description). This file is the agreement between the three parts:

1. **Agent → API** (`backend/agent.py`, `backend/models.py`): the shape of the agent's answer, `ShopReply`.
2. **API → website** (`backend/main.py`, `frontend/src/api.ts`): the JSON the chat routes return, `ChatMessageOut`.
3. **Website** (`frontend/src/components/ChatWidget.tsx`, `frontend/src/pages/ProductsPage.tsx`): what the page does with it.

The Python types in `backend/models.py` are the source of truth; `frontend/src/api.ts` mirrors them in TypeScript. FastAPI also publishes them at http://127.0.0.1:8000/docs.

## The flow

```
Shopper types "Show me navy hoodies"
  → POST /api/chat {"message": "Show me navy hoodies"}
    → agent calls search_products(garment_type="hooded sweatshirt", color="navy")
    → agent answers ShopReply{message, product_ids: [12 ids], search_title: "Navy hoodies"}
    → truth check: every id came from the tool; any $ amount came from a tool
    → saved in chat_messages (product_ids + search_title)
  ← ChatMessageOut{..., search: {title, products: [12 cards]}}
Website: opens /products?chat=<message id> with the 12 cards,
         and the chat panel shows a 3-card preview + "See all 12 on the page →"
```

## 1. Agent output: `ShopReply`

| Field | Type | Rule |
|---|---|---|
| `message` | string (Markdown) | The chat reply. For a search, brief: how many were found, one or two highlights. |
| `product_ids` | list of strings, 0–12 | Only ids a tool returned during this reply. **Search:** every result `search_products` returned, in its order (up to 12). **Ordinary reply:** at most 6. |
| `search_title` | string (1–60 characters) or `null` | Set **only** for a catalogue search: the heading for the Product page, e.g. "Navy hoodies". `null` for everything else. |

The output validator in `agent.py` enforces the rules in code, not just in the prompt:
- Ids no tool returned → sent back to the model to fix.
- A dollar amount in `message` **or** `search_title` that no tool returned → sent back to the model to fix.
- `search_title` with no ids → set to `null`, so an empty search never blanks the page.
- No `search_title` → `product_ids` trimmed to 6.

## 2. Chat routes

Both work for logged-in shoppers (session cookie; chats saved in `chat_messages`) and, since Problem 8, for guests (a `cc_guest` cookie; chats kept in server memory for the visit only, never in the database). Errors: 403 must change password, 422 empty or over 1,000 characters, 429 too many messages (shoppers 20, guests 10 per browser and 30 per network address, per 10 minutes), 502 AI service failed (nothing is saved). A guest's search results page works for the rest of their visit.

### `POST /api/chat`

Request:

```json
{ "message": "Show me navy hoodies" }
```

With page context (added in Problem 8; optional, so older clients still work):

```json
{ "message": "hey, do you have this in pink?",
  "page": { "path": "/products/basic-hoodie-big-yale", "product_id": "basic-hoodie-big-yale" } }
```

| `page` field | Rule |
|---|---|
| `path` | Starts with `/`; at most 200 characters; letters, digits and `/_.?=&%+-` only. |
| `product_id` | Lowercase letters, digits and dashes, or `null`. Used only if the product exists. |

Response `200`: one `ChatMessageOut` (the assistant's reply).

### `GET /api/chat/history`

Response `200`: the shopper's last 50 messages, oldest first, each a `ChatMessageOut`. Search replies keep their `search`, so a reloaded or bookmarked results page can be rebuilt. Product cards are looked up fresh every time, so prices and stock are always current.

### `ChatMessageOut`

| Field | Type | Meaning |
|---|---|---|
| `id` | integer | Message id. A search's page address is `/products?chat=<id>`. |
| `role` | `"user"` or `"assistant"` | Who wrote it. |
| `content` | string | The text; Markdown for the assistant. |
| `products` | list of `ProductSummary` | Cards **inside the chat panel**. Ordinary reply: the 0–6 cards discussed. Search reply: the **first 3** of `search.products`, as a preview. |
| `search` | `CatalogSearch` or `null` | **Set only for a catalogue search.** The website shows it on the Product page. `null` for user messages and ordinary replies. |
| `created_at` | string | When it was saved (UTC, `YYYY-MM-DD HH:MM:SS`). |

### `CatalogSearch`

| Field | Type | Meaning |
|---|---|---|
| `title` | string, 1–60 characters | Heading the agent wrote, e.g. "Navy hoodies". |
| `products` | list of `ProductSummary`, 1–12 | Every match, best first. |

### `ProductSummary` (one product card)

The same card the Product page already uses (`GET /api/products`), so the page can show chat results with no extra requests.

| Field | Type | Shown on the card as |
|---|---|---|
| `product_id` | string | Link to `/products/<product_id>`. |
| `name` | string | Product name. |
| `garment_type` | string | (Used for filtering, not shown.) |
| `garment_label` | string | Category, e.g. "Hoodies". |
| `short_description` | string | One line under the price. |
| `price_cents` | integer | Price, formatted on the site as `$68.00`. Whole cents, so no rounding errors. |
| `image_url` | string | Photo, served by `GET /images/products/<file>.jpg`. |
| `in_stock` | boolean | "Sold out" badge when `false`. |

### Example: a search reply

```json
{
  "id": 34,
  "role": "assistant",
  "content": "I found 23 navy hoodies; the Product page shows the top 12. You can narrow them by size, sport, or family design if you'd like.",
  "products": [
    {
      "product_id": "basic-hoodie-big-yale",
      "name": "Basic Big Yale Hoodie",
      "garment_type": "hooded sweatshirt",
      "garment_label": "Hoodies",
      "short_description": "Large white YALE lettering on a navy pullover hoodie",
      "price_cents": 6800,
      "image_url": "/images/products/basic-hoodie-big-yale.jpg",
      "in_stock": true
    },
    "… 2 more (the first 3 of search.products)"
  ],
  "search": {
    "title": "Navy hoodies",
    "products": [
      { "product_id": "basic-hoodie-big-yale", "…": "same card as above" },
      {
        "product_id": "yale-aunt-hoodie",
        "name": "Yale Aunt Hoodie",
        "garment_type": "hooded sweatshirt",
        "garment_label": "Hoodies",
        "short_description": "Navy hoodie with white Yale University Aunt graphic",
        "price_cents": 6800,
        "image_url": "/images/products/yale-aunt-hoodie.jpg",
        "in_stock": true
      },
      "… 10 more"
    ]
  },
  "created_at": "2026-10-26 01:55:12"
}
```

An ordinary reply ("Is the Basic Big Yale Hoodie in XL?") has `"search": null` and its cards in `products`; the page doesn't change.

## 3. What the website does

| When | Website behavior |
|---|---|
| A new reply has `search` | Opens `/products?chat=<id>` and passes the search in router state, so the page appears instantly with no extra request. The chat panel stays open. |
| Shopper clicks **See all N on the page →** (on any search reply, including older ones) | Same as above. On a phone (600px wide or less), where the panel covers the page, it also closes the panel. |
| `/products?chat=<id>` is reloaded or bookmarked | The page reads the search back from `GET /api/chat/history`, with current prices and stock. |
| The id isn't in the shopper's history, or they're logged out | "These search results are no longer available. Ask the shop assistant again, or browse every product." |
| A reply has no `search` | The page doesn't change; cards appear in the chat only. |

The results page shows a "Shop Assistant results" label, the agent's title as the heading, "N items found by the shop assistant", and the same cards and category chips as the rest of the Product page (choosing a chip leaves the search).

## Storage

`chat_messages` gained one column, added automatically at API startup if missing:

| Column | Type | Meaning |
|---|---|---|
| `search_title` | TEXT, 1–60 characters, or NULL | Set for a catalogue search. The existing `product_ids` column holds its results. |

Only the ids and title are stored, never prices or names, so a saved search always shows today's prices and stock.

## Tests (`backend/test_agent.py`)

- A search reply keeps all 12 matches; an ordinary reply is trimmed to 6; an empty search doesn't change the page.
- A made-up price in `search_title` is rejected.
- `POST /api/chat` returns a `search` whose cards match the database exactly (name, price, short description, image URL that loads), with the first 3 in `products`; `GET /api/chat/history` returns the same `search`.
- An ordinary reply returns `"search": null`.
