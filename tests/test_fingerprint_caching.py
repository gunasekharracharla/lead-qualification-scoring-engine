import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_leads_cache.db")
os.environ["AI_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from backend.database.database import SessionLocal
from backend.database.repository import delete_all_lead_records
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_test_db():
    db = SessionLocal()
    try:
        delete_all_lead_records(db)
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        delete_all_lead_records(db)
    finally:
        db.close()


_MICHAEL = {
    "name": "Michael Johnson", "company": "AI Solutions Pvt Ltd", "job_title": "CEO",
    "country": "United States", "industry": "SaaS", "company_size": 120,
    "pain_point": "Manual lead qualification is taking too much time",
    "buying_signal": "Currently looking for AI automation for the sales process",
    "recent_activity": True,
}


def test_first_submission_creates_new_lead_not_cached():
    res = client.post("/qualify-lead", json=_MICHAEL)
    assert res.status_code == 200
    body = res.json()
    assert body["cached"] is False
    assert body["lead"]["id"] is not None


def test_identical_resubmission_returns_same_lead_id_and_is_cached():
    first = client.post("/qualify-lead", json=_MICHAEL).json()
    second = client.post("/qualify-lead", json=_MICHAEL).json()

    assert second["cached"] is True
    assert second["qualification_source"] == "database"
    assert second["lead"]["id"] == first["lead"]["id"]
    assert second["qualification"]["score"] == first["qualification"]["score"]


def test_changed_field_reuses_lead_id_but_recalculates_score():
    first = client.post("/qualify-lead", json=_MICHAEL).json()

    changed = dict(_MICHAEL)
    changed["buying_signal"] = None
    second = client.post("/qualify-lead", json=changed).json()

    assert second["cached"] is False
    assert second["lead"]["id"] == first["lead"]["id"]  # same Lead ID, same real person
    assert second["qualification"]["score"] < first["qualification"]["score"]


def test_different_lead_gets_different_lead_id():
    first = client.post("/qualify-lead", json=_MICHAEL).json()

    other = {"name": "Someone Else", "company": "Other Company"}
    second = client.post("/qualify-lead", json=other).json()

    assert second["lead"]["id"] != first["lead"]["id"]
