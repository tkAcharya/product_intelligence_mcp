# Product Intelligence MCP

## What this does

Product Intelligence MCP is a Model Context Protocol server that lets a Claude agent search for a product across multiple online retailers, fetch review snippets with pros and cons, save the enriched comparison data to disk, and instantly render a live comparison dashboard in your browser — all without leaving your AI assistant.

The dashboard is built with **[Prefab](https://prefab.prefect.io)** — a reactive Python UI framework. The page stays open indefinitely. When a new search runs, the browser updates the cards in-place with no page reload.

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
   Open `.env` and fill in your key:
   ```
   SERPAPI_KEY=your_serpapi_key_here
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

## How the UI works

### Initial load
When the agent calls `push_prefab_component` for the first time:

1. Comparison data is written to `ui/current_comparison.json`
2. `prefab_app.build_html()` generates a self-contained HTML page using Prefab components (`ForEach`, `If`, `Rx`, `Card`, `Badge`, `Link`, etc.) with the latest data baked in as initial state
3. The page also contains a `SetInterval` action that calls `GET /api/data` every 3 seconds
4. A Flask server starts on `http://127.0.0.1:5175` serving two routes:
   - `GET /` — the cached Prefab HTML page
   - `GET /api/data` — the live JSON endpoint
5. Your browser opens to `http://127.0.0.1:5175`

### Live updates (no page reload)
On every subsequent search the agent runs:

1. New comparison data is written to `ui/current_comparison.json`
2. The cached HTML is rebuilt with the new initial state
3. The browser page that's already open polls `GET /api/data` within 3 seconds
4. The Prefab React runtime receives the new data, calls `SetState("data", result)`, and re-renders only the changed components — `ForEach` rebuilds the card list, `If` toggles the badges, `Rx` text nodes update — **the tab never reloads**

### Why this is different from a static HTML approach
The old approach generated a raw HTML string with a Python loop and served it via Flask. Each new search replaced the entire file and the user had to refresh.

The new approach generates HTML once using Prefab's component tree (`ForEach`, `If`, `Rx`). The React runtime embedded in that page owns the live DOM. Updates flow through the reactive state system — only the components whose data changed are re-rendered.

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

Replace `/absolute/path/to/server.py` with the actual absolute path on your system.

## Example Agent Prompt

```
Compare boAt Rockerz 450 headphones across all retailers,
save the comparison, and show me a live dashboard.
```

The agent will automatically:
1. Call `search_product` to find retailers and prices
2. Call `get_product_reviews` for each retailer to collect pros and cons
3. Call `save_comparison_to_file` to persist the data
4. Call `push_prefab_component` to build the Prefab UI and open your browser

Run another comparison while the tab is open — the cards will swap out within 3 seconds.

## Project Architecture

```
You ask Claude: "Compare mini LED TVs"
        │
        ▼
  server.py  ← MCP tools
  ┌──────────────────────────────────────────────────────────────────┐
  │  Tool 1: search_product          ──► serpapi_client.py ──► SerpAPI (Shopping)
  │  Tool 2: get_product_reviews     ──► serpapi_client.py ──► SerpAPI (Search)
  │  Tool 3: save_comparison_to_file ──► file_manager.py   ──► saved_comparisons/*.json
  │  Tool 4: push_prefab_component   ──► prefab_client.py
  │  Tool 5: list_comparisons        │        │
  │  Tool 6: load_saved_comparison   │        ▼
  └──────────────────────────────────┘  writes current_comparison.json
                                         builds Prefab HTML (prefab_app.py)
                                         starts Flask on :5175
                                         opens browser
```

### The 6 tools and their order of use

| # | Tool | What it does |
|---|---|---|
| 1 | `search_product` | Searches Google Shopping via SerpAPI, returns retailer list |
| 2 | `get_product_reviews` | Searches Google for reviews of that product at that retailer |
| 3 | `save_comparison_to_file` | Saves enriched data as a timestamped JSON |
| 4 | `push_prefab_component` | Builds Prefab HTML, starts server, opens browser |
| 5 | `list_comparisons` | Lists all past saved JSONs |
| 6 | `load_saved_comparison` | Loads a specific past JSON |

### File responsibilities

| File | Role |
|---|---|
| `server.py` | MCP entry point — registers all 6 tools, runs over stdio |
| `serpapi_client.py` | Fetches prices from Google Shopping and review snippets from Google Search |
| `file_manager.py` | Saves, loads, and lists timestamped JSON comparison files |
| `prefab_app.py` | Builds the Prefab component tree; `build_html()` returns a self-contained HTML page with `SetInterval + Fetch` polling wired in |
| `prefab_client.py` | Thin Flask server — `GET /` serves the cached Prefab HTML, `GET /api/data` serves live JSON; calls `build_html()` on each new search |

## Data Flow

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
     ├──► file_manager.py ──► saved_comparisons/product_YYYYMMDD_HHMMSS.json
     │
     └──► prefab_client.py
              ├── writes ui/current_comparison.json
              ├── calls prefab_app.build_html()  ──► PrefabApp with:
              │        ├── state: {"data": enriched_data}   (initial render)
              │        ├── on_mount: SetInterval(3000, Fetch /api/data)
              │        └── ForEach(comparison_data)
              │                 └── Card per retailer with If badges, Rx text
              ├── caches the HTML string
              ├── starts Flask on :5175 (once)
              └── webbrowser.open()

Browser (stays open):
     ├── renders initial cards from baked-in state
     └── every 3 s → GET /api/data → SetState("data", result)
                                           └── ForEach re-renders card list
                                           └── If re-evaluates badges
                                           └── Rx text nodes update
                                               ── no page reload
```

## How to Run It

### Option A — Standalone Python script

```python
# run_search.py
import sys
sys.path.insert(0, ".")
from serpapi_client import search_product_prices, search_product_reviews
from file_manager import save_comparison
from prefab_client import push_comparison_dashboard

PRODUCT = "mini LED TV"

results = search_product_prices(PRODUCT)
enriched = []
for item in results[:6]:
    rev = search_product_reviews(PRODUCT, item["retailer"])
    item.update(rev)
    enriched.append(item)

save_comparison(PRODUCT, enriched)
push_comparison_dashboard(PRODUCT, enriched)
```

```bash
C:\Users\tarun\AppData\Local\Programs\Python\Python310\python.exe run_search.py
```

### Option B — Claude Desktop (intended use)

**Step 1** — Find your config file:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Step 2** — Add this entry:

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

**Step 3** — Restart Claude Desktop, then type:

```
Compare boAt Rockerz 450 headphones across all retailers,
save the comparison, and show me a live dashboard.
```

The browser opens to `http://127.0.0.1:5175`. Keep the tab open and run another search — the cards update live.

## Project structure

```
product_intelligence_mcp/
├── server.py                     ← MCP server with 6 tools
├── prefab_app.py                 ← Prefab component tree + build_html()
├── prefab_client.py              ← Flask server (GET / and GET /api/data)
├── serpapi_client.py             ← SerpAPI search + review extraction
├── file_manager.py               ← JSON save / load / list
├── ui/
│   └── current_comparison.json  ← latest comparison data (written each search)
├── saved_comparisons/            ← timestamped JSON files (auto-created)
├── .env.example                  ← environment variable template
├── requirements.txt
└── README.md
```
