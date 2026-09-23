"""Category and region catalogue shipped with the package."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache
def catalog() -> dict:
    path = Path(__file__).parent / "data" / "categories.json"
    return json.loads(path.read_text())


def categories() -> list[dict]:
    return catalog()["categories"]


def regions() -> list[dict]:
    return catalog()["regions"]


def category_by_id(category_id: str) -> dict | None:
    for item in categories():
        if item["id"] == category_id:
            return item
    return None


def region_by_id(region_id: str) -> dict | None:
    for item in regions():
        if item["id"] == region_id:
            return item
    return None
