import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.config.settings import settings
from backend.database.database import get_db
from backend.database.repository import (
    create_lead_record, create_qualification_history, delete_all_lead_records, delete_lead_record,
    get_lead, get_lead_by_identity, list_leads, list_qualification_history, update_lead_record,
)
from backend.schemas.lead_schema import LeadCreate, LeadStatusUpdate, LeadUpdate
from backend.services.analysis_service import analyze_lead
from backend.services.fingerprint_service import compute_fingerprint, compute_identity_key

logger = logging.getLogger("lead_engine.leads")

router = APIRouter(tags=["Lead Qualification"])


def _lead_dict(record) -> dict:
    return {
        "id": record.id,
        "name": record.name,
        "company": record.company,
        "job_title": record.job_title,
        "country": record.country,
        "industry": record.industry,
        "company_size": record.company_size,
        "website": record.website,
        "linkedin": record.linkedin,
        "pain_point": record.pain_point,
        "buying_signal": record.buying_signal,
        "custom_offer": record.custom_offer,
        "recent_activity": record.recent_activity,
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _qualification_dict(record) -> dict:
    return {
        "lead_id": record.id,
        "score": record.score,
        "lead_score": record.score,
        "classification": record.classification,
        "qualified": record.qualified,
        "icp_fit": record.icp_fit,
        "icp_matches": record.icp_matches,
        "icp_missing": record.icp_missing,
        "buying_intent": record.buying_intent,
        "recommended_offer": record.recommended_offer,
        "next_action": record.next_action,
        "reason": record.reason,
        "matched_criteria": record.matched_criteria,
        "failed_criteria": record.failed_criteria,
        "pain_points": record.pain_points,
        "buying_signals": record.buying_signals,
        "ai_assessment": record.ai_assessment,
        "scoring_breakdown": record.scoring_breakdown,
        "website_research": record.website_research,
        "recommended_team": record.recommended_team,
        "expected_revenue": record.expected_revenue,
        "probability": record.probability,
        "offer_reason": record.offer_reason,
        "ai_insights": record.ai_insights,
        "sales_action_plan": record.sales_action_plan,
    }


def _lead_input_dict(record) -> dict:
    return {
        "name": record.name,
        "company": record.company,
        "job_title": record.job_title,
        "country": record.country,
        "industry": record.industry,
        "company_size": record.company_size,
        "website": record.website,
        "linkedin": record.linkedin,
        "pain_point": record.pain_point,
        "buying_signal": record.buying_signal,
        "custom_offer": record.custom_offer,
        "recent_activity": record.recent_activity,
    }


def _save_qualification_run(
    db: Session, record, previous_run: dict | None = None
) -> None:
    history = list_qualification_history(db, record.id)
    if not history and previous_run is not None:
        create_qualification_history(
            db, record.id, previous_run["lead"], previous_run["qualification"], commit=False
        )
    create_qualification_history(
        db, record.id, _lead_input_dict(record), _qualification_dict(record), commit=False
    )
    db.commit()


@router.get("/health")
def health():
    provider = settings.AI_PROVIDER
    key_present = {
        "groq": bool(settings.GROQ_API_KEY),
        "openai": bool(settings.OPENAI_API_KEY),
        "gemini": bool(settings.GEMINI_API_KEY),
    }.get(provider, False)
    model = {
        "groq": settings.GROQ_MODEL,
        "openai": settings.OPENAI_MODEL,
        "gemini": settings.GEMINI_MODEL,
    }.get(provider)

    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ai_enabled_flag": settings.AI_ENABLED,
        "ai_provider": provider,
        "ai_model": model,
        "llm_enabled": bool(settings.AI_ENABLED and key_present),
        "database": settings.DATABASE_URL.split("://")[0],
    }


