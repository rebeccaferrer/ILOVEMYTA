# Campus Customs Shop + Chatbot

A customer-facing Yale apparel shop with an AI shop assistant. Shoppers browse the catalogue, create accounts and chat with the assistant, which **answers only from the store's live database**. It gives true prices and stock by size, puts matching items on the page, remembers returning shoppers, and offers a restock alert (with a joke) when a size is sold out.

Built for HW 4 of *AI for Managers* (Yale SOM) by Rebecca Ferrer.

## What's inside

| Part | Tech | Highlights |
|---|---|---|
| Website (`frontend/`) | React 19 + Vite + TypeScript | Yale Blue design, home-page photo carousel, product galleries with "cards per row", single-item pages with live stock, accounts, chat widget |
| API (`backend/main.py`) | FastAPI + SQLite | Products, accounts with secure passwords, chat, restock alerts, a manager-only missed-demand report |
| Shop assistant (`backend/agent.py`) | PydanticAI + `gpt-5.6-luna` (through Portkey) | 5 tools over the catalogue, a code-enforced truth check, customer memory, page context, guest chat |
| Audit trail (`output/audit_trail.json`) | Append-only JSON, hash-chained | One record per agent turn: tool calls, retries, outcome, token use |

## Repository layout

```
hw4/
├── AI_prompts.md          Every prompt used to build this, by problem, with an assessment
├── README.md
├── requirements.txt       Python packages
├── .env.example           Copy to .env and add your Portkey key
├── .gitignore
├── frontend/              React + Vite + TypeScript website
├── backend/
│   ├── main.py            FastAPI app: product, account and chat routes
│   ├── agent.py           The PydanticAI shop assistant, truth check and audit hook
│   ├── models.py          Pydantic types: tool results, the agent's reply, API models
│   ├── tools.py           The agent's tools (catalogue, stock, restock alerts)
│   ├── prompts/prompt.md  System prompt (re-read on every turn)
│   ├── auth.py, catalog.py, db.py, guest_chat.py, insights.py, audit.py
│   └── test_agent.py, test_auth.py, conftest.py   80 tests, no AI calls needed
├── output/
│   ├── harness.md         Full harness: model fields, tools, safety rules, specs, database
│   ├── design.md          Design notes (home-page carousel)
│   ├── usability.md       Usability improvements and how they help shoppers
│   ├── app_check.html     Manual site checks, with screenshots in app_check_images/
│   ├── audit_trail.json   Append-only log of agent activity
│   ├── api_contract.md    Chat search API contract
│   └── notes/             How the front end talks to FastAPI, with diagrams
├── images/                Home-page carousel photos (made with Leonardo.AI)
├── models.py, passwords.py               Shared garment types and password hashing
└── *.py (top level)       One-time data scripts: cleanup, photo fixes, descriptions, carousel trim
```

## The data pack (not in this repository)

The store's data stays local and is **not pushed to GitHub**: `data/data/campus_customs.db` (the catalogue, stock, shopper accounts and chats) and `data/data/products/` (product photos). To run the site, place the course's data pack so that you have:

```
hw4/data/data/campus_customs.db
hw4/data/data/products/<product_id>.jpg
```

The API adds its own tables (sessions, restock alerts, demand signals) on first start.

## Run it

You need Python 3.13+, Node.js 20+ and a Portkey API key with access to `gpt-5.6-luna`.

**1. Set up (once)**, from the `hw4` folder:

```bash
python -m venv .venv
```

```bash
.venv/Scripts/pip install -r requirements.txt
```

```bash
cp .env.example .env
```

Then put your key in `.env`. Next, install the website's packages:

```bash
cd frontend && npm install
```

(On macOS or Linux, use `.venv/bin/` instead of `.venv/Scripts/`.)

**2. Start the API** (terminal 1, from `hw4/backend`):

```bash
../.venv/Scripts/uvicorn main:app --reload --port 8000
```

**3. Start the website** (terminal 2, from `hw4/frontend`):

```bash
npm run dev
```

Then open **http://localhost:5174**. The website forwards `/api` and `/images` to port 8000. If that port is taken, run both with the same `API_PORT` value.

## Test it

From the `hw4` folder:

```bash
.venv/Scripts/python -m pytest backend -q
```

The 80 tests use a scripted stand-in for the AI model, a throwaway copy of the database and a throwaway audit trail, so they need the data pack but no API key. For the website (from `hw4/frontend`):

```bash
npm run build && npm run lint
```

## Useful commands

| Command (from `hw4`) | What it does |
|---|---|
| `.venv/Scripts/python backend/agent.py --trace "Do you have navy hoodies in M?"` | Chat with the assistant in the terminal and see each tool call |
| `.venv/Scripts/python backend/audit.py verify` | Check that the audit trail is intact (no record edited or removed) |
| `.venv/Scripts/python backend/insights.py make-manager <email>` | Let an account see the missed-demand **Manager report** |

## Documentation

- **[`output/harness.md`](output/harness.md):** how it all fits together: model fields and why, tools and abilities, safety rules, specs (loop limits, result caps, models), the database, the API and the website.
- **[`AI_prompts.md`](AI_prompts.md):** the prompts used to build the project, problem by problem, with what worked and what needed fixing.
