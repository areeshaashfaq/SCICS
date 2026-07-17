from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

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
    return {"message": "Message saved"}