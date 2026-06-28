# fuzzy_match_icd.py — Stage 4 of the SCICS pipeline.
# Takes the entity pool from stages 1-3 and assigns ICD codes using two passes:
#   Pass A: Synonym reverse-lookup  (fast, for known SIUT phrases)
#   Pass B: Fuzzy string matching   (for new diagnoses not in the synonym list)
# confidence_score = base_confidence (by section) x (fuzzy_score / 100)

import os
import re
import pandas as pd
from rapidfuzz import process, fuzz


# Load ICD-10 WHO CSV once at import 

_CSV_PATH = os.path.join(os.path.dirname(__file__), "icd10_2019.csv")
_icd_df   = pd.read_csv(_CSV_PATH)
_icd_df["sub-code"]   = _icd_df["sub-code"].astype(str).str.strip()
_icd_df["definition"] = _icd_df["definition"].astype(str).str.strip()

_icd_definitions       = _icd_df["definition"].tolist()
_icd_codes             = _icd_df["sub-code"].tolist()
_icd_definitions_lower = [d.lower() for d in _icd_definitions]


#  Build synonym reverse-lookup from _CODE_SYNONYMS 
# _CODE_SYNONYMS maps  code → [synonym, synonym, ...]
# We invert it to synonym_phrase → (code, description)
# Used in Pass A.

def _build_reverse_synonym_map():
    # Inverts _CODE_SYNONYMS so we can look up  synonym_phrase → (code, definition).
    # For ICD-10-CM subcodes not in the WHO CSV (e.g. C64.1, K29.50),
    # tries progressively shorter parent codes until a definition is found.
    from icd_synonyms import _CODE_SYNONYMS

    code_to_def = dict(zip(_icd_codes, _icd_definitions))

    def _resolve_definition(code):
        if code in code_to_def:
            return code_to_def[code]
        parts = code.split(".")
        if len(parts) == 2:
            sub = parts[1]
            while sub:
                candidate = parts[0] + "." + sub
                if candidate in code_to_def:
                    return code_to_def[candidate]
                sub = sub[:-1]
            if parts[0] in code_to_def:
                return code_to_def[parts[0]]
        return code

    reverse = {}
    for code, synonyms in _CODE_SYNONYMS.items():
        definition = _resolve_definition(code)
        for syn in synonyms:
            reverse[syn.lower().strip()] = (code, definition)
    return reverse


_SYNONYM_REVERSE = _build_reverse_synonym_map()


# Base confidence by section 
_BASE_CONFIDENCE = {
    "diagnosis":  1.00,
    "reason":     0.85,
    "background": 0.85,
    "management": 0.75,
    "procedures": 0.70,
    "followup":   0.60,
    "discharge":  0.65,
}

_DEFAULT_BASE_CONFIDENCE = 0.70


# Pass A — synonym reverse-lookup 

def _synonym_lookup(text):
    # Returns (icd_code, definition) if extracted text matches a known synonym, else None.
    # First tries exact match, then checks if any synonym is a substring of the text.
    # Minimum synonym length of 4 chars prevents short noise words from matching.
    text_lower = text.lower().strip()

    # Exact match first
    if text_lower in _SYNONYM_REVERSE:
        return _SYNONYM_REVERSE[text_lower]

    # Substring match — longest matching synonym wins (avoid "uti" hitting "beautiful")
    best_syn   = None
    best_len   = 0
    best_match = None

    for syn, pair in _SYNONYM_REVERSE.items():
        if len(syn) >= 4 and syn in text_lower:   # min 4 chars prevents short word noise
            if len(syn) > best_len:
                best_syn   = syn
                best_len   = len(syn)
                best_match = pair

    return best_match   # None if nothing found


# Pass B — keyword-filtered fuzzy matching 

