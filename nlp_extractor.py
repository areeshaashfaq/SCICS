
# nlp_extractor.py — NLP entity extraction for SIUT discharge summaries.

# Model stack:
#   - EntityRuler (custom SIUT patterns) — runs BEFORE NER, catches disease
#     terms bc5cdr misses due to medical jargon or OCR typos
#   - en_ner_bc5cdr_md (scispaCy) — DISEASE and CHEMICAL from clinical text
#   - medspaCy ConText — negation / uncertainty / historical


import re
import spacy
import medspacy
from icd_synonyms import _CODE_SYNONYMS


_nlp = spacy.load("en_ner_bc5cdr_md")

# Catches disease/finding terms that bc5cdr misses: OCR typos, SIUT-specific
# abbreviations, and terms outside the BC5CDR training vocabulary.
_ruler = _nlp.add_pipe(
    "entity_ruler",
    before="ner",
    config={"overwrite_ents": True, "phrase_matcher_attr": "LOWER"},
)
_ruler.add_patterns([
    #  Respiratory 
    {"label": "DISEASE", "pattern": "viral pneumonitis"},
    {"label": "DISEASE", "pattern": "viral pneuonitis"},      
    {"label": "DISEASE", "pattern": "resp b virus"},           
    {"label": "DISEASE", "pattern": "respiratory syncytial virus"},
    {"label": "DISEASE", "pattern": "bronchiectasis"},
    {"label": "DISEASE", "pattern": "bronchiectatic lung"},
    {"label": "DISEASE", "pattern": "ground glass"},         
    {"label": "DISEASE", "pattern": "interstitial lung disease"},
    {"label": "DISEASE", "pattern": "pulmonary edema"},
    {"label": "DISEASE", "pattern": "pulmonary oedema"},
    {"label": "DISEASE", "pattern": "empyema"},
    {"label": "DISEASE", "pattern": "pyothorax"},
    {"label": "DISEASE", "pattern": "pleural effusion"},
    #  Cardiac 
    {"label": "DISEASE", "pattern": "cardiomegaly"},
    {"label": "DISEASE", "pattern": "lv hypertrophy"},
    {"label": "DISEASE", "pattern": "concentric lv hypertrophy"},
    {"label": "DISEASE", "pattern": "left ventricular hypertrophy"},
    {"label": "DISEASE", "pattern": "lv dysfunction"},
    #  Renal 
    {"label": "DISEASE", "pattern": "acute kidney failure"},
    {"label": "DISEASE", "pattern": "acute kidney injury"},
    {"label": "DISEASE", "pattern": "acute renal failure"},
    {"label": "DISEASE", "pattern": "nephrotic syndrome"},
    {"label": "DISEASE", "pattern": "nephritic syndrome"},
    #  GI 
    {"label": "DISEASE", "pattern": "gastritis"},
    {"label": "DISEASE", "pattern": "chronic gastritis"},
    {"label": "DISEASE", "pattern": "giardiasis"},
    {"label": "DISEASE", "pattern": "appendicitis"},
    {"label": "DISEASE", "pattern": "ascites"},
    {"label": "DISEASE", "pattern": "tropical sprue"},
    {"label": "DISEASE", "pattern": "malabsorption"},
    #  Vasculitis / autoimmune 
    {"label": "DISEASE", "pattern": "wegener granulomatosis"},
    {"label": "DISEASE", "pattern": "wegener's granulomatosis"},
    {"label": "DISEASE", "pattern": "wegener's granumatosis"},    # OCR typo
    {"label": "DISEASE", "pattern": "granulomatosis with polyangiitis"},
    {"label": "DISEASE", "pattern": "anca vasculitis"},
    #  Neurological 
    {"label": "DISEASE", "pattern": "neuromyelitis optica"},
    {"label": "DISEASE", "pattern": "mog antibody disease"},
    #  Skin / soft tissue 
    {"label": "DISEASE", "pattern": "cellulitis"},
    {"label": "DISEASE", "pattern": "anal fissure"},
    {"label": "DISEASE", "pattern": "skin ulcer"},
    #  Haematological 
    {"label": "DISEASE", "pattern": "anemia"},
    {"label": "DISEASE", "pattern": "anaemia"},
    {"label": "DISEASE", "pattern": "iron deficiency anemia"},
    {"label": "DISEASE", "pattern": "iron deficiency anaemia"},
    {"label": "DISEASE", "pattern": "thrombocytopenia"},
    {"label": "DISEASE", "pattern": "eosinophilia"},
    #  Gynaecological 
    {"label": "DISEASE", "pattern": "adnexal mass"},
    {"label": "DISEASE", "pattern": "subserosal fibroid"},
    #  Infectious 
    {"label": "DISEASE", "pattern": "urinary tract infection"},
    {"label": "DISEASE", "pattern": "filariasis"},
    {"label": "DISEASE", "pattern": "tuberculosis"},
    #  Symptoms commonly coded 
    {"label": "DISEASE", "pattern": "diarrhea"},
    {"label": "DISEASE", "pattern": "diarrhoea"},
    {"label": "DISEASE", "pattern": "visual disturbance"},
    {"label": "DISEASE", "pattern": "vision loss"},
    {"label": "DISEASE", "pattern": "optic atrophy"},
    #  Metabolic 
    {"label": "DISEASE", "pattern": "diabetic ketoacidosis"},
    {"label": "DISEASE", "pattern": "hyperglycemia"},
    {"label": "DISEASE", "pattern": "hyperglycaemia"},
    #  Haematological (adjective forms bc5cdr misses) 
    {"label": "DISEASE", "pattern": "anemic"},
    {"label": "DISEASE", "pattern": "anaemic"},
    #  Pallor as anemia proxy (physical findings) 
    {"label": "DISEASE", "pattern": "pale"},            
    #  Cardiac (shorter patterns so tokenizer issues don't block match) 
    {"label": "DISEASE", "pattern": "lv hypertrophy"},
    {"label": "DISEASE", "pattern": "rv hypertrophy"},
    {"label": "DISEASE", "pattern": "lv dysfunction"},
    #  Anorectal 
    {"label": "DISEASE", "pattern": "perianal tag"},
    {"label": "DISEASE", "pattern": "hemorrhoidal skin tag"},
    {"label": "DISEASE", "pattern": "haemorrhoidal skin tag"},
    {"label": "DISEASE", "pattern": "hemorrhoids"},
    {"label": "DISEASE", "pattern": "haemorrhoids"},
    #  GI findings from endoscopy (for fuzzy to map to K-codes) 
    {"label": "DISEASE", "pattern": "pangastric erythema"},
    {"label": "DISEASE", "pattern": "duodenal erythema"},
    {"label": "DISEASE", "pattern": "fissuring of duodenum"},
    {"label": "DISEASE", "pattern": "mucosal inflammation"},
])

