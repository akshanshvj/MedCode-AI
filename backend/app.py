"""
Medical Coding AI - Flask Backend v2
"""
import os
import logging
import json
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import io

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Init DB on startup
from auth import init_db
init_db()

_icd_service = None
_llm_service = None
_nlp_service = None

def get_services():
    global _icd_service, _llm_service, _nlp_service
    if _icd_service is None:
        from services.icd_service import ICDService
        from services.llm_service import LLMService
        from services.medical_nlp import MedicalNLPService
        _icd_service = ICDService()
        _llm_service = LLMService()
        _nlp_service = MedicalNLPService()
    return _icd_service, _llm_service, _nlp_service


# ── Health ────────────────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "version": "2.0.0"})


# ── Auth ──────────────────────────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def register():
    from auth import register as _register
    return _register()

@app.route('/api/auth/login', methods=['POST'])
def login():
    from auth import login as _login
    return _login()

@app.route('/api/auth/me', methods=['GET'])
def me():
    from auth import get_me
    return get_me()


# ── Payments ──────────────────────────────────────────────────────────
@app.route('/api/payment/create-order', methods=['POST'])
def create_order():
    from payment import create_order as _create_order
    return _create_order()

@app.route('/api/payment/verify', methods=['POST'])
def verify_payment():
    from payment import verify_payment as _verify
    return _verify()

@app.route('/api/payment/status', methods=['GET'])
def payment_status():
    from payment import get_subscription_status
    return get_subscription_status()


# ── Analyze ───────────────────────────────────────────────────────────
@app.route('/api/analyze', methods=['POST'])
def analyze():
    icd_service, llm_service, nlp_service = get_services()
    text = ""
    extraction_meta = {}

    try:
        if 'file' in request.files:
            file = request.files['file']
            if not file.filename:
                return jsonify({"error": "Empty filename"}), 400
            from services.ocr_service import extract_text
            extraction_result = extract_text(file)
            text = extraction_result["text"]
            extraction_meta = {
                "file_type": extraction_result["file_type"],
                "page_count": extraction_result["page_count"],
                "ocr_confidence": extraction_result["confidence"],
                "warnings": extraction_result["warnings"]
            }
            logger.info(f"OCR: {len(text)} chars from {file.filename}")

        elif request.is_json and request.json.get('text'):
            text = request.json['text']
            extraction_meta = {"file_type": "text", "page_count": 1,
                               "ocr_confidence": 1.0, "warnings": []}
        else:
            return jsonify({"error": "Provide a file or JSON with 'text' field"}), 400

        if not text or len(text.strip()) < 3:
            return jsonify({
                "error": "Insufficient text extracted",
                "extraction": extraction_meta
            }), 422

        entities = nlp_service.extract_entities(text)
        search_queries = _build_search_queries(text, entities)
        candidate_codes = icd_service.search_multi(search_queries, top_k=30)
        coding_result = llm_service.analyze(text, entities, candidate_codes)

        drug_interactions = []
        if entities.get("medications"):
            drug_interactions = llm_service.check_drug_interactions(entities["medications"])

        # Allergy risk flag (not raw allergy strings)
        allergy_risk = _assess_allergy_risk(entities.get("medications", []),
                                            entities.get("allergies", []))

        return jsonify({
            "success": True,
            "extraction": extraction_meta,
            "document_type": entities.get("document_type", "unknown"),
            "patient_info": entities.get("demographics", {}),
            "vitals": entities.get("vitals", {}),
            "labs": entities.get("labs", {}),
            "medications": entities.get("medications", []),
            "allergy_risk": allergy_risk,
            "abnormal_flags": entities.get("flagged_abnormals", []),
            "coding": coding_result,
            "drug_interactions": drug_interactions,
            "candidate_codes_searched": len(candidate_codes),
            "text_preview": text[:500] + "..." if len(text) > 500 else text,
        })

    except Exception as e:
        logger.exception(f"Analysis error: {e}")
        return jsonify({"error": str(e), "success": False}), 500


