from backend.schemas.lead_schema import LeadCreate
from backend.services.analysis_service import analyze_lead


def _hot_lead(**overrides):
    base = dict(
        name="John Smith", company="ABC SaaS", job_title="Founder",
        country="United States", industry="SaaS", company_size=50,
        pain_point="Manual lead qualification and sales follow-up are taking too much time.",
        buying_signal="We are actively evaluating automation vendors.",
    )
    base.update(overrides)
    return LeadCreate(**base)


def test_strong_lead_classifies_hot(monkeypatch):
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", False)
    result = analyze_lead(_hot_lead())
    assert result["score"] >= 80
    assert result["classification"] == "HOT"
    assert result["icp_fit"] is True


def test_removing_buying_signal_drops_score_by_exactly_its_weight(monkeypatch):
    """This is the CTO's specific requested test: remove ONLY the buying
    signal from a HOT lead and confirm the score drops by exactly the
    configured weight (20 points), moving HOT -> WARM."""
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", False)

    hot_result = analyze_lead(_hot_lead())
    warm_result = analyze_lead(_hot_lead(buying_signal=None))

    assert hot_result["score"] - warm_result["score"] == 20
    assert hot_result["classification"] == "HOT"
    assert warm_result["classification"] == "WARM"
    assert "Buying signal" in warm_result["failed_criteria"]


def test_removing_pain_point_also_drops_score(monkeypatch):
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", False)
    full_result = analyze_lead(_hot_lead())
    no_pain_result = analyze_lead(_hot_lead(pain_point=None))
    assert no_pain_result["score"] < full_result["score"]


def test_poor_fit_lead_classifies_cold(monkeypatch):
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", False)
    lead = LeadCreate(
        name="Anil Kumar", company="Sunrise Clinic", job_title="Engineer",
        country="India", industry="Healthcare", company_size=5,
    )
    result = analyze_lead(lead)
    assert result["classification"] == "COLD"
    assert result["icp_fit"] is False
    assert result["qualified"] is False


def test_five_lead_spread_is_not_flat(monkeypatch):
    """Regression guard against the original bug where every lead scored 100."""
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", False)

    leads = [
        _hot_lead(),
        _hot_lead(name="Emma Clarke", company="NorthPeak", country="United Kingdom", industry="Technology", company_size=100),
        _hot_lead(name="Raj Patel", company="CloudDesk", company_size=40, buying_signal=None),
        _hot_lead(name="Sophie Turner", company="BrightPath", country="United Kingdom", buying_signal=None),
        LeadCreate(name="Anil Kumar", company="Sunrise Clinic", country="India", industry="Healthcare", company_size=5),
    ]
    scores = [analyze_lead(lead)["score"] for lead in leads]
    assert len(set(scores)) > 1, "All leads scored identically - scoring is not differentiating"
    assert min(scores) < 60
    assert max(scores) >= 80


def test_optional_custom_offer_auto_generated_when_not_supplied(monkeypatch):
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", False)
    result = analyze_lead(_hot_lead(custom_offer=None))
    assert result["recommended_offer"]  # non-empty, auto-generated


def test_custom_offer_override_respected_when_supplied(monkeypatch):
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", False)
    result = analyze_lead(_hot_lead(custom_offer="Custom Enterprise Package"))
    assert result["recommended_offer"] == "Custom Enterprise Package"
