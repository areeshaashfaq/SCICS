# fake_data.py — mirrors the exact shape the real backend will return

FAKE_DOCUMENTS = [
    {
        "document_id": 1,
        "patient_ref": "00247-KHI",
        "source_filename": "051904.txt",
        "upload_date": "2026-06-12",
        "status": "pending",
        "notes": ""
    },
    {
        "document_id": 2,
        "patient_ref": "00312-KHI",
        "source_filename": "490434.txt",
        "upload_date": "2026-06-13",
        "status": "pending",
        "notes": ""
    },
]

FAKE_RAW_TEXTS = {
    1: """SIUT — DISCHARGE SUMMARY

Patient Ref  : 00247-KHI
Source File  : 051904.txt
Admitted     : 12-Jun-2026
Discharged   : 19-Jun-2026

REASON FOR ADMISSION
Patient presented with progressively worsening bilateral
pedal oedema, decreased urine output, and dyspnoea on exertion.

BACKGROUND MEDICAL PROBLEMS
- Diabetes Mellitus Type 2 (on oral hypoglycaemics x 8 yrs)
- Hypertension (controlled, on ARB)
- CKD Stage 3 (diagnosed 2022)

SIGNIFICANT PHYSICAL FINDINGS
BP: 158/96 mmHg   HR: 88 bpm   SpO2: 94% RA
Bilateral pitting oedema up to mid-shin.

DIAGNOSIS DURING THIS ADMISSION
1. Acute Kidney Injury (AKI) on background CKD Stage 3
2. Hypertensive urgency

DIAGNOSTIC & THERAPEUTIC PROCEDURES
- Renal ultrasound: bilateral echogenic kidneys
- Haemodialysis x 2 sessions

MANAGEMENT DURING ADMISSION
INJ Furosemide 40mg IV OD
TAB Amlodipine 5mg PO OD
TAB Losartan 50mg PO OD
""",
    2: """SIUT — DISCHARGE SUMMARY

Patient Ref  : 00312-KHI
Source File  : 490434.txt
Admitted     : 10-Jun-2026
Discharged   : 17-Jun-2026

REASON FOR ADMISSION
Patient presented with high-grade fever, productive cough,
and progressive shortness of breath for 5 days.

BACKGROUND MEDICAL PROBLEMS
- Hypertension (on antihypertensives x 3 yrs)
- No prior respiratory illness

SIGNIFICANT PHYSICAL FINDINGS
BP: 146/92 mmHg   HR: 102 bpm   Temp: 38.9°C   SpO2: 91% RA
Bilateral lower zone crepitations on auscultation.
Mild bilateral pedal oedema noted.

DIAGNOSIS DURING THIS ADMISSION
1. RSV Pneumonia (confirmed on respiratory panel PCR)
2. Essential Hypertension

DIAGNOSTIC & THERAPEUTIC PROCEDURES
- Chest X-ray: bilateral infiltrates, lower zone predominant
- Respiratory viral panel PCR: RSV positive
- Sputum culture: no growth

MANAGEMENT DURING ADMISSION
INJ Ceftriaxone 1g IV BD
TAB Azithromycin 500mg PO OD
INJ Methylprednisolone 40mg IV OD
TAB Amlodipine 5mg PO OD
O2 via nasal prongs at 4L/min
"""
}

