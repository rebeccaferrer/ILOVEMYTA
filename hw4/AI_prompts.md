# HW 4: Campus Customs Shop + Chatbot — AI Prompts Log

## Setup — Scenario, database check, and garment-type cleanup

**Prompts:**

> This is Homework 4: Campus Customs Shop + Chatbot.  Everything will be saved to folder: "C:\Users\rebec\OneDrive\Desktop\I LOVE MY TA DAN ROCKS\hw4"

> Yes, hw4 needs a log of prompts too.  And it's okay to build on my HW 3 code.

> Before we start with Problem 1, know the scenario: we're building a customer facing website with a chatbot.  Shoppers will browse, create accounts, chat about items, see matching items, and get true responses to questions about inventory and prices.  Check that we have a campus_customs.db

> Can you fix the messy garment types so that it is structured data?

**Assessment:** Successful. Stating the scenario up front and asking for a database check found `campus_customs.db` (102 products, stock in 6 sizes, users, chat history) and surfaced a real problem: 22 inconsistent garment-type spellings. The short follow-up prompt was enough to fix it. `normalize_garment_types.py` mapped them to 9 standard types reused from HW3, and the database now rejects anything else. The first prompt alone wasn't enough to start work, because the assignment text hadn't been shared yet.

## Problem 1 — Vibe coder prompts

**Prompts:**

> Problem 1: Vibe coder prompts. Make sure to update the AI_prompts.md file as we go along.  The log is separated into sections.  Each section header includes problem number and title.  Each section lists the prompts I give you and a brief, plain-language assessment of how successful/unsuccessful the prompts were.

**Assessment:** Successful. The prompt clearly set the log's format (sections by problem number and title, prompts word for word, and a plain-language assessment), so this file was restructured to match with no back-and-forth.

## Problem 2 — Analyze the database

**Prompts:**

> Problem 2: Analyze the database.  In the setup, you already helped structure the data for item types.  Thanks.  Analyzing campus_customs.db further, do you find anything else that need a cleaning up?  Be sure to check catalogue, inventory, and users.

**Assessment:** Successful. Naming the three tables kept the audit focused, and a read-only check of every column turned up real cleanup work. In the catalogue: 3 placeholder products with no real description or colors, product names that are just the web address turned into words ("Ua Mens Tech L S 2 0", "Creqneck"), and inconsistent color and tag spellings. In users: password hashes that don't record their settings, and email addresses where capital letters count, so one person could sign up twice. Inventory was clean apart from sizes sorting in the wrong order. The audit also showed that the "stray character" reported during setup was a false alarm: it was a curly apostrophe that the terminal couldn't display.

> Yes, apply all the recommended cleanup fixes to the database (back it up first).

**Assessment (cleanup):** Successful after one quick fix. A one-line go-ahead was enough because the audit had already listed every fix. `clean_database.py` backed up the database, then rebuilt each table:
- **Catalogue:** readable names reused from HW3, real details for the 3 placeholder products, one standard color list, consistent tags, and prices in whole cents.
- **Inventory:** sizes that sort XS → XXL, and stock that can't go negative.
- **Users:** emails that can't be duplicated by changing capital letters, and password hashes that record their settings.
- **Chat history:** saved replies now store product ids instead of old copies of prices and stock.

The database now blocks bad data on its own. **Troubleshooting:** the first run stopped because the HW3 catalogue file was laid out differently than expected; the change rolled back safely, and it worked after a one-line fix. The password settings were found by testing the Test User's known test password; the other two accounts are assumed to use the same settings.

> Thanks.   Also create a file output/harness.md that we will continue to edit.  For now in the file just list each table in the database, the fields each uses, and one short line explaining why each field is needed for the chatbot.

**Assessment (harness):** Successful. The prompt clearly set the scope ("for now", only tables, fields and one line each), so `output/harness.md` was created in one step from the cleaned database: all 7 tables, including the 3 lookup tables added during cleanup.

## Problem 3 — Build the Campus Customs website

**Prompts:**

> Problem 3: Build the Campus Customs website.  Referencing yalebulldogblue.com for aesthetic guidelines, scaffold a Reach + Vite + TypeScript front end.  The top navigation includes: Home; Product; About Us; Log In; Create Account

**Assessment:** Successful. Naming the reference site and the exact five nav items gave a clear target. The "Reach" typo was read as React. Studying yalebulldogblue.com gave concrete style rules (Yale Blue `#00356B`, Open Sans, uppercase nav, bordered cards), and the new site in `frontend/` builds, passes the code checks, and works on desktop and phone. **Troubleshooting:**
- Port 5173 was already used by the Lecture 10 app, so this site runs on 5174.
- The name fields on the sign-up form spilled past the card and needed a CSS fix.
- 73 of the 102 product photos turned out to have black backgrounds or side bars, so the home page uses only clean photos for now.

> Yes, fix the product photos so the black backgrounds and side bars become white (keep the originals).

**Assessment (photo fix):** Successful after a few tries. The prompt was specific about the goal (white instead of black) and the constraint (keep the originals). `fix_product_photos.py` saved the originals to `products_original/` and whitened 74 photos, and the site now uses all of them. **Troubleshooting:**
- The first version leaked into the dark shadow of a navy hoodie's sleeve, which shows the difficulty of telling dark garments from black backgrounds. Counting only pure, neutral black as background, and closing tiny gaps in the garment outline, fixed it.
- A contact sheet of every changed photo then caught one more case: a thin black frame, which the script now also handles.

> Can you replace the banner photo with an image generated from the attached which is of me with my 14 year son.  Make him look 18.  Place us on the Yale University campus with a lot of other visiting families.  We're both wearing apparel from the store.  He looks excited, eager to start Yale.  I look proudly at him.

> *(attached a family photo in the chat)*

> I saved the photo as hw4/data/banner_source.jpg. Go ahead and generate the banner.

