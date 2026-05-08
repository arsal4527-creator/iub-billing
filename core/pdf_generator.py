import os
import re
import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")

IUB_GREEN = colors.HexColor("#1a5276")
IUB_LIGHT = colors.HexColor("#d6eaf8")
IUB_GOLD  = colors.HexColor("#b7950b")

ROLE_SHORT = {
    "Superintendent":          "Supt",
    "Deputy Superintendent":   "DySupt",
    "Resident Inspector":      "RI",
    "Distributing Inspector":  "DI",
    "Member Inspection Squad": "MIS",
    "Invigilator":             "Invg",
    "Paper Checker":           "PC",
}


def _make_filename(prefix, role, full_name, cnic):
    short     = ROLE_SHORT.get(role, re.sub(r'[^A-Za-z0-9]', '', role)[:6])
    name_part = re.sub(r'[^A-Za-z0-9_\-]', '', full_name.replace(" ", "_"))
    return f"{prefix}_{short}_{name_part}_{cnic}.pdf"


def _output_path(filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, filename)


def _base_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("IUBTitle",    fontName="Helvetica-Bold",  fontSize=14, alignment=TA_CENTER, spaceAfter=2))
    styles.add(ParagraphStyle("IUBSub",      fontName="Helvetica-Bold",  fontSize=11, alignment=TA_CENTER, spaceAfter=2))
    styles.add(ParagraphStyle("IUBSmall",    fontName="Helvetica",       fontSize=9,  alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle("BillTitle",   fontName="Helvetica-Bold",  fontSize=12, alignment=TA_CENTER, spaceAfter=6, textColor=IUB_GREEN))
    styles.add(ParagraphStyle("FieldLabel",  fontName="Helvetica-Bold",  fontSize=9,  spaceBefore=2))
    styles.add(ParagraphStyle("FieldValue",  fontName="Helvetica",       fontSize=9))
    styles.add(ParagraphStyle("SmallNote",   fontName="Helvetica",       fontSize=8,  textColor=colors.grey))
    styles.add(ParagraphStyle("SignLabel",   fontName="Helvetica-Bold",  fontSize=9,  alignment=TA_CENTER))
    styles.add(ParagraphStyle("CenterNorm",  fontName="Helvetica",       fontSize=9,  alignment=TA_CENTER))
    styles.add(ParagraphStyle("RightNorm",   fontName="Helvetica",       fontSize=9,  alignment=TA_RIGHT))
    return styles


def _header(styles):
    elements = []
    elements.append(Paragraph("The Islamia University of Bahawalpur", styles["IUBTitle"]))
    elements.append(Paragraph("EXAMINATIONS DEPARTMENT", styles["IUBSub"]))
    elements.append(Paragraph("Examinations Branch — Billing Section", styles["IUBSmall"]))
    elements.append(HRFlowable(width="100%", thickness=2, color=IUB_GREEN))
    elements.append(Spacer(1, 0.3*cm))
    return elements


def _info_table(bill_data, appt, session_name, styles):
    rows = [
        [Paragraph("<b>Bill No.:</b>",         styles["FieldLabel"]), Paragraph(bill_data.get("bill_no",""), styles["FieldValue"]),
         Paragraph("<b>Date of Bill:</b>",      styles["FieldLabel"]), Paragraph(datetime.now().strftime("%d-%m-%Y"), styles["FieldValue"])],
        [Paragraph("<b>Name:</b>",              styles["FieldLabel"]), Paragraph(appt.get("full_name",""), styles["FieldValue"]),
         Paragraph("<b>Phone:</b>",             styles["FieldLabel"]), Paragraph(appt.get("phone","") or "—", styles["FieldValue"])],
        [Paragraph("<b>Designation:</b>",       styles["FieldLabel"]), Paragraph(appt.get("designation","") or "—", styles["FieldValue"]),
         Paragraph("<b>CNIC:</b>",              styles["FieldLabel"]), Paragraph(appt.get("cnic",""), styles["FieldValue"])],
        [Paragraph("<b>Institution:</b>",       styles["FieldLabel"]), Paragraph(appt.get("institution","") or "—", styles["FieldValue"]),
         Paragraph("<b>Centre:</b>",            styles["FieldLabel"]), Paragraph(appt.get("centre","") or "—", styles["FieldValue"])],
        [Paragraph("<b>Examination:</b>",       styles["FieldLabel"]), Paragraph(session_name, styles["FieldValue"]),
         Paragraph("<b>Letter No. & Date:</b>", styles["FieldLabel"]),
         Paragraph(f"{appt.get('letter_no','')} / {appt.get('letter_date','')}", styles["FieldValue"])],
    ]
    t = Table(rows, colWidths=[3.2*cm, 7*cm, 3.2*cm, 5.6*cm])
    t.setStyle(TableStyle([
        ("VALIGN",    (0,0),(-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,0),(-1,-1), [IUB_LIGHT, colors.white]),
        ("TOPPADDING",  (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING", (0,0),(-1,-1), 4),
    ]))
    return t


def _duty_table(duties, styles):
    header = [
        Paragraph("<b>Date</b>",    styles["SignLabel"]),
        Paragraph("<b>Session</b>", styles["SignLabel"]),
        Paragraph("<b>Type</b>",    styles["SignLabel"]),
        Paragraph("<b>Details</b>", styles["SignLabel"]),
    ]
    rows = [header]
    for d in duties:
        rows.append([
            Paragraph(d.get("duty_date",""), styles["FieldValue"]),
            Paragraph(d.get("session",""),   styles["FieldValue"]),
            Paragraph(d.get("session_type",""), styles["FieldValue"]),
            Paragraph(f"{d.get('session_type','')} — {d.get('session','')} Session", styles["FieldValue"]),
        ])
    t = Table(rows, colWidths=[3.5*cm, 3*cm, 3*cm, 9.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0), IUB_GREEN),
        ("TEXTCOLOR",    (0,0),(-1,0), colors.white),
        ("GRID",         (0,0),(-1,-1), 0.5, colors.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, IUB_LIGHT]),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
    ]))
    return t