FAKE_SUGGESTIONS = [
    {
        "suggestion_id": 101,
        "document_id": 1,
        "suggestion_type": "diagnosis_principal",
        "extracted_text": "Acute Kidney Injury",
        "icd_code": "N17.9",
        "icd_description": "Acute kidney injury, unspecified",
        "confidence_score": 0.52,
        "source_snippet": "Acute Kidney Injury (AKI) on background CKD Stage 3",
        "source_char_start": 245,
        "source_char_end": 290,
        "is_ambiguous": True,
        "ambiguity_reason": "Low confidence — verify with coder",
        "coder_decision": None,
    },
    {
        "suggestion_id": 102,
        "document_id": 1,
        "suggestion_type": "diagnosis_associative",
        "extracted_text": "Type 2 Diabetes",
        "icd_code": "E11.9",
        "icd_description": "Type 2 diabetes mellitus without complications",
        "confidence_score": 0.88,
        "source_snippet": "Diabetes Mellitus Type 2 (on oral hypoglycaemics x 8 yrs)",
        "source_char_start": 310,
        "source_char_end": 368,
        "is_ambiguous": False,
        "ambiguity_reason": "",
        "coder_decision": None,
    },
    {
        "suggestion_id": 103,
        "document_id": 1,
        "suggestion_type": "diagnosis_associative",
        "extracted_text": "Hypertensive urgency",
        "icd_code": "I10",
        "icd_description": "Essential (primary) hypertension",
        "confidence_score": 0.85,
        "source_snippet": "Hypertensive urgency",
        "source_char_start": 400,
        "source_char_end": 420,
        "is_ambiguous": False,
        "ambiguity_reason": "",
        "coder_decision": None,
    },
    {
        "suggestion_id": 104,
        "document_id": 1,
        "suggestion_type": "procedure",
        "extracted_text": "Haemodialysis",
        "icd_code": "5A1D70Z",
        "icd_description": "Performance of Urinary Filtration (Haemodialysis)",
        "confidence_score": 0.95,
        "source_snippet": "Haemodialysis x 2 sessions",
        "source_char_start": 500,
        "source_char_end": 525,
        "is_ambiguous": False,
        "ambiguity_reason": "",
        "coder_decision": None,
    },
    {
        "suggestion_id": 105,
        "document_id": 1,
        "suggestion_type": "medication",
        "extracted_text": "Furosemide",
        "icd_code": "—",
        "icd_description": "Furosemide 40mg IV OD",
        "confidence_score": 0.99,
        "source_snippet": "INJ Furosemide 40mg IV OD",
        "source_char_start": 600,
        "source_char_end": 625,
        "is_ambiguous": False,
        "ambiguity_reason": "",
        "coder_decision": None,
    },
    # ── document 2 suggestions ─────────────────────────────────────────────────
    {
        "suggestion_id": 201,
        "document_id": 2,
        "suggestion_type": "diagnosis_principal",
        "extracted_text": "RSV Pneumonia",
        "icd_code": "J12.1",
        "icd_description": "Respiratory syncytial virus pneumonia",
        "confidence_score": 0.76,
        "source_snippet": "RSV Pneumonia (confirmed on respiratory panel PCR)",
        "source_char_start": 310,
        "source_char_end": 360,
        "is_ambiguous": True,
        "ambiguity_reason": "J12.0 may be more specific — verify with coder",
        "coder_decision": None,
    },
    {
        "suggestion_id": 202,
        "document_id": 2,
        "suggestion_type": "diagnosis_associative",
        "extracted_text": "Essential Hypertension",
        "icd_code": "I10",
        "icd_description": "Essential (primary) hypertension",
        "confidence_score": 0.91,
        "source_snippet": "Essential Hypertension",
        "source_char_start": 380,
        "source_char_end": 402,
        "is_ambiguous": False,
        "ambiguity_reason": "",
        "coder_decision": None,
    },
    {
        "suggestion_id": 203,
        "document_id": 2,
        "suggestion_type": "diagnosis_associative",
        "extracted_text": "pedal oedema",
        "icd_code": "R60.9",
        "icd_description": "Oedema, unspecified",
        "confidence_score": 0.61,
        "source_snippet": "Mild bilateral pedal oedema noted",
        "source_char_start": 290,
        "source_char_end": 322,
        "is_ambiguous": True,
        "ambiguity_reason": "Oedema may be secondary to pneumonia — confirm if codeable separately",
        "coder_decision": None,
    },
    {
        "suggestion_id": 204,
        "document_id": 2,
        "suggestion_type": "procedure",
        "extracted_text": "Chest X-ray",
        "icd_code": "BW03ZZZ",
        "icd_description": "Plain Radiography of Chest",
        "confidence_score": 0.97,
        "source_snippet": "Chest X-ray: bilateral infiltrates, lower zone predominant",
        "source_char_start": 430,
        "source_char_end": 488,
        "is_ambiguous": False,
        "ambiguity_reason": "",
        "coder_decision": None,
    },
    {
        "suggestion_id": 205,
        "document_id": 2,
        "suggestion_type": "medication",
        "extracted_text": "Ceftriaxone",
        "icd_code": "—",
        "icd_description": "Ceftriaxone 1g IV BD",
        "confidence_score": 0.99,
        "source_snippet": "INJ Ceftriaxone 1g IV BD",
        "source_char_start": 550,
        "source_char_end": 574,
        "is_ambiguous": False,
        "ambiguity_reason": "",
        "coder_decision": None,
    },
]

