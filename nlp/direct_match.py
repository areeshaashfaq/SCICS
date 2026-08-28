
# direct_match.py — run alongside NLP.
# Option 1 — Direct diagnosis-line extraction
#     The diagnosis section is a doctor-written list of conditions.
#     Each line/phrase is extracted directly as a candidate, bypassing NLP
#     entity detection entirely. This catches conditions NLP missed due to
#     typos, rare terminology or OCR noise.

# Option 2 — Medication → Z-code inference
#     ICD-10 Z79.x codes represent long-term drug use and are assigned
#     whenever a patient is on a chronic medication. These codes are never
#     found by reading clinical text — they come from knowing the drug.
#     The map here is built from ICD-10-CM coding rules, not from the
#     7 samples, so it generalises to any discharge summary.


from text_filters import is_measurement_noise, is_negated_phrase
import re


# DIRECT DIAGNOSIS LINE EXTRACTION
# ignore timestamps 
_TIMESTAMP = re.compile(
    r"\d{1,2}-[A-Z]{3}-\d{2,4}\s+\d{2}:\d{2}:\d{2}\s*", re.IGNORECASE
)

# Prefixes that introduce the diagnosis but are not part of the diagnosis
_DX_PREFIX = re.compile(
    r"^(known\s+case\s+of|known\s+case|k/c\s+of|k/c|h/o\s+of|h/o|"
    r"now\s+with|admitted\s+with|c/o|c/o\s+of|"
    r"background\s+of|history\s+of|presented\s+with)\s*",
    re.IGNORECASE
)

_PAREN_DETAIL = re.compile(r"\([^)]{0,60}\)")
# Trailing qualifiers that don't affect the ICD code
_TRAILING_NOISE = re.compile(
    r"\s+(since\s+\d.*|for\s+\d.*|\d+\s+years.*|\d+\s+months.*"
    r"|grade\s+\d.*|stage\s+\d.*|type\s+\d.*)$",
    re.IGNORECASE
)

# splits chronic conditions from acute ones
_NOW_WITH = re.compile(r"\.\s*now\s+with\s*|\bNOW\s+WITH\b", re.IGNORECASE)

# Splits on ;  ,  .  and  / (SIUT summaries often use "IDA/anal fissure" style)
_PHRASE_SEP = re.compile(r"[;,\.\/]\s*|\s*\band\b\s*", re.IGNORECASE)

_MIN_PHRASE_LEN = 5

# Single words that are not standalone diagnoses
# NOTE: "bilateral" / "unilateral" / "right" / "left" are intentionally NOT stopwords
# because they carry laterality information the ICD-10-CM matcher needs.
_STOPWORDS = {
    "stable", "discharge", "admission", "patient", "relapse",
    "positive", "negative", "mild", "moderate", "severe",
    "acute", "chronic",
}


def _clean_phrase(text):
    text = _TIMESTAMP.sub("", text)
    text = _PAREN_DETAIL.sub("", text)
    text = _DX_PREFIX.sub("", text)
    text = _TRAILING_NOISE.sub("", text)
    text = text.strip(" .,;-•\t")
    return text


