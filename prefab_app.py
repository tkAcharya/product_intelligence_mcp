"""Prefab component tree for the product comparison dashboard.

`build_html(initial_data)` generates a self-contained HTML page whose React
runtime polls `/api/data` every 3 s via SetInterval + Fetch.  When the
browser receives new data it calls SetState("data", RESULT), which causes
ForEach and If to re-render the affected cards in-place — no page reload.
"""

from prefab_ui.actions import Fetch, SetInterval, SetState
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge,
    Card,
    CardContent,
    CardFooter,
    Column,
    H3,
    H4,
    Link,
    Muted,
    Row,
    Text,
)
from prefab_ui.components.control_flow import ForEach, If
from prefab_ui.rx import ITEM, RESULT, Rx

POLL_MS = 3_000


# ---------------------------------------------------------------------------
# Data helper — adds computed fields so the reactive template stays simple
# ---------------------------------------------------------------------------

def _enrich(raw: dict) -> dict:
    items = list(raw.get("comparison_data", []))

    priced = [c for c in items if c.get("price", 0) > 0]
    best = min(priced, key=lambda c: c["price"]).get("retailer") if priced else None

    rated = [c for c in items if c.get("rating") is not None]
    top = (
        max(rated, key=lambda c: float(c.get("rating", 0))).get("retailer")
        if rated
        else None
    )

    for item in items:
        item["is_best"] = item.get("retailer") == best
        item["is_top"] = item.get("retailer") == top
        item["pros_str"] = " · ".join(f"✅ {p}" for p in item.get("pros", []))
        item["cons_str"] = " · ".join(f"❌ {c}" for c in item.get("cons", []))
        rs = item.get("review_summary", "")
        item["snippet"] = (rs[:200] + "…") if len(rs) > 200 else rs
        r = item.get("rating")
        rev = item.get("reviews", 0)
        item["rating_str"] = (
            f"{'⭐' * int(float(r))} {r}  ({rev} reviews)" if r is not None else ""
        )

    return {
        "product_name": raw.get("product_name", ""),
        "comparison_data": items,
        "timestamp": raw.get("timestamp", ""),
    }


# ---------------------------------------------------------------------------
# HTML builder — called once per new search, result is cached by the server
# ---------------------------------------------------------------------------

def build_html(initial_data: dict) -> str:
    """Return a full HTML page with the Prefab React runtime embedded.

    The page polls /api/data every POLL_MS ms.  On each successful response
    it overwrites the "data" state key, triggering reactive re-renders of
    all bound components (ForEach cards, If badges, Rx text nodes).
    """
    product_name = Rx("data.product_name")
    comparison_data = Rx("data.comparison_data")
    timestamp = Rx("data.timestamp")

    with PrefabApp(
        title="Product Intelligence",
        state={"data": initial_data},
        # on_mount attaches to the root div; fires once when the page loads.
        on_mount=SetInterval(
            POLL_MS,
            on_tick=Fetch.get("/api/data", on_success=SetState("data", RESULT)),
        ),
    ) as app:
        with Column(gap=6, css_class="max-w-7xl mx-auto px-8 py-6"):

            # ── Header ──────────────────────────────────────────────────
            with Row(css_class="items-center justify-between pb-4 border-b gap-4"):
                with Column(gap=1):
                    H3(f"🛍️ {product_name}")
                    Muted(f"Generated at {timestamp}")
                Badge(f"{comparison_data.length()} retailers", variant="default")

            # ── Retailer cards — rendered reactively via ForEach ─────────
            with Row(css_class="flex-wrap items-start gap-4"):
                with ForEach(comparison_data):
                    with Card(css_class="min-w-64 max-w-xs flex-1"):
                        with CardContent(css_class="flex flex-col gap-3 pt-4"):

                            with Row(css_class="gap-2 flex-wrap min-h-6"):
                                with If(ITEM["is_best"]):
                                    Badge("🏷️ Best Value", variant="success")
                                with If(ITEM["is_top"]):
                                    Badge("⭐ Top Rated", variant="outline")

                            H3(ITEM["retailer"])
                            H4(ITEM["price_raw"])

                            with If(ITEM["rating_str"]):
                                Muted(ITEM["rating_str"])

                            with If(ITEM["pros_str"]):
                                Text(ITEM["pros_str"])

                            with If(ITEM["cons_str"]):
                                Text(ITEM["cons_str"])

                            with If(ITEM["snippet"]):
                                Muted(f'💬 {ITEM["snippet"]}')

                        with CardFooter():
                            Link("View Deal →", href=ITEM["link"], target="_blank")

    return app.html()
