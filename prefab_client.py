import threading
import time
import webbrowser
import os
from flask import Flask
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

UI_PORT = int(os.getenv("UI_PORT", "5050"))

UI_DIR = Path(__file__).parent / "ui"
DASHBOARD_FILE = UI_DIR / "dashboard.html"

flask_app = Flask(__name__)

_server_started = False
_server_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Part A: HTML Generator
# ---------------------------------------------------------------------------

def generate_dashboard_html(product_name: str, comparison_data: list[dict]) -> str:
    """Generate a complete self-contained dark-themed comparison dashboard HTML string."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    retailer_count = len(comparison_data)

    # Determine best value (lowest non-zero price) and top rated
    priced = [c for c in comparison_data if c.get("price", 0) > 0]
    best_value = min(priced, key=lambda c: c["price"]) if priced else None
    rated = [c for c in comparison_data if c.get("rating") is not None]
    top_rated = max(rated, key=lambda c: float(c.get("rating", 0))) if rated else None

    # Build cards
    cards_html = ""
    for item in comparison_data:
        retailer = item.get("retailer", "Unknown")
        price = item.get("price", 0)
        price_raw = item.get("price_raw", f"₹{price:,.0f}" if price else "N/A")
        rating = item.get("rating")
        reviews = item.get("reviews")
        link = item.get("link", "#")
        pros = item.get("pros", [])
        cons = item.get("cons", [])
        review_summary = item.get("review_summary", "")

        # Glow styles
        border_style = "border: 1px solid #444;"
        badge_html = ""
        is_best = best_value and retailer == best_value.get("retailer") and price == best_value.get("price")
        is_top = top_rated and retailer == top_rated.get("retailer")
        if is_best and is_top:
            border_style = "border: 2px solid #00D4AA; box-shadow: 0 0 16px #00D4AA88;"
            badge_html = '<span style="background:#00D4AA;color:#000;border-radius:4px;padding:2px 8px;font-size:0.75rem;margin-right:4px;">🏷️ Best Value</span><span style="background:#FFD700;color:#000;border-radius:4px;padding:2px 8px;font-size:0.75rem;">⭐ Top Rated</span>'
        elif is_best:
            border_style = "border: 2px solid #00D4AA; box-shadow: 0 0 16px #00D4AA88;"
            badge_html = '<span style="background:#00D4AA;color:#000;border-radius:4px;padding:2px 8px;font-size:0.75rem;">🏷️ Best Value</span>'
        elif is_top:
            border_style = "border: 2px solid #FFD700; box-shadow: 0 0 16px #FFD70088;"
            badge_html = '<span style="background:#FFD700;color:#000;border-radius:4px;padding:2px 8px;font-size:0.75rem;">⭐ Top Rated</span>'

        # Stars
        stars_html = ""
        if rating is not None:
            full = int(float(rating))
            stars_html = "⭐" * full + ("½" if float(rating) - full >= 0.5 else "")
            reviews_str = f"({reviews} reviews)" if reviews else ""
            stars_html = f'<div style="color:#FFD700;margin:6px 0;">{stars_html} <span style="color:#aaa;font-size:0.8rem;">{rating} {reviews_str}</span></div>'

        # Pros
        pros_html = ""
        if pros:
            items = "".join(f'<li style="color:#4ade80;margin:3px 0;">✅ {p}</li>' for p in pros)
            pros_html = f'<ul style="list-style:none;padding:0;margin:8px 0 4px 0;">{items}</ul>'

        # Cons
        cons_html = ""
        if cons:
            items = "".join(f'<li style="color:#f87171;margin:3px 0;">❌ {c}</li>' for c in cons)
            cons_html = f'<ul style="list-style:none;padding:0;margin:4px 0;">{items}</ul>'

        # Review snippet
        review_html = ""
        if review_summary:
            escaped = review_summary.replace("<", "&lt;").replace(">", "&gt;")
            review_html = f'<p style="color:#aaa;font-size:0.8rem;border-left:3px solid #555;padding-left:8px;margin:8px 0;">💬 {escaped[:200]}{"…" if len(escaped) > 200 else ""}</p>'

        cards_html += f"""
        <div style="background:#1e1e2e;{border_style}border-radius:12px;padding:20px;min-width:280px;max-width:320px;flex:1;display:flex;flex-direction:column;gap:4px;">
            <div style="margin-bottom:6px;">{badge_html}</div>
            <h3 style="color:#e2e8f0;margin:0 0 4px 0;font-size:1rem;">{retailer}</h3>
            <div style="color:#00D4AA;font-size:1.8rem;font-weight:700;margin:4px 0;">{price_raw}</div>
            {stars_html}
            {pros_html}
            {cons_html}
            {review_html}
            <a href="{link}" target="_blank" rel="noopener" style="display:inline-block;margin-top:auto;padding-top:12px;background:#00D4AA;color:#000;text-align:center;border-radius:8px;padding:10px 16px;text-decoration:none;font-weight:600;font-size:0.9rem;">View Deal →</a>
        </div>
