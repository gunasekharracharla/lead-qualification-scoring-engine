from backend.schemas.lead_schema import LeadCreate
from backend.services.icp_service import evaluate_icp_fit


def test_icp_fit_true_when_all_three_match():
    lead = LeadCreate(name="A", company="B", country="United States", industry="SaaS", company_size=50)
    fit, matched, failed = evaluate_icp_fit(lead)
    assert fit is True
    assert failed == []


def test_icp_fit_false_when_country_wrong_even_with_other_matches():
    """Regression test: previously a lead with the wrong country could still
    pass ICP fit if enough OTHER criteria matched. This must not happen."""
    lead = LeadCreate(name="A", company="B", country="India", industry="SaaS", company_size=50)
    fit, matched, failed = evaluate_icp_fit(lead)
    assert fit is False
    assert "Target country" in failed


def test_icp_fit_false_when_size_out_of_range():
    lead = LeadCreate(name="A", company="B", country="United States", industry="SaaS", company_size=500)
    fit, matched, failed = evaluate_icp_fit(lead)
    assert fit is False
    assert "Company size fits ICP" in failed


def test_icp_fit_false_when_industry_wrong():
    lead = LeadCreate(name="A", company="B", country="United Kingdom", industry="Healthcare", company_size=20)
    fit, matched, failed = evaluate_icp_fit(lead)
    assert fit is False
    assert "Target industry" in failed
