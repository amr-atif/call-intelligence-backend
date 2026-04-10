import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers import calls, contacts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    # ── Startup ───────────────────────────────────
    logger.info("Starting Call Intelligence API...")
    os.makedirs(settings.AUDIO_STORAGE_DIR, exist_ok=True)
    await init_db()
    logger.info(f"Audio storage: {settings.AUDIO_STORAGE_DIR}")
    logger.info(f"Database:      {settings.DATABASE_PATH}")
    logger.info("Ready ✓")
    yield
    # ── Shutdown ──────────────────────────────────
    logger.info("Shutting down.")


app = FastAPI(
    title="Call Intelligence API",
    description=(
        "Backend for the Call Intelligence Assistant. "
        "Upload call recordings and get AI-generated transcripts and summaries."
    ),
    version="1.0.0",
    lifespan=lifespan,
    # Explicit server URL so Swagger UI sends requests to http://localhost:8000
    # instead of a schemeless URL (which causes the "CORS / Failed to fetch" error).
    servers=[{"url": "http://localhost:8000", "description": "Local dev server"}],
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow all origins in development so the React Native app can connect.
# Restrict this to specific origins before any deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(calls.router, prefix="/calls", tags=["Calls"])
app.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """Quick liveness check for monitoring and mobile app connectivity tests."""
    return {"status": "ok", "version": "1.0.0"}
