from pydantic import BaseModel
from typing import Optional


# ──────────────────────────────────────────────
#  Request Models
# ──────────────────────────────────────────────

class CallUploadMeta(BaseModel):
    """Metadata submitted alongside the audio file upload (as form fields)."""
    phone_number: str
    direction: str = "unknown"          # incoming | outgoing | unknown
    duration_sec: Optional[int] = None
    recorded_at: str                    # ISO 8601 string
    contact_name: Optional[str] = None


# ──────────────────────────────────────────────
#  Response Models
# ──────────────────────────────────────────────

class CallUploadResponse(BaseModel):
    call_id: int
    status: str


class CallSummaryResponse(BaseModel):
    id: int
    phone_number: str
    direction: Optional[str]
    duration_sec: Optional[int]
    recorded_at: str
    summary: Optional[str]
    key_points: Optional[list[str]]
    action_items: Optional[list[str]]
    status: str


class CallDetailResponse(CallSummaryResponse):
    transcript: Optional[str]
    audio_path: Optional[str]
    contact_name: Optional[str]
    contact_id: Optional[int]


class CallListResponse(BaseModel):
    calls: list[CallSummaryResponse]
    total: int


class ContactResponse(BaseModel):
    id: int
    phone_number: str
    display_name: Optional[str]
    total_calls: int
    last_call_at: Optional[str]
    last_summary: Optional[str]


class ContactListResponse(BaseModel):
    contacts: list[ContactResponse]


class ContactTimelineResponse(BaseModel):
    contact: ContactResponse
    calls: list[CallSummaryResponse]
