import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from serpapi_client import search_product_prices, search_product_reviews
from file_manager import save_comparison, load_comparison, list_saved_comparisons
from prefab_client import push_comparison_dashboard
from models import (
    SearchToolResult, SearchResult,
    ReviewToolResult,
    SaveToolInput, SaveToolResult,
    RetailerItem,
)

load_dotenv()

mcp = FastMCP("product-intelligence")


# ---------------------------------------------------------------------------
# Tool 1: search_product
# ---------------------------------------------------------------------------

@mcp.tool()
def search_product(product_name: str) -> dict:
    """
    Search for a product across retailers using SerpAPI Google Shopping.
    Returns a list of retailers with prices, ratings, and links.
    Call this first before fetching reviews or saving comparisons.
    """
    results = search_product_prices(product_name)
    if not results:
        return {"status": "no_results", "product_name": product_name, "results": [], "retailer_count": 0}

    # Validate each result row and coerce types
    validated_results = [SearchResult(**r).model_dump() for r in results]
    output = SearchToolResult(
        status="success",
        product_name=product_name,
        retailer_count=len(validated_results),
        results=[SearchResult(**r) for r in validated_results],
    )
    return output.model_dump()


# ---------------------------------------------------------------------------
# Tool 2: get_product_reviews
# ---------------------------------------------------------------------------

@mcp.tool()
def get_product_reviews(product_name: str, retailer: str) -> dict:
    """
    Fetch review snippets, pros, and cons for a specific product at a given retailer.
    Call this for each retailer returned by search_product to enrich the comparison.
    """
    review_data = search_product_reviews(product_name, retailer)
    output = ReviewToolResult(
        status="success",
        product_name=product_name,
        retailer=retailer,
        pros=review_data.get("pros", []),
        cons=review_data.get("cons", []),
        review_summary=review_data.get("review_summary", ""),
    )
    return output.model_dump()


# ---------------------------------------------------------------------------
# Tool 3: save_comparison_to_file
# ---------------------------------------------------------------------------

@mcp.tool()
def save_comparison_to_file(product_name: str, comparison_data: list[dict]) -> dict:
    """
    Save the enriched comparison data (prices + reviews) to a timestamped JSON file.
    comparison_data should be a list of dicts, one per retailer, each containing:
      retailer, price, price_raw, rating, reviews, link, pros, cons, review_summary.
    Returns the file path of the saved JSON.
    Call this after get_product_reviews and before push_prefab_component.
    """
    # Validate input with Pydantic before persisting
    validated = SaveToolInput(
        product_name=product_name,
        comparison_data=comparison_data,
    )
    raw_list = [item.model_dump() for item in validated.comparison_data]
    filepath = save_comparison(validated.product_name, raw_list)
    output = SaveToolResult(
        status="success",
        product_name=validated.product_name,
        file_path=filepath,
        retailer_count=len(raw_list),
    )
    return output.model_dump()


# ---------------------------------------------------------------------------
# Tool 4: push_prefab_component
# ---------------------------------------------------------------------------

@mcp.tool()
def push_prefab_component(
    product_name: str,
    comparison_data: list[dict],
) -> dict:
    """
    Dynamically generates a comparison dashboard HTML file and serves it on a local
    Flask server at localhost:5050. Automatically opens the browser. Creates one card
    per retailer — card count is never hardcoded, changes with every search.
    Always call this last after save_comparison_to_file.
    Returns the local dashboard URL.
    """
    result = push_comparison_dashboard(product_name, comparison_data)
    return result


# ---------------------------------------------------------------------------
# Tool 5: list_comparisons
# ---------------------------------------------------------------------------

@mcp.tool()
def list_comparisons() -> dict:
    """
    List all previously saved product comparisons with metadata.
    Returns file paths, product names, timestamps, and retailer counts.
    """
    saved = list_saved_comparisons()
    return {
        "status": "success",
        "count": len(saved),
        "comparisons": saved,
    }


# ---------------------------------------------------------------------------
# Tool 6: load_saved_comparison
# ---------------------------------------------------------------------------

@mcp.tool()
def load_saved_comparison(filepath: str) -> dict:
    """
    Load a previously saved comparison JSON file by its absolute file path.
    Returns the full comparison data including all retailer details.
    """
    data = load_comparison(filepath)
    return {"status": "success", "data": data}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
