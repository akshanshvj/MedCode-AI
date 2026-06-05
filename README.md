# MedCode AI v2 — Quick Start

## Prerequisites
- Python 3.9+ (recommended), Node.js 18+
- Tesseract OCR installed
- Groq API key (free): https://console.groq.com

## Run in 5 minutes

### 1. Backend
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

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**

---

## Feature Setup

### Payments (Razorpay ₹1)
1. Sign up free at https://razorpay.com
2. Dashboard → Settings → API Keys → **Test Mode**
3. Add to `.env`:
   ```
   RAZORPAY_KEY_ID=rzp_test_xxxxxx
   RAZORPAY_KEY_SECRET=xxxxxx
   ```
4. Test card: `4111 1111 1111 1111` | CVV: `123` | Expiry: any future date

> Without Razorpay keys, the app runs in **demo mode** — subscription activates instantly for testing.

### Email Results
1. Gmail → My Account → Security → 2-Step Verification → App Passwords
2. Create app password for "Mail"
3. Add to `.env`:
   ```
   SMTP_USER=your@gmail.com
   SMTP_PASS=your16charpassword
   ```

### WhatsApp Sharing
Works automatically — no setup needed.

---

## What's in v2

| Feature | Free | Pro (₹1/mo) |
|---------|------|-------------|
| ICD-10 code extraction | ✅ | ✅ |
| Drug interaction alerts | ✅ | ✅ |
| Abnormal value flagging | ✅ | ✅ |
| Allergy risk assessment | ✅ | ✅ |
| TSV export | ✅ | ✅ |
| PDF detailed report | ❌ | ✅ |
| Email results | ❌ | ✅ |
| WhatsApp share | ❌ | ✅ |
