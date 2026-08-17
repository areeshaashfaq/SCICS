# fuzzy_match_icd.py — Stage 4 of the SCICS pipeline.
# Takes the entity pool from stages 1-3 and assigns ICD codes using two passes:
#   Pass A: Synonym reverse-lookup  (fast, for known SIUT phrases)
#   Pass B: Fuzzy string matching   (for new diagnoses not in the synonym list)
# confidence_score = base_confidence (by section) x (fuzzy_score / 100)

import os
import re
import pandas as pd
from rapidfuzz import process, fuzz

# Optional DB imports for the corrections feedback loop.
# If psycopg2/dotenv aren't installed the pipeline still works — just no
# learned synonyms will be loaded.
try:
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv()
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False


# Load SIUT Diagnosis CSV (ICD-10-CM, 92K codes) — replaces WHO 2019 CSV

_DIAG_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "Diagnosis.csv")
_icd_df = pd.read_csv(_DIAG_CSV_PATH, sep='\t', encoding='utf-8', encoding_errors='replace', dtype=str)
_icd_df = _icd_df[_icd_df["Active"].str.strip() == "1"].copy()
_icd_df["sub-code"]   = _icd_df["Diagnosis_ID"].astype(str).str.strip()
_icd_df["definition"] = _icd_df["Diagnosis"].astype(str).str.strip()

_icd_definitions       = _icd_df["definition"].tolist()
_icd_codes             = _icd_df["sub-code"].tolist()
_icd_definitions_lower = [d.lower() for d in _icd_definitions]


# Load SIUT Procedure CSV (ICD-10-PCS, 5992 codes)

_PROC_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "Procedure.csv")
_proc_df = pd.read_csv(_PROC_CSV_PATH, encoding='utf-8-sig', dtype=str)
_proc_df["code"] = _proc_df["ProcedureID"].astype(str).str.strip()
_proc_df["desc"] = _proc_df["Procedures"].astype(str).str.strip()
_proc_codes             = _proc_df["code"].tolist()
_proc_definitions       = _proc_df["desc"].tolist()
_proc_definitions_lower = [d.lower() for d in _proc_definitions]


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


# CORRECTIONS FEEDBACK LOOP
# Loads coder-verified phrase→code mappings from the learned_synonyms table
# (populated by retrain.py from the corrections table). Coder-verified
# mappings override hand-crafted synonyms because they reflect real usage.
def _load_learned_synonyms():
    if not _DB_AVAILABLE:
        return {}
    try:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return {}
        conn = psycopg2.connect(db_url + "?sslmode=require")
        cur  = conn.cursor()
        cur.execute("SELECT phrase, icd_code FROM learned_synonyms")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        code_to_def = dict(zip(_icd_codes, _icd_definitions))
        return {
            phrase.lower().strip(): (code, code_to_def.get(code, code))
            for phrase, code in rows
        }
    except Exception as e:
        print(f"[NLP] Could not load learned synonyms: {e}")
        return {}


_LEARNED_SYNONYMS = _load_learned_synonyms()
_SYNONYM_REVERSE.update(_LEARNED_SYNONYMS)   # coder-verified beats hand-crafted
if _LEARNED_SYNONYMS:
    print(f"[NLP] Loaded {len(_LEARNED_SYNONYMS)} learned synonyms from corrections")


# Procedure synonym reverse-lookup: phrase → (pcs_code, definition)
def _build_reverse_procedure_map():
    from icd_synonyms import _PROC_SYNONYMS
    proc_code_to_def = dict(zip(_proc_codes, _proc_definitions))
    reverse = {}
    for code, synonyms in _PROC_SYNONYMS.items():
        definition = proc_code_to_def.get(code, code)
        for syn in synonyms:
            reverse[syn.lower().strip()] = (code, definition)
    return reverse


_PROC_SYN_REVERSE = _build_reverse_procedure_map()


