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

def _letter_body(role, appt, session_name, styles):
    """Return a list of ReportLab flowables for the role-specific letter body."""
    name    = appt.get("full_name", "")
    centre  = appt.get("centre", "")
    desig   = appt.get("designation", "") or ""
    inst    = appt.get("institution", "") or ""

    bodies = {
        "Superintendent": (
            f"I am directed to inform you that you have been appointed as "
            f"<b>Superintendent</b> at <b>{centre}</b> for the <b>{session_name}</b>. "
            f"You are required to ensure the smooth and transparent conduct of the examination "
            f"at your centre in accordance with the Examination Rules of The Islamia University "
            f"of Bahawalpur. You will be responsible for the collection and safe custody of "
            f"question papers, proper seating of candidates, maintenance of discipline, and "
            f"timely dispatch of answer books to the Examinations Branch. "
            f"Your remuneration will be paid as per the prescribed rates after submission of "
            f"the duly completed duty register.",
            "I hereby accept the appointment as Superintendent and undertake to perform all "
            "duties assigned to me in accordance with the University's Examination Rules and "
            "Regulations, maintaining the highest standards of integrity and fairness.",
            "Signature of Superintendent"
        ),
        "Deputy Superintendent": (
            f"I am directed to inform you that you have been appointed as "
            f"<b>Deputy Superintendent</b> at <b>{centre}</b> for the <b>{session_name}</b>. "
            f"You will assist the Superintendent in the overall management of the examination "
            f"centre, including supervision of invigilators, maintenance of attendance sheets, "
            f"and ensuring the sanctity of the examination process. You are required to carry "
            f"out all instructions of the Superintendent and the Examinations Branch. "
            f"Your remuneration will be paid as per the prescribed rates after the completion "
            f"of examination duties.",
            "I hereby accept the appointment as Deputy Superintendent and undertake to assist "
            "the Superintendent and perform all assigned duties in strict accordance with the "
            "University's Examination Rules.",
            "Signature of Deputy Superintendent"
        ),
        "Resident Inspector": (
            f"I am directed to inform you that you have been appointed as "
            f"<b>Resident Inspector</b> for the <b>{session_name}</b>. "
            f"You are required to visit the assigned examination centres regularly, ensure "
            f"compliance with the University's Examination Rules, check for any malpractice, "
            f"and submit daily inspection reports to the Controller of Examinations. "
            f"You will also coordinate with Superintendents to resolve any issues arising "
            f"during the examination period. "
            f"Your remuneration will be paid as per the prescribed rates on completion of duty.",
            "I hereby accept the appointment as Resident Inspector and undertake to perform "
            "regular inspections and submit accurate reports in accordance with the University's "
            "directives.",
            "Signature of Resident Inspector"
        ),
        "Distributing Inspector": (
            f"I am directed to inform you that you have been appointed as "
            f"<b>Distributing Inspector</b> for the <b>{session_name}</b>. "
            f"You are required to collect the sealed question paper packets from the "
            f"Examinations Branch and distribute them to the designated examination centres "
            f"on the scheduled dates. You must maintain a proper record of distribution "
            f"and obtain signatures from the Superintendents upon delivery. "
            f"Your remuneration will be paid as per the prescribed rates on completion of duty.",
            "I hereby accept the appointment as Distributing Inspector and undertake to "
            "distribute question papers securely and maintain accurate records as required "
            "by the University's Examination Rules.",
            "Signature of Distributing Inspector"
        ),
        "Member Inspection Squad": (
            f"I am directed to inform you that you have been appointed as "
            f"<b>Member of the Inspection Squad</b> for the <b>{session_name}</b>. "
            f"As a member of the Inspection Squad, you are required to conduct surprise "
            f"visits to examination centres, ensure strict observance of examination rules, "
            f"report any irregularities or malpractice to the Controller of Examinations, "
            f"and take immediate corrective action where necessary. "
            f"Your remuneration will be paid as per the prescribed rates on submission of "
            f"completed duty reports.",
            "I hereby accept the appointment as Member of the Inspection Squad and undertake "
            "to conduct thorough and impartial inspections as directed by the Controller of "
            "Examinations.",
            "Signature of Member (Inspection Squad)"
        ),
        "Invigilator": (
            f"I am directed to inform you that you have been appointed as "
            f"<b>Invigilator</b> at <b>{centre}</b> for the <b>{session_name}</b>. "
            f"You are required to report for duty at least 30 minutes before the commencement "
            f"of each examination session. You will be responsible for the proper seating of "
            f"candidates, distribution of answer books, prevention of any form of malpractice, "
            f"and collection of answer books at the end of each session. "
            f"You must strictly follow the instructions of the Superintendent and the "
            f"Examinations Branch. Your remuneration will be paid as per Form 95-A rates "
            f"after completion of duty.",
            "I hereby accept the appointment as Invigilator and undertake to perform "
            "invigilator duties honestly and diligently in accordance with the University's "
            "Examination Rules, under the supervision of the Superintendent.",
            "Signature of Invigilator"
        ),
    }

    # Use role-specific text or fall back to generic
    if role in bodies:
        body_text, acceptance_text, sig_label = bodies[role]
    else:
        body_text = (
            f"I am directed to inform you that you have been appointed as <b>{role}</b> "
            f"at <b>{centre}</b> for the <b>{session_name}</b>. You are requested to "
            f"perform your duties diligently in accordance with the University's rules "
            f"and regulations."
        )
        acceptance_text = (
            f"I hereby accept the appointment as {role} for the {session_name} and "
            f"undertake to perform the assigned duties in accordance with the University's "
            f"rules and regulations."
        )
        sig_label = "Signature of Appointee"

    elems = []
    elems.append(Paragraph(body_text, styles["FieldValue"]))
    elems.append(Spacer(1, 0.8*cm))
    sig = Table(
        [[Paragraph(
            "________________________\n<b>Additional Controller of Examinations</b>\n"
            "The Islamia University of Bahawalpur",
            styles["CenterNorm"]
        )]],
        colWidths=[19*cm]
    )
    sig.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT")]))
    elems.append(sig)
    elems.append(Spacer(1, 1*cm))
    elems.append(HRFlowable(width="100%", thickness=1, color=IUB_GREEN))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph("<b>FORM OF ACCEPTANCE</b>", styles["BillTitle"]))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph(
        f"I, <b>{name}</b>, {desig}{', ' + inst if inst else ''}, "
        f"{acceptance_text}",
        styles["FieldValue"]
    ))
    elems.append(Spacer(1, 1*cm))
    elems.append(Table(
        [[Paragraph(f"________________________\n{sig_label}", styles["CenterNorm"]),
          Paragraph("________________________\nDate", styles["CenterNorm"])]],
        colWidths=[9.5*cm, 9.5*cm]
    ))
    return elems


