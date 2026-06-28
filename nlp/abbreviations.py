"""
abbreviations.py — Medical abbreviation expander for SIUT discharge summaries.

Purpose:
    Discharge summaries use shorthand that ICD code descriptions never use.
    "IDA" won't fuzzy-match "Iron Deficiency Anemia" — expansion bridges the gap.

Three tiers:
    TIER 1 — Universal medical abbreviations (standard across all hospitals)
    TIER 2 — SIUT / Pakistan clinical documentation style (local variants)
    TIER 3 — Drug brand names used at SIUT (expand to generic names)

Expansion rules:
    - Whole-word only (\b boundaries) — "DM" won't touch "ADMINISTER"
    - Longest match first — "IM OPD" matches before "IM" alone
    - Case-insensitive matching
    - CAP is ambiguous (capsule vs pneumonia) — resolved by section context
    - Unknown abbreviations pass through unchanged
"""

import re

# ===========================================================================
# TIER 1 — UNIVERSAL MEDICAL ABBREVIATIONS
# Standard shorthand used across all hospitals worldwide.
# ===========================================================================

ABBREV_MAP = {

    # --- Diseases & Conditions ---
    "DM":       "diabetes mellitus",
    "HTN":      "hypertension",
    "IDA":      "iron deficiency anemia",
    "IHD":      "ischemic heart disease",
    "CKD":      "chronic kidney disease",
    "ESRD":     "end stage renal disease",
    "AKI":      "acute kidney injury",
    "UTI":      "urinary tract infection",
    "URTI":     "upper respiratory tract infection",
    "LRTI":     "lower respiratory tract infection",
    "CAP":      "community acquired pneumonia",   # ambiguous — resolved by section below
    "TB":       "tuberculosis",
    "GN":       "glomerulonephritis",
    "FSGS":     "focal segmental glomerulosclerosis",
    "MGN":      "membranous glomerulonephritis",
    "ITP":      "immune thrombocytopenic purpura",
    "SLE":      "systemic lupus erythematosus",
    "RA":       "rheumatoid arthritis",
    "NMO":      "neuromyelitis optica",
    "MS":       "multiple sclerosis",
    "DVT":      "deep vein thrombosis",
    "PE":       "pulmonary embolism",
    "CCF":      "congestive cardiac failure",
    "LVF":      "left ventricular failure",
    "RVF":      "right ventricular failure",
    "MI":       "myocardial infarction",
    "CVA":      "cerebrovascular accident stroke",
    "TIA":      "transient ischemic attack",
    "GERD":     "gastroesophageal reflux disease",
    "PUD":      "peptic ulcer disease",
    "IBD":      "inflammatory bowel disease",
    "SOB":      "shortness of breath dyspnea",
    "DOE":      "dyspnea on exertion",
    "PAH":      "pulmonary arterial hypertension",
    "RCC":      "renal cell carcinoma",
    "HCC":      "hepatocellular carcinoma",
    "CML":      "chronic myeloid leukemia",
    "AML":      "acute myeloid leukemia",
    # ALL omitted — matches the common word "all" too aggressively

    # --- Signs, Symptoms & Exam Findings ---
    "BP":       "blood pressure",
    "PR":       "pulse rate",
    "RR":       "respiratory rate",
    "GCS":      "glasgow coma scale",
    "HMF":      "higher mental functions",
    "DRE":      "digital rectal examination",
    "LV":       "left ventricle left ventricular",
    "RV":       "right ventricle right ventricular",
    "EF":       "ejection fraction",
    "IVC":      "inferior vena cava",
    "B/L":      "bilateral",
    "R/L":      "right left",
    "LL":       "lower limb",
    "UL":       "upper limb",
    "VR":       "vocal resonance",

    # --- Investigations & Tests ---
    "CBC":      "complete blood count",
    "LFT":      "liver function test",
    "RFT":      "renal function test",
    "TFT":      "thyroid function test",
    "RBS":      "random blood sugar",
    "HBA1C":    "glycated hemoglobin",
    "ECG":      "electrocardiogram",
    "ECHO":     "echocardiography",
    "MRI":      "magnetic resonance imaging",
    "MR":       "magnetic resonance imaging",
    "CT":       "computed tomography scan",
    "HRCT":     "high resolution computed tomography",
    "CXR":      "chest x-ray radiograph",
    "PET":      "positron emission tomography",
    "US":       "ultrasound",
    "CSF":      "cerebrospinal fluid",
    "VEP":      "visual evoked potential",
    "EEG":      "electroencephalogram",
    "EMG":      "electromyogram",
    "NCV":      "nerve conduction velocity",
    "PCR":      "polymerase chain reaction test",
    "GS":       "gram stain",
    "CS":       "culture sensitivity",
    "TLC":      "total leucocyte count",
    "MCV":      "mean corpuscular volume",
    "INR":      "international normalised ratio",
    "PT":       "prothrombin time",
    "APTT":     "activated partial thromboplastin time",
    "ALT":      "alanine aminotransferase",
    "AST":      "aspartate aminotransferase",
    "GGT":      "gamma glutamyl transferase",
    "ANA":      "antinuclear antibodies",
    "ANCA":     "anti neutrophil cytoplasmic antibodies",
    "AFB":      "acid fast bacilli tuberculosis smear",
    "MTB":      "mycobacterium tuberculosis",

    # --- Procedures ---
    "EGD":      "esophagogastroduodenoscopy upper gastrointestinal endoscopy",
    "GI":       "gastrointestinal",
    "BAL":      "bronchoalveolar lavage",
    "PCV":      "packed cell volume red blood cell transfusion",
    "FFP":      "fresh frozen plasma transfusion",
    "LP":       "lumbar puncture",
    "OT":       "operation theatre surgical procedure",

    # --- Drug Dose Timing & Route ---
    "OD":       "once daily",
    "BD":       "twice daily",
    "TDS":      "three times daily",
    "QID":      "four times daily",
    "SOS":      "as needed when required",
    "STAT":     "immediately single dose",
    "IV":       "intravenous",
    "IM":       "intramuscular",
    "SC":       "subcutaneous",
    "PO":       "oral by mouth",
    "LA":       "local application topical",
    "TSF":      "teaspoon 5ml",

    # --- Drug Forms ---
    "INJ":      "injection",
    "SYP":      "syrup",
    "TAB":      "tablet",

    # --- Administrative / Care ---
    "DC":       "discharge",
    "OPD":      "outpatient department",
    "ICU":      "intensive care unit",
    "HDU":      "high dependency unit",
    "K/C":      "known case of",
    "KC":       "known case of",
    "H/O":      "history of",
    "C/O":      "complaint of",
    "P/H":      "past history",
    "F/H":      "family history",
    "POD":      "post operative day",
}


