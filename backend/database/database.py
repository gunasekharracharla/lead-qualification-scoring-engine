import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config.settings import settings


def _migrate_legacy_database_file() -> None:
    if settings.DATABASE_URL != "sqlite:///./leads.db":
        return

    legacy_path = Path("mnrathi_leads.db")
    current_path = Path("leads.db")
    if not legacy_path.is_file() or current_path.exists():
        return

    source = sqlite3.connect(legacy_path)
    destination = sqlite3.connect(current_path)
    try:
        source.backup(destination)
    finally:
        source.close()
        destination.close()


_migrate_legacy_database_file()

# SQLite needs this special connect arg for multi-threaded FastAPI access.
# Any other DATABASE_URL (Postgres, MySQL) just works without it.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_light_migrations() -> None:
    """
    Rename the legacy custom-offer column and add model columns missing from an
    already-created table.

    Base.metadata.create_all() only creates missing TABLES, not missing
    COLUMNS on a table that already exists - so a pre-existing database file
    (e.g. a checked-in dev .db, or any long-lived environment) would otherwise
    keep its old schema forever and error out on the new qualification
    fields. This project has no Alembic setup, so a small ADD COLUMN pass is
    the lowest-risk way to extend the schema without dropping existing rows.
    Safe to call every startup: changes preserve existing rows and values.
    """
    inspector = inspect(engine)
    if "leads" not in inspector.get_table_names():
        return

    from backend.database.models import LeadRecord  # local import: avoid circular import

    existing_columns = {c["name"] for c in inspector.get_columns("leads")}
    if "mnrathi_offer" in existing_columns and "custom_offer" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE leads RENAME COLUMN "mnrathi_offer" TO "custom_offer"'))
        existing_columns.remove("mnrathi_offer")
        existing_columns.add("custom_offer")

    for column in LeadRecord.__table__.columns:
        if column.name in existing_columns:
            continue
        col_type = column.type.compile(engine.dialect)
        with engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE leads ADD COLUMN "{column.name}" {col_type}'))
