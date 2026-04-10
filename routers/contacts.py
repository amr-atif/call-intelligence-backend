import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from database import execute_query
from models import (
    ContactListResponse,
    ContactResponse,
    ContactTimelineResponse,
)
from routers.utils import parse_json_list, row_to_call_summary

logger = logging.getLogger(__name__)

router = APIRouter()


def _row_to_contact(row: dict, last_summary: Optional[str] = None) -> ContactResponse:
    return ContactResponse(
        id=row["id"],
        phone_number=row["phone_number"],
        display_name=row.get("display_name"),
        total_calls=row.get("total_calls", 0),
        last_call_at=row.get("last_call_at"),
        last_summary=last_summary,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  GET /contacts
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=ContactListResponse)
async def list_contacts(search: Optional[str] = None):
    """
    List all contacts ordered by most recent call.
    Optional `search` filters by display_name or phone_number.
    Includes the last call's summary for each contact.
    """
    base_query = "SELECT * FROM contacts"
    params: list = []

    if search:
        base_query += " WHERE display_name LIKE ? OR phone_number LIKE ?"
        pattern = f"%{search}%"
        params.extend([pattern, pattern])

    base_query += " ORDER BY last_call_at DESC"
    contact_rows = await execute_query(base_query, tuple(params))

    contacts = []
    for row in contact_rows:
        # Fetch the latest summary for this contact
        summary_rows = await execute_query(
            """SELECT summary FROM calls
               WHERE contact_id = ? AND summary IS NOT NULL
               ORDER BY recorded_at DESC
               LIMIT 1""",
            (row["id"],),
        )
        last_summary = summary_rows[0]["summary"] if summary_rows else None
        contacts.append(_row_to_contact(row, last_summary))

    return ContactListResponse(contacts=contacts)


# ─────────────────────────────────────────────────────────────────────────────
#  GET /contacts/{phone}/timeline
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{phone}/timeline", response_model=ContactTimelineResponse)
async def get_contact_timeline(phone: str):
    """
    Return a contact's full chronological call history with summaries.
    `phone` should be URL-encoded if it contains '+' (e.g. %2B201234567890).
    """
    contact_rows = await execute_query(
        "SELECT * FROM contacts WHERE phone_number = ?", (phone,)
    )
    if not contact_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No contact found for phone number '{phone}'",
        )

    contact_row = contact_rows[0]

    # Fetch last summary for this contact
    summary_rows = await execute_query(
        """SELECT summary FROM calls
           WHERE contact_id = ? AND summary IS NOT NULL
           ORDER BY recorded_at DESC LIMIT 1""",
        (contact_row["id"],),
    )
    last_summary = summary_rows[0]["summary"] if summary_rows else None
    contact = _row_to_contact(contact_row, last_summary)

    # Fetch all calls ordered newest first
    call_rows = await execute_query(
        "SELECT * FROM calls WHERE contact_id = ? ORDER BY recorded_at DESC",
        (contact_row["id"],),
    )

    return ContactTimelineResponse(
        contact=contact,
        calls=[row_to_call_summary(r) for r in call_rows],
    )
