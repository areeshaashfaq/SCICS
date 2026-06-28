import os
import re


# STEP 1 — FILE LOADING
def load_file(filepath):
    with open(filepath, "r") as f:
        return f.read()


def load_all_samples(folder=None):
    if folder is None:
        folder = os.path.join(os.path.dirname(__file__), "..", "Samples")
    all_files = {}
    for filename in os.listdir(folder):
        if filename.endswith(".txt"):
            all_files[filename] = load_file(os.path.join(folder, filename))
    return all_files


# STEP 2 — TEXT CLEANING
def clean_text(raw_text):
    text = raw_text.lower()
    text = re.sub(r'\d{2}-[a-z]{3}-\d{2}\s+\d{2}:\d{2}:\d{2}\s*', '', text)  # strip timestamps
    text = re.sub(r'[ \t]+', ' ', text)  # collapse spaces/tabs
    text = re.sub(r'\n{3,}', '\n\n', text)  # collapse excess blank lines
    text = re.sub(r'\b(hrct|echo|mri|egd|bal|ct|us|cxr)(done|showed|showing|performed|reported)',
                  r'\1 \2', text, flags=re.IGNORECASE)
    return text.strip()


# STEP 3 — SECTION PARSING
SECTION_PATTERNS = [
    ("patient_header",        r"^patient\s+(male|female)"),
    ("diagnosis",             r"diagnosis during this admission"),
    ("background",            r"back[gq]round medical problem"),  # 'q'/'g' OCR typo seen in samples
    ("reason_for_admission",  r"reason for admission"),
    ("physical_findings",     r"(significant\s+)?physical findings on admission"),
    ("management",            r"management during admission"),
    ("procedures",            r"diagnostic\s*[&a-z]*\s*therapeutic procedures"),
    ("condition_at_discharge",r"condition at discharge"),
    ("followup_instructions", r"follow.?up instructions"),
    ("followup_tests",        r"significant tests.{0,10}problems to address"),
]

_COMPILED = [(key, re.compile(pat, re.IGNORECASE)) for key, pat in SECTION_PATTERNS]

def parse_sections(cleaned_text):
    #Split a cleaned discharge summary into its named sections.

    lines = cleaned_text.splitlines()
    current_section = None
    sections = {}
    buffer = []

    def flush():
        if current_section and buffer:
            text = "\n".join(buffer).strip()
            if text:
                sections[current_section] = text

    for line in lines:
        stripped = line.strip()

        # Check if this line is a section header
        matched_key = None
        for key, pattern in _COMPILED:
            if pattern.search(stripped):
                matched_key = key
                break

        if matched_key:
            flush() # save whatever we were collecting
            current_section = matched_key
            buffer = [] # start fresh — the header line itself is not content
        else:
            if stripped:   # skip blank lines inside a section
                buffer.append(stripped)

    flush()  # save the last section
    return sections


# STEP 4 — MEDICATION EXTRACTION
_MED_PREFIX = re.compile(
    r"^[\-\d\.\s]*(dc\s+on\s+)?(tab|cap|inj|syp|syr|drp|drop|gel|oint|crm|cream|sachet|sol|soln|susp)",
    re.IGNORECASE
)


def extract_medications(sections):
    # Pull medication lines from the two sections that contain them.
    def pull_meds(text):
        meds = []
        for line in text.splitlines():
            if _MED_PREFIX.match(line.strip()):
                meds.append(line.strip())
        return meds

    inpatient_src = sections.get("management", "")
    discharge_src = (
        sections.get("followup_instructions", "") + "\n" +
        sections.get("condition_at_discharge", "")   # some files put DC meds here (e.g. 736411)
    )

    return {
        "inpatient": pull_meds(inpatient_src),
        "discharge":  pull_meds(discharge_src),
    }


# STEP 5 — KNOWN-CASE TAGGER  (principal vs associate hint)
_KNOWN_CASE = re.compile(r"\bknown case\b|\bk/c\b|\bkc\b", re.IGNORECASE)
_ACUTE_PIVOT = re.compile(
    r"\b(now with|presenting with|admitted with|presenting as|now presenting)\b",
    re.IGNORECASE
)