def _proc_synonym_lookup(text):
    # Deterministic procedure phrase → PCS code lookup.
    # Same substring rules as diagnosis lookup — 6-char minimum for substring match.
    text_lower = text.lower().strip()
    if text_lower in _PROC_SYN_REVERSE:
        return _PROC_SYN_REVERSE[text_lower]
    best_len   = 0
    best_match = None
    for syn, pair in _PROC_SYN_REVERSE.items():
        if len(syn) >= 6 and syn in text_lower:
            if len(syn) > best_len:
                best_len   = len(syn)
                best_match = pair
    return best_match


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

    # 6-char minimum for substring match — 4 was too permissive, caused false
    # positives like "cyst"→a rare synonym or "pain"→noise. Exact matches still
    # work for any length.
    for syn, pair in _SYNONYM_REVERSE.items():
        if len(syn) >= 6 and syn in text_lower:
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


# Procedure fuzzy match — with anatomical-site boosting.
# Naive fuzzy match confuses "BAL" with "Drainage of L lower lobe" because
# both share "bronch/lung/left" words. We rerank candidates by whether they
# also contain the same body-part / procedure-verb keywords as the query.

_PROC_ANATOMY_KEYWORDS = {
    "antrum", "duodenum", "ileum", "cecum", "colon", "jejunum", "stomach",
    "kidney", "renal", "bladder", "ureter", "urethra", "prostate",
    "lung", "bronch", "pleural", "trachea", "pleura",
    "liver", "gallbladder", "pancreas", "bile",
    "spleen", "thyroid", "adrenal",
    "heart", "coronary", "aorta", "vein", "artery",
    "brain", "spinal", "csf", "cerebrospinal",
    "skin", "muscle", "bone", "joint",
    "uterus", "cervix", "ovary", "fallopian",
    "eye", "ear", "nose", "throat",
    "breast", "axilla",
}

_PROC_VERB_KEYWORDS = {
    "biopsy", "excision", "resection", "removal", "extraction",
    "lavage", "aspiration", "drainage", "tap",
    "transfusion", "infusion", "injection",
    "endoscopic", "percutaneous", "open", "laparoscopic",
    "insertion", "placement", "replacement", "repair",
    "diagnostic", "therapeutic",
    "right", "left", "bilateral", "lower", "upper",
}

def _keyword_overlap_bonus(query_words, candidate_words):
    q_anat = query_words & _PROC_ANATOMY_KEYWORDS
    c_anat = candidate_words & _PROC_ANATOMY_KEYWORDS
    q_verb = query_words & _PROC_VERB_KEYWORDS
    c_verb = candidate_words & _PROC_VERB_KEYWORDS
    # Anatomy match is critical (worth up to +15 score)
    anat_score = len(q_anat & c_anat) * 8 - len(q_anat ^ c_anat) * 3
    # Verb match is helpful (worth up to +8)
    verb_score = len(q_verb & c_verb) * 4 - len(q_verb ^ c_verb) * 1
    return max(-10, min(15, anat_score)) + max(-5, min(8, verb_score))


def _fuzzy_match_procedures(text, top_n=3, threshold=75):
    if not text or not text.strip():
        return []
    query    = text.lower().strip()
    keywords = re.findall(r"[a-z]{4,}", query)
    if keywords:
        filtered_idx = [i for i, d in enumerate(_proc_definitions_lower)
                        if any(kw in d for kw in keywords)]
        filtered_defs = [_proc_definitions_lower[i] for i in filtered_idx]
    else:
        filtered_idx  = list(range(len(_proc_definitions_lower)))
        filtered_defs = _proc_definitions_lower
    if not filtered_defs:
        return []

    # First get a larger pool (top 10) from raw fuzzy, then rerank with anatomy
    raw_results = process.extract(query, filtered_defs,
                                  scorer=fuzz.token_sort_ratio,
                                  limit=10, score_cutoff=threshold)

    query_words = set(re.findall(r"[a-z]+", query))

    reranked = []
    for _matched_lower, score, local_idx in raw_results:
        global_idx = filtered_idx[local_idx]
        cand_text  = _proc_definitions_lower[global_idx]
        cand_words = set(re.findall(r"[a-z]+", cand_text))
        bonus      = _keyword_overlap_bonus(query_words, cand_words)
        final_score = int(score) + bonus
        reranked.append({
            "icd_code":    _proc_codes[global_idx],
            "definition":  _proc_definitions[global_idx],
            "fuzzy_score": final_score,
            "raw_score":   int(score),
        })

    reranked.sort(key=lambda m: -m["fuzzy_score"])
    return reranked[:top_n]


