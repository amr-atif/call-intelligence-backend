import asyncio
import logging
from config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — loaded once at first use to avoid startup delay
_model = None


def _load_model():
    """Load the faster-whisper model (synchronous, cached as singleton)."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info(f"Loading faster-whisper model '{settings.WHISPER_MODEL_SIZE}'...")
        # device="cpu", compute_type="int8" → best for CPU-only servers (low memory)
        _model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8",
        )
        logger.info("faster-whisper model loaded successfully.")
    return _model


async def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe an audio file to text using faster-whisper (local, free).

    Uses CTranslate2 backend — 2-4x faster than openai-whisper on CPU,
    lower memory usage with int8 quantization.

    Runs in a thread pool executor to avoid blocking the async event loop,
    since inference is CPU-bound.

    Args:
        audio_path: Absolute path to the audio file (.wav, .m4a, .amr, etc.)

    Returns:
        Full transcript text as a string.
    """
    def _run() -> str:
        model = _load_model()
        # language=None → auto-detect Arabic + English
        segments, info = model.transcribe(
            str(audio_path),
            language=None,
            beam_size=5,
        )
        logger.info(
            f"Detected language: {info.language} "
            f"(probability: {info.language_probability:.2f})"
        )
        # segments is a generator — must be consumed here (inside executor thread)
        full_text = " ".join(segment.text for segment in segments)
        return full_text.strip()

    loop = asyncio.get_event_loop()
    transcript = await loop.run_in_executor(None, _run)
    return transcript
