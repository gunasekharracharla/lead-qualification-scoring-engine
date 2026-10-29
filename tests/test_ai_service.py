from backend.schemas.lead_schema import LeadCreate
from backend.services.ai_service import assess_lead


def _lead(**overrides):
    base = dict(name="John Smith", company="TechFlow", industry="SaaS", job_title="Founder")
    base.update(overrides)
    return LeadCreate(**base)


def test_ai_fallback_returns_all_required_keys(monkeypatch):
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", False)
    lead = _lead(pain_point="Manual lead qualification", buying_signal="Evaluating automation")
    result = assess_lead(lead)
    for key in [
        "industry_relevance", "decision_maker_relevance", "pain_point_relevant",
        "buying_signal_present", "automation_opportunity", "recent_activity",
        "pain_points", "buying_signals", "reasoning", "recommended_action",
    ]:
        assert key in result
    assert result["assessment_source"] == "fallback"


def test_ai_fallback_does_not_invent_missing_data(monkeypatch):
    """Hallucination guard: if no pain point / buying signal is given, the
    fallback must not report them as present."""
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", False)
    lead = _lead(pain_point=None, buying_signal=None)
    result = assess_lead(lead)
    assert result["pain_point_relevant"] is False
    assert result["buying_signal_present"] is False
    assert result["pain_points"] == []
    assert result["buying_signals"] == []


def test_ai_disabled_never_crashes():
    lead = _lead()
    result = assess_lead(lead)
    assert isinstance(result, dict)


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeChatResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeChatResponse(self._content)


class _FakeChat:
    def __init__(self, **kwargs):
        self.completions = _FakeCompletions(**kwargs)


class _FakeClient:
    """Stand-in for the openai.OpenAI client used by ai_service, so a
    simulated provider failure/bad response can be tested without a real
    network call or API key."""

    def __init__(self, **kwargs):
        self.chat = _FakeChat(**kwargs)


def test_ai_provider_exception_falls_back_safely(monkeypatch):
    """Simulates a Groq/network failure while AI is enabled: assess_lead
    must never raise and must return the deterministic fallback."""
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", True)
    fake_client = _FakeClient(raise_exc=RuntimeError("simulated network timeout"))
    monkeypatch.setattr(
        "backend.services.ai_service._client_and_model",
        lambda: (fake_client, "fake-model", "openai_compatible"),
    )
    lead = _lead(pain_point="Manual process", buying_signal="Evaluating vendors")
    result = assess_lead(lead)
    assert result["assessment_source"] == "fallback"
    assert isinstance(result, dict)


def test_ai_invalid_json_response_falls_back_safely(monkeypatch):
    """Simulates the LLM returning malformed/non-JSON content: assess_lead
    must catch the parse failure and fall back rather than crash the request."""
    monkeypatch.setattr("backend.services.ai_service.settings.AI_ENABLED", True)
    fake_client = _FakeClient(content="this is not valid json {{{")
    monkeypatch.setattr(
        "backend.services.ai_service._client_and_model",
        lambda: (fake_client, "fake-model", "openai_compatible"),
    )
    lead = _lead()
    result = assess_lead(lead)
    assert result["assessment_source"] == "fallback"