**Troubleshooting (so far):** The first prompt pointed to an attachment the assistant couldn't save to disk, so it asked for the photo to be saved as a file. `generate_banner.py` then tried `gpt-5.6-luna`'s built-in image tool, per AGENTS.md, but the Azure account behind Portkey has no image deployment linked to that model; all 6 deployment names tried were "not found". Paused to ask permission before using a separate image model.

> Yes, use gpt-image-2 for the banner image only; keep gpt-5.6-luna for everything else.

**Assessment (banner, so far):** Unsuccessful so far, through no fault of the prompts. They were clear about the scene, the people and the model exception. But Portkey rejects `gpt-image-2` image edits ("Unexpected deployment name"), with both the plain and dated model names. The model list turned out to be Azure's catalog of models that *could* be deployed; the only deployment this key reaches is `gpt-5.6-luna`, which can't produce images. No image was generated. The script `generate_banner.py` is ready to run as soon as an image deployment is available.

> I'll ask my TA to add an image deployment to the Portkey key. Meanwhile, build the full-width photo banner layout so it's ready.

**Assessment (banner layout):** Successful. Asking for the layout while access is pending kept the work moving. The home page now picks up `frontend/src/assets/banner.jpg` automatically and shows it full width, with a Yale Blue fade behind the headline; on phones the photo sits above the headline. Without the file, it falls back to the old navy banner. It was tested with a temporary stand-in image at phone, 1280px and 1920px widths, and the stand-in was then removed. **Troubleshooting:**
- The phone layout seemed broken at first. The cause was the dev server missing CSS changes, since file watching is unreliable in OneDrive folders, and a server restart fixed it.
- On very wide screens the crop was moved up so faces won't be cut off.

> I decided to generate my own image for the banner.  Can you use this: *(attached image)*

**Assessment (your own banner image):** Successful. Supplying a finished image was the fastest path, since the AI access issue was outside the project. The image was saved as `frontend/src/assets/banner.jpg`, with the original kept in `data/banner_user.webp`. **Troubleshooting:**
- The pair stand in the center of this photo, not the right third the earlier layout expected, so a text overlay would have covered the mother's face. The banner became side by side: headline panel on the left, photo on the right.
- At 1920px wide the headline wrapped to four lines, so the text column now sizes itself to the headline.
- The scrollbar threw the headline 8px out of line with the content below; that was fixed too.
- Faces stay in view at 375 (phone), 900, 1280 and 1920px wide.

> On the products page, show catalogue images, it's name, price, and short description.  When an item tile is clicked, open a single-item page.  Large image on one side, full product text on the other: long description, price, sizes in stock.  Also, add a chat interface in the bottom right of the site.  It does not need to talk to the agent yet.  Start a simple FastAPI in backend/main.py to serve products and images.

**Assessment:** Successful. The prompt clearly listed what each card and the item page must show, which made it easy to build and check. Results:
- **Short descriptions:** the database had only one description, so `add_short_descriptions.py` had `gpt-5.6-luna` write a one-line short description for all 102 products from the existing text (no new claims). The full text is the long description.
- **Backend:** `backend/main.py` (FastAPI on port 8001) serves the product list, product details with stock per size, categories and photos.
- **Pages:** the Product page shows real tiles that open a single-item page.
- **Chat:** a chat widget sits in the bottom-right corner with a placeholder reply.

**Troubleshooting:**
- Port 8000 was taken by the Lecture 10 app, so the API uses 8001.
- Under several requests at once, the API returned errors: SQLite rejected a connection used across FastAPI's worker threads. Allowing that fixed it, and a test of 210 requests at once all succeeded.
- The code checker flagged a "loading" pattern that caused extra renders, and both pages were rewritten to avoid it.

> i would like smooth edges, per the last bullet point.

**Assessment:** Successful. Pointing back to the earlier note was enough context. `fix_product_photos.py` now removes stray specks and blends each edge pixel onto white according to how much of it is garment, so edges fade smoothly instead of showing a dark, jagged rim. Across all 74 fixed photos, the backgrounds went from 15,606 visibly non-white pixels to 0, and garment interiors were unchanged. **Troubleshooting:**
- The first version left a dark sliver on the coral tee: near-black pixels with a slight color cast sat just beyond the 3-pixel edge band. The band was widened to 6 pixels, with a check that only lightens pixels matching the garment's own color, so real trim is kept.
- The softening step then turned the vintage-shield tee's 1-pixel frame gray. Limiting the softening to the garment side kept backgrounds pure white.

## Problem 4 — Create account and login

**Prompts:**

> Problem 4: Create account and login.  Build  a typical create-account/ login flow.  Secure passwords to avoid human or AI hacking.

**Assessment:** Successful. "Typical flow" plus "human or AI hacking" was enough direction: it led to a standard sign-up/log-in/log-out flow plus defenses against automated and personalized guessing.
- **Passwords:** hashed with PBKDF2 at 600,000 rounds. Guessable passwords are refused, including ones built from the shopper's name, email or Yale words, and old seed hashes are upgraded at login.
- **Guessing:** lockout after 5 wrong passwords, plus limits per address.
- **Sessions:** HttpOnly session cookies, with only a hash of each token stored. Other websites are blocked from acting for a shopper.
- **Checks:** 22 attack-style tests pass, and the full flow worked in the browser. The test account was then removed from the real database.

**Troubleshooting:**
- The strength checker rated "yalebulldogs2026" and "Rebecca2026Ferrer!" as strong, because it multiplies the guesses for each piece. A second rule now requires the rest of the password to be strong without the personal or Yale words.
- A startup helper closed its database connection too early.
- The email validator rightly refused `.test` addresses, so the tests switched to `example.com`.

> Yes — add a change-password step so accounts whose password breaks the new rules must pick a new one at their next login.

**Assessment (forced password change):** Successful. The prompt named exactly who is affected and when, so the design followed directly.
- **At login:** the password is checked against today's rules (the only moment it's available in plain form), and a failing one flags the session.
- **While flagged:** the site keeps the shopper on "Choose a New Password", and shopper features answer 403.
- **The change:** it needs the current password, applies the full rules, and logs out every other device.
- **Checks:** 28 tests pass. The flow was tested in the browser with a temporary old-style account: forced to the page, bounced back when trying to leave, still flagged after a reload, changed, then returned to the page they wanted. The temporary account was deleted afterwards, and the real seed accounts were left untouched so they meet the step at their next login.
- **Troubleshooting:** only a test-script slip. It looked for "Continue" while the button displays in capitals.

