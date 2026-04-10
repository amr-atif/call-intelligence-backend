from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    AUDIO_STORAGE_DIR: Path = Path(__file__).resolve().parent / "audio_storage"
    DATABASE_PATH: Path = Path(__file__).resolve().parent / "call_intelligence.db"

    # Groq (free tier)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Whisper
    WHISPER_MODEL_SIZE: str = "base"  # options: tiny, base, small, medium

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