def _calc_table_inspector(singles, doubles, rate_single, rate_double, amount, styles):
    rows = [
        [Paragraph("<b>Description</b>", styles["SignLabel"]),
         Paragraph("<b>Qty</b>",         styles["SignLabel"]),
         Paragraph("<b>Rate (Rs.)</b>",  styles["SignLabel"]),
         Paragraph("<b>Amount (Rs.)</b>",styles["SignLabel"])],
        [Paragraph("Single Sessions", styles["FieldValue"]),
         Paragraph(str(singles),      styles["CenterNorm"]),
         Paragraph(f"{rate_single:,.0f}", styles["CenterNorm"]),
         Paragraph(f"{singles*rate_single:,.0f}", styles["RightNorm"])],
        [Paragraph("Double Sessions", styles["FieldValue"]),
         Paragraph(str(doubles),      styles["CenterNorm"]),
         Paragraph(f"{rate_double:,.0f}", styles["CenterNorm"]),
         Paragraph(f"{doubles*rate_double:,.0f}", styles["RightNorm"])],
        [Paragraph("<b>TOTAL</b>",    styles["FieldLabel"]),
         Paragraph("",                styles["CenterNorm"]),
         Paragraph("",                styles["CenterNorm"]),
         Paragraph(f"<b>Rs. {amount:,.0f}/-</b>", styles["RightNorm"])],
    ]
    t = Table(rows, colWidths=[8*cm, 3*cm, 3.5*cm, 4.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0), IUB_GREEN),
        ("TEXTCOLOR",    (0,0),(-1,0), colors.white),
        ("GRID",         (0,0),(-1,-1), 0.5, colors.grey),
        ("BACKGROUND",   (0,-1),(-1,-1), IUB_LIGHT),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
    ]))
    return t