> Are you putting new accounts in the users table?

**Assessment (question):** Successful. A good check question: it confirmed that sign-up writes to the existing `users` table (`backend/auth.py`), and explained why the table still shows only the 3 seed accounts (test accounts were deleted after testing; automated tests use a throwaway copy).

> As a test (or another test), log into the site with the email test@campuscustoms.yale.edu and password = password1

**Assessment (manual login test):** Successful as a test; the login itself was correctly refused. The seed Test User's stored password is a different value, so the site showed the generic "Email or password is incorrect." message and stayed on the Log In page. This counted as 1 of the 5 wrong tries allowed before the 15-minute lockout. The account and its password were not changed.

## Problem 5 — PydanticAI agent backend

**Prompts:**

> Problem 5: PydanticAI agent backend.  Now let's build the chatbot plugged into the front end.  Create it as a PydanticAI agent behind FastAPI.  The agent has the four files shown here: *(attached image listing: `backend/prompts/prompt.md` — system prompt (grow this same file later); `backend/agent.py` — agent entry / wiring; `backend/tools.py` — tools the agent can call; `backend/models.py` — Pydantic / PydanticAI structured types)*

**Assessment:** Successful. Naming the framework, the hosting (behind FastAPI) and the exact four files made the structure unambiguous. The project scenario ("true responses to questions about inventory and prices") shaped the key design: the agent can only answer from read-only catalogue tools, and code checks every reply so it can't quote a price or show a product that no tool returned.

What's in place:
- **The four files**, plus a shared `catalog.py` so the product pages and the agent read the same live data.
- **Chat API:** `POST /api/chat` and `GET /api/chat/history`, for logged-in shoppers only, rate-limited, with history saved.
- **Chat widget:** replies with product cards and history.
- **Tests:** 49 pass, including 21 new agent tests that use a scripted stand-in model.
- **Live check:** a conversation with `gpt-5.6-luna` covering stock, prices, sold-out sizes, items not sold, a fake discount, and password and ordering questions. Every answer was checked against the database.

**Troubleshooting:**
- **Content filter:** Azure blocked an "ignore your rules" message with an error. It now returns a polite refusal.
- **Fake price crash:** a made-up "$40 student price" made the model keep repeating $40 until the truth check gave up and the chat crashed. The prompt now says not to repeat shopper-suggested prices, and a safe fallback reply was added.
- **Invented feature:** the assistant pointed to a password reset that doesn't exist. The prompt now lists the site's real features.
- **Follow-ups:** "How many are left in XL?" was answered about the wrong hoodie, because history was text-only. Earlier replies now carry the ids of the cards they showed.
- **Wrong models module:** `auth.py` put `hw4/` first on Python's import path, which would load the wrong `models.py`. It's now added at the end.

> The problem instructs: In main.py expose a chat route so the website returns a reply from the agent.  Was this already done?  If not, what information do you need from me?

**Assessment (question):** Successful. A good requirement check against the assignment text. It confirmed the route already exists (`POST /api/chat` in `backend/main.py`, which calls the agent and returns its reply), is live on the running server, and is used by the chat widget. No further information was needed.

> Set up a prompts/prompt.md if you haven't already done so.  This will be updated with voice and safety basics.  Start or update types in models/py for chat replies/product cards as needed.

**Assessment (check):** Successful. Another useful check against the assignment text: both were already in place from the Problem 5 build.
- **Prompt:** `backend/prompts/prompt.md` already had voice and safety sections. The only change was renaming "Style" to "Voice" to match the assignment's wording.
- **Types:** `backend/models.py` already had the chat reply and product card types (`ShopReply`, `ChatMessageOut`, `ProductSummary`), so nothing needed adding.
- **Tests:** all 21 agent tests still pass.

> The assignment asks me to note how the front end talks to FastAPI and how the agent is loaded (prompt file + model).  Can you explain this to me?  I'm a visual learner, so perhaps a diagram will help.

**Assessment (explanation):** Successful. Saying "I'm a visual learner" led to two diagrams instead of a wall of text. The first shows the request path: chat widget → Vite proxy (5174) → FastAPI `main.py` (8001) → agent, then the reply back. The second shows how `agent.py` builds the agent from `prompt.md`, the root `.env` key, `tools.py` and `models.py`, and connects through Portkey to `gpt-5.6-luna` and read-only to the database. Each step was explained in plain language alongside them.

> Add these notes to a new file output/notes/rfnotes.md and add the diagrams as jpgs in output/notes

**Assessment:** Successful. The prompt named the exact file and folder.
- **Notes:** `output/notes/rfnotes.md` covers how the front end talks to FastAPI (5 steps), how the agent is loaded (at startup and on every message), and a quick-reference table.
- **Diagrams:** `frontend-to-fastapi.jpg` and `agent-loading.jpg` are embedded in the notes. **Troubleshooting:** the chat diagrams use colors that depend on the chat's light/dark theme, so they were redrawn as standalone pages with fixed colors and a title, then rendered by Edge in headless mode at double resolution (1360px wide) and saved as JPGs.

> The last part of problem 5 is to make sure the backend runs form the backend/ folder like this:
> uvicorn main:app --reload --port 8000
> But, I have my doubts about this line.  I thought you created another port.  Help me understand, please.

**Assessment (question):** Successful. The doubt was justified and caught a real mismatch.
- **The command works:** run from `backend/`, it starts the app (tested on spare port 8002: health, products and chat all answered).
- **But not on 8000:** port 8000 is taken by the Lecture 10 backend, which is why HW4 has been on 8001.
- **The website would break:** its forwarding rule points to 8001, so a backend started on 8000 wouldn't be reached.
- **Next step:** proposed switching HW4 to the assignment's port 8000.