# POST-PROCESSORS (workbook-driven refinements)
# Applied after Pass A/B match to correct laterality, 7th char, combinations,
# principal-diagnosis uniqueness, and symptom-code suppression.

# 1. LATERALITY REFINEMENT — swap unspecified digit for right/left/bilateral

_LAT_KEYWORDS = [
    (["bilateral", "b/l", "both"], "3"),
    (["right", "rt", "r/", "rt.", "right-sided"], "1"),
    (["left", "lt", "l/", "lt.", "left-sided"], "2"),
]

# Set of all known codes for fast membership tests
_CODE_SET = set(_icd_codes)

def _refine_laterality(code, phrase):
    # If phrase mentions a side and a sibling code with that side digit exists, swap.
    if not code or not phrase:
        return code
    phrase_lower = " " + phrase.lower() + " "
    detected_digit = None
    for kws, digit in _LAT_KEYWORDS:
        if any(f" {k} " in phrase_lower for k in kws):
            detected_digit = digit
            break
    if not detected_digit:
        return code
    # Try swapping the LAST digit
    if code and code[-1].isdigit():
        candidate = code[:-1] + detected_digit
        if candidate in _CODE_SET and candidate != code:
            return candidate
    return code


# 2. SEVENTH-CHARACTER AUTO-APPEND — SIUT discharge = initial encounter

_SEVENTH_CHAR_PREFIXES = ("S", "T", "V", "W", "X", "Y", "M8")   # ICD-10-CM chapters needing 7th char

def _ensure_seventh_character(code):
    # If a stem code lacks its required 7th character but the "A" variant exists, use it.
    if not code:
        return code
    if not code.startswith(_SEVENTH_CHAR_PREFIXES):
        return code
    # Already has a letter suffix
    if code[-1].isalpha():
        return code
    # Try appending A (initial encounter) — safest default for discharge summaries
    for suffix in ("A", "XXXA"):
        candidate = code + suffix
        if candidate in _CODE_SET:
            return candidate
    return code


# 3. DM COMBINATION CODES — collapse DM + manifestation into single combination

# Trigger: E11.9 present AND a manifestation term appears anywhere in doc text
_DM_COMBINATIONS = [
    (["polyneuropathy", "neuropathy"],          "E11.42",  "Type 2 diabetes mellitus with diabetic polyneuropathy"),
    (["nephropathy", "diabetic kidney"],         "E11.21",  "Type 2 diabetes mellitus with diabetic nephropathy"),
    (["foot ulcer", "diabetic foot"],            "E11.621", "Type 2 diabetes mellitus with foot ulcer"),
    (["retinopathy", "diabetic retinopathy"],    "E11.319", "Type 2 diabetes mellitus with retinopathy"),
    (["gastroparesis"],                          "E11.43",  "Type 2 diabetes mellitus with gastroparesis"),
    (["ckd", "chronic kidney disease"],          "E11.22",  "Type 2 diabetes mellitus with diabetic chronic kidney disease"),
]

def _apply_dm_combinations(entities):
    # If E11.9 was suggested AND a manifestation term shows up in ANY entity text,
    # upgrade E11.9 to the specific combination code (workbook chapter 6 rule).
    dm_entities = [e for e in entities if e.get("icd_code") == "E11.9"]
    if not dm_entities:
        return entities
    all_text = " ".join(e.get("extracted_text", "").lower() for e in entities)
    for kws, combo_code, combo_desc in _DM_COMBINATIONS:
        if any(kw in all_text for kw in kws):
            for dm in dm_entities:
                dm["icd_code"]        = combo_code
                dm["icd_description"] = combo_desc
                dm["match_method"]    = "dm_combination_rule"
                dm["ambiguity_reason"] = f"Upgraded from E11.9 — manifestation found in document"
            break
    return entities


