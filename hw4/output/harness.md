# Campus Customs Shop + Chatbot — Harness

A customer-facing Yale apparel shop (React + Vite + TypeScript) with a PydanticAI shop assistant behind FastAPI. The assistant answers only from `data/data/campus_customs.db`.

**Contents**
- **Harness summary** (this section): model fields, tools and abilities, safety rules, and specs.
- **Details:** database tables, shop API, the shop assistant agent, audit trail, account security, website front end and product photos.

## Harness summary (Problem 12)

### 1. Model fields in `models.py` and why I chose them

**The agent's answer: `ShopReply`** (what the model must return; checked by code before anyone sees it)

| Field | Why |
|---|---|
| `message` | The reply in short Markdown. Its text, never the model's free-form output, is what the shopper sees. |
| `product_ids` (0–12) | The site draws product cards from these ids with **live** prices and stock, so the model never types a price into a card. Only ids a tool returned this turn are accepted. At most 6 for an ordinary reply; up to 12 for a search. |
| `search_title` (≤ 60 characters) | Set only for "show me a type of item"; it tells the website to put the results on the Product page under this heading. Kept separate so the page only changes when a real search happened. |
| `unmet_request` (≤ 60 characters) | 2–5 words naming something the shop doesn't carry ("Yale umbrellas"), for the manager report. Accepted only if a search this turn really found nothing. |

**What the tools give the model: `ProductMatch` / `SearchResults`, `ProductDetails`, `StockCheck`, `CategoryInfo`, `RestockRequestResult`**

| Fields | Why |
|---|---|
| `product_id` | Stable, unique key, used for follow-ups ("is it in XL?") and cards. Names can repeat; ids can't. |
| `price` as text ("$68.00"), not `price_cents` | Ready to quote exactly, so the model never converts or rounds. The truth check compares every `$` in the reply with these. |
| `sizes_in_stock`, `sold_out_sizes`, `stock_by_size`, `quantity`, `in_stock`, `total_in_stock`, `other_sizes_in_stock` | Live stock in the shapes questions need ("is it in M?", "what's left?"), so one call answers, and alternatives are ready when a size is out. |
| `description` (details), `short_description`, `primary_color`, `accent_colors`, `category` | The only allowed sources for describing an item. Two color fields let "navy" mean the garment or its lettering. |
| `total_matches` | Tells the model when there are more than the 12 results shown, so it can offer to narrow the search. |
| `garment_type` + `price_range` (`CategoryInfo`) | The exact value to pass back to `search_products`, plus the honest price range for "what do you sell?". |
| `sold_out_quip` | A canned, fact-free joke, only when a size is at 0, so humor can't invent a restock date. |
| `result` (`RestockRequestResult`) | One of `saved`, `already_saved`, `in_stock`, `needs_account`, `unknown`, `too_many`, so the agent says exactly what happened. |
| *Left out on purpose* | `price_cents`, image paths, `search_tags` (matching only), and every account, session and chat column. |

**Per-turn state the model never sees: `ShopDeps`**

| Field | Why |
|---|---|
| `first_name` (`None` = guest) | Friendly greetings without exposing an email or id. |
| `saved_messages`, `last_chat_at` | Memory: first chat, ongoing, or "welcome back" after more than 2 hours away. |
| `page_path`, `viewing_product` | Page context: what "this" means. Checked against the database first. |
| `user_id` | Lets `request_restock_alert` save for the person chatting only; never put in the prompt. |
| `back_in_stock` | Sizes the shopper asked about that are available again, as good news to share. |
| `quoted_prices`, `seen_products` | Every price and id a tool returned this turn: the evidence the truth check compares the reply against. |
| `searches`, `sold_out_asks` | Unmet demand noticed this turn, saved anonymously for the manager report. |

**API and website models**

| Model | Fields and why |
|---|---|
| `ProductSummary` | `product_id`, `name`, `garment_type`/`garment_label`, `short_description`, `price_cents`, `image_url`, `in_stock`: everything a product card shows, shared by galleries and chat. Prices stay in cents here; the website formats them. |
| `ProductDetail` (+ `SizeStock`) | Adds `description`, colors, `sizes` (every size with its quantity) and `total_stock` for the single-item page. |
| `ChatIn` + `PageContext` | `message` (1–1,000 characters) plus the page `path` and `product_id`, with strict patterns so odd text is refused (422) before it can reach the agent. |
| `ChatMessageOut` + `CatalogSearch` | `id`, `role`, `content`, `products` (cards in the chat) and `search` (`title` + cards for the Product page): the API contract in `output/api_contract.md`. |
| `GarmentTypeOut` | Category chips: `garment_type`, `label`, `product_count`. |

### 2. Tools and abilities

**Tools** (`backend/tools.py`; all read the database live)

| Tool | What it can do | Reads / writes |
|---|---|---|
| `search_products` | Find items by words plus category, color, maximum price and size; up to 12 results, ranked | Read-only |
| `get_product_details` | Full description, colors, price and stock for every size of one product | Read-only |
| `check_stock` | Stock of one product in one size, other sizes in stock, price, and a joke if it's sold out | Read-only |
| `list_categories` | What the shop sells: categories, counts, price ranges | Read-only |
| `request_restock_alert` | Save a "notify me when it's back" request, only after the shopper says yes and only for a logged-in shopper | Writes one row to `restock_requests` |

**Abilities built around the tools**
- **True answers only:** the truth check rejects any price or product card no tool returned, with an honest fallback if the model can't comply.
- **Chat search updates the page:** "show me navy hoodies" fills the Product page with matching cards.
- **Customer memory:** a logged-in shopper's chat is saved and reloaded, with "welcome back" after a break. Guests can chat too; their visit is remembered in memory only.
- **Page context:** "do you have **this** in pink?" on a product page means that product.
- **Sold-out humor and restock alerts:** a joke, the real sizes left, and an offer to notify.
- **Missed demand:** what shoppers wanted and couldn't find, anonymous, for managers.
- **Audit trail:** every turn's steps appended to `output/audit_trail.json`.

### 3. Safety rules

**Truthfulness**
- Every product, price, color, description detail and stock number must come from a tool called during this reply, and stock is checked again each time. **Enforced in code** by the output validator.
- The agent never repeats a price the shopper suggests, never invents features (no password reset, no checkout), and makes no promises about restock dates, holds or discounts. Jokes are canned and fact-free.

**Privacy**
- The agent sees only the shopper's first name, never their email or id. Tools can't read accounts, sessions or chats (a test checks the code).
- Who is chatting comes from the login cookie, never from the chat text.
- Guests' chats are never written to the database. The missed-demand log has no identity. The audit trail stores message lengths, not shoppers' words.
- The agent never asks for passwords, card numbers or other personal data, and tells shoppers not to share them.

**Prompt injection and tampering**
- Shopper messages can't change the rules. Azure's content filter blocks obvious jailbreaks, with a polite refusal instead of an error.
- Page context from the browser is checked against the database before the agent sees it: a product id only if it exists, a category only if it's real, and any other text dropped.
- The agent's only write is a restock request, for the logged-in shopper, after a yes, capped at 50 per shopper.

**Accounts**
- Passwords: at least 12 characters, rated strong even without names or Yale words, and hashed with PBKDF2-SHA256 (600,000 rounds).
- Guessing limits: lockout after 5 failed logins for an email (20 per network address) in 15 minutes.
- Sessions: HttpOnly cookies with only a hash stored, 7-day expiry, and requests from other websites refused.
- Weak old passwords must be changed at the next login. Manager-only report (`is_manager`).

