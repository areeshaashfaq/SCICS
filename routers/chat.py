from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from chatbot import generate_response

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/documents/{document_id}")
def get_chat(document_id: int, db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT * FROM chat_messages WHERE document_id = :document_id
        ORDER BY created_at ASC
    """), {"document_id": document_id})
    rows = result.fetchall()
    return {"messages": [dict(row._mapping) for row in rows]}

@router.post("/documents/{document_id}")
def send_message(document_id: int, sender: str, message_text: str,
                 related_suggestion_id: int = None, db: Session = Depends(get_db)):

    # Save coder message
    db.execute(text("""
        INSERT INTO chat_messages (document_id, sender, message_text, related_suggestion_id)
        VALUES (:document_id, :sender, :message_text, :related_suggestion_id)
    """), {
        "document_id": document_id,
        "sender": sender,
        "message_text": message_text,
        "related_suggestion_id": related_suggestion_id
    })
    db.commit()

    if sender == "coder":
        # Fetch suggestions with icd_description
        sugg_rows = db.execute(text("""
            SELECT s.*, i.description as icd_description
            FROM suggestions s
            LEFT JOIN icd_codes i ON i.icd_code = s.icd_code
            WHERE s.document_id = :document_id
        """), {"document_id": document_id}).fetchall()
        suggestions = [dict(row._mapping) for row in sugg_rows]

        # Fetch raw text
        doc = db.execute(text("""
            SELECT raw_text FROM documents WHERE document_id = :document_id
        """), {"document_id": document_id}).fetchone()
        raw_text = doc.raw_text if doc else ""

        # Generate response
        answer = generate_response(message_text, suggestions, raw_text)

        db.execute(text("""
    INSERT INTO chat_messages (document_id, sender, message_text)
    VALUES (:document_id, 'assistant', :message_text)
"""), {"document_id": document_id, "message_text": answer})
        db.commit()

        return {"message": "Message saved", "answer": answer}

    return {"message": "Message saved"}