
# icd_synonyms.py — Clinical synonym → ICD-10 code mapping for SIUT.

# Structure:  icd_code → [synonym, synonym, ...]
# The synonyms are clinical phrases SIUT coders and clinicians actually write.
# They cover abbreviations, OCR typos, US/UK spelling, brand names, and
# phrases that map to ICD descriptions via medical knowledge (not text similarity).


# ICD-10-PCS PROCEDURE SYNONYMS
# Used by fuzzy_match_icd._proc_synonym_lookup so common procedure phrases
# map to the correct PCS code deterministically instead of losing to a close
# but wrong fuzzy neighbour (e.g. "bal done" → 0B9C8ZX not 0B9L8ZX).
_PROC_SYNONYMS = {
    "0B9C8ZX":  ["bal done", "bal performed", "bronchoalveolar lavage",
                 "bronchoalveoler lavage", "bal diagnostic"],
    "30233N1":  ["pcv transfused", "packed cell transfused", "packed cells transfused",
                 "blood transfusion", "prbc transfused", "1 point pcv",
                 "transfusion of packed cells", "red blood cell transfusion"],
    "0W993ZX":  ["pleural tap", "pleural aspiration", "thoracocentesis",
                 "thoracentesis", "pleural fluid aspiration"],
    "0DB78ZX":  ["antrum biopsy", "biopsy of antrum", "gastric antrum biopsy"],
    "0DB98ZX":  ["duodenal biopsy", "duodenum biopsy", "biopsy of duodenum",
                 "duodenal mucosa biopsy"],
    "0DBB8ZX":  ["ileum biopsy", "biopsy of ileum", "terminal ileum biopsy",
                 "biopsy of terminal ileum"],
    "0DBH8ZX":  ["cecum biopsy", "biopsy of cecum", "caecum biopsy",
                 "biopsy of caecum"],
    "009U3ZX":  ["csf biopsy", "cerebrospinal fluid biopsy", "lumbar puncture",
                 "lp done", "csf sample"],
    "0B9J8ZX":  ["drainage of left lower lung", "left lower lobe drainage"],
}


