"""
LLM Service for ICD-10 code suggestion with anti-hallucination.
Uses Groq (free) as primary, Anthropic as fallback.
Anti-hallucination: LLM only picks from BM25-retrieved candidate codes.
All output codes validated against database before returning.
"""
import os
import json
import re
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"
ANTHROPIC_MODEL = "claude-sonnet-4-6"


class LLMService:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    def analyze(self, text: str, entities: dict, candidate_codes: list) -> dict:
        if not candidate_codes:
            return self._empty_result("No candidate codes found for this text.")

        candidates_text = "\n".join([
            f"  - {c['code']}: {c['description']} [{c['chapter']}]"
            for c in candidate_codes[:30]
        ])
        clinical_summary = self._build_clinical_summary(entities)

        prompt = f"""You are a certified medical coder (CCS, CPC) with expertise in ICD-10-CM coding. Analyze the clinical document below and assign ICD-10-CM codes.

CLINICAL DOCUMENT:
{text[:3000]}

EXTRACTED CLINICAL INFORMATION:
{clinical_summary}

CANDIDATE ICD-10-CM CODES — you MUST only select from this exact list:
{candidates_text}

INSTRUCTIONS:
1. First determine: is this a legitimate medical/clinical document? If the text is garbled, non-medical, or completely unreadable, set principal_diagnosis confidence to "low" and explain in coding_summary.
2. Select the PRINCIPAL DIAGNOSIS (main reason for encounter/admission).
3. List SECONDARY DIAGNOSES (comorbidities, complications, symptoms).
4. For each code: cite SPECIFIC evidence from the document text.
5. Assign confidence: "high" = explicitly documented, "medium" = implied/inferred, "low" = speculative/unclear text.
6. Follow ICD-10-CM Official Guidelines (code to highest specificity).
7. NEVER invent codes not in the candidate list above.

Return ONLY valid JSON:
{{
  "principal_diagnosis": {{
    "code": "CODE_FROM_LIST",
    "description": "exact description",
    "confidence": "high|medium|low",
    "justification": "specific text evidence",
    "coding_notes": "ICD-10-CM guideline notes"
  }},
  "secondary_diagnoses": [
    {{
      "code": "CODE_FROM_LIST",
      "description": "exact description",
      "confidence": "high|medium|low",
      "justification": "specific text evidence",
      "coding_notes": "guideline notes",
      "relationship": "comorbidity|complication|symptom|history"
    }}
  ],
  "excluded_considerations": [
    {{
      "code": "CODE_FROM_LIST",
      "reason_excluded": "why considered but not selected"
    }}
  ],
  "coding_summary": "overall coding rationale",
  "documentation_gaps": ["missing info that would support more specific coding"],
  "query_for_physician": "clinical queries for the treating physician"
}}

Only use codes from the CANDIDATE LIST. Respond with ONLY the JSON, no extra text."""

        try:
            raw = self._call_llm(prompt)
            return self._parse_and_validate(raw, candidate_codes)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._fallback_result(candidate_codes, str(e))

    def _build_clinical_summary(self, entities: dict) -> str:
        lines = []
        if entities.get("document_type"):
            lines.append(f"Document type: {entities['document_type'].replace('_', ' ').title()}")
        demo = entities.get("demographics", {})
        if demo:
            parts = []
            if "age" in demo: parts.append(f"Age: {demo['age']}")
            if "gender" in demo: parts.append(f"Gender: {demo['gender']}")
            if demo.get("pregnant"): parts.append("Pregnant")
            if parts: lines.append("Patient: " + ", ".join(parts))
        if entities.get("vitals"):
            v = entities["vitals"]
            vp = []
            if "bp" in v: vp.append(f"BP {v['bp']['systolic']}/{v['bp']['diastolic']}")
            for k in ["hr", "temp", "spo2", "glucose", "weight", "bmi"]:
                if k in v: vp.append(f"{k.upper()} {v[k]}")
            if vp: lines.append("Vitals: " + ", ".join(vp))
        if entities.get("labs"):
            lp = [f"{k.upper()}={v}" for k, v in list(entities["labs"].items())[:10]]
            if lp: lines.append("Labs: " + ", ".join(lp))
        if entities.get("medications"):
            lines.append("Medications: " + ", ".join(entities["medications"][:15]))
        if entities.get("allergies"):
            lines.append("Allergies: " + ", ".join(entities["allergies"]))
        if entities.get("keywords"):
            lines.append("Clinical terms: " + ", ".join(entities["keywords"][:20]))
        if entities.get("flagged_abnormals"):
            flags = [f"{f['label']} ({f['value']})" for f in entities["flagged_abnormals"][:5]]
            if flags: lines.append("⚠️ Abnormals: " + ", ".join(flags))
        return "\n".join(lines) if lines else "No structured clinical data extracted"

    def _call_llm(self, prompt: str) -> str:
        if self.provider == "groq" and self.groq_key:
            return self._call_groq(prompt)
        elif self.provider == "anthropic" and self.anthropic_key:
            return self._call_anthropic(prompt)
        elif self.groq_key:
            return self._call_groq(prompt)
        elif self.anthropic_key:
            return self._call_anthropic(prompt)
        else:
            raise ValueError("No LLM API key configured. Add GROQ_API_KEY to backend/.env")

    def _call_groq(self, prompt: str) -> str:
        from groq import Groq
        import httpx
        # httpx.Client() avoids the 'proxies' conflict on groq 0.9.x + httpx 0.28+
        client = Groq(api_key=self.groq_key, http_client=httpx.Client())
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=3000,
        )
        return response.choices[0].message.content

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=self.anthropic_key)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def _parse_and_validate(self, raw: str, candidate_codes: list) -> dict:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON in LLM response")
        data = json.loads(json_match.group())
        valid_codes = {c["code"]: c for c in candidate_codes}

        # Validate principal
        principal = data.get("principal_diagnosis", {})
        if principal.get("code") in valid_codes:
            principal["verified"] = True
            db = valid_codes[principal["code"]]
            principal.update({"description": db["description"],
                              "chapter": db["chapter"], "category": db["category"]})
        else:
            principal["verified"] = False
            principal["warning"] = "Code not in verified database — review required"

        # Validate secondaries
        validated = []
        for d in data.get("secondary_diagnoses", []):
            if d.get("code") in valid_codes:
                d["verified"] = True
                db = valid_codes[d["code"]]
                d.update({"description": db["description"],
                          "chapter": db["chapter"], "category": db["category"]})
                validated.append(d)

        data["secondary_diagnoses"] = validated
        data["principal_diagnosis"] = principal
        data["total_codes"] = 1 + len(validated)
        data["all_verified"] = principal.get("verified", False) and all(
            d.get("verified", False) for d in validated)
        return data

    def _fallback_result(self, candidate_codes: list, error: str) -> dict:
        top = candidate_codes[:5] if candidate_codes else []
        return {
            "principal_diagnosis": {
                "code": top[0]["code"] if top else "R69",
                "description": top[0]["description"] if top else "Illness unspecified",
                "confidence": "low",
                "justification": "LLM unavailable — BM25 fallback. Manual review required.",
                "verified": True, "warning": f"LLM error: {error}"
            },
            "secondary_diagnoses": [
                {"code": c["code"], "description": c["description"], "confidence": "low",
                 "justification": "BM25 fallback", "verified": True, "relationship": "comorbidity"}
                for c in top[1:4]
            ],
            "coding_summary": f"LLM service error — manual review required. Error: {error}",
            "documentation_gaps": ["Manual review required"],
            "query_for_physician": "Please verify all codes manually",
            "total_codes": len(top), "all_verified": True, "error": error
        }

    def _empty_result(self, message: str) -> dict:
        return {"principal_diagnosis": None, "secondary_diagnoses": [],
                "coding_summary": message, "documentation_gaps": [],
                "query_for_physician": "", "total_codes": 0,
                "all_verified": True, "error": message}

    def check_drug_interactions(self, medications: list) -> list:
        if len(medications) < 2:
            return []
        KNOWN_INTERACTIONS = [
            ({"warfarin"}, {"aspirin", "ibuprofen", "naproxen", "diclofenac"}, "MAJOR",
             "NSAIDs + Warfarin: Significantly increased bleeding risk. Monitor INR closely."),
            ({"warfarin"}, {"ciprofloxacin", "metronidazole", "fluconazole"}, "MAJOR",
             "Antibiotics/antifungals may potentiate warfarin. INR may increase dramatically."),
            ({"metformin"}, {"contrast", "iodinated"}, "MODERATE",
             "Hold metformin before iodinated contrast — lactic acidosis risk."),
            ({"ssri", "sertraline", "fluoxetine", "paroxetine", "citalopram", "escitalopram"},
             {"tramadol", "fentanyl", "morphine", "codeine"}, "MAJOR",
             "SSRI + Opioids: Risk of serotonin syndrome."),
            ({"lithium"}, {"ibuprofen", "naproxen", "diclofenac", "indomethacin"}, "MAJOR",
             "NSAIDs increase lithium levels — toxicity risk."),
            ({"atorvastatin", "simvastatin", "rosuvastatin"},
             {"clarithromycin", "itraconazole", "voriconazole"}, "MODERATE",
             "CYP3A4 inhibitors increase statin levels — myopathy risk."),
            ({"lisinopril", "enalapril", "ramipril"},
             {"spironolactone"}, "MODERATE",
             "ACE inhibitor + spironolactone: Hyperkalemia risk."),
            ({"methotrexate"}, {"ibuprofen", "naproxen", "diclofenac", "aspirin"}, "MAJOR",
             "NSAIDs reduce methotrexate clearance — toxicity risk."),
            ({"digoxin"}, {"amiodarone"}, "MAJOR",
             "Amiodarone increases digoxin levels — toxicity risk."),
            ({"sertraline", "fluoxetine"}, {"selegiline"}, "CONTRAINDICATED",
             "SSRI + MAOI: Contraindicated — serotonin syndrome risk."),
            ({"sildenafil", "tadalafil", "vardenafil"},
             {"isosorbide", "nitroglycerin"}, "CONTRAINDICATED",
             "PDE5 inhibitors + Nitrates: Contraindicated — severe hypotension."),
            ({"ciprofloxacin", "levofloxacin"}, {"prednisolone", "dexamethasone"}, "MODERATE",
             "Fluoroquinolones + Corticosteroids: Tendon rupture risk."),
            ({"clopidogrel"}, {"omeprazole", "esomeprazole"}, "MODERATE",
             "Omeprazole reduces clopidogrel efficacy. Consider pantoprazole."),
        ]
        meds_lower = [m.lower() for m in medications]
        warnings = []
        for s1, s2, severity, message in KNOWN_INTERACTIONS:
            f1 = any(any(d in m for d in s1) for m in meds_lower)
            f2 = any(any(d in m for d in s2) for m in meds_lower)
            if f1 and f2:
                m1 = [m for m in meds_lower if any(d in m for d in s1)]
                m2 = [m for m in meds_lower if any(d in m for d in s2)]
                warnings.append({
                    "severity": severity,
                    "drugs": m1 + m2,
                    "message": message,
                    "action": "Review with prescriber" if severity == "MODERATE"
                              else "IMMEDIATE clinical review required"
                })
        return warnings