def _signature_block(styles):
    rows = [[
        Paragraph("________________________\nSignature of Claimant", styles["CenterNorm"]),
        Paragraph("________________________\nController of Examinations", styles["CenterNorm"]),
    ]]
    t = Table(rows, colWidths=[9.5*cm, 9.5*cm])
    t.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),20),("ALIGN",(0,0),(-1,-1),"CENTER")]))
    return t


def _approval_block(styles):
    headers = ["Controller of Examinations", "Accounts Branch\n(Asst/Deputy/Treasurer)", "Audit Branch", "Cheque Section"]
    row = [[Paragraph(f"________________________\n{h}", styles["CenterNorm"]) for h in headers]]
    t = Table(row, colWidths=[4.75*cm]*4)
    t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.5,colors.grey),
        ("GRID",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("TOPPADDING",(0,0),(-1,-1),20),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
    ]))
    return t


# ── PDF Type 1: Inspector Bill ─────────────────────────────────────────────────

def generate_inspector_bill(bill_data, appt, duties, session_name):
    role = appt.get("role","")
    path = _output_path(_make_filename("Bill", role, appt.get("full_name",""), appt.get("cnic","")))
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = _base_styles()
    elems = _header(styles)
    elems.append(Paragraph(f"BILL OF {role.upper()}", styles["BillTitle"]))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(_info_table(bill_data, appt, session_name, styles))
    elems.append(Spacer(1, 0.4*cm))
    elems.append(Paragraph("DUTY DETAILS", styles["IUBSub"]))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(_duty_table(duties, styles))
    elems.append(Spacer(1, 0.4*cm))
    singles = bill_data.get("total_days", 0)
    doubles = bill_data.get("total_double", 0)
    elems.append(_calc_table_inspector(singles, doubles, bill_data["rate_single"], bill_data["rate_double"], bill_data["amount"], styles))
    elems.append(Spacer(1, 0.3*cm))
    amount = bill_data["amount"]
    elems.append(Paragraph(f"<b>Pay Rupees: Rs. {amount:,.0f}/-</b>", styles["BillTitle"]))
    elems.append(Spacer(1, 0.4*cm))
    elems.append(Paragraph(
        "I certify that I have conducted the Inspection/Distribution work during the period cited above.",
        styles["FieldValue"]
    ))
    elems.append(Spacer(1, 0.6*cm))
    elems.append(_signature_block(styles))
    elems.append(Spacer(1, 0.6*cm))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(Paragraph("FOR OFFICE USE ONLY", styles["IUBSmall"]))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(_approval_block(styles))
    doc.build(elems)
    return path


# ── PDF Type 2: Superintendent Contingent Bill ────────────────────────────────