@router.post("/qualify-lead")
def qualify_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    """
    Main qualification endpoint with duplicate/caching behavior:

    1. Compute an identity key (name+company) to find the same real lead.
    2. Compute a fingerprint of the qualification-meaningful fields.
    3. If an existing record with the same identity_key AND same fingerprint
       is found -> skip Groq entirely, return the stored qualification.
    4. If an existing record with the same identity_key but a DIFFERENT
       fingerprint is found -> requalify, but UPDATE that same record
       (same Lead ID preserved) instead of creating a duplicate lead.
    5. If no existing record for this identity -> create a new lead + Lead ID
       and run qualification.
    """
    identity_key = compute_identity_key(lead)
    fingerprint = compute_fingerprint(lead)

    existing = get_lead_by_identity(db, identity_key)

    if existing is not None and existing.fingerprint == fingerprint:
        logger.info(f"Existing qualification found for lead_id={existing.id}. Skipping Groq.")
        return {
            "success": True,
            "message": "Lead qualified successfully",
            "qualification_source": "database",
            "cached": True,
            "lead": _lead_dict(existing),
            "qualification": _qualification_dict(existing),
        }

    if existing is not None:
        logger.info(f"Lead data changed for lead_id={existing.id}. Re-running qualification.")
    else:
        logger.info("No existing qualification found. Running Groq analysis.")

    previous_run = None
    if existing is not None and existing.score is not None:
        previous_run = {
            "lead": _lead_input_dict(existing),
            "qualification": _qualification_dict(existing),
        }

    result = analyze_lead(lead)

    record_data = lead.model_dump()
    record_data.update({
        "identity_key": identity_key,
        "fingerprint": fingerprint,
        "score": result["score"],
        "classification": result["classification"],
        "qualified": result["qualified"],
        "icp_fit": result["icp_fit"],
        "icp_matches": result["icp_matches"],
        "icp_missing": result["icp_missing"],
        "buying_intent": result["buying_intent"],
        "recommended_offer": result["recommended_offer"],
        "next_action": result["next_action"],
        "reason": result["reason"],
        "matched_criteria": result["matched_criteria"],
        "failed_criteria": result["failed_criteria"],
        "pain_points": result["pain_points"],
        "buying_signals": result["buying_signals"],
        "ai_assessment": result["ai_assessment"],
        "scoring_breakdown": result["scoring_breakdown"],
        "website_research": result["website_research"],
        "recommended_team": result["recommended_team"],
        "expected_revenue": result["expected_revenue"],
        "probability": result["probability"],
        "offer_reason": result["offer_reason"],
        "ai_insights": result["ai_insights"],
        "sales_action_plan": result["sales_action_plan"],
    })

    if existing is not None:
        record = update_lead_record(db, existing, record_data, commit=False)
    else:
        record = create_lead_record(db, record_data, commit=False)

    _save_qualification_run(db, record, previous_run)
    if existing is not None:
        logger.info(f"Qualification persisted for lead_id={record.id} (updated existing lead).")
    else:
        logger.info(f"Qualification persisted for lead_id={record.id} (new lead).")

    return {
        "success": True,
        "message": "Lead qualified successfully",
        "qualification_source": "ai" if settings.AI_ENABLED else "fallback",
        "cached": False,
        "lead": _lead_dict(record),
        "qualification": _qualification_dict(record),
    }


@router.get("/leads")
def get_leads(limit: int = 100, db: Session = Depends(get_db)):
    records = list_leads(db, limit=limit)
    return {
        "success": True,
        "count": len(records),
        "leads": [
            _lead_dict(r) | {"qualification": _qualification_dict(r) if r.score is not None else None}
            for r in records
        ],
    }


@router.delete("/leads")
def delete_all_leads(db: Session = Depends(get_db)):
    """
    Permanently delete EVERY lead in the database. Use this to wipe out
    leftover test/dummy leads (e.g. entries created while manually testing
    the form) so Recent Leads and the stats bar start from a clean slate.
    This cannot be undone.
    """
    count = delete_all_lead_records(db)
    logger.info(f"Cleared all leads. {count} record(s) deleted.")
    return {"success": True, "message": f"Deleted {count} lead(s)", "deleted_count": count}