# ===========================================================================
# TIER 2 — SIUT / PAKISTAN CLINICAL DOCUMENTATION STYLE
# Local variants and abbreviations specific to how SIUT doctors write.
# Add entries here as new samples introduce new patterns.
# ===========================================================================

ABBREV_MAP.update({

    # --- Test name variants used at SIUT ---
    "CBT":      "complete blood test",             # SIUT writes CBT instead of CBC
    "UCE":      "urine culture and electrolytes",  # SIUT standard — elsewhere written MC&S
    "LET":      "liver enzymes test",              # SIUT variant of LFT
    "BSR":      "blood sugar random",              # SIUT writes BSR not RBS

    # --- Neurological shorthand seen in SIUT notes ---
    "BERL":     "bilateral equal reactive to light pupils normal",
    "TPP":      "oriented to time place person",
    "HMF":      "higher mental functions intact",

    # --- Antibody / immunology shorthand ---
    "MOG":      "myelin oligodendrocyte glycoprotein antibody",
    "AQP4":     "aquaporin 4 antibody",
    "PLA2R":    "phospholipase a2 receptor antibody",
    "ANTI MOG": "anti myelin oligodendrocyte glycoprotein antibody disease",
    "ANTI PLA2R": "anti phospholipase a2 receptor membranous nephropathy",

    # --- Radiology findings shorthand ---
    "GGO":      "ground glass opacity",
    "B/L GGO":  "bilateral ground glass opacity",

    # --- Administrative variants ---
    "IM OPD":   "internal medicine outpatient department",
    "IM OPO":   "internal medicine outpatient department",  # OCR typo: O instead of D
    "OPO":      "outpatient department",                    # OCR typo seen in samples
    "OP":       "post operative",

    # --- Pathology shorthand ---
    # NG omitted globally — matches inside units like "ng/ml". Handled in NLP layer instead.
    "VE":       "negative result",                 # "-VE" = negative
    "FA":       "folic acid",                      # used as drug name in some notes

    # --- Cardiology ---
    "LV":       "left ventricular",
    "RV":       "right ventricular",
    "PAH":      "pulmonary arterial hypertension",
})


# ===========================================================================
# TIER 3 — DRUG BRAND NAMES USED AT SIUT
# Expand to generic drug names so NLP can match to ICD drug-related codes.
# When a brand name maps to multiple drugs, list all — the fuzzy matcher
# will pick the best match from the ICD table.
# ===========================================================================