def generate_superintendent_bill(bill_data, appt, duties, session_name, extra_items):
    path = _output_path(_make_filename("Bill", appt.get("role",""), appt.get("full_name",""), appt.get("cnic","")))
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = _base_styles()
    elems = _header(styles)
    elems.append(Paragraph("SUPERINTENDENT CONTINGENT BILL", styles["BillTitle"]))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(_info_table(bill_data, appt, session_name, styles))
    elems.append(Spacer(1, 0.4*cm))
    elems.append(Paragraph("DUTY DETAILS", styles["IUBSub"]))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(_duty_table(duties, styles))
    elems.append(Spacer(1, 0.4*cm))

    singles = bill_data.get("total_days", 0)
    doubles = bill_data.get("total_double", 0)
    remuneration = (singles * bill_data["rate_single"]) + (doubles * bill_data["rate_double"])
    ei = extra_items or {}

    def rs(v): return f"Rs. {float(v or 0):,.0f}" if v else "—"

    contingent_rows = [
        [Paragraph("<b>#</b>", styles["SignLabel"]),
         Paragraph("<b>Description</b>", styles["SignLabel"]),
         Paragraph("<b>Amount (Rs.)</b>", styles["SignLabel"])],
        ["1", Paragraph(f"Superintendent Remuneration ({singles} Single × {bill_data['rate_single']:,.0f} + {doubles} Double × {bill_data['rate_double']:,.0f})", styles["FieldValue"]),
         Paragraph(f"{remuneration:,.0f}", styles["RightNorm"])],
        ["2", Paragraph("Collection of Question Papers", styles["FieldValue"]),
         Paragraph(rs(ei.get("collection_qp",0)), styles["RightNorm"])],
        ["3", Paragraph("Dispatch of Answer Books", styles["FieldValue"]),
         Paragraph(rs(ei.get("dispatch_ab",0)), styles["RightNorm"])],
        ["4", Paragraph("Menial Establishment", styles["FieldValue"]),
         Paragraph(rs(ei.get("menial",0)), styles["RightNorm"])],
        ["5", Paragraph("Stationery for Centre", styles["FieldValue"]),
         Paragraph(rs(ei.get("stationery",0)), styles["RightNorm"])],
        ["6", Paragraph("Ice for Centre", styles["FieldValue"]),
         Paragraph(rs(ei.get("ice",0)), styles["RightNorm"])],
        ["", Paragraph("<b>GROSS TOTAL</b>", styles["FieldLabel"]),
         Paragraph(f"<b>{ei.get('gross', remuneration):,.0f}</b>", styles["RightNorm"])],
        ["", Paragraph("Less: Advance Already Paid", styles["FieldValue"]),
         Paragraph(rs(ei.get("advance",0)), styles["RightNorm"])],
        ["", Paragraph("<b>NET PAYABLE</b>", styles["FieldLabel"]),
         Paragraph(f"<b>Rs. {bill_data['amount']:,.0f}/-</b>", styles["RightNorm"])],
    ]
    t = Table(contingent_rows, colWidths=[1*cm, 13*cm, 5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), IUB_GREEN),
        ("TEXTCOLOR",     (0,0),(-1,0), colors.white),
        ("GRID",          (0,0),(-1,-1), 0.5, colors.grey),
        ("BACKGROUND",    (0,-1),(-1,-1), IUB_LIGHT),
        ("FONTNAME",      (0,-1),(-1,-1), "Helvetica-Bold"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph(
        "<b>NOTE:</b> NTN status (ACTIVE or INACTIVE) is mandatory. Tax deduction applies if inactive.",
        styles["SmallNote"]
    ))
    elems.append(Spacer(1, 0.6*cm))
    elems.append(_signature_block(styles))
    elems.append(Spacer(1, 0.6*cm))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(Paragraph("FOR OFFICE USE ONLY", styles["IUBSmall"]))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(_approval_block(styles))
    doc.build(elems)
    return path


# ── PDF Type 3: Form 95-A (Invigilator / Deputy Superintendent) ───────────────

