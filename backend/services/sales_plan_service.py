import json
import logging

from pydantic import ValidationError

from backend.config.settings import settings
from backend.schemas.sales_action_plan_schema import SalesActionPlan

logger = logging.getLogger("lead_sales_plan")

SYSTEM_PROMPT = """You are a B2B sales enablement assistant for an AI automation company.

You will receive one lead's raw data AND the qualification result already produced by a separate
deterministic scoring engine (score, classification, ICP fit, matched/failed criteria, pain
points, buying signals, recommended offer, next action). You may also receive a "research" object
alongside the lead with:
- website_summary: real text (page titles, descriptions, headings, and content excerpts) fetched
    from up to three relevant pages on the lead's company website. Use it to ground talking_points
    and discovery_questions in specific company details, not generic industry claims.
- website_sources: URLs of the fetched pages, provided only as source references.
- linkedin_hint: a NAME HINT ONLY, derived from the LinkedIn URL slug, NOT real profile content
  (LinkedIn blocks unauthenticated scraping) - never present it as a verified fact, only use it
  as a light naming cue if it adds anything at all.

Your ONLY job is to turn that into a concrete, lead-specific SALES ACTION PLAN for the rep who
owns this lead. You do not re-score or re-classify the lead - that decision has already been made
and is final.

Return ONLY a JSON object with exactly these keys:

- next_action: string - the immediate action the rep should take
- approach: string - how the rep should approach this specific lead (e.g. a consultative
  discovery approach, understanding current workflow before presenting the product)
- communication_strategy: string - a short label such as "Consultative", "Technical",
  "ROI-focused", "Executive-level", or "Discovery-first" (or a similarly short label that fits
  this lead better)
- meeting_objective: string - what the rep should accomplish during the first meeting
- talking_points: array of strings (2-6) - important topics to raise
- discovery_questions: array of strings (2-6) - specific questions to ask THIS lead, grounded in
  their actual industry, job title, pain point, buying signal, and company size wherever that
  data is available, AND in research.website_summary when present (ask about specifics you can
  see on their real site rather than generic questions)
- pain_points_to_validate: array of strings (1-6) - pain points to confirm during the conversation
- recommended_offer: string - the most relevant solution/offer
- recommended_team: array of strings (1-4) - internal roles/teams that should be involved,
  e.g. ["Sales", "RevOps", "Marketing"]
- possible_objections: array of strings (2-6) - objections this specific prospect may realistically
  raise (e.g. cost, CRM integration, AI accuracy, security, implementation timeline)
- objection_handling: array of strings, SAME LENGTH AND ORDER as possible_objections - one short
  recommended response/approach per objection, formatted as "<Objection>: <response>"
- after_meeting_actions: array of strings (2-6) - what the rep should do after the meeting
- information_to_collect: array of strings (1-6) - information still required before moving the
  lead forward that is NOT already present in the supplied lead data (e.g. current CRM, lead
  volume, sales team size, existing qualification workflow, budget, timeline)
- success_criteria: array of strings (2-5) - what would indicate the discovery meeting succeeded
- follow_up_plan: string - recommended follow-up timing and action

CRITICAL RULES:
1. Ground every talking point, discovery question, and objection in the ACTUAL supplied lead data,
   qualification result, and research.website_summary when present. Never invent a fact, pain
   point, technology, or buying signal that was not given to you, and never treat
   research.linkedin_hint as a verified fact - it is a name hint only.
2. Tailor tone, urgency, and depth to the classification and score you are given - a HOT lead
   gets an urgent, meeting-ready plan; a WARM lead gets a measured outreach plan; a COLD lead
   gets a lighter-touch nurture-oriented plan.
3. Do NOT return "score", "confidence", "ai_confidence", or any classification/qualification
   field - those are already decided and are not yours to set.
4. Every string field must be non-empty. Keep each string field concise (1-3 sentences).
5. Return ONLY the JSON object. No markdown, no commentary, no code fences.
"""


def _fallback(lead, qualification: dict) -> dict:
    """
    Safe deterministic fallback used when AI is disabled, unavailable, or its
    output fails schema validation. Never crashes the qualification flow -
    always returns a fully valid, lead-specific plan built from the actual
    lead fields and the actual qualification result (never static/dummy
    content), mirroring the _fallback() pattern in ai_service.py.
    """
    company = (lead.company or "the company").strip()
    industry = (lead.industry or "their industry").strip()
    title = (lead.job_title or "the contact").strip()
    pain_point = (lead.pain_point or "").strip()
    buying_signal = (lead.buying_signal or "").strip()
    size = lead.company_size

    classification = (qualification.get("classification") or "COLD").upper()
    offer = qualification.get("recommended_offer") or "AI automation assessment"
    next_action = qualification.get("next_action") or "Follow up with the lead to confirm interest and availability."

    talking_points = []
    if pain_point:
        talking_points.append(f"How '{pain_point.rstrip('.')}' is currently affecting {company}'s team")
    talking_points.append(f"What a strong outcome looks like for {title} at {company} this quarter")
    if buying_signal:
        talking_points.append(f"Their current evaluation status: {buying_signal.rstrip('.')}")
    talking_points.append(f"How the solution fits {company}'s existing workflow as a {industry} business")

    discovery_questions = [
        f"Walk me through how {company} currently handles this process today.",
        f"What prompted {title or 'your team'} to start looking into this now?",
    ]
    if pain_point:
        discovery_questions.append(f"How much time or cost is '{pain_point.rstrip('.')}' costing the team each week?")
    if size:
        discovery_questions.append(f"With a team of around {size} people, who else would be involved in a decision like this?")
    discovery_questions.append("What does success look like 90 days after go-live?")

    pain_points_to_validate = [pain_point] if pain_point else [
        f"Manual or inefficient processes typical of a {industry} company at this stage"
    ]

    possible_objections = ["Cost", "Implementation timeline", "CRM / tooling integration", "Data security"]
    objection_handling = [
        "Cost: anchor on the cost of the current manual process versus the offer's ROI timeline.",
        "Implementation timeline: propose a phased pilot so value is visible before a full rollout.",
        "CRM / tooling integration: confirm their current stack in discovery and reference supported integrations.",
        "Data security: share standard security/compliance documentation and offer a technical review call.",
    ]

    recommended_team = ["Sales"]
    if classification == "HOT":
        recommended_team += ["RevOps", "Solutions Engineering"]
    elif classification == "WARM":
        recommended_team.append("RevOps")

    approach = (
        f"Use a consultative discovery approach for this {classification.lower()} lead - understand "
        f"{company}'s current workflow as a {industry} company before presenting the product."
    )
    lower_title = title.lower()
    if any(t in lower_title for t in ["ceo", "founder", "coo", "president", "chief"]):
        communication_strategy = "Executive-level"
    elif any(t in lower_title for t in ["cto", "engineer", "vp eng", "head of engineering", "technical"]):
        communication_strategy = "Technical"
    else:
        communication_strategy = "Consultative"

    meeting_objective = f"Confirm {company}'s pain point, buying timeline, and stakeholders, and agree on concrete next steps."

    information_to_collect = [
        label for label, already_known in [
            ("Current CRM", False),
            ("Lead volume", False),
            ("Sales team size", size is not None),
            ("Existing qualification workflow", bool(pain_point)),
            ("Budget", False),
            ("Timeline", bool(buying_signal)),
        ] if not already_known
    ] or ["Budget", "Timeline"]

    if classification == "HOT":
        follow_up_plan = "Follow up within 24 hours with a meeting recap and a proposed next-step date."
    elif classification == "WARM":
        follow_up_plan = "Follow up within 3-5 business days with relevant resources and a check-in."
    else:
        follow_up_plan = "Add to a nurture sequence and re-engage in 30-60 days."

    return {
        "next_action": next_action,
        "approach": approach,
        "communication_strategy": communication_strategy,
        "meeting_objective": meeting_objective,
        "talking_points": talking_points[:6],
        "discovery_questions": discovery_questions[:6],
        "pain_points_to_validate": pain_points_to_validate[:6],
        "recommended_offer": offer,
        "recommended_team": recommended_team,
        "possible_objections": possible_objections,
        "objection_handling": objection_handling,
        "after_meeting_actions": [
            "Confirm requirements discussed on the call",
            "Define pilot/engagement scope",
            "Send a written proposal",
            "Schedule a technical/solutions discussion if needed",
            "Set a concrete follow-up date",
        ],
        "information_to_collect": information_to_collect,
        "success_criteria": [
            "Pain point and business impact confirmed in the prospect's own words",
            "Decision-making process and timeline understood",
            "Clear agreement on the next step and a date",
        ],
        "follow_up_plan": follow_up_plan,
        "assessment_source": "fallback",
    }


def _client_and_model():
    """
    Returns (client, model_name, kind) for whichever provider is configured,
    same provider/env config as ai_service.py. Built independently (rather
    than importing ai_service._client_and_model) because the Gemini branch
    needs a model instance bound to THIS module's SYSTEM_PROMPT, not
    ai_service's qualification-assessment prompt.
    """
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


def generate_sales_action_plan(lead, qualification: dict, research: dict | None = None) -> dict:
    """
    Hybrid architecture entry point for the sales action plan, mirroring
    ai_service.assess_lead(): the AI produces the lead-specific sales
    guidance, but next_action and recommended_offer are pinned to the values
    the deterministic scoring/recommendation engine already computed, so the
    plan can never contradict the rest of the qualification result. Never
    raises - always returns a valid, schema-conformant plan.

    `research` (optional) is the dict from research_service.build_research():
    real fetched website text plus a URL-derived LinkedIn name hint, used to
    ground discovery_questions/talking_points in real company specifics.
    """
    if not settings.AI_ENABLED:
        return _fallback(lead, qualification)

    client, model, kind = _client_and_model()
    if client is None:
        return _fallback(lead, qualification)

    payload = {
        "lead": lead.model_dump(mode="json"),
        "research": research or {},
        "qualification_result": {
            "score": qualification.get("score"),
            "classification": qualification.get("classification"),
            "qualified": qualification.get("qualified"),
            "icp_fit": qualification.get("icp_fit"),
            "buying_intent": qualification.get("buying_intent"),
            "matched_criteria": qualification.get("matched_criteria"),
            "failed_criteria": qualification.get("failed_criteria"),
            "pain_points": qualification.get("pain_points"),
            "buying_signals": qualification.get("buying_signals"),
            "recommended_offer": qualification.get("recommended_offer"),
            "next_action": qualification.get("next_action"),
            "reason": qualification.get("reason"),
        },
    }

    try:
        if kind == "openai_compatible":
            response = client.chat.completions.create(
                model=model,
                temperature=0.3,
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
                generation_config={"temperature": 0.3, "response_mime_type": "application/json"},
            )
            content = response.text or "{}"

        else:
            return _fallback(lead, qualification)

        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise ValueError("sales action plan response was not a JSON object")

        # Never let the LLM introduce a confidence-style field.
        raw.pop("confidence", None)
        raw.pop("ai_confidence", None)

        # Pin these two to the deterministic engine's own output so the plan
        # can never contradict the qualification result shown next to it.
        raw["next_action"] = qualification.get("next_action") or raw.get("next_action")
        raw["recommended_offer"] = qualification.get("recommended_offer") or raw.get("recommended_offer")

        plan = SalesActionPlan(**raw)  # raises ValidationError on any malformed/missing field
        result = plan.model_dump()
        result["assessment_source"] = "llm"
        return result

    except (json.JSONDecodeError, ValidationError, ValueError, KeyError, TypeError) as exc:
        logger.warning(f"Sales action plan validation failed ({exc.__class__.__name__}); using deterministic fallback.")
        return _fallback(lead, qualification)
    except Exception as exc:
        # Any provider/network/timeout failure -> safe fallback, never crash or hang the request
        logger.warning(f"Sales action plan generation failed ({exc.__class__.__name__}); using deterministic fallback.")
        return _fallback(lead, qualification)
