# Product Intelligence MCP

## What this does

Product Intelligence MCP is a Model Context Protocol server that lets a Claude agent search for a product across multiple online retailers, fetch review snippets with pros and cons, save the enriched comparison data to disk, and instantly render a live comparison dashboard in your browser — all without leaving your AI assistant.

## Setup

1. **Clone / download** this repository into a local folder.

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in your keys:
   ```
   SERPAPI_KEY=your_serpapi_key_here
   UI_PORT=5050
   ```

4. **Get a SerpAPI key (free tier available):**
   - Sign up at [https://serpapi.com](https://serpapi.com)
   - Free tier includes 100 searches/month
   - Copy your API key from the dashboard into `.env`

5. **Start the MCP server:**
   ```bash
   python server.py
   ```

6. **Connect Claude Desktop** (see section below) and use the example prompt.

## No Prefab Cloud needed

The dashboard UI runs entirely on your local machine — no external API keys or cloud accounts required beyond SerpAPI. A lightweight Flask server is started automatically on `http://localhost:5050` the first time the agent calls the dashboard tool. After every product comparison the file `ui/dashboard.html` is regenerated from scratch and your browser opens automatically to show the updated results.

## Connecting to Claude Desktop

Add the following to your Claude Desktop `claude_desktop_config.json` (usually at `~/Library/Application Support/Claude/` on macOS or `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "product-intelligence": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

Replace `/absolute/path/to/server.py` with the actual absolute path to `server.py` on your system, for example:
- macOS/Linux: `/home/user/product_intelligence_mcp/server.py`
- Windows: `C:\Users\user\product_intelligence_mcp\server.py`

## Example Agent Prompt

```
Compare boAt Rockerz 450 headphones across all retailers,
save the comparison, and show me a live dashboard.
```

The agent will automatically:
1. Call `search_product` to find retailers and prices
2. Call `get_product_reviews` for each retailer to collect pros and cons
3. Call `save_comparison_to_file` to persist the data
4. Call `push_prefab_component` to generate the HTML and open your browser

## How dynamic component generation works

- SerpAPI returns N retailers per search (could be 3, could be 8 — varies by product)
- A Python loop in `prefab_client.py` generates exactly N cards in the HTML — the number is never hardcoded
- Each new search completely overwrites `ui/dashboard.html` from scratch
- No two searches produce the same UI structure; the layout adapts to however many retailers were found
- Best Value (lowest price) gets a green glow border; Top Rated gets a yellow glow border — determined at render time from the actual data

## Project Architecture

```
You ask Claude: "Compare mini LED TVs"
        │
        ▼
  server.py  ← MCP tools (the brain)
  ┌──────────────────────────────────────────────────────┐
  │  Tool 1: search_product           │──► serpapi_client.py ──► SerpAPI (Google Shopping)
  │  Tool 2: get_product_reviews      │──► serpapi_client.py ──► SerpAPI (Google Search)
  │  Tool 3: save_comparison_to_file  │──► file_manager.py   ──► saved_comparisons/*.json
  │  Tool 4: push_prefab_component    │──► prefab_client.py  ──► ui/dashboard.html
  │  Tool 5: list_comparisons         │                           + Flask server on :5050
  │  Tool 6: load_saved_comparison    │                           + webbrowser.open()
  └──────────────────────────────────────────────────────┘
```

### The 6 tools and their order of use

| # | Tool | What it does |
|---|---|---|
| 1 | `search_product` | Searches Google Shopping via SerpAPI, returns retailer list |
| 2 | `get_product_reviews` | Searches Google for reviews of that product at that retailer |
| 3 | `save_comparison_to_file` | Saves enriched data as a timestamped JSON |
| 4 | `push_prefab_component` | Generates HTML + starts Flask + opens browser |
| 5 | `list_comparisons` | Lists all past saved JSONs |
| 6 | `load_saved_comparison` | Loads a specific past JSON |

### File responsibilities

| File | Role |
|---|---|
| `server.py` | Entry point — registers all tools with FastMCP, starts the MCP server over stdio |
| `serpapi_client.py` | Fetches prices from Google Shopping and review snippets from Google Search |
| `file_manager.py` | Saves, loads, and lists timestamped JSON comparison files |
| `prefab_client.py` | Generates the HTML dashboard, runs Flask, opens the browser |

## Data Flow Summary

```
.env (SERPAPI_KEY)
     │
     ▼
serpapi_client.py ──► SerpAPI ──► Google Shopping
     │                              └── N retailer listings (price, rating, link)
     │                          SerpAPI ──► Google Search
     │                              └── review snippets per retailer
     ▼
list of dicts: [{ retailer, price, rating, pros, cons, link }, ...]
     │
     ├──► file_manager.py ──► saved_comparisons/product-name_YYYYMMDD_HHMMSS.json
     │
     └──► prefab_client.py
              ├── generate_dashboard_html()  ──► loops over N items → N cards (never hardcoded)
              ├── write_dashboard_file()     ──► ui/dashboard.html  (overwritten each search)
              ├── start_local_server()       ──► Flask on localhost:5050 (starts once, reuses)
              └── webbrowser.open()          ──► your default browser opens automatically
```

Key points:
- `best_value` (lowest price) is computed at render time → gets a **green glow** border
- `top_rated` (highest rating) is computed at render time → gets a **yellow glow** border
- The Flask server uses a `_server_started` flag so it only boots once even if you run multiple searches
- `dashboard.html` is a fully self-contained file — no CDN, no external CSS, works offline

## How to Run It

### Option A — View the already-generated dashboard (instant)

If a search has already been run, the file `ui/dashboard.html` already exists.  
Open it directly in your browser — no server needed:

```
D:\Study\tsai\product_intelligence_mcp\ui\dashboard.html
```

Or, if the Flask server is still running from a previous script run, just visit:

```
http://localhost:5050
```

---

### Option B — Run a new search as a standalone Python script

Create a file `run_search.py` in the project folder:

```python
import sys
sys.path.insert(0, ".")
from serpapi_client import search_product_prices, search_product_reviews
from file_manager import save_comparison
from prefab_client import push_comparison_dashboard

PRODUCT = "mini LED TV"   # change this to any product

results = search_product_prices(PRODUCT)
enriched = []
for item in results[:6]:
    rev = search_product_reviews(PRODUCT, item["retailer"])
    item.update(rev)
    enriched.append(item)

save_comparison(PRODUCT, enriched)
push_comparison_dashboard(PRODUCT, enriched)
```

Then run it:

```bash
# Windows — use Python 3.10+
C:\Users\tarun\AppData\Local\Programs\Python\Python310\python.exe run_search.py
```

Your browser will open automatically to `http://localhost:5050` when done.

---

### Option C — Connect to Claude Desktop (MCP mode, intended use)

**Step 1** — Find your Claude Desktop config file:

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Step 2** — Add this entry (use absolute paths):

```json
{
  "mcpServers": {
    "product-intelligence": {
      "command": "C:\\Users\\tarun\\AppData\\Local\\Programs\\Python\\Python310\\python.exe",
      "args": ["D:\\Study\\tsai\\product_intelligence_mcp\\server.py"]
    }
  }
}
```

**Step 3** — Restart Claude Desktop completely.

**Step 4** — Click the tools/hammer icon in the chat input — you should see `product-intelligence` with its 6 tools listed.

**Step 5** — Type a prompt like:

```
Compare boAt Rockerz 450 headphones across all retailers,
save the comparison, and show me a live dashboard.
```

Claude will call all 6 tools in the right order and your browser opens to `http://localhost:5050` automatically.

---

## Project structure

```
product_intelligence_mcp/
├── server.py              ← MCP server with 6 tools
├── prefab_client.py       ← HTML generator + Flask server + browser opener
├── serpapi_client.py      ← SerpAPI search + review extraction
├── file_manager.py        ← JSON save / load / list
├── ui/
│   └── dashboard.html     ← auto-generated on each search (git-ignored)
├── saved_comparisons/     ← timestamped JSON files (auto-created)
├── .env.example           ← environment variable template
├── requirements.txt
└── README.md
```