def generate_form95a_bill(bill_data, appt, duties, session_name):
    path = _output_path(_make_filename("Bill", appt.get("role",""), appt.get("full_name",""), appt.get("cnic","")))
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = _base_styles()
    elems = _header(styles)
    elems.append(Paragraph("INVIGILATOR / DEPUTY SUPERINTENDENT BILL (Form No. 95-A)", styles["BillTitle"]))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(_info_table(bill_data, appt, session_name, styles))
    elems.append(Spacer(1, 0.4*cm))

    header = [
        Paragraph("<b>Date</b>",           styles["SignLabel"]),
        Paragraph("<b>Session</b>",        styles["SignLabel"]),
        Paragraph("<b>Type</b>",           styles["SignLabel"]),
        Paragraph("<b>No. of Candidates</b>", styles["SignLabel"]),
        Paragraph("<b>Remarks</b>",        styles["SignLabel"]),
    ]
    rows = [header]
    for d in duties:
        rows.append([
            Paragraph(d.get("duty_date",""),     styles["FieldValue"]),
            Paragraph(d.get("session",""),       styles["FieldValue"]),
            Paragraph(d.get("session_type",""),  styles["FieldValue"]),
            Paragraph("",                        styles["FieldValue"]),
            Paragraph("",                        styles["FieldValue"]),
        ])
    t = Table(rows, colWidths=[3.2*cm, 2.8*cm, 2.8*cm, 4*cm, 6.2*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0), IUB_GREEN),
        ("TEXTCOLOR",    (0,0),(-1,0), colors.white),
        ("GRID",         (0,0),(-1,-1), 0.5, colors.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, IUB_LIGHT]),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 0.4*cm))

    singles = bill_data.get("total_days", 0)
    doubles = bill_data.get("total_double", 0)
    total_sessions = singles + doubles
    calc = [
        [Paragraph("<b>Total Sessions</b>", styles["SignLabel"]),
         Paragraph("<b>Rate Per Session (Rs.)</b>", styles["SignLabel"]),
         Paragraph("<b>Total Remuneration (Rs.)</b>", styles["SignLabel"])],
        [Paragraph(str(total_sessions), styles["CenterNorm"]),
         Paragraph(f"Single: {bill_data['rate_single']:,.0f} / Double: {bill_data['rate_double']:,.0f}", styles["CenterNorm"]),
         Paragraph(f"<b>{bill_data['amount']:,.0f}/-</b>", styles["CenterNorm"])],
    ]
    tc = Table(calc, colWidths=[6.3*cm, 7*cm, 5.7*cm])
    tc.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0), IUB_GREEN),
        ("TEXTCOLOR",    (0,0),(-1,0), colors.white),
        ("GRID",         (0,0),(-1,-1), 0.5, colors.grey),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("ALIGN",        (0,0),(-1,-1), "CENTER"),
    ]))
    elems.append(tc)
    elems.append(Spacer(1, 0.6*cm))

    sig_rows = [[
        Paragraph("________________________\nSignature of Invigilator", styles["CenterNorm"]),
        Paragraph("________________________\nSuperintendent", styles["CenterNorm"]),
        Paragraph("________________________\nController of Examinations", styles["CenterNorm"]),
    ]]
    st = Table(sig_rows, colWidths=[6.3*cm, 6.3*cm, 6.4*cm])
    st.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),20),("ALIGN",(0,0),(-1,-1),"CENTER")]))
    elems.append(st)
    elems.append(Spacer(1, 0.6*cm))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(Paragraph("FOR OFFICE USE ONLY", styles["IUBSmall"]))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(_approval_block(styles))
    doc.build(elems)
    return path


# ── PDF Type 4: Paper Checker Bill ────────────────────────────────────────────