def extract_diagnosis_phrases(sections, diag_tags=None):
    if diag_tags is None:
        diag_tags = {"acute": [], "chronic": []}

    acute_lower   = {l.strip().lower() for l in diag_tags.get("acute",   [])}
    chronic_lower = {l.strip().lower() for l in diag_tags.get("chronic", [])}

    results  = []
    seen     = set()

    # Sections to process with direct diagnosis matching.
    # Procedures and physical_findings sections often contain diagnostic findings
    # ("fissuring of distal duodenum", "nodularity in terminal ileum") that map
    # to diagnosis codes, not procedure codes. Include them at lower confidence.
    target_sections = {
        "diagnosis":            (1.00, False),
        "reason_for_admission": (0.85, False),
        "background":           (0.80, True),
        "procedures":           (0.70, False),   # findings inside procedure reports
        "physical_findings":    (0.70, False),   # findings on exam
    }

    for section_key, (base_conf, force_historical) in target_sections.items():
        section_text = sections.get(section_key, "")
        if not section_text or not section_text.strip():
            continue

        # Split on "NOW WITH" first to separate chronic from acute segments
        if section_key == "diagnosis" and _NOW_WITH.search(section_text):
            parts = _NOW_WITH.split(section_text, maxsplit=1)
            chronic_segment = parts[0]
            acute_segment   = parts[1] if len(parts) > 1 else ""
        else:
            chronic_segment = "" if not force_historical else section_text
            acute_segment   = section_text if not force_historical else ""

        for segment, is_historical in [
            (chronic_segment, True),
            (acute_segment,   force_historical),
        ]:
            if not segment.strip():
                continue

            # Split segment into individual lines
            lines = re.split(r"[\n]", segment)
            for line in lines:
                line = _TIMESTAMP.sub("", line).strip()
                if not line:
                    continue

                # Split each line into phrases
                phrases = _PHRASE_SEP.split(line)

                for phrase in phrases:
                    clean = _clean_phrase(phrase)

                    if len(clean) < _MIN_PHRASE_LEN:
                        continue
                    if clean.lower() in _STOPWORDS:
                        continue
                    if re.match(r"^[\d\s\.\,\-\/]+$", clean):
                        continue
                    if is_measurement_noise(clean):
                        continue
                    if is_negated_phrase(clean):
                        continue

                    key = clean.lower()
                    if key in seen:
                        continue
                    seen.add(key)

                    if not is_historical:
                        if any(clean.lower() in al for al in acute_lower):
                            is_historical = False
                        elif any(clean.lower() in cl for cl in chronic_lower):
                            is_historical = True

                    if section_key == "diagnosis":
                        sugg_type = ("diagnosis_associative" if is_historical
                                     else "diagnosis_principal")
                    else:
                        sugg_type = "diagnosis_associative"
                    pos = section_text.find(phrase.strip())
                    if pos == -1:
                        pos = 0

                    results.append({
                        "extracted_text":    clean,
                        "suggestion_type":   sugg_type,
                        "source_char_start": pos,
                        "source_char_end":   pos + len(clean),
                        "source_snippet":    clean,
                        "is_ambiguous":      False,
                        "ambiguity_reason":  None,
                        "icd_code":          None,
                        "confidence_score":  None,
                        "coder_decision":    "pending",
                        "negated":           False,
                        "source_section":    section_key,
                        "entity_type":       "DISEASE",
                        "base_confidence":   base_conf,
                        "source":            "direct_line",  
                    })

    return results


#  PROCEDURE LINE EXTRACTION
#  bc5cdr NER doesn't tag procedures — this pulls procedure lines directly
#  from the "procedures", "management", and "physical_findings" sections
#  so the fuzzy_procedure matcher can score them against Procedure.csv.

def extract_procedure_entities(sections):
    from pipeline import extract_procedures
    proc_dict = extract_procedures(sections)
    results = []
    seen    = set()

    # First procedure from the procedures section = principal.
    principal_assigned = False

    section_to_key = {
        "from_procedures":         ("procedures", 0.85),
        "from_management":         ("management", 0.75),
        "from_physical_findings":  ("physical_findings", 0.70),
        "from_reason":             ("reason_for_admission", 0.75),
    }

    for src_key, lines in proc_dict.items():
        section_key, base_conf = section_to_key.get(src_key, ("procedures", 0.70))
        for line in lines:
            clean = line.strip(" -.,;•\t")
            if len(clean) < 4:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)

            if src_key == "from_procedures" and not principal_assigned:
                sugg_type = "procedure_principal"
                principal_assigned = True
            else:
                sugg_type = "procedure_associative"

            results.append({
                "extracted_text":    clean,
                "suggestion_type":   sugg_type,
                "source_char_start": 0,
                "source_char_end":   len(clean),
                "source_snippet":    clean,
                "is_ambiguous":      False,
                "ambiguity_reason":  None,
                "icd_code":          None,
                "confidence_score":  None,
                "coder_decision":    "pending",
                "negated":           False,
                "source_section":    section_key,
                "entity_type":       "PROCEDURE",
                "base_confidence":   base_conf,
                "source":            "procedure_line",
            })
    return results


