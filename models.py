"""Pydantic models for the Product Intelligence pipeline.

These models validate data at every boundary:
  - MCP tool inputs / outputs   (server.py)
  - Agent data cache             (agent.py  — _last_comparison)
  - UI rendering payload         (agent.py  — _try_execute_ui_code)
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator, model_validator


# ---------------------------------------------------------------------------
# Shared / primitive models
# ---------------------------------------------------------------------------

class RetailerItem(BaseModel):
    """One row returned by search_product and enriched by get_product_reviews."""

    retailer: str
    price: float = 0.0
    price_raw: str = ""
    rating: Optional[float] = None
    reviews: int = 0
    link: str = ""

    # Review fields — populated after get_product_reviews
    pros: list[str] = []
    cons: list[str] = []
    review_summary: str = ""

    @field_validator("price", mode="before")
    @classmethod
    def coerce_price(cls, v):
        """Accept None or empty string as 0."""
        if v is None or v == "":
            return 0.0
        return float(v)

    @field_validator("rating", mode="before")
    @classmethod
    def coerce_rating(cls, v):
        if v is None or v == "":
            return None
        return float(v)

    @field_validator("reviews", mode="before")
    @classmethod
    def coerce_reviews(cls, v):
        if v is None or v == "":
            return 0
        return int(v)


# ---------------------------------------------------------------------------
# Tool: search_product
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """Raw result row from SerpAPI Google Shopping."""

    retailer: str
    price: float = 0.0
    price_raw: str = ""
    rating: Optional[float] = None
    reviews: int = 0
    link: str = ""

    @field_validator("price", mode="before")
    @classmethod
    def coerce_price(cls, v):
        if v is None or v == "":
            return 0.0
        return float(v)

    @field_validator("rating", mode="before")
    @classmethod
    def coerce_rating(cls, v):
        if v is None or v == "":
            return None
        return float(v)

    @field_validator("reviews", mode="before")
    @classmethod
    def coerce_reviews(cls, v):
        if v is None or v == "":
            return 0
        return int(v)


class SearchToolResult(BaseModel):
    """Return value of the search_product MCP tool."""

    status: str
    product_name: str
    retailer_count: int = 0
    results: list[SearchResult] = []

    @model_validator(mode="after")
    def check_results_match_count(self) -> "SearchToolResult":
        if self.status == "success":
            assert len(self.results) == self.retailer_count, (
                f"retailer_count={self.retailer_count} but "
                f"results has {len(self.results)} items"
            )
        return self


# ---------------------------------------------------------------------------
# Tool: get_product_reviews
# ---------------------------------------------------------------------------

class ReviewToolResult(BaseModel):
    """Return value of the get_product_reviews MCP tool."""

    status: str
    product_name: str
    retailer: str
    pros: list[str] = []
    cons: list[str] = []
    review_summary: str = ""


# ---------------------------------------------------------------------------
# Tool: save_comparison_to_file
# ---------------------------------------------------------------------------

class SaveToolInput(BaseModel):
    """Validated input for save_comparison_to_file."""

    product_name: str
    comparison_data: list[RetailerItem]

    @field_validator("product_name")
    @classmethod
    def product_name_not_empty(cls, v: str) -> str:
        assert v.strip(), "product_name must not be empty"
        return v.strip()

    @field_validator("comparison_data")
    @classmethod
    def at_least_one_retailer(cls, v: list) -> list:
        assert len(v) > 0, "comparison_data must contain at least one retailer"
        return v


class SaveToolResult(BaseModel):
    """Return value of save_comparison_to_file."""

    status: str
    product_name: str
    file_path: str
    retailer_count: int


# ---------------------------------------------------------------------------
# Agent: comparison cache (_last_comparison)
# ---------------------------------------------------------------------------

class ComparisonPayload(BaseModel):
    """The data dict cached by the agent after save_comparison_to_file succeeds.
    This is passed verbatim to the LLM-generated build_html(initial_data).
    """

    product_name: str
    comparison_data: list[RetailerItem]

    @field_validator("product_name")
    @classmethod
    def product_name_not_empty(cls, v: str) -> str:
        assert v.strip(), "product_name must not be empty"
        return v.strip()

    @field_validator("comparison_data")
    @classmethod
    def at_least_one_retailer(cls, v: list) -> list:
        assert len(v) > 0, "comparison_data must contain at least one retailer"
        return v

    def to_dict(self) -> dict:
        """Return a plain dict compatible with build_html(initial_data)."""
        return self.model_dump()
