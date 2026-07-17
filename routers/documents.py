from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nlp'))
from fuzzy_match_icd import match_all_from_text

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/")
def get_documents(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM documents"))
    rows = result.fetchall()
    return {"documents": [dict(row._mapping) for row in rows]}

@router.post("/")
async def create_document(file: UploadFile = File(...), patient_ref: str = "", db: Session = Depends(get_db)):
    raw_text = (await file.read()).decode("utf-8")
    
    result = db.execute(text("""
        INSERT INTO documents (source_filename, patient_ref, raw_text)
        VALUES (:filename, :patient_ref, :raw_text)
        RETURNING document_id
    """), {"filename": file.filename, "patient_ref": patient_ref, "raw_text": raw_text})
    db.commit()
    document_id = result.fetchone()[0]

    try:
        entities = match_all_from_text(raw_text)
        for ent in entities:
            db.execute(text("""
                INSERT INTO suggestions (
                    document_id, suggestion_type, extracted_text,
                    icd_code, confidence_score,
                    source_char_start, source_char_end, source_snippet,
                    is_ambiguous, ambiguity_reason
                ) VALUES (
                    :document_id, :suggestion_type, :extracted_text,
                    :icd_code, :confidence_score,
                    :source_char_start, :source_char_end, :source_snippet,
                    :is_ambiguous, :ambiguity_reason
                )
            """), {
                "document_id": document_id,
                "suggestion_type": ent.get("suggestion_type", "diagnosis_associative"),
                "extracted_text": ent.get("extracted_text", ""),
                "icd_code": ent.get("icd_code"),
                "confidence_score": ent.get("confidence_score"),
                "source_char_start": ent.get("source_char_start", 0),
                "source_char_end": ent.get("source_char_end", 0),
                "source_snippet": ent.get("source_snippet", ""),
                "is_ambiguous": ent.get("is_ambiguous", False),
                "ambiguity_reason": ent.get("ambiguity_reason", "")
            })
        db.commit()
        suggestion_count = len(entities)
    except Exception as e:
        suggestion_count = 0
        print(f"NLP error: {e}")

    return {
        "message": "Document uploaded successfully",
        "document_id": document_id,
        "suggestions_generated": suggestion_count
    }