FAKE_CHAT_HISTORY = [
    {
        "message_id": 1,
        "document_id": 1,
        "sender": "system",
        "message_text": "Hello! I can answer questions about any suggestion.",
        "related_suggestion_id": None,
    }
]


FAKE_CORRECTIONS = [
    {
        "correction_id": 1, "suggestion_id": 101,
        "original_icd_code": "N17.9", "corrected_icd_code": None,
        "icd_description": "Acute kidney injury, unspecified",
        "correction_type": "accept", "coder_name": "Fatimah M.",
        "comment": "", "corrected_at": "2026-06-12T14:32:00",
        "document_id": 1, "patient_ref": "00247-KHI",
        "source_filename": "051904.txt",
    },
    {
        "correction_id": 2, "suggestion_id": 102,
        "original_icd_code": "E11.9", "corrected_icd_code": None,
        "icd_description": "Type 2 diabetes mellitus without complications",
        "correction_type": "accept", "coder_name": "Fatimah M.",
        "comment": "", "corrected_at": "2026-06-12T14:33:00",
        "document_id": 1, "patient_ref": "00247-KHI",
        "source_filename": "051904.txt",
    },
    {
        "correction_id": 3, "suggestion_id": 103,
        "original_icd_code": "I10", "corrected_icd_code": None,
        "icd_description": "Essential (primary) hypertension",
        "correction_type": "reject", "coder_name": "Fatimah M.",
        "comment": "Not relevant to this admission",
        "corrected_at": "2026-06-12T14:34:00",
        "document_id": 1, "patient_ref": "00247-KHI",
        "source_filename": "051904.txt",
    },
    {
        "correction_id": 4, "suggestion_id": 104,
        "original_icd_code": "5A1D70Z", "corrected_icd_code": None,
        "icd_description": "Performance of Urinary Filtration (Haemodialysis)",
        "correction_type": "accept", "coder_name": "Fatimah M.",
        "comment": "", "corrected_at": "2026-06-12T14:34:00",
        "document_id": 1, "patient_ref": "00247-KHI",
        "source_filename": "051904.txt",
    },
    {
        "correction_id": 5, "suggestion_id": 201,
        "original_icd_code": "J12.1", "corrected_icd_code": "J12.0",
        "icd_description": "RSV Pneumonia",
        "correction_type": "edit", "coder_name": "Fatimah M.",
        "comment": "More specific code applies",
        "corrected_at": "2026-06-13T10:10:00",
        "document_id": 2, "patient_ref": "00312-KHI",
        "source_filename": "490434.txt",
    },
    {
        "correction_id": 6, "suggestion_id": 202,
        "original_icd_code": "I10", "corrected_icd_code": None,
        "icd_description": "Essential (primary) hypertension",
        "correction_type": "accept", "coder_name": "Fatimah M.",
        "comment": "", "corrected_at": "2026-06-13T10:11:00",
        "document_id": 2, "patient_ref": "00312-KHI",
        "source_filename": "490434.txt",
    },
    {
        "correction_id": 7, "suggestion_id": 203,
        "original_icd_code": "R60.9", "corrected_icd_code": None,
        "icd_description": "Oedema, unspecified",
        "correction_type": "reject", "coder_name": "Fatimah M.",
        "comment": "", "corrected_at": "2026-06-13T10:12:00",
        "document_id": 2, "patient_ref": "00312-KHI",
        "source_filename": "490434.txt",
    },
]