# 4. ENFORCE SINGLE PRINCIPAL DIAGNOSIS (UHDDS rule)

def _enforce_single_principal(entities):
    # Only the highest-confidence diagnosis_principal stays principal.
    # The rest get downgraded to diagnosis_associative.
    principals = [e for e in entities if e.get("suggestion_type") == "diagnosis_principal"]
    if len(principals) <= 1:
        return entities
    principals.sort(key=lambda e: e.get("confidence_score") or 0, reverse=True)
    for e in principals[1:]:
        e["suggestion_type"] = "diagnosis_associative"
    return entities


# 5. SYMPTOM (R-CODE) SUPPRESSION — global rule
# Coder rule: symptoms (R00-R99) are NOT coded when a definitive diagnosis
# (any code from chapters A-Q) is documented for the same patient. This is
# a UHDDS-derived guideline and applies to every discharge summary — not
# just the samples. Only exception: if the whole document has no definitive
# dx, keep R-codes (pure symptom admission).

_DEFINITIVE_CHAPTERS = tuple("ABCDEFGHIJKLMNOPQ")   # ICD-10 chapters with real diseases

def _is_r_code(code):
    return bool(code) and code.startswith("R") and len(code) > 1 and code[1].isdigit()

def _suppress_symptoms_globally(entities):
    all_codes = [e.get("icd_code") or "" for e in entities]
    has_definitive_dx = any(c and c.startswith(_DEFINITIVE_CHAPTERS) for c in all_codes)
    if not has_definitive_dx:
        return entities  # keep symptoms — no definitive dx to absorb them
    return [e for e in entities if not _is_r_code(e.get("icd_code"))]


# 6. SECTION-BASED CONFIDENCE DOWNGRADE (SOFT rule — do NOT drop)
# Reverted from the previous hard-drop rule. Coders regularly find real codes
# in followup / physical-findings / discharge sections (e.g. Z20.822 COVID
# contact, Z79.4 insulin, physical exam findings). Instead of dropping, we
# just downgrade the confidence when a code originates ONLY in a weak section
# and mark it ambiguous so the coder pays extra attention.

_STRONG_SECTIONS = {"diagnosis", "reason_for_admission", "background",
                    "procedures", "management", "inferred"}
_WEAK_SECTIONS   = {"followup_instructions", "followup_tests",
                    "physical_findings", "condition_at_discharge"}

def _soft_downgrade_weak_sections(entities):
    strong_codes = {
        e.get("icd_code")
        for e in entities
        if e.get("source_section") in _STRONG_SECTIONS and e.get("icd_code")
    }
    for e in entities:
        section = e.get("source_section", "")
        code    = e.get("icd_code")
        if section in _WEAK_SECTIONS and code and code not in strong_codes:
            # Weak-section novel code: keep but downgrade
            conf = e.get("confidence_score") or 0
            e["confidence_score"] = round(conf * 0.75, 3)
            if not e.get("is_ambiguous"):
                e["is_ambiguous"]     = True
                e["ambiguity_reason"] = f"Only found in weak section ({section}) — verify with coder"
    return entities


# 7. VALIDATE EMITTED CODES EXIST IN THE CSV
# Prevents junk codes like "J13" (no dot), "M1A." (partial), "I10 I10"
# from ever reaching the coder.

_ALL_VALID_CODES = _CODE_SET | set(_proc_codes)

def _drop_invalid_codes(entities):
    keep = []
    for e in entities:
        code = e.get("icd_code")
        if code and code not in _ALL_VALID_CODES:
            continue
        keep.append(e)
    return keep


# 8. DEDUPLICATE BY ICD CODE
# Collapse duplicate codes, keep the entity with highest confidence, and
# append extra source snippets so the coder still sees all evidence.