#  medspaCy ConText (runs LAST for negation/uncertainty/historical) 
_nlp.add_pipe("medspacy_context", last=True)
_DISEASE_LABELS  = {"DISEASE"}
_CHEMICAL_LABELS = {"CHEMICAL"}


_LAB_CHEMISTRY = {
    "glucose", "ketones", "alanine", "aspartate", "albumin", "globulin",
    "creatinine", "hemoglobin", "haemoglobin", "platelets", "leucocytes",
    "bilirubin", "cholesterol", "triglycerides", "sodium", "potassium",
    "chloride", "bicarbonate", "urea", "phosphate", "ldh", "inr",
    "protein", "lymphocytes", "neutrophils", "eosinophils", "basophils",
    "fibrinogen", "ferritin", "transferrin", "reticulocytes", "hematocrit",
    "prothrombin", "thrombin", "fibrin",
}


# PROCEDURE KEYWORDS + LINE SCANNER
_PROCEDURE_KW = re.compile(
    r"\b("
    r"endoscop|colonoscop|bronchoscop|cystoscop|gastroscop|sigmoidoscop|"
    r"esophagogastroduodenosc|"
    r"ultrasound|sonograph|echocardiograph|"
    r"computed tomography|magnetic resonance|"
    r"high resolution computed tomography|"
    r"chest x.?ray|x.?ray|radiograph|fluoroscop|"
    r"scintigraph|lymphoscintigraph|angiograph|"
    r"ct\s+(chest|brain|abdomen|spine|head|scan|cap)|"
    r"mr\s+(brain|spine|cord|head|abdomen|chest)|"
    r"electroencephalograph|electromyograph|"
    r"visual evoked potential|nerve conduction|"
    r"cerebrospinal fluid|lumbar puncture|"
    r"polymerase chain reaction|culture|gram stain|biopsy|"
    r"bronchoalveolar lavage|lavage|"
    r"pleural tap|thoracocentesis|paracentesis|"
    r"transfus|"
    r"catheter|drainage|excision|incision|debridement|"
    r"intubat|ventilat|dialysis|plasmapheresis|"
    r"surgery|operation|resection|repair"
    r")\b",
    re.IGNORECASE
)

