
# icd_synonyms.py — Clinical synonym → ICD-10 code mapping for SIUT.

# Structure:  icd_code → [synonym, synonym, ...]
# The synonyms are clinical phrases SIUT coders and clinicians actually write.
# They cover abbreviations, OCR typos, US/UK spelling, brand names, and
# phrases that map to ICD descriptions via medical knowledge (not text similarity).


_CODE_SYNONYMS = {
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
    "R19.09":  ["adnexal", "fibroid", "pelvic mass", "adexenal"],
    "Z20.822": ["covid", "sars-cov", "coronavirus", "covid pcr"],
    #  523037 
    "C64.1":   ["renal cell carcinoma", "clear cell carcinoma", "kidney carcinoma",
                "right kidney", "renal neoplasm", "right renal cell"],
    "Z79.4":   ["insulin", "long term insulin"],
    "Z90.5":   ["absence of kidney", "nephrectomy"],
    #  618013 
    "D64.9":   ["anemia", "anaemia", "pale", "anemic", "anaemic", "iron deficiency anemia"],
    "J13":     ["streptococcus pneumoniae", "streptococcus pneumonae", "pneumococcal"],
    "J47.1":   ["bronchiectasis", "bronchiectatic", "bronchiectasis with acute exacerbation"],
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
                "distal duodenum"],
    "K36":     ["appendicitis", "appendix"],
    "K52.9":   ["gastroenteritis", "colitis"],
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