def generate_paper_checker_bill(bill_data, appt, duties, session_name):
    path = _output_path(_make_filename("Bill", appt.get("role",""), appt.get("full_name",""), appt.get("cnic","")))
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = _base_styles()
    elems = _header(styles)
    elems.append(Paragraph("PAPER CHECKER BILLING STATEMENT", styles["BillTitle"]))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(_info_table(bill_data, appt, session_name, styles))
    elems.append(Spacer(1, 0.4*cm))

    header = [
        Paragraph("<b>Entry No.</b>", styles["SignLabel"]),
        Paragraph("<b>Date</b>",      styles["SignLabel"]),
        Paragraph("<b>Description</b>", styles["SignLabel"]),
        Paragraph("<b>Scripts/Bundles</b>", styles["SignLabel"]),
    ]
    rows = [header]
    for i, d in enumerate(duties, 1):
        rows.append([
            Paragraph(str(i), styles["CenterNorm"]),
            Paragraph(d.get("duty_date",""), styles["FieldValue"]),
            Paragraph("Paper Checking", styles["FieldValue"]),
            Paragraph(str(d.get("scripts", 1)), styles["CenterNorm"]),
        ])
    t = Table(rows, colWidths=[2.5*cm, 3.5*cm, 8*cm, 5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0), IUB_GREEN),
        ("TEXTCOLOR",    (0,0),(-1,0), colors.white),
        ("GRID",         (0,0),(-1,-1), 0.5, colors.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, IUB_LIGHT]),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 0.4*cm))

    calc = [
        [Paragraph("<b>Total Scripts</b>", styles["SignLabel"]),
         Paragraph("<b>Rate Per Script (Rs.)</b>", styles["SignLabel"]),
         Paragraph("<b>Total Amount (Rs.)</b>", styles["SignLabel"])],
        [Paragraph(str(bill_data.get("total_qty",0)), styles["CenterNorm"]),
         Paragraph(f"{bill_data['rate_single']:,.0f}", styles["CenterNorm"]),
         Paragraph(f"<b>{bill_data['amount']:,.0f}/-</b>", styles["CenterNorm"])],
    ]
    tc = Table(calc, colWidths=[6.3*cm, 7*cm, 5.7*cm])
    tc.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0), IUB_GREEN),
        ("TEXTCOLOR",    (0,0),(-1,0), colors.white),
        ("GRID",         (0,0),(-1,-1), 0.5, colors.grey),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("ALIGN",        (0,0),(-1,-1), "CENTER"),
    ]))
    elems.append(tc)
    elems.append(Spacer(1, 0.6*cm))
    elems.append(_signature_block(styles))
    elems.append(Spacer(1, 0.6*cm))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(Paragraph("FOR OFFICE USE ONLY", styles["IUBSmall"]))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(_approval_block(styles))
    doc.build(elems)
    return path


# ── Appointment Letter ─────────────────────────────────────────────────────────