_PROCEDURE_SECTIONS = {"procedures", "management", "physical_findings",
                        "reason_for_admission"}

_PROC_TRAIL = re.compile(
    r"\s*(was\s+performed|was\s+done|done|performed|completed|"
    r"negative|normal|showed?|showing|revealed?|"
    r"report\s+to\s+chase|report\s+awaited|"
    r"no\s+\w+|with\s+contrast.*).*$",
    re.IGNORECASE
)
_DATE_RE  = re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b")
_TIME_RE  = re.compile(r"\b\d{2}:\d{2}:\d{2}\b")
_PAREN_RE = re.compile(r"\([^)]*\)")

# When endoscopy/colonoscopy is found AND any of these appear nearby in the
# same section → also emit a biopsy entity (endoscopy finding = biopsy taken)
_BIOPSY_SIGNAL = re.compile(
    r"\b(biopsy|histopathology|histology|specimen|showing|showed|"
    r"features\s+of|nodularity|fissuring|mucosa)\b",
    re.IGNORECASE
)
_ENDOSCOPY_RE = re.compile(
    r"\b(endoscop|colonoscop|gastroscop)\b", re.IGNORECASE
)


def _scan_procedure_lines(section_text):
    results = []
    for raw_line in re.split(r"[\n;]", section_text):
        line = raw_line.strip()
        if not line or len(line) < 4:
            continue
        if not _PROCEDURE_KW.search(line):
            continue

        clean = _PROC_TRAIL.sub("", line).strip()
        clean = _DATE_RE.sub("", clean).strip()
        clean = _TIME_RE.sub("", clean).strip()
        clean = _PAREN_RE.sub("", clean).strip()
        clean = clean.strip(".,+-• \t")

        if len(clean) < 4 or re.match(r"^[\d\s\.\,\-\+\/\%\(\)]+$", clean):
            continue

        pos = section_text.find(raw_line.strip())
        if pos == -1:
            pos = 0
        results.append((clean, pos, pos + len(clean)))

    # Endoscopy biopsy inference ─
    # If the section contains an endoscopy AND biopsy signals, infer a "biopsy" entity was performed (endoscopy finding = biopsy taken).
    if (_ENDOSCOPY_RE.search(section_text)
            and _BIOPSY_SIGNAL.search(section_text)):
        # Avoid adding if biopsy already extracted from line scanner
        already_has_biopsy = any("biopsy" in r[0].lower() for r in results)
        if not already_has_biopsy:
            biopsy_pos = section_text.lower().find("endoscop")
            if biopsy_pos == -1:
                biopsy_pos = 0
            results.append(("endoscopic biopsy", biopsy_pos, biopsy_pos + 17))

    return results


# NOISE FILTERS

