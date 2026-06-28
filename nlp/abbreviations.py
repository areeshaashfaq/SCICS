# abbreviations.py — Medical abbreviation expander for SIUT discharge summaries.
# Discharge summaries use shorthand that ICD descriptions never use.
# "IDA" won't fuzzy-match "Iron Deficiency Anemia" — expansion bridges the gap.

import re

# UNIVERSAL MEDICAL ABBREVIATIONS

ABBREV_MAP = {
    # Diseases & Conditions
    "DM":    "diabetes mellitus",
    "HTN":   "hypertension",
    "IDA":   "iron deficiency anemia",
    "IHD":   "ischemic heart disease",
    "CKD":   "chronic kidney disease",
    "ESRD":  "end stage renal disease",
    "AKI":   "acute kidney injury",
    "UTI":   "urinary tract infection",
    "URTI":  "upper respiratory tract infection",
    "LRTI":  "lower respiratory tract infection",
    "CAP":   "community acquired pneumonia",
    "TB":    "tuberculosis",
    "GN":    "glomerulonephritis",
    "FSGS":  "focal segmental glomerulosclerosis",
    "MGN":   "membranous glomerulonephritis",
    "ITP":   "immune thrombocytopenic purpura",
    "SLE":   "systemic lupus erythematosus",
    "RA":    "rheumatoid arthritis",
    "NMO":   "neuromyelitis optica",
    "MS":    "multiple sclerosis",
    "DVT":   "deep vein thrombosis",
    "PE":    "pulmonary embolism",
    "CCF":   "congestive cardiac failure",
    "LVF":   "left ventricular failure",
    "RVF":   "right ventricular failure",
    "MI":    "myocardial infarction",
    "CVA":   "cerebrovascular accident stroke",
    "TIA":   "transient ischemic attack",
    "GERD":  "gastroesophageal reflux disease",
    "PUD":   "peptic ulcer disease",
    "IBD":   "inflammatory bowel disease",
    "SOB":   "shortness of breath dyspnea",
    "DOE":   "dyspnea on exertion",
    "PAH":   "pulmonary arterial hypertension",
    "RCC":   "renal cell carcinoma",
    "HCC":   "hepatocellular carcinoma",
    "CML":   "chronic myeloid leukemia",
    "AML":   "acute myeloid leukemia",

    # Signs, Symptoms & Exam Findings
    "BP":    "blood pressure",
    "PR":    "pulse rate",
    "RR":    "respiratory rate",
    "GCS":   "glasgow coma scale",
    "HMF":   "higher mental functions",
    "DRE":   "digital rectal examination",
    "LV":    "left ventricle left ventricular",
    "RV":    "right ventricle right ventricular",
    "EF":    "ejection fraction",
    "IVC":   "inferior vena cava",
    "B/L":   "bilateral",
    "R/L":   "right left",
    "LL":    "lower limb",
    "UL":    "upper limb",
    "VR":    "vocal resonance",

    # Investigations & Tests
    "CBC":   "complete blood count",
    "LFT":   "liver function test",
    "RFT":   "renal function test",
    "TFT":   "thyroid function test",
    "RBS":   "random blood sugar",
    "HBA1C": "glycated hemoglobin",
    "ECG":   "electrocardiogram",
    "ECHO":  "echocardiography",
    "MRI":   "magnetic resonance imaging",
    "MR":    "magnetic resonance imaging",
    "CT":    "computed tomography scan",
    "HRCT":  "high resolution computed tomography",
    "CXR":   "chest x-ray radiograph",
    "PET":   "positron emission tomography",
    "US":    "ultrasound",
    "CSF":   "cerebrospinal fluid",
    "VEP":   "visual evoked potential",
    "EEG":   "electroencephalogram",
    "EMG":   "electromyogram",
    "NCV":   "nerve conduction velocity",
    "PCR":   "polymerase chain reaction test",
    "GS":    "gram stain",
    "CS":    "culture sensitivity",
    "TLC":   "total leucocyte count",
    "MCV":   "mean corpuscular volume",
    "INR":   "international normalised ratio",
    "PT":    "prothrombin time",
    "APTT":  "activated partial thromboplastin time",
    "ALT":   "alanine aminotransferase",
    "AST":   "aspartate aminotransferase",
    "GGT":   "gamma glutamyl transferase",
    "ANA":   "antinuclear antibodies",
    "ANCA":  "anti neutrophil cytoplasmic antibodies",
    "AFB":   "acid fast bacilli tuberculosis smear",
    "MTB":   "mycobacterium tuberculosis",

    # Procedures
    "EGD":   "esophagogastroduodenoscopy upper gastrointestinal endoscopy",
    "GI":    "gastrointestinal",
    "BAL":   "bronchoalveolar lavage",
    "PCV":   "packed cell volume red blood cell transfusion",
    "FFP":   "fresh frozen plasma transfusion",
    "LP":    "lumbar puncture",
    "OT":    "operation theatre surgical procedure",

    # Drug Dose Timing & Route
    "OD":    "once daily",
    "BD":    "twice daily",
    "TDS":   "three times daily",
    "QID":   "four times daily",
    "SOS":   "as needed when required",
    "STAT":  "immediately single dose",
    "IV":    "intravenous",
    "IM":    "intramuscular",
    "SC":    "subcutaneous",
    "PO":    "oral by mouth",
    "LA":    "local application topical",
    "TSF":   "teaspoon 5ml",

    # Drug Forms
    "INJ":   "injection",
    "SYP":   "syrup",
    "TAB":   "tablet",

    # Administrative / Care
    "DC":    "discharge",
    "OPD":   "outpatient department",
    "ICU":   "intensive care unit",
    "HDU":   "high dependency unit",
    "K/C":   "known case of",
    "KC":    "known case of",
    "H/O":   "history of",
    "C/O":   "complaint of",
    "P/H":   "past history",
    "F/H":   "family history",
    "POD":   "post operative day",
}


