import os
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # ---- AI provider selection: "groq" (current), "openai", or "gemini" (future) ----
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "groq").lower()
    AI_ENABLED: bool = _as_bool(os.getenv("AI_ENABLED", "true"))

    # Groq (OpenAI-compatible endpoint)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    # OpenAI (future option)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Gemini (future option)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Database - real SQL, defaults to local SQLite file, swap to Postgres via env var only
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./leads.db")
    if DATABASE_URL.startswith(("postgres://", "postgresql://")):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://", "postgresql+psycopg://", 1
        ).replace("postgresql://", "postgresql+psycopg://", 1)

    # CORS - not strictly needed since frontend+backend share an origin, but kept for flexibility
    CORS_ORIGINS = [x.strip() for x in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",") if x.strip()]

    APP_NAME: str = "Lead Qualification & Scoring Engine"
    APP_VERSION: str = "3.0.0"


settings = Settings()