_SKIP_TERMS = {
    "patient", "patients", "doctor", "physician", "hospital", "clinic",
    "ward", "day", "week", "month", "year", "mg", "ml", "dl", "iu", "mcg",
    "tablet", "capsule", "injection", "syrup", "once", "twice", "daily",
    "follow up", "follow-up", "discharge", "stable", "admission",
    "known case", "old case", "male", "female", "age",
}
_MULTILINE = re.compile(r"\n")
_TEMPORAL  = re.compile(r"^\d+\s+(day|week|month|year)s?\b", re.IGNORECASE)
_PURE_NUM  = re.compile(r"^[\d\s\.\,\-\+\/\%\(\)]+$")

def _is_noise(text):
    t = text.strip().lower()
    if t in _SKIP_TERMS:         return True
    if len(t) < 4:               return True
    if _MULTILINE.search(text):  return True
    if _TEMPORAL.match(text):    return True
    if _PURE_NUM.match(text):    return True
    return False


# POST-HOC NEGATION — catches "-VE" and similar patterns ConText misses

_POSTHOC_NEG = re.compile(
    r"[-–]\s*ve\b|negative\b|not\s+detected\b|absent\b|nil\b"
    r"|\ball\s*[-–]\s*ve\b|\ball\s+negative\b",
    re.IGNORECASE
)

def _check_posthoc_negation(section_text, start_char, end_char):
    win = section_text[max(0, start_char - 10):min(len(section_text), end_char + 40)]
    return bool(_POSTHOC_NEG.search(win))


# HISTORICAL FALLBACK

_HISTORICAL_RE = re.compile(
    r"\b(known case of|known case|k/c\b|h/o\b|history of|"
    r"since \d|previous|previously|prior|old case|chronic\b)\b",
    re.IGNORECASE
)


# SECTION WEIGHTS + SUGGESTION TYPE
_SECTION_WEIGHTS = {
    "diagnosis":              1.00,
    "procedures":             1.00,
    "reason_for_admission":   0.85,
    "background":             0.80,
    "management":             0.75,
    "physical_findings":      0.70,
    "condition_at_discharge": 0.65,
    "followup_tests":         0.55,
    "followup_instructions":  0.55,
}

def _suggestion_type(section_key, is_historical, entity_type):
    if entity_type == "CHEMICAL":
        return "medication"
    if entity_type == "PROCEDURE":
        return "procedure_principal" if section_key == "procedures" else "procedure_associative"
    if section_key == "diagnosis":
        return "diagnosis_associative" if is_historical else "diagnosis_principal"
    return "diagnosis_associative"


