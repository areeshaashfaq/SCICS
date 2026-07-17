from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

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
def update_suggestion(suggestion_id: int, decision: str, db: Session = Depends(get_db)):
    db.execute(text("""
        UPDATE suggestions SET coder_decision = :decision
        WHERE suggestion_id = :suggestion_id
    """), {"decision": decision, "suggestion_id": suggestion_id})
    db.commit()
    return {"message": f"Suggestion {suggestion_id} marked as {decision}"}