import io
import os
import sys

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nlp'))
from fuzzy_match_icd import match_all_from_text

router = APIRouter(prefix="/documents", tags=["documents"])


def _extract_pdf_text(data: bytes) -> str:
    """Pull the text layer out of a PDF.

    SIUT's PDFs are exported from their hospital system, so they carry a real
    text layer and need no OCR. A scanned PDF would come back empty here, which
    is why that case is reported rather than silently producing no suggestions.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PDF support requires the pypdf package on the server.",
        )

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read the PDF: {exc}")

    extracted = "\n".join(pages).strip()
    if not extracted:
        raise HTTPException(
            status_code=400,
            detail=("No text found in this PDF. It is most likely a scan rather "
                    "than an exported document; please paste the text instead."),
        )
    return extracted


def _decode_text(data: bytes) -> str:
    """Decode a .txt upload, tolerating the encodings clinical exports use."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


@router.get("/")
def get_documents(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM documents"))
    rows = result.fetchall()
    return {"documents": [dict(row._mapping) for row in rows]}


@router.post("/")
async def create_document(
    file: UploadFile = File(None),
    raw_text: str = Form(None),
    patient_ref: str = Form(""),
    db: Session = Depends(get_db),
):
    """Create a document from a pasted summary, a .txt file or a .pdf file.

    patient_ref stays accepted as a query parameter too, so the existing
    desktop client keeps working without changes.
    """
    source_filename = "pasted.txt"

    if file is not None and file.filename:
        data = await file.read()
        # Only the file's own name, never the full path the client sent.
        source_filename = os.path.basename(file.filename)
        suffix = os.path.splitext(source_filename)[1].lower()

        if suffix == ".pdf":
            summary_text = _extract_pdf_text(data)
        elif suffix in (".txt", ""):
            summary_text = _decode_text(data)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{suffix}'. Use a PDF or TXT file.",
            )
    elif raw_text and raw_text.strip():
        summary_text = raw_text
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a PDF/TXT file or the pasted summary text.",
        )

    if len(summary_text.strip()) < 40:
        raise HTTPException(
            status_code=400,
            detail="That summary looks too short to code. Please check the content.",
        )

    result = db.execute(text("""
        INSERT INTO documents (source_filename, patient_ref, raw_text)
        VALUES (:filename, :patient_ref, :raw_text)
        RETURNING document_id
    """), {
        "filename": source_filename,
        "patient_ref": patient_ref,
        "raw_text": summary_text,
    })
    db.commit()
    document_id = result.fetchone()[0]

    try:
        entities = match_all_from_text(summary_text)
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
        db.rollback()
        suggestion_count = 0
        print(f"NLP error: {e}")

    return {
        "message": "Document uploaded successfully",
        "document_id": document_id,
        "suggestions_generated": suggestion_count,
        "source_filename": source_filename,
    }