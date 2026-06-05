"""
PDF Report Generation Service.
Generates a detailed, professionally formatted medical coding report.
Requires reportlab: pip install reportlab
"""
import io
import os
from datetime import datetime

def generate_pdf_report(analysis_result: dict, patient_name: str = "Patient") -> bytes:
    """Generate a detailed PDF report from analysis result. Returns bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import (
        HexColor, white, black, Color
    )
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    buffer = io.BytesIO()

    # ── Colors ──────────────────────────────────────────────────────
    TEAL      = HexColor("#0D9488")
    NAVY      = HexColor("#0F172A")
    SLATE     = HexColor("#1E293B")
    LIGHT_BG  = HexColor("#F8FAFC")
    BORDER    = HexColor("#CBD5E1")
    RED       = HexColor("#EF4444")
    AMBER     = HexColor("#F59E0B")
    GREEN     = HexColor("#10B981")
    GRAY      = HexColor("#64748B")
    WHITE     = white

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
        title="MedCode AI — Clinical Coding Report"
    )

    styles = getSampleStyleSheet()

    # Custom styles
    def s(name, **kw):
        return ParagraphStyle(name, **kw)

    H1 = s("H1", fontSize=22, textColor=WHITE, fontName="Helvetica-Bold",
            spaceAfter=4, leading=26)
    H2 = s("H2", fontSize=14, textColor=TEAL, fontName="Helvetica-Bold",
            spaceAfter=6, spaceBefore=14, leading=18)
    H3 = s("H3", fontSize=11, textColor=NAVY, fontName="Helvetica-Bold",
            spaceAfter=4, leading=14)
    BODY = s("BODY", fontSize=9.5, textColor=NAVY, fontName="Helvetica",
             spaceAfter=4, leading=14)
    SMALL = s("SMALL", fontSize=8.5, textColor=GRAY, fontName="Helvetica",
              spaceAfter=3, leading=12)
    CODE_STYLE = s("CODE", fontSize=13, textColor=TEAL, fontName="Helvetica-Bold",
                   spaceAfter=2, leading=16)
    ITALIC = s("ITALIC", fontSize=9, textColor=GRAY, fontName="Helvetica-Oblique",
               spaceAfter=4, leading=12)

    W = A4[0] - 4*cm  # content width
    story = []

    # ── HEADER BANNER ─────────────────────────────────────────────────
    header_data = [[
        Paragraph("🏥  MedCode AI", H1),
        Paragraph(f"<font color='#94A3B8' size='9'>ICD-10-CM Clinical Coding Report<br/>"
                  f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}</font>",
                  s("hdr_sub", fontSize=9, textColor=HexColor("#94A3B8"),
                    fontName="Helvetica", leading=14, alignment=TA_RIGHT))
    ]]
    header_tbl = Table(header_data, colWidths=[W*0.6, W*0.4])
    header_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY),
        ('ROWPADDING', (0,0), (-1,-1), 14),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [6,6,6,6]),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── DOCUMENT META ─────────────────────────────────────────────────
    doc_type = analysis_result.get("document_type", "Medical Document").replace("_", " ").title()
    patient = analysis_result.get("patient_info", {})
    extraction = analysis_result.get("extraction", {})
    coding = analysis_result.get("coding", {})

    meta_items = [
        ["Document Type",   doc_type],
        ["Patient",         f"{patient.get('age', '—')}y {patient.get('gender', '').title()}"],
        ["OCR Confidence",  f"{int(extraction.get('ocr_confidence', 1)*100)}%"],
        ["Codes Found",     str(coding.get('total_codes', 0))],
        ["Verification",    "✓ All codes verified" if coding.get('all_verified') else "⚠ Review required"],
    ]
    meta_data = [[
        Paragraph(k, s("mk", fontSize=8, textColor=GRAY, fontName="Helvetica-Bold", leading=11)),
        Paragraph(v, s("mv", fontSize=9, textColor=NAVY, fontName="Helvetica", leading=12))
    ] for k, v in meta_items]

    meta_tbl = Table(meta_data, colWidths=[W*0.25, W*0.25]*2 if False else [W/len(meta_items)]*len(meta_items),
                     colWidths=[3*cm, 3*cm, 3*cm, 2.5*cm, 4*cm])
    meta_tbl = Table([[
        Paragraph(f"<b>{k}</b><br/><font color='#0F172A' size='9'>{v}</font>",
                  s("mt", fontSize=8, textColor=GRAY, fontName="Helvetica",
                    leading=13, spaceAfter=0))
        for k, v in meta_items
    ]], colWidths=[3*cm, 3.2*cm, 2.8*cm, 2.5*cm, 3.5*cm])
    meta_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.3, BORDER),
        ('ROWPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 0.5*cm))

    # ── PRINCIPAL DIAGNOSIS ───────────────────────────────────────────
    principal = coding.get("principal_diagnosis")
    if principal:
        story.append(Paragraph("Principal Diagnosis", H2))
        _add_code_block(story, principal, True, W, TEAL, NAVY, LIGHT_BG, BORDER, GRAY,
                        CODE_STYLE, H3, BODY, SMALL, ITALIC)
        story.append(Spacer(1, 0.3*cm))

    # ── SECONDARY DIAGNOSES ───────────────────────────────────────────
    secondary = coding.get("secondary_diagnoses", [])
    if secondary:
        story.append(Paragraph(f"Secondary Diagnoses ({len(secondary)} codes)", H2))
        for code in secondary:
            _add_code_block(story, code, False, W, TEAL, NAVY, LIGHT_BG, BORDER, GRAY,
                            CODE_STYLE, H3, BODY, SMALL, ITALIC)
            story.append(Spacer(1, 0.2*cm))

    # ── VITALS & LABS ─────────────────────────────────────────────────
    vitals = analysis_result.get("vitals", {})
    labs = analysis_result.get("labs", {})
    if vitals or labs:
        story.append(Paragraph("Extracted Clinical Values", H2))
        rows = []
        if "bp" in vitals:
            rows.append(["Blood Pressure", f"{vitals['bp']['systolic']}/{vitals['bp']['diastolic']} mmHg"])
        for k, label in [("hr","Heart Rate"),("temp","Temperature"),("spo2","SpO₂"),
                         ("glucose","Glucose"),("weight","Weight"),("bmi","BMI")]:
            if k in vitals:
                rows.append([label, str(vitals[k])])
        lab_labels = {"hb":"Hemoglobin","wbc":"WBC","platelets":"Platelets",
                      "creatinine":"Creatinine","hba1c":"HbA1c","egfr":"eGFR",
                      "sodium":"Sodium","potassium":"Potassium","alt":"ALT",
                      "ast":"AST","tsh":"TSH","troponin":"Troponin",
                      "cholesterol":"Cholesterol","ldl":"LDL","hdl":"HDL",
                      "triglycerides":"Triglycerides","inr":"INR","crp":"CRP"}
        for k, label in lab_labels.items():
            if k in labs:
                rows.append([label, str(labs[k])])

        if rows:
            # 2-column layout
            paired = []
            for i in range(0, len(rows), 2):
                row1 = rows[i]
                row2 = rows[i+1] if i+1 < len(rows) else ["", ""]
                paired.append([
                    Paragraph(row1[0], s("vl", fontSize=8, textColor=GRAY, fontName="Helvetica-Bold", leading=11)),
                    Paragraph(row1[1], s("vv", fontSize=9, textColor=NAVY, fontName="Helvetica-Bold", leading=12)),
                    Paragraph(row2[0], s("vl2", fontSize=8, textColor=GRAY, fontName="Helvetica-Bold", leading=11)),
                    Paragraph(row2[1], s("vv2", fontSize=9, textColor=NAVY, fontName="Helvetica-Bold", leading=12)),
                ])
            vt = Table(paired, colWidths=[W*0.2, W*0.3, W*0.2, W*0.3])
            vt.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
                ('BOX', (0,0), (-1,-1), 0.5, BORDER),
                ('INNERGRID', (0,0), (-1,-1), 0.3, BORDER),
                ('ROWPADDING', (0,0), (-1,-1), 6),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(vt)
        story.append(Spacer(1, 0.3*cm))

    # ── MEDICATIONS ───────────────────────────────────────────────────
    meds = analysis_result.get("medications", [])
    if meds:
        story.append(Paragraph("Medications Identified", H2))
        med_text = "  ·  ".join(m.title() for m in meds)
        story.append(Paragraph(med_text, BODY))
        story.append(Spacer(1, 0.2*cm))

    # ── DRUG INTERACTIONS ─────────────────────────────────────────────
    interactions = analysis_result.get("drug_interactions", [])
    if interactions:
        story.append(Paragraph("⚠️  Drug Interaction Alerts", H2))
        for ia in interactions:
            sev = ia.get('severity', 'MODERATE')
            color = RED if sev == 'CONTRAINDICATED' else (AMBER if sev == 'MAJOR' else HexColor("#F97316"))
            row_data = [[
                Paragraph(f"<b>{sev}</b>", s("sev", fontSize=9, textColor=color,
                          fontName="Helvetica-Bold", leading=12)),
                Paragraph(f"<b>{' + '.join(ia.get('drugs', []))}</b><br/>"
                          f"<font size='8' color='#374151'>{ia.get('message', '')}</font><br/>"
                          f"<font size='8' color='#DC2626'><i>{ia.get('action', '')}</i></font>",
                          s("iad", fontSize=9, textColor=NAVY, fontName="Helvetica", leading=13))
            ]]
            it = Table(row_data, colWidths=[2.5*cm, W-2.5*cm])
            it.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
                ('BOX', (0,0), (-1,-1), 1, color),
                ('ROWPADDING', (0,0), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            story.append(it)
            story.append(Spacer(1, 0.15*cm))

    # ── ABNORMAL FLAGS ────────────────────────────────────────────────
    flags = analysis_result.get("abnormal_flags", [])
    if flags:
        story.append(Paragraph("Clinical Alerts", H2))
        flag_rows = []
        for f in flags:
            t = f.get('type', 'INFO')
            c = RED if t == 'CRITICAL' else (AMBER if t == 'WARNING' else HexColor("#3B82F6"))
            flag_rows.append([
                Paragraph(t, s("ft", fontSize=8, textColor=c, fontName="Helvetica-Bold", leading=11)),
                Paragraph(f.get('label', ''), s("fl", fontSize=9, textColor=NAVY, fontName="Helvetica-Bold", leading=12)),
                Paragraph(f.get('value', ''), s("fv", fontSize=9, textColor=GRAY, fontName="Helvetica", leading=12)),
            ])
        ft = Table(flag_rows, colWidths=[2.5*cm, W*0.5, W*0.3])
        ft.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
            ('BOX', (0,0), (-1,-1), 0.5, BORDER),
            ('INNERGRID', (0,0), (-1,-1), 0.3, BORDER),
            ('ROWPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(ft)
        story.append(Spacer(1, 0.3*cm))

    # ── CODING SUMMARY ────────────────────────────────────────────────
    if coding.get("coding_summary"):
        story.append(Paragraph("Coding Summary", H2))
        story.append(Paragraph(coding["coding_summary"], BODY))

    if coding.get("documentation_gaps"):
        story.append(Paragraph("Documentation Gaps", H3))
        for gap in coding["documentation_gaps"]:
            story.append(Paragraph(f"• {gap}", BODY))

    if coding.get("query_for_physician"):
        story.append(Paragraph("Clinical Query for Physician", H3))
        story.append(Paragraph(coding["query_for_physician"], BODY))

    # ── DISCLAIMER ────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "⚕️  DISCLAIMER: This report is generated by MedCode AI for coding assistance only. "
        "All ICD-10-CM codes must be reviewed and verified by a certified medical coder (CCS/CPC). "
        "Not a substitute for professional clinical or coding judgment.",
        s("disc", fontSize=7.5, textColor=GRAY, fontName="Helvetica-Oblique", leading=11)
    ))

    doc.build(story)
    return buffer.getvalue()


def _add_code_block(story, code_data, is_principal, W,
                    TEAL, NAVY, LIGHT_BG, BORDER, GRAY,
                    CODE_STYLE, H3, BODY, SMALL, ITALIC):
    """Add a single formatted code card to the story."""
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.colors import HexColor

    conf = code_data.get("confidence", "medium")
    conf_color = {"high": HexColor("#10B981"), "medium": HexColor("#F59E0B"),
                  "low": HexColor("#EF4444")}.get(conf, HexColor("#F59E0B"))

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    header_content = [
        [
            Paragraph(
                f"<font color='#0D9488' size='13'><b>{code_data.get('code','')}</b></font>  "
                f"<font color='#0F172A' size='10'>{code_data.get('description','')}</font>",
                ps("ch", fontSize=10, textColor=NAVY, fontName="Helvetica", leading=16)
            ),
            Paragraph(
                f"<font color='#{conf_color.hexval()[2:]}' size='8'><b>{conf.upper()}</b></font>"
                f"<br/><font size='7' color='#64748B'>{code_data.get('chapter','')} · {code_data.get('category','')}</font>",
                ps("cc", fontSize=8, textColor=GRAY, fontName="Helvetica", leading=12,
                   alignment=1)  # right
            ),
        ]
    ]
    line_color = TEAL if is_principal else HexColor("#334155")
    header_tbl = Table(header_content, colWidths=[W*0.75, W*0.25])
    header_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor("#0F2744") if is_principal else LIGHT_BG),
        ('BOX', (0,0), (-1,-1), 1.5 if is_principal else 0.5, line_color),
        ('ROWPADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(header_tbl)

    # Justification + notes
    if code_data.get("justification") or code_data.get("coding_notes"):
        detail_rows = []
        if code_data.get("justification"):
            detail_rows.append([
                Paragraph("Clinical Justification",
                          ps("jh", fontSize=8, textColor=TEAL, fontName="Helvetica-Bold", leading=11)),
                Paragraph(code_data["justification"],
                          ps("jb", fontSize=9, textColor=NAVY, fontName="Helvetica", leading=13))
            ])
        if code_data.get("coding_notes"):
            detail_rows.append([
                Paragraph("Coding Notes",
                          ps("nh", fontSize=8, textColor=HexColor("#3B82F6"),
                             fontName="Helvetica-Bold", leading=11)),
                Paragraph(code_data["coding_notes"],
                          ps("nb", fontSize=9, textColor=GRAY, fontName="Helvetica", leading=13))
            ])
        dt = Table(detail_rows, colWidths=[3*cm, W-3*cm])
        dt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), HexColor("#F8FAFC")),
            ('BOX', (0,0), (-1,-1), 0.5, HexColor("#CBD5E1")),
            ('INNERGRID', (0,0), (-1,-1), 0.3, HexColor("#E2E8F0")),
            ('ROWPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(dt)
