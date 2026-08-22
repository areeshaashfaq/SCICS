from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(tags=["corrections"])

# The corrections table has a CHECK constraint on correction_type. Anything
# outside this set makes Postgres reject the row, which surfaced as a 500.
# Clients have historically sent "edit"/"accept"/"reject", so we translate
# those rather than breaking them.
_VALID_CORRECTION_TYPES = {"reclassified", "rejected", "added_missed", "confirmed"}
_CORRECTION_TYPE_ALIASES = {
    "edit":     "reclassified",
    "accept":   "confirmed",
    "approved": "confirmed",
    "reject":   "rejected",
}


def _normalise_correction_type(raw: str) -> str:
    """Map a client-supplied type onto a value the DB constraint allows."""
    value = (raw or "").strip().lower()
    value = _CORRECTION_TYPE_ALIASES.get(value, value)
    if value not in _VALID_CORRECTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid correction_type '{raw}'. "
                f"Expected one of: {', '.join(sorted(_VALID_CORRECTION_TYPES))}"
            ),
        )
    return value


# ── PATCH /documents/{id}/complete ──────────────────────────
@router.patch("/documents/{document_id}/complete")
def complete_document(document_id: int, db: Session = Depends(get_db)):
    db.execute(text("""
        UPDATE documents SET status = 'complete'
        WHERE document_id = :document_id
    """), {"document_id": document_id})
    db.commit()
    return {"status": "ok"}


# ── GET /corrections/ ────────────────────────────────────────
@router.get("/corrections/")
def get_corrections(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT
            c.correction_id,
            c.suggestion_id,
            c.document_id,
            c.original_icd_code,
            c.corrected_icd_code,
            COALESCE(i.description, '') AS icd_description,
            c.correction_type,
            c.coder_name,
            c.comment,
            c.corrected_at,
            d.patient_ref,
            d.source_filename
        FROM corrections c
        LEFT JOIN suggestions s ON s.suggestion_id = c.suggestion_id
        LEFT JOIN icd_codes i   ON i.icd_code = COALESCE(c.corrected_icd_code, c.original_icd_code)
        LEFT JOIN documents d   ON d.document_id = c.document_id
        ORDER BY c.corrected_at DESC
    """)).fetchall()

    return [
        {
            "correction_id":     row.correction_id,
            "suggestion_id":     row.suggestion_id,
            "document_id":       row.document_id,
            "original_icd_code": row.original_icd_code,
            "corrected_icd_code":row.corrected_icd_code,
            "icd_description":   row.icd_description,
            "correction_type":   row.correction_type,
            "coder_name":        row.coder_name,
            "comment":           row.comment,
            "corrected_at":      row.corrected_at.isoformat() if row.corrected_at else None,
            "patient_ref":       row.patient_ref,
            "source_filename":   row.source_filename
        }
        for row in rows
    ]


# ── POST /corrections/ ───────────────────────────────────────
class CorrectionRequest(BaseModel):
    suggestion_id:      int
    corrected_icd_code: str
    correction_type:    str = "reclassified"
    comment:            str = ""
    coder_name:         str = "coder"


@router.post("/corrections/")
def post_correction(req: CorrectionRequest, db: Session = Depends(get_db)):
    # Reject bad input with a 400 before it reaches Postgres, so a wrong value
    # returns a readable error instead of an integrity-error 500.
    correction_type = _normalise_correction_type(req.correction_type)

    # Look up original code and document_id
    sugg = db.execute(text("""
        SELECT icd_code, document_id FROM suggestions WHERE suggestion_id = :sid
    """), {"sid": req.suggestion_id}).fetchone()

    if sugg is None:
        raise HTTPException(
            status_code=404,
            detail=f"No suggestion with id {req.suggestion_id}",
        )

    result = db.execute(text("""
        INSERT INTO corrections (
            suggestion_id, original_icd_code, corrected_icd_code,
            correction_type, coder_name, comment, corrected_at, document_id
        ) VALUES (
            :suggestion_id, :original_icd_code, :corrected_icd_code,
            :correction_type, :coder_name, :comment, :corrected_at, :document_id
        )
        RETURNING correction_id
    """), {
        "suggestion_id":      req.suggestion_id,
        "original_icd_code":  sugg.icd_code,
        "corrected_icd_code": req.corrected_icd_code,
        "correction_type":    correction_type,
        "coder_name":         req.coder_name,
        "comment":            req.comment,
        "corrected_at":       datetime.utcnow(),
        "document_id":        sugg.document_id
    })
    db.commit()
    correction_id = result.fetchone()[0]

    return {"status": "ok", "correction_id": correction_id}