FAKE_ANALYTICS = {
    "total_documents":    24,
    "pending_documents":   7,
    "complete_documents": 17,
    "total_suggestions":  112,
    "accepted":            89,
    "rejected":            15,
    "edited":               8,
    "acceptance_rate":     0.79,
    "avg_confidence":      0.81,
    "flagged_ambiguous":    6,
    "top_corrected_codes": [
        {"icd_code": "N17.9",   "description": "Acute kidney injury, unspecified",        "corrections": 8},
        {"icd_code": "E11.9",   "description": "Type 2 diabetes mellitus",                "corrections": 5},
        {"icd_code": "I10",     "description": "Essential (primary) hypertension",        "corrections": 4},
        {"icd_code": "J18.9",   "description": "Pneumonia, unspecified organism",         "corrections": 3},
        {"icd_code": "N18.3",   "description": "Chronic kidney disease, stage 3",         "corrections": 2},
    ],
    "recent_activity": [
        {"action": "approved", "icd_code": "N17.9",          "coder": "Fatimah M.", "patient_ref": "00247-KHI", "timestamp": "2026-08-07T10:45:00"},
        {"action": "rejected", "icd_code": "I10",            "coder": "Fatimah M.", "patient_ref": "00247-KHI", "timestamp": "2026-08-07T10:44:00"},
        {"action": "edited",   "icd_code": "J12.1 → J12.0", "coder": "Fatimah M.", "patient_ref": "00312-KHI", "timestamp": "2026-08-06T15:22:00"},
        {"action": "approved", "icd_code": "E11.9",          "coder": "Fatimah M.", "patient_ref": "00312-KHI", "timestamp": "2026-08-06T15:21:00"},
        {"action": "approved", "icd_code": "5A1D70Z",        "coder": "Fatimah M.", "patient_ref": "00247-KHI", "timestamp": "2026-08-06T15:20:00"},
        {"action": "rejected", "icd_code": "R60.9",          "coder": "Fatimah M.", "patient_ref": "00312-KHI", "timestamp": "2026-08-06T15:19:00"},
    ],
}

FAKE_USERS = [
    {"username": "fatimah", "password": "coder123", "role": "coder",  "name": "Fatimah M."},
    {"username": "admin",   "password": "admin123",  "role": "admin",  "name": "Administrator"},
]

def login(username: str, password: str):
    match = next((u for u in FAKE_USERS if u["username"] == username), None)
    if match is None:
        return {"error": "user_not_found"}
    if match["password"] != password:
        return {"error": "wrong_password"}
    return {"token": "fake-jwt-token", "role": match["role"], "name": match["name"]}

def get_analytics():
    from collections import Counter
    # FAKE_CORRECTIONS is the single source of truth:
    # submit_decision writes here, submit_correction writes here, pre-seeded data is here
    accepted  = sum(1 for c in FAKE_CORRECTIONS if c.get("correction_type") == "accept")
    rejected  = sum(1 for c in FAKE_CORRECTIONS if c.get("correction_type") == "reject")
    edits     = [c for c in FAKE_CORRECTIONS if c.get("correction_type") == "edit"]
    total_dec = accepted + rejected + len(edits)
    acc_rate  = round(accepted / total_dec, 2) if total_dec else 0.0
    confs     = [s["confidence_score"] for s in FAKE_SUGGESTIONS if s.get("confidence_score")]
    avg_conf  = round(sum(confs) / len(confs), 2) if confs else 0.0
    complete  = [d for d in FAKE_DOCUMENTS if d.get("status") == "complete"]
    pending   = [d for d in FAKE_DOCUMENTS if d.get("status") != "complete"]

    # top corrected codes from corrections list
    code_counts = Counter(c["original_icd_code"] for c in FAKE_CORRECTIONS)
    top_codes = []
    for code, count in code_counts.most_common(5):
        desc = next((s["icd_description"] for s in FAKE_SUGGESTIONS
                     if s["icd_code"] == code), "")
        top_codes.append({"icd_code": code, "description": desc, "corrections": count})

    # recent activity from corrections, newest first
    recent = sorted(FAKE_CORRECTIONS, key=lambda c: c.get("corrected_at",""), reverse=True)[:6]
    activity = []
    for c in recent:
        activity.append({
            "action":      c.get("correction_type", ""),
            "icd_code":    c.get("corrected_icd_code") or c.get("original_icd_code", ""),
            "coder":       c.get("coder_name", ""),
            "patient_ref": c.get("patient_ref", ""),
            "timestamp":   c.get("corrected_at", ""),
        })

    return {
        "total_documents":    len(FAKE_DOCUMENTS),
        "pending_documents":  len(pending),
        "complete_documents": len(complete),
        "total_suggestions":  len(FAKE_SUGGESTIONS),
        "accepted":           accepted,
        "rejected":           rejected,
        "edited":             len(edits),
        "acceptance_rate":    acc_rate,
        "avg_confidence":     avg_conf,
        "flagged_ambiguous":  sum(1 for s in FAKE_SUGGESTIONS if s.get("is_ambiguous")),
        "top_corrected_codes": top_codes,
        "recent_activity":    activity,
    }

