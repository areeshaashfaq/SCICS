
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

_PHRASE_SEP = re.compile(r"[;,\.]\s+|\s*\band\b\s*", re.IGNORECASE)

_MIN_PHRASE_LEN = 5

# Single words that are not standalone diagnoses
_STOPWORDS = {
    "stable", "discharge", "admission", "patient", "relapse",
    "positive", "negative", "mild", "moderate", "severe",
    "acute", "chronic", "bilateral", "unilateral",
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

    # Sections to process with direct matching
    target_sections = {
        "diagnosis":(1.00, False),  
        "reason_for_admission": (0.85, False),
        "background":(0.80, True),    
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


def infer_zcodes_from_meds(codeable_entities):
    # Takes the full list of codeable entities (output of filter_codeable).
    # For every medication entity whose drug name matches _MED_ZCODE_MAP,
    # returns a new entity dict with the Z-code pre-filled.

    # Z-codes are deduplicated — same Z-code from multiple drugs only appears once.
    
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
            if drug_key in drug_text:
                if zcode in seen_zcodes:
                    break
                seen_zcodes.add(zcode)

                results.append({
                    "extracted_text":    zdesc,
                    "suggestion_type":   "diagnosis_associative",
                    "source_char_start": ent["source_char_start"],
                    "source_char_end":   ent["source_char_end"],
                    "source_snippet":    f"inferred from medication: {ent['extracted_text']}",
                    "is_ambiguous":      False,
                    "ambiguity_reason":  None,
                    "icd_code":          zcode,          # pre-filled — no fuzzy needed
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


# MERGE — combine NLP + direct_line + med_inference results
def merge_all_entities(nlp_entities, direct_entities, zcode_entities):
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

        # All three strategies
        nlp_ents    = filter_codeable(extract_entities(expanded, diag_tags))
        direct_ents = extract_diagnosis_phrases(sections, diag_tags)
        zcode_ents  = infer_zcodes_from_meds(nlp_ents)

        merged = merge_all_entities(nlp_ents, direct_ents, zcode_ents)

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
