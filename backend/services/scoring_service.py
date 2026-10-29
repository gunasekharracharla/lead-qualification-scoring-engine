import json
from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "scoring_rules.json"


def _load_rules() -> dict:
    with open(_RULES_PATH, "r", encoding="utf-8") as f:
        rules = json.load(f)
    total_weight = sum(rules["criteria"].values())
    if total_weight != 100:
        import logging
        logging.getLogger("lead_engine.scoring").warning(
            f"scoring_rules.json criteria weights sum to {total_weight}, expected 100"
        )
    return rules


def calculate_score(ai_assessment: dict, company_size_fit: bool) -> tuple[int, dict, list[str], list[str]]:
    """
    THE single source of truth for the final 0-100 score. Takes the AI's
    structured true/false assessment plus a structured company_size_fit
    boolean (from icp_service.company_size_ok - no fragile string matching),
    applies the configurable weights from scoring_rules.json, and returns:
      (total_score, per_criterion_breakdown, matched_criteria, failed_criteria)

    matched_criteria and failed_criteria are built from ONE consistent set
    of 7 boolean flags, so a criterion can never appear in both lists at
    once - this fixes the earlier bug where the same "Target industry"
    label could show up in both matched and failed criteria from two
    different sources of truth.

    The AI never sets this number directly - it only supplies the booleans
    this function scores against. This is the hybrid architecture: AI
    interprets, Python decides the number.
    """
    rules = _load_rules()
    weights = rules["criteria"]

    flags = {
        "Target industry": bool(ai_assessment.get("industry_relevance")),
        "Decision maker": bool(ai_assessment.get("decision_maker_relevance")),
        "Company size fits ICP": bool(company_size_fit),
        "Clear pain point": bool(ai_assessment.get("pain_point_relevant")),
        "Buying signal": bool(ai_assessment.get("buying_signal_present")),
        "Automation opportunity": bool(ai_assessment.get("automation_opportunity")),
        "Recent activity": bool(ai_assessment.get("recent_activity")),
    }

    breakdown = {
        "target_industry": weights["target_industry"] if flags["Target industry"] else 0,
        "decision_maker": weights["decision_maker"] if flags["Decision maker"] else 0,
        "company_size": weights["company_size"] if flags["Company size fits ICP"] else 0,
        "pain_point": weights["pain_point"] if flags["Clear pain point"] else 0,
        "buying_signal": weights["buying_signal"] if flags["Buying signal"] else 0,
        "automation_opportunity": weights["automation_opportunity"] if flags["Automation opportunity"] else 0,
        "recent_activity": weights["recent_activity"] if flags["Recent activity"] else 0,
    }

    matched_criteria = [label for label, ok in flags.items() if ok]
    failed_criteria = [label for label, ok in flags.items() if not ok]

    total = sum(breakdown.values())
    total = max(0, min(100, total))  # structurally guaranteed by weights summing to 100, kept as a hard safety clamp
    return total, breakdown, matched_criteria, failed_criteria


def classify(score: int) -> str:
    rules = _load_rules()
    if score >= rules["thresholds"]["hot"]:
        return "HOT"
    if score >= rules["thresholds"]["warm"]:
        return "WARM"
    return "COLD"
