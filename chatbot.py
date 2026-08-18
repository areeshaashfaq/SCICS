import re
from rapidfuzz import fuzz

# ── ICD code regex ─────────────────────────────────────────────────────────────
_ICD_RE = re.compile(r'\b([A-Z]\d{1,2}\.?\d*)\b', re.IGNORECASE)

def _extract_code(message: str):
    m = _ICD_RE.search(message)
    return m.group(1).upper() if m else None

def _find_suggestion(code: str, suggestions: list):
    if not code:
        return None
    return next((s for s in suggestions if s.get("icd_code", "").upper() == code), None)

def _fuzzy_match(message: str, keywords: list, threshold: int = 70) -> bool:
    msg = message.lower()
    words = msg.split()
    for kw in keywords:
        if kw in msg:
            return True
        for word in words:
            if fuzz.ratio(word, kw) >= threshold:
                return True
    return False

# ── intent routing ─────────────────────────────────────────────────────────────
_INTENTS = [
    ("ask_why",        ["why", "reason", "how come", "basis", "how did you get",
                        "how was", "what made", "explain why"]),
    ("ask_evidence",   ["evidence", "source", "where", "found in", "support",
                        "text", "snippet", "phrase", "mention", "show me"]),
    ("ask_confidence", ["confidence", "confident", "sure", "certain", "score",
                        "percent", "accurate", "accuracy", "how sure"]),
    ("ask_ambiguous",  ["ambiguous", "flagged", "flag", "unclear", "uncertain",
                        "warning", "ambiguity", "unsure"]),
    ("ask_meaning",    ["mean", "describe", "definition", "explain",
                        "stands for", "full form", "what is", "what does"]),
    ("ask_principal",  ["principal", "primary", "main diagnosis", "main",
                        "primary diagnosis", "most important"]),
    ("ask_procedures", ["procedure", "procedures", "surgery", "surgeries",
                        "intervention", "operation", "done", "performed"]),
    ("ask_meds",       ["medication", "medications", "drug", "drugs",
                        "medicine", "prescribed", "tablet", "injection"]),
    ("ask_all",        ["all", "list", "show all", "every", "codes",
                        "suggestions", "summary", "everything"]),
]

def _detect_intent(message: str) -> str:
    for intent, keywords in _INTENTS:
        if _fuzzy_match(message, keywords):
            return intent
    return "unknown"


def _ask_why(code, target, suggestions):
    if not code:
        return "Which code are you asking about? Try: \"Why was N17.9 suggested?\""
    if not target:
        return f"No suggestion found for code {code} in this document."
    snippet = target.get("source_snippet") or "—"
    conf    = int((target.get("confidence_score") or 0) * 100)
    ext     = target.get("extracted_text") or target.get("icd_code")
    return (f"{target['icd_code']} ({target.get('icd_description','')}) was suggested "
            f"because the phrase \"{snippet}\" was found in the discharge summary. "
            f"The extracted concept was \"{ext}\" with {conf}% confidence.")

def _ask_evidence(code, target, suggestions):
    if not code:
        return "Which code? Try: \"What evidence supports N17.9?\""
    if not target:
        return f"No suggestion found for code {code}."
    snippet = target.get("source_snippet") or "—"
    start   = target.get("source_char_start", "")
    end     = target.get("source_char_end", "")
    pos     = f" (characters {start}–{end})" if start else ""
    return (f"The evidence for {target['icd_code']} is the phrase: "
            f"\"{snippet}\"{pos} in the discharge summary.")

def _ask_confidence(code, target, suggestions):
    if not code:
        lines = [f"  • {s['icd_code']} — {int((s.get('confidence_score') or 0)*100)}%"
                 for s in suggestions]
        return "Confidence scores:\n" + "\n".join(lines) if lines else "No suggestions loaded."
    if not target:
        return f"No suggestion found for code {code}."
    conf = int((target.get("confidence_score") or 0) * 100)
    detail = ""
    if target.get("is_ambiguous"):
        detail = f" It is flagged as ambiguous: {target.get('ambiguity_reason','unclear match')}."
    return f"{target['icd_code']} has a confidence score of {conf}%.{detail}"

