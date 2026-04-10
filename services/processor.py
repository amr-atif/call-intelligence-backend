import json
import logging
from database import execute_query, execute_write
from services.transcription import transcribe_audio
from services.summarization import summarize_transcript

logger = logging.getLogger(__name__)


async def process_call(call_id: int) -> None:
    """
    Full background processing pipeline for a single call:

    1. Fetch call record
    2. Whisper transcription  → status: 'transcribing' → 'transcribed'
    3. Groq summarization     → status: 'summarizing'  → 'done'

    On any failure, status is set to 'failed' and the error is logged.
    """
    logger.info(f"[Processor] Starting pipeline for call_id={call_id}")

    # ── 1. Fetch the call record ──────────────────────────────────────────
    try:
        rows = await execute_query("SELECT * FROM calls WHERE id = ?", (call_id,))
        if not rows:
            logger.error(f"[Processor] Call {call_id} not found in database.")
            return
        call = rows[0]
        audio_path = call["audio_path"]

        if not audio_path:
            logger.error(f"[Processor] Call {call_id} has no audio_path.")
            await execute_write(
                "UPDATE calls SET status = 'failed' WHERE id = ?", (call_id,)
            )
            return
    except Exception as e:
        logger.exception(f"[Processor] DB read error for call {call_id}: {e}")
        return

    # ── 2. Transcription ─────────────────────────────────────────────────
    try:
        await execute_write(
            "UPDATE calls SET status = 'transcribing' WHERE id = ?", (call_id,)
        )
        logger.info(f"[Processor] Transcribing call {call_id} — file: {audio_path}")

        transcript = await transcribe_audio(audio_path)

        await execute_write(
            "UPDATE calls SET transcript = ?, status = 'transcribed' WHERE id = ?",
            (transcript, call_id),
        )
        logger.info(f"[Processor] Call {call_id} transcribed ({len(transcript)} chars).")
    except Exception as e:
        logger.exception(f"[Processor] Transcription failed for call {call_id}: {e}")
        await execute_write(
            "UPDATE calls SET status = 'failed' WHERE id = ?", (call_id,)
        )
        return

    # ── 3. Summarization ─────────────────────────────────────────────────
    try:
        await execute_write(
            "UPDATE calls SET status = 'summarizing' WHERE id = ?", (call_id,)
        )
        logger.info(f"[Processor] Summarizing call {call_id}...")

        result = await summarize_transcript(transcript)

        await execute_write(
            """UPDATE calls
               SET summary      = ?,
                   key_points   = ?,
                   action_items = ?,
                   status       = 'done'
               WHERE id = ?""",
            (
                result["summary"],
                json.dumps(result["key_points"], ensure_ascii=False),
                json.dumps(result["action_items"], ensure_ascii=False),
                call_id,
            ),
        )
        logger.info(f"[Processor] Call {call_id} processing complete ✓")
    except Exception as e:
        logger.exception(f"[Processor] Summarization failed for call {call_id}: {e}")
        # Transcript was already saved; just mark as failed so user sees partial data
        await execute_write(
            "UPDATE calls SET status = 'failed' WHERE id = ?", (call_id,)
        )
