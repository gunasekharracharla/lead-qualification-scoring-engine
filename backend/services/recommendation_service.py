import json
from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "offer_rules.json"


def _load_rules() -> dict:
    with open(_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def recommend(classification: str, lead) -> tuple[str, str]:
    """
    Returns (recommended_offer, next_action).
    If the user supplied custom_offer explicitly, that overrides the
    auto-generated one - respecting "custom_offer is optional; if not
    given, generate automatically" from the requirements.
    """
    rules = _load_rules()
    tier = classification.lower()
    tier_rules = rules.get(tier, rules["cold"])

    offer = (lead.custom_offer or "").strip() or tier_rules["offer"]
    next_action = tier_rules["next_action"]
    return offer, next_action


def build_reason(score: int, classification: str, matched_criteria: list[str], failed_criteria: list[str]) -> str:
    if not matched_criteria:
        return f"The lead received {score}/100 because limited qualifying evidence was identified."
    matched_text = ", ".join(m.lower() for m in matched_criteria)
    return f"The lead received {score}/100 ({classification}) based on: {matched_text}."