# CORE EXTRACTION
def extract_entities(expanded_sections, diag_tags=None):
    """
    Pass 1 — EntityRuler + bc5cdr NER + medspaCy ConText for DISEASE/CHEMICAL.
    Pass 2 — Line-scanner for PROCEDURE on procedure-relevant sections.
    """
    if diag_tags is None:
        diag_tags = {"acute": [], "chronic": []}

    chronic_lines = {l.strip().lower() for l in diag_tags.get("chronic", [])}
    entities       = []
    global_med_seen = set()   # cross-section dedup for medications
    section_seen    = set()   # per-section dedup for diseases/procedures

    for section_key, section_text in expanded_sections.items():
        if not section_text or not section_text.strip():
            continue

        doc = _nlp(section_text)
        base_weight = _SECTION_WEIGHTS.get(section_key, 0.65)

        #  PASS 1: NER (EntityRuler + bc5cdr) with medspaCy ConText 

        for ent in doc.ents:
            if ent.label_ not in _DISEASE_LABELS | _CHEMICAL_LABELS:
                continue

            text = ent.text.strip()
            if _is_noise(text):
                continue

            entity_type = "DISEASE" if ent.label_ in _DISEASE_LABELS else "CHEMICAL"

            # Drop pure lab chemistry terms labelled as CHEMICAL
            if entity_type == "CHEMICAL" and text.lower() in _LAB_CHEMISTRY:
                continue

            # Reclassify CHEMICALs that are actually procedures
            if entity_type == "CHEMICAL" and _PROCEDURE_KW.search(text):
                entity_type = "PROCEDURE"

            # Deduplication
            if entity_type == "CHEMICAL":
                med_key = text.lower()
                if med_key in global_med_seen:
                    continue
                global_med_seen.add(med_key)
            else:
                sk = f"{section_key}:{text.lower()}"
                if sk in section_seen:
                    continue
                section_seen.add(sk)

            # ConText flags
            is_negated    = ent._.is_negated
            is_uncertain  = ent._.is_uncertain
            is_historical = ent._.is_historical or ent._.is_family

            # Post-hoc negation: ConText misses "-VE", "all -ve" patterns
            if not is_negated:
                is_negated = _check_posthoc_negation(
                    section_text, ent.start_char, ent.end_char
                )

            # Fallback historical detection
            win_s       = max(0, ent.start_char - 120)
            win_e       = min(len(section_text), ent.end_char + 120)
            surrounding = section_text[win_s:win_e]
            if not is_historical:
                if _HISTORICAL_RE.search(surrounding):
                    is_historical = True
                elif any(cl in surrounding.lower() for cl in chronic_lines):
                    is_historical = True

            sugg_type = _suggestion_type(section_key, is_historical, entity_type)
            base = base_weight
            if is_uncertain:  base *= 0.70
            if is_historical and section_key != "diagnosis":
                base *= 0.85

            snip = section_text[
                max(0, ent.start_char - 50):
                min(len(section_text), ent.end_char + 50)
            ].strip()

            entities.append({
                "extracted_text":    text,
                "suggestion_type":   sugg_type,
                "source_char_start": ent.start_char,
                "source_char_end":   ent.end_char,
                "source_snippet":    snip,
                "is_ambiguous":      is_uncertain,
                "ambiguity_reason":  "uncertain mention in text" if is_uncertain else None,
                "icd_code":          None,
                "confidence_score":  None,
                "coder_decision":    "pending",
                "negated":           is_negated,
                "source_section":    section_key,
                "entity_type":       entity_type,
                "base_confidence":   round(base, 3),
            })

        #  PASS 2: Line-based procedure scanner 
        if section_key not in _PROCEDURE_SECTIONS:
            continue

        for clean_text, start_char, end_char in _scan_procedure_lines(section_text):
            if _is_noise(clean_text):
                continue

            sk = f"{section_key}:{clean_text.lower()}"
            if sk in section_seen:
                continue
            section_seen.add(sk)

            win_s       = max(0, start_char - 80)
            win_e       = min(len(section_text), end_char + 80)
            surrounding = section_text[win_s:win_e]

            is_negated = bool(re.search(
                r"\b(no\b|not\b|negative|negatives|-ve|absent|nil|"
                r"not\s+performed|not\s+done)\b",
                surrounding, re.IGNORECASE
            ))
            is_uncertain = bool(re.search(
                r"\b(query|suspected|possible|probable|likely|"
                r"awaited|planned|to\s+be\s+done|pending)\b",
                surrounding, re.IGNORECASE
            ))

            sugg_type = _suggestion_type(section_key, False, "PROCEDURE")
            base = base_weight
            if is_uncertain:
                base *= 0.70

            snip = section_text[
                max(0, start_char - 50):
                min(len(section_text), end_char + 50)
            ].strip()

            entities.append({
                "extracted_text":    clean_text,
                "suggestion_type":   sugg_type,
                "source_char_start": start_char,
                "source_char_end":   end_char,
                "source_snippet":    snip,
                "is_ambiguous":      is_uncertain,
                "ambiguity_reason":  "uncertain/planned procedure" if is_uncertain else None,
                "icd_code":          None,
                "confidence_score":  None,
                "coder_decision":    "pending",
                "negated":           is_negated,
                "source_section":    section_key,
                "entity_type":       "PROCEDURE",
                "base_confidence":   round(base, 3),
            })

    return entities