**Cost and abuse**
- Per-turn loop limits (see Specs), per-shopper and per-guest message limits, and a 1,000-character message cap.

**Accountability**
- Append-only, hash-chained audit trail of every agent turn, checked with `backend/audit.py verify`.

### 4. Specs

**Models**

| Use | Model | How |
|---|---|---|
| Shop assistant (all chat) | `gpt-5.6-luna` | Through Portkey (`https://api.portkey.ai/v1`), with `PORTKEY_API_KEY` from the project-root `.env` |
| Short product descriptions (one-time script, `add_short_descriptions.py`) | `gpt-5.6-luna` | Same |
| Banner image (`generate_banner.py`, never used) | `gpt-image-2` | User-approved exception for that image only; the key has no image deployment, so the carousel uses Leonardo.AI photos instead |
| Tests | PydanticAI `FunctionModel` | Scripted stand-in: no AI calls or cost |

**Agent loop limits**

| Limit | Value |
|---|---|
| Model requests per turn | 8 (`UsageLimits(request_limit=8)`) |
| Tool calls per turn | 15 (`tool_calls_limit=15`) |
| Retries (tool errors and failed truth checks) | 2 per tool/output; after that, the honest fallback reply |
| Earlier messages sent as context | 20 |
| "Returning after a break" | more than 2 hours since the last message |

**Result caps**

| Cap | Value |
|---|---|
| Search results per search | 12 (`total_matches` reports the full count) |
| Cards under an ordinary reply / on the page for a search / chat preview | 6 / 12 / 3 |
| Chat history shown on the website | last 50 messages |
| Message length | 1–1,000 characters |
| Search heading, unmet request | 60 characters each |
| Logged-in shopper messages | 20 per 10 minutes |
| Guest messages | 10 per browser and 30 per network address per 10 minutes |
| Guest chats in memory | 2,000 chats × 40 messages, forgotten 2 hours after the last message |
| Restock alerts | 50 open per shopper |
| Manager report | top 25 searches and top 25 sizes, over 7, 30 or 90 days (1–365 allowed) |
| Audit trail text | 300 characters per retry reason or unusual tool result |

**How to run the front end and back end** (two terminals, from the `hw4` folder)

| | Back end (FastAPI) | Front end (React + Vite) |
|---|---|---|
| First time | `python -m venv .venv`, then `.venv/Scripts/pip install -r requirements.txt` | `cd frontend`, then `npm install` |
| Start | `cd backend`, then `../.venv/Scripts/uvicorn main:app --reload --port 8000` | `cd frontend`, then `npm run dev` |
| Address | http://127.0.0.1:8000 (API at `/api/...`) | **http://localhost:5174** (open this one) |

- **Ports:** the website forwards `/api` and `/images` to port 8000. If 8000 is taken, start both with the same `API_PORT` (e.g. `API_PORT=8001`).
- **Environment:** `PORTKEY_API_KEY` must be in the project-root `.env`, which is never committed.
- **Without auto-reload:** `../.venv/Scripts/python main.py` from `backend/`. OneDrive can hide file changes from `--reload`, so restart after edits if needed.
- **Tests:** `.venv/Scripts/python -m pytest backend -q` runs 80 tests (52 agent, 28 accounts) on a throwaway copy of the database and audit trail. Then `cd frontend` and run `npm run build` and `npm run lint`.
- **Useful commands:**
  - `.venv/Scripts/python backend/agent.py --trace "question"` chats from the terminal and shows the tool calls;
  - `.venv/Scripts/python backend/audit.py verify` checks the audit trail;
  - `.venv/Scripts/python backend/insights.py make-manager <email>` gives an account the manager report.
- **Versions:** Python 3.13, FastAPI, PydanticAI 2.55, React 19, Vite 8, TypeScript 6.

## Database: `data/data/campus_customs.db`

### `catalogue` — one row per product

| Field | Why the chatbot needs it |
|---|---|
| `product_id` | Stable key the chatbot uses to look up a product, its stock, and to show product cards. |
| `name` | Readable product name the chatbot says to shoppers and shows on cards. |
| `garment_type` | Filters requests like "show me hoodies" to the right kind of item. |
| `description` | The full (long) description: accurate details the chatbot uses to describe an item and match shopper questions. |
| `short_description` | One line (at most 70 characters) for product cards and quick chatbot lists; written by `gpt-5.6-luna` from `description` only, so it adds no new claims. |
| `primary_color` | Answers "do you have it in navy?" using the garment's own color, not its lettering. |
| `accent_colors` | Matches requests about print or logo colors, like "something with red lettering". |
| `search_tags` | Extra keywords (sport, college, school, style) for finding matching items. |
| `image_file_path` | Shows a photo of each product the chatbot recommends. |
| `price_cents` | Gives exact, true prices; stored in cents so totals never round wrong. |

### `inventory` — stock for each product and size

| Field | Why the chatbot needs it |
|---|---|
| `id` | Unique row key so a single stock record can be updated. |
| `product_id` | Links the stock count to its product in the catalogue. |
| `size` | Answers "do you have it in a medium?" |
| `quantity` | Gives true in-stock / sold-out answers; can never go below 0. |

### `users` — shopper accounts

| Field | Why the chatbot needs it |
|---|---|
| `id` | Ties each shopper to their own chat history. |
| `first_name` | Lets the chatbot greet the shopper by name. |
| `last_name` | Completes the shopper's account name. |
| `email` | Login ID; unique ignoring capital letters so no one gets two accounts. |
| `password_hash` | Securely checks logins without storing the real password (PBKDF2-SHA256, 600,000 rounds, random salt). The chatbot must never read this column. |
| `created_at` | Records when the account was made. |
| `is_manager` | 1 for Campus Customs managers, who can see the missed-demand report. Added at API startup (Problem 9). Set with `backend/insights.py make-manager <email>`. |

### `sessions` — who is logged in (created by the API)

| Field | Why the chatbot needs it |
|---|---|
| `token_hash` | SHA-256 of the browser's session token; identifies the logged-in shopper without storing the token itself. |
| `user_id` | Which shopper the session belongs to, so the chatbot loads their name and chat history. |
| `created_at` | When the session started. |
| `expires_at` | Sessions end after 7 days, so a forgotten login on a shared computer doesn't last forever. |
| `must_change_password` | 1 when the shopper logged in with an older password that breaks today's rules. Until they pick a new one, the session can only change the password or log out, and the chatbot must refuse to serve it. |

### `auth_attempts` — sign-up and login attempts (created by the API)

| Field | Why the chatbot needs it |
|---|---|
| `kind` | `login` or `signup`, so each has its own limit. |
| `email` | Counts wrong passwords per account, to lock out guessing. |
| `ip` | Counts attempts per network address, to stop one source trying many accounts. |
| `success` | Separates failures (which count toward a lockout) from successes. |
| `created_at` | Limits are per time window; rows older than a day are deleted. |

### `chat_messages` — saved conversation history

| Field | Why the chatbot needs it |
|---|---|
| `id` | Keeps messages in the order they were sent. |
| `user_id` | Shows each shopper only their own conversation. |
| `role` | Marks who spoke (`user` or `assistant`) so the chat displays and replays correctly. |
| `content` | The message text, reloaded so the chatbot remembers earlier questions. |
| `product_ids` | Products shown with a reply; looked up fresh so prices and stock are never stale. |
| `search_title` | Heading for a chat search shown on the Product page (e.g. "Navy hoodies"); NULL for other messages. Added at API startup for Problem 7. |
| `created_at` | Timestamp for each message. |

