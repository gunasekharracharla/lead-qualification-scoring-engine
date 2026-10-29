from pydantic import BaseModel, Field


class LeadCreate(BaseModel):
    """
    Input schema for POST /qualify-lead.
    Only name and company are required - everything else, including
    custom_offer is optional so a BDE can submit a partial lead.
    website/linkedin are plain strings (not a strict URL type) so an
    empty string or a bare domain doesn't cause a 422.
    """

    name: str = Field(..., min_length=1, max_length=120)
    company: str = Field(..., min_length=1, max_length=150)
    job_title: str | None = None
    country: str | None = None
    industry: str | None = None
    company_size: int | None = Field(default=None, gt=0, strict=True)
    website: str | None = None
    linkedin: str | None = None
    pain_point: str | None = None
    buying_signal: str | None = None
    custom_offer: str | None = None
    recent_activity: bool | None = Field(default=None, strict=True)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "John Smith",
                "company": "ABC SaaS",
                "job_title": "Founder",
                "country": "United States",
                "industry": "SaaS",
                "company_size": 50,
                "website": "https://example.com",
                "linkedin": "https://linkedin.com/company/example",
                "pain_point": "Manual lead qualification and sales follow-up are taking too much time.",
                "buying_signal": "We are actively evaluating automation vendors."
            }
        }
    }


class LeadUpdate(BaseModel):
    """Partial update schema for editing an existing lead in place."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    company: str | None = Field(default=None, min_length=1, max_length=150)
    job_title: str | None = None
    country: str | None = None
    industry: str | None = None
    company_size: int | None = Field(default=None, gt=0, strict=True)
    website: str | None = None
    linkedin: str | None = None
    pain_point: str | None = None
    buying_signal: str | None = None
    custom_offer: str | None = None
    recent_activity: bool | None = Field(default=None, strict=True)