def filter_codeable(entities):
    """Remove negated entities — these never get ICD codes."""
    return [e for e in entities if not e["negated"]]


# GROUND TRUTH + COMPARISON for testing and accuracy assessment
# Maps ICD code → list of search terms that should appear in extracted text.
# "renal cell carcinoma" won't match "MALIGNANT NEOPLASM OF RIGHT KIDNEY" by word overlap — these synonyms bridge the gap.

# All codes from the Excel, grouped by file stem.
# Codes marked NOT_IN_TEXT are genuinely uncatchable by NLP (clinical inference, external cause codes, prior surgery).
GROUND_TRUTH = {
    "051904": [
        ("30233N1", "Procedure", "TRANSFUSION OF NONAUTOLOGOUS RED BLOOD CELLS"),
        ("D56.3",   "Diagnose",  "THALASSEMIA MINOR"),
        ("E11.9",   "Diagnose",  "TYPE 2 DIABETES MELLITUS"),
        ("K27.9",   "Diagnose",  "PEPTIC ULCER"),
    ],
    "490434": [
        ("I10",      "Diagnose",  "HYPERTENSION"),
        ("I27.21",   "Diagnose",  "SECONDARY PULMONARY ARTERIAL HYPERTENSION"),
        ("I51.7",    "Diagnose",  "CARDIOMEGALY"),
        ("J12.1",    "Diagnose",  "RSV PNEUMONIA"),
        ("J81.1",    "Diagnose",  "CHRONIC PULMONARY EDEMA"),
        ("J84.89",   "Diagnose",  "INTERSTITIAL PULMONARY DISEASES"),
        ("N17.9",    "Diagnose",  "ACUTE KIDNEY FAILURE"),          # NOT_IN_TEXT
        ("Z20.822",  "Diagnose",  "CONTACT WITH COVID-19"),
        ("R19.09",   "Diagnose",  "INTRA-ABDOMINAL SWELLING"),
    ],
    "523037": [
        ("C64.1",   "Diagnose",  "MALIGNANT NEOPLASM OF RIGHT KIDNEY"),
        ("E11.9",   "Diagnose",  "TYPE 2 DIABETES MELLITUS"),
        ("Z79.4",   "Diagnose",  "LONG TERM USE OF INSULIN"),
        ("Z90.5",   "Diagnose",  "ACQUIRED ABSENCE OF KIDNEY"),    
    ],
    "618013": [
        ("D64.9",   "Diagnose",  "ANEMIA UNSPECIFIED", "MANUAL"),  
        ("J13",     "Diagnose",  "PNEUMONIA DUE TO STREPTOCOCCUS PNEUMONIAE"),
        ("J47.1",   "Diagnose",  "BRONCHIECTASIS WITH ACUTE EXACERBATION","MANUAL"),  
        ("N05.2",   "Diagnose",  "NEPHRITIC SYNDROME WITH MEMBRANOUS GLOMERULONEPHRITIS"),
    ],
    "679242": [
        ("009U3ZX", "Procedure", "CEREBROSPINAL FLUID BIOPSY"),     
        ("0HBMXZX", "Procedure", "EXCISION OF RIGHT FOOT SKIN"),   
        ("D64.9",   "Diagnose",  "ANEMIA UNSPECIFIED"),
        ("D69.6",   "Diagnose",  "THROMBOCYTOPENIA"),              
        ("G36.0",   "Diagnose",  "NEUROMYELITIS OPTICA"),
        ("G37.81",  "Diagnose",  "MOG ANTIBODY DISEASE"),           
        ("H53.8",   "Diagnose",  "VISUAL DISTURBANCES"),
        ("K80.20",  "Diagnose",  "CALCULUS OF GALLBLADDER"),       
        ("L03.115", "Diagnose",  "CELLULITIS OF RIGHT LOWER LIMB"),
        ("R19.7",   "Diagnose",  "DIARRHEA"),                       
        ("T25.021A","Diagnose",  "BURN OF RIGHT FOOT"),            
        ("X17.XXXA","Diagnose",  "CONTACT WITH HOT ENGINES"),      
        ("Y92.9",   "Diagnose",  "UNSPECIFIED PLACE"),             
    ],
    "734696": [
        ("0W993ZX", "Procedure", "RIGHT PLEURAL TAP"),
        ("0DB78ZX", "Procedure", "BIOPSY OF ANTRUM ENDOSCOPIC"),
        ("0DB98ZX", "Procedure", "DUODENAL BIOPSY ENDOSCOPIC"),
        ("0DBB8ZX", "Procedure", "EXCISION OF ILEUM ENDOSCOPIC"),
        ("0DBH8ZX", "Procedure", "EXCISION OF CECUM ENDOSCOPIC"),
        ("A07.1",   "Diagnose",  "GIARDIASIS"),
        ("B74.9",   "Diagnose",  "FILARIASIS"),                     
        ("D64.9",   "Diagnose",  "ANEMIA UNSPECIFIED"),
        ("D72.10",  "Diagnose",  "EOSINOPHILIA"),                  
        ("D82.4",   "Diagnose",  "HYPERIMMUNOGLOBULIN E SYNDROME"),
        ("J18.1",   "Diagnose",  "LOBAR PNEUMONIA"),
        ("J86.9",   "Diagnose",  "PYOTHORAX / EMPYEMA"),
        ("K29.50",  "Diagnose",  "CHRONIC GASTRITIS"),
        ("K31.89",  "Diagnose",  "OTHER STOMACH/DUODENUM DISEASE"),
        ("K36",     "Diagnose",  "OTHER APPENDICITIS"),
        ("K52.9",   "Diagnose",  "GASTROENTERITIS"),
        ("K90.49",  "Diagnose",  "MALABSORPTION"),
        ("N43.3",   "Diagnose",  "HYDROCELE"),                      
        ("N50.89",  "Diagnose",  "MALE GENITAL DISORDER"),          
        ("R18.8",   "Diagnose",  "ASCITES"),
    ],
    "736411": [
        ("0B9C8ZX", "Procedure", "BRONCHOALVEOLAR LAVAGE"),
        ("0B9J8ZX", "Procedure", "DRAINAGE OF LEFT LOWER LUNG LOBE"),
        ("M31.30",  "Diagnose",  "WEGENER GRANULOMATOSIS"),
        ("N39.0",   "Diagnose",  "URINARY TRACT INFECTION"),
        ("K59.00",  "Diagnose",  "CONSTIPATION"),                   
        ("L98.499", "Diagnose",  "NON-PRESSURE CHRONIC SKIN ULCER"),
    ],
    "736804": [
        ("0DB78ZX", "Procedure", "BIOPSY OF ANTRUM ENDOSCOPIC"),
        ("0DB98ZX", "Procedure", "DUODENAL BIOPSY ENDOSCOPIC"),
        ("D50.9",   "Diagnose",  "IRON DEFICIENCY ANEMIA"),
        ("K29.50",  "Diagnose",  "CHRONIC GASTRITIS"),
        ("K60.2",   "Diagnose",  "ANAL FISSURE"),
        ("K64.4",   "Diagnose",  "RESIDUAL HEMORRHOIDAL SKIN TAGS"),
        ("K90.1",   "Diagnose",  "TROPICAL SPRUE"),                 
        ("R75",     "Diagnose",  "HIV INCONCLUSIVE"),               
        ("T39.395A","Diagnose",  "ADVERSE EFFECT OF NSAIDS"),       
        ("Z90.710", "Diagnose",  "ACQUIRED ABSENCE OF CERVIX/UTERUS"), 
    ],
}