> Yes, switch HW4 to port 8000 to match the assignment: update the Vite forwarding, main.py, launch settings and notes, and stop the Lecture 10 backend that's using 8000.

**Assessment (so far):** Partly successful. All the HW4 changes are done:
- **Vite forwarding:** goes to port 8000 by default, or to `API_PORT` if set.
- **`main.py`:** defaults to 8000 and documents the assignment's command.
- **Launch settings:** run `uvicorn main:app --app-dir hw4/backend --port 8000`.
- **Notes and harness:** updated, and the request-path diagram JPG was re-rendered with 8000.
- **Checks:** the front end builds cleanly.

**Troubleshooting:** the Lecture 10 backend was stopped, but about a minute later the separate "Lesson 10: AI for Managers" Claude session restarted it on 8000. The assignment's command then failed to start (Windows error 10013: port in use), and the website's requests reached the Lecture 10 (Harry Potter) app instead. Paused to let the user decide how to free port 8000, rather than repeatedly stopping another session's server.

> I archived Lesson 10.

**Assessment (port 8000, finished):** Successful.
- **Freeing the port:** archiving the Lesson 10 session ended that session, but its Lecture 10 server kept running, left behind. With nothing left to restart it, it was stopped, and port 8000 stayed free for a full minute.
- **The assignment's command:** `uvicorn main:app --reload --port 8000`, run from `backend/`, started HW4 with auto-reload. Through the website it showed all 102 products with photos, the chat refused logged-out shoppers, and a temporary account got a real agent reply ("$68.00" plus a product card).
- **Cleanup:** the test account was deleted, the test server and its reload helper were stopped, and the backend was restarted from the launch settings on 8000.
- **Tests:** all 49 backend tests pass.

## Problem 6 — Tools: product info and stock

**Prompts:**

> Problem 6: Tools: product info and stock.  Now we have to give the agent tools that look up real info from campus_customs.db and the agent uses the db.  It cannot invent information.  If an item is out of stock. the agent replies with something funny.

**Assessment:** Successful. Most of this problem was already built in Problem 5: four read-only tools (`search_products`, `get_product_details`, `check_stock`, `list_categories`) query `campus_customs.db` live, and code rejects any reply that quotes a price or shows a product no tool returned. The new part was the funny sold-out reply, and the prompt's two rules pulled against each other: be funny, but invent nothing.
- **How both rules hold:** `check_stock` now returns a `sold_out_quip` whenever a size is at 0, chosen from 7 Yale-themed jokes written in code (e.g. "That size graduated early: summa cum sold out."). The jokes contain no prices, dates or promises.
- **Prompt:** a new "Sold out? Make them smile" section says to open with one joke, then state the real sizes in stock. It forbids jokes that hint at restocks, holds, waitlists or discounts, and any joke when the item is in stock.
- **Tests:** 50 pass, including a new one that checks the jokes only appear for sold-out sizes and state no facts.
- **Live check with `gpt-5.6-luna`:** for the Champion Reverse Weave crewneck in XS (0 in the database), it opened with a Sterling Library joke and then correctly said only M and XL are in stock. A follow-up got the right price ($58.00) and medium stock (12), with no joke. "Yale umbrellas" got an honest "we don't carry those". Every answer matched the database.

> Now expand prompts/prompt.md so the agent knows to call the tools for price and stock questions... add or update return types in models.py and then in the harness, list each tool and explain which model fields you chose for lookup and why.

**Assessment (tool rules, return types, harness):** Successful. The prompt named three clear deliverables, one per file.
- **`prompt.md`:** "Using the tools" now opens with a rule: call a tool before every answer that mentions a price or stock, even for an item that came up a moment ago. It maps each kind of question to a tool ("how much?", "is it in M?", "what sizes are left?", "under $60", "what do you sell?", comparisons). It also says what to do when a tool reports an error, and to say "I can't check right now" rather than estimate.
- **`models.py`:** `StockCheck` gained `price`, so "how much, and is it in medium?" takes one call. `ProductMatch` gained `sold_out_sizes`. Fields that lacked descriptions now have them, and a note explains that the model sees field names and values (not descriptions), so names were chosen to be self-explanatory.
- **Harness:** a new section lists each lookup field (`product_id`, `garment_type`, colors, `price_cents`, size, quantity, the text fields) and why it was chosen, then each tool with its return type and fields. It also lists which columns are left out on purpose.
- **Checks:** 51 tests pass, including a new one for `sold_out_sizes` and the price in `check_stock`. Live with `gpt-5.6-luna`, every price and stock number matched the database.

**Troubleshooting:** this also fixed the slow sold-out lookup noted in the last assessment. The `size` filter hid items that are sold out in that size, so the prompt now says to search without it and then call `check_stock`. The "Champion crewneck in XS?" question dropped from 4 tool calls to 2.

## Problem 7 — Chat search that updates the page

**Prompts:**

> Problem 7: Chat search that updates the page. Make an API contract. When a consumer asks about a type of item, the agent should search the catalog and the website should show those matching items as product cards. Include things like image, name, price, and short description.

**Assessment:** Successful. The prompt named the trigger (a shopper asking about a *type* of item), the result (the website shows the matches as product cards) and the card fields (image, name, price, short description). That was enough to design the contract without questions. The one choice it left open was where the cards go. They already appeared small inside the chat, so "updates the page" was read as the Product page itself.
- **Contract:** `output/api_contract.md` defines it end to end. The agent's answer (`ShopReply`) gained `search_title`, which is set only for a catalogue search, with up to 12 `product_ids`. The chat reply (`ChatMessageOut`) gained `search: {title, products}`, using the same product card as the Product page. Code enforces the rules: only tool-returned ids, no made-up prices even in the title, and an empty search never blanks the page.
- **Prompt:** "Showing products" now explains the two modes: a catalogue search (every result goes on the page, with a brief message) or an ordinary reply (up to 6 cards in the chat).
- **Website:** a search reply opens `/products?chat=<id>` with a "Shop Assistant results" label, the agent's heading and the cards. The chat shows a 3-card preview and a **See all N on the page →** button. Reloading the page rebuilds it from saved chat history with current prices. The `search_title` column was added to `chat_messages` at startup.
- **Checks:** 55 backend tests pass (5 new), and the front end builds and passes its code checks. In the browser with `gpt-5.6-luna`, "Show me navy hoodies" opened the page with 12 cards, all real navy hoodies; the agent said 23 matched, which the database confirms. "Any hockey T-shirts?" on a phone found both hockey tees at $32.00. "Is the Basic Big Yale Hoodie in XL?" kept the page as it was and answered "2 available, $68.00", also correct. The temporary test account was deleted afterwards.