# SIUT-SPECIFIC CLINICAL DOCUMENTATION

ABBREV_MAP.update({

    # Test name variants used at SIUT
    "CBT":   "complete blood test",
    "UCE":   "urine culture and electrolytes",
    "LET":   "liver enzymes test",
    "BSR":   "blood sugar random",

    # Neurological shorthand seen in SIUT notes
    "BERL":  "bilateral equal reactive to light pupils normal",
    "TPP":   "oriented to time place person",

    # Antibody / immunology shorthand
    "MOG":        "myelin oligodendrocyte glycoprotein antibody",
    "AQP4":       "aquaporin 4 antibody",
    "PLA2R":      "phospholipase a2 receptor antibody",
    "ANTI MOG":   "anti myelin oligodendrocyte glycoprotein antibody disease",
    "ANTI PLA2R": "anti phospholipase a2 receptor membranous nephropathy",

    # Radiology findings shorthand
    "GGO":     "ground glass opacity",
    "B/L GGO": "bilateral ground glass opacity",

    # Administrative variants
    "IM OPD": "internal medicine outpatient department",
    "IM OPO": "internal medicine outpatient department",
    "OPO":    "outpatient department",
    "OP":     "post operative",

    # Pathology shorthand
    "VE": "negative result",
    "FA": "folic acid",

    # Cardiology
    "LV":  "left ventricular",
    "RV":  "right ventricular",
})


# DRUG BRAND NAMES USED AT SIUT
# Expanded to generic names so NLP can match ICD drug-related codes.

ABBREV_MAP.update({

    # Gastrointestinal
    "RISEK":      "omeprazole proton pump inhibitor",
    "OMEPRAZOLE": "omeprazole proton pump inhibitor",
    "MUCAINE":    "antacid oxethazaine algeldrate magnesium hydroxide",
    "ULSANIC":    "sucralfate gastric mucosal protectant",
    "DUPHALAC":   "lactulose laxative",
    "MOVCAL":     "calcium carbonate vitamin d supplement",

    # Antimicrobials
    "SEPTRAN":    "co-trimoxazole trimethoprim sulfamethoxazole antibiotic",
    "SEPTRAN DS": "co-trimoxazole trimethoprim sulfamethoxazole double strength antibiotic",
    "DIFLUCAN":   "fluconazole antifungal",
    "NILSTAT":    "nystatin antifungal",
    "FASIGYN":    "tinidazole antiprotozoal antibiotic",

    # Corticosteroids
    "DELTA":       "prednisolone corticosteroid",
    "METHYLPRED":  "methylprednisolone corticosteroid intravenous",
    "METHYL PRED": "methylprednisolone corticosteroid intravenous",

    # Anticoagulants
    "CLEXANE": "enoxaparin low molecular weight heparin anticoagulant",
    "CICXANE": "enoxaparin low molecular weight heparin anticoagulant",

    # Vitamins & Supplements
    "NEUROBION": "vitamin b complex thiamine pyridoxine cyanocobalamin",
    "NLUROBION": "vitamin b complex thiamine pyridoxine cyanocobalamin",
    "QALSAN":    "calcium carbonate vitamin d3 supplement",
    "IBRET":     "ferrous sulfate folic acid iron supplement",
    "IBRETFOUC": "ferrous sulfate folic acid iron supplement",

    # Antihypertensives
    "AMLODIPINE": "amlodipine calcium channel blocker antihypertensive",
    "LOSARTAN":   "losartan angiotensin receptor blocker antihypertensive",

    # Antidiabetics
    "GLUCOPHAGE":  "metformin antidiabetic biguanide",
    "METFORMIN":   "metformin antidiabetic biguanide",
    "GLIMIPERIDE": "glimepiride sulfonylurea antidiabetic",

    # Respiratory
    "COMBIVAIR": "salmeterol fluticasone inhaler bronchodilator corticosteroid",

    # Wound care
    "EUSOL":     "edinburgh university solution of lime antiseptic wound dressing",
    "XYLOCAINE": "lidocaine local anaesthetic",
    "GTN":       "glyceryl trinitrate nitroglycerin topical",
})


# CAP is ambiguous: in clinical sections it means Community Acquired Pneumonia,
# in treatment sections it means Capsule (drug form).

_CLINICAL_SECTIONS = {"diagnosis", "reason_for_admission", "procedures", "background"}

_sorted_abbrevs = sorted(ABBREV_MAP.keys(), key=len, reverse=True)
_pattern = r'\b(' + '|'.join(re.escape(a) for a in _sorted_abbrevs) + r')\b'
_ABBREV_RE = re.compile(_pattern, re.IGNORECASE)

_CT_CAP = re.compile(r'\bct\s+cap\b', re.IGNORECASE)


def expand_abbreviations(text, section_key=None):
    # Replace known abbreviations with their full medical terms.
    text = _CT_CAP.sub("ct chest abdomen pelvis scan", text)

    def replace(match):
        token = match.group(0).upper()
        if token == "CAP":
            return ("community acquired pneumonia caused by"
                    if section_key in _CLINICAL_SECTIONS else "capsule")
        return ABBREV_MAP.get(token, match.group(0))

    return _ABBREV_RE.sub(replace, text)


def expand_sections(sections):
    # Run expand_abbreviations on every section in the sections dict.
    return {
        key: expand_abbreviations(text, section_key=key)
        for key, text in sections.items()
    }


# MAIN — show before/after expansions for all sample files

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
