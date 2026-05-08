import os
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SERPAPI_BASE = "https://serpapi.com/search"


def _fetch_serpapi(params: dict) -> dict:
    params["api_key"] = SERPAPI_KEY
    with httpx.Client(timeout=30) as client:
        response = client.get(SERPAPI_BASE, params=params)
        response.raise_for_status()
        return response.json()


def search_product_prices(product_name: str) -> list[dict]:
    """Search for product prices across retailers using SerpAPI Google Shopping."""
    params = {
        "engine": "google_shopping",
        "q": product_name,
        "gl": "in",
        "hl": "en",
        "num": 10,
    }
    data = _fetch_serpapi(params)
    results = []
    shopping_results = data.get("shopping_results", [])
    for item in shopping_results:
        retailer = item.get("source", "Unknown")
        price_str = item.get("price", "")
        price = _parse_price(price_str)
        link = item.get("link", "")
        title = item.get("title", product_name)
        rating = item.get("rating")
        reviews = item.get("reviews")
        results.append(
            {
                "retailer": retailer,
                "title": title,
                "price": price,
                "price_raw": price_str,
                "rating": rating,
                "reviews": reviews,
                "link": link,
            }
        )
    return results


def search_product_reviews(product_name: str, retailer: str) -> dict:
    """Fetch organic search snippets for a product review at a specific retailer."""
    query = f"{product_name} review {retailer} pros cons"
    params = {
        "engine": "google",
        "q": query,
        "gl": "in",
        "hl": "en",
        "num": 5,
    }
    data = _fetch_serpapi(params)
    organic = data.get("organic_results", [])
    snippets = [r.get("snippet", "") for r in organic if r.get("snippet")]
    pros, cons = _extract_pros_cons(snippets)
    review_summary = snippets[0] if snippets else "No review data available."
    return {
        "retailer": retailer,
        "pros": pros,
        "cons": cons,
        "review_summary": review_summary,
    }


def _parse_price(price_str: str) -> float:
    """Extract numeric price from strings like '₹1,299', '$19.99', etc."""
    import re
    cleaned = re.sub(r"[^\d.]", "", price_str.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _extract_pros_cons(snippets: list[str]) -> tuple[list[str], list[str]]:
    """Heuristically split review snippets into pros and cons lists."""
    pros_keywords = ["good", "great", "excellent", "best", "love", "comfortable",
                     "impressive", "fast", "clear", "quality", "value", "durable"]
    cons_keywords = ["bad", "poor", "issue", "problem", "worst", "slow", "low",
                     "weak", "short", "loud", "uncomfortable", "laggy", "defect"]
    pros, cons = [], []
    for snippet in snippets:
        lower = snippet.lower()
        if any(k in lower for k in pros_keywords):
            sentence = snippet.split(".")[0].strip()
            if sentence and sentence not in pros:
                pros.append(sentence)
        if any(k in lower for k in cons_keywords):
            sentence = snippet.split(".")[-1].strip()
            if sentence and sentence not in cons:
                cons.append(sentence)
    return pros[:3], cons[:3]
