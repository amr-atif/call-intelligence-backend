# Call Intelligence Backend

Phase 1 Backend for the Call Intelligence Assistant.

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install ffmpeg (required by Whisper for audio conversion)
#    Windows:  choco install ffmpeg
#    Ubuntu:   sudo apt install ffmpeg
#    macOS:    brew install ffmpeg

# 4. Set your Groq API key in .env
#    Get a free key at: https://console.groq.com
GROQ_API_KEY=gsk_YOUR_KEY_HERE

# 5. Run the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Docs

Once running, visit: http://localhost:8000/docs

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Liveness check |
| POST | /calls/upload | Upload audio + metadata |
| GET | /calls | List calls (filter by phone, paginate) |
| GET | /calls/{id} | Full call detail + transcript |
| GET | /contacts | List contacts (with search) |
| GET | /contacts/{phone}/timeline | Chronological call history |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | **Yes** | — | Free at https://console.groq.com |
| `WHISPER_MODEL_SIZE` | No | `base` | `tiny`, `base`, `small`, `medium` |

## Project Structure

```
call-intelligence-backend/
├── main.py                 # FastAPI app entry point
├── config.py               # Settings (pydantic-settings + .env)
├── database.py             # SQLite init + async helpers
├── models.py               # Pydantic schemas
├── routers/
│   ├── calls.py            # /calls endpoints
│   └── contacts.py         # /contacts endpoints
├── services/
│   ├── transcription.py    # Whisper local transcription
│   ├── summarization.py    # Groq API summarization
│   └── processor.py        # Pipeline orchestrator
├── audio_storage/          # Created at startup
├── requirements.txt
└── .env                    # Add your GROQ_API_KEY here
```

## Test Upload (curl)

```bash
curl -X POST http://localhost:8000/calls/upload \
  -F "file=@test.wav" \
  -F "phone_number=+201234567890" \
  -F "direction=outgoing" \
  -F "recorded_at=2026-04-10T12:00:00" \
  -F "contact_name=Ahmed"
```
