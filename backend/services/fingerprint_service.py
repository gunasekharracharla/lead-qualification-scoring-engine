import hashlib
import json

# Only fields that meaningfully affect qualification go into the fingerprint.
# Fields like custom_offer (a display override) deliberately do NOT affect
# it - changing your offer text shouldn't force an expensive re-qualification.
_FINGERPRINT_FIELDS = [
    "name", "company", "job_title", "country", "industry", "company_size",
    "website", "linkedin", "pain_point", "buying_signal", "recent_activity",
]


def _normalize(value):
    """Trim whitespace, lowercase strings, pass through numbers/bools/None
    unchanged so the fingerprint is stable regardless of casing or spacing."""
    if isinstance(value, str):
        v = value.strip().lower()
        return v if v else None
    return value


def compute_fingerprint(lead) -> str:
    """
    Stable SHA-256 fingerprint of the meaningful qualification input.
    Same normalized data -> same fingerprint -> safe to reuse a stored
    qualification instead of calling the AI provider again.
    Any change to a fingerprinted field -> different fingerprint -> the
    lead is treated as needing fresh qualification.
    """
    payload = {field: _normalize(getattr(lead, field, None)) for field in _FINGERPRINT_FIELDS}
    stable_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def compute_identity_key(lead) -> str:
    """
    Broader identity match ("is this the same real person/company") used to
    decide whether to reuse the same Lead ID on resubmission, independent of
    whether their qualification-relevant details changed. Based only on
    name + company - deliberately looser than the full fingerprint.
    """
    payload = {
        "name": _normalize(getattr(lead, "name", None)),
        "company": _normalize(getattr(lead, "company", None)),
    }
    stable_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()