# ── PDF Report (subscription only) ───────────────────────────────────
@app.route('/api/report/download', methods=['POST'])
def download_report():
    from auth import require_subscription
    # Manual auth check (can't use decorator on route directly with require_subscription pattern)
    from auth import _extract_token, _verify_token, _get_db
    import time
    token = _extract_token()
    if not token:
        return jsonify({"error": "Authentication required"}), 401
    payload = _verify_token(token)
    if not payload:
        return jsonify({"error": "Invalid token"}), 401
    with _get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id=?", (payload['sub'],)).fetchone()
    if not user or not (user['is_subscribed'] and user['subscription_expires'] > int(time.time())):
        return jsonify({"error": "Active subscription required", "code": "SUBSCRIPTION_REQUIRED"}), 403

    try:
        data = request.get_json()
        analysis = data.get('analysis', {})
        from report_service import generate_pdf_report
        pdf_bytes = generate_pdf_report(analysis)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name='MedCode_Report.pdf'
        )
    except Exception as e:
        logger.exception(f"PDF generation error: {e}")
        return jsonify({"error": str(e)}), 500


# ── Email Results (subscription only) ────────────────────────────────
@app.route('/api/report/email', methods=['POST'])
def email_report():
    from auth import _extract_token, _verify_token, _get_db
    import time
    token = _extract_token()
    if not token:
        return jsonify({"error": "Authentication required"}), 401
    payload = _verify_token(token)
    if not payload:
        return jsonify({"error": "Invalid token"}), 401
    with _get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id=?", (payload['sub'],)).fetchone()
    if not user or not (user['is_subscribed'] and user['subscription_expires'] > int(time.time())):
        return jsonify({"error": "Active subscription required", "code": "SUBSCRIPTION_REQUIRED"}), 403

    try:
        data = request.get_json()
        to_email = data.get('email', user['email'])
        analysis = data.get('analysis', {})

        # Generate PDF attachment
        pdf_bytes = None
        try:
            from report_service import generate_pdf_report
            pdf_bytes = generate_pdf_report(analysis)
        except Exception as e:
            logger.warning(f"PDF for email failed: {e}")

        from email_service import send_results_email
        result = send_results_email(to_email, analysis, pdf_bytes)
        return jsonify(result)
    except Exception as e:
        logger.exception(f"Email error: {e}")
        return jsonify({"error": str(e)}), 500


# ── Code search ───────────────────────────────────────────────────────
@app.route('/api/search-codes', methods=['GET'])
def search_codes():
    icd_service, _, _ = get_services()
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 20)), 50)
    if not query:
        return jsonify({"results": [], "query": query})
    results = icd_service.search(query, top_k=limit)
    clean = [{k: v for k, v in r.items() if k != 'bm25_score'} for r in results]
    return jsonify({"results": clean, "query": query, "count": len(clean)})


@app.route('/api/code-info/<code>', methods=['GET'])
def code_info(code):
    icd_service, _, _ = get_services()
    entry = icd_service.validate_code(code)
    if entry:
        return jsonify(entry)
    return jsonify({"error": f"Code {code} not found"}), 404