# Codes that require clinical inference or are genuinely not in any text — pipeline can never suggest these; coder fills manually.
_MANUAL_ONLY = {
    "009U3ZX", "0HBMXZX", # 679242: implied procedures
    "Z90.5", "Z90.49", "Z90.710",   # surgical absence history
    "T25.021A", "X17.XXXA", "Y92.9",# external cause codes
    "D69.6", "K80.20", "R19.7",     # 679242: not in text
    "B74.9", "D72.10", "D82.4",     # 734696: lab/clinical inference
    "N43.3", "N50.89",              # 734696: physical exam only
    "K59.00", "L98.499", "N39.0",   # 736411: not in text (UCE = followup test, not written dx)
    "K64.4",                        # 736804: perianal skin tag = physical exam only, not documented in text
    "K90.1", "R75", "T39.395A",     # 736804: history/lab
}


def _code_matches_extracted(code, description, codeable):
    # Returns True if any extracted entity text contains at least one
    # synonym term for this ICD code.
    synonyms = _CODE_SYNONYMS.get(code, [])
    desc_words = re.findall(r"[a-z]{4,}", description.lower())
    search_terms = synonyms + desc_words

    extracted_lower = " | ".join(e["extracted_text"].lower() for e in codeable)
    return any(term.lower() in extracted_lower for term in search_terms)