**Troubleshooting:** only small things. The shell couldn't parse one long inline edit script, so it was saved as a file and run. The first draft of the results page lost its heading after a reload, so the heading and the cards now come from the same lookup.

> I manually checked one product card to make sure it still opens (like we did in Problem 3).  I clicked on a card and it correctly opened to full product page.  Do you need to run this test in another way?  If so, please do.  If not, just update my prompt and harness files.

**Assessment (manual check):** Successful. The hands-on test confirmed that the new search page didn't break the link from a card to its product page. No extra automated test was needed. All three listings (all products, one category and a chat search) build their cards from the same `ProductCard` link, so one working card shows they all work. The backend tests already check that every search card is a real product with a working photo. The question was worth asking: it confirmed the check was enough and avoided running a duplicate test.

## Problem 8 — Customer memory

**Prompts:**

> Problem 8: Customer memory.  Make sure the agent knows which shopper is chatting (based on their login) and save their chat history in the database in a table.  When they return, the agent should reload the chat history.

**Assessment:** Successful. The prompt listed three requirements. A check showed the first two were already built in Problem 5:
- **Which shopper:** the chat route identifies the shopper from their login cookie and passes the agent their first name.
- **Saved history:** every message is saved in the `chat_messages` table.

The third requirement, reloading history on return, was only half done. The last 20 messages were reloaded, but the agent couldn't tell when they were sent. To it, a shopper back after a week looked the same as one who never left. What was added:
- **Agent:** each turn now passes the number of saved messages and the time of the last one. The agent is told whether this is a first conversation, an ongoing one, or a return after a break of more than 2 hours.
- **Prompt:** a new "Memory" section. Know the shopper from the login only, use what they said before (sizes, colors, items), welcome a returning shopper back once, and look up prices and stock again, because memory is not stock.
- **Chat panel:** saved messages now sit under day dividers, with a "Welcome back, <name>!" line where the new visit begins.
- **Checks:** 57 backend tests pass (2 new), and the front end builds and passes its code checks. The new test has one shopper log out and return 3 days later, with another shopper chatting in between: each gets only their own history. Live with `gpt-5.6-luna`, a temporary shopper said their son wears a medium and loves hockey. Three days later (moved back in the database), "Any other hockey shirts in his size?" got "Welcome back, Pat!" and a medium-size result that the database confirms (25 in stock). The account was deleted afterwards.

**Troubleshooting:** only one style fix. The welcome-back line used the same gray as the chat background, so it was invisible, and it now uses white with a thin border.

> to pass enough page context so that if someone is on a product page and asks, hey, do you have this in pink? the agent knows which item they mean. What does my professor mean by page context? Is this something that I have to do manually, or is this something that you can test?

**Assessment (question):** Successful. A good question to ask before building: it turned up a real gap. The chat sends only the message text, so on a product page the agent can't tell what "this" means. "Page context" means the website also sends which page the shopper is viewing (for example the product's id) with each message, so the agent can look that item up. It can be built and tested automatically (tests plus a browser check); nothing has to be done by hand.

> Yes, build the code.  This is still part of Problem 8.

**Assessment (page context):** Successful. Asking "what does this mean?" first paid off: by the time of the go-ahead, the gap and the plan were clear.
- **Website:** the chat now sends the page with every message (its address, plus the product id on a single-item page).
- **Backend:** the page data is checked against the database before the agent sees it. A product id is kept only if the product exists, a category only if it's real, and any other text in the address is dropped, so a tampered address can't slip instructions to the agent. The agent then gets one line saying which product the shopper is viewing.
- **Prompt:** a new "Page context" section says what "this" means and how to answer "this in another color" (each product comes in one color, so it searches the same kind of item in that color) and "this in a large".
- **Checks:** 64 backend tests pass (7 new), and the front end builds and passes its code checks. Live with `gpt-5.6-luna`, on the Basic Big Yale Hoodie page, "hey, do you have this in pink?" got "only in navy… not pink" plus the one coral item, the Big Yale Tri-Blend T-Shirt, with its correct sizes. On the Champion crewneck page, "Do you have this in a large?" correctly said L is sold out and M and XL are in stock. The temporary test account was deleted.

**Troubleshooting:** one new test failed at first because it checked that the words "made-up" never appeared in the agent's instructions, and the prompt itself uses that phrase. The test now checks for the fake product id specifically. Planning also caught a security gap before it shipped: the first draft passed the address's category text straight to the agent.

> I tried chatting with the agent, but it didn't respond.  It told me to log in.  Is it possible to allow a guest to chat and keep the chat history just for logged-in users?

**Assessment (guest chat):** Successful. Trying the site as a real visitor caught a design gap: since Problem 5 the chat had required a login, which made sense for saving history but shut out casual shoppers. The prompt said clearly what to keep (history for logged-in users only), so the design followed directly.
- **Guests:** they can now chat. Their conversation is kept only in the server's memory for the visit, so the agent can follow it, and it's never written to the database. It's forgotten 2 hours after their last message.
- **Logged-in shoppers:** they keep the saved history and welcome-back from Problem 8. Logging in drops any guest chat instead of copying it into the account.
- **Abuse protection:** since anyone can now use the AI, guests have their own message limits, per browser and per network address.
- **Prompt:** the agent knows when it's talking to a guest. It uses no name and explains that saving needs a free account only if they ask about being remembered.
- **Chat panel:** guests see a short note with Log in / create a free account links.
- **Checks:** 67 backend tests pass (4 new guest tests replace the old "login required" test), and the front end builds and passes its code checks. Live, a logged-out visitor on the hoodie page asked "hey, do you have this in pink?" and got a true answer, based on the product's own description. The database's chat table didn't change, and the guest chat survived a page reload during the visit.