def find_icd_matches(text, top_n=3, threshold=75):
    # Fuzzy-match a clinical phrase against ICD-10 definitions.
    # Returns up to top_n matches as dicts: {icd_code, definition, fuzzy_score}.
    # Uses keyword pre-filter first to avoid false positives on 11,000+ rows.
    if not text or not text.strip():
        return []

    query = text.lower().strip()

    # Step 1 — keyword pre-filter
    # Only keep ICD definitions that share at least one 4+ char word with query.
    keywords = re.findall(r"[a-z]{4,}", query)

    if keywords:
        filtered_idx  = [
            i for i, defn in enumerate(_icd_definitions_lower)
            if any(kw in defn for kw in keywords)
        ]
        filtered_defs = [_icd_definitions_lower[i] for i in filtered_idx]
    else:
        # Very short query (<4 char words) — search everything
        filtered_idx  = list(range(len(_icd_definitions_lower)))
        filtered_defs = _icd_definitions_lower

    if not filtered_defs:
        return []

    # Step 2 — fuzzy score on filtered subset
    # token_sort_ratio: sorts tokens alphabetically then does ratio.
    # Less aggressive than token_set_ratio; requires mutual word overlap.
    results = process.extract(
        query,
        filtered_defs,
        scorer=fuzz.token_sort_ratio,
        limit=top_n,
        score_cutoff=threshold,
    )

    matches = []
    for _matched_lower, score, local_idx in results:
        global_idx = filtered_idx[local_idx]
        matches.append({
            "icd_code":    _icd_codes[global_idx],
            "definition":  _icd_definitions[global_idx],
            "fuzzy_score": int(score),
        })

    return sorted(matches, key=lambda m: -m["fuzzy_score"])


#  Main pipeline function 

def run_fuzzy_matching(entities, threshold=75):
    # Stage 4: assign ICD codes to all entities that don't have one yet.
    # Per entity: skip if already coded → flag procedures → try Pass A → try Pass B → mark unmatched.
    for ent in entities:

        stype = ent.get("suggestion_type", "")

        # 1. Already coded (Z-code inference etc.) 
        if ent.get("icd_code"):
            ent.setdefault("is_ambiguous",     False)
            ent.setdefault("ambiguity_reason", "")
            ent.setdefault("fuzzy_score",       100)
            ent.setdefault("alternative_codes", [])
            continue

        # 2. Procedure — PCS codes not in WHO CSV 
        if stype.startswith("procedure_"):
            ent.update({
                "icd_code":        None,
                "confidence_score": None,
                "is_ambiguous":     True,
                "ambiguity_reason": "ICD-10-PCS procedure code not in WHO CSV — manual coding required",
                "fuzzy_score":      0,
                "alternative_codes": [],
            })
            continue

        # 3. Raw medication without Z-code         
        if stype == "medication":
            ent.update({
                "icd_code":        None,
                "confidence_score": None,
                "is_ambiguous":     False,
                "ambiguity_reason": "",
                "fuzzy_score":      0,
                "alternative_codes": [],
            })
            continue

        # Determine base confidence from source section
        section_key = (
            ent.get("source_section")
            or ent.get("section_key")
            or ent.get("section", "")
        )
        base_conf = _BASE_CONFIDENCE.get(section_key, _DEFAULT_BASE_CONFIDENCE)

        extracted = ent.get("extracted_text", "")

        # 4. Pass A — synonym reverse-lookup 
        syn_result = _synonym_lookup(extracted)
        if syn_result:
            code, definition = syn_result
            ent["icd_code"]         = code
            ent["icd_description"]  = definition
            ent["fuzzy_score"]      = 92          # deterministic — high confidence proxy
            ent["confidence_score"] = round(base_conf * 0.92, 3)
            ent["is_ambiguous"]     = False
            ent["ambiguity_reason"] = ""
            ent["alternative_codes"] = []
            ent["match_method"]     = "synonym_lookup"
            continue

        #5. Pass B — fuzzy matching
        matches = find_icd_matches(extracted, threshold=threshold)

        if matches:
            best = matches[0]

            ent["icd_code"]        = best["icd_code"]
            ent["icd_description"] = best["definition"]
            ent["fuzzy_score"]     = best["fuzzy_score"]
            ent["confidence_score"] = round(base_conf * (best["fuzzy_score"] / 100), 3)
            ent["alternative_codes"] = matches[1:]
            ent["match_method"]    = "fuzzy"

            # Ambiguity: low score OR very close top-2
            is_ambiguous     = False
            ambiguity_reason = ""

            if best["fuzzy_score"] < 82:
                is_ambiguous     = True
                ambiguity_reason = f"Fuzzy score {best['fuzzy_score']}% — below high-confidence threshold"
            elif len(matches) > 1 and (best["fuzzy_score"] - matches[1]["fuzzy_score"]) < 5:
                is_ambiguous     = True
                ambiguity_reason = (
                    f"Close alternatives: {matches[0]['icd_code']} ({matches[0]['fuzzy_score']}%) "
                    f"vs {matches[1]['icd_code']} ({matches[1]['fuzzy_score']}%)"
                )

            ent["is_ambiguous"]     = is_ambiguous
            ent["ambiguity_reason"] = ambiguity_reason

        else:
            #6. No match            ent.update({
                "icd_code":        None,
                "confidence_score": None,
                "icd_description": None,
                "fuzzy_score":      0,
                "is_ambiguous":     True,
                "ambiguity_reason": f"No ICD match above {threshold}% threshold",
                "alternative_codes": [],
                "match_method":     "none",
            })

    return entities


