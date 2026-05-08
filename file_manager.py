import os
import json
from datetime import datetime
from pathlib import Path
from slugify import slugify

SAVE_DIR = Path(__file__).parent / "saved_comparisons"


def save_comparison(product_name: str, comparison_data: list[dict]) -> str:
    """Persist comparison data as a timestamped JSON file. Returns the file path."""
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(product_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slug}_{timestamp}.json"
    filepath = SAVE_DIR / filename
    payload = {
        "product_name": product_name,
        "generated_at": datetime.now().isoformat(),
        "retailer_count": len(comparison_data),
        "comparison_data": comparison_data,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return str(filepath.resolve())


def load_comparison(filepath: str) -> dict:
    """Load a previously saved comparison JSON file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Comparison file not found: {filepath}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_saved_comparisons() -> list[dict]:
    """Return metadata for all saved comparison files, newest first."""
    if not SAVE_DIR.exists():
        return []
    files = sorted(SAVE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    results = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            results.append(
                {
                    "file": str(f.resolve()),
                    "product_name": data.get("product_name", "Unknown"),
                    "generated_at": data.get("generated_at", ""),
                    "retailer_count": data.get("retailer_count", 0),
                }
            )
        except (json.JSONDecodeError, KeyError):
            continue
    return results