**Troubleshooting:**
- One new test failed because the phrase it looked for ("first name is") also appears in the prompt's own wording, and the test was made more exact.
- The code checker flagged a React warning in the first version of the panel change, and it was restructured.
- The browser pane was too small for a readable screenshot, so the layout was checked at real phone size (375×812) instead.

## Problem 9 — Usability improvements

**Prompts:**

> Problem 9: Usability improvements.  I have 2 ideas for improvements on the front end.  1- As a shopper in the full product view, I would like a way to X out or return to my sub category.  2- When in any gallery view, I would like the option of changing how many cards I see in one view.  I don't have any ideas for back-end improvements... can you propose 2 ideas?

**Assessment:** Successful for both front-end ideas. Each was described from the shopper's point of view ("as a shopper in the full product view…"), which made the goal clear. Two details had to be decided:
- **"Return to my sub category":** it now returns to the gallery the shopper actually came from, *at the same scroll position*. A check showed that a plain "back" link would have dropped them at the top of a long gallery.
- **"How many cards I see in one view":** read as cards per row (Auto, 2–5 on wide screens, 1–2 on phones), remembered between visits.

**Results:**
- **Product page:** a **Back to <gallery> ×** button, also reached with Esc.
- **Galleries:** every product gallery has a **Cards per row** picker.
- **Checks:** the front end builds and passes its code checks. In the browser, closing a product returned to the right gallery and scroll position, and each per-row choice gave the right number of columns on desktop and phone.

**Troubleshooting:**
- The first version recorded the scroll position when a card was drawn rather than when it was clicked, so it would have been wrong. It now records it at the click.
- One CSS rule made the phone's "1 per row" option show 2. The rule order was fixed.