# ── Helpers ───────────────────────────────────────────────────────────
def _assess_allergy_risk(medications: list, raw_allergies: list) -> dict:
    """
    Instead of showing raw allergy strings, return a structured risk assessment.
    """
    risks = []

    ALLERGY_DRUG_MAP = {
        "penicillin":    ["amoxicillin", "ampicillin", "piperacillin"],
        "sulfa":         ["trimethoprim", "sulfasalazine"],
        "nsaid":         ["ibuprofen", "naproxen", "diclofenac", "indomethacin", "ketorolac"],
        "aspirin":       ["aspirin", "clopidogrel"],
        "quinolone":     ["ciprofloxacin", "levofloxacin"],
        "cephalosporin": ["ceftriaxone", "cefixime"],
    }

    meds_lower = [m.lower() for m in medications]
    for allergy_class, drugs in ALLERGY_DRUG_MAP.items():
        for drug in drugs:
            if any(drug in m for m in meds_lower):
                risks.append({
                    "class": allergy_class.title(),
                    "drug_found": drug,
                    "note": f"Patient is prescribed {drug} — verify allergy history to {allergy_class}"
                })

    has_documented = bool(raw_allergies and
                         not all('nkda' in a.lower() or 'no known' in a.lower()
                                 for a in raw_allergies))

    return {
        "has_documented_allergy": has_documented,
        "cross_reactivity_risks": risks,
        "note": "Review allergy history before dispensing" if (has_documented or risks) else None
    }


def _build_search_queries(text: str, entities: dict) -> list:
    queries = [text[:600]]
    if entities.get("keywords"):
        queries.append(" ".join(entities["keywords"][:20]))

    MED_TO_CONDITION = {
        "metformin": "type 2 diabetes mellitus",
        "insulin": "diabetes mellitus",
        "levothyroxine": "hypothyroidism",
        "salbutamol": "asthma bronchospasm",
        "albuterol": "asthma bronchospasm",
        "furosemide": "heart failure edema",
        "lisinopril": "hypertension heart failure",
        "atorvastatin": "hyperlipidemia dyslipidemia",
        "warfarin": "anticoagulation atrial fibrillation",
        "methotrexate": "rheumatoid arthritis",
        "hydroxychloroquine": "lupus rheumatoid arthritis",
        "omeprazole": "GERD peptic ulcer",
        "pantoprazole": "GERD peptic ulcer",
        "sertraline": "depression anxiety",
        "fluoxetine": "depression anxiety",
        "amoxicillin": "bacterial infection",
        "prednisolone": "inflammatory condition",
        "ciprofloxacin": "bacterial infection UTI",
        "allopurinol": "gout hyperuricemia",
        "amlodipine": "hypertension",
        "aspirin": "coronary artery disease antiplatelet",
        "clopidogrel": "coronary artery disease antiplatelet",
        "digoxin": "atrial fibrillation heart failure",
    }
    for med in entities.get("medications", []):
        for k, cond in MED_TO_CONDITION.items():
            if k in med.lower():
                queries.append(cond)
                break

    vitals = entities.get("vitals", {})
    if "bp" in vitals:
        s = vitals["bp"]["systolic"]
        if s >= 140: queries.append("hypertension high blood pressure")
        elif s < 90: queries.append("hypotension shock")
    if "spo2" in vitals and vitals["spo2"] < 94:
        queries.append("hypoxemia respiratory failure")
    if "glucose" in vitals:
        g = vitals["glucose"]
        if g > 200: queries.append("diabetes hyperglycemia")
        elif g < 70: queries.append("hypoglycemia")

    labs = entities.get("labs", {})
    if "hba1c" in labs and labs["hba1c"] > 6.5:
        queries.append("diabetes mellitus type 2")
    if "hb" in labs and labs["hb"] < 10:
        queries.append("anemia low hemoglobin")
    if "creatinine" in labs and labs["creatinine"] > 1.5:
        queries.append("chronic kidney disease renal impairment")
    if "tsh" in labs:
        if labs["tsh"] > 4.5: queries.append("hypothyroidism")
        elif labs["tsh"] < 0.3: queries.append("hyperthyroidism")
    if "troponin" in labs and labs["troponin"] > 0.04:
        queries.append("myocardial infarction acute coronary syndrome")
    if "wbc" in labs and labs["wbc"] > 11000:
        queries.append("leukocytosis infection sepsis")
    if "platelets" in labs and labs["platelets"] < 150000:
        queries.append("thrombocytopenia")

    return list(dict.fromkeys(q for q in queries if q and len(q.strip()) > 3))


if __name__ == '__main__':
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"🏥 MedCode AI v2 starting on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
