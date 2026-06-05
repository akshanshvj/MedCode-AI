"""
Email Service — sends coding results via Gmail SMTP.
Configure SMTP_USER and SMTP_PASS (Gmail App Password) in .env
"""
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime

logger = logging.getLogger(__name__)


def send_results_email(to_email: str, analysis_result: dict, pdf_bytes: bytes = None) -> dict:
    """
    Send coding results to user's email.
    Returns {"success": True} or {"success": False, "error": str}
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_pass:
        return {"success": False, "error": "Email not configured. Add SMTP_USER and SMTP_PASS to .env"}

    coding = analysis_result.get("coding", {})
    principal = coding.get("principal_diagnosis", {})
    secondary = coding.get("secondary_diagnoses", [])
    patient = analysis_result.get("patient_info", {})
    doc_type = analysis_result.get("document_type", "Medical Document").replace("_", " ").title()

    # ── Build HTML email ──────────────────────────────────────────────
    all_codes_html = ""
    if principal:
        conf = principal.get("confidence", "low")
        conf_color = {"high": "#10B981", "medium": "#F59E0B", "low": "#EF4444"}.get(conf, "#F59E0B")
        all_codes_html += f"""
        <div style="border:2px solid #0D9488;border-radius:8px;padding:16px;margin-bottom:12px;background:#0F2744;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="background:#0D9488;color:white;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold;">PRINCIPAL</span>
                <span style="color:{conf_color};font-size:12px;font-weight:bold;">{conf.upper()}</span>
            </div>
            <div style="margin-top:8px;">
                <span style="color:#2DD4BF;font-size:18px;font-weight:bold;font-family:monospace;">{principal.get('code','')}</span>
                <span style="color:#E2E8F0;font-size:14px;margin-left:12px;">{principal.get('description','')}</span>
            </div>
            {"<div style='margin-top:8px;color:#94A3B8;font-size:12px;'><b style='color:#2DD4BF;'>Justification:</b> " + principal.get('justification','') + "</div>" if principal.get('justification') else ""}
        </div>"""

    for code in secondary:
        conf = code.get("confidence", "low")
        conf_color = {"high": "#10B981", "medium": "#F59E0B", "low": "#EF4444"}.get(conf, "#F59E0B")
        all_codes_html += f"""
        <div style="border:1px solid #334155;border-radius:8px;padding:14px;margin-bottom:8px;background:#1E293B;">
            <div style="display:flex;justify-content:space-between;">
                <div>
                    <span style="color:#2DD4BF;font-size:16px;font-weight:bold;font-family:monospace;">{code.get('code','')}</span>
                    <span style="color:#E2E8F0;font-size:13px;margin-left:10px;">{code.get('description','')}</span>
                </div>
                <span style="color:{conf_color};font-size:11px;font-weight:bold;">{conf.upper()}</span>
            </div>
            {"<div style='margin-top:6px;color:#94A3B8;font-size:11px;'>" + code.get('justification','') + "</div>" if code.get('justification') else ""}
        </div>"""

    flags_html = ""
    for f in analysis_result.get("abnormal_flags", []):
        t = f.get("type", "INFO")
        color = {"CRITICAL": "#EF4444", "WARNING": "#F59E0B", "INFO": "#3B82F6"}.get(t, "#3B82F6")
        flags_html += f'<span style="background:{color}22;color:{color};border:1px solid {color};padding:3px 8px;border-radius:4px;font-size:11px;margin:2px;">{f.get("label","")} · {f.get("value","")}</span> '

    meds = analysis_result.get("medications", [])
    meds_html = "".join(f'<span style="background:#0D948822;color:#0D9488;border:1px solid #0D9488;padding:2px 8px;border-radius:12px;font-size:11px;margin:2px;">{m.title()}</span>' for m in meds) if meds else "<span style='color:#64748B;'>None detected</span>"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:'IBM Plex Sans',Arial,sans-serif;background:#0A0F1E;color:#E2E8F0;margin:0;padding:0;">
<div style="max-width:680px;margin:0 auto;padding:24px;">

  <!-- Header -->
  <div style="background:#0F172A;border-radius:12px;padding:24px;margin-bottom:20px;border:1px solid #1E293B;">
    <div style="font-size:24px;font-weight:bold;color:white;">🏥 MedCode AI</div>
    <div style="color:#2DD4BF;font-size:13px;margin-top:4px;">ICD-10-CM Clinical Coding Report</div>
    <div style="color:#64748B;font-size:12px;margin-top:2px;">{datetime.now().strftime('%d %B %Y, %I:%M %p')}</div>
  </div>

  <!-- Meta -->
  <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;">
    <div style="background:#1E293B;padding:10px 16px;border-radius:8px;border:1px solid #334155;">
      <div style="color:#64748B;font-size:10px;text-transform:uppercase;font-weight:bold;">Document</div>
      <div style="color:#E2E8F0;font-size:13px;margin-top:2px;">{doc_type}</div>
    </div>
    <div style="background:#1E293B;padding:10px 16px;border-radius:8px;border:1px solid #334155;">
      <div style="color:#64748B;font-size:10px;text-transform:uppercase;font-weight:bold;">Patient</div>
      <div style="color:#E2E8F0;font-size:13px;margin-top:2px;">{patient.get('age','—')}y {patient.get('gender','').title()}</div>
    </div>
    <div style="background:#1E293B;padding:10px 16px;border-radius:8px;border:1px solid #334155;">
      <div style="color:#64748B;font-size:10px;text-transform:uppercase;font-weight:bold;">Codes Found</div>
      <div style="color:#2DD4BF;font-size:16px;font-weight:bold;margin-top:2px;">{coding.get('total_codes',0)}</div>
    </div>
  </div>

  <!-- Abnormal Flags -->
  {f'<div style="background:#1E293B;border-radius:8px;padding:14px;margin-bottom:16px;border:1px solid #334155;"><div style="color:#F59E0B;font-weight:bold;margin-bottom:8px;">⚡ Clinical Alerts</div>{flags_html}</div>' if flags_html else ''}

  <!-- Codes -->
  <div style="margin-bottom:20px;">
    <div style="color:#2DD4BF;font-size:16px;font-weight:bold;margin-bottom:12px;">ICD-10-CM Codes</div>
    {all_codes_html}
  </div>

  <!-- Medications -->
  <div style="background:#1E293B;border-radius:8px;padding:14px;margin-bottom:16px;border:1px solid #334155;">
    <div style="color:#E2E8F0;font-weight:bold;margin-bottom:8px;">💊 Medications</div>
    {meds_html}
  </div>

  <!-- Coding Summary -->
  {f'<div style="background:#1E293B;border-radius:8px;padding:14px;margin-bottom:16px;border:1px solid #334155;"><div style="color:#E2E8F0;font-weight:bold;margin-bottom:8px;">📝 Coding Summary</div><div style="color:#94A3B8;font-size:13px;line-height:1.6;">' + coding.get("coding_summary","") + '</div></div>' if coding.get("coding_summary") else ''}

  <!-- Disclaimer -->
  <div style="border-top:1px solid #1E293B;padding-top:16px;margin-top:16px;">
    <p style="color:#475569;font-size:11px;line-height:1.6;">⚕️ This report is for coding assistance only. All ICD-10-CM codes must be verified by a certified medical coder. Not a substitute for professional clinical judgment.</p>
    <p style="color:#334155;font-size:10px;">Generated by MedCode AI</p>
  </div>
</div>
</body>
</html>"""

    # ── Send email ────────────────────────────────────────────────────
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"MedCode AI — Coding Report ({doc_type})"
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))

        if pdf_bytes:
            pdf_part = MIMEApplication(pdf_bytes, Name="MedCode_Report.pdf")
            pdf_part['Content-Disposition'] = 'attachment; filename="MedCode_Report.pdf"'
            msg.attach(pdf_part)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())

        logger.info(f"Report emailed to {to_email}")
        return {"success": True}

    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "Email authentication failed. Check SMTP_USER and SMTP_PASS in .env"}
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return {"success": False, "error": str(e)}