#  MEDICATION → Z-CODE INFERENCE

_MED_ZCODE_MAP = {
    # Anticoagulants
    "enoxaparin":        ("Z79.01", "Long-term use of anticoagulants",           0.90),
    "heparin":           ("Z79.01", "Long-term use of anticoagulants",           0.90),
    "warfarin":          ("Z79.01", "Long-term use of anticoagulants",           0.90),
    "rivaroxaban":       ("Z79.01", "Long-term use of anticoagulants",           0.90),
    "apixaban":          ("Z79.01", "Long-term use of anticoagulants",           0.90),
    "dabigatran":        ("Z79.01", "Long-term use of anticoagulants",           0.90),

    # Antiplatelets
    "aspirin":           ("Z79.82", "Long-term use of aspirin",                  0.90),
    "clopidogrel":       ("Z79.02", "Long-term use of antithrombotics",          0.88),

    # Insulin
    "insulin":           ("Z79.4",  "Long-term current use of insulin",          0.95),

    # Oral hypoglycemics
    "metformin":         ("Z79.84", "Long-term use of oral hypoglycemic drugs",  0.90),
    "glimepiride":       ("Z79.84", "Long-term use of oral hypoglycemic drugs",  0.90),
    "glibenclamide":     ("Z79.84", "Long-term use of oral hypoglycemic drugs",  0.90),
    "gliclazide":        ("Z79.84", "Long-term use of oral hypoglycemic drugs",  0.90),
    "sitagliptin":       ("Z79.84", "Long-term use of oral hypoglycemic drugs",  0.88),
    "empagliflozin":     ("Z79.84", "Long-term use of oral hypoglycemic drugs",  0.88),

    # Systemic steroids
    "prednisolone":      ("Z79.52", "Long-term use of systemic steroids",        0.90),
    "methylprednisolone":("Z79.52", "Long-term use of systemic steroids",        0.90),
    "dexamethasone":     ("Z79.52", "Long-term use of systemic steroids",        0.90),
    "hydrocortisone":    ("Z79.52", "Long-term use of systemic steroids",        0.88),
    "prednisone":        ("Z79.52", "Long-term use of systemic steroids",        0.88),

    # Long-term antibiotics
    "co-trimoxazole":    ("Z79.2",  "Long-term use of antibiotics",              0.85),
    "trimethoprim":      ("Z79.2",  "Long-term use of antibiotics",              0.85),
    "azithromycin":      ("Z79.2",  "Long-term use of antibiotics",              0.82),
    "doxycycline":       ("Z79.2",  "Long-term use of antibiotics",              0.82),

    # Immunosuppressants / biologics
    "rituximab":         ("Z79.899","Long-term use of other medication",         0.85),
    "mycophenolate":     ("Z79.899","Long-term use of other medication",         0.85),
    "tacrolimus":        ("Z79.899","Long-term use of other medication",         0.85),
    "cyclosporine":      ("Z79.899","Long-term use of other medication",         0.85),
    "azathioprine":      ("Z79.899","Long-term use of other medication",         0.85),

    # NSAIDs
    "ibuprofen":         ("Z79.1",  "Long-term use of non-steroidal anti-inflammatory drugs", 0.85),
    "naproxen":          ("Z79.1",  "Long-term use of non-steroidal anti-inflammatory drugs", 0.85),
    "diclofenac":        ("Z79.1",  "Long-term use of non-steroidal anti-inflammatory drugs", 0.85),
    "celecoxib":         ("Z79.1",  "Long-term use of non-steroidal anti-inflammatory drugs", 0.85),
}

