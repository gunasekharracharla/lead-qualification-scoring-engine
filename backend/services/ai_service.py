import json
import logging

from backend.config.settings import settings

logger = logging.getLogger("lead_qualifier.ai")

SYSTEM_PROMPT = """You are a B2B lead qualification analyst for an AI automation company.

You will receive structured lead/company data. You may also receive a "research" object with:
- website_summary: real text (page titles, descriptions, headings, content excerpts, and source
    text) fetched from up to three relevant pages on the lead's company website. Treat it as
    grounded company context.
- website_sources: URLs of the fetched pages. These are source references, not additional facts.
- linkedin_hint: a NAME HINT ONLY, derived from the LinkedIn URL slug, NOT real profile content
  (LinkedIn blocks unauthenticated scraping) - never treat it as a verified fact about the person
  or company, only as a naming aid.

Assess it and return ONLY a JSON object with exactly these keys:

- industry_relevance: boolean - does the industry match a SaaS/software/technology/service business?
- decision_maker_relevance: boolean - does the job title indicate real purchasing authority
  (Founder, CEO, CTO, COO, VP, Director, Head of X)?
- pain_point_relevant: boolean - is there a stated pain point that automation could genuinely solve?
- buying_signal_present: boolean - is there an explicit statement of buying intent or evaluation activity?
- automation_opportunity: boolean - does the pain point describe a manual/repetitive process?
- recent_activity: boolean - is there explicit evidence of recent hiring, expansion, or relevant activity?
- pain_points: array of strings - the specific pain points found in the input, verbatim or lightly summarized
- buying_signals: array of strings - the specific buying signals found in the input
- reasoning: string - 2-3 sentences explaining your assessment, grounded ONLY in the supplied data
- recommended_action: string - a concrete, specific next step for the sales rep
- ai_insights: array of strings - 1-4 short qualitative observations about this lead that a sales
  rep would find useful (not a restatement of pain_points/buying_signals)
- recommendation: object with these string sub-fields (use "" if you don't have a grounded
  answer - never invent specifics):
    - offer_reason: why this offer/approach fits this lead
    - recommended_team: which internal team (e.g. "Sales", "Solutions Engineering") should own it
    - expected_revenue: a rough qualitative/quantitative revenue expectation
    - probability: "High", "Medium", or "Low" likelihood of closing

CRITICAL RULES:
1. Base every judgment ONLY on the data actually provided (including research.website_summary
   when present). Never invent a pain point, buying signal, technology, or fact that was not
   given to you. Never treat research.linkedin_hint as a verified fact - it is a name hint only.
2. If a field is missing or empty (e.g. no pain_point given), the corresponding boolean MUST be
   false and it must NOT appear in pain_points/buying_signals.
3. Do not guess company technology, funding, or headcount beyond what's supplied.
4. Do NOT return a "score", "confidence", or "ai_confidence" field. You do not decide the final
   score or classification - a separate deterministic engine does that from your booleans.
5. Return ONLY the JSON object. No markdown, no commentary, no code fences.
"""


def _fallback(lead) -> dict:
    """Safe deterministic fallback used when AI is disabled or the LLM call fails.
    Never crashes the qualification flow - always returns a valid structured result."""
    pain_point = (lead.pain_point or "").strip()
    buying_signal = (lead.buying_signal or "").strip()
    industry = (lead.industry or "").lower()
    title = (lead.job_title or "").lower()

    decision_titles = ["founder", "ceo", "cto", "coo", "vp", "director", "head of", "chief"]
    is_decision_maker = any(t in title for t in decision_titles)
    target_industries = ["saas", "software", "technology", "it services", "b2b", "ai"]
    is_target_industry = any(t in industry for t in target_industries)

    return {
        "industry_relevance": is_target_industry,
        "decision_maker_relevance": is_decision_maker,
        "pain_point_relevant": bool(pain_point),
        "buying_signal_present": bool(buying_signal),
        "automation_opportunity": bool(pain_point) and any(
            w in pain_point.lower() for w in ["manual", "repetitive", "time-consuming", "slow", "workload"]
        ),
        "recent_activity": bool(lead.recent_activity),
        "pain_points": [pain_point] if pain_point else [],
        "buying_signals": [buying_signal] if buying_signal else [],
        "reasoning": "AI assessment unavailable; deterministic fallback used based only on supplied fields.",
        "recommended_action": "Review the qualification result and follow the classification-based next action.",
        "ai_insights": [],
        "offer_reason": "",
        "recommended_team": "",
        "expected_revenue": "",
        "probability": "",
        "assessment_source": "fallback",
    }


