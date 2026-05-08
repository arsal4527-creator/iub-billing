COLUMN_MAP = {
    "full name":            "full_name",
    "father's name":        "father_name",
    "father name":          "father_name",
    "cnic number":          "cnic",
    "cnic":                 "cnic",
    "gender":               "gender",
    "contact number":       "mobile",
    "mobile no (whatsapp)": "mobile",
    "email address":        "email",
    "e-mail":               "email",
    "qualification":        "qualification",
    "are you filer":        "tax_filer",
    "tax filer":            "tax_filer",
    "current designation":  "post",
    "post":                 "post",
    "bps":                  "basic_pay_scale",
    "basic pay scale":      "basic_pay_scale",
    "institution":          "institution",
    "institution name":     "institution",
    "home address":         "residential_address",
    "residential address":  "residential_address",
    "preferred duty type":  "apply_for",
    "apply for":            "apply_for",
    "experience":           "exp_teaching_inst",
    "in which city":        "proposed_station_1",
    "proposed station 1":   "proposed_station_1",
    "district":             "district",
    # Legacy internal CSV column names
    "ntn #":                "ntn",
    "academic qualification": "qualification",
    "phone office":         "phone_office",
    "phone res":            "phone_res",
    "teaching years":       "exp_teaching_years",
    "teaching institution": "exp_teaching_inst",
    "superintendent years": "exp_supt_years",
    "superintendent institution": "exp_supt_inst",
    "deputy superintendent years": "exp_dy_supt_years",
    "deputy superintendent institution": "exp_dy_supt_inst",
    "invigilator years":    "exp_invig_years",
    "invigilator institution": "exp_invig_inst",
    "proposed station 2":   "proposed_station_2",
    "proposed station 3":   "proposed_station_3",
}

_DEFAULTS = {
    "father_name": "", "gender": "", "ntn": "", "tax_filer": 0,
    "qualification": "", "post": "", "basic_pay_scale": "", "district": "",
    "institution": "", "residential_address": "", "phone_office": "",
    "phone_res": "", "mobile": "", "email": "", "apply_for": "",
    "exp_teaching_years": 0, "exp_teaching_inst": "",
    "exp_supt_years": 0, "exp_supt_inst": "",
    "exp_dy_supt_years": 0, "exp_dy_supt_inst": "",
    "exp_invig_years": 0, "exp_invig_inst": "",
    "proposed_station_1": "", "proposed_station_2": "", "proposed_station_3": "",
}


def _format_cnic(raw):
    digits = ''.join(c for c in str(raw) if c.isdigit())
    if len(digits) == 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
    return raw.strip()


def import_from_csv_file(filepath, session_tag=None):
    """
    Import applications from a local CSV file (including Google Form exports).
    Column names are matched case-insensitively using startswith against COLUMN_MAP.
    Returns (imported_count, skipped_count, error_message)
    """
    import csv
    from core.database import get_all_applications, add_application, get_connection

    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        return 0, 0, f"Could not read file: {e}"

    existing = get_all_applications()
    existing_cnics = {a["cnic"] for a in existing}
    imported = 0
    skipped = 0

    for row in rows:
        data = {}
        for col, val in row.items():
            if col.strip().lower() == "timestamp":
                continue
            col_lower = col.strip().lower()
            matched = None
            for key, db_field in COLUMN_MAP.items():
                if col_lower.startswith(key):
                    matched = db_field
                    break
            if matched:
                data[matched] = str(val or "").strip()

        # Format CNIC
        raw_cnic = data.get("cnic", "").strip()
        if raw_cnic:
            data["cnic"] = _format_cnic(raw_cnic)

        cnic = data.get("cnic", "")
        if not cnic or not data.get("full_name"):
            skipped += 1
            continue

        if cnic in existing_cnics:
            skipped += 1
            continue

        # Normalize tax_filer
        tax_raw = data.get("tax_filer", "").lower()
        data["tax_filer"] = 1 if tax_raw in ("yes", "1", "true") else 0

        # Numeric experience year fields
        for k in ("exp_teaching_years", "exp_supt_years",
                  "exp_dy_supt_years", "exp_invig_years"):
            try:
                data[k] = int(data.get(k, 0) or 0)
            except ValueError:
                data[k] = 0

        final = {**_DEFAULTS, **data}

        try:
            app_id = add_application(final)
            if session_tag and app_id:
                conn = get_connection()
                try:
                    conn.execute("UPDATE applications SET session_tag=? WHERE id=?",
                                 (session_tag, app_id))
                    conn.commit()
                finally:
                    conn.close()
            existing_cnics.add(cnic)
            imported += 1
        except Exception:
            skipped += 1

    return imported, skipped, ""