# Drugs where long-term use is routine/supportive and no Z-code is assigned
_NO_ZCODE_DRUGS = {
    "omeprazole", "pantoprazole", "esomeprazole", "lansoprazole",  # PPIs
    "sucralfate", "antacid", "oxethazaine", "magnesium hydroxide",  # antacids
    "lactulose", "nystatin", "fluconazole",                         # GI/antifungal
    "calcium carbonate", "vitamin d", "cholecalciferol",            # supplements
    "folic acid", "ferrous sulfate", "iron",                        # supplements
    "vitamin b", "thiamine", "pyridoxine", "cyanocobalamin",        # vitamins
    "paracetamol", "acetaminophen",                                 # PRN analgesia
    "lidocaine", "xylocaine",                                       # local
    "nitroglycerin", "glyceryl trinitrate",                         # PRN cardiac
}


# Sections where a drug's presence implies CHRONIC use (patient continues on discharge)
_CHRONIC_SECTIONS = {"background", "condition_at_discharge",
                     "followup_instructions", "followup_tests"}

# Keywords that flag chronic use even when the drug appears elsewhere
_CHRONIC_KEYWORDS = re.compile(
    r"\b(long\s*term|long-term|chronic(?:ally)?|maintenance|"
    r"years?|months?|since\s+\d|on\s+\w+\s+for\s+|"
    r"home\s+medication|regular\s+medication|continue\s+|"
    r"lifelong|life-long|daily\s+dose|maintenance\s+dose)\b",
    re.IGNORECASE
)


def _has_chronic_use_evidence(drug_key, sections):
    # Two ways to qualify a drug as CHRONIC:
    # 1. It shows up in a chronic section (background / discharge meds / followup)
    # 2. Chronic-use language appears within ~60 chars of the drug name anywhere
    for sect_name, sect_text in sections.items():
        if not sect_text:
            continue
        lower = sect_text.lower()
        if drug_key not in lower:
            continue
        if sect_name in _CHRONIC_SECTIONS:
            return True
        # Check a 60-char window around the drug mention for chronic keywords
        idx = lower.find(drug_key)
        while idx != -1:
            window = lower[max(0, idx - 60): idx + len(drug_key) + 60]
            if _CHRONIC_KEYWORDS.search(window):
                return True
            idx = lower.find(drug_key, idx + 1)
    return False


def infer_zcodes_from_meds(codeable_entities, sections=None):
    # Emit Z79 codes ONLY when there is evidence of chronic use.
    # Without `sections`, falls back to the old behaviour for backward compat,
    # but callers should always pass sections in production.
    results     = []
    seen_zcodes = set()

    for ent in codeable_entities:
        if ent.get("suggestion_type") != "medication":
            continue

        drug_text = ent["extracted_text"].lower()

        # Skip known no-Z-code supportive drugs
        if any(nd in drug_text for nd in _NO_ZCODE_DRUGS):
            continue

        for drug_key, (zcode, zdesc, zconf) in _MED_ZCODE_MAP.items():
            if drug_key not in drug_text:
                continue
            if zcode in seen_zcodes:
                break

            # Chronic-use gate — without sections, permissive; with sections, strict
            if sections is not None and not _has_chronic_use_evidence(drug_key, sections):
                break

            seen_zcodes.add(zcode)
            results.append({
                "extracted_text":    zdesc,
                "suggestion_type":   "diagnosis_associative",
                "source_char_start": ent["source_char_start"],
                "source_char_end":   ent["source_char_end"],
                "source_snippet":    f"inferred from chronic medication: {ent['extracted_text']}",
                "is_ambiguous":      False,
                "ambiguity_reason":  None,
                "icd_code":          zcode,
                "confidence_score":  zconf,
                "coder_decision":    "pending",
                "negated":           False,
                "source_section":    ent["source_section"],
                "entity_type":       "DISEASE",
                "base_confidence":   zconf,
                "source":            "med_inference",
            })
            break   # one drug match per entity is enough

    return results


