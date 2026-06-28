"""
test_fuzzy.py — Live end-to-end demonstration of the full pipeline.

Shows exactly how each stage connects for every sample file:
  Stage 1: NLP  (bc5cdr + EntityRuler + medspaCy ConText)
  Stage 2: Direct line matching on diagnosis / reason / background
  Stage 3: Medication → Z-code inference
  Stage 4: Fuzzy matching + synonym lookup → ICD code assignment

ICD codes are looked up from: icd10_2019.csv (same folder as this script)
The CSV has 11,243 rows of ICD-10 WHO 2019 definitions.

Run from WSL:
    python3 test_fuzzy.py
"""

import os
from pipeline      import load_all_samples, clean_text, parse_sections, tag_diagnosis_lines
from abbreviations import expand_sections
from nlp_extractor import extract_entities, filter_codeable, GROUND_TRUTH, _MANUAL_ONLY
from direct_match  import extract_diagnosis_phrases, infer_zcodes_from_meds, merge_all_entities
from fuzzy_match_icd import run_fuzzy_matching, _CSV_PATH

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ── Confirm where ICD codes come from ────────────────────────────────────────

print(f"\n{BOLD}ICD CODE SOURCE{RESET}")
print(f"  File : {_CSV_PATH}")
print(f"  Exists: {os.path.exists(_CSV_PATH)}")

import pandas as pd
_df = pd.read_csv(_CSV_PATH)
print(f"  Rows  : {len(_df):,}  (ICD-10 WHO 2019 definitions)")
print(f"  Cols  : {list(_df.columns)}")
print(f"  Sample rows:")
for _, row in _df.sample(3, random_state=42).iterrows():
    print(f"    {row['sub-code']:<12} {row['definition']}")


# ── Run full pipeline on every sample ────────────────────────────────────────

samples = load_all_samples()

for filename in sorted(samples.keys()):
    stem = filename.replace(".txt", "")
    raw  = samples[filename]
    gt   = GROUND_TRUTH.get(stem, [])
    if not gt:
        continue

    # ── Stage 1-3: extract entities ──────────────────────────────────────────
    cleaned   = clean_text(raw)
    sections  = parse_sections(cleaned)
    expanded  = expand_sections(sections)
    diag_tags = tag_diagnosis_lines(sections.get("diagnosis", ""))

    nlp_ents    = filter_codeable(extract_entities(expanded, diag_tags))
    direct_ents = extract_diagnosis_phrases(sections, diag_tags)
    zcode_ents  = infer_zcodes_from_meds(nlp_ents)
    merged      = merge_all_entities(nlp_ents, direct_ents, zcode_ents)

    # ── Stage 4: fuzzy matching ───────────────────────────────────────────────
    coded = run_fuzzy_matching(merged)

    # ── Print header ─────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"{BOLD}  FILE: {filename}{RESET}")
    print(f"  Entities — NLP:{len(nlp_ents)}  Direct:{len(direct_ents)}  "
          f"Z-codes:{len(zcode_ents)}  Total:{len(merged)}")
    print(f"{'='*72}")

    # ── Show every entity with what Stage 4 assigned ─────────────────────────
    print(f"\n  {BOLD}STAGE 4 OUTPUT — what each entity got coded as:{RESET}")
    print(f"  {'Type':<22} {'ICD Code':<12} {'Conf':<6} {'Method':<14} {'Source text'}")
    print(f"  {'-'*70}")

    for e in coded:
        icd    = e.get("icd_code") or "—"
        conf   = f"{e['confidence_score']:.2f}" if e.get("confidence_score") else "—"
        method = e.get("match_method", "pre-filled")
        text   = e["extracted_text"][:40]
        sect   = e.get("source_section", "?")
        ambig  = f" {YELLOW}⚠{RESET}" if e.get("is_ambiguous") else ""

        # Colour by method
        if method == "synonym_lookup":
            colour = GREEN
        elif method == "fuzzy":
            colour = CYAN
        elif method == "none":
            colour = RED
        else:
            colour = RESET

        print(f"  {colour}{e['suggestion_type']:<22}{RESET} "
              f"{colour}{icd:<12}{RESET} "
              f"{conf:<6} {method:<14} [{sect}] '{text}'{ambig}")

    # ── Ground truth comparison ───────────────────────────────────────────────
    print(f"\n  {BOLD}GROUND TRUTH COMPARISON:{RESET}")
    print(f"  {'Status':<12} {'Code':<10} {'Type':<10} Description")
    print(f"  {'-'*60}")

    # Build a lookup from icd_code → list of entities (for matching)
    code_pool = set(e["icd_code"] for e in coded if e.get("icd_code"))

    for entry in gt:
        code, ctype, desc = entry[0], entry[1], entry[2]
        per_file_manual   = len(entry) > 3 and entry[3] == "MANUAL"
        is_manual         = code in _MANUAL_ONLY or per_file_manual

        if is_manual:
            status = f"{YELLOW}— MANUAL  {RESET}"
        elif code in code_pool:
            status = f"{GREEN}✓ MATCHED {RESET}"
        else:
            # Check if any entity text matches a synonym (same logic as run_analysis)
            from icd_synonyms import _CODE_SYNONYMS
            import re
            synonyms   = _CODE_SYNONYMS.get(code, [])
            desc_words = re.findall(r"[a-z]{4,}", desc.lower())
            pool_text  = " | ".join(e["extracted_text"].lower() for e in coded)
            terms      = synonyms + desc_words
            if any(t in pool_text for t in terms):
                status = f"{GREEN}✓ MATCHED {RESET}"
                code_pool.add(code)
            else:
                status = f"{RED}✗ MISSED  {RESET}"

        print(f"  {status} {code:<10} {ctype:<10} {desc}")

    # ── Section breakdown ─────────────────────────────────────────────────────
    print(f"\n  {BOLD}WHERE entities came from:{RESET}")
    by_section = {}
    for e in coded:
        s = e.get("source_section", "unknown")
        by_section.setdefault(s, []).append(e["extracted_text"])
    for sec, texts in sorted(by_section.items()):
        print(f"    [{sec}]  {', '.join(repr(t) for t in texts[:4])}"
              + (" ..." if len(texts) > 4 else ""))

print(f"\n{'='*72}")
print(f"{BOLD}  DONE — all samples processed{RESET}")
print(f"{'='*72}\n")