def generate_appointment_letter(appt, session_name):
    role = appt.get("role", "")
    path = _output_path(_make_filename("Letter", role, appt.get("full_name",""), appt.get("cnic","")))
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2.5*cm, rightMargin=2.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = _base_styles()
    elems = _header(styles)

    date_now = datetime.now().strftime("%d %B, %Y")
    elems.append(Table(
        [[Paragraph("", styles["FieldValue"]),
          Paragraph(
              f"<b>No.:</b> {appt.get('letter_no','')}<br/><b>Date:</b> {date_now}",
              styles["RightNorm"]
          )]],
        colWidths=[10*cm, 9*cm]
    ))
    elems.append(Spacer(1, 0.5*cm))

    addr_parts = [appt.get("full_name", ""), appt.get("designation", "") or "", appt.get("institution", "") or ""]
    addr_text = "<br/>".join(p for p in addr_parts if p)
    elems.append(Paragraph(f"<b>To:</b><br/>{addr_text}", styles["FieldValue"]))
    elems.append(Spacer(1, 0.4*cm))
    elems.append(Paragraph("Dear Sir/Madam,", styles["FieldValue"]))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph(
        f"<b>Subject: APPOINTMENT OF {role.upper()} FOR THE {session_name.upper()}</b>",
        styles["FieldLabel"]
    ))
    elems.append(Spacer(1, 0.3*cm))

    elems.extend(_letter_body(role, appt, session_name, styles))
    doc.build(elems)
    return path


# ── Dispatch ──────────────────────────────────────────────────────────────────

INSPECTOR_ROLES = {"Resident Inspector", "Distributing Inspector", "Member Inspection Squad"}
FORM95A_ROLES   = {"Invigilator", "Deputy Superintendent"}


