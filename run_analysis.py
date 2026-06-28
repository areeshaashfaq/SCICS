"""
run_analysis.py — Full pipeline accuracy analysis against ground truth Excel.

Runs all three extraction stages for every sample:
  Stage 1 : NLP  (bc5cdr + EntityRuler + medspaCy ConText)
  Stage 2 : Direct line matching on diagnosis / reason / background sections
  Stage 3 : Medication → Z-code inference

Then compares the merged entity pool against every ICD code in the Excel
and reports matched / missed / manual-only counts with accuracy percentages.
"""

import re
from pipeline      import load_all_samples, clean_text, parse_sections, tag_diagnosis_lines
from abbreviations import expand_sections
from nlp_extractor import extract_entities, filter_codeable, GROUND_TRUTH, _CODE_SYNONYMS, _MANUAL_ONLY
from direct_match  import extract_diagnosis_phrases, infer_zcodes_from_meds, merge_all_entities


# ---------------------------------------------------------------------------
# MATCHING HELPER
# ---------------------------------------------------------------------------

def entity_pool_text(merged):
    """Single lowercase string of all extracted entity text for fast searching."""
    return " | ".join(e["extracted_text"].lower() for e in merged)


def zcode_pool(merged):
    """Set of pre-filled ICD codes from medication inference."""
    return {e["icd_code"] for e in merged if e.get("icd_code")}


def code_matched(code, description, pool_text, zcodes):
    """
    Returns True if the code is likely covered by the entity pool.
    Checks:
      1. Pre-filled Z-codes from medication inference (exact match)
      2. Synonym terms from _CODE_SYNONYMS
      3. 4+ char words from the ICD description as fallback
    """
    if code in zcodes:
        return True

    synonyms   = _CODE_SYNONYMS.get(code, [])
    desc_words = re.findall(r"[a-z]{4,}", description.lower())
    terms      = synonyms + desc_words

    return any(term.lower() in pool_text for term in terms)


# ---------------------------------------------------------------------------
# COLOURS FOR TERMINAL OUTPUT
# ---------------------------------------------------------------------------

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ---------------------------------------------------------------------------
# MAIN ANALYSIS
# ---------------------------------------------------------------------------

