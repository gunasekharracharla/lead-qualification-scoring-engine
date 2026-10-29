from backend.schemas.lead_schema import LeadCreate
from backend.schemas.sales_action_plan_schema import SalesActionPlan
from backend.services.sales_plan_service import generate_sales_action_plan

_PLAN_KEYS = [
    "next_action", "approach", "communication_strategy", "meeting_objective",
    "talking_points", "discovery_questions", "pain_points_to_validate",
    "recommended_offer", "recommended_team", "possible_objections",
    "objection_handling", "after_meeting_actions", "information_to_collect",
    "success_criteria", "follow_up_plan",
]


def _lead(**overrides):
    base = dict(name="John Smith", company="TechFlow", industry="SaaS", job_title="Founder")
    base.update(overrides)
    return LeadCreate(**base)


def _qualification(**overrides):
    base = dict(
        score=85, classification="HOT", qualified=True, icp_fit=True,
        buying_intent="High", matched_criteria=["Target industry"], failed_criteria=[],
        pain_points=["Manual lead qualification"], buying_signals=["Evaluating vendors"],
        recommended_offer="AI Lead-to-Sales Automation",
        next_action="Contact within 24 hours and schedule a sales/demo call.",
        reason="The lead received 85/100 (HOT).",
    )
    base.update(overrides)
    return base


def test_fallback_plan_has_all_required_keys(monkeypatch):
    monkeypatch.setattr("backend.services.sales_plan_service.settings.AI_ENABLED", False)
    lead = _lead(pain_point="Manual lead qualification", buying_signal="Evaluating automation")
    plan = generate_sales_action_plan(lead, _qualification())
    for key in _PLAN_KEYS:
        assert key in plan
    assert plan["assessment_source"] == "fallback"


def test_fallback_plan_next_action_and_offer_match_qualification(monkeypatch):
    """The plan must never contradict the deterministic engine's own
    next_action / recommended_offer."""
    monkeypatch.setattr("backend.services.sales_plan_service.settings.AI_ENABLED", False)
    lead = _lead()
    qualification = _qualification(
        next_action="Contact within 24 hours and schedule a sales/demo call.",
        recommended_offer="AI Lead-to-Sales Automation",
    )
    plan = generate_sales_action_plan(lead, qualification)
    assert plan["next_action"] == qualification["next_action"]
    assert plan["recommended_offer"] == qualification["recommended_offer"]


def test_fallback_plan_validates_against_schema(monkeypatch):
    monkeypatch.setattr("backend.services.sales_plan_service.settings.AI_ENABLED", False)
    lead = _lead(pain_point="Manual process", buying_signal="Evaluating vendors", company_size=50)
    plan = generate_sales_action_plan(lead, _qualification())
    validated = SalesActionPlan(**{k: v for k, v in plan.items() if k != "assessment_source"})
    assert validated.next_action
    assert validated.recommended_offer


def test_fallback_never_crashes_on_minimal_lead(monkeypatch):
    monkeypatch.setattr("backend.services.sales_plan_service.settings.AI_ENABLED", False)
    lead = _lead(name="Jane Doe", company="Acme", industry=None, job_title=None)
    plan = generate_sales_action_plan(lead, _qualification(classification="COLD", score=20))
    assert isinstance(plan, dict)
    assert plan["follow_up_plan"]


def test_schema_rejects_missing_required_field():
    import pytest
    data = {
        "next_action": "Call now", "approach": "Consultative", "communication_strategy": "Consultative",
        "meeting_objective": "Confirm pain point",
        # "recommended_offer" intentionally omitted
        "follow_up_plan": "Follow up in 24 hours",
    }
    with pytest.raises(Exception):
        SalesActionPlan(**data)


def test_schema_coerces_string_list_fields():
    data = {
        "next_action": "Call now", "approach": "Consultative", "communication_strategy": "Consultative",
        "meeting_objective": "Confirm pain point", "recommended_offer": "AI Automation",
        "follow_up_plan": "Follow up in 24 hours",
        "talking_points": "Single point as a bare string",
    }
    plan = SalesActionPlan(**data)
    assert plan.talking_points == ["Single point as a bare string"]
