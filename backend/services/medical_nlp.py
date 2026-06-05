"""
Medical NLP Service - Entity extraction from clinical text.
Extracts: diagnoses, symptoms, medications, allergies, vitals, lab values,
          procedures, patient demographics.
Pure regex/heuristic approach — no ML model required (no GPU needed).
"""
import re
import logging

logger = logging.getLogger(__name__)

MED_PATTERNS = [
    r'\b(metformin|insulin|glipizide|glibenclamide|sitagliptin|empagliflozin|canagliflozin|dapagliflozin|liraglutide|semaglutide)\b',
    r'\b(atorvastatin|rosuvastatin|simvastatin|pravastatin|lovastatin)\b',
    r'\b(amlodipine|nifedipine|diltiazem|verapamil)\b',
    r'\b(lisinopril|enalapril|ramipril|perindopril|captopril)\b',
    r'\b(losartan|valsartan|telmisartan|irbesartan|olmesartan)\b',
    r'\b(metoprolol|atenolol|bisoprolol|carvedilol|propranolol|nebivolol)\b',
    r'\b(furosemide|spironolactone|hydrochlorothiazide|HCTZ|chlorthalidone|indapamide)\b',
    r'\b(aspirin|clopidogrel|ticagrelor|prasugrel|warfarin|rivaroxaban|apixaban|dabigatran|edoxaban)\b',
    r'\b(omeprazole|esomeprazole|pantoprazole|lansoprazole|rabeprazole)\b',
    r'\b(amoxicillin|amoxicillin.clavulanate|augmentin|ciprofloxacin|levofloxacin|azithromycin|doxycycline|metronidazole|clindamycin|trimethoprim|nitrofurantoin|ceftriaxone|cefixime|vancomycin|meropenem|piperacillin.tazobactam)\b',
    r'\b(paracetamol|acetaminophen|ibuprofen|naproxen|diclofenac|celecoxib|indomethacin|ketorolac)\b',
    r'\b(morphine|oxycodone|tramadol|codeine|fentanyl|hydrocodone|buprenorphine)\b',
    r'\b(prednisolone|prednisone|dexamethasone|hydrocortisone|methylprednisolone|budesonide)\b',
    r'\b(levothyroxine|thyroxine|carbimazole|methimazole|propylthiouracil)\b',
    r'\b(salbutamol|albuterol|ipratropium|tiotropium|salmeterol|formoterol|fluticasone|beclomethasone)\b',
    r'\b(sertraline|fluoxetine|paroxetine|citalopram|escitalopram|venlafaxine|duloxetine|mirtazapine|amitriptyline|clomipramine)\b',
    r'\b(haloperidol|risperidone|olanzapine|quetiapine|aripiprazole|clozapine|ziprasidone)\b',
    r'\b(lithium|valproate|valproic acid|carbamazepine|lamotrigine|levetiracetam|phenytoin|phenobarbitone)\b',
    r'\b(methotrexate|hydroxychloroquine|sulfasalazine|leflunomide|infliximab|adalimumab|etanercept|tocilizumab|rituximab|abatacept)\b',
    r'\b(alendronate|risedronate|zoledronic acid|denosumab|teriparatide)\b',
    r'\b(ondansetron|metoclopramide|domperidone|prochlorperazine|promethazine)\b',
    r'\b(allopurinol|febuxostat|colchicine|probenecid)\b',
    r'\b(digoxin|amiodarone|flecainide|adenosine|lidocaine|atropine)\b',
    r'\b(heparin|enoxaparin|fondaparinux|dalteparin)\b',
    r'\b(sildenafil|tadalafil|vardenafil)\b',
    r'\b(tamsulosin|finasteride|dutasteride)\b',
    r'\b(gabapentin|pregabalin|capsaicin)\b',
    r'\b(acyclovir|valacyclovir|oseltamivir|remdesivir|tenofovir|emtricitabine|dolutegravir)\b',
    r'\b(fluconazole|itraconazole|voriconazole|amphotericin)\b',
]

