import json
from datetime import datetime
from core.database import (
    get_appointment_by_id, get_duties_for_appointment, get_connection,
    save_bill, generate_bill_number,
)


def calculate_bill(appointment_id, extra_items=None):
    appt = get_appointment_by_id(appointment_id)
    if not appt:
        raise ValueError(f"Appointment {appointment_id} not found.")

    duties = get_duties_for_appointment(appointment_id)
    if not duties:
        raise ValueError("Cannot generate a bill with zero duties logged.")

    role = appt["role"]

    conn = get_connection()
    try:
        rate_row = conn.execute("SELECT * FROM rates WHERE role=?", (role,)).fetchone()
    finally:
        conn.close()

    if not rate_row:
        raise ValueError(f"No rate configured for role: {role}")

    rate_single = rate_row["rate_single"]
    rate_double = rate_row["rate_double"]
    unit = rate_row["unit"]

    if unit == "per_script":
        # Paper Checker: each duty row = one script batch; total_qty = count of duties
        total_qty = len(duties)
        total_days = total_qty
        total_double = 0
        amount = total_qty * rate_single
        extra_items_json = "{}"
    else:
        # Singles: rows with session_type='Single'
        # Doubles: unique DATES where session_type='Double'
        #   (Morning+Evening on same date = 1 double billing unit, stored as 2 rows)
        singles = sum(1 for d in duties if d["session_type"] == "Single")
        double_dates = set(d["duty_date"] for d in duties if d["session_type"] == "Double")
        doubles = len(double_dates)
        total_days = singles
        total_double = doubles
        total_qty = singles + doubles

        amount = (singles * rate_single) + (doubles * rate_double)

        if role == "Superintendent" and extra_items:
            gross = amount
            contingent_total = 0
            for key in ("collection_qp", "dispatch_ab", "menial", "stationery", "ice"):
                contingent_total += float(extra_items.get(key, 0) or 0)
            advance = float(extra_items.get("advance", 0) or 0)
            gross += contingent_total
            amount = max(0, gross - advance)
            extra_items["gross"] = round(gross, 2)
            extra_items["contingent_total"] = round(contingent_total, 2)

        extra_items_json = json.dumps(extra_items or {})

    session_id = appt["session_id"]
    bill_no = generate_bill_number(session_id, appointment_id)

    save_bill(
        appointment_id=appointment_id,
        bill_no=bill_no,
        total_days=total_days,
        total_double=total_double,
        total_qty=total_qty,
        rate_single=rate_single,
        rate_double=rate_double,
        amount=amount,
        extra_items=extra_items_json,
        pdf_path="",
    )

    return {
        "bill_no": bill_no,
        "appointment_id": appointment_id,
        "role": role,
        "full_name": appt["full_name"],
        "centre": appt["centre"],
        "session_id": session_id,
        "total_days": total_days,
        "total_double": total_double,
        "total_qty": total_qty,
        "rate_single": rate_single,
        "rate_double": rate_double,
        "amount": amount,
        "extra_items": extra_items or {},
        "duties": [dict(d) for d in duties],
        "appt": dict(appt),
    }
