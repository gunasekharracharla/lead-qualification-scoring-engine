import os

os.environ["DATABASE_URL"] = "sqlite:///./test_leads.db"
os.environ["AI_ENABLED"] = "false"

import pytest
from sqlalchemy import create_engine, inspect, text
from fastapi.testclient import TestClient

import backend.database.database as database
from backend.database.database import SessionLocal
from backend.database.repository import delete_all_lead_records
from backend.main import app

client = TestClient(app)


def test_legacy_offer_column_migrates_without_losing_value(monkeypatch):
    migration_engine = create_engine("sqlite://")
    with migration_engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE leads (id INTEGER PRIMARY KEY, mnrathi_offer VARCHAR(200))"
        ))
        connection.execute(text(
            "INSERT INTO leads (id, mnrathi_offer) VALUES (1, 'Existing offer')"
        ))

    monkeypatch.setattr(database, "engine", migration_engine)
    try:
        database.run_light_migrations()
        columns = {column["name"] for column in inspect(migration_engine).get_columns("leads")}
        with migration_engine.connect() as connection:
            offer = connection.execute(
                text("SELECT custom_offer FROM leads WHERE id = 1")
            ).scalar_one()
            status = connection.execute(
                text("SELECT status FROM leads WHERE id = 1")
            ).scalar_one()
        assert "custom_offer" in columns
        assert "mnrathi_offer" not in columns
        assert offer == "Existing offer"
        assert status == "New"
    finally:
        migration_engine.dispose()


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


def test_health_endpoint_returns_expected_shape():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    for key in ["status", "ai_enabled_flag", "ai_provider", "ai_model", "llm_enabled", "database"]:
        assert key in body