@router.get("/leads/{lead_id}")
def get_lead_by_id(lead_id: int, db: Session = Depends(get_db)):
    record = get_lead(db, lead_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Lead with id {lead_id} not found")
    return {
        "success": True,
        "lead": _lead_dict(record),
        "qualification": _qualification_dict(record) if record.score is not None else None,
    }


@router.put("/leads/{lead_id}")
def update_lead_by_id(lead_id: int, lead: LeadUpdate, db: Session = Depends(get_db)):
    """Edit an existing lead in place and immediately re-qualify it."""
    record = get_lead(db, lead_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Lead with id {lead_id} not found")

    update_data = lead.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No lead fields were provided to update")

    merged = {
        "name": record.name,
        "company": record.company,
        "job_title": record.job_title,
        "country": record.country,
        "industry": record.industry,
        "company_size": record.company_size,
        "website": record.website,
        "linkedin": record.linkedin,
        "pain_point": record.pain_point,
        "buying_signal": record.buying_signal,
        "custom_offer": record.custom_offer,
        "recent_activity": record.recent_activity,
    }
    for key, value in update_data.items():
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                value = None
        merged[key] = value

    if not merged.get("name") or not merged.get("company"):
        raise HTTPException(status_code=400, detail="Lead name and company are required")
    if merged.get("company_size") is not None and merged["company_size"] <= 0:
        raise HTTPException(status_code=400, detail="Company size must be a positive number")

    previous_run = None
    if record.score is not None:
        previous_run = {
            "lead": _lead_input_dict(record),
            "qualification": _qualification_dict(record),
        }

    # Recompute a real identity + fingerprint using the edited data.
    identity_key = compute_identity_key(type("LeadPayload", (), merged)())
    fingerprint = compute_fingerprint(type("LeadPayload", (), merged)())

    result = analyze_lead(LeadCreate(**merged))
    record_data = {**merged, "identity_key": identity_key, "fingerprint": fingerprint}
    record_data.update({
        "score": result["score"],
        "classification": result["classification"],
        "qualified": result["qualified"],
        "icp_fit": result["icp_fit"],
        "icp_matches": result["icp_matches"],
        "icp_missing": result["icp_missing"],
        "buying_intent": result["buying_intent"],
        "recommended_offer": result["recommended_offer"],
        "next_action": result["next_action"],
        "reason": result["reason"],
        "matched_criteria": result["matched_criteria"],
        "failed_criteria": result["failed_criteria"],
        "pain_points": result["pain_points"],
        "buying_signals": result["buying_signals"],
        "ai_assessment": result["ai_assessment"],
        "scoring_breakdown": result["scoring_breakdown"],
        "website_research": result["website_research"],
        "recommended_team": result["recommended_team"],
        "expected_revenue": result["expected_revenue"],
        "probability": result["probability"],
        "offer_reason": result["offer_reason"],
        "ai_insights": result["ai_insights"],
        "sales_action_plan": result["sales_action_plan"],
    })

    updated = update_lead_record(db, record, record_data, commit=False)
    _save_qualification_run(db, updated, previous_run)
    logger.info(f"Lead {lead_id} updated and requalified successfully.")
    return {
        "success": True,
        "message": "Lead updated and requalified",
        "lead": _lead_dict(updated),
        "qualification": _qualification_dict(updated),
    }


@router.delete("/leads/{lead_id}")
def delete_lead_by_id(lead_id: int, db: Session = Depends(get_db)):
    """
    Permanently delete a single lead by ID. Use this to clean up individual
    test/dummy records (e.g. leads created while testing) without affecting
    any other real, persisted lead. This never clears the whole database.
    """
    record = get_lead(db, lead_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Lead with id {lead_id} not found")
    delete_lead_record(db, record)
    return {"success": True, "message": f"Lead {lead_id} deleted"}


@router.get("/leads/{lead_id}/qualification")
def get_qualification_by_lead_id(lead_id: int, db: Session = Depends(get_db)):
    """
    Retrieve the persisted qualification result for a lead by lead_id.
    Reads exclusively from the database - proves qualification results
    genuinely survive a backend restart rather than living only in memory.
    """
    record = get_lead(db, lead_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Lead with id {lead_id} not found")
    if record.score is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} has not been qualified yet")
    return {
        "success": True,
        "qualification": _qualification_dict(record),
    }


@router.get("/leads/{lead_id}/qualification-history")
def get_qualification_history(lead_id: int, db: Session = Depends(get_db)):
    if get_lead(db, lead_id) is None:
        raise HTTPException(status_code=404, detail=f"Lead with id {lead_id} not found")
    history = list_qualification_history(db, lead_id)
    return {
        "success": True,
        "count": len(history),
        "history": [
            {
                "id": item.id,
                "lead_id": item.lead_id,
                "lead": item.lead_data,
                "qualification": item.qualification,
                "rules_version": item.rules_version,
                "created_at": item.created_at.isoformat(),
            }
            for item in history
        ],
    }


@router.patch("/leads/{lead_id}/status")
def update_lead_status(
    lead_id: int,
    update: LeadStatusUpdate,
    db: Session = Depends(get_db),
):
    record = get_lead(db, lead_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Lead with id {lead_id} not found")
    updated = update_lead_record(db, record, {"status": update.status})
    return {"success": True, "lead": _lead_dict(updated)}
