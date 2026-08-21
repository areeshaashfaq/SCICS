# proc_matcher.py — compositional ICD-10-PCS procedure matching.
#
# Why this exists:
#   PCS descriptions and clinical prose share almost no vocabulary.
#   A doctor writes "biopsies taken from terminal ileum and caecum";
#   PCS calls the same event "Excision of Ileum, Endoscopic, Diagnostic".
#   Fuzzy string matching cannot bridge that, and phrase lookup fails on
#   wording variants ("biopsy of cecum" vs "biopsies from caecum").
#
#   So instead of matching whole phrases, we detect the ACTION and the
#   BODY SITE independently, then look up the pair. One sentence can name
#   several sites, so this returns a LIST of codes, not a single code.
#
# Safety rule: every code emitted here already exists in the curated
# _PROC_SYNONYMS table. Nothing is invented.

import re

# (action, site) -> PCS code
_ACTION_SITE_CODES = {
    ("biopsy", "antrum"):        "0DB78ZX",
    ("biopsy", "stomach"):       "0DB78ZX",
    ("biopsy", "duodenum"):      "0DB98ZX",
    ("biopsy", "ileum"):         "0DBB8ZX",
    ("biopsy", "cecum"):         "0DBH8ZX",
    ("lavage", "lung"):          "0B9C8ZX",
    ("drainage", "left_lower_lobe"): "0B9J8ZX",
    ("tap", "pleura"):           "0W993ZX",
    ("sample", "csf"):           "009U3ZX",
    ("transfusion", "blood"):    "30233N1",
}

# Action vocabulary as clinicians write it.
_ACTIONS = {
        "biopsy": r"\b(biops(?:y|ies|ied)|bx|histopath\w*|histolog\w*|"
              r"specimen\s+taken|features\s+of|nodularity|mucosa\w*)\b",
    "lavage": r"\b(bronchoalveolar\s+lavage|bronchoalveoler\s+lavage|bal)\b",
    "drainage": r"\b(drain\w*|aspirat\w*)\b",
    # Pleural fluid being analysed at all implies it was obtained by tap.
    "tap": r"\b(pleural\s+tap|thoraco?centesis|pleural\s+aspirat\w*|"
           r"pleural\s+fluid)\b",
    "sample": r"\b(lumbar\s+puncture|\blp\b|csf\s+(?:study|studies|analysis|"
              r"sample|sent|examination|tlc|dr\b))\b",
    "transfusion": r"\b(transfus\w*|pcv\s+given|packed\s+cells?)\b",
}

# Body-site vocabulary, including British spellings and OCR-friendly variants.
_SITES = {
    "antrum":  r"\b(antrum|antral|gastric\s+antrum)\b",
    "stomach": r"\b(stomach|gastric\s+(?:body|mucosa)|pangastric)\b",
    "duodenum": r"\b(duoden\w*|d1\b|d2\b|bulb)\b",
    "ileum":   r"\b(ileum|ileal|terminal\s+ile\w*|ilcum)\b",
    "cecum":   r"\b(ca?ecum|ca?ecal|cccum)\b",
    "lung":    r"\b(lung|bronch\w*|alveolar|pulmonary)\b",
    "left_lower_lobe": r"\b(l(?:eft)?\s*lower\s+(?:lobe|zone)|lll)\b",
    "pleura":  r"\b(pleura\w*)\b",
    "csf":     r"\b(csf|cerebrospinal)\b",
    "blood":   r"\b(pcv|packed\s+cells?|prbc|blood|red\s+blood\s+cells?)\b",
}

# Actions whose own wording already fixes the body site, so no separate
# site word is required in the sentence ("BAL done" names no lung).
_SITE_IMPLIED_BY_ACTION = {("lavage", "lung"), ("tap", "pleura"), ("sample", "csf")}

# Guard against "no pleural fluid seen" being read as a tap.
_NO_PLEURAL_RE = re.compile(r"\bno\s+(?:significant\s+|obvious\s+)?pleural\b",
                            re.IGNORECASE)

_ACTION_RE = {k: re.compile(v, re.IGNORECASE) for k, v in _ACTIONS.items()}
_SITE_RE   = {k: re.compile(v, re.IGNORECASE) for k, v in _SITES.items()}

# Endoscopic biopsy codes only apply when a scope was actually used.
_SCOPE_RE = re.compile(
    r"\b(endoscop\w*|colonoscop\w*|gastroscop\w*|sigmoidoscop\w*|egd|"
    r"esophagogastroduodenoscop\w*|upper\s+gi|lower\s+gi|bronchoscop\w*)\b",
    re.IGNORECASE,
)

# Do not code a procedure that was explicitly not done or is still pending.
_NOT_PERFORMED_RE = re.compile(
    r"\b(not\s+(?:done|performed)|awaited|planned|to\s+be\s+done|pending|"
    r"advised|deferred|refused)\b",
    re.IGNORECASE,
)


def match_procedure_codes(text):
    """Return a list of (pcs_code, evidence) for every procedure named in text.

    One clinical sentence often documents several procedures, so several
    codes can come back from a single line.
    """
    if not text or not text.strip():
        return []

    t = text.lower()
    has_scope = bool(_SCOPE_RE.search(t))
    found, seen = [], set()

    for (action, site), code in _ACTION_SITE_CODES.items():
        if code in seen:
            continue
        a_match = _ACTION_RE[action].search(t)
        if not a_match:
            continue
        s_match = _SITE_RE[site].search(t)
        if not s_match and (action, site) not in _SITE_IMPLIED_BY_ACTION:
            continue
        if site == "pleura" and _NO_PLEURAL_RE.search(t):
            continue
        # Endoscopic GI biopsy codes require evidence a scope was used.
        if action == "biopsy" and not has_scope:
            continue
        # "biopsy awaited" is not a performed procedure.
        if _NOT_PERFORMED_RE.search(t):
            continue
        seen.add(code)
        evidence = (f"{a_match.group(0)} + {s_match.group(0)}"
                    if s_match else a_match.group(0))
        found.append((code, evidence))

    return found