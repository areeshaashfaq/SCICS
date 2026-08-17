from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from datetime import datetime

router = APIRouter(prefix="/suggestions", tags=["suggestions"])

@router.get("/documents/{document_id}")
def get_suggestions(document_id: int, db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT * FROM suggestions WHERE document_id = :document_id
        ORDER BY suggestion_type, confidence_score DESC
    """), {"document_id": document_id})
    rows = result.fetchall()
    return {"suggestions": [dict(row._mapping) for row in rows]}

@router.patch("/{suggestion_id}")
def update_suggestion(suggestion_id: int, decision: str, coder_name: str = "coder", db: Session = Depends(get_db)):
    # Update coder_decision on suggestion
    db.execute(text("""
        UPDATE suggestions SET coder_decision = :decision
        WHERE suggestion_id = :suggestion_id
    """), {"decision": decision, "suggestion_id": suggestion_id})

    # Look up original_icd_code and document_id from suggestion
    row = db.execute(text("""
        SELECT icd_code, document_id FROM suggestions WHERE suggestion_id = :suggestion_id
    """), {"suggestion_id": suggestion_id}).fetchone()

    if row:
        correction_type = "accept" if decision == "approved" else "reject"
        db.execute(text("""
            INSERT INTO corrections (
                suggestion_id, original_icd_code, corrected_icd_code,
                correction_type, coder_name, comment, corrected_at, document_id
            ) VALUES (
                :suggestion_id, :original_icd_code, null,
                :correction_type, :coder_name, '', :corrected_at, :document_id
            )
        """), {
            "suggestion_id": suggestion_id,
            "original_icd_code": row.icd_code,
            "correction_type": correction_type,
            "coder_name": coder_name,
            "corrected_at": datetime.utcnow(),
            "document_id": row.document_id
        })

    db.commit()
    return {"message": f"Suggestion {suggestion_id} marked as {decision}"}