"""
Pagination helper — framework-agnostic, pure Python.
"""
from typing import Any, Dict, List, TypeVar

from api.utils.constants import ITEMS_PER_PAGE

T = TypeVar("T")


def paginate(items: List[T], page: int, per_page: int = ITEMS_PER_PAGE) -> Dict[str, Any]:
    """
    Slice a list and return pagination metadata.

    Returns::

        {
          "items":       [...],
          "page":        1,
          "total_pages": 4,
          "total":       35,
          "has_prev":    False,
          "has_next":    True,
        }
    """
    total = len(items)
    total_pages = max(1, -(-total // per_page))   # ceiling division
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    return {
        "items":       items[offset : offset + per_page],
        "page":        page,
        "total_pages": total_pages,
        "total":       total,
        "has_prev":    page > 1,
        "has_next":    page < total_pages,
    }