def test_qualify_lead_happy_path():
    payload = {
        "name": "John Smith", "company": "ABC SaaS", "job_title": "Founder",
        "country": "United States", "industry": "SaaS", "company_size": 50,
        "pain_point": "Manual lead qualification.", "buying_signal": "Evaluating vendors.",
    }
    res = client.post("/qualify-lead", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["qualification"]["score"] is not None
    assert body["lead"]["id"] is not None


def test_custom_offer_round_trips_through_api():
    response = client.post("/qualify-lead", json={
        "name": "Offer Test",
        "company": "OfferCo",
        "custom_offer": "Custom Enterprise Package",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["lead"]["custom_offer"] == "Custom Enterprise Package"
    assert body["qualification"]["recommended_offer"] == "Custom Enterprise Package"


def test_website_research_is_persisted_and_returned(monkeypatch):
    research = {
        "website_summary": "The company builds inventory software.",
        "website_sources": ["https://example.com/", "https://example.com/about"],
    }
    monkeypatch.setattr("backend.services.analysis_service.build_research", lambda lead: research)

    created = client.post("/qualify-lead", json={"name": "Research Test", "company": "ResearchCo"})
    assert created.status_code == 200
    expected = {
        "summary": "The company builds inventory software.",
        "sources": ["https://example.com/", "https://example.com/about"],
    }
    assert created.json()["qualification"]["website_research"] == expected

    lead_id = created.json()["lead"]["id"]
    fetched = client.get(f"/leads/{lead_id}")
    assert fetched.status_code == 200
    assert fetched.json()["qualification"]["website_research"] == expected


def test_qualify_lead_missing_required_field_returns_422():
    res = client.post("/qualify-lead", json={"company": "ABC SaaS"})  # missing name
    assert res.status_code == 422


def test_qualify_lead_minimal_input_does_not_crash():
    """Only name + company supplied - everything else optional."""
    res = client.post("/qualify-lead", json={"name": "Jane Doe", "company": "Acme"})
    assert res.status_code == 200
    assert res.json()["qualification"]["classification"] in ("HOT", "WARM", "COLD")


def test_get_lead_by_id_returns_persisted_result():
    create_res = client.post("/qualify-lead", json={"name": "Persist Test", "company": "PersistCo"})
    lead_id = create_res.json()["lead"]["id"]

    get_res = client.get(f"/leads/{lead_id}")
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["lead"]["name"] == "Persist Test"
    assert body["qualification"]["score"] is not None


def test_get_nonexistent_lead_returns_404():
    res = client.get("/leads/999999")
    assert res.status_code == 404


def test_list_leads_returns_array():
    res = client.get("/leads")
    assert res.status_code == 200
    assert isinstance(res.json()["leads"], list)


def test_qualification_response_has_no_confidence_field():
    payload = {
        "name": "No Confidence Test", "company": "ConfCo", "job_title": "CEO",
        "country": "United States", "industry": "SaaS", "company_size": 50,
        "pain_point": "Manual, repetitive lead triage.", "buying_signal": "Evaluating vendors now.",
        "recent_activity": True,
    }
    res = client.post("/qualify-lead", json=payload)
    assert res.status_code == 200
    body_str = res.text
    assert "ai_confidence" not in body_str
    assert '"confidence"' not in body_str
    q = res.json()["qualification"]
    for field in ["recommended_team", "expected_revenue", "probability", "offer_reason", "ai_insights"]:
        assert field in q


def test_invalid_company_size_zero_rejected():
    res = client.post("/qualify-lead", json={"name": "A", "company": "B", "company_size": 0})
    assert res.status_code == 422


def test_invalid_company_size_negative_rejected():
    res = client.post("/qualify-lead", json={"name": "A", "company": "B", "company_size": -20})
    assert res.status_code == 422


def test_invalid_company_size_string_rejected():
    res = client.post("/qualify-lead", json={"name": "A", "company": "B", "company_size": "120"})
    assert res.status_code == 422


def test_invalid_recent_activity_string_rejected():
    res = client.post("/qualify-lead", json={"name": "A", "company": "B", "recent_activity": "yes"})
    assert res.status_code == 422


def test_valid_positive_company_size_accepted():
    res = client.post("/qualify-lead", json={"name": "A", "company": "B", "company_size": 120})
    assert res.status_code == 200


def test_get_qualification_by_lead_id_endpoint():
    create_res = client.post("/qualify-lead", json={"name": "Qual Endpoint Test", "company": "QualCo"})
    lead_id = create_res.json()["lead"]["id"]

    res = client.get(f"/leads/{lead_id}/qualification")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["qualification"]["lead_id"] == lead_id
    assert body["qualification"]["score"] is not None


def test_get_qualification_for_nonexistent_lead_returns_404():
    res = client.get("/leads/999999/qualification")
    assert res.status_code == 404


def test_lead_includes_created_and_updated_timestamps():
    """The frontend's lead list/detail views need created_at/updated_at to
    show real Created/Updated dates instead of dummy values."""
    res = client.post("/qualify-lead", json={"name": "Timestamp Test", "company": "TimeCo"})
    assert res.status_code == 200
    lead = res.json()["lead"]
    assert lead["created_at"] is not None
    assert lead["updated_at"] is not None

    list_res = client.get("/leads")
    assert list_res.status_code == 200
    listed = next(l for l in list_res.json()["leads"] if l["id"] == res.json()["lead"]["id"])
    assert listed["created_at"] is not None
    assert listed["updated_at"] is not None


def test_lead_workflow_status_can_be_updated_and_is_validated():
    created = client.post("/qualify-lead", json={"name": "Status Test", "company": "StatusCo"})
    lead_id = created.json()["lead"]["id"]
    assert created.json()["lead"]["status"] == "New"

    updated = client.patch(f"/leads/{lead_id}/status", json={"status": "Contacted"})
    assert updated.status_code == 200
    assert updated.json()["lead"]["status"] == "Contacted"

    listed = client.get("/leads").json()["leads"]
    assert next(lead for lead in listed if lead["id"] == lead_id)["status"] == "Contacted"
    assert client.patch(f"/leads/{lead_id}/status", json={"status": "Unknown"}).status_code == 422
    assert client.patch("/leads/999999/status", json={"status": "Qualified"}).status_code == 404


def test_qualification_history_preserves_runs_and_skips_cached_submissions():
    payload = {
        "name": "History Test",
        "company": "HistoryCo",
        "industry": "SaaS",
        "company_size": 80,
    }
    first = client.post("/qualify-lead", json=payload).json()
    lead_id = first["lead"]["id"]

    cached = client.post("/qualify-lead", json=payload).json()
    assert cached["cached"] is True
    history = client.get(f"/leads/{lead_id}/qualification-history").json()["history"]
    assert len(history) == 1
    assert history[0]["qualification"]["score"] == first["qualification"]["score"]
    assert history[0]["lead"]["company_size"] == 80
    assert len(history[0]["rules_version"]) == 64

    changed = {**payload, "company_size": 20}
    second = client.post("/qualify-lead", json=changed).json()
    history = client.get(f"/leads/{lead_id}/qualification-history").json()["history"]
    assert len(history) == 2
    assert history[0]["qualification"]["score"] == second["qualification"]["score"]
    assert history[1]["qualification"]["score"] == first["qualification"]["score"]

    edited = client.put(f"/leads/{lead_id}", json={"company_size": 30})
    assert edited.status_code == 200
    history = client.get(f"/leads/{lead_id}/qualification-history").json()["history"]
    assert len(history) == 3
    assert history[0]["qualification"]["score"] == edited.json()["qualification"]["score"]


def test_qualification_history_for_missing_lead_returns_404():
    assert client.get("/leads/999999/qualification-history").status_code == 404


_SALES_PLAN_KEYS = [
    "next_action", "approach", "communication_strategy", "meeting_objective",
    "talking_points", "discovery_questions", "pain_points_to_validate",
    "recommended_offer", "recommended_team", "possible_objections",
    "objection_handling", "after_meeting_actions", "information_to_collect",
    "success_criteria", "follow_up_plan",
]


def test_qualify_lead_returns_sales_action_plan():
    """A HOT lead: full sales_action_plan must be present with every field
    the frontend renders, and it must line up with the deterministic
    next_action / recommended_offer rather than contradicting them."""
    payload = {
        "name": "Hot Lead Test", "company": "HotCo", "job_title": "Founder",
        "country": "United States", "industry": "SaaS", "company_size": 80,
        "pain_point": "Manual, repetitive lead qualification and follow-up.",
        "buying_signal": "Actively evaluating automation vendors this quarter.",
        "recent_activity": True,
    }
    res = client.post("/qualify-lead", json=payload)
    assert res.status_code == 200
    body = res.json()
    q = body["qualification"]
    assert "sales_action_plan" in q
    plan = q["sales_action_plan"]
    for key in _SALES_PLAN_KEYS:
        assert key in plan, f"missing sales_action_plan.{key}"
    assert plan["next_action"] == q["next_action"]
    assert plan["recommended_offer"] == q["recommended_offer"]


def test_sales_action_plan_is_persisted_and_retrievable_by_lead_id():
    payload = {
        "name": "Plan Persist Test", "company": "PlanPersistCo", "job_title": "CTO",
        "country": "United States", "industry": "SaaS", "company_size": 40,
        "pain_point": "Slow manual sales follow-up.", "buying_signal": "Comparing vendors now.",
    }
    create_res = client.post("/qualify-lead", json=payload)
    assert create_res.status_code == 200
    lead_id = create_res.json()["lead"]["id"]
    created_plan = create_res.json()["qualification"]["sales_action_plan"]
    assert created_plan is not None

    get_res = client.get(f"/leads/{lead_id}")
    assert get_res.status_code == 200
    fetched_plan = get_res.json()["qualification"]["sales_action_plan"]
    assert fetched_plan == created_plan

    qual_res = client.get(f"/leads/{lead_id}/qualification")
    assert qual_res.status_code == 200
    assert qual_res.json()["qualification"]["sales_action_plan"] == created_plan


def test_sales_action_plan_has_no_confidence_field():
    payload = {"name": "No Conf Plan", "company": "NoConfCo", "job_title": "CEO"}
    res = client.post("/qualify-lead", json=payload)
    assert res.status_code == 200
    assert '"confidence"' not in res.text
    assert "ai_confidence" not in res.text


def test_qualification_persists_and_is_retrievable_after_reload():
    """
    Simulates a backend restart: re-imports a fresh TestClient bound to the
    same DATABASE_URL, which re-runs Base.metadata.create_all() and
    run_light_migrations() exactly as a real process restart would, then
    reads the qualification back purely from the database.
    """
    create_res = client.post("/qualify-lead", json={
        "name": "Restart Test", "company": "RestartCo", "job_title": "CEO",
        "country": "United States", "industry": "SaaS", "company_size": 50,
        "pain_point": "Manual repetitive process.", "buying_signal": "Evaluating now.",
    })
    lead_id = create_res.json()["lead"]["id"]
    original_score = create_res.json()["qualification"]["score"]

    from fastapi.testclient import TestClient as _TestClient
    from backend.main import app as _reloaded_app
    fresh_client = _TestClient(_reloaded_app)

    res = fresh_client.get(f"/leads/{lead_id}/qualification")
    assert res.status_code == 200
    assert res.json()["qualification"]["score"] == original_score