def _dedupe_by_code(entities):
    grouped = {}
    order   = []
    for e in entities:
        code = e.get("icd_code")
        if not code:
            order.append(("__nocode__", e))   # keep no-code entities as-is
            continue
        if code not in grouped:
            grouped[code] = e
            order.append((code, None))
        else:
            existing = grouped[code]
            new_conf = e.get("confidence_score") or 0
            old_conf = existing.get("confidence_score") or 0
            # keep higher confidence entity, merge snippets
            merged_snippet = " | ".join(filter(None, [
                existing.get("source_snippet") or "",
                e.get("source_snippet") or ""
            ]))
            if new_conf > old_conf:
                e["source_snippet"] = merged_snippet
                grouped[code] = e
            else:
                existing["source_snippet"] = merged_snippet
    result = []
    for code, ent in order:
        if code == "__nocode__":
            result.append(ent)
        elif code in grouped:
            result.append(grouped[code])
            del grouped[code]
    return result


#  Main pipeline function

def run_fuzzy_matching(entities, threshold=78):
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
            # Fill icd_description from CSV if missing
            if not ent.get("icd_description"):
                _cd = dict(zip(_icd_codes, _icd_definitions))
                ent["icd_description"] = _cd.get(ent["icd_code"], ent["icd_code"])
            continue

        # Resolve section and text before any match block
        section_key = (
            ent.get("source_section")
            or ent.get("section_key")
            or ent.get("section", "")
        )
        base_conf = _BASE_CONFIDENCE.get(section_key, _DEFAULT_BASE_CONFIDENCE)
        extracted = ent.get("extracted_text", "")

        # 2. Procedure — try synonym lookup first, then fuzzy match
        if stype.startswith("procedure_"):
            # Pass A for procedures — deterministic phrase lookup
            proc_syn = _proc_synonym_lookup(extracted)
            if proc_syn:
                code, definition = proc_syn
                ent["icd_code"]         = code
                ent["icd_description"]  = definition
                ent["fuzzy_score"]      = 92
                ent["confidence_score"] = round(base_conf * 0.92, 3)
                ent["is_ambiguous"]     = False
                ent["ambiguity_reason"] = ""
                ent["alternative_codes"] = []
                ent["match_method"]     = "proc_synonym_lookup"
                continue

            proc_matches = _fuzzy_match_procedures(extracted, threshold=threshold)
            if proc_matches:
                best = proc_matches[0]
                ent["icd_code"]         = best["icd_code"]
                ent["icd_description"]  = best["definition"]
                ent["fuzzy_score"]      = best["fuzzy_score"]
                ent["confidence_score"] = round(base_conf * (best["fuzzy_score"] / 100), 3)
                ent["alternative_codes"] = proc_matches[1:]
                ent["match_method"]     = "fuzzy_procedure"
                is_ambiguous     = best["fuzzy_score"] < 82
                ambiguity_reason = f"Procedure fuzzy score {best['fuzzy_score']}% — verify with coder" if is_ambiguous else ""
                ent["is_ambiguous"]     = is_ambiguous
                ent["ambiguity_reason"] = ambiguity_reason
            else:
                ent.update({
                    "icd_code":         None,
                    "confidence_score":  None,
                    "is_ambiguous":      True,
                    "ambiguity_reason":  "No procedure match found — manual coding required",
                    "fuzzy_score":       0,
                    "alternative_codes": [],
                    "match_method":      "none",
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

        # 4. Pass A — synonym reverse-lookup
        syn_result = _synonym_lookup(extracted)
        if syn_result:
            code, definition = syn_result
            # Distinguish coder-learned from hand-crafted for feedback-loop analytics
            is_learned = extracted.lower().strip() in _LEARNED_SYNONYMS
            ent["icd_code"]         = code
            ent["icd_description"]  = definition
            ent["fuzzy_score"]      = 95 if is_learned else 92    # coder-verified = higher
            ent["confidence_score"] = round(base_conf * (0.95 if is_learned else 0.92), 3)
            ent["is_ambiguous"]     = False
            ent["ambiguity_reason"] = ""
            ent["alternative_codes"] = []
            ent["match_method"]     = "learned_synonym" if is_learned else "synonym_lookup"
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
            # 6. No match
            ent.update({
                "icd_code":        None,
                "confidence_score": None,
                "icd_description": None,
                "fuzzy_score":      0,
                "is_ambiguous":     True,
                "ambiguity_reason": f"No ICD match above {threshold}% threshold",
                "alternative_codes": [],
                "match_method":     "none",
            })

    # Per-entity refinements (laterality + 7th-char) before doc-level rules
    for ent in entities:
        code = ent.get("icd_code")
        if not code:
            continue
        refined = _refine_laterality(code, ent.get("extracted_text", ""))
        refined = _ensure_seventh_character(refined)
        if refined != code:
            ent["icd_code"] = refined
            _cd = dict(zip(_icd_codes, _icd_definitions))
            if refined in _cd:
                ent["icd_description"] = _cd[refined]

    # Doc-level rules — ORDER MATTERS
    entities = _apply_dm_combinations(entities)          # upgrade E11.9 → E11.42 etc
    entities = _drop_invalid_codes(entities)             # sanity: only valid CSV codes survive
    entities = _soft_downgrade_weak_sections(entities)   # weak-section codes kept, but flagged
    entities = _suppress_symptoms_globally(entities)     # drop R-codes if definitive dx exists
    entities = _dedupe_by_code(entities)                 # collapse duplicates
    entities = _enforce_single_principal(entities)       # only one principal survives

    return entities


#Convenience wrapper

def match_all_from_text(raw_text):
    # Run the full 4-stage pipeline on a raw discharge summary string.
    # Returns entities ready for the database (icd_code and confidence_score filled).
    from pipeline      import clean_text, parse_sections, tag_diagnosis_lines
    from abbreviations import expand_sections
    from nlp_extractor import extract_entities, filter_codeable
    from direct_match  import extract_diagnosis_phrases, extract_procedure_entities, infer_zcodes_from_meds, infer_adverse_and_status_codes, merge_all_entities

    cleaned   = clean_text(raw_text)
    sections  = parse_sections(cleaned)
    expanded  = expand_sections(sections)
    diag_tags = tag_diagnosis_lines(sections.get("diagnosis", ""))

    nlp_ents    = filter_codeable(extract_entities(expanded, diag_tags))
    direct_ents = extract_diagnosis_phrases(sections, diag_tags)
    zcode_ents  = infer_zcodes_from_meds(nlp_ents, sections)
    status_ents = infer_adverse_and_status_codes(sections)
    proc_ents   = extract_procedure_entities(sections)
    merged      = merge_all_entities(nlp_ents, direct_ents, zcode_ents, status_ents, proc_ents)

    return run_fuzzy_matching(merged)


# test across samples
if __name__ == "__main__":
    import os
    from pipeline      import load_all_samples, clean_text, parse_sections, tag_diagnosis_lines
    from abbreviations import expand_sections
    from nlp_extractor import extract_entities, filter_codeable
    from direct_match  import extract_diagnosis_phrases, extract_procedure_entities, infer_zcodes_from_meds, infer_adverse_and_status_codes, merge_all_entities

    print("\n" + "=" * 65)
    print("  fuzzy_match_icd.py — Stage 4 self-test")
    print("=" * 65)
    print(f"  Diag CSV : {_DIAG_CSV_PATH}")
    print(f"  Proc CSV : {_PROC_CSV_PATH}")
    print(f"  Rows     : {len(_icd_definitions):,} diagnosis definitions  +  {len(_proc_definitions):,} procedure definitions")
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
        zcode_ents  = infer_zcodes_from_meds(nlp_ents, sections)
        status_ents = infer_adverse_and_status_codes(sections)
        proc_ents   = extract_procedure_entities(sections)
        merged      = merge_all_entities(nlp_ents, direct_ents, zcode_ents, status_ents, proc_ents)
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