# FIX: Allergy patterns now require a colon after "allergies" to avoid
# matching the word in unrelated contexts (e.g. lab report headers).
# Also minimum 3 chars and maximum 100 chars for the matched value.
ALLERGY_PATTERNS = [
    r'(?:allerg(?:ic|y)\s+to|NKDA|NKA|no known drug allerg(?:y|ies)|drug allerg(?:y|ies))\s*:?\s*([^\n.;]{3,100})',
    r'(?:allergies?)\s*:\s*([^\n.;]{3,100})',
    r'(?:sensitive\s+to|intolerance?\s+to|reaction\s+to)\s+([^\n.;,]{3,80})',
]

VITAL_PATTERNS = {
    "bp":      r'(?:BP|blood\s+pressure)\s*:?\s*(\d{2,3})\s*/\s*(\d{2,3})',
    "hr":      r'(?:HR|heart\s+rate|pulse\s+rate)\s*:?\s*(\d{2,3})\s*(?:bpm|/min)?',
    "rr":      r'(?:RR|respiratory\s+rate)\s*:?\s*(\d{1,2})\s*(?:/min)?',
    # FIX: temp requires °C/°F/deg unit — prevents matching numbers from lab tables
    "temp":    r'(?:temp(?:erature)?)\s*:?\s*(\d{2,3}(?:\.\d)?)\s*(?:°[CF]|deg)',
    "spo2":    r'(?:SpO2|O2\s*sat(?:uration)?|oxygen\s+sat(?:uration)?)\s*:?\s*(\d{2,3})\s*%?',
    "weight":  r'(?:weight|wt)\s*:?\s*(\d{2,3}(?:\.\d+)?)\s*(?:kg|lbs?)',
    "height":  r'(?:height|ht)\s*:?\s*(\d{2,3}(?:\.\d+)?)\s*(?:cm|m|ft)',
    "bmi":     r'(?:BMI|body\s+mass\s+index)\s*:?\s*(\d{2,3}(?:\.\d+)?)',
    "glucose": r'(?:glucose|blood\s+sugar|FBS|RBS|FPG)\s*:?\s*(\d{2,4}(?:\.\d+)?)\s*(?:mg/dL|mmol/L)?',
}

# FIX: WBC and platelets now require the /cmm or /uL unit AFTER the number.
# This prevents matching reference range values like "4000 - 10000".
# In Indian lab reports the format is: "WBC Count ... H 10570 /cmm"
LAB_PATTERNS = {
    # Hemoglobin: matches "Hemoglobin ... 14.5 g/dL" — requires g/dL unit
    "hb": (
        r'(?:Hb|Hgb|[Hh]emoglobin|[Hh]aemoglobin)'
        r'[^0-9\n]{0,40}?'
        r'(\d{1,3}(?:\.\d+)?)'
        r'\s*g/dL'
    ),
    # WBC: matches number followed by /cmm or /uL — rules out reference ranges
    "wbc": (
        r'(?:WBC(?:\s+[Cc]ount)?|[Ww]hite\s+[Bb]lood\s+[Cc]ell[s]?)'
        r'[^0-9\n]{0,60}?'
        r'[HhLl]?\s*'
        r'(\d{3,6}(?:\.\d+)?)'
        r'\s*/(?:cmm|[cC]mm|[μuU][Ll]|mm3)'
    ),
    # Platelets: same approach — requires /cmm or /uL
    "platelets": (
        r'(?:[Pp]latelet(?:\s+[Cc]ount)?|PLT)'
        r'[^0-9\n]{0,60}?'
        r'[HhLl]?\s*'
        r'(\d{4,7}(?:\.\d+)?)'
        r'\s*/(?:cmm|[cC]mm|[μuU][Ll]|mm3)'
    ),
    "creatinine":   r'(?:[Cc]reatinine|Cr\b|SCr)\s*:?\s*(\d{1,3}(?:\.\d+)?)\s*(?:mg/dL|umol/L|μmol/L)?',
    "hba1c":        r'(?:HbA1c|A1C|[Gg]lycated\s+[Hh]emoglobin)\s*:?\s*(\d{1,2}(?:\.\d+)?)\s*%?',
    "egfr":         r'(?:eGFR|GFR)\s*:?\s*(\d{1,3}(?:\.\d+)?)',
    "sodium":       r'(?:[Ss]odium|Na\+?)\s*:?\s*(\d{2,3}(?:\.\d+)?)',
    "potassium":    r'(?:[Pp]otassium|K\+?)\s*:?\s*(\d{1,2}(?:\.\d+)?)',
    "alt":          r'(?:ALT|SGPT)\s*:?\s*(\d{1,5}(?:\.\d+)?)',
    "ast":          r'(?:AST|SGOT)\s*:?\s*(\d{1,5}(?:\.\d+)?)',
    "bilirubin":    r'(?:[Bb]ilirubin)\s*:?\s*(\d{1,3}(?:\.\d+)?)',
    "albumin":      r'(?:[Aa]lbumin)\s*:?\s*(\d{1,2}(?:\.\d+)?)',
    "tsh":          r'(?:TSH|[Tt]hyroid\s+[Ss]timulating\s+[Hh]ormone)\s*:?\s*(\d{1,3}(?:\.\d+)?)',
    "cholesterol":  r'(?:[Tt]otal\s+[Cc]holesterol|TC)\s*:?\s*(\d{2,4}(?:\.\d+)?)',
    "ldl":          r'(?:LDL)\s*:?\s*(\d{2,4}(?:\.\d+)?)',
    "hdl":          r'(?:HDL)\s*:?\s*(\d{2,3}(?:\.\d+)?)',
    "triglycerides": r'(?:[Tt]riglycerides?|TG)\s*:?\s*(\d{2,4}(?:\.\d+)?)',
    "inr":          r'(?:INR)\s*:?\s*(\d{1,2}(?:\.\d+)?)',
    "crp":          r'(?:CRP|[Cc]-[Rr]eactive\s+[Pp]rotein)\s*:?\s*(\d{1,5}(?:\.\d+)?)',
    "psa":          r'(?:PSA|[Pp]rostate\s+[Ss]pecific\s+[Aa]ntigen)\s*:?\s*(\d{1,3}(?:\.\d+)?)',
    "troponin":     r'(?:[Tt]roponin|cTnI|cTnT|hs-[Tt]roponin)\s*:?\s*(\d{1,5}(?:\.\d+)?)',
}