def generate_appointment_letter(appt, session_name):
    """Generate appointment letter in official IUB format."""
    role        = appt.get("role", "")
    name        = appt.get("full_name", "")
    designation = appt.get("designation", "") or ""
    institution = appt.get("institution", "") or ""
    cnic        = appt.get("cnic", "")
    phone       = appt.get("phone", "") or ""
    centre      = appt.get("centre", "") or ""
    letter_no   = appt.get("letter_no", "") or ""
    letter_date = appt.get("letter_date", "") or datetime.now().strftime("%d/%m/%Y")

    path = _output_path(_make_filename("Letter", role, name, cnic))
    doc  = SimpleDocTemplate(path, pagesize=A4,
                             leftMargin=2.5*cm, rightMargin=2.5*cm,
                             topMargin=2*cm,    bottomMargin=2*cm)
    styles = _base_styles()
    elems  = []

    # ── University header ──────────────────────────────────────────────────────
    elems.append(Paragraph(
        "The Islamia University of Bahawalpur", styles["IUBTitle"]))
    elems.append(Paragraph(
        "Examinations Department", styles["IUBSub"]))
    elems.append(Paragraph(
        "(0349-4440047)", styles["IUBSmall"]))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=IUB_GREEN))
    elems.append(Spacer(1, 0.4*cm))

    # ── No. / Date row ─────────────────────────────────────────────────────────
    no_date = Table(
        [["",
          Paragraph(
              f"<b>No.</b> {letter_no}/Cond/Exam<br/>"
              f"<b>Dated:</b>  {letter_date}",
              styles["RightNorm"]
          )]],
        colWidths=[12*cm, 7*cm]
    )
    no_date.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elems.append(no_date)
    elems.append(Spacer(1, 0.2*cm))

    # ── Addressee ──────────────────────────────────────────────────────────────
    elems.append(Paragraph("To,", styles["FieldValue"]))
    addr_lines = [f"<b>{name}</b>"]
    if designation:
        addr_lines.append(designation)
    addr_lines.append(f"({cnic})")
    if institution:
        addr_lines.append(institution)
    elems.append(Paragraph("<br/>".join(addr_lines), styles["FieldValue"]))
    elems.append(Spacer(1, 0.4*cm))

    # ── Salutation & body ──────────────────────────────────────────────────────
    elems.append(Paragraph("Dear Sir / Madam,", styles["FieldValue"]))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph(
        f"I have the honor to inform you that you have been appointed as "
        f"<b>{role}</b> in <b>{session_name}</b>",
        styles["FieldValue"]
    ))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph(
        "If you are available to act as such on the following rates, you are requested "
        "to send your willingness to the undersigned immediately on the enclosed forms.",
        styles["FieldValue"]
    ))
    elems.append(Spacer(1, 0.2*cm))
    elems.append(Paragraph(
        "You are directed to reach the Centre / Office one day before (at 02:00 PM) the "
        "commencement of the Examination to help the Superintendent in making necessary "
        "arrangements for conduct of Examination.",
        styles["FieldValue"]
    ))
    elems.append(Spacer(1, 0.3*cm))

    # ── Notes ──────────────────────────────────────────────────────────────────
    elems.append(Paragraph("<b>NOTE:</b>", styles["FieldLabel"]))
    for i, note in enumerate([
        "Mobile phone is neither allowed to candidate nor to the Supervisory Staff "
        "except Superintendent.",
        "Please ensure the searching of all candidates before entry to the Examination hall.",
        "Check the Original CNIC and Roll No. slips of the candidates.",
        "NO T.A / D.A WILL BE ALLOWED.",
    ], 1):
        elems.append(Paragraph(f"{i}. {note}", styles["FieldValue"]))
    elems.append(Spacer(1, 0.5*cm))

    # ── Sign-off ───────────────────────────────────────────────────────────────
    elems.append(Paragraph("Yours Sincerely", styles["FieldValue"]))
    elems.append(Spacer(1, 1.2*cm))
    sign_off = Table(
        [[Paragraph(
            "Additional Controller of Examinations<br/>"
            "For Controller of Examinations",
            styles["FieldValue"]
        )]],
        colWidths=[19*cm]
    )
    sign_off.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT")]))
    elems.append(sign_off)
    elems.append(Spacer(1, 0.5*cm))

    # ── Form of Acceptance ─────────────────────────────────────────────────────
    elems.append(HRFlowable(width="100%", thickness=1, color=IUB_GREEN))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph(
        "The Islamia University of Bahawalpur", styles["IUBTitle"]))
    elems.append(Spacer(1, 0.1*cm))
    elems.append(Paragraph("<b>FORM OF ACCEPTANCE</b>", styles["BillTitle"]))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph(
        f"I accept the offer to work as <b>{role}</b> in <b>{session_name}</b> "
        f"at <b>{centre}</b> on the terms and conditions mentioned in the covering letter. "
        f"I certify that none of my relative(s) is appearing in the said Examination "
        f"Centre within jurisdiction of the Islamia University of Bahawalpur.",
        styles["FieldValue"]
    ))
    elems.append(Spacer(1, 0.5*cm))

    # Acceptance field table
    accept_rows = [
        [Paragraph(f"<b>Name:</b> {name}", styles["FieldValue"]),
         Paragraph(f"<b>Phone No.</b> {phone}", styles["FieldValue"])],
        [Paragraph(f"<b>Address:</b> {institution}", styles["FieldValue"]), ""],
        [Paragraph("Signature:  ________________________", styles["FieldValue"]),
         Paragraph(f"<b>ID:</b>  {cnic}", styles["FieldValue"])],
    ]
    at = Table(accept_rows, colWidths=[10.5*cm, 8.5*cm])
    at.setStyle(TableStyle([
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ("SPAN",           (0, 1), (1,  1)),
    ]))
    elems.append(at)
    elems.append(Spacer(1, 0.4*cm))
    elems.append(Paragraph(
        f"At <b>{centre}</b><br/>"
        f"<b>{session_name}</b> w.e.f. {letter_date}",
        styles["FieldValue"]
    ))

    doc.build(elems)
    return path