### `garment_types` — allowed item types (lookup)

| Field | Why the chatbot needs it |
|---|---|
| `garment_type` | The standard type names `catalogue.garment_type` must use, so filters never miss items. |
| `display_name` | Shopper-friendly label for the browse menu, such as "Hoodies". |
| `sort_order` | Order the types appear in the browse menu. |

### `color_names` — allowed colors (lookup)

| Field | Why the chatbot needs it |
|---|---|
| `color` | The standard color names products must use, so color searches are consistent. |
| `sort_order` | Order colors appear in a color filter. |

### `sizes` — allowed sizes (lookup)

| Field | Why the chatbot needs it |
|---|---|
| `size` | The valid sizes (XS–XXL) stock can be recorded in. |
| `sort_order` | Lists sizes smallest to largest instead of alphabetically. |

### `restock_requests` — "notify me when it's back" (Problem 9, created by the API)

| Field | Why it's needed |
|---|---|
| `id` | Lets a shopper cancel or dismiss one alert. |
| `user_id` | The logged-in shopper who asked; their alerts only. Deleted with the account. |
| `product_id`, `size` | The sold-out size they want. One request per shopper, product and size. |
| `created_at` | When they asked. |

"Back in stock" isn't stored: it's worked out live from `inventory`, so it works however stock gets updated.

### `demand_signals` — missed demand, anonymous (Problem 9, created by the API)

