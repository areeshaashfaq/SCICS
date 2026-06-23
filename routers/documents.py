from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/")
def get_documents(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM documents"))
    rows = result.fetchall()
    return {"documents": [dict(row._mapping) for row in rows]}

@router.post("/")
def create_document(filename: str, patient_ref: str, raw_text: str, db: Session = Depends(get_db)):
    db.execute(text("""
        INSERT INTO documents (source_filename, patient_ref, raw_text)
        VALUES (:filename, :patient_ref, :raw_text)
    """), {"filename": filename, "patient_ref": patient_ref, "raw_text": raw_text})
    db.commit()
    return {"message": "Document uploaded successfully"}