# ADVERSE EFFECT / UNDERDOSING / STATUS Z-CODE INFERENCE (workbook chapter)
# Reads the full document text and emits T-codes for adverse drug effects,
# Z-codes for underdosing/noncompliance, and F/Z codes for social history
# (current smoker, former smoker, alcohol use). These are text-derivable
# codes that _MED_ZCODE_MAP alone cannot catch.

_ADVERSE_EFFECT_MAP = {
    # phrase trigger  →  (code, description, confidence)
    "adverse reaction to nsaid":   ("T39.395A", "Adverse effect of nonsteroidal anti-inflammatory drugs, initial encounter", 0.85),
    "reaction to ibuprofen":       ("T39.315A", "Adverse effect of propionic acid derivatives, initial encounter", 0.82),
    "reaction to diclofenac":      ("T39.395A", "Adverse effect of nonsteroidal anti-inflammatory drugs, initial encounter", 0.82),
    "adverse effect of steroid":   ("T38.0X5A", "Adverse effect of glucocorticoids, initial encounter", 0.85),
    "steroid induced":             ("T38.0X5A", "Adverse effect of glucocorticoids, initial encounter", 0.80),
    "penicillin allergy":          ("Z88.0",    "Allergy status to penicillin", 0.92),
    "sulfa allergy":               ("Z88.2",    "Allergy status to sulfonamides", 0.90),
    "nkda":                        (None,       None, 0.0),  # sentinel — do NOT emit code, just recognised
}

_STATUS_CODE_MAP = {
    # Social / behavioural history
    "current smoker":              ("F17.210", "Nicotine dependence, cigarettes, uncomplicated", 0.90),
    "still smoking":               ("F17.210", "Nicotine dependence, cigarettes, uncomplicated", 0.88),
    "cigarette use":               ("F17.210", "Nicotine dependence, cigarettes, uncomplicated", 0.85),
    "former smoker":               ("Z87.891", "Personal history of nicotine dependence", 0.92),
    "ex-smoker":                   ("Z87.891", "Personal history of nicotine dependence", 0.90),
    "quit smoking":                ("Z87.891", "Personal history of nicotine dependence", 0.88),
    "alcohol dependence":          ("F10.20",  "Alcohol dependence, uncomplicated", 0.88),
    "alcohol abuse":               ("F10.10",  "Alcohol abuse, uncomplicated", 0.85),

    # Compliance
    "non-compliance":              ("Z91.19",  "Patient noncompliance with other medical treatment and regimen", 0.88),
    "noncompliance":               ("Z91.19",  "Patient noncompliance with other medical treatment and regimen", 0.88),
    "not taking medication":       ("Z91.128", "Patient's intentional underdosing of medication regimen for other reason", 0.82),
    "patient refused medication":  ("Z91.128", "Patient's intentional underdosing of medication regimen for other reason", 0.82),
    "financial hardship":          ("Z91.120", "Patient's intentional underdosing of medication regimen due to financial hardship", 0.80),

    # Body mass index / lifestyle
    "morbidly obese":              ("E66.01",  "Morbid (severe) obesity due to excess calories", 0.85),
    "overweight":                  ("E66.3",   "Overweight", 0.80),
}


def infer_adverse_and_status_codes(sections):
    # Scans the full document (all sections concatenated) for phrase triggers.
    # Emits at most one entity per code (deduplicated).
    full_text = " ".join(v for v in sections.values() if v).lower()
    results     = []
    seen_codes  = set()

    combined = {**_ADVERSE_EFFECT_MAP, **_STATUS_CODE_MAP}
    for phrase, (code, desc, conf) in combined.items():
        if code is None:
            continue
        if phrase in full_text and code not in seen_codes:
            seen_codes.add(code)
            results.append({
                "extracted_text":    phrase,
                "suggestion_type":   "diagnosis_associative",
                "source_char_start": 0,
                "source_char_end":   len(phrase),
                "source_snippet":    f"inferred from phrase: '{phrase}'",
                "is_ambiguous":      False,
                "ambiguity_reason":  None,
                "icd_code":          code,
                "icd_description":   desc,
                "confidence_score":  conf,
                "coder_decision":    "pending",
                "negated":           False,
                "source_section":    "inferred",
                "entity_type":       "STATUS",
                "base_confidence":   conf,
                "source":            "status_inference",
            })
    return results