LAB_RANGES = {
    "hb":          {"low": 12.0,   "high": 17.5,   "unit": "g/dL",  "low_flag": "Anemia",                        "high_flag": "Polycythemia"},
    "wbc":         {"low": 4000,   "high": 11000,  "unit": "/μL",   "low_flag": "Leukopenia/Neutropenia",        "high_flag": "Leukocytosis/Infection"},
    "platelets":   {"low": 150000, "high": 400000, "unit": "/μL",   "low_flag": "Thrombocytopenia",              "high_flag": "Thrombocytosis"},
    "creatinine":  {"low": 0.5,    "high": 1.2,    "unit": "mg/dL", "low_flag": None,                            "high_flag": "Renal impairment"},
    "hba1c":       {"low": 0,      "high": 6.5,    "unit": "%",     "low_flag": "Hypoglycemia risk",             "high_flag": "Poor glycemic control"},
    "sodium":      {"low": 136,    "high": 145,    "unit": "mEq/L", "low_flag": "Hyponatremia",                  "high_flag": "Hypernatremia"},
    "potassium":   {"low": 3.5,    "high": 5.0,    "unit": "mEq/L", "low_flag": "Hypokalemia",                   "high_flag": "Hyperkalemia"},
    "alt":         {"low": 0,      "high": 56,     "unit": "U/L",   "low_flag": None,                            "high_flag": "Liver injury"},
    "tsh":         {"low": 0.4,    "high": 4.0,    "unit": "mIU/L", "low_flag": "Hyperthyroidism",               "high_flag": "Hypothyroidism"},
    "ldl":         {"low": 0,      "high": 100,    "unit": "mg/dL", "low_flag": None,                            "high_flag": "Dyslipidemia"},
    "inr":         {"low": 0.8,    "high": 1.2,    "unit": "",      "low_flag": None,                            "high_flag": "Coagulopathy/Over-anticoagulation"},
    "troponin":    {"low": 0,      "high": 0.04,   "unit": "ng/mL", "low_flag": None,                            "high_flag": "Myocardial injury — URGENT"},
}