| Field | Why it's needed |
|---|---|
| `id` | Row key. |
| `kind` | `no_results` (asked for something we don't carry) or `sold_out_size` (asked about a size at 0). |
| `request` | For `no_results`: what was wanted, e.g. "Yale umbrellas" (at most 120 characters). |
| `product_id`, `size` | For `sold_out_size`: the size that was sold out. |
| `created_at` | When it happened, for the report's 7, 30 or 90-day periods. |

There's deliberately no user id, email or chat text, so the report can't identify shoppers.

## Shop API: `backend/main.py`

FastAPI, reading `campus_customs.db` read-only. Run it from the `backend/` folder, as in the assignment; it serves http://127.0.0.1:8000:

```bash
../.venv/Scripts/uvicorn main:app --reload --port 8000
```

- **Without auto-reload:** `../.venv/Scripts/python main.py` does the same. In this OneDrive folder, `--reload` can miss file changes, so restart if an edit doesn't show up.
- **If port 8000 is taken** (e.g. by the Lecture 10 app): pick another port and set `API_PORT` to the same number for the website's dev server, e.g. `API_PORT=8001 npm run dev`.

| Endpoint | Returns |
|---|---|
| `GET /api/products?type=<garment_type>` | Product cards: id, name, type label, short description, price in cents, photo URL, in-stock flag. `type` is optional. |
| `GET /api/products/{product_id}` | Everything on a card, plus the full description, colors, stock per size (XS→XXL) and total stock; 404 if unknown. |
| `GET /api/garment-types` | Categories that have products, with labels and counts, in menu order. |
| `GET /images/products/<file>.jpg` | Product photos from `data/data/products/`. |
| `GET /api/health` | `{"status": "ok"}`. |
| `POST /api/auth/signup` | Creates an account (first name, last name, email, password) and logs in; 400 with reasons for a guessable password, 409 for an email already in use. |
| `POST /api/auth/login` | Logs in; 401 "Email or password is incorrect." for any failure; 429 while locked. |
| `POST /api/auth/logout` | Ends the session and clears the cookie. |
| `GET /api/auth/me` | The logged-in shopper (id, names, email, `must_change_password`), or 401. |
| `POST /api/auth/change-password` | Needs a login and the current password. The new password must meet the rules and differ from the old one. On success, every other session for the account is logged out and this one gets a fresh, unflagged session. |
| `POST /api/chat` | `{"message": "...", "page": {"path": "...", "product_id": "..."}}` (message 1–1000 characters; `page` optional, see "Page context") gets the assistant's reply: Markdown text plus product cards with live prices, and a `search` (title plus up to 12 cards) when the shopper asked to see a type of item. See `output/api_contract.md`. Open to guests and logged-in shoppers; a session that must change its password gets 403. Shoppers: at most 20 messages per 10 minutes, saved in `chat_messages`. Guests: at most 10 per browser and 30 per network address per 10 minutes, kept in memory only (429 past a limit). 502 if the AI service fails, and nothing is saved then. |
| `GET /api/chat/history` | A shopper's own last 50 saved messages, or a guest's messages from this visit, with product cards and searches looked up fresh. |
| `GET /api/restock-alerts` | The shopper's restock alerts (logged in): product, size, photo, and `status` `waiting` or `back`, with back-in-stock ones first. |
| `POST /api/restock-alerts` | `{"product_id", "size"}` saves an alert. 404 unknown, 409 if that size is in stock now, 429 past 50 alerts. Saving the same one again changes nothing. |
| `DELETE /api/restock-alerts/{id}` | Cancels or dismisses one of the shopper's own alerts (204). |
| `GET /api/manager/demand-report?days=30` | Managers only (403 otherwise): top 25 searches with no results, and top 25 sold-out sizes by how often they were asked about and how many shoppers are waiting, with current stock. |

Code:
- `backend/main.py`: the app, product and chat routes, and the security middleware.
- `backend/auth.py`: accounts and sessions.
- `backend/catalog.py`: catalogue queries shared by the API and the agent's tools.
- `backend/db.py`: database connections.
- `passwords.py`: hashing and password rules.
- The agent: `backend/agent.py`, `backend/tools.py`, `backend/models.py` and `backend/prompts/prompt.md` (see "Shop assistant agent").

- **Prices and stock** come straight from the database on every request, so the site and the chatbot always show true values.
- **Database connections:** each request opens its own read-only connection. That connection may be used across FastAPI's worker threads, never shared between requests.

## Shop assistant agent (PydanticAI behind FastAPI)

A PydanticAI `Agent` using `gpt-5.6-luna` through Portkey (key from the root `.env`). It answers questions about products, prices and stock using live data from the database.

| File | Role |
|---|---|
| `backend/prompts/prompt.md` | System prompt in sections: Role, Truthfulness, The website, Using the tools, Sold out? Make them smile, Restock alerts, Showing products (catalogue search for the page vs. cards in the chat), Memory, Page context, Voice, Safety. It's re-read on every turn, so edits apply without restarting; this is the file to grow later. Today's date, who is chatting (name or guest, saved history, good news) and the page they're on are added at run time. |
| `backend/agent.py` | Builds the agent: model, prompt, tools, `ShopReply` output, 2 retries, and limits of 8 model calls and 15 tool calls per turn. It holds the **truth check** (an output validator), turns saved chat rows into message history, handles Azure's content filter politely, writes each turn to the audit trail, and has a command-line runner (`--trace` shows tool calls). |
| `backend/tools.py` | `search_products` (words plus category, color, maximum price and size filters), `get_product_details`, `check_stock`, `list_categories` and `request_restock_alert`. Read-only, catalogue and stock only, except `request_restock_alert`, which saves a "notify me" request for the logged-in shopper. Bad categories, sizes or ids raise `ModelRetry` with the valid choices. When a size is sold out, `check_stock` also returns a `sold_out_quip`: one of 7 canned jokes. |
| `backend/models.py` | Pydantic types: the API's product models; the tool results the model is allowed to quote (`ProductMatch`, `SearchResults`, `ProductDetails`, `StockCheck`, `CategoryInfo`) (see "Agent tools and the fields they use"); the run state `ShopDeps`; the output `ShopReply` (Markdown `message`, up to 6 `product_ids`, or up to 12 with a `search_title` for a catalogue search); and the chat API's `ChatIn`, `ChatMessageOut` and `CatalogSearch` (see `output/api_contract.md`). |

### Agent tools and the fields they use (`backend/tools.py`, `backend/models.py`)

Each tool reads `campus_customs.db` live through a read-only connection, and returns a Pydantic type from `models.py` instead of raw rows. The model gets each result as JSON (field names and values), so every field name says what it means, and columns the model shouldn't quote or reason about are left out. The prompt's "Using the tools" section maps each kind of shopper question to a tool, and requires a tool call before any price or stock answer.

**Lookup fields: the columns the tools search or filter on, and why**

| Lookup field | Used by | Why this field |
|---|---|---|
| `catalogue.product_id` | `get_product_details`, `check_stock` | The table's stable, unique key. Names can repeat or be reworded, but an id always points to exactly one product. It also links each product to its `inventory` rows and to the product cards. |
| `catalogue.garment_type` | `search_products(garment_type=...)` | A controlled vocabulary checked against `garment_types`, so "hoodies" maps to exactly one value. A free-text match would miss spelling variants, the problem fixed during setup. An unknown value returns the valid list to the model. |
| `catalogue.primary_color`, `accent_colors` | `search_products(color=...)` | Two fields, so "navy" can mean the garment or its lettering. A match on the garment's own color ranks higher. Values come from the `color_names` list; common words like "grey" and "navy blue" are mapped to it. |
| `catalogue.price_cents` | `search_products(max_price=...)` | Whole cents, so "under $40" is an exact integer comparison with no rounding errors. |
| `inventory.size` (via `sizes`) | `check_stock`, `search_products(size=...)` | Normalized to XS–XXL from the `sizes` table, whose `sort_order` keeps sizes smallest-first. Words like "medium" are translated before the lookup. |
| `inventory.quantity` | All tools that return stock | The only true source for stock. 0 means sold out, and a database rule stops it going below 0. |
| `catalogue.name`, `search_tags`, `description`, `short_description` | `search_products(query=...)` | Words in the name count most (3 points), tags next (2), and the descriptions and colors least (1), so "hockey" ranks hockey designs above a passing mention. |
| `garment_types.display_name`, `MIN/MAX(price_cents)` | `list_categories` | Gives shopper-facing category names, counts and price ranges for "what do you sell?". |

**Each tool and what it returns**

| Tool | Answers | Returns (`models.py`) | Fields chosen and why |
|---|---|---|---|
| `search_products` | "Show me navy hoodies under $60", "anything for hockey?" | `SearchResults` → list of `ProductMatch` | `product_id` for follow-ups and cards. `name`, `category`, `short_description` and colors to describe the item. `price` as ready-to-quote text ("$68.00"), not cents, so the model never does arithmetic. `sizes_in_stock` and `sold_out_sizes` (new) give stock at a glance without a second call. `total_matches` tells the model there may be more than the 12 shown. |
| `get_product_details` | "Tell me about it", "what sizes are left?", comparisons | `ProductDetails` | `description` is the full text, and the only allowed source for item details. `stock_by_size` lists every size with its count (0 = sold out), and `total_in_stock` (now documented) flags a fully sold-out product. |
| `check_stock` | "Do you have it in M?", "how many XL are left?" | `StockCheck` | `size` comes back normalized so the reply names it correctly. `quantity` and `in_stock` give the exact answer. `other_sizes_in_stock` gives alternatives when it's out. `price` (new) means "how much, and is it in medium?" takes one call. `sold_out_quip` is a canned joke, only when the size is at 0. |
| `list_categories` | "What do you sell?", "what's the cheapest hoodie?" | list of `CategoryInfo` | `category` is the shopper-facing name, `garment_type` the exact value to pass to `search_products`, plus `product_count` and `price_range` (lowest to highest listed price). |

| `request_restock_alert` | "Yes, let me know when it's back" (after the agent offers) | `RestockRequestResult` | `result` is `saved`, `already_saved`, `in_stock`, `needs_account` (guests), `unknown` or `too_many`, so the agent says exactly what happened. The shopper's id comes from `ShopDeps.user_id`, which the model never sees, so it can only save for the person chatting. |

**Left out on purpose:** `price_cents` (the model gets the formatted `price` instead), `image_file_path` (the website adds photos from `product_ids`), `search_tags` (used for matching only), and all account, session and chat tables, which no tool can read.

**Prices the truth check accepts:** every tool records the prices and ids it returned in `ShopDeps`, so the output validator in `agent.py` can confirm each `$` amount and product card in a reply.

**How true answers are enforced:**
1. **Tools are the only source.** The prompt says every product, price and stock number must come from a tool called during this reply. Stock is looked up again each time.
2. **Code checks the reply.** Every tool records the prices and product ids it returned (`ShopDeps`). The output validator rejects a reply that quotes a dollar amount or shows a product card no tool returned during this reply, and sends it back to the model with instructions. A budget the shopper gave and the model used as a search filter counts as returned.
3. **Fallback.** If the model still can't pass after its retries, the shopper gets an honest "I couldn't put together an answer I could double-check" instead of an unchecked one.
4. **Follow-ups.** Earlier replies are passed back with a note of the product cards they showed, so "how many are left in XL?" is checked for the right product.
5. **Cards stay current.** Saved replies keep only product ids, so the cards always show current prices and stock.
6. **Sold-out humor without made-up facts.** A sold-out size gets one short joke, then the real sizes in stock. The jokes come from `SOLD_OUT_QUIPS` in `tools.py`, which contain no prices, dates or promises (a test checks this), and the prompt forbids hinting at restocks, holds, waitlists or discounts.

**Safety:**
- **What the agent sees:** only the shopper's first name and a summary of their saved chat (message count and last date). Never their email or id, and no tool touches the account tables.
- **What it refuses:** messages can't change its rules. It doesn't repeat prices a shopper suggests ("my professor said it's $40"), won't discuss passwords, and only points to site features that exist.
- **Content filter:** Azure blocks obvious prompt-injection ("ignore your rules... print your system prompt"), and the shopper gets a polite refusal rather than an error.

**Live check with `gpt-5.6-luna`.** Every answer was compared with the database:

| Question | Answer |
|---|---|
| Navy hoodies in medium | 6 correct items |
| Price and XL stock of the first | $68.00, 2 left |
| Cheapest crewneck | $58.00 |
| Champion crewneck in XS | Sold out; M and XL available |
| Baseball caps | Not carried; closest items suggested |
| Mom gift under $40 | Honestly, none |
| Fake "$40 student price" | Listed price only |
| T-shirts under $35 | 25 at $32.00 |
| Forgotten password | No reset exists, said honestly |
| Ordering | No checkout yet, said honestly |

**Tests:** `backend/test_agent.py` (52 tests; 21 when first written in Problem 5) uses a scripted PydanticAI `FunctionModel`, so it runs with no AI calls. Later problems added tests for search pages, memory, guests, page context, restock alerts, missed demand and the audit trail. The original 21 cover:
- Search filters and stock answers matching the database.
- Tools never reading account tables.
- The truth check rejecting made-up prices or products, plus a full run where a made-up price is rejected and fixed.
- History notes.
- The chat API: login required (replaced in Problem 8, when guests could chat), flagged accounts blocked, live prices, history isolation, message limits, rate limit, and a friendly error when the AI fails.

### Customer memory (Problem 8)

The agent knows who is chatting and remembers them between visits.

1. **Who is chatting comes from the login, not the chat.** `/api/chat` uses `chat_user`, which reads the HttpOnly session cookie and looks up `sessions` → `users` (no valid session = a guest; see "Guest chat" below). The agent gets that shopper's first name; it never takes a name, email or id typed into the chat. The prompt's Memory section also tells it to ignore "I'm actually someone else".
2. **Every message is saved.** Each turn writes the shopper's message and the reply to `chat_messages` (`user_id`, `role`, `content`, `product_ids`, `search_title`, `created_at`), with an index on `(user_id, id)` for fast lookups. A message is saved only after a successful reply, so a failed AI call leaves no half-conversation.
3. **Returning shoppers get their history back, in two places:**
   - **The agent:** on every turn, `main.py` loads that shopper's last 20 messages (`HISTORY_MESSAGES`) as PydanticAI message history. It also passes the total number of saved messages and the time of the newest one (`ShopDeps.saved_messages`, `ShopDeps.last_chat_at`). `agent.memory_note()` turns those into one line under "This conversation": first conversation, earlier today, or "N days ago … returning after a break" once the gap is over 2 hours (`NEW_VISIT_GAP`).
   - **The website:** the chat panel reloads up to 50 saved messages (`GET /api/chat/history`), groups them under day dividers ("Thursday, October 22", "Yesterday", "Today"), and shows "Welcome back, <name>! Your earlier chat is above." before the new visit.
4. **Prompt rules (Memory section):** use the history (sizes, colors, budgets, items shown) so shoppers don't repeat themselves, welcome a returning shopper back once, and **re-check prices and stock with a tool**, since memory is not stock. If asked about something older than the history, say so.

**Privacy:** each shopper's history is loaded with `WHERE user_id = ?` from their own session, so no one sees another shopper's chat (tests check this for both the website and the agent). The agent only ever gets the shopper's first name.

**Checks:** `test_returning_shopper_gets_their_own_history_back` logs Ada in and out, with Grace chatting in between, and moves Ada's chat back 3 days. On return, Ada's history reloads, the agent receives exactly her earlier messages plus "returning after a break", and Grace's chat never reaches it. Live with `gpt-5.6-luna`: a shopper said their son wears a medium and loves hockey. Three days later (moved back in the database), "Any other hockey shirts in his size?" got "Welcome back, Pat!" and the Yale Field Hockey T-Shirt, which has 25 in medium.

### Guest chat (Problem 8)

Anyone can chat; only logged-in shoppers' chats are saved.

| | Logged-in shopper | Guest |
|---|---|---|
| Can chat | Yes | Yes |
| Where the chat is kept | `chat_messages` table, for good | Server memory only (`backend/guest_chat.py`), never the database |
| How long | Every future visit | Until 2 hours after the last message, a server restart, or logging in |
| Agent knows | First name, saved history, last visit date | "A guest": no name, just this visit's messages |
| Limits | 20 messages per 10 minutes | 10 per browser and 30 per network address per 10 minutes |

- **How a guest is recognized:** a random id in an HttpOnly `cc_guest` cookie (page scripts can't read it), linked to their messages in memory. At most 2,000 guest chats of 40 messages are kept, and the oldest are dropped first.
- **Logging in switches to the saved history.** The guest chat is dropped and its cookie cleared. It isn't copied into the account, because "saved" should mean the shopper chose to keep it. Logging out later doesn't bring it back.
- **Prompt (Memory section):** guests get no name, even if they type one. If they ask to be remembered or about an earlier visit, the agent explains that chats are saved only with a free account, and otherwise doesn't push sign-up.
- **Checks:** 4 tests:
  - a guest can chat, with nothing written to the database;
  - the agent gets "guest", no name, and the visit's messages;
  - both guest limits work;
  - logging in drops the guest chat and starts the saved history.

  Live, a logged-out visitor on the Basic Big Yale Hoodie page asked "hey, do you have this in pink?" and got a true answer (navy only; the dusty coral Big Yale Tri-Blend T-Shirt in S, M, XL and XXL). The database's chat table was unchanged, and the chat came back after a page reload during the same visit.

### Footer account links (Problem 9)

The footer's **Account** links now match who is visiting, like the header:
- **Guests:** Log in, Create account.
- **Logged-in shoppers:** Change password and Log out, plus Manager report for managers.

Log out is a button, since it's an action rather than a page, styled like the other footer links.

### Back-end improvements (Problem 9): `backend/insights.py`

**1. Restock alerts ("notify me when it's back")**
- **Asking:** a logged-in shopper asks in one of two ways:
  - on a product page, with the **Notify me** button on a sold-out size (it becomes **✓ Alert on**, and clicking again cancels);
  - in the chat, where after a sold-out answer the agent asks "Want me to let you know if it's back in L?" and calls `request_restock_alert` only after a yes.
- **Guests:** they're asked to log in, since an alert needs an account to reach them.
- **When stock returns:**
  - a **Good news!** banner under the header (View / ×; × dismisses and deletes the alert);
  - the agent is told under "This conversation" and mentions it once, after checking current stock.
- **The promise is limited on purpose:** the prompt makes the agent say only "If the L comes back in stock, you'll see a note here on the site", never a date, hold or guarantee.

**2. Missed-demand report (managers)**
- **What's recorded:** what shoppers wanted and the store couldn't supply, saved in `demand_signals` with no identity:
  - **No results:** the agent names the request in `ShopReply.unmet_request` (e.g. "Yale umbrellas"). The output validator accepts it only if a search that turn really found nothing. If the agent gives none but every search found nothing, the first search is recorded instead.
  - **Sold-out sizes:** every `check_stock` that finds 0 is recorded.
- **The report:** **Manager report** (footer link, managers only, `/manager`) shows both tables for the last 7, 30 or 90 days. Sold-out sizes are ranked by shoppers waiting (×3) plus times asked, with current stock, so restocked items show "(restocked)".

**Checks:**
- **Tests:** 74 backend tests pass (8 new):
  - alerts need an account, refuse in-stock sizes, don't duplicate, turn `back` when stock returns, and only the owner can delete them;
  - the tool saves only for a logged-in shopper;
  - the agent hears the good news;
  - demand is recorded once per turn, without identity, and alternatives don't hide a miss;
  - the report is managers-only and ranks correctly.
- **Front end:** builds and passes its code checks.
- **Live with `gpt-5.6-luna`:**
  - A guest asked "Do you sell Yale umbrellas?" and "Any pink hoodies?", and both were recorded.
  - A shopper asked "Do you have this in a large?" on the Champion crewneck page. The agent made a sold-out joke, gave the real sizes, and offered the alert. After "Yes please!" it was saved.
  - **Notify me** on XS saved a second alert.
  - After L was set to 3 for the test, the banner appeared and the agent said "back in L, with 3 available… $58.00".
  - The manager page listed both searches and both sizes.
- **Cleanup:** the test stock, account, alerts and demand rows were all removed afterwards.

**Why a model-named request, not just "the search found nothing":** in the first live test the agent searched "umbrella" (nothing), then searched again for alternatives to suggest, which found items, so the simple rule missed it. Letting the agent name the request, checked by code, records what the shopper actually wanted.

### Page context (Problem 8)

So that "do you have **this** in pink?" on a product page means that product.

1. **The website sends the page with every message.** `ChatWidget.tsx` adds `page: {path, product_id}` to `POST /api/chat`: the address (e.g. `/products/basic-hoodie-big-yale`), and the product id when the shopper is on a single-item page (`null` elsewhere).
2. **The API checks it before the agent sees it.** The browser could send anything, so `main.page_for_agent()` keeps:
   - a product id only if that product exists, adding its name from the database;
   - a category filter only if it names a real category (shown by its label, e.g. "Hoodies");
   - a search-results page only by its number;
   - any other page reduced to home, Product, About or "other".

   `PageContext` in `models.py` also rejects odd characters and long values (422). So text smuggled into the address never reaches the agent's instructions.
3. **The agent is told where the shopper is.** `agent.page_note()` adds one line under "This conversation", e.g. *The shopper is on the product page for "Basic Big Yale Hoodie" (product_id: basic-hoodie-big-yale). Words like "this", "it" or "this one" mean that item.*
4. **Prompt rules (Page context section):**
   - On a product page, look that item up right away.
   - For "this in another color", say what color it comes in (each product has one), then search the same kind of garment in the color asked; "pink" is listed as coral.
   - For "this in a large", check that size.
   - A different item named in the message wins over the page.
   - On pages without a product, "this" comes from the history, or the agent asks which item.

**Checks:** 64 backend tests pass (7 new): the line the agent gets, the database checks (including smuggled text in the address and fake product ids), malformed page data refused, and the product reaching the agent's instructions. Live with `gpt-5.6-luna`:

| Page | Shopper asked | Agent answered | Database |
|---|---|---|---|
| Basic Big Yale Hoodie | "hey, do you have this in pink?" | Only in navy with white YALE lettering, not pink. The coral Big Yale Tri-Blend T-Shirt comes in S, M, XL and XXL. Both cards were shown. | ✓ |
| Yale Champion Reverse Weave Crewneck | "Do you have this in a large?" | A sold-out joke, then sold out in L, available in M and XL, $58.00 | ✓ |

## Audit trail (Problem 12): `output/audit_trail.json`

An append-only record of the shop assistant's agent loop. One record is added per chat turn (`backend/audit.py`, written from `agent.reply_to`), and the file is never wiped between runs.

**Each record holds:**

| Field | What it records |
|---|---|
| `seq`, `prev_hash`, `hash` | Position in the trail and a SHA-256 chain to the record before it (tamper evidence). |
| `time`, `duration_ms` | When the turn started (UTC) and how long it took. |
| `event`, `agent`, `model` | `chat_turn`, `campus_customs_shop_assistant`, `gpt-5.6-luna`. |
| `shopper` | `{"type": "account", "user_id": 7}` or `{"type": "guest"}`, from the login session, never from the chat. |
| `page`, `viewing_product` | Page context, already checked against the database. |
| `message_chars`, `history_messages` | Length of the shopper's message and how many earlier messages were sent as context. **The message text itself isn't stored.** |
| `steps` | The agent loop in order: `model_response` (with the exact model version), `tool_call` (tool and arguments), `tool_result` (a summary of what the tool returned) and `retry` (a tool error or the reply truth check, with the reason). |
| `model_requests`, `tool_calls`, `retries` | Counts, for quick scanning. |
| `writes` | Anything the agent saved, e.g. `restock alert saved: champion-reverse-weave-crewneck L`. |
| `outcome`, `error` | `answered`, `refused_by_content_filter`, `fallback_unverified` (truth checks kept failing) or `error` (the chat got a 502), plus the error type. |
| `reply` | Length, product card ids, search title and unmet request. Not the text, which can repeat what the shopper said. |
| `usage` | Model requests and input/output tokens (cost). |

**How it stays append-only:**
- **Never rewritten:** the file is a JSON list, like the course's Lecture 5 audit log, so it opens as normal JSON. But it's never rewritten: a new record replaces only the closing `]`, and the bytes before it never change. A test checks this.
- **Never reset:** after a server restart the trail is read (to continue `seq` and the hash chain), never cleared. The class pattern started a new list whenever the file couldn't be read; this one never does. If the end of the file is damaged, new records go to `audit_trail.rescue.json` and the original is left untouched.
- **Checking it:** `.venv/Scripts/python backend/audit.py verify` (from `hw4/`) checks the whole chain. Any edited, deleted or reordered record is reported by number.
- **Tests:** they write to a throwaway trail (`CC_AUDIT_PATH`, set in `conftest.py`), so test runs never add to the real one.
- **Never breaks a chat:** an audit failure is logged and the chat goes on. A turn that fails is still recorded (outcome `error`) before the 502 is returned.

**Privacy:**
- **No shoppers' words:** guests were promised their chats aren't saved, and anyone may type personal details. The trail records what the agent did, not what people said.
- **Account number only:** shoppers appear by account id, with no names or emails.
- **Tool arguments:** these are the agent's own search terms and product ids.

**Checks:**
- **Tests:** 80 backend tests pass (6 new), covering:
  - append-only bytes, and continuing after a "restart";
  - detection of an edited record and of a deleted one;
  - a damaged file left untouched, with a rescue file used instead;
  - a full chat turn recorded step by step, without the shopper's words (a message with a name and phone number was checked);
  - a truth-check retry and a failed turn recorded;
  - tests isolated from the real file.
- **Live with `gpt-5.6-luna`:** two guest turns were recorded:
  - a stock check: `search_products` → `check_stock` (XS: 0, M and XL in stock), 3 model requests, about 14,000 input tokens;
  - a hockey T-shirt search: 2 results.

  After a server restart, a third turn ("What categories do you sell?" → `list_categories`) was added as record 3, linked to record 2, and `verify` reported "3 records, chain intact".

## Account security

The goal is to stop both people and automated tools (including AI agents) from guessing or stealing passwords.

| Threat | Defense |
|---|---|
| **Weak or reused passwords** | At least 12 characters, at most 128. The `zxcvbn` strength checker refuses common passwords, keyboard patterns and dictionary words (score of at least 3 out of 4 required). No forced symbols, following NIST SP 800-63B. |
| **Personal guesses** (name, email, "yalebulldogs2026"): what an AI that looked someone up would try first | The shopper's own name and email, plus Yale and shop words, count as guessable. Once those are removed, what's left must be strong on its own. |
| **Online guessing / credential stuffing** | An email locks for 15 minutes after 5 wrong passwords, even for the right one; one address locks after 20 failures; sign-ups are limited to 10 tries per address per hour. Responses are 429 with `Retry-After`. |
| **Finding out who has an account** | The login page gives the same message for an unknown email and a wrong password, and both take the same time (a dummy hash check). The sign-up page does say when an email is taken, a usual trade-off for shops, softened by the sign-up limit. |
| **Stolen database** | Passwords are PBKDF2-SHA256 with 600,000 rounds (OWASP's level) and a 16-byte random salt, about 0.2 s per guess. Session tokens are stored only as SHA-256 hashes. Old 120,000-round seed hashes are upgraded at the next login. |
| **Stolen session** | A 256-bit random token in an `HttpOnly` (page scripts can't read it), `Secure`, `SameSite=Lax` cookie that lasts 7 days and ends at log out. |
| **Another website acting for a logged-in shopper** (cross-site request forgery) | Changes are only accepted from the shop's own pages (the Origin check), with a JSON-only API and SameSite cookies. |
| **Other web attacks** | Headers block framing (`X-Frame-Options: DENY`) and file-type sniffing; auth responses aren't cached; names refuse `<` and `>`. |
| **Older weak passwords** (set before these rules, e.g. the seed accounts) | At login the password is checked against today's rules. If it fails, the login works but the session is flagged: the site sends the shopper to **Choose a New Password**, and `require_user` (for shopper features like the chat) answers 403 `password_change_required`. The change needs the current password, a stolen session alone isn't enough, and wrong guesses count toward the lockout. A successful change logs out every other device. |
| **Prompt injection against the chatbot** (an "AI hack" on the shop itself) | The agent's tools read only the catalogue and stock, never `users`, `sessions`, `auth_attempts` or chat history (a test checks the code). The agent never takes an email or user id from the chat. `/api/chat` acts only for the logged-in shopper `require_user` identifies, and passes the agent just their first name. Azure's content filter also blocks obvious jailbreak messages. |
| **AI cost abuse** (a script hammering the chat) | 20 messages per shopper per 10 minutes; guests 10 per browser and 30 per network address per 10 minutes; 1000 characters per message, and at most 8 model calls and 15 tool calls per reply. |

**Tests:** `backend/test_auth.py` runs 28 attack-style tests against a throwaway copy of the database: guessable passwords, duplicate emails, plain-text leaks, identical failure messages and timing, lockout, password spraying, sign-up flooding, hash upgrade, cookie flags, reuse of a logged-out token, other-site requests, and the forced change (flagging, blocking, wrong current password, weak or unchanged new password, other devices logged out, lockout). Run them from `hw4`:

```bash
.venv/Scripts/python -m pytest backend -q
```

That command runs both test files: 49 tests, with the throwaway database set up in `backend/conftest.py`.

**Known limits:**
- **Seed accounts:** the three seed accounts keep their old passwords until their next login. Any that break the rules (the Test User's certainly does) must then choose a new one before shopping.
- **Address limits in development:** through the Vite dev server every request appears to come from `127.0.0.1`, so the per-address limits are effectively shared in development.
- **Not built yet:** password reset, email verification and two-factor login.

## Website front end: `frontend/`

React + Vite + TypeScript, with React Router for pages. Run it with `npm run dev` inside `frontend/`; it serves at http://localhost:5174 (5173 is used by the Lecture 10 app). The dev server forwards `/api` and `/images` to the shop API on port 8000 (or `API_PORT`), so start the API too.

### Top navigation and pages

| Nav item | Route | Page file | What it does now |
|---|---|---|---|
| Home | `/` | `src/pages/HomePage.tsx` | Hero banner (headline panel + a photo carousel of the JPGs in `images/`), six "Shop by category" tiles, and three feature notes (live stock, shop assistant, matching items). |
| Product | `/products` | `src/pages/ProductsPage.tsx` | Category chips from `/api/garment-types` (`?type=` filters) and a grid of product tiles: photo, name, price, short description, and a "Sold out" badge when nothing is left. Each tile opens its product page. `?chat=<message id>` shows a chat search instead, under a "Shop Assistant results" label and the agent's heading. A **Cards per row** picker sits above every gallery (see "Usability improvements"). |
| *(from a tile)* | `/products/:productId` | `src/pages/ProductPage.tsx` | Large photo on the left. On the right: type, name, price, full description, colors, and all six sizes, each marked "In stock", "Only N left" (5 or fewer) or "Sold out". Includes a breadcrumb back to the category and a **Back to <gallery> ×** button (or Esc) that returns to the gallery the shopper came from, scrolled to where they were; unknown ids show "Product not found". |
| About Us | `/about` | `src/pages/AboutPage.tsx` | What Campus Customs sells and how the shop assistant and accounts help. |
| Log In | `/login` | `src/pages/LoginPage.tsx` | Email + password (with Show/Hide). On success it returns to the page you came from; it shows the generic failure or lockout message otherwise. If you're already logged in, it shows a "You're logged in" card. |
| Create Account | `/create-account` | `src/pages/CreateAccountPage.tsx` | First and last name, email, password + confirm. A hint explains what makes a good password, and the server's reasons appear under the field they belong to. On success you're logged in and returned. |

**Change Password** (`/change-password`, `src/pages/ChangePasswordPage.tsx`) asks for the current password and a new one, entered twice. When the session is flagged, it's titled "Choose a New Password", explains why, and offers "Log out instead". `src/App.tsx` sends a flagged shopper back to it from any other page. After saving, Continue returns to where they were headed. The shared password limits and hint live in `src/passwordRules.ts`.

When someone is logged in, the header swaps **Log In / Create Account** for **"Hi, First name"** and **Log Out**. The login state comes from `src/auth/` (an `AuthProvider` that asks `/api/auth/me` on load, and a `useAuth()` hook). `src/components/PasswordField.tsx` is the shared password input.

Shared pieces:
- `src/components/SiteHeader.tsx`: the nav, with a menu button on phones.
- `src/components/SiteFooter.tsx`: the footer.
- `src/api.ts`: typed calls to the shop API, plus price formatting.
- `src/catalogue.ts`: the home page's category tiles and photo lookup.
- `src/components/ChatWidget.tsx`: the chat.

### Usability improvements (Problem 9)

**1. Close a product and return to the gallery** (`ProductPage.tsx`, `gallery.ts`)
- **The button:** each product page has a **Back to Hoodies ×** button at the top right, next to the breadcrumb. **Esc** does the same, except while typing or using the chat.
- **Where it goes:** the gallery the shopper came from (a category, All Products, or a chat search such as "Navy hoodies"), scrolled back to where they were. A product card records the gallery and scroll position at the moment it's clicked, in router state. Ctrl-click still opens a new tab.
- **Opened directly** (a link, bookmark or chat card): the button goes to the product's own category, e.g. "Back to T-Shirts".
- **Phones:** the button shrinks to just the × icon, still labelled "Close and go back to …" for screen readers.

**2. Choose how many cards per row** (`ProductsPage.tsx`, `index.css`)
- **The picker:** "Cards per row" sits beside the item count on every product gallery (All Products, each category, chat search results).
- **Choices:**

  | Screen | Options |
  |---|---|
  | Wider screens | Auto (fits about 5), 2, 3, 4, 5 |
  | Tablets | at most 3 |
  | Phones | 1 or 2 |
- **Remembered:** the choice is kept in this browser (`localStorage`) and applies to every gallery. If storage is blocked, the page just uses Auto.

**Checks:**
- **Builds:** the front end builds and passes its code checks.
- **Browser, closing a product:**
  - From Hoodies scrolled down 1,500px, a card opened its page and **Back to Hoodies ×** returned to Hoodies at exactly 1,500px.
  - From All Products, the button read "Back to All Products".
  - A product opened directly read "Back to T-Shirts", and Esc went there.
- **Browser, cards per row:**
  - Auto/2/3/4/5 gave 5/2/3/4/5 columns.
  - The choice carried over to another category and survived a reload.
  - On a phone (375px) only 1 and 2 are offered, 1 gives a single column, and nothing scrolls sideways.

### Chat widget (bottom right, every page)

- **Opening and closing:** a round Yale Blue button opens a chat panel titled "Shop Assistant". The × button, the launcher or the Escape key closes it.
- **Sending:** Enter sends and Shift+Enter adds a new line. Messages appear as bubbles (shopper on the right in Yale Blue, assistant on the left in white), and the list scrolls to the newest.
- **Connected to the agent:** messages go to `POST /api/chat`. While the agent works, three animated dots show it's typing.
- **Replies:** shown as Markdown (via `react-markdown`, which doesn't run raw HTML), followed by a row of small product cards (photo, name, live price, "Sold out" if so) that link to each item's page. Errors (rate limit, AI outage) appear as a red assistant bubble.
- **Logged out:** guests chat normally, under a note: "You're chatting as a guest, so this chat isn't saved after you leave. Log in or create a free account to keep your chat history." A flagged account is asked to choose a new password first.
- **History:** the first time the panel opens, it loads the shopper's saved conversation (`GET /api/chat/history`), or greets them by first name if there's none (guests get "Hi!" and this visit's messages). Logging in, out or switching accounts starts a fresh panel.
- **Search updates the page:** when a reply is a catalogue search, the site opens the Product page with all the matching cards, and the chat shows the first 3 plus **See all N on the page →**. On phones, where the panel covers the page, that button also closes the panel. Contract: `output/api_contract.md`.
- **Cards still open their product page:** checked by hand after Problem 7, as in Problem 3. A card on the chat-search results page opened the full product page. Every listing (category, all products, chat search) uses the same `ProductCard` link in `ProductsPage.tsx`, so one working card covers the rest, and the backend tests confirm each search card's id is a real product.
- **Phones:** the panel fills the screen with 16px margins.

### Look and feel (from yalebulldogblue.com)

- **Colors:** Yale Blue `#00356B` for the top bar, hero, buttons and footer; white pages; near-black text `#1D1D1D`; light gray lines and panels; teal `#046E82` saved for prices.
- **Type:** Open Sans; uppercase, semi-bold navigation and section titles.
- **Shapes:** product and category cards with thin gray borders and small 3px corners, as on the reference site.
- **Phones:** the nav collapses into a menu button under 860px wide, and there's no sideways scrolling at phone width.

### Home banner carousel (Problem 10): photos from `images/`

The banner rotates through every `.jpg` in `hw4/images/`, in file-name order. Today that's four photos:
1. mother and son on campus;
2. students at a football game;
3. Handsome Dan outside a shop;
4. three women at the School of Management.

- **Code:**
  - `src/carouselPhotos.ts` finds the photos and holds each one's screen-reader description and crop point;
  - `src/components/HeroCarousel.tsx` is the carousel;
  - `src/pages/HomePage.tsx` puts it in the banner's photo column.
- **Rotation:**
  - each photo shows for 6 seconds and cross-fades into the next;
  - it waits while the pointer is over the photos, while a control has keyboard focus, and while the browser tab is hidden;
  - it doesn't start on its own for visitors whose device asks for reduced motion.
- **Controls:**
  - previous/next arrows (wrapping around);
  - one dot per photo (the current one is filled and marked `aria-current`);
  - a pause/play button, which accessibility guidelines require for anything that moves on its own for more than 5 seconds.
- **Screen readers:** the carousel is labelled "Campus Customs photos", each photo has its own description and "1 of 4", and a new photo is announced only when the shopper changes it, never while it rotates on its own.
- **Loading:** all four photos (about 0.7 MB together) load with the page, the first one first, so no photo fades in half-loaded.
- **Layout:** the same as before. On desktop the headline panel is on the left and the photo fills the rest, cropped around each photo's focus point. Under 860px wide, the whole photo shows on top with the headline below.
- **Adding a photo:** drop a `.jpg` into `images/` and restart the dev server. If it has white bars, run `.venv/Scripts/python trim_carousel_images.py` first, which cuts plain white borders and keeps the untouched originals in `images/originals/`. Optionally add a description and crop point for it in `carouselPhotos.ts`; otherwise it gets a general description and a centered crop.
- **Prepared:** `image-4.jpg` was a square file with 224px white bars above and below. It was trimmed to 1024×576, and the original is in `images/originals/`.
- **Checks:**
  - **Build:** the front end builds and passes its code checks.
  - **Rotation and controls:** in the browser, all 4 photos load and it rotates on its own after 6 seconds. The arrows wrap in both directions (two quick clicks count twice), the dots jump to a photo, pause holds a photo past 6 seconds, and play resumes.
  - **Crops:** calculated for 1280px and 1920px windows. Every photo keeps its people and Handsome Dan in view; at 1280px the far-left student in the game photo is partly cut, and the other five faces stay fully visible.
  - **Phones (375px):** the whole photo shows, the controls fit inside it, and nothing scrolls sideways.
- **Fallback:** with no photos in `images/`, the home page shows the navy banner with a hoodie photo.
- **Clothing vs. catalogue:** the photos show Yale apparel that isn't necessarily in the catalogue (e.g. a "YALE MOTHER" quarter-zip, SOM quarter-zips). The chatbot must answer from the catalogue, never from the banner.

### Earlier banner photo: `frontend/src/assets/banner.jpg` (replaced by the carousel)

Kept for reference; the home page no longer uses it.

The banner is an image the user generated themselves: a mother and her college-bound son in Yale apparel on the Yale campus in autumn, with other visiting families behind them. The original is kept as `data/banner_user.webp` (1344×768); `banner.jpg` is a JPEG copy of it.

- **Layout:**
  - **Desktop:** the headline sits on a Yale Blue panel at left, lined up with the page content below, and the photo fills the rest of the banner.
  - **Why not text over the photo:** the mother and son fill the middle of this photo (about 13–87% across), so a text overlay would cover the mother.
  - **Crop:** checked at 900, 1280 and 1920px wide; both faces are always in view, and the crop comes mostly from the bottom.
  - **Phones (under 860px):** the whole photo sits on top, with the headline below.
- **Fallback:** if `banner.jpg` is removed, the home page shows the navy banner with a hoodie photo.
- **Clothing vs. catalogue:** the banner shows a "YALE MOTHER" quarter-zip, a Yale crest tee and a Y cap. None of these are exact catalogue items (the closest are the Yale Mom Crewneck and Basic Big Yale Hoodie). The chatbot must answer from the catalogue, never from the banner.
- **`generate_banner.py`:** an unused alternative that would make a banner from `data/banner_source.jpg` with `gpt-image-2`, a user-approved exception to the `gpt-5.6-luna` rule for this image only. It can't run yet, because the Portkey key has no image deployment.
- **After replacing the image:** restart the dev server (`npm run dev`). Vite's file watcher can miss changes in this OneDrive folder.

## Product photos: `data/data/products/`

74 of the 102 photos came with black backgrounds (45), black bars at the sides (28), or a thin black frame (1), which looked broken on the site's white cards. `fix_product_photos.py` turns that black white:

- **Only true background changes:** a pixel counts as background only if it is pure, neutral black (no blue tint) **and** connected to the photo's edge. Dark navy shadows inside a garment are never touched.
- **No leaks:** 1–2 pixel gaps in a garment's outline are closed off first, so the fill can't spill into a dark sleeve.
- **No specks:** small bits not attached to the garment (JPEG noise left in the black) count as background, so they turn white.
- **Smooth edges:** along the outline, each pixel is part garment and part black. The script compares it with the garment color just inside the outline to estimate how much is garment, then replaces the black part with white, so edges fade cleanly into white instead of leaving a dark, jagged rim.
  - **Details protected:** only pixels that look like the garment's own color darkened toward black are lightened, so real details near an edge (navy trim on a cream sweatshirt) stay as they are.
  - **Checked across all 74 photos:** 0 visibly non-white pixels remain in the backgrounds (down from 15,606), and garment interiors are unchanged (average difference 0.26 out of 255, just JPEG re-saving).
- **Originals kept:** the untouched photos are saved in `data/data/products_original/`. The script always reads from there, so it's safe to re-run, and the image paths in the database didn't change.

Run with the hw4 virtual environment (needs `opencv-python-headless`, listed in `requirements.txt`):

```bash
.venv/Scripts/python fix_product_photos.py
```