def get_letter_preview_text(appt, session_name):
    """Return plain-text letter content for preview (no HTML tags)."""
    role      = appt.get("role", "")
    name      = appt.get("full_name", "")
    centre    = appt.get("centre", "") or ""
    desig     = appt.get("designation", "") or ""
    inst      = appt.get("institution", "") or ""
    letter_no = appt.get("letter_no", "") or ""
    date_now  = datetime.now().strftime("%d %B, %Y")

    bodies = {
        "Superintendent": (
            f"I am directed to inform you that you have been appointed as Superintendent at "
            f"{centre} for the {session_name}. You are required to ensure the smooth and "
            f"transparent conduct of the examination at your centre in accordance with the "
            f"Examination Rules of The Islamia University of Bahawalpur. You will be responsible "
            f"for the collection and safe custody of question papers, proper seating of candidates, "
            f"maintenance of discipline, and timely dispatch of answer books to the Examinations "
            f"Branch. Your remuneration will be paid as per the prescribed rates after submission "
            f"of the duly completed duty register.",
            "I hereby accept the appointment as Superintendent and undertake to perform all duties "
            "assigned to me in accordance with the University's Examination Rules and Regulations, "
            "maintaining the highest standards of integrity and fairness.",
            "Signature of Superintendent",
        ),
        "Deputy Superintendent": (
            f"I am directed to inform you that you have been appointed as Deputy Superintendent "
            f"at {centre} for the {session_name}. You will assist the Superintendent in the "
            f"overall management of the examination centre, including supervision of invigilators, "
            f"maintenance of attendance sheets, and ensuring the sanctity of the examination "
            f"process. You are required to carry out all instructions of the Superintendent and "
            f"the Examinations Branch. Your remuneration will be paid as per the prescribed rates "
            f"after the completion of examination duties.",
            "I hereby accept the appointment as Deputy Superintendent and undertake to assist the "
            "Superintendent and perform all assigned duties in strict accordance with the "
            "University's Examination Rules.",
            "Signature of Deputy Superintendent",
        ),
        "Resident Inspector": (
            f"I am directed to inform you that you have been appointed as Resident Inspector for "
            f"the {session_name}. You are required to visit the assigned examination centres "
            f"regularly, ensure compliance with the University's Examination Rules, check for any "
            f"malpractice, and submit daily inspection reports to the Controller of Examinations. "
            f"You will also coordinate with Superintendents to resolve any issues arising during "
            f"the examination period. Your remuneration will be paid as per the prescribed rates "
            f"on completion of duty.",
            "I hereby accept the appointment as Resident Inspector and undertake to perform "
            "regular inspections and submit accurate reports in accordance with the University's "
            "directives.",
            "Signature of Resident Inspector",
        ),
        "Distributing Inspector": (
            f"I am directed to inform you that you have been appointed as Distributing Inspector "
            f"for the {session_name}. You are required to collect the sealed question paper "
            f"packets from the Examinations Branch and distribute them to the designated "
            f"examination centres on the scheduled dates. You must maintain a proper record of "
            f"distribution and obtain signatures from the Superintendents upon delivery. Your "
            f"remuneration will be paid as per the prescribed rates on completion of duty.",
            "I hereby accept the appointment as Distributing Inspector and undertake to distribute "
            "question papers securely and maintain accurate records as required by the University's "
            "Examination Rules.",
            "Signature of Distributing Inspector",
        ),
        "Member Inspection Squad": (
            f"I am directed to inform you that you have been appointed as Member of the Inspection "
            f"Squad for the {session_name}. As a member of the Inspection Squad, you are required "
            f"to conduct surprise visits to examination centres, ensure strict observance of "
            f"examination rules, report any irregularities or malpractice to the Controller of "
            f"Examinations, and take immediate corrective action where necessary. Your remuneration "
            f"will be paid as per the prescribed rates on submission of completed duty reports.",
            "I hereby accept the appointment as Member of the Inspection Squad and undertake to "
            "conduct thorough and impartial inspections as directed by the Controller of "
            "Examinations.",
            "Signature of Member (Inspection Squad)",
        ),
        "Invigilator": (
            f"I am directed to inform you that you have been appointed as Invigilator at "
            f"{centre} for the {session_name}. You are required to report for duty at least "
            f"30 minutes before the commencement of each examination session. You will be "
            f"responsible for the proper seating of candidates, distribution of answer books, "
            f"prevention of any form of malpractice, and collection of answer books at the end "
            f"of each session. You must strictly follow the instructions of the Superintendent "
            f"and the Examinations Branch. Your remuneration will be paid as per Form 95-A rates "
            f"after completion of duty.",
            "I hereby accept the appointment as Invigilator and undertake to perform invigilator "
            "duties honestly and diligently in accordance with the University's Examination Rules, "
            "under the supervision of the Superintendent.",
            "Signature of Invigilator",
        ),
    }

    if role in bodies:
        body_text, acceptance_text, sig_label = bodies[role]
    else:
        body_text = (
            f"I am directed to inform you that you have been appointed as {role} at {centre} "
            f"for the {session_name}. You are requested to perform your duties diligently in "
            f"accordance with the University's rules and regulations."
        )
        acceptance_text = (
            f"I hereby accept the appointment as {role} for the {session_name} and undertake "
            f"to perform the assigned duties in accordance with the University's rules and "
            f"regulations."
        )
        sig_label = "Signature of Appointee"

    lines = [
        f"No.: {letter_no}",
        f"Date: {date_now}",
        "",
        "To:",
        name,
    ]
    if desig:
        lines.append(desig)
    if inst:
        lines.append(inst)
    lines += [
        "",
        "Dear Sir/Madam,",
        "",
        f"Subject: APPOINTMENT OF {role.upper()} FOR THE {session_name.upper()}",
        "",
        body_text,
        "",
        "Yours faithfully,",
        "",
        "________________________",
        "Additional Controller of Examinations",
        "The Islamia University of Bahawalpur",
        "",
        "─" * 55,
        "FORM OF ACCEPTANCE",
        "",
        f"I, {name}, {desig}{', ' + inst if inst else ''}, {acceptance_text}",
        "",
        f"{sig_label}: ________________________",
        "Date: ________________________",
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
