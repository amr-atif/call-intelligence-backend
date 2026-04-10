"""
Shared utilities for routers — avoids duplicating these helpers in every router file.
"""
import json
from typing import Optional

from models import CallSummaryResponse


def parse_json_list(raw: Optional[str]) -> Optional[list[str]]:
    """Parse a JSON string column into a Python list. Returns None if null, [] if invalid."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def row_to_call_summary(row: dict) -> CallSummaryResponse:
    """Convert a raw DB row dict into a CallSummaryResponse."""
    return CallSummaryResponse(
        id=row["id"],
        phone_number=row["phone_number"],
        direction=row.get("direction"),
        duration_sec=row.get("duration_sec"),
        recorded_at=row["recorded_at"],
        summary=row.get("summary"),
        key_points=parse_json_list(row.get("key_points")),
        action_items=parse_json_list(row.get("action_items")),
        status=row["status"],
    )