def _ask_ambiguous(code, target, suggestions):
    if code and target:
        if target.get("is_ambiguous"):
            return (f"{target['icd_code']} is flagged because: "
                    f"{target.get('ambiguity_reason') or 'the NLP match was ambiguous'}.")
        return f"{target['icd_code']} is not flagged as ambiguous."
    flagged = [s for s in suggestions if s.get("is_ambiguous")]
    if flagged:
        lines = [f"  • {s['icd_code']} — {s.get('ambiguity_reason','')}" for s in flagged]
        return "Flagged suggestions:\n" + "\n".join(lines)
    return "No suggestions are flagged as ambiguous for this document."

def _ask_meaning(code, target, suggestions):
    if not code:
        return "Which code? Try: \"What does N17.9 mean?\""
    if not target:
        return f"No suggestion found for code {code} in this document."
    return f"{target['icd_code']} — {target.get('icd_description','no description available')}."

def _ask_principal(suggestions):
    p = next((s for s in suggestions if s.get("suggestion_type") == "diagnosis_principal"), None)
    if p:
        conf = int((p.get("confidence_score") or 0) * 100)
        return (f"The principal diagnosis is {p['icd_code']} — "
                f"{p.get('icd_description','')} ({conf}% confidence).")
    return "No principal diagnosis has been identified for this document."

def _ask_procedures(suggestions):
    procs = [s for s in suggestions if "procedure" in s.get("suggestion_type", "")]
    if not procs:
        return "No procedures were identified in this document."
    lines = [f"  • {p['icd_code']} — {p.get('icd_description','')}" for p in procs]
    return "Coded procedures:\n" + "\n".join(lines)

def _ask_meds(suggestions):
    meds = [s for s in suggestions if s.get("suggestion_type") == "medication"]
    if not meds:
        return "No medications were identified in this document."
    lines = [f"  • {m['icd_code']} — {m.get('icd_description','')}" for m in meds]
    return "Medications:\n" + "\n".join(lines)

def _ask_all(suggestions):
    if not suggestions:
        return "No suggestions loaded for this document."
    from collections import defaultdict
    grouped = defaultdict(list)
    for s in suggestions:
        grouped[s.get("suggestion_type","other")].append(s)
    label_map = {
        "diagnosis_principal":   "Principal Diagnosis",
        "diagnosis_associative": "Associative Diagnoses",
        "procedure_principal":   "Procedures",
        "procedure_associative": "Procedures",
        "medication":            "Medications",
    }
    parts = []
    for stype, items in grouped.items():
        header = label_map.get(stype, stype.replace("_"," ").title())
        lines  = [f"  • {s['icd_code']} — {s.get('icd_description','')}" for s in items]
        parts.append(f"{header}:\n" + "\n".join(lines))
    return "\n\n".join(parts)

def _unknown():
    return (
        "I can answer questions about this document's ICD suggestions. Try:\n"
        "  • \"Why was N17.9 suggested?\"\n"
        "  • \"What does E11.9 mean?\"\n"
        "  • \"What evidence supports I10?\"\n"
        "  • \"What is the principal diagnosis?\"\n"
        "  • \"What procedures were coded?\"\n"
        "  • \"Why is N17.9 flagged?\"\n"
        "  • \"What is the confidence for N17.9?\"\n"
        "  • \"List all suggestions\""
    )

def generate_response(message: str, suggestions: list, raw_text: str = "") -> str:
    intent = _detect_intent(message)
    code   = _extract_code(message)
    target = _find_suggestion(code, suggestions)

    if intent == "ask_why":        return _ask_why(code, target, suggestions)
    if intent == "ask_evidence":   return _ask_evidence(code, target, suggestions)
    if intent == "ask_confidence": return _ask_confidence(code, target, suggestions)
    if intent == "ask_ambiguous":  return _ask_ambiguous(code, target, suggestions)
    if intent == "ask_meaning":    return _ask_meaning(code, target, suggestions)
    if intent == "ask_principal":  return _ask_principal(suggestions)
    if intent == "ask_procedures": return _ask_procedures(suggestions)
    if intent == "ask_meds":       return _ask_meds(suggestions)
    if intent == "ask_all":        return _ask_all(suggestions)
    return _unknown()