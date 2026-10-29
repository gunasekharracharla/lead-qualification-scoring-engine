import json
from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "icp_rules.json"


def _load_rules() -> dict:
    with open(_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_icp_fit(lead) -> tuple[bool, list[str], list[str]]:
    """
    ICP fit is a mandatory gate: country AND industry AND company size must ALL
    match for icp_fit to be True. This replaces the earlier "4 of 6 criteria"
    approach, which could pass a lead with the wrong country/industry as long
    as enough other boxes were checked.

    Returns (icp_fit, matched_country_industry_size, failed_country_industry_size)

    NOTE: this is a SEPARATE, deterministic market-fit gate from the
    AI-scored "target_industry"/"decision_maker" criteria used in
    scoring_service.py. The two are intentionally distinct concepts (is
    this lead in our target market at all, vs. how well do the qualitative
    signals score) and are exposed as separate fields (icp_matches/
    icp_missing vs matched_criteria/failed_criteria) in the API response so
    they can never contradict each other under the same label.
    """
    rules = _load_rules()
    matched, failed = [], []

    country = (lead.country or "").strip().lower()
    target_countries = [c.lower() for c in rules["target_countries"]]
    country_ok = bool(country) and any(country == tc or tc in country for tc in target_countries)
    (matched if country_ok else failed).append("Target country")

    industry = (lead.industry or "").strip().lower()
    target_industries = [i.lower() for i in rules["target_industries"]]
    industry_ok = bool(industry) and any(industry == ti or ti in industry for ti in target_industries)
    (matched if industry_ok else failed).append("Target industry")

    size_ok = company_size_ok(lead, rules)
    (matched if size_ok else failed).append("Company size fits ICP")

    icp_fit = country_ok and industry_ok and size_ok
    return icp_fit, matched, failed


def company_size_ok(lead, rules: dict | None = None) -> bool:
    """
    Structured boolean for whether company_size falls in the configured ICP
    range. Exposed as its own function so scoring_service.py can use this
    directly instead of fragile string-matching against a label list.
    """
    rules = rules or _load_rules()
    size = lead.company_size
    size_min = rules["company_size_min"]
    size_max = rules.get("company_size_max")  # None/missing = no upper bound
    return size is not None and size >= size_min and (size_max is None or size <= size_max)