def tag_diagnosis_lines(diagnosis_text):
    chronic, acute = [], []
    for line in diagnosis_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if _KNOWN_CASE.search(line):
            pivot = _ACUTE_PIVOT.search(line)
            if pivot:
                # Split: before pivot → chronic background; from pivot onward → new acute complaint
                chronic_part = line[:pivot.start()].strip().rstrip(",. ")
                acute_part   = line[pivot.start():].strip()
                if chronic_part:
                    chronic.append(chronic_part)
                if acute_part:
                    acute.append(acute_part)
            else:
                chronic.append(line)
        else:
            acute.append(line)
    return {"chronic": chronic, "acute": acute}


# STEP 6 — PROCEDURE EXTRACTION
_PROCEDURE_KEYWORDS = re.compile(
    r"\b("
    r"biopsy|endoscopy|egd|colonoscopy|sigmoidoscopy|bronchoscopy|bal|cystoscopy|"
    r"mri|mr\b|ct\b|hrct|cxr|x-ray|xray|pet|"
    r"echo|echocardiography|doppler|ultrasound|u/s|us\b|"
    r"vep|eeg|emg|ncv|"
    r"csf|lumbar puncture|lp\b|tap\b|thoracocentesis|pleural tap|paracentesis|"
    r"transfusion|pcv|ffp|platelet|"
    r"catheter|foley|stent|drain|"
    r"lavage|aspiration|aspirat|"
    r"scintigraphy|lymphoscintigraphy|"
    r"culture|sputum|pcr|biopsy|smear|afb|"
    r"surgery|operation|excision|incision|resection|repair|"
    r"angiography|angiogram|scope"
    r")\b",
    re.IGNORECASE
)

_LAB_RESULT_ONLY = re.compile(
    r"^[\w\s/\.\(\)]+\s+[\d\.\-\+]+\s*(g/dl|mg/dl|iu|u/l|mmhg|%|ng/ml|g/l|meq/l|'?ve)?$",
    re.IGNORECASE
)

def _is_lab_result_only(line):
    """Return True only if the line looks like a pure numeric lab result AND
    contains no procedure keyword — prevents ECHO/MRI lines from being dropped."""
    return bool(_LAB_RESULT_ONLY.match(line)) and not bool(_PROCEDURE_KEYWORDS.search(line))

# Procedure verbs — lines with these verbs and no keyword still warrant review
_PROCEDURE_VERB = re.compile(
    r"\b(done|performed|sent|collected|removed|placed|inserted|instilled|given iv|given im)\b",
    re.IGNORECASE
)


def extract_procedures(sections):
    def pull_procedures(text):
        candidates = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Skip lines that are pure numeric lab values with no procedure keyword
            if _is_lab_result_only(line):
                continue
            # Keep lines that name a procedure keyword OR use a procedure verb
            if _PROCEDURE_KEYWORDS.search(line) or _PROCEDURE_VERB.search(line):
                candidates.append(line)
        return candidates

    return {
        "from_procedures":        pull_procedures(sections.get("procedures", "")),
        "from_management":        pull_procedures(sections.get("management", "")),
        "from_physical_findings": pull_procedures(sections.get("physical_findings", "")),
        "from_reason":            pull_procedures(sections.get("reason_for_admission", "")),
    }


# MAIN — run all steps on every sample and print results

if __name__ == "__main__":
    samples = load_all_samples()
    print(f"Loaded {len(samples)} files\n")

    for filename, raw in sorted(samples.items()):
        print("=" * 60)
        print(f"FILE: {filename}")
        print("=" * 60)

        cleaned  = clean_text(raw)
        sections = parse_sections(cleaned)
        meds     = extract_medications(sections)
        procs    = extract_procedures(sections)
        diag_tag = tag_diagnosis_lines(sections.get("diagnosis", ""))

        print(f"  Sections found           : {list(sections.keys())}")
        print(f"  Acute dx hint            : {diag_tag['acute']}")
        print(f"  Chronic dx hint          : {diag_tag['chronic']}")
        print(f"  Inpatient meds           : {meds['inpatient']}")
        print(f"  Discharge meds           : {meds['discharge']}")
        print(f"  Procedures (procedures)  : {procs['from_procedures']}")
        print(f"  Procedures (management)  : {procs['from_management']}")
        print(f"  Procedures (phys.findings): {procs['from_physical_findings']}")
        print(f"  Procedures (reason)      : {procs['from_reason']}")
        print()