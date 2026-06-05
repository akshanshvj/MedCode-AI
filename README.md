# MedCode AI v2 — Intelligent Medical Coding Assistant

MedCode AI is an advanced AI-powered tool designed to automate and enhance medical coding workflows. It processes medical reports using OCR and Large Language Models (LLMs) to accurately extract relevant medical data and provide actionable insights.

## Core Features
- **ICD-10 Code Extraction**: Automatically identifies and maps diagnoses to accurate ICD-10 codes.
- **Drug Interaction Alerts**: Flags potential adverse interactions between prescribed medications.
- **Abnormal Value Flagging**: Highlights lab results and vitals that fall outside normal reference ranges.
- **Allergy Risk Assessment**: Identifies patient allergies and cross-references them against current medications.
- **TSV Export**: Easily export extracted structured data for integration with EHR/EMR systems.

## Prerequisites
- Python 3.9+ (recommended), Node.js 18+
- Tesseract OCR installed
- Groq API key (free): https://console.groq.com

## Run in 5 minutes

### 1. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# OR: source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt

# If Python 3.14: fix tesseract compatibility
python ..\fix_python314.py

copy .env.example .env         # Windows
# OR: cp .env.example .env     # Mac/Linux
# → Edit .env and add your GROQ_API_KEY

python app.py
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** in your browser.

---

*Note: This application also includes extended modules like Razorpay subscription integration, Email reporting, and WhatsApp sharing. These are optional, and the core application will run seamlessly in demo mode if their respective API keys are not provided.*