# MERGE — combine NLP + direct_line + med_inference + status_inference results
def merge_all_entities(nlp_entities, direct_entities, zcode_entities, status_entities=None, procedure_entities=None):
    """
    Merge all three entity lists, deduplicating on extracted_text.lower().
    NLP entities take priority over direct-line duplicates (NLP has richer
    context flags). Z-code entities are always kept since they're unique codes.
    """
    seen_text = {e["extracted_text"].lower() for e in nlp_entities}
    merged = list(nlp_entities)

    for e in direct_entities:
        if e["extracted_text"].lower() not in seen_text:
            seen_text.add(e["extracted_text"].lower())
            merged.append(e)

    # Z-code entities are keyed by icd_code, not text — always unique
    seen_zcodes = set()
    for e in zcode_entities:
        zc = e.get("icd_code")
        if zc and zc not in seen_zcodes:
            seen_zcodes.add(zc)
            merged.append(e)

    # Status/adverse-effect entities also keyed by icd_code
    if status_entities:
        for e in status_entities:
            sc = e.get("icd_code")
            if sc and sc not in seen_zcodes:
                seen_zcodes.add(sc)
                merged.append(e)

    # Procedure entities — dedupe on extracted_text (no icd_code yet)
    if procedure_entities:
        seen_proc = {e["extracted_text"].lower() for e in merged}
        for e in procedure_entities:
            t = e["extracted_text"].lower()
            if t not in seen_proc:
                seen_proc.add(t)
                merged.append(e)

    return merged


# Main — test on all samples

if __name__ == "__main__":
    from pipeline import load_all_samples, clean_text, parse_sections, tag_diagnosis_lines
    from abbreviations import expand_sections
    from nlp_extractor import extract_entities, filter_codeable

    samples = load_all_samples()

    for filename, raw in sorted(samples.items()):
        print("=" * 65)
        print(f"FILE: {filename}")
        print("=" * 65)

        cleaned   = clean_text(raw)
        sections  = parse_sections(cleaned)
        expanded  = expand_sections(sections)
        diag_tags = tag_diagnosis_lines(sections.get("diagnosis", ""))

        # All five strategies
        nlp_ents    = filter_codeable(extract_entities(expanded, diag_tags))
        direct_ents = extract_diagnosis_phrases(sections, diag_tags)
        zcode_ents  = infer_zcodes_from_meds(nlp_ents, sections)
        status_ents = infer_adverse_and_status_codes(sections)
        proc_ents   = extract_procedure_entities(sections)

        merged = merge_all_entities(nlp_ents, direct_ents, zcode_ents, status_ents, proc_ents)

        nlp_only    = [e for e in merged if e.get("source") != "direct_line"
                       and e.get("source") != "med_inference"]
        direct_only = [e for e in merged if e.get("source") == "direct_line"]
        zcode_only  = [e for e in merged if e.get("source") == "med_inference"]

        print(f"  NLP:         {len(nlp_only):3} entities")
        print(f"  Direct line: {len(direct_only):3} entities  (new phrases NLP missed)")
        print(f"  Z-codes:     {len(zcode_only):3} entities  (from medication inference)")
        print(f"  TOTAL:       {len(merged):3} codeable entities")
        print()

        if direct_only:
            print("  ── NEW from direct line matching ──")
            for e in direct_only:
                print(f"    [{e['suggestion_type']:<28}] "
                      f"conf:{e['base_confidence']:.2f}  {e['extracted_text']}")

        if zcode_only:
            print("  ── Z-codes inferred from medications ──")
            for e in zcode_only:
                print(f"    {e['icd_code']}  conf:{e['confidence_score']:.2f}  "
                      f"{e['extracted_text']}")
        print()