#Convenience wrapper

def match_all_from_text(raw_text):
    # Run the full 4-stage pipeline on a raw discharge summary string.
    # Returns entities ready for the database (icd_code and confidence_score filled).
    from pipeline      import clean_text, parse_sections, tag_diagnosis_lines
    from abbreviations import expand_sections
    from nlp_extractor import extract_entities, filter_codeable
    from direct_match  import extract_diagnosis_phrases, infer_zcodes_from_meds, merge_all_entities

    cleaned   = clean_text(raw_text)
    sections  = parse_sections(cleaned)
    expanded  = expand_sections(sections)
    diag_tags = tag_diagnosis_lines(sections.get("diagnosis", ""))

    nlp_ents    = filter_codeable(extract_entities(expanded, diag_tags))
    direct_ents = extract_diagnosis_phrases(sections, diag_tags)
    zcode_ents  = infer_zcodes_from_meds(nlp_ents)
    merged      = merge_all_entities(nlp_ents, direct_ents, zcode_ents)

    return run_fuzzy_matching(merged)


# test across samples
if __name__ == "__main__":
    import os
    from pipeline      import load_all_samples, clean_text, parse_sections, tag_diagnosis_lines
    from abbreviations import expand_sections
    from nlp_extractor import extract_entities, filter_codeable
    from direct_match  import extract_diagnosis_phrases, infer_zcodes_from_meds, merge_all_entities

    print("\n" + "=" * 65)
    print("  fuzzy_match_icd.py — Stage 4 self-test")
    print("=" * 65)
    print(f"  ICD CSV  : {_CSV_PATH}")
    print(f"  Rows     : {len(_icd_definitions):,} ICD-10 WHO 2019 definitions")
    print(f"  Synonyms : {len(_SYNONYM_REVERSE)} known clinical phrases loaded")
    print()

    samples = load_all_samples()

    for filename in sorted(samples.keys()):
        raw = samples[filename]

        cleaned   = clean_text(raw)
        sections  = parse_sections(cleaned)
        expanded  = expand_sections(sections)
        diag_tags = tag_diagnosis_lines(sections.get("diagnosis", ""))

        nlp_ents    = filter_codeable(extract_entities(expanded, diag_tags))
        direct_ents = extract_diagnosis_phrases(sections, diag_tags)
        zcode_ents  = infer_zcodes_from_meds(nlp_ents)
        merged      = merge_all_entities(nlp_ents, direct_ents, zcode_ents)
        coded       = run_fuzzy_matching(merged)

        print(f"FILE: {filename}  ({len(coded)} entities after Stage 4)")
        print(f"  {'Type':<22} {'ICD Code':<12} {'Conf':<6} {'Method':<16} Text")
        print(f"  {'-' * 65}")

        for e in coded:
            icd    = e.get("icd_code") or "—"
            conf   = f"{e['confidence_score']:.2f}" if e.get("confidence_score") else "—"
            method = e.get("match_method", "pre-filled")
            text   = e["extracted_text"][:38]
            ambig  = " [?]" if e.get("is_ambiguous") else ""
            print(f"  {e['suggestion_type']:<22} {icd:<12} {conf:<6} {method:<16} {text}{ambig}")

        print()

    print("=" * 65)
    print("  Done. Pass A = synonym_lookup  |  Pass B = fuzzy  |  — = no match")
    print("=" * 65 + "\n")