def run():
    samples = load_all_samples()

    grand_total        = 0
    grand_catchable    = 0
    grand_matched      = 0
    grand_manual       = 0

    # Per-stage contribution tracking
    stage_contributions = {"NLP": 0, "direct_line": 0, "med_inference": 0}

    for filename, raw in sorted(samples.items()):
        stem = filename.replace(".txt", "")
        gt   = GROUND_TRUTH.get(stem, [])
        if not gt:
            continue

        # ── Run all three stages ──────────────────────────────────────────
        cleaned   = clean_text(raw)
        sections  = parse_sections(cleaned)
        expanded  = expand_sections(sections)
        diag_tags = tag_diagnosis_lines(sections.get("diagnosis", ""))

        nlp_ents    = filter_codeable(extract_entities(expanded, diag_tags))
        direct_ents = extract_diagnosis_phrases(sections, diag_tags)
        zcode_ents  = infer_zcodes_from_meds(nlp_ents)
        merged      = merge_all_entities(nlp_ents, direct_ents, zcode_ents)

        pool_text  = entity_pool_text(merged)
        zcodes     = zcode_pool(merged)

        # ── Stage breakdown ───────────────────────────────────────────────
        nlp_pool    = entity_pool_text(nlp_ents)
        nlp_zcodes  = zcode_pool(nlp_ents)

        direct_pool = entity_pool_text(
            [e for e in merged if e.get("source") == "direct_line"]
        )
        zcode_pool_ = zcode_pool(zcode_ents)

        # ── Header ───────────────────────────────────────────────────────
        print()
        print(f"{BOLD}{'=' * 70}{RESET}")
        print(f"{BOLD}  FILE: {filename}{RESET}")
        print(f"  Entities — NLP: {len(nlp_ents)}  "
              f"Direct: {len([e for e in merged if e.get('source')=='direct_line'])}  "
              f"Z-codes: {len(zcode_ents)}  "
              f"Total merged: {len(merged)}")
        print(f"{'=' * 70}")

        file_total     = 0
        file_catchable = 0
        file_matched   = 0
        file_manual    = 0

        rows = []
        for entry in gt:
            code, ctype, desc = entry[0], entry[1], entry[2]
            # 4-tuple with "MANUAL" as 4th element = file-specific manual override
            per_file_manual = len(entry) > 3 and entry[3] == "MANUAL"
            file_total += 1
            grand_total += 1
            is_manual = code in _MANUAL_ONLY or per_file_manual

            if is_manual:
                file_manual  += 1
                grand_manual += 1
                rows.append((code, ctype, desc, "MANUAL", None))
                continue

            file_catchable  += 1
            grand_catchable += 1

            matched = code_matched(code, desc, pool_text, zcodes)

            if matched:
                file_matched  += 1
                grand_matched += 1

                # Track which stage first enabled the match
                if code in nlp_zcodes or code_matched(code, desc, nlp_pool, nlp_zcodes):
                    stage_contributions["NLP"] += 1
                elif code in zcode_pool_:
                    stage_contributions["med_inference"] += 1
                else:
                    stage_contributions["direct_line"] += 1

                rows.append((code, ctype, desc, "MATCH", True))
            else:
                rows.append((code, ctype, desc, "MISS", False))

        # ── Print rows ────────────────────────────────────────────────────
        for code, ctype, desc, status, _ in rows:
            if status == "MATCH":
                icon  = f"{GREEN}✓ MATCHED  {RESET}"
            elif status == "MISS":
                icon  = f"{RED}✗ MISSED   {RESET}"
            else:
                icon  = f"{YELLOW}— MANUAL   {RESET}"

            print(f"  {icon} [{ctype:<9}] {code:<10}  {desc}")

        # ── File summary ──────────────────────────────────────────────────
        catchable_pct = (file_matched / file_catchable * 100) if file_catchable else 0
        total_pct     = (file_matched / (file_total - file_manual) * 100) if (file_total - file_manual) else 0

        print()
        print(f"  {'─'*50}")
        print(f"  Total codes in Excel : {file_total}")
        print(f"  Manual-only          : {file_manual}  "
              f"{YELLOW}(clinical inference / not in text){RESET}")
        print(f"  Pipeline-catchable   : {file_catchable}")
        print(f"  Matched by pipeline  : {GREEN}{file_matched}{RESET} / {file_catchable}  "
              f"({catchable_pct:.0f}%)")

    # ── Grand totals ──────────────────────────────────────────────────────
    catchable_pct  = (grand_matched / grand_catchable * 100) if grand_catchable else 0
    manual_pct     = (grand_manual  / grand_total     * 100) if grand_total     else 0
    overall_pct    = (grand_matched / grand_total      * 100) if grand_total     else 0

    print()
    print(f"{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  OVERALL ACCURACY ACROSS ALL 8 SAMPLES{RESET}")
    print(f"{'=' * 70}")
    print(f"  Total codes in Excel              : {grand_total}")
    print(f"  Manual-only (never catchable)     : {YELLOW}{grand_manual}{RESET}  "
          f"({manual_pct:.0f}%  — coder fills these)")
    print(f"  Pipeline-catchable codes          : {grand_catchable}")
    print(f"  Matched by pipeline               : {GREEN}{grand_matched}{RESET} / {grand_catchable}  "
          f"({BOLD}{catchable_pct:.0f}%{RESET})")
    print(f"  Coverage of ALL codes in Excel    : {grand_matched} / {grand_total}  "
          f"({overall_pct:.0f}%)")
    print()
    print(f"  {'─'*50}")
    print(f"  Stage contribution (of matched codes):")
    print(f"    NLP (bc5cdr + EntityRuler)  : {GREEN}{stage_contributions['NLP']}{RESET}")
    print(f"    Direct line matching        : {CYAN}{stage_contributions['direct_line']}{RESET}")
    print(f"    Medication Z-code inference : {CYAN}{stage_contributions['med_inference']}{RESET}")
    print(f"{'=' * 70}")
    print()
    print(f"  {YELLOW}NOTE: Procedure codes (ICD-10-PCS: 0XXXXX, 30XXXXX) are NOT in the{RESET}")
    print(f"  {YELLOW}ICD-10 WHO CSV. The pipeline flags the procedure was performed;{RESET}")
    print(f"  {YELLOW}the exact PCS code is always assigned manually by the coder.{RESET}")
    print()


if __name__ == "__main__":
    run()