def get_corrections():
    return FAKE_CORRECTIONS

def get_documents():
    return FAKE_DOCUMENTS

def get_suggestions(document_id: int):
    return [s for s in FAKE_SUGGESTIONS if s["document_id"] == document_id]

def get_raw_text(document_id: int):
    return FAKE_RAW_TEXTS.get(document_id, "")

def submit_decision(suggestion_id: int, decision: str):
    from datetime import datetime
    # update suggestion row
    sugg = next((s for s in FAKE_SUGGESTIONS if s["suggestion_id"] == suggestion_id), {})
    sugg["coder_decision"] = decision

    # also write a correction record so analytics picks it up
    correction_type = "accept" if decision == "approved" else "reject"
    new_id = max((c["correction_id"] for c in FAKE_CORRECTIONS), default=0) + 1
    FAKE_CORRECTIONS.append({
        "correction_id":      new_id,
        "suggestion_id":      suggestion_id,
        "original_icd_code":  sugg.get("icd_code", ""),
        "corrected_icd_code": None,
        "icd_description":    sugg.get("icd_description", ""),
        "correction_type":    correction_type,
        "coder_name":         "Fatimah M.",
        "comment":            "",
        "corrected_at":       datetime.now().isoformat(timespec="seconds"),
        "document_id":        sugg.get("document_id", 0),
        "patient_ref":        next((d["patient_ref"] for d in FAKE_DOCUMENTS
                                    if d["document_id"] == sugg.get("document_id")), ""),
        "source_filename":    next((d["source_filename"] for d in FAKE_DOCUMENTS
                                    if d["document_id"] == sugg.get("document_id")), ""),
    })
    return {"status": "ok"}

def submit_correction(suggestion_id: int, corrected_icd_code: str):
    from datetime import datetime
    sugg = next((s for s in FAKE_SUGGESTIONS if s["suggestion_id"] == suggestion_id), {})
    new_id = max((c["correction_id"] for c in FAKE_CORRECTIONS), default=0) + 1
    FAKE_CORRECTIONS.append({
        "correction_id":      new_id,
        "suggestion_id":      suggestion_id,
        "original_icd_code":  sugg.get("icd_code", ""),
        "corrected_icd_code": corrected_icd_code,
        "icd_description":    sugg.get("icd_description", ""),
        "correction_type":    "edit",
        "coder_name":         "Fatimah M.",
        "comment":            "",
        "corrected_at":       datetime.now().isoformat(timespec="seconds"),
        "document_id":        sugg.get("document_id", 0),
        "patient_ref":        next((d["patient_ref"] for d in FAKE_DOCUMENTS
                                    if d["document_id"] == sugg.get("document_id")), ""),
        "source_filename":    next((d["source_filename"] for d in FAKE_DOCUMENTS
                                    if d["document_id"] == sugg.get("document_id")), ""),
    })
    return {"status": "ok"}

def get_chat_history(document_id: int):
    return [m for m in FAKE_CHAT_HISTORY if m["document_id"] == document_id]

def send_chat(document_id: int, message: str):
    from chatbot import generate_response
    suggestions = get_suggestions(document_id)
    raw_text    = get_raw_text(document_id)
    answer      = generate_response(message, suggestions, raw_text)
    return {"answer": answer}

def mark_complete(document_id: int):
    for doc in FAKE_DOCUMENTS:
        if doc["document_id"] == document_id:
            doc["status"] = "complete"
            break
    print(f"[FAKE] Document {document_id} marked complete")
    return {"status": "ok"}

def upload_document(filepath: str, patient_ref: str = ""):
    import os
    from datetime import date
    new_id = max(d["document_id"] for d in FAKE_DOCUMENTS) + 1

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        raw_text = f.read()
    FAKE_RAW_TEXTS[new_id] = raw_text

    FAKE_DOCUMENTS.append({
        "document_id":     new_id,
        "patient_ref":     patient_ref or f"REF-{new_id:04d}",
        "source_filename": os.path.basename(filepath),
        "upload_date":     str(date.today()),
        "status":          "pending",
        "raw_text":        raw_text,
        "notes":           ""
    })
    print(f"[FAKE] Uploaded {os.path.basename(filepath)} → document_id={new_id}")
    return {"document_id": new_id, "suggestions_generated": 0}