_CODE_SYNONYMS = {
    #  Workbook additions — cardiology / STEMI / arrhythmia
    "I22.1":   ["subsequent stemi inferior", "second mi inferior wall"],
    "I21.02":  ["stemi lad", "stemi left anterior descending", "anterior stemi"],
    "I21.4":   ["nstemi", "non-st elevation mi", "non st elevation myocardial infarction"],
    "I48.19":  ["persistent atrial fibrillation", "persistent afib"],
    "I48.20":  ["chronic atrial fibrillation", "chronic afib"],
    "I48.91":  ["atrial fibrillation unspecified", "afib", "atrial fibrillation"],
    "I25.10":  ["coronary artery disease", "cad", "atherosclerotic heart disease"],
    "I25.5":   ["ischemic cardiomyopathy"],
    "I50.9":   ["heart failure", "chf", "congestive heart failure", "cardiac failure"],
    "I50.21":  ["acute systolic heart failure"],
    "I50.32":  ["chronic diastolic heart failure"],
    "E78.5":   ["hyperlipidemia", "hyperlipidaemia", "dyslipidemia", "dyslipidaemia"],
    "E78.00":  ["hypercholesterolemia", "hypercholesterolaemia"],
    "E66.3":   ["overweight"],
    "E66.01":  ["morbid obesity", "morbidly obese", "severe obesity"],

    #  Workbook additions — DM combination codes (backup for combination rule)
    "E11.42":  ["diabetes with polyneuropathy", "diabetic polyneuropathy", "diabetes with neuropathy"],
    "E11.621": ["diabetic foot ulcer", "diabetes with foot ulcer"],
    "E11.22":  ["diabetic nephropathy", "diabetes with ckd", "diabetes with chronic kidney disease"],
    "E11.319": ["diabetic retinopathy", "diabetes with retinopathy"],
    "E11.43":  ["diabetic gastroparesis"],
    "E10.9":   ["type 1 diabetes", "t1dm", "insulin dependent diabetes", "iddm"],

    #  Workbook additions — respiratory
    "J44.9":   ["copd", "chronic obstructive pulmonary disease"],
    "J44.1":   ["copd exacerbation", "acute exacerbation of copd", "acute copd"],
    "J44.0":   ["copd with acute lower respiratory infection", "copd with pneumonia"],
    "J45.909": ["asthma", "bronchial asthma"],
    "J45.901": ["asthma exacerbation", "acute asthma"],
    "J96.00":  ["acute respiratory failure"],
    "J96.10":  ["chronic respiratory failure"],
    "J96.20":  ["acute on chronic respiratory failure"],
    "J96.21":  ["acute on chronic hypercapnic respiratory failure"],
    "J20.9":   ["acute bronchitis"],

    #  Workbook additions — mental health / neuro
    "F32.9":   ["depression", "major depression", "depressive episode"],
    "F41.9":   ["anxiety", "anxiety disorder", "generalized anxiety"],
    "F10.20":  ["alcohol dependence", "alcoholism"],
    "F17.210": ["nicotine dependence", "current smoker", "tobacco dependence"],
    "G30.9":   ["alzheimer", "alzheimers disease", "alzheimer disease"],
    "F03.90":  ["dementia", "unspecified dementia"],
    "R45.1":   ["restlessness", "agitation"],

    #  Workbook additions — status Z-codes
    "Z87.891": ["former smoker", "ex-smoker", "history of tobacco use", "quit smoking"],
    "Z95.5":   ["coronary stent", "prior stent", "prior angioplasty", "history of pci"],
    "Z95.1":   ["prior cabg", "coronary bypass graft"],
    "Z79.82":  ["long term aspirin", "aspirin therapy"],
    "Z79.01":  ["long term anticoagulant", "warfarin therapy", "on warfarin"],
    "Z88.0":   ["penicillin allergy"],
    "Z88.2":   ["sulfa allergy", "sulfonamide allergy"],
    "Z91.19":  ["noncompliance", "non compliance", "not compliant with treatment"],

    #  Common symptoms (American spelling not in WHO CSV)
    "R06.00": ["dyspnea", "dyspnoea", "shortness of breath", "sob", "breathlessness"],
    "R06.09": ["exertional dyspnea", "dyspnea on exertion", "doe"],
    "K92.1":  ["melena", "melaena", "blood in stool", "black stool", "tarry stool"],
    "R63.4":  ["weight loss", "loss of weight", "losing weight"],
    "R16.2":  ["hepatosplenomegaly", "hepato-splenomegaly"],
    "R20.2":  ["numbness", "tingling", "paraesthesia", "paresthesia"],
    "R10.13": ["epigastric pain", "epigastric burning", "epigastric discomfort"],
    "R40.20": ["coma", "unconscious", "unresponsive"],
    "R41.3":  ["confusion", "confused", "altered consciousness"],
    "R00.0":  ["tachycardia", "fast heart rate", "heart rate elevated"],
    "R50.9":  ["fever", "pyrexia", "febrile", "high temperature", "high grade fever",
               "low grade fever", "febrile illness", "acute febrile illness"],
    "R60.9":  ["edema", "oedema", "swelling", "bilateral swelling",
               "bilateral lower limb swelling", "pitting edema", "body swelling"],
    "R05.9":  ["cough", "dry cough", "productive cough", "chronic cough"],
    "R19.7":  ["diarrhea", "diarrhoea", "loose stool", "loose motions"],
    #  051904 
    "30233N1": ["transfusion", "transfused", "pcv", "packed cell"],
    "D56.3":   ["thalassemia", "thalassaemia"],
    "E11.9":   ["diabetes", "diabetic", "dm"],
    "K27.9":   ["peptic ulcer", "peptic ulcer disease", "ulcer", "pud"],
    #  490434 
    "I10":     ["hypertension", "hypertensive", "htn", "hbp", "high blood pressure",
                "essential hypertension", "systemic hypertension"],
    "I27.21":  ["pulmonary artery hypertension", "pah", "pulmonary hypertension"],
    "I51.7":   ["cardiomegaly", "lv hypertrophy", "concentric lv", "lv hypertrophy ef",
                "rv hypertrophy", "left ventricular hypertrophy", "concentric lv hypertrophy"],
    "J12.1":   ["viral pneumonitis", "viral pneuonitis", "rsv", "resp b virus",
                "respiratory syncytial", "resp b virus positive"],
    "J81.1":   ["pulmonary edema", "pulmonary oedema", "ground glass"],
    "J84.89":  ["interstitial lung", "ground glass", "hrct", "bilateral ground glass",
                "b/l ground glass"],
    "N00.9":   ["nephritic", "nephrotic"],
    "N17.9":   ["acute kidney injury", "aki", "acute kidney failure", "acute renal failure"],
    "R19.09":  ["adnexal", "fibroid", "pelvic mass", "adexenal",
                "adnexal mass", "subserosal fibroid", "intra-abdominal mass",
                "abdominal mass", "abdominal swelling"],
    "Z20.822": ["covid", "sars-cov", "coronavirus", "covid pcr"],
    #  523037 
    "C64.1":   ["renal cell carcinoma", "clear cell carcinoma", "kidney carcinoma",
                "right kidney", "renal neoplasm", "right renal cell"],
    "Z79.4":   ["insulin", "long term insulin"],
    "Z90.5":   ["absence of kidney", "nephrectomy"],
    #  618013 
    "D64.9":   ["anemia", "anaemia", "pale", "anemic", "anaemic", "iron deficiency anemia"],
    "J13.":    ["streptococcus pneumoniae", "streptococcus pneumonae", "pneumococcal", "pneumococcal pneumonia"],
    "J47.1":   ["bronchiectasis", "bronchiectatic", "bronchiectasis with acute exacerbation",
                "bronchiaciatic", "bronchactasis", "bronchectasis"],   # common typing errors
    "N05.2":   ["membranous glomerulonephritis", "membranious", "nephritic syndrome",
                "membranous nephropathy"],
    #  679242 
    "D69.6":   ["thrombocytopenia", "itp"],
    "G36.0":   ["neuromyelitis optica", "nmo", "devic"],
    "G37.81":  ["mog antibody", "myelin oligodendrocyte", "mog"],
    "H53.8":   ["visual disturbance", "vision loss", "optic atrophy"],
    "K80.20":  ["gallbladder", "gallstone", "cholecystitis"],
    "L03.115": ["cellulitis", "lower limb cellulitis", "cellulitls"],

    "T25.021A":["burn of right foot", "foot burn"],
    #  734696 
    "J90":     ["pleural effusion", "pleural fluid", "hydrothorax"],
    "A16.2":   ["pulmonary tuberculosis", "pulmonary tb", "tb lung", "tuberculosis lung",
                "ptb", "pulm tb"],
    "0W993ZX": ["pleural tap", "thoracocentesis", "pleural fluid"],
    "A07.1":   ["giardia", "giardiasis"],
    "B74.9":   ["filariasis", "lymphoedema", "lymphedema", "lymphatic"],
    "D72.10":  ["eosinophilia", "eosinophil"],
    "D82.4":   ["ige", "hyperimmunoglobulin", "hyper-ige"],
    "J18.1":   ["pneumonia", "lobar pneumonia"],
    "J86.9":   ["empyema", "pyothorax"],
    "K29.50":  ["gastritis", "chronic gastritis", "pangastric erythema",
                "pan gastric", "gastric erythema"],
    "K31.89":  ["stomach", "duodenum", "duodenal erythema", "fissuring of duodenum",
                "distal duodenum", "duodenal ulcer", "duodenitis", "gastroduodenitis",
                "erythematous duodenum", "erosive duodenum"],
    "K36":     ["appendicitis", "appendix"],
    "K52.9":   ["gastroenteritis", "colitis", "diarrhoea and vomiting", "loose stools with fever",
                "acute diarrhoeal illness", "diarrhoeal illness"],
    "K90.49":  ["malabsorption"],
    "N43.3":   ["hydrocele"],
    "R18.8":   ["ascites", "abdominal fluid", "abdominal swelling"],
    #  736411 
    "B96.20":  ["e. coli", "escherichia coli", "ecoli"],
    "M31.30":  ["wegener", "granulomatosis", "granumatosis", "wegener's granumatosis",
                "wegener granulomatosis"],
    "N39.0":   ["urinary tract infection", "uti", "urine infection", "urinary infection"],
    #  736804 
    "D50.9":   ["iron deficiency", "iron deficiency anemia"],
    "K60.2":   ["anal fissure", "fissure"],
    "K64.4":   ["hemorrhoidal", "haemorrhoidal", "skin tag", "perianal tag",
                "hemorrhoidal skin tag", "haemorrhoidal skin tag"],
    "K90.1":   ["tropical sprue"],
    "R75":     ["hiv", "human immunodef"],
    "T39.395A":["nsaid", "anti-inflammatory"],
    "Z90.710": ["absence of cervix", "absence of uterus", "hysterectomy"],
}