ABBREV_MAP.update({

    # --- Gastrointestinal ---
    "RISEK":        "omeprazole proton pump inhibitor",
    "OMEPRAZOLE":   "omeprazole proton pump inhibitor",   # already generic, reinforce
    "MUCAINE":      "antacid oxethazaine algeldrate magnesium hydroxide",
    "ULSANIC":      "sucralfate gastric mucosal protectant",
    "DUPHALAC":     "lactulose laxative",
    "MOVCAL":       "calcium carbonate vitamin d supplement",

    # --- Antimicrobials ---
    "SEPTRAN":      "co-trimoxazole trimethoprim sulfamethoxazole antibiotic",
    "SEPTRAN DS":   "co-trimoxazole trimethoprim sulfamethoxazole double strength antibiotic",
    "DIFLUCAN":     "fluconazole antifungal",
    "NILSTAT":      "nystatin antifungal",
    "FASIGYN":      "tinidazole antiprotozoal antibiotic",

    # --- Corticosteroids ---
    "DELTA":        "prednisolone corticosteroid",
    "METHYLPRED":   "methylprednisolone corticosteroid intravenous",
    "METHYL PRED":  "methylprednisolone corticosteroid intravenous",

    # --- Anticoagulants ---
    "CLEXANE":      "enoxaparin low molecular weight heparin anticoagulant",
    "CICXANE":      "enoxaparin low molecular weight heparin anticoagulant",  # OCR typo for CLEXANE

    # --- Vitamins & Supplements ---
    "NEUROBION":    "vitamin b complex thiamine pyridoxine cyanocobalamin",
    "NLUROBION":    "vitamin b complex thiamine pyridoxine cyanocobalamin",   # OCR typo
    "QALSAN":       "calcium carbonate vitamin d3 supplement",
    "IBRET":        "ferrous sulfate folic acid iron supplement",
    "IBRETFOUC":    "ferrous sulfate folic acid iron supplement",             # OCR fusion

    # --- Antihypertensives ---
    "AMLODIPINE":   "amlodipine calcium channel blocker antihypertensive",
    "LOSARTAN":     "losartan angiotensin receptor blocker antihypertensive",

    # --- Antidiabetics ---
    "GLUCOPHAGE":   "metformin antidiabetic biguanide",
    "METFORMIN":    "metformin antidiabetic biguanide",                       # already generic
    "GLIMIPERIDE":  "glimepiride sulfonylurea antidiabetic",                  # misspelling of glimepiride

    # --- Respiratory ---
    "COMBIVAIR":    "salmeterol fluticasone inhaler bronchodilator corticosteroid",

    # --- Wound care ---
    "EUSOL":        "edinburgh university solution of lime antiseptic wound dressing",
    "XYLOCAINE":    "lidocaine local anaesthetic",
    "GTN":          "glyceryl trinitrate nitroglycerin topical",              # used for anal fissure
})


# ===========================================================================
# AMBIGUOUS ABBREVIATIONS — resolved by section context
# ===========================================================================
# CAP in clinical sections (diagnosis / reason / procedures / background)
#   → Community Acquired Pneumonia caused by [organism]
# CAP in treatment sections (management / followup / condition_at_discharge)
#   → Capsule (drug form)

_CLINICAL_SECTIONS = {"diagnosis", "reason_for_admission", "procedures", "background"}


# ===========================================================================
# CORE EXPANSION ENGINE
# ===========================================================================

# Build one compiled regex — sorted longest-first so multi-word entries like
# "SEPTRAN DS" and "IM OPD" match before their shorter substrings do.
_sorted_abbrevs = sorted(ABBREV_MAP.keys(), key=len, reverse=True)
_pattern = r'\b(' + '|'.join(re.escape(a) for a in _sorted_abbrevs) + r')\b'
_ABBREV_RE = re.compile(_pattern, re.IGNORECASE)


# "CT CAP" in radiology = Chest Abdomen Pelvis scan — pre-replace before general CAP logic runs
_CT_CAP = re.compile(r'\bct\s+cap\b', re.IGNORECASE)


def expand_abbreviations(text, section_key=None):
    """
    Replace known abbreviations in text with their full medical terms.

    Args:
        text        : cleaned (lowercased) text from a single section
        section_key : which section this text came from — resolves CAP ambiguity

    Unknown abbreviations are left unchanged.
    """
    # Pre-pass: fix multi-word radiology terms before single-token regex runs
    text = _CT_CAP.sub("ct chest abdomen pelvis scan", text)

    def replace(match):
        token = match.group(0).upper()
        if token == "CAP":
            return ("community acquired pneumonia caused by"
                    if section_key in _CLINICAL_SECTIONS else "capsule")
        return ABBREV_MAP.get(token, match.group(0))

    return _ABBREV_RE.sub(replace, text)


def expand_sections(sections):
    """
    Run expand_abbreviations on every section in the sections dict.
    Returns a new dict — original is not modified.
    """
    return {
        key: expand_abbreviations(text, section_key=key)
        for key, text in sections.items()
    }


# ===========================================================================
# MAIN — show before/after for all sections of every sample
# ===========================================================================

if __name__ == "__main__":
    from pipeline import load_all_samples, clean_text, parse_sections

    samples = load_all_samples()

    for filename, raw in sorted(samples.items()):
        print("=" * 60)
        print(f"FILE: {filename}")
        print("=" * 60)

        cleaned  = clean_text(raw)
        sections = parse_sections(cleaned)
        expanded = expand_sections(sections)

        shown_any = False
        for key in ("diagnosis", "reason_for_admission", "management",
                    "procedures", "physical_findings"):
            original     = sections.get(key, "")
            expanded_txt = expanded.get(key, "")
            if original and original != expanded_txt:
                print(f"\n  [{key}]")
                # Print line-by-line diff so changes are easy to spot
                orig_lines = original.splitlines()
                exp_lines  = expanded_txt.splitlines()
                for o, e in zip(orig_lines, exp_lines):
                    if o != e:
                        print(f"    BEFORE: {o[:110]}")
                        print(f"    AFTER : {e[:110]}")
                shown_any = True

        if not shown_any:
            print("  (no expansions triggered)")
        print()