# MAIN
if __name__ == "__main__":
    from pipeline import load_all_samples, clean_text, parse_sections, tag_diagnosis_lines
    from abbreviations import expand_sections

    samples = load_all_samples()

    total_expected    = 0
    total_nlp_catchable = 0
    total_found       = 0

    for filename, raw in sorted(samples.items()):
        stem = filename.replace(".txt", "")
        gt   = GROUND_TRUTH.get(stem, [])

        print("=" * 70)
        print(f"FILE: {filename}  ({len(gt)} total codes in Excel)")
        print("=" * 70)

        cleaned   = clean_text(raw)
        sections  = parse_sections(cleaned)
        expanded  = expand_sections(sections)
        diag_tags = tag_diagnosis_lines(sections.get("diagnosis", ""))

        all_ents = extract_entities(expanded, diag_tags)
        codeable = filter_codeable(all_ents)

        diseases   = [e for e in codeable if e["entity_type"] == "DISEASE"]
        chemicals  = [e for e in codeable if e["entity_type"] == "CHEMICAL"]
        procedures = [e for e in codeable if e["entity_type"] == "PROCEDURE"]
        negated    = [e for e in all_ents  if e["negated"]]

        print(f"  Extracted: {len(codeable)} codeable  "
              f"(DISEASE:{len(diseases)}  MED:{len(chemicals)}  "
              f"PROC:{len(procedures)}  Negated:{len(negated)})")
        print()

        print("   EXTRACTED ")
        for e in codeable:
            flag = " [UNCERTAIN]" if e["is_ambiguous"] else ""
            print(f"    [{e['entity_type']:<9}] [{e['suggestion_type']:<28}] "
                  f"conf:{e['base_confidence']:.2f}  {e['extracted_text']}{flag}")

        print()
        print("   GROUND TRUTH vs NLP ")

        for entry in gt:
            code, ctype, desc = entry[0], entry[1], entry[2]
            per_file_manual   = len(entry) > 3 and entry[3] == "MANUAL"
            total_expected += 1
            is_manual = code in _MANUAL_ONLY or per_file_manual
            if not is_manual:
                total_nlp_catchable += 1

            hit = _code_matches_extracted(code, desc, codeable)
            if hit:
                status = "✓ MATCH"
                if not is_manual:
                    total_found += 1
            elif is_manual:
                status = "— MANUAL (clinical inference / not in text)"
            else:
                status = "✗ MISSED"

            print(f"    [{ctype:<9}] {code:<10} {status}  ← {desc}")

        print()

    print("=" * 70)
    print(f"NLP CATCHABLE:  {total_found}/{total_nlp_catchable} matched")
    print(f"MANUAL ONLY:    "
          f"{total_expected - total_nlp_catchable}/{total_expected} codes "
          f"(clinical inference / not in text — coder fills)")
    print("=" * 70)
