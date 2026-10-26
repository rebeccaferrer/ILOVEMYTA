# Campus Customs — Usability Improvements (Problem 9)

Five improvements: two front-end ideas from the shopper's point of view, two back-end ideas, and one fix found along the way.

| # | Improvement | Who it helps | Where |
|---|---|---|---|
| 1 | Close a product and return to the gallery | Shoppers browsing | Product page |
| 2 | Choose how many cards per row | Shoppers browsing | Every product gallery |
| 3 | "Notify me when it's back" restock alerts | Shoppers who find their size sold out | Product page, chat, site banner |
| 4 | Missed-demand report | Store managers | Manager report page |
| 5 | Footer links that match who is logged in | Everyone | Site footer |

---

## Front end

### 1. Close a product and return to the gallery

**What was added**
- A **Back to Hoodies ×** button at the top right of every product page. Its label names the gallery the shopper came from: a category, "All Products", or a chat search like "Navy hoodies".
- Pressing **Esc** does the same, except while typing or using the chat.
- The shopper returns to the **same spot** in the gallery, not the top.
- If a product was opened directly (a link, bookmark or chat card), the button goes to that product's category, e.g. "Back to T-Shirts".
- On phones it shrinks to just the × icon, and screen readers still hear "Close and go back to …".

**How it helps**
- Shoppers can look at an item and get straight back to browsing, without hunting for the category again.
- Coming back to the same scroll position means they don't lose their place in a long list, like 25 T-shirts.
- It's a familiar pattern (close an item, see the list again), so it needs no explanation.

### 2. Choose how many cards per row

**What was added**
- A **Cards per row** picker next to the item count on every product gallery: All Products, each category, and chat search results.

  | Screen | Choices |
  |---|---|
  | Laptop or desktop | Auto (about 5), 2, 3, 4, 5 |
  | Tablet | up to 3 |
  | Phone | 1 or 2 |
- The choice is remembered in the browser and applies to every gallery.

**How it helps**
- **Fewer, bigger cards:** shoppers who care about the design can see larger photos, lettering and graphics.
- **More, smaller cards:** shoppers who know what they want can scan more items at once.
- **Phones:** one per row gives full-width photos on a small screen.
- **Set once:** they don't have to choose again on each page.

---

## Back end

### 3. "Notify me when it's back" restock alerts

**What was added**
- **On the product page:** a **Notify me** button on each sold-out size. It becomes **✓ Alert on**, and clicking again cancels.
- **In the chat:** after a sold-out answer, the shop assistant asks "Want me to let you know if it's back in L?" It saves the alert only after the shopper says yes.
- **When the size is back:** a **Good news!** banner appears under the header (with **View** and ×), and the assistant mentions it once after checking the current stock.
- **Guests:** they're invited to log in or create an account, since an alert needs an account to reach them.
- **Behind the scenes:** a new `restock_requests` table and `/api/restock-alerts` endpoints. "Back in stock" is worked out live from the inventory.

**How it helps**
- A sold-out size is no longer a dead end. The shopper has a next step instead of leaving.
- Shoppers don't have to keep checking back; the site tells them.
- It's honest: the assistant only says "If the L comes back in stock, you'll see a note here on the site." It never promises a date, a hold or that it will return.
- The same alerts show in the chat and on the product page, so the shopper sees one consistent list.

### 4. Missed-demand report (for managers)

**What was added**
- **What's recorded:** the chat notes what shoppers asked for that the store couldn't supply.
  - Searches with no results, e.g. "Yale umbrellas", "pink hoodies". The assistant names the request, and code accepts it only if a search really found nothing.
  - Sold-out sizes shoppers asked about.
- **Privacy:** these are saved in a new `demand_signals` table **without names, emails or chat text**.
- **Manager report page** (footer link, managers only):
  - shows the last 7, 30 or 90 days;
  - ranks searches with no results;
  - ranks sold-out sizes by how often they were asked about and how many shoppers are waiting for an alert;
  - marks sizes that have since been restocked.
- **Who can see it:** managers are marked with a new `is_manager` flag, set with:

  ```bash
  .venv/Scripts/python backend/insights.py make-manager someone@yale.edu
  ```

**How it helps**
- Managers see real, unmet demand from the store's own shoppers: what to add to the range and which sizes to reorder first.
- It turns everyday chat questions into business data with no extra work from shoppers.
- Shoppers stay anonymous, so the report can't be used to identify anyone.
- Over time, shoppers find more of what they ask for in stock.

---

## Fix found along the way

### 5. Footer links that match who is logged in

**What was changed**

| Who's visiting | Footer "Account" links |
|---|---|
| Guest | Log in, Create account |
| Logged-in shopper | Change password, Log out |
| Manager | Change password, Manager report, Log out |

**How it helps**
- Logged-in shoppers are no longer offered "Log in" and "Create account", which was confusing.
- Useful account actions (Change password, Log out) are where people look for them at the bottom of the page.
- Managers get a direct link to their report.

---

## How each was checked

| Improvement | Checked by |
|---|---|
| 1. Back to gallery | In the browser: Hoodies scrolled 1,500px → product → **Back to Hoodies ×** returned to Hoodies at exactly 1,500px. "Back to All Products" and the direct-link fallback ("Back to T-Shirts", also via Esc) worked. On a phone it shows the × icon only. |
| 2. Cards per row | In the browser: Auto/2/3/4/5 gave 5/2/3/4/5 columns. The choice carried over to another category and survived a reload. On a phone, "1" gave a single column with no sideways scrolling. |
| 3. Restock alerts | 5 automated tests. Live with `gpt-5.6-luna`: sold-out answer → alert offered → saved after "Yes please!" → stock set back to 3 for the test → banner appeared and the assistant said "back in L, with 3 available… $58.00". |
| 4. Missed demand | 3 automated tests. Live: "Do you sell Yale umbrellas?" and "Any pink hoodies?" appeared in the Manager report with the sold-out crewneck sizes. |
| 5. Footer | In the browser: correct links as a guest and when logged in; Log out worked. |

All 74 backend tests pass, and the front end builds and passes its code checks. All test accounts and test data were removed afterwards. More technical detail is in `output/harness.md`.
