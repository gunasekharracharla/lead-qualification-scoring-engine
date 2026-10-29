from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes.lead_routes import router as lead_router
from backend.config.settings import settings
from backend.database.database import Base, engine, run_light_migrations

Base.metadata.create_all(bind=engine)
run_light_migrations()

app = FastAPI(
    title=settings.APP_NAME,
    description="Hybrid AI assessment + deterministic lead qualification & scoring engine",
    version=settings.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes live under no prefix (e.g. /qualify-lead, /leads, /health) so the
# existing frontend JS calls work with simple relative paths.
app.include_router(lead_router)

# Serve the frontend as static files on the SAME app/port as the API.
# Visiting http://127.0.0.1:8000/ loads the UI; http://127.0.0.1:8000/docs
# still shows Swagger; http://127.0.0.1:8000/qualify-lead is the API.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