"""

    # Summary bar
    best_val_html = ""
    if best_value:
        bv_price = best_value.get("price_raw", f"₹{best_value.get('price', 0):,.0f}")
        best_val_html = f'<span style="margin-right:24px;">🏷️ <strong>Best Value:</strong> {best_value.get("retailer")} &nbsp;<span style="color:#00D4AA;">{bv_price}</span></span>'

    top_rated_html = ""
    if top_rated:
        top_rated_html = f'<span>⭐ <strong>Top Rated:</strong> {top_rated.get("retailer")} &nbsp;<span style="color:#FFD700;">{top_rated.get("rating")}</span></span>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Product Comparison: {product_name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f0f1a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 32px 40px; border-bottom: 1px solid #2d2d44; }}
  .header h1 {{ font-size: 1.8rem; font-weight: 700; color: #fff; }}
  .header .meta {{ color: #888; margin-top: 8px; font-size: 0.9rem; }}
  .cards-section {{ padding: 32px 40px; }}
  .cards-wrap {{ display: flex; flex-wrap: wrap; gap: 20px; }}
  .summary-bar {{ background: #1a1a2e; border-top: 1px solid #2d2d44; padding: 20px 40px; display: flex; align-items: center; flex-wrap: wrap; gap: 16px; font-size: 0.95rem; }}
  @media (max-width: 600px) {{ .header, .cards-section, .summary-bar {{ padding: 20px; }} }}
</style>
</head>
<body>
<div class="header">
  <h1>🛍️ Product Comparison: {product_name}</h1>
  <div class="meta">
    <span>{retailer_count} retailer{"s" if retailer_count != 1 else ""} found</span>
    &nbsp;·&nbsp;
    <span>Generated at: {timestamp}</span>
  </div>
</div>
<div class="cards-section">
  <div class="cards-wrap">
{cards_html}
  </div>
</div>
<div class="summary-bar">
  {best_val_html}
  {top_rated_html}
</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Part B: File Writer
# ---------------------------------------------------------------------------

def write_dashboard_file(html_content: str) -> str:
    """Write html_content to ./ui/dashboard.html, creating the directory if needed."""
    UI_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_FILE.write_text(html_content, encoding="utf-8")
    return str(DASHBOARD_FILE.resolve())


# ---------------------------------------------------------------------------
# Part C: Local Flask Server
# ---------------------------------------------------------------------------

@flask_app.route("/")
def serve_dashboard():
    if not DASHBOARD_FILE.exists():
        return "<h2 style='font-family:sans-serif;padding:40px;'>No comparison run yet. Ask the agent to compare a product.</h2>"
    return DASHBOARD_FILE.read_text(encoding="utf-8")


def start_local_server() -> None:
    """Start the Flask server in a daemon thread if it isn't already running."""
    global _server_started
    with _server_lock:
        if _server_started:
            return
        import httpx as _httpx
        try:
            _httpx.get(f"http://localhost:{UI_PORT}/", timeout=2)
            _server_started = True
            return
        except Exception:
            pass

        thread = threading.Thread(
            target=lambda: flask_app.run(
                port=UI_PORT,
                debug=False,
                use_reloader=False,
            )
        )
        thread.daemon = True
        thread.start()
        time.sleep(1)
        _server_started = True


# ---------------------------------------------------------------------------
# Part D: Main push function
# ---------------------------------------------------------------------------

def push_comparison_dashboard(
    product_name: str,
    comparison_data: list[dict],
) -> dict:
    """Generate dashboard HTML, save it, start the local server, and open the browser."""
    html_content = generate_dashboard_html(product_name, comparison_data)
    file_path = write_dashboard_file(html_content)
    start_local_server()
    url = f"http://localhost:{UI_PORT}/"
    webbrowser.open(url)
    return {
        "status": "success",
        "dashboard_url": url,
        "file_path": file_path,
        "card_count": len(comparison_data),
        "message": f"Dashboard opened at localhost:{UI_PORT} with {len(comparison_data)} retailer cards",
    }