class MedicalNLPService:
    def extract_entities(self, text: str) -> dict:
        text_lower = text.lower()
        result = {
            "medications":       self._extract_medications(text_lower),
            "allergies":         self._extract_allergies(text),
            "vitals":            self._extract_vitals(text),
            "labs":              self._extract_labs(text),
            "demographics":      self._extract_demographics(text),
            "keywords":          self._extract_clinical_keywords(text_lower),
            "document_type":     self._classify_document(text_lower),
            "flagged_abnormals": [],
        }
        result["flagged_abnormals"] = self._flag_abnormals(result["vitals"], result["labs"])
        return result

    # ── Medications ───────────────────────────────────────────────────
    def _extract_medications(self, text: str) -> list:
        meds = set()
        for pattern in MED_PATTERNS:
            for m in re.findall(pattern, text, re.IGNORECASE):
                meds.add(m.strip().lower())
        return sorted(list(meds))

    # ── Allergies ─────────────────────────────────────────────────────
    def _extract_allergies(self, text: str) -> list:
        allergies = []
        for pattern in ALLERGY_PATTERNS:
            for m in re.findall(pattern, text, re.IGNORECASE):
                t = m.strip()
                if not t or len(t) < 3 or len(t) > 100:
                    continue
                # Skip values that are just numbers, dates, or lab values
                if re.match(r'^[\d\s./:-]+$', t):
                    continue
                t_lower = t.lower()
                if t_lower in ['nkda', 'nka', 'none', 'nil', 'no', 'n/a', 'na']:
                    allergies.append("NKDA (No Known Drug Allergies)")
                else:
                    allergies.append(t)
        # Deduplicate, keep only meaningful ones
        seen = set()
        result = []
        for a in allergies:
            key = a.lower()
            if key not in seen:
                seen.add(key)
                result.append(a)
        return result

    # ── Vitals ────────────────────────────────────────────────────────
    def _extract_vitals(self, text: str) -> dict:
        vitals = {}
        for key, pattern in VITAL_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if key == "bp":
                    vitals[key] = {
                        "systolic": int(match.group(1)),
                        "diastolic": int(match.group(2))
                    }
                else:
                    try:
                        vitals[key] = float(match.group(1))
                    except ValueError:
                        pass

        # Sanity checks — remove physiologically impossible values
        if "temp" in vitals:
            t = vitals["temp"]
            if not (34.0 <= t <= 43.0 or 93.0 <= t <= 110.0):
                del vitals["temp"]

        if "hr" in vitals:
            if not (20 <= vitals["hr"] <= 300):
                del vitals["hr"]

        if "spo2" in vitals:
            if not (50 <= vitals["spo2"] <= 100):
                del vitals["spo2"]

        if "weight" in vitals:
            if not (1 <= vitals["weight"] <= 500):
                del vitals["weight"]

        if "bmi" in vitals:
            if not (10 <= vitals["bmi"] <= 70):
                del vitals["bmi"]

        return vitals

    # ── Labs ──────────────────────────────────────────────────────────
    def _extract_labs(self, text: str) -> dict:
        labs = {}
        for key, pattern in LAB_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    labs[key] = float(match.group(1))
                except ValueError:
                    pass

        # Sanity checks
        if "wbc" in labs and labs["wbc"] > 150000:
            del labs["wbc"]

        if "platelets" in labs:
            if not (10000 <= labs["platelets"] <= 2000000):
                del labs["platelets"]

        if "hb" in labs and not (1 <= labs["hb"] <= 25):
            del labs["hb"]

        if "creatinine" in labs and not (0.1 <= labs["creatinine"] <= 30):
            del labs["creatinine"]

        if "hba1c" in labs and not (3 <= labs["hba1c"] <= 20):
            del labs["hba1c"]

        if "sodium" in labs and not (100 <= labs["sodium"] <= 180):
            del labs["sodium"]

        if "potassium" in labs and not (1.0 <= labs["potassium"] <= 10.0):
            del labs["potassium"]

        return labs

    # ── Demographics ──────────────────────────────────────────────────
    def _extract_demographics(self, text: str) -> dict:
        demo = {}

        # Age — handle formats: "41 Y", "41 year old", "41y", "41/M"
        age_match = re.search(
            r'(\d{1,3})\s*(?:[Yy](?:ear)?(?:s)?(?:\s*[Oo]ld)?|[Yy][Rr])',
            text
        )
        if age_match:
            age = int(age_match.group(1))
            if 0 < age < 130:
                demo["age"] = age

        # Gender
        if re.search(r'\b(?:male|man|gentleman|boy|Mr\.?|/\s*M\b)\b', text, re.IGNORECASE):
            demo["gender"] = "male"
        elif re.search(r'\b(?:female|woman|lady|girl|Mrs\.?|Ms\.?|/\s*F\b)\b', text, re.IGNORECASE):
            demo["gender"] = "female"

        # Pregnancy
        if re.search(r'\b(?:pregnant|pregnancy|gravid|trimester|gestation)\b', text, re.IGNORECASE):
            demo["pregnant"] = True

        return demo

    # ── Clinical Keywords ─────────────────────────────────────────────
    def _extract_clinical_keywords(self, text: str) -> list:
        terms = []
        patterns = [
            r'\b(fever|pyrexia|hyperthermia)\b',
            r'\b(chest pain|chest tightness|angina)\b',
            r'\b(shortness of breath|dyspnea|breathlessness|SOB)\b',
            r'\b(cough|hemoptysis)\b',
            r'\b(abdominal pain|epigastric pain)\b',
            r'\b(nausea|vomiting|diarrhoea|diarrhea|constipation)\b',
            r'\b(headache|migraine)\b',
            r'\b(dizziness|vertigo|syncope|fainting)\b',
            r'\b(palpitations|irregular heartbeat)\b',
            r'\b(edema|oedema|swelling)\b',
            r'\b(jaundice|icterus)\b',
            r'\b(hematuria|blood in urine)\b',
            r'\b(dysuria|burning urination|urinary frequency)\b',
            r'\b(joint pain|arthralgia|arthritis)\b',
            r'\b(back pain|lumbago|sciatica)\b',
            r'\b(rash|pruritus|itching|urticaria)\b',
            r'\b(weight loss|weight gain|obesity)\b',
            r'\b(fatigue|lethargy|weakness|malaise)\b',
            r'\b(confusion|altered mental status|encephalopathy)\b',
            r'\b(seizure|convulsion|epilepsy)\b',
            r'\b(stroke|CVA|TIA|hemiplegia|aphasia)\b',
            r'\b(diabetes|diabetic|hyperglycemia|hypoglycemia)\b',
            r'\b(hypertension|high blood pressure|HTN)\b',
            r'\b(hypotension|shock)\b',
            r'\b(tachycardia|bradycardia|atrial fibrillation)\b',
            r'\b(heart failure|CHF|cardiac failure)\b',
            r'\b(myocardial infarction|heart attack|MI|STEMI|NSTEMI)\b',
            r'\b(pneumonia|chest infection|consolidation)\b',
            r'\b(asthma|wheeze|bronchospasm)\b',
            r'\b(COPD|emphysema|chronic bronchitis)\b',
            r'\b(tuberculosis|TB|AFB)\b',
            r'\b(sepsis|septicemia|bacteremia)\b',
            r'\b(cancer|carcinoma|malignancy|tumor|neoplasm)\b',
            r'\b(HIV|AIDS|immunodeficiency)\b',
            r'\b(dengue|malaria|typhoid|COVID)\b',
            r'\b(hypothyroid|hyperthyroid|goiter|thyroid)\b',
            r'\b(kidney|renal|nephritis|CKD|AKI)\b',
            r'\b(liver|hepatic|hepatitis|cirrhosis)\b',
            r'\b(complete blood count|CBC|blood count)\b',
            r'\b(leukocytosis|leukopenia|neutrophilia|lymphocytosis)\b',
            r'\b(anemia|anaemia)\b',
            r'\b(thrombocytopenia|thrombocytosis)\b',
            r'\b(malarial parasite|parasite not detected|malaria)\b',
            r'\b(normochromic|normocytic|microcytic|macrocytic)\b',
        ]
        for p in patterns:
            for m in re.findall(p, text, re.IGNORECASE):
                if isinstance(m, tuple):
                    terms.extend([t.lower() for t in m if t])
                else:
                    terms.append(m.lower())
        return list(set(terms))

    # ── Document classifier ───────────────────────────────────────────
    def _classify_document(self, text: str) -> str:
        if re.search(r'\b(?:prescription|rx|tablets?|capsules?|sig:|dispense)\b', text, re.IGNORECASE):
            return "prescription"
        elif re.search(r'\b(?:discharge\s+summary|discharged|admission|hospital\s+stay)\b', text, re.IGNORECASE):
            return "discharge_summary"
        elif re.search(r'\b(?:laboratory\s+test\s+report|lab\s+report|laboratory|test\s+results?|complete\s+blood\s+count|CBC)\b', text, re.IGNORECASE):
            return "lab_report"
        elif re.search(r'\b(?:radiology|X-ray|CT\s+scan|MRI|ultrasound|imaging)\b', text, re.IGNORECASE):
            return "radiology_report"
        elif re.search(r'\b(?:operation|surgery|operative|intraoperative|postoperative)\b', text, re.IGNORECASE):
            return "operative_report"
        elif re.search(r'\b(?:chief\s+complaint|history\s+of\s+present\s+illness|HPI|assessment|plan)\b', text, re.IGNORECASE):
            return "clinical_note"
        elif re.search(r'\b(?:outpatient|OPD|clinic\s+visit|follow.?up)\b', text, re.IGNORECASE):
            return "outpatient_note"
        return "medical_document"

    # ── Abnormal flagging ─────────────────────────────────────────────
    def _flag_abnormals(self, vitals: dict, labs: dict) -> list:
        flags = []

        if "bp" in vitals:
            s, d = vitals["bp"]["systolic"], vitals["bp"]["diastolic"]
            if s >= 180 or d >= 120:
                flags.append({"type": "CRITICAL", "label": "Hypertensive Crisis",   "value": f"{s}/{d} mmHg"})
            elif s >= 140 or d >= 90:
                flags.append({"type": "WARNING",  "label": "Stage 2 Hypertension", "value": f"{s}/{d} mmHg"})
            elif s < 90 or d < 60:
                flags.append({"type": "CRITICAL", "label": "Hypotension",           "value": f"{s}/{d} mmHg"})

        if "spo2" in vitals:
            v = vitals["spo2"]
            if v < 90:   flags.append({"type": "CRITICAL", "label": "Severe Hypoxemia", "value": f"{v}%"})
            elif v < 94: flags.append({"type": "WARNING",  "label": "Hypoxemia",        "value": f"{v}%"})

        if "hr" in vitals:
            v = vitals["hr"]
            if v > 150:   flags.append({"type": "CRITICAL", "label": "Severe Tachycardia", "value": f"{v} bpm"})
            elif v > 100: flags.append({"type": "WARNING",  "label": "Tachycardia",        "value": f"{v} bpm"})
            elif v < 40:  flags.append({"type": "CRITICAL", "label": "Severe Bradycardia", "value": f"{v} bpm"})
            elif v < 60:  flags.append({"type": "INFO",     "label": "Bradycardia",        "value": f"{v} bpm"})

        if "temp" in vitals:
            v = vitals["temp"]
            if v >= 39.5:   flags.append({"type": "WARNING", "label": "High Fever",  "value": f"{v}°C"})
            elif v >= 38.0: flags.append({"type": "INFO",    "label": "Fever",       "value": f"{v}°C"})
            elif v < 36.0:  flags.append({"type": "WARNING", "label": "Hypothermia", "value": f"{v}°C"})

        for key, ref in LAB_RANGES.items():
            if key in labs:
                val = labs[key]
                if ref["high"] and val > ref["high"]:
                    sev = "CRITICAL" if key in ["troponin", "potassium", "inr"] else "WARNING"
                    flags.append({
                        "type": sev,
                        "label": ref["high_flag"],
                        "value": f"{val} {ref['unit']}",
                        "lab": key.upper()
                    })
                elif ref["low"] and val < ref["low"] and ref["low_flag"]:
                    sev = "CRITICAL" if key == "hb" and val < 7 else "WARNING"
                    flags.append({
                        "type": sev,
                        "label": ref["low_flag"],
                        "value": f"{val} {ref['unit']}",
                        "lab": key.upper()
                    })

        priority = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        flags.sort(key=lambda x: priority.get(x["type"], 3))
        return flags