**Back-end ideas proposed (not built yet; waiting for the shopper's choice):**
1. **"Notify me when it's back."** When a size is sold out, the chatbot (or the product page) can offer to remember the request. A `restock_requests` table stores the shopper, product and size. When stock is updated, waiting shoppers see "Good news: it's back in M" at their next visit. This turns a sold-out moment into a future sale, and it tells the store which sizes to reorder.
2. **Missed-demand report.** Record, without names, what shoppers asked for that the store couldn't supply: searches with no results ("umbrellas", "pink hoodie") and sold-out size checks. A manager-only report then ranks the top unmet requests. It uses data the chatbot already sees, and it's a manager's view of what to stock next.

> Build both back-end ideas.

**Assessment (back-end ideas):** Successful. "Build both" was enough because the proposals had already spelled out what each one does.
- **Restock alerts:**
  - a `restock_requests` table and three endpoints;
  - a **Notify me** button on sold-out sizes;
  - a "Good news!" banner when stock returns;
  - an agent tool (`request_restock_alert`) that the agent uses only after offering and hearing a yes. It's the only tool that saves anything, and only for the logged-in shopper.
- **Missed-demand report:** an anonymous `demand_signals` table, filled from the chat (searches with no results, and sold-out sizes asked about), plus a managers-only **Manager report** page. Managers are marked with a new `is_manager` flag, set by a one-line command.
- **Checks:** 74 backend tests pass (8 new), and the front end builds and passes its code checks. Live with `gpt-5.6-luna`, the whole loop worked end to end:
  - sold-out answer → alert offered → saved after "yes";
  - stock returned → banner, and the agent shared the good news with correct numbers;
  - "Yale umbrellas" and "pink hoodies" showed up in the manager report.

  All test data was removed afterwards.

**Troubleshooting:**
- The first live test showed the "no results" rule missed real requests. The agent searched "umbrella" (nothing), then searched for alternatives, which found items. The fix lets the agent name what the shopper wanted (e.g. "Yale umbrellas"), and code only accepts it when a search that turn really found nothing.
- One new test failed because test accounts were deleted without the database's foreign-key enforcement turned on, so their alerts stayed behind. The test setup now removes them.

> Yes, fix the footer links too.

**Assessment (footer):** Successful. A one-line go-ahead was enough, since the problem had been described in the previous reply. The footer's Account links now depend on who is visiting:
- **Guests:** Log in and Create account.
- **Logged-in shoppers:** Change password and Log out, plus Manager report for managers.

The front end builds and passes its code checks. In the browser, the footer showed the right links as a guest and when logged in, and its Log out button logged the shopper out and returned to the home page. The temporary account was deleted.

> Summarize all these usability improvements in a output/usability.md file.  List what was added and how it helps the user.

**Assessment (summary):** Successful. The prompt named the file and the two things each entry needs ("what was added" and "how it helps the user"), so `output/usability.md` follows that structure for all five Problem 9 improvements:
- the two front-end ideas;
- the two back-end ideas;
- the footer fix.

It opens with an overview table and ends with how each improvement was checked.

## Problem 10 — Style the website

**Prompts:**

> Problem 10: Style the website. Instead of showing one static image, create a carousel on the home page rotating between the jpgs in the images/ folder.

**Assessment:** Successful. The prompt named the folder and the behavior ("rotating between the jpgs"), so the carousel reads `images/` directly: adding a JPG there adds it to the rotation.
- **Carousel:**
  - 6-second cross-fades;
  - arrows, dots and a pause button;
  - pauses on hover, keyboard focus or a hidden tab;
  - no auto-rotation for reduced-motion users;
  - screen-reader descriptions for each photo.
- **Layout:** the same as the earlier banner (headline panel left, photo right; photo on top on phones).
- **Checks:** the front end builds and passes its code checks. In the browser, every control worked, all photos loaded, and the phone layout fit. A contact sheet of the calculated crops at 1280px and 1920px showed every photo keeps its people (and Handsome Dan) in view.

**Troubleshooting:**
- **White bars:** `image-4.jpg` was a square file with white bars above and below the photo, which would have shown as white strips. `trim_carousel_images.py` trimmed them and kept the original in `images/originals/`. Its first run printed an arrow character the Windows terminal couldn't display, which was fixed.
- **Lazy loading:** photos 2–4 were lazy-loaded and hadn't loaded when the first rotation happened, so all four now load with the page.
- **Rapid clicks:** two quick "previous" clicks only moved back one photo, because both read the same position. Each click now steps from the latest photo.
- **Code checker:** the photo list moved to its own file, as the checker asked.
- **Screenshots:** the browser pane couldn't show a full 1280px page, so crops were checked by calculating exactly what each photo shows at each window size.

> In output/design.md write a summary that explains a carousel was added to include a diversity of students and other potential customers.  Images were created using Leonardo.AI website.  Of course Handsome Dan had to make an appearance somewhere.

**Assessment (design summary):** Successful. The prompt gave the file, the main message (diversity of students and other potential customers), the image source (Leonardo.AI) and a fun detail to include (Handsome Dan). `output/design.md` covers:
- why the carousel replaced the single photo;
- a table of the four photos and who each one speaks to (families, current students and fans, everyone via Handsome Dan, and graduate/professional students and alumni);
- the design and accessibility details;
- a short note that the AI-generated photos aren't product shots, so true details come from the catalogue.

## Problem 11 — Site testing (app check)

**Prompts:**

> Problem 11: Site testing (app check).  Open the live site so I can run a few manual checks.

> Create a folder output/app_check.html to document that I manually checked 1, that I can create a new account, 2, that I can interact with the chat bot and get inventory levels and dynamic search result cards, and 3, that one of the usability features (that the search card closes) does indeed work.  Do you want me to provide screenshots?

**Assessment (so far):** Successful. The prompt listed the three checks clearly. "Create a folder output/app_check.html" was read as both:
- a page, `output/app_check.html`;
- a folder for its screenshots, `output/app_check/`.

The page records the tester, date and setup, a summary table, and for each check the steps, expected result, outcome (passed, as confirmed by the user) and two screenshot slots. Until a screenshot file is added, its slot shows a dashed placeholder with the exact file name to use. Answering the question: yes, screenshots are recommended as evidence for a manual check.

> I saved the screenshots in output/app_check, but my professor wants them in output/app_check_images/ and also linked from the html with relative paths.

**Assessment (screenshots):** Successful. The prompt stated the professor's two requirements (the folder `output/app_check_images/` and relative links), and the page now meets both.
- **The five screenshots:** copied into `output/app_check_images/`. Each is shown on the page with a relative path (`app_check_images/…`), and clicking one opens it full size. A script confirmed that every link resolves.
- **Check-2 duplicate:** the two check-2 files turned out to be the same picture (one was saved as `.png.png`). That one screenshot already shows both the chat's inventory answer and the search card, so it's used once, as `2-chat-search-cards.png`.
- **Steps and results:** rewritten to match what the screenshots actually show (a School of Management search), and the reply was checked against the database: $32.00, XL 0, L 2, and the only School of Management product. All of it matched.

**Troubleshooting:** removing the old `output/app_check/` folder was blocked as a destructive step, so the files were copied instead. The old folder can be deleted by hand.

## Problem 12 — Audit trail, safety, finish harness

**Prompts:**

> No need.  Let's move on to Problem 12: Audit trail, safety, finish harness.  The instruction is to keep an append-only output/audit_trail.json of agent-loop activity and not wipe it between runs.  Is this something you can do?

**Assessment (audit trail):** Successful. The instruction was precise (append-only, `output/audit_trail.json`, agent-loop activity, never wiped between runs), so the main design questions were how to make "append-only" real and what to leave out.
- **What's recorded:** each chat turn records the agent loop step by step:
  - model responses (with the model version);
  - tool calls with their arguments, and summarized tool results;
  - truth-check retries with the reason;
  - anything saved, such as restock alerts;
  - the outcome and the token usage.
- **Append-only:** the file stays a JSON list, like the course's Lecture 5 log. But new records only replace the closing `]`, and the file is never reset. Lecture 5's pattern started a new list whenever the file couldn't be read, which could wipe it.
- **Tamper evidence:** a SHA-256 hash chain, plus a `verify` command, reveals any edited or deleted record.
- **Privacy:** shoppers' messages aren't stored, only their length, because guests were promised their chats aren't saved.
- **Checks:** 80 backend tests pass (6 new), and tests write to a throwaway trail. Live, two real turns were recorded. A third, after a server restart, continued the trail as record 3 with the chain intact.

**Troubleshooting:** two details found while building it. The captured messages include the earlier chat history, so only the new turn's messages are logged. And a turn that errors is still recorded (outcome `error`) before the 502 goes back to the shopper.

> Yes, complete the harness with the following info:
> *(attached image listing: Model fields in `models.py` and why you chose them; Tools and abilities; Safety rules; Specs (loop limits, result caps, models, how to run front + back))*

**Assessment (finishing the harness):** Successful. The four headings in the attached list became a new "Harness summary" at the top of `output/harness.md`, so a reader finds them first, and the existing problem-by-problem sections stay below as the detail.
1. **Model fields:** every field of `ShopReply`, the tool results, `ShopDeps` and the API models, each with why it was chosen, plus what was left out on purpose.
2. **Tools and abilities:** the 5 tools (which read and which write), plus the abilities built around them.
3. **Safety rules:** grouped as truthfulness, privacy, prompt injection and tampering, accounts, cost and abuse, and accountability.
4. **Specs:**
   - the models, with their uses and the one image exception;
   - the loop limits (8 model requests, 15 tool calls, 2 retries, 20 history messages);
   - every result cap;
   - how to run the back end (port 8000) and the front end (port 5174), with tests and helper commands.

Every number was taken from the code rather than from memory. The pass also fixed stale lines: the prompt's section list (now 11 sections), the test count (80 now, not 21), and "login required" (guests can chat since Problem 8).

## Problem 13 — Push to a public GitHub

**Prompts:**

> Problem 13 is the last step and it is to push it to a public GitHub, but I don't think I have everything in my hw4 folder.  What am I missing from the expected file layout:
> *(attached image of the expected layout: hw4/ with AI_prompts.md, requirements.txt, .env.example, .gitignore, README.md, frontend/, backend/ (main.py, agent.py, models.py, tools.py, prompts/prompt.md), output/ (harness.md, design.md, usability.md, app_check.html, app_check_images/, audit_trail.json))*

> I think hw4 should go into a new repo of its own.  the data pack (campus_customs.db and products/) stays local only and should not be pushed to git.  Do create the missing files.

**Assessment (missing files):** Successful. The prompt settled the two open questions (a new repo of its own; the data pack stays local), so the three files followed directly.
- **`README.md`:** what the project is, the repository layout, how to place the local data pack, setup and run steps for the back end (port 8000) and the website (port 5174), tests, useful commands, and links to the harness and prompt log.
- **`.env.example`:** a placeholder `PORTKEY_API_KEY`, with no real key.
- **`.gitignore`:** keeps `.env` and the whole `data/` folder local. That folder holds the database (with shopper accounts and chats), its backups, the product photos and the private banner source photo. The file also excludes `*.db`, `*.zip`, `.venv`, `node_modules`, the build folder, test caches and the old `output/app_check/` folder.
- **Check:** a dry run showed 86 files would be committed, none from the data pack.

**Troubleshooting:** making `hw4` its own repo exposed a problem. The code only read `.env` from the course folder above `hw4`, which wouldn't exist for someone downloading the repo. The backend and both AI scripts now read `hw4/.env` first and still fall back to the course folder. All 80 tests pass, the front end builds, and the key still loads.

> Please check that I correctly created the repo: https://github.com/rebeccaferrer/campus-customs

**Assessment (repo check):** Not yet successful, though the check itself worked. The link returns "Repository not found" (404), and the account's public repositories are only `ILOVEMYTA` and `yale-som-virtual-tour`. So `campus-customs` either hasn't been created yet, or was created as **private**, which hides it from anyone not logged in, including this check. Asking for a check before pushing caught this early.

> I made it public, please check again

**Assessment (repo check, second try):** Successful. `rebeccaferrer/campus-customs` is now public and empty (no branches yet), which is right for a first push.
- **Course repo:** `hw4/` was added to the course repo's `.gitignore`, so the two repositories don't overlap.
- **New repository:** `hw4` was set up as its own repository.

**Troubleshooting:** staging the files was stopped by Git's "dubious ownership" safety check. The `hw4` folder is owned by a different Windows account (`CodexSandboxOffline`) than the user's (`rebec`), and Git won't work in a folder owned by someone else until its owner approves it. That approval is a security setting, so it was left for the user to run.

> Maybe hw4 shouldn't be it's own repo.  Let's go back to the original.

**Assessment (back to the course repo):** Successful. "Go back to the original" was clear, and nothing had been committed, so everything was undone with nothing lost:
- **Course repo:** `.gitignore` was restored byte for byte, after a first restore had changed its line endings.
- **The separate repository:** the empty `hw4/.git` folder (no commits or files) was removed. On the first try Windows reported it busy, and a second try worked.

`hw4` is a normal folder in the ILOVEMYTA course repo again. Its own `.gitignore` still applies there: a dry run shows 86 files would be added, with no data pack, `.env`, `.venv`, `node_modules` or build files. The empty `campus-customs` repo on GitHub is unused and can be deleted on GitHub.

> Yes, commit just the hw4 folder

**Assessment (commit):** Successful. The prompt was specific ("just the hw4 folder"), so only `hw4/` was staged. `Lecture 7/`, `Lecture 10/` and `.claude/` were left out. The staged list was checked before committing: 86 files, all inside `hw4/`, none from the data pack, `.env`, `.venv`, `node_modules` or the build. The commit went to the ILOVEMYTA course repo's `main` branch; pushing it to GitHub is left to the user.

> I pushed it, please check that everything arrived

**Assessment (push check):** Not successful yet, though the check worked. GitHub's ILOVEMYTA repo was still empty. The terminal showed three push attempts, each failing partway through a single ~100 MB upload ("RPC failed… Connection was aborted", "unable to rewind rpc post data", then "the remote end hung up"). The closing "Everything up-to-date" line was misleading. hw4 is only about 3 MB of that upload; the rest is from the earlier, never-pushed course commit, mostly 83 MB of `Lecture 6` videos and a 15 MB hw3 video.

**Suggested fixes:** first raise Git's upload buffer for this repository (`git config http.postBuffer 524288000`) and push again. If that still fails (a `SEC_E_MESSAGE_ALTERED` error hints at network or security-software interference), try another network, or remove the lecture videos from the unpushed commit to shrink the upload to about 20 MB.

> I pushed again after the postBuffer fix, please check

**Assessment (second push check):** Not successful yet, but the cause was found. GitHub was still empty, and the terminal showed the same mid-upload failure. Checking Git's settings showed the fix had never taken effect: `http.postBuffer` wasn't set for the repository or the account, and the terminal history had no `git config` command. Since the user meant to apply it, it was set on the course repo (`git config http.postBuffer 524288000`), confirmed in `.git/config`, and the user was asked to push once more. If that also fails, the next step is removing the 83 MB of lecture videos from the unpushed commit, or trying another network.

> At this point, I'm really frustrated.  I don't care about what prior Lecture material is pushed to git.  The lecture stuff doesn't make sense to me.  I just need to get hw4 up so that I can finish already.  This has taken all day.

**Assessment (hw4-only push):** The prompt made the priority clear: get hw4 onto GitHub and drop everything else. The earlier attempts kept failing because the first push also carried the never-pushed course commit (about 100 MB, mostly lecture videos). The fix sent GitHub a commit containing only the `hw4/` folder (about 3 MB), built from the committed hw4 files without changing any local files or commits.

