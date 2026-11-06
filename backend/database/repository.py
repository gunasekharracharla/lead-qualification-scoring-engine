from pathlib import Path
from hashlib import sha256

from sqlalchemy.orm import Session

from backend.database.models import LeadRecord, QualificationHistory


_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"
_RULE_FILES = ("icp_rules.json", "offer_rules.json", "scoring_rules.json")


def qualification_rules_version() -> str:
    digest = sha256()
    for filename in _RULE_FILES:
        digest.update(filename.encode("utf-8"))
        digest.update((_RULES_DIR / filename).read_bytes())
    return digest.hexdigest()


def create_qualification_history(
    db: Session,
    lead_id: int,
    lead_data: dict,
    qualification: dict,
    commit: bool = True,
) -> QualificationHistory:
    history = QualificationHistory(
        lead_id=lead_id,
        lead_data=lead_data,
        qualification=qualification,
        rules_version=qualification_rules_version(),
    )
    db.add(history)
    db.flush()
    if commit:
        db.commit()
    db.refresh(history)
    return history


def list_qualification_history(db: Session, lead_id: int) -> list[QualificationHistory]:
    return (
        db.query(QualificationHistory)
        .filter(QualificationHistory.lead_id == lead_id)
        .order_by(QualificationHistory.created_at.desc(), QualificationHistory.id.desc())
        .all()
    )


def create_lead_record(db: Session, data: dict, commit: bool = True) -> LeadRecord:
    record = LeadRecord(**data)
    db.add(record)
    db.flush()
    if commit:
        db.commit()
    db.refresh(record)
    return record


def update_lead_record(
    db: Session, record: LeadRecord, data: dict, commit: bool = True
) -> LeadRecord:
    """Update an existing lead record in place (same Lead ID preserved)."""
    for key, value in data.items():
        setattr(record, key, value)
    db.flush()
    if commit:
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
    db.query(QualificationHistory).filter(
        QualificationHistory.lead_id == record.id
    ).delete()
    db.delete(record)
    db.commit()


def delete_all_lead_records(db: Session) -> int:
    """Permanently remove every lead record (used to wipe leftover
    test/dummy leads so Recent Leads starts clean). Returns the number
    of rows deleted."""
    db.query(QualificationHistory).delete()
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
