"""
Product Intelligence — MCP client orchestrator
================================================
Starts `run_server.py` in a background subprocess (streamable-HTTP on 8090),
then uses FastMCP Client to call the four MCP tools in sequence:

  1. search_product         — Google Shopping results via SerpAPI
  2. get_product_reviews    — review snippets per retailer
  3. save_comparison_to_file — persist enriched data as JSON
  4. push_prefab_component  — build Prefab HTML + open browser dashboard

Usage:
    python main.py "Sony OLED TV"          # default
    python main.py "Samsung QLED 65 inch"  # any product
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
from fastmcp import Client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MCP_SERVER_URL = "http://127.0.0.1:8090/mcp"
MAX_WAIT_SEC = 15          # seconds to wait for MCP server to be ready
REVIEWS_LIMIT = 5          # max retailers to enrich with reviews (speed vs depth)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_server(url: str, timeout: int = MAX_WAIT_SEC) -> bool:
    """Poll the MCP server until it responds or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def _result(tool_output) -> dict | list:
    """Extract the Python object from a FastMCP 3.x CallToolResult.

    FastMCP 3.x returns a CallToolResult dataclass with:
      .data            — already-parsed Python object (preferred)
      .content         — list[ContentBlock] with .text for raw JSON fallback
    """
    # Preferred: .data is already deserialized
    if hasattr(tool_output, "data") and tool_output.data is not None:
        return tool_output.data

    # Fallback: parse first content block's text
    content = getattr(tool_output, "content", None)
    if content:
        text = getattr(content[0], "text", None) or str(content[0])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}

    return {}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(product_name: str) -> None:
    print(f"\n[SEARCH]  Searching for: {product_name!r}")
    print(f"[MCP]     Connecting to MCP server at {MCP_SERVER_URL}\n")

    async with Client(MCP_SERVER_URL) as client:

        # ── Step 1: Search Google Shopping ──────────────────────────────────
        print("[1/4] search_product ...")
        raw = await client.call_tool("search_product", {"product_name": product_name})
        search = _result(raw)

        if search.get("status") != "success":
            print(f"  ❌  Search returned no results: {search}")
            return

        retailers = search["results"]
        print(f"  OK  Found {len(retailers)} retailers")

        # ── Step 2: Fetch reviews per retailer ──────────────────────────────
        enriched: list[dict] = []
        top_retailers = retailers[:REVIEWS_LIMIT]

        for i, item in enumerate(top_retailers, 1):
            retailer = item["retailer"]
            print(f"[2/4] get_product_reviews ({i}/{len(top_retailers)}) -- {retailer} ...")
            raw_rev = await client.call_tool(
                "get_product_reviews",
                {"product_name": product_name, "retailer": retailer},
            )
            review = _result(raw_rev)
            merged = {**item, **{
                "pros":           review.get("pros", []),
                "cons":           review.get("cons", []),
                "review_summary": review.get("review_summary", ""),
            }}
            enriched.append(merged)

        # ── Step 3: Save to file ─────────────────────────────────────────────
        print(f"\n[3/4] save_comparison_to_file ...")
        raw_save = await client.call_tool(
            "save_comparison_to_file",
            {"product_name": product_name, "comparison_data": enriched},
        )
        save_res = _result(raw_save)
        print(f"  OK  Saved -> {save_res.get('file_path', '?')}")

        # ── Step 4: Push dashboard ────────────────────────────────────────────
        print(f"\n[4/4] push_prefab_component (opens browser) ...")
        raw_push = await client.call_tool(
            "push_prefab_component",
            {"product_name": product_name, "comparison_data": enriched},
        )
        push_res = _result(raw_push)
        print(f"  OK  {push_res.get('message', push_res)}")
        print(f"\nDone! Dashboard live at {push_res.get('dashboard_url', 'http://127.0.0.1:5175/')}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    product_name = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Sony OLED TV"

    # 1. Start the MCP server as a background subprocess
    venv_python = str(Path(__file__).parent / "venv310" / "Scripts" / "python.exe")
    run_server = str(Path(__file__).parent / "run_server.py")

    print(f"[START] Launching MCP server (run_server.py) ...")
    proc = subprocess.Popen(
        [venv_python, run_server],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # 2. Wait for the server to be ready
    print(f"[WAIT]  Waiting for MCP server to be ready at {MCP_SERVER_URL} ...")
    if not _wait_for_server(MCP_SERVER_URL, MAX_WAIT_SEC):
        print("[ERROR] MCP server did not start in time. Check run_server.py for errors.")
        proc.terminate()
        sys.exit(1)
    print("[READY] MCP server is up!\n")

    # 3. Run the async pipeline
    try:
        asyncio.run(run_pipeline(product_name))
        input("\n[INFO] Pipeline complete. The dashboard is live. Press Enter to exit and stop the server...")
    except KeyboardInterrupt:
        print("\n[WARN] Interrupted by user.")
    finally:
        # 4. Shut down the MCP server
        print("[STOP] Stopping MCP server ...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[DONE] Exited.")


if __name__ == "__main__":
    main()
