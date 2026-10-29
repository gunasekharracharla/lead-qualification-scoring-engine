from sqlalchemy.orm import Session

from backend.database.models import LeadRecord


def create_lead_record(db: Session, data: dict) -> LeadRecord:
    record = LeadRecord(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_lead_record(db: Session, record: LeadRecord, data: dict) -> LeadRecord:
    """Update an existing lead record in place (same Lead ID preserved)."""
    for key, value in data.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


def get_lead(db: Session, lead_id: int) -> LeadRecord | None:
    return db.get(LeadRecord, lead_id)


def get_lead_by_identity(db: Session, identity_key: str) -> LeadRecord | None:
    """Find an existing lead record for the same real person/company,
    so a resubmission reuses the same Lead ID instead of creating a new one."""
    return (
        db.query(LeadRecord)
        .filter(LeadRecord.identity_key == identity_key)
        .order_by(LeadRecord.created_at.desc())
        .first()
    )


def delete_lead_record(db: Session, record: LeadRecord) -> None:
    """Permanently remove a single lead record (used to clean up individual
    test/dummy rows without touching any other persisted lead)."""
    db.delete(record)
    db.commit()


def delete_all_lead_records(db: Session) -> int:
    """Permanently remove every lead record (used to wipe leftover
    test/dummy leads so Recent Leads starts clean). Returns the number
    of rows deleted."""
    count = db.query(LeadRecord).delete()
    db.commit()
    return count


def list_leads(db: Session, limit: int = 100) -> list[LeadRecord]:
    """Newest activity first: a lead that was just re-qualified (updated_at
    bumped) surfaces at the top of Recent Leads, same as a brand-new lead
    (whose created_at == updated_at on first insert)."""
    return (
        db.query(LeadRecord)
        .order_by(LeadRecord.updated_at.desc(), LeadRecord.created_at.desc())
        .limit(limit)
        .all()
    )
