from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/")
def get_analytics(db: Session = Depends(get_db)):

    # Corrections counts
    # These values must match the corrections_correction_type_check constraint:
    # reclassified / rejected / added_missed / confirmed.
    corr = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE correction_type = 'confirmed')    AS accepted,
            COUNT(*) FILTER (WHERE correction_type = 'rejected')     AS rejected,
            COUNT(*) FILTER (WHERE correction_type = 'reclassified') AS edited
        FROM corrections
    """)).fetchone()

    accepted = corr.accepted or 0
    rejected = corr.rejected or 0
    edited   = corr.edited   or 0
    total_decisions = accepted + rejected + edited
    acceptance_rate = round(accepted / total_decisions, 2) if total_decisions > 0 else 0.0

    # Avg confidence
    avg_conf = db.execute(text("""
        SELECT ROUND(AVG(confidence_score)::numeric, 2) FROM suggestions
        WHERE confidence_score IS NOT NULL
    """)).scalar() or 0.0

    # Documents
    # documents.status allows pending / processing / reviewed / finalized.
    docs = db.execute(text("""
        SELECT
            COUNT(*)                                        AS total_documents,
            COUNT(*) FILTER (WHERE status IN ('reviewed', 'finalized'))     AS complete_documents,
            COUNT(*) FILTER (WHERE status NOT IN ('reviewed', 'finalized')) AS pending_documents
        FROM documents
    """)).fetchone()

    # Suggestions
    sugg = db.execute(text("""
        SELECT
            COUNT(*)                                    AS total_suggestions,
            COUNT(*) FILTER (WHERE is_ambiguous = true) AS flagged_ambiguous
        FROM suggestions
    """)).fetchone()

    # Top 5 corrected codes
    # Deliberately only counts rows where the coder actually supplied a new
    # code, so plain accepts and rejects do not inflate the "most corrected"
    # list. No suggestions join here, so no s.* references are valid.
    top_codes = db.execute(text("""
        SELECT
            c.corrected_icd_code        AS icd_code,
            i.description               AS description,
            COUNT(*)                    AS corrections
        FROM corrections c
        LEFT JOIN icd_codes i ON i.icd_code = c.corrected_icd_code
        WHERE c.corrected_icd_code IS NOT NULL
        GROUP BY c.corrected_icd_code, i.description
        ORDER BY corrections DESC
        LIMIT 5
    """)).fetchall()

    # Recent activity
    # An accept or reject leaves corrected_icd_code null, which showed as a
    # blank cell in the dashboard. Fall back to the original code, then to the
    # suggestion's own code, so every row names the code it refers to.
    recent = db.execute(text("""
        SELECT
            c.correction_type,
            COALESCE(c.corrected_icd_code, c.original_icd_code, s.icd_code) AS icd_code,
            i.description               AS description,
            c.coder_name,
            c.corrected_at,
            d.patient_ref
        FROM corrections c
        LEFT JOIN suggestions s  ON s.suggestion_id = c.suggestion_id
        LEFT JOIN documents d    ON d.document_id   = c.document_id
        LEFT JOIN icd_codes i    ON i.icd_code      = COALESCE(c.corrected_icd_code, c.original_icd_code, s.icd_code)
        ORDER BY c.corrected_at DESC
        LIMIT 10
    """)).fetchall()

    return {
        "accepted":           int(accepted),
        "rejected":           int(rejected),
        "edited":             int(edited),
        "total_decisions":    int(total_decisions),
        "acceptance_rate":    float(acceptance_rate),
        "avg_confidence":     float(avg_conf),
        "total_documents":    int(docs.total_documents),
        "complete_documents": int(docs.complete_documents),
        "pending_documents":  int(docs.pending_documents),
        "total_suggestions":  int(sugg.total_suggestions),
        "flagged_ambiguous":  int(sugg.flagged_ambiguous),
        "top_corrected_codes": [
            {
                "icd_code":    row.icd_code,
                "description": row.description,
                "corrections": int(row.corrections)
            }
            for row in top_codes
        ],
        "recent_activity": [
            {
                "correction_type": row.correction_type,
                "icd_code":        row.icd_code,
                "description":     row.description,
                "coder_name":      row.coder_name,
                "corrected_at":    row.corrected_at.isoformat() if row.corrected_at else None,
                "patient_ref":     row.patient_ref
            }
            for row in recent
        ]
    }