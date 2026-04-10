import asyncio
import json
import logging
from groq import Groq
from config import settings

logger = logging.getLogger(__name__)

# Initialize Groq client once at module level
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


SUMMARIZATION_PROMPT = """\
You are a professional call assistant. Analyze this phone call transcript and provide a structured analysis.

Respond ONLY in the following JSON format, with no extra text or markdown:
{{
  "summary": "A concise 2-3 sentence summary of what the call was about.",
  "key_points": ["Most important point 1", "Most important point 2", "...up to 7 points"],
  "action_items": ["Follow-up task 1", "Follow-up task 2"]
}}

Rules:
- key_points: 3 to 7 bullet points of the most important things discussed
- action_items: specific follow-up tasks or commitments made. If none, return an empty array []
- Maintain the original language of the conversation (Arabic/English)
- Always cite specific details (numbers, dates, names) when mentioned

Transcript:
\"\"\"
{transcript}
\"\"\"\
"""


async def summarize_transcript(transcript: str) -> dict:
    """
    Summarize a call transcript using Groq API (llama3-8b, free tier).

    Args:
        transcript: Full text transcript of the call.

    Returns:
        dict with keys: summary (str), key_points (list[str]), action_items (list[str])
    """
    if not transcript or len(transcript.strip()) < 20:
        logger.warning("Transcript too short to summarize.")
        return {
            "summary": "Call too short or empty to summarize.",
            "key_points": [],
            "action_items": [],
        }

    prompt = SUMMARIZATION_PROMPT.format(transcript=transcript)

    def _call_groq() -> str:
        client = _get_client()
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert call summarizer. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    loop = asyncio.get_event_loop()

    try:
        raw = await loop.run_in_executor(None, _call_groq)
        parsed = json.loads(raw)
        return {
            "summary": parsed.get("summary", ""),
            "key_points": parsed.get("key_points", []),
            "action_items": parsed.get("action_items", []),
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Groq JSON response: {e}")
        raw_text = raw if isinstance(raw, str) else "Summarization failed."
        return {
            "summary": raw_text[:500],
            "key_points": [],
            "action_items": [],
        }
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise
