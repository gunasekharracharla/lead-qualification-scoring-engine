from backend.services.ai_service import assess_lead
from backend.services.icp_service import evaluate_icp_fit, company_size_ok
from backend.services.scoring_service import calculate_score, classify
from backend.services.recommendation_service import recommend, build_reason
from backend.services.research_service import build_research
from backend.services.sales_plan_service import generate_sales_action_plan


def analyze_lead(lead) -> dict:
    """
    The full hybrid pipeline, in order:
      0. Research (best-effort): fetch real text from the lead's website, plus a
         URL-derived LinkedIn name hint (LinkedIn blocks unauthenticated scraping,
         so no page content is fetched for it - see research_service.py). Run once
         and shared with both AI steps below so the site isn't fetched twice.
      1. AI assessment (interprets unstructured signals into structured booleans,
         grounded in research when available)
      2. ICP fit gate (deterministic, mandatory: country + industry + size) -
         a separate market-fit concept from scoring, exposed as its own
         icp_matches/icp_missing fields so it can never contradict
         matched_criteria/failed_criteria under the same label
      3. Deterministic scoring (weights from scoring_rules.json)
      4. Classification (HOT/WARM/COLD from configurable thresholds)
      5. Recommendation (offer + next action, respecting optional custom_offer override)
      6. Sales action plan (AI-generated, lead-specific sales guidance built on top of
         the already-finalized qualification result AND research - see sales_plan_service.py)

    Returns a single structured dict ready to persist and return via the API.
    """
    research = build_research(lead)
    ai_assessment = assess_lead(lead, research=research)
    icp_fit, icp_matches, icp_missing = evaluate_icp_fit(lead)
    size_fit = company_size_ok(lead)

    score, breakdown, matched_criteria, failed_criteria = calculate_score(ai_assessment, size_fit)
    classification = classify(score)

    offer, next_action = recommend(classification, lead)
    reason = build_reason(score, classification, matched_criteria, failed_criteria)

    qualified = icp_fit and score >= 60
    buying_intent = "High" if ai_assessment.get("buying_signal_present") and score >= 80 else (
        "Medium" if score >= 60 else "Low"
    )

    qualification_result = {
        "score": score,
        "classification": classification,
        "qualified": qualified,
        "icp_fit": icp_fit,
        "icp_matches": icp_matches,
        "icp_missing": icp_missing,
        "buying_intent": buying_intent,
        "recommended_offer": offer,
        "next_action": next_action,
        "reason": reason,
        "matched_criteria": matched_criteria,
        "failed_criteria": failed_criteria,
        "pain_points": ai_assessment.get("pain_points", []),
        "buying_signals": ai_assessment.get("buying_signals", []),
        "ai_assessment": ai_assessment,
        "scoring_breakdown": breakdown,
      "website_research": {
         "summary": research["website_summary"],
         "sources": research.get("website_sources", []),
      } if research.get("website_summary") else None,
        # AI-sourced qualitative fields (normalized in ai_service.py, already
        # stripped of confidence). Never used to set score/classification.
        "recommended_team": ai_assessment.get("recommended_team", ""),
        "expected_revenue": ai_assessment.get("expected_revenue", ""),
        "probability": ai_assessment.get("probability", ""),
        "offer_reason": ai_assessment.get("offer_reason", ""),
        "ai_insights": ai_assessment.get("ai_insights", []),
    }

    # Sales action plan is generated from the FINAL qualification result above
    # (score/classification/offer/etc. are already locked in), so it can never
    # contradict them - see generate_sales_action_plan()'s next_action/
    # recommended_offer pinning.
    qualification_result["sales_action_plan"] = generate_sales_action_plan(lead, qualification_result, research=research)

    return qualification_result
