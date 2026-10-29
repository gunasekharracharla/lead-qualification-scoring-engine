from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.database import Base


class LeadRecord(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Identity key for a real-world lead across resubmissions/updates.
    # Same company+name -> same Lead ID is reused rather than creating a
    # new record every time the same person is submitted again.
    identity_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # SHA-256 of the meaningful qualification input (see fingerprint_service.py).
    # Same fingerprint on the same identity_key -> skip Groq, reuse stored result.
    fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # --- Input fields ---
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    company: Mapped[str] = mapped_column(String(150), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    company_size: Mapped[int | None] = mapped_column(Integer)
    website: Mapped[str | None] = mapped_column(String(500))
    linkedin: Mapped[str | None] = mapped_column(String(500))
    pain_point: Mapped[str | None] = mapped_column(Text)
    buying_signal: Mapped[str | None] = mapped_column(Text)
    custom_offer: Mapped[str | None] = mapped_column(String(200))
    recent_activity: Mapped[bool | None] = mapped_column(Boolean)

    # --- Qualification result fields (all persisted, retrievable by ID) ---
    score: Mapped[int | None] = mapped_column(Integer)
    classification: Mapped[str | None] = mapped_column(String(20))
    qualified: Mapped[bool | None] = mapped_column(Boolean)
    icp_fit: Mapped[bool | None] = mapped_column(Boolean)
    icp_matches: Mapped[list | None] = mapped_column(JSON)
    icp_missing: Mapped[list | None] = mapped_column(JSON)
    buying_intent: Mapped[str | None] = mapped_column(String(20))
    recommended_offer: Mapped[str | None] = mapped_column(String(300))
    next_action: Mapped[str | None] = mapped_column(String(500))
    reason: Mapped[str | None] = mapped_column(Text)
    matched_criteria: Mapped[list | None] = mapped_column(JSON)
    failed_criteria: Mapped[list | None] = mapped_column(JSON)
    pain_points: Mapped[list | None] = mapped_column(JSON)
    buying_signals: Mapped[list | None] = mapped_column(JSON)
    ai_assessment: Mapped[dict | None] = mapped_column(JSON)
    scoring_breakdown: Mapped[dict | None] = mapped_column(JSON)
    website_research: Mapped[dict | None] = mapped_column(JSON)
    recommended_team: Mapped[str | None] = mapped_column(String(200))
    expected_revenue: Mapped[str | None] = mapped_column(String(100))
    probability: Mapped[str | None] = mapped_column(String(50))
    offer_reason: Mapped[str | None] = mapped_column(Text)
    ai_insights: Mapped[list | None] = mapped_column(JSON)

    # Structured, lead-specific sales guidance generated after qualification
    # (see sales_plan_service.py). Persisted as JSON and keyed to this same
    # Lead ID, so GET /leads/{lead_id} always returns the same plan that was
    # shown right after qualification.
    sales_action_plan: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