# ── Dispatch ──────────────────────────────────────────────────────────────────

INSPECTOR_ROLES = {"Resident Inspector", "Distributing Inspector", "Member Inspection Squad"}
FORM95A_ROLES   = {"Invigilator", "Deputy Superintendent"}


def get_letter_preview_text(appt, session_name):
    """Return plain-text letter content for preview — matches official IUB format."""
    role        = appt.get("role", "")
    name        = appt.get("full_name", "")
    designation = appt.get("designation", "") or ""
    institution = appt.get("institution", "") or ""
    cnic        = appt.get("cnic", "")
    phone       = appt.get("phone", "") or ""
    centre      = appt.get("centre", "") or ""
    letter_no   = appt.get("letter_no", "") or ""
    letter_date = appt.get("letter_date", "") or datetime.now().strftime("%d/%m/%Y")

    addr = [name]
    if designation:
        addr.append(designation)
    addr.append(f"({cnic})")
    if institution:
        addr.append(institution)

    lines = [
        "The Islamia University of Bahawalpur",
        "Examinations Department",
        "(0349-4440047)",
        "─" * 58,
        f"No. {letter_no}/Cond/Exam                              Dated: {letter_date}",
        "",
        "To,",
    ] + addr + [
        "",
        "Dear Sir / Madam,",
        "",
        f"I have the honor to inform you that you have been appointed as {role}",
        f"in {session_name}",
        "",
        "If you are available to act as such on the following rates, you are requested",
        "to send your willingness to the undersigned immediately on the enclosed forms.",
        "You are directed to reach the Centre / Office one day before (at 02:00 PM) the",
        "commencement of the Examination to help the Superintendent in making necessary",
        "arrangements for conduct of Examination.",
        "",
        "NOTE:",
        "1. Mobile phone is neither allowed to candidate nor to the Supervisory Staff",
        "   except Superintendent.",
        "2. Please ensure the searching of all candidates before entry to the Examination hall.",
        "3. Check the Original CNIC and Roll No. slips of the candidates.",
        "4. NO T.A / D.A WILL BE ALLOWED.",
        "",
        "Yours Sincerely",
        "",
        "",
        "                                       Additional Controller of Examinations",
        "                                       For Controller of Examinations",
        "",
        "─" * 58,
        "The Islamia University of Bahawalpur",
        "FORM OF ACCEPTANCE",
        "",
        f"I accept the offer to work as {role} in {session_name}",
        f"at {centre}",
        "on the terms and conditions mentioned in the covering letter. I certify that",
        "none of my relative(s) is appearing in the said Examination Centre within",
        "jurisdiction of the Islamia University of Bahawalpur.",
        "",
        f"Name: {name}     Phone No. {phone}",
        f"Address: {institution}",
        "",
        f"Signature: ________________________    ID: {cnic}",
        "",
        f"At {centre}",
        f"{session_name} w.e.f. {letter_date}",
    ]
    return "\n".join(lines)


def generate_bill_pdf(bill_data, appt, duties, session_name, extra_items=None):
    role = appt.get("role","")
    if role == "Superintendent":
        return generate_superintendent_bill(bill_data, appt, duties, session_name, extra_items or {})
    elif role in INSPECTOR_ROLES:
        return generate_inspector_bill(bill_data, appt, duties, session_name)
    elif role in FORM95A_ROLES:
        return generate_form95a_bill(bill_data, appt, duties, session_name)
    elif role == "Paper Checker":
        return generate_paper_checker_bill(bill_data, appt, duties, session_name)
    else:
        return generate_inspector_bill(bill_data, appt, duties, session_name)
