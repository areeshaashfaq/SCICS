# text_filters.py — shared noise / negation / match-sanity filters.
#
# Added to stop three classes of bad suggestion reaching the coder:
#   1. Lab values and vital signs extracted as diagnoses ("alt 23 u", "bp 105")
#   2. Negated findings coded as if present ("no growth", "ana -ve")
#   3. Fuzzy matches with no real word in common ("ct cap with contrast"
#      scoring against "Contact with cat")

import re

# Lab analytes, vital-sign abbreviations and panel names. A phrase built around
# one of these is a measurement, not a diagnosis.
_LAB_VITAL_TOKENS = {
    "hb","hgb","hct","mcv","mch","mchc","tlc","dlc","plt","plts","pits","pit",
    "wbc","rbc","retic","esr","crp","ferritin","transferrin",
    "alt","ast","alp","ggt","ldh","inr","pt","ptt","aptt","bili","bilirubin",
    "albumin","globulin","protein","urea","creatinine","bun","egfr",
    "na","k","cl","hco3","ca","po4","mg","phosphate","bicarbonate",
    "rbs","fbs","hba1c","glucose","ketones","tsh","ft3","ft4","ige","iga","igg","igm",
    "bp","pr","hr","rr","spo2","sats","temp","gcs","bmi","afebrile","pulse",
    "ana","anca","afb","dr","cs","gs","xpert","mtb","titre","titer","level","levels",
    "c3","c4","r3","ef","aptt23","ratio","power","tone","bulk","jerks",
    "reflexes","clonus","plantars","pupils","min","sec","hrs",
}

# Exam/vital words that mean a measurement even with no number attached.
_STANDALONE_VITALS = {"afebrile","gcs","spo2","bmi","tpp","berl"}

# A number immediately followed by a unit of measure.
_UNIT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ug|ml|dl|dL|g|kg|iu|u|l|mmol|meq|mm|cm|"
    r"mmhg|%|f|c)\b|/\s*(?:dl|l|min|ml|hpf|mm3)\b|\b\d+\s*/\s*\d+\b",
    re.IGNORECASE,
)

# Phrases that assert absence. These are findings, not codeable diagnoses.
_NEGATION_LEAD = re.compile(
    r"^(no\b|not\b|nil\b|none\b|negative\b|absent\b|denies\b|without\b|"
    r"unremarkable\b|normal\b|nkda\b)",
    re.IGNORECASE,
)
_NEGATION_TRAIL = re.compile(
    r"(\-\s*ve\b|\bnegative\b|\bnot\s+detected\b|\bnil\b|\bno\s+growth\b|"
    r"\bunremarkable\b|\bwithin\s+normal\b|\bnormal\b)\s*[\.\,]?\s*$",
    re.IGNORECASE,
)

def is_negated_phrase(text):
    t = text.strip()
    return bool(_NEGATION_LEAD.match(t) or _NEGATION_TRAIL.search(t))

def is_measurement_noise(text):
    t = text.lower().strip()
    words = re.findall(r"[a-z]+", t)
    if not words:
        return True
    digits  = sum(c.isdigit() for c in t)
    letters = sum(c.isalpha() for c in t)
    if digits and digits / (digits + letters) > 0.30:
        return True
    if _UNIT_RE.search(t):
        return True
    if words[0] in _LAB_VITAL_TOKENS:
        return True
    if digits and any(w in _LAB_VITAL_TOKENS for w in words):
        return True
    if len(words) == 1 and words[0] in _LAB_VITAL_TOKENS:
        return True
    if any(w in _STANDALONE_VITALS for w in words):
        return True
    # A phrase that opens with a bare number is a reading, not a diagnosis
    # ("25 hydroxyvitamin d 10", "5 right ll", "62 pr 81").
    if re.match(r"^\d", t):
        return True
    return False

_STOP = {"with","without","and","the","of","in","on","for","to","was","were",
         "is","are","from","due","other","unspecified","site","not","elsewhere",
         "classified","specified","acute","chronic","left","right","both"}

def shares_content_word(query, definition):
    """At least one non-trivial word must be common to query and definition."""
    q = {w for w in re.findall(r"[a-z]{4,}", query.lower())  if w not in _STOP}
    d = {w for w in re.findall(r"[a-z]{4,}", definition.lower()) if w not in _STOP}
    if not q:
        return True   # nothing to check against; leave the score to decide
    if q & d:
        return True
    # allow stem overlap: "ulcer" vs "ulcers", "nephropathy" vs "nephropathies"
    if any(a.startswith(b[:5]) or b.startswith(a[:5]) for a in q for b in d):
        return True
    # allow spelling variants: melena/melaena, anemia/anaemia, edema/oedema
    from rapidfuzz import fuzz as _f
    return any(_f.ratio(a, b) >= 88 for a in q for b in d)