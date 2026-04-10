import logging
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from config import settings
from database import execute_query, execute_write
from models import (
    CallDetailResponse,
    CallListResponse,
    CallUploadResponse,
)
from routers.utils import parse_json_list, row_to_call_summary
from services.processor import process_call

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".m4a", ".amr", ".wav", ".ogg", ".mp3", ".aac", ".opus"}


# ─────────────────────────────────────────────────────────────────────────────
#  POST /calls/upload
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=CallUploadResponse, status_code=201)
async def upload_call(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio recording file"),
    phone_number: str = Form(...),
    direction: str = Form("unknown"),
    recorded_at: str = Form(...),
    duration_sec: Optional[int] = Form(None),
    contact_name: Optional[str] = Form(None),
):
    """
    Upload a call recording with metadata.

    - Saves the audio file to disk
    - Upserts the contact record
    - Creates a call record with status='uploaded'
    - Enqueues background processing (transcription + summarization)
    """
    # ── Validate file extension ───────────────────────────────────────────
    suffix = Path(file.filename).suffix.lower() if file.filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # ── Save audio file to disk ───────────────────────────────────────────
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    dest_path = settings.AUDIO_STORAGE_DIR / unique_name

    async with aiofiles.open(dest_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    logger.info(f"Saved audio to {dest_path} ({len(content)} bytes)")

    # ── Upsert contact ────────────────────────────────────────────────────
    existing = await execute_query(
        "SELECT id FROM contacts WHERE phone_number = ?", (phone_number,)
    )

    if existing:
        contact_id = existing[0]["id"]
        await execute_write(
            """UPDATE contacts
               SET total_calls  = total_calls + 1,
                   last_call_at = ?,
                   display_name = COALESCE(?, display_name)
               WHERE id = ?""",
            (recorded_at, contact_name, contact_id),
        )
    else:
        contact_id = await execute_write(
            """INSERT INTO contacts (phone_number, display_name, total_calls, last_call_at)
               VALUES (?, ?, 1, ?)""",
            (phone_number, contact_name, recorded_at),
        )

    # ── Create call record ────────────────────────────────────────────────
    call_id = await execute_write(
        """INSERT INTO calls
               (contact_id, phone_number, direction, duration_sec, recorded_at, audio_path, status)
           VALUES (?, ?, ?, ?, ?, ?, 'uploaded')""",
        (contact_id, phone_number, direction, duration_sec, recorded_at, str(dest_path)),
    )

    # ── Enqueue background processing ─────────────────────────────────────
    background_tasks.add_task(process_call, call_id)

    return CallUploadResponse(call_id=call_id, status="uploaded")


# ─────────────────────────────────────────────────────────────────────────────
#  GET /calls
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=CallListResponse)
async def list_calls(
    phone_number: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """List calls ordered by most recent, with optional contact filter and pagination."""
    base_where = "WHERE 1=1"
    params: list = []

    if phone_number:
        base_where += " AND phone_number = ?"
        params.append(phone_number)

    rows = await execute_query(
        f"SELECT * FROM calls {base_where} ORDER BY recorded_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )

    count_rows = await execute_query(
        f"SELECT COUNT(*) as total FROM calls {base_where}",
        tuple(params),
    )
    total = count_rows[0]["total"] if count_rows else 0

    return CallListResponse(
        calls=[row_to_call_summary(r) for r in rows],
        total=total,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  GET /calls/{call_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{call_id}", response_model=CallDetailResponse)
async def get_call(call_id: int):
    """Get full detail for a single call, including transcript."""
    rows = await execute_query(
        """SELECT c.*, co.display_name as contact_name
           FROM calls c
           LEFT JOIN contacts co ON c.contact_id = co.id
           WHERE c.id = ?""",
        (call_id,),
    )

    if not rows:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")

    row = rows[0]
    return CallDetailResponse(
        id=row["id"],
        phone_number=row["phone_number"],
        direction=row.get("direction"),
        duration_sec=row.get("duration_sec"),
        recorded_at=row["recorded_at"],
        summary=row.get("summary"),
        key_points=parse_json_list(row.get("key_points")),
        action_items=parse_json_list(row.get("action_items")),
        status=row["status"],
        transcript=row.get("transcript"),
        audio_path=row.get("audio_path"),
        contact_name=row.get("contact_name"),
        contact_id=row.get("contact_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  POST /calls/{call_id}/reprocess
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{call_id}/reprocess", response_model=CallUploadResponse)
async def reprocess_call(call_id: int, background_tasks: BackgroundTasks):
    """
    Re-trigger the transcription + summarization pipeline for a call.

    Useful when a call is stuck at 'failed' due to a transient error
    (Groq API down, wrong model name, network issue, etc.).
    The call's audio file must still exist on disk.
    """
    rows = await execute_query(
        "SELECT id, status, audio_path FROM calls WHERE id = ?", (call_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")

    call = rows[0]
    if not call["audio_path"]:
        raise HTTPException(
            status_code=400,
            detail="Call has no audio file — cannot reprocess.",
        )

    # Reset status so the processor starts from scratch
    await execute_write(
        "UPDATE calls SET status = 'uploaded', transcript = NULL, "
        "summary = NULL, key_points = NULL, action_items = NULL WHERE id = ?",
        (call_id,),
    )

    background_tasks.add_task(process_call, call_id)

    return CallUploadResponse(call_id=call_id, status="reprocessing")