def _normalize_ai_result(result: dict) -> dict:
    """
    Defensive normalization layer for whatever the LLM provider returns.

    Handles: nested `recommendation` object, top-level fields instead of nested,
    missing optional fields, and invalid/null recommendation - never crashes.
    Also strips confidence/ai_confidence wherever they appear (top-level or
    nested) so it can never leak into the normalized result, the database, or
    the API response, even if the provider still returns it.
    """
    if not isinstance(result, dict):
        return {}

    recommendation = result.get("recommendation", {})
    if not isinstance(recommendation, dict):
        recommendation = {}

    def _text(*candidates) -> str:
        for c in candidates:
            if isinstance(c, str) and c.strip():
                return c.strip()
        return ""

    result["offer_reason"] = _text(recommendation.get("offer_reason"), result.get("offer_reason"))
    result["recommended_team"] = _text(recommendation.get("recommended_team"), result.get("recommended_team"))
    result["expected_revenue"] = _text(recommendation.get("expected_revenue"), result.get("expected_revenue"))
    result["probability"] = _text(recommendation.get("probability"), result.get("probability"))

    insights = result.get("ai_insights", [])
    if isinstance(insights, str):
        insights = [insights] if insights.strip() else []
    elif not isinstance(insights, list):
        insights = []
    result["ai_insights"] = [str(i) for i in insights if str(i).strip()]

    # Confidence is not part of this system - never propagate it, from any location.
    result.pop("confidence", None)
    result.pop("ai_confidence", None)
    result.pop("recommendation", None)

    return result


def _client_and_model():
    """Returns (client, model_name, kind) for whichever provider is configured.
    kind is 'openai_compatible' or 'gemini' so assess_lead() knows how to call it."""
    provider = settings.AI_PROVIDER

    if provider == "groq":
        if not settings.GROQ_API_KEY:
            return None, None, None
        from openai import OpenAI
        return OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.GROQ_BASE_URL, timeout=20.0, max_retries=1), settings.GROQ_MODEL, "openai_compatible"

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            return None, None, None
        from openai import OpenAI
        return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=20.0, max_retries=1), settings.OPENAI_MODEL, "openai_compatible"

    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            return None, None, None
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL, system_instruction=SYSTEM_PROMPT)
        return model, settings.GEMINI_MODEL, "gemini"

    return None, None, None


def assess_lead(lead, research: dict | None = None) -> dict:
    """
    Hybrid architecture entry point: AI provides a structured assessment only.
    It does NOT calculate the final score - scoring_service.py does that
    deterministically from these boolean flags.

    `research` (optional) is the dict produced by research_service.build_research():
    real fetched website text plus a URL-derived LinkedIn name hint. When present
    it's included in the payload as extra grounded context - see SYSTEM_PROMPT.
    """
    if not settings.AI_ENABLED:
        return _fallback(lead)

    client, model, kind = _client_and_model()
    if client is None:
        return _fallback(lead)

    payload = lead.model_dump(mode="json")
    if research:
        payload["research"] = research

    try:
        if kind == "openai_compatible":
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            )
            content = response.choices[0].message.content or "{}"

        elif kind == "gemini":
            response = client.generate_content(
                json.dumps(payload, ensure_ascii=False),
                generation_config={"temperature": 0, "response_mime_type": "application/json"},
            )
            content = response.text or "{}"

        else:
            return _fallback(lead)

        result = json.loads(content)

        # Validate required keys exist; fill any gaps safely rather than trusting blindly
        required_bools = [
            "industry_relevance", "decision_maker_relevance", "pain_point_relevant",
            "buying_signal_present", "automation_opportunity", "recent_activity",
        ]
        for key in required_bools:
            result.setdefault(key, False)
        result.setdefault("pain_points", [])
        result.setdefault("buying_signals", [])
        result.setdefault("reasoning", "")
        result.setdefault("recommended_action", "")
        result = _normalize_ai_result(result)
        result["assessment_source"] = "llm"
        return result

    except Exception as exc:
        # Any provider/network/timeout/parsing failure -> safe fallback, never crash or hang the request
        logger.warning(f"Groq call failed ({exc.__class__.__name__}); using deterministic fallback.")
        return _fallback(lead)
