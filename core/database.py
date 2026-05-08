import sqlite3
import os
import hashlib
import binascii
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iub_billing.db")

INITIAL_RATES = [
    ("Resident Inspector",      1000, 1500, "per_session"),
    ("Distributing Inspector",  1500, 2000, "per_session"),
    ("Member Inspection Squad",  500,  500, "per_session"),
    ("Superintendent",           350,  450, "per_session"),
    ("Deputy Superintendent",    300,  400, "per_session"),
    ("Invigilator",              200,  300, "per_session"),
    ("Paper Checker",             12,   12, "per_script"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   TEXT NOT NULL,
    cnic        TEXT UNIQUE NOT NULL,
    phone       TEXT,
    address     TEXT,
    designation TEXT,
    institution TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS exam_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name  TEXT NOT NULL,
    programs      TEXT,
    year          TEXT,
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id        INTEGER NOT NULL REFERENCES staff(id),
    session_id      INTEGER NOT NULL REFERENCES exam_sessions(id),
    role            TEXT NOT NULL,
    centre          TEXT,
    letter_no       TEXT,
    letter_date     TEXT,
    status          TEXT DEFAULT 'appointed',
    created_at      TEXT,
    UNIQUE(staff_id, session_id, role)
);

CREATE TABLE IF NOT EXISTS duty_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id  INTEGER NOT NULL REFERENCES appointments(id),
    duty_date       TEXT NOT NULL,
    session         TEXT NOT NULL,
    session_type    TEXT NOT NULL,
    locked          INTEGER DEFAULT 0,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS bills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id  INTEGER NOT NULL UNIQUE REFERENCES appointments(id),
    bill_no         TEXT UNIQUE,
    total_days      INTEGER DEFAULT 0,
    total_double    INTEGER DEFAULT 0,
    total_qty       REAL DEFAULT 0,
    rate_single     REAL DEFAULT 0,
    rate_double     REAL DEFAULT 0,
    amount          REAL DEFAULT 0,
    extra_items     TEXT DEFAULT '{}',
    generated_at    TEXT,
    pdf_path        TEXT
);

CREATE TABLE IF NOT EXISTS rates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    role        TEXT UNIQUE NOT NULL,
    rate_single REAL NOT NULL DEFAULT 0,
    rate_double REAL NOT NULL DEFAULT 0,
    unit        TEXT DEFAULT 'per_session',
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,
    detail      TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name           TEXT NOT NULL,
    father_name         TEXT,
    cnic                TEXT UNIQUE NOT NULL,
    gender              TEXT,
    ntn                 TEXT,
    tax_filer           INTEGER DEFAULT 0,
    qualification       TEXT,
    post                TEXT,
    basic_pay_scale     TEXT,
    district            TEXT,
    institution         TEXT,
    residential_address TEXT,
    phone_office        TEXT,
    phone_res           TEXT,
    mobile              TEXT,
    email               TEXT,
    apply_for           TEXT,
    exp_teaching_years  INTEGER DEFAULT 0,
    exp_teaching_inst   TEXT,
    exp_supt_years      INTEGER DEFAULT 0,
    exp_supt_inst       TEXT,
    exp_dy_supt_years   INTEGER DEFAULT 0,
    exp_dy_supt_inst    TEXT,
    exp_invig_years     INTEGER DEFAULT 0,
    exp_invig_inst      TEXT,
    proposed_station_1  TEXT,
    proposed_station_2  TEXT,
    proposed_station_3  TEXT,
    status              TEXT DEFAULT 'applied',
    created_at          TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        now = datetime.now().isoformat()
        for role, rs, rd, unit in INITIAL_RATES:
            conn.execute(
                """INSERT OR IGNORE INTO rates (role, rate_single, rate_double, unit, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (role, rs, rd, unit, now),
            )
        conn.commit()
    finally:
        conn.close()


# ── Settings / PIN ─────────────────────────────────────────────────────────────

def _hash_pin(pin: str, salt: bytes = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000)
    return binascii.hexlify(salt).decode() + ":" + binascii.hexlify(dk).decode()


def _check_pin_hash(pin: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split(":")
        salt = binascii.unhexlify(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000)
        return binascii.hexlify(dk).decode() == dk_hex
    except Exception:
        return False


def has_billing_pin() -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key='billing_pin'").fetchone()
        return row is not None
    finally:
        conn.close()


def set_billing_pin(pin: str, old_pin: str = None):
    """Set or change the billing PIN. Raises ValueError on wrong old_pin."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT value FROM settings WHERE key='billing_pin'").fetchone()
        if existing:
            if old_pin is None or not _check_pin_hash(old_pin, existing["value"]):
                raise ValueError("Current PIN is incorrect.")
            action = "pin_change"
        else:
            action = "pin_set"
        hashed = _hash_pin(pin)
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('billing_pin', ?)",
            (hashed,))
        conn.commit()
        audit(conn, action, "Billing PIN updated")
        conn.commit()
    finally:
        conn.close()


def verify_billing_pin(pin: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key='billing_pin'").fetchone()
        if not row:
            return True  # no PIN set — always passes
        result = _check_pin_hash(pin, row["value"])
        audit(conn, "pin_unlock" if result else "pin_fail",
              "Billing section unlock attempt")
        conn.commit()
        return result
    finally:
        conn.close()


def delete_billing_pin(current_pin: str):
    """Remove the billing PIN. Requires the current PIN."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key='billing_pin'").fetchone()
        if not row:
            return
        if not _check_pin_hash(current_pin, row["value"]):
            raise ValueError("Current PIN is incorrect.")
        conn.execute("DELETE FROM settings WHERE key='billing_pin'")
        conn.commit()
        audit(conn, "pin_removed", "Billing PIN removed")
        conn.commit()
    finally:
        conn.close()


def delete_bill(bill_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
        if not row:
            raise ValueError("Bill not found.")
        conn.execute("DELETE FROM bills WHERE id=?", (bill_id,))
        conn.commit()
        audit(conn, "bill_delete",
              f"Deleted bill id={bill_id} bill_no={row['bill_no']} amount={row['amount']}")
        conn.commit()
    finally:
        conn.close()


# ── Staff ──────────────────────────────────────────────────────────────────────

def get_all_staff(search=""):
    conn = get_connection()
    try:
        if search:
            q = f"%{search}%"
            return conn.execute(
                "SELECT * FROM staff WHERE full_name LIKE ? OR cnic LIKE ? OR institution LIKE ? ORDER BY full_name",
                (q, q, q),
            ).fetchall()
        return conn.execute("SELECT * FROM staff ORDER BY full_name").fetchall()
    finally:
        conn.close()


def get_staff_by_id(staff_id):
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
    finally:
        conn.close()


def add_staff(full_name, cnic, phone, address, designation, institution):
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            "INSERT INTO staff (full_name,cnic,phone,address,designation,institution,created_at) VALUES (?,?,?,?,?,?,?)",
            (full_name, cnic, phone, address, designation, institution, now),
        )
        conn.commit()
        audit(conn, "staff_add", f"Added staff: {full_name} ({cnic})")
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_staff(staff_id, full_name, cnic, phone, address, designation, institution):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE staff SET full_name=?,cnic=?,phone=?,address=?,designation=?,institution=? WHERE id=?",
            (full_name, cnic, phone, address, designation, institution, staff_id),
        )
        conn.commit()
        audit(conn, "staff_edit", f"Updated staff id={staff_id}")
        conn.commit()
    finally:
        conn.close()


# ── Sessions ───────────────────────────────────────────────────────────────────

def get_all_sessions():
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM exam_sessions ORDER BY id DESC").fetchall()
    finally:
        conn.close()


def get_session_by_id(session_id):
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM exam_sessions WHERE id=?", (session_id,)).fetchone()
    finally:
        conn.close()


def add_session(session_name, programs, year):
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            "INSERT INTO exam_sessions (session_name,programs,year,created_at) VALUES (?,?,?,?)",
            (session_name, programs, year, now),
        )
        conn.commit()
        audit(conn, "session_add", f"Added session: {session_name}")
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ── Appointments ───────────────────────────────────────────────────────────────

def get_appointments_for_session(session_id):
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT a.*, s.full_name, s.cnic, s.phone, s.designation, s.institution, s.address
               FROM appointments a
               JOIN staff s ON a.staff_id = s.id
               WHERE a.session_id=?
               ORDER BY s.full_name""",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()


def get_appointment_by_id(appointment_id):
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT a.*, s.full_name, s.cnic, s.phone, s.designation, s.institution, s.address
               FROM appointments a JOIN staff s ON a.staff_id=s.id
               WHERE a.id=?""",
            (appointment_id,),
        ).fetchone()
    finally:
        conn.close()


def add_appointment(staff_id, session_id, role, centre, letter_no, letter_date):
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            "INSERT INTO appointments (staff_id,session_id,role,centre,letter_no,letter_date,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (staff_id, session_id, role, centre, letter_no, letter_date, "appointed", now),
        )
        conn.commit()
        audit(conn, "appointment_add", f"staff_id={staff_id} session_id={session_id} role={role}")
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ── Duty Log ───────────────────────────────────────────────────────────────────

def get_duties_for_appointment(appointment_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM duty_log WHERE appointment_id=? ORDER BY duty_date, session",
            (appointment_id,),
        ).fetchall()
    finally:
        conn.close()


def add_duty(appointment_id, duty_date, session, session_type):
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
            (appointment_id, duty_date, session, session_type, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_duty(duty_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT locked FROM duty_log WHERE id=?", (duty_id,)).fetchone()
        if row and row["locked"]:
            raise ValueError("Cannot delete a locked duty record.")
        conn.execute("DELETE FROM duty_log WHERE id=? AND locked=0", (duty_id,))
        conn.commit()
    finally:
        conn.close()


def lock_duties_for_appointment(appointment_id, conn=None):
    own = conn is None
    if own:
        conn = get_connection()
    try:
        conn.execute("UPDATE duty_log SET locked=1 WHERE appointment_id=?", (appointment_id,))
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()


def is_appointment_locked(appointment_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM duty_log WHERE appointment_id=? AND locked=1",
            (appointment_id,),
        ).fetchone()
        return row["c"] > 0
    finally:
        conn.close()


# ── Bills ──────────────────────────────────────────────────────────────────────

def get_bill_for_appointment(appointment_id):
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM bills WHERE appointment_id=?", (appointment_id,)).fetchone()
    finally:
        conn.close()


def get_bills_for_session(session_id):
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT b.*, a.role, a.centre, a.letter_no, a.letter_date,
                      s.full_name, s.cnic, s.phone, s.designation, s.institution, s.address
               FROM bills b
               JOIN appointments a ON b.appointment_id=a.id
               JOIN staff s ON a.staff_id=s.id
               WHERE a.session_id=?
               ORDER BY s.full_name""",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()


def save_bill(appointment_id, bill_no, total_days, total_double, total_qty,
              rate_single, rate_double, amount, extra_items, pdf_path):
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        # Delete any existing bill for this appointment first to avoid bill_no
        # UNIQUE collisions when re-generating (the table has two UNIQUE constraints:
        # appointment_id and bill_no — INSERT OR REPLACE could silently delete a
        # different appointment's bill if bill_nos happen to collide).
        conn.execute("DELETE FROM bills WHERE appointment_id=?", (appointment_id,))
        conn.execute(
            """INSERT INTO bills
               (appointment_id,bill_no,total_days,total_double,total_qty,
                rate_single,rate_double,amount,extra_items,generated_at,pdf_path)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (appointment_id, bill_no, total_days, total_double, total_qty,
             rate_single, rate_double, amount, extra_items, now, pdf_path),
        )
        conn.execute("UPDATE appointments SET status='billed' WHERE id=?", (appointment_id,))
        lock_duties_for_appointment(appointment_id, conn)
        conn.commit()
        audit(conn, "bill_generate", f"Bill {bill_no} generated for appointment_id={appointment_id}")
        conn.commit()
    finally:
        conn.close()


def generate_bill_number(session_id, appointment_id=None):
    """Generate a unique bill number for the session.

    If appointment_id is supplied, excludes that appointment's existing bill
    from the count so re-generating doesn't inflate the sequence number.
    """
    conn = get_connection()
    try:
        if appointment_id is not None:
            count = conn.execute(
                """SELECT COUNT(*) FROM bills b
                   JOIN appointments a ON b.appointment_id=a.id
                   WHERE a.session_id=? AND b.appointment_id != ?""",
                (session_id, appointment_id),
            ).fetchone()[0]
        else:
            count = conn.execute(
                "SELECT COUNT(*) FROM bills b JOIN appointments a ON b.appointment_id=a.id WHERE a.session_id=?",
                (session_id,),
            ).fetchone()[0]
        from datetime import datetime as dt
        return f"IUB-{session_id:03d}-{dt.now().strftime('%Y%m%d')}-{(count+1):03d}"
    finally:
        conn.close()


# ── Rates ──────────────────────────────────────────────────────────────────────

def get_all_rates():
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM rates ORDER BY id").fetchall()
    finally:
        conn.close()


def update_rate(role, rate_single, rate_double):
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE rates SET rate_single=?, rate_double=?, updated_at=? WHERE role=?",
            (rate_single, rate_double, now, role),
        )
        conn.commit()
        audit(conn, "rate_change", f"Rate updated for {role}: single={rate_single} double={rate_double}")
        conn.commit()
    finally:
        conn.close()


# ── Audit ──────────────────────────────────────────────────────────────────────

def audit(conn, action, detail=""):
    conn.execute(
        "INSERT INTO audit_log (action,detail,created_at) VALUES (?,?,?)",
        (action, detail, datetime.now().isoformat()),
    )


# ── Delete helpers ─────────────────────────────────────────────────────────────

def delete_staff(staff_id):
    conn = get_connection()
    try:
        has_appts = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE staff_id=?",
            (staff_id,)
        ).fetchone()[0]
        if has_appts:
            raise ValueError("Cannot delete staff with existing appointments.")
        conn.execute("DELETE FROM staff WHERE id=?", (staff_id,))
        conn.commit()
        audit(conn, "staff_delete", f"Deleted staff id={staff_id}")
        conn.commit()
    finally:
        conn.close()


def delete_application(app_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM applications WHERE id=?", (app_id,))
        conn.commit()
        audit(conn, "app_delete", f"Deleted application id={app_id}")
        conn.commit()
    finally:
        conn.close()


def delete_appointment(appt_id):
    conn = get_connection()
    try:
        has_bill = conn.execute(
            "SELECT COUNT(*) FROM bills WHERE appointment_id=?",
            (appt_id,)
        ).fetchone()[0]
        if has_bill:
            raise ValueError("Cannot delete — bill already generated.")
        conn.execute("DELETE FROM duty_log WHERE appointment_id=?", (appt_id,))
        conn.execute("DELETE FROM appointments WHERE id=?", (appt_id,))
        conn.commit()
        audit(conn, "appt_delete", f"Deleted appointment id={appt_id}")
        conn.commit()
    finally:
        conn.close()


def delete_session(session_id):
    conn = get_connection()
    try:
        has_bills = conn.execute("""
            SELECT COUNT(*) FROM bills b
            JOIN appointments a ON b.appointment_id = a.id
            WHERE a.session_id = ?
        """, (session_id,)).fetchone()[0]
        if has_bills:
            raise ValueError("Cannot delete — bills have been generated.")
        conn.execute(
            "DELETE FROM duty_log WHERE appointment_id IN "
            "(SELECT id FROM appointments WHERE session_id=?)",
            (session_id,)
        )
        conn.execute("DELETE FROM appointments WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM exam_sessions WHERE id=?", (session_id,))
        conn.commit()
    finally:
        conn.close()


# ── Dashboard ─────────────────────────────────────────────────────────────────

def get_dashboard_stats():
    conn = get_connection()
    try:
        return {
            "sessions": conn.execute("SELECT COUNT(*) FROM exam_sessions").fetchone()[0],
            "staff":    conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0],
            "bills":    conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0],
            "amount":   conn.execute("SELECT COALESCE(SUM(amount),0) FROM bills").fetchone()[0],
        }
    finally:
        conn.close()


def get_recent_sessions(limit=5):
    conn = get_connection()
    try:
        sessions = conn.execute(
            "SELECT * FROM exam_sessions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for s in sessions:
            appt_count = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE session_id=?", (s["id"],)
            ).fetchone()[0]
            bill_count = conn.execute(
                "SELECT COUNT(*) FROM bills b JOIN appointments a ON b.appointment_id=a.id WHERE a.session_id=?",
                (s["id"],),
            ).fetchone()[0]
            total_amount = conn.execute(
                "SELECT COALESCE(SUM(b.amount),0) FROM bills b JOIN appointments a ON b.appointment_id=a.id WHERE a.session_id=?",
                (s["id"],),
            ).fetchone()[0]
            result.append({
                "session": s,
                "appt_count": appt_count,
                "bill_count": bill_count,
                "total_amount": total_amount,
            })
        return result
    finally:
        conn.close()


def get_billing_by_role():
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT a.role, COALESCE(SUM(b.amount), 0) AS total
               FROM bills b
               JOIN appointments a ON b.appointment_id = a.id
               GROUP BY a.role
               ORDER BY total DESC"""
        ).fetchall()
        return [{"role": r["role"], "total": r["total"]} for r in rows]
    finally:
        conn.close()


def get_dashboard_sessions():
    conn = get_connection()
    try:
        sessions = conn.execute(
            "SELECT * FROM exam_sessions ORDER BY id DESC LIMIT 3"
        ).fetchall()
        result = []
        for s in sessions:
            appt_count = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE session_id=?", (s["id"],)
            ).fetchone()[0]
            bill_count = conn.execute(
                "SELECT COUNT(*) FROM bills b JOIN appointments a ON b.appointment_id=a.id WHERE a.session_id=?",
                (s["id"],),
            ).fetchone()[0]
            total_amount = conn.execute(
                "SELECT COALESCE(SUM(b.amount),0) FROM bills b JOIN appointments a ON b.appointment_id=a.id WHERE a.session_id=?",
                (s["id"],),
            ).fetchone()[0]
            result.append({
                "session": s,
                "appt_count": appt_count,
                "bill_count": bill_count,
                "total_amount": total_amount,
            })
        return result
    finally:
        conn.close()


# ── Sample Data ────────────────────────────────────────────────────────────────

def seed_sample_data():
    conn = get_connection()
    try:
        existing = conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0]
        if existing > 0:
            return
        now = datetime.now().isoformat()
        staff_data = [
            ("Rana Muhammad Jameel", "31202-9722964-3", "0300-6171482",
             "Govt. S.E. Graduate College, Bahawalpur", "Assistant Professor",
             "Govt. S.E. Graduate College, Bahawalpur"),
            ("Muhammad Afzal Hameed", "33100-3498548-3", "0349-4440047",
             "GGC Satiana Road, Peoples Colony No.2, Faisalabad", "Principal",
             "GGC Satiana Road, Peoples Colony No.2, Faisalabad"),
            ("Anwar Ali Saqib", "31202-7127198-1", "0301-7732681",
             "Govt. Boys Secondary School, Bahawalpur", "SST",
             "Govt. Boys Secondary School, Bahawalpur"),
            ("Fatima Malik", "35202-1234567-8", "0300-1234567",
             "Govt. College, Bahawalpur", "Lecturer", "Govt. College, Bahawalpur"),
        ]
        ids = []
        for row in staff_data:
            cur = conn.execute(
                "INSERT OR IGNORE INTO staff (full_name,cnic,phone,address,designation,institution,created_at) VALUES (?,?,?,?,?,?,?)",
                (*row, now),
            )
            if cur.lastrowid:
                ids.append(cur.lastrowid)
            else:
                ids.append(conn.execute("SELECT id FROM staff WHERE cnic=?", (row[1],)).fetchone()[0])

        sess_cur = conn.execute(
            "INSERT INTO exam_sessions (session_name,programs,year,created_at) VALUES (?,?,?,?)",
            ("Annual Examination 2025", "BS Nursing, DPT, MLT, HND, POST RN", "2025", now),
        )
        session_id = sess_cur.lastrowid

        appointments = [
            (ids[0], "Resident Inspector",   "Govt. S.E. Graduate College, BWP", "No. 2385/Cond/Exam", "26-12-2025"),
            (ids[1], "Distributing Inspector","GGC Satiana Road, Faisalabad",     "No. 2389/Cond/Exam", "23-12-2025"),
            (ids[2], "Superintendent",        "Govt. Boys Secondary School, BWP", "No. 2316/Cond/Exam", "26-12-2025"),
            (ids[3], "Invigilator",           "Govt. College, Bahawalpur",        "No. 2390/Cond/Exam", "26-12-2025"),
        ]
        appt_ids = []
        for staff_id, role, centre, letter_no, letter_date in appointments:
            cur = conn.execute(
                "INSERT OR IGNORE INTO appointments (staff_id,session_id,role,centre,letter_no,letter_date,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (staff_id, session_id, role, centre, letter_no, letter_date, "appointed", now),
            )
            if cur.lastrowid:
                appt_ids.append(cur.lastrowid)
            else:
                row = conn.execute(
                    "SELECT id FROM appointments WHERE staff_id=? AND session_id=? AND role=?",
                    (staff_id, session_id, role),
                ).fetchone()
                appt_ids.append(row[0])

        # Resident Inspector: 12 single + 1 double
        ri_id = appt_ids[0]
        for i in range(1, 13):
            conn.execute(
                "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
                (ri_id, f"2025-12-{i+1:02d}", "Morning", "Single", now),
            )
        conn.execute(
            "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
            (ri_id, "2025-12-14", "Morning", "Double", now),
        )
        conn.execute(
            "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
            (ri_id, "2025-12-14", "Evening", "Double", now),
        )

        # Distributing Inspector: 12 single + 1 double
        di_id = appt_ids[1]
        for i in range(1, 13):
            conn.execute(
                "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
                (di_id, f"2025-12-{i+1:02d}", "Morning", "Single", now),
            )
        conn.execute(
            "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
            (di_id, "2025-12-14", "Morning", "Double", now),
        )
        conn.execute(
            "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
            (di_id, "2025-12-14", "Evening", "Double", now),
        )

        # Superintendent: 10 single + 1 double
        sup_id = appt_ids[2]
        for i in range(1, 11):
            conn.execute(
                "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
                (sup_id, f"2025-12-{i+1:02d}", "Morning", "Single", now),
            )
        conn.execute(
            "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
            (sup_id, "2025-12-12", "Morning", "Double", now),
        )
        conn.execute(
            "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
            (sup_id, "2025-12-12", "Evening", "Double", now),
        )

        # Invigilator: 8 single + 1 double
        inv_id = appt_ids[3]
        for i in range(1, 9):
            conn.execute(
                "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
                (inv_id, f"2025-12-{i+1:02d}", "Morning", "Single", now),
            )
        conn.execute(
            "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
            (inv_id, "2025-12-10", "Morning", "Double", now),
        )
        conn.execute(
            "INSERT INTO duty_log (appointment_id,duty_date,session,session_type,locked,created_at) VALUES (?,?,?,?,0,?)",
            (inv_id, "2025-12-10", "Evening", "Double", now),
        )

        conn.commit()
    finally:
        conn.close()


# ── Applications ───────────────────────────────────────────────────────────────

def get_all_applications(search="", status_filter=""):
    conn = get_connection()
    try:
        query = "SELECT * FROM applications WHERE 1=1"
        params = []
        if search:
            q = f"%{search}%"
            query += " AND (full_name LIKE ? OR cnic LIKE ? OR institution LIKE ?)"
            params.extend([q, q, q])
        if status_filter:
            query += " AND status=?"
            params.append(status_filter)
        query += " ORDER BY full_name"
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def get_application_by_id(app_id):
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    finally:
        conn.close()


def add_application(data: dict):
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        cur = conn.execute("""
            INSERT INTO applications (
                full_name, father_name, cnic, gender, ntn, tax_filer,
                qualification, post, basic_pay_scale, district,
                institution, residential_address, phone_office, phone_res,
                mobile, email, apply_for,
                exp_teaching_years, exp_teaching_inst,
                exp_supt_years, exp_supt_inst,
                exp_dy_supt_years, exp_dy_supt_inst,
                exp_invig_years, exp_invig_inst,
                proposed_station_1, proposed_station_2, proposed_station_3,
                status, created_at
            ) VALUES (
                :full_name, :father_name, :cnic, :gender, :ntn, :tax_filer,
                :qualification, :post, :basic_pay_scale, :district,
                :institution, :residential_address, :phone_office, :phone_res,
                :mobile, :email, :apply_for,
                :exp_teaching_years, :exp_teaching_inst,
                :exp_supt_years, :exp_supt_inst,
                :exp_dy_supt_years, :exp_dy_supt_inst,
                :exp_invig_years, :exp_invig_inst,
                :proposed_station_1, :proposed_station_2, :proposed_station_3,
                'applied', :created_at
            )
        """, {**data, "created_at": now})
        new_id = cur.lastrowid
        conn.commit()
        audit(conn, "application_add", f"Applied: {data.get('full_name')} ({data.get('cnic')})")
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_application_status(app_id, status):
    """Status values: applied, shortlisted, appointed, rejected"""
    conn = get_connection()
    try:
        conn.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))
        conn.commit()
        audit(conn, "application_status", f"app_id={app_id} status={status}")
        conn.commit()
    finally:
        conn.close()


def promote_application_to_staff(app_id):
    """
    Copy application data into the staff table.
    Returns the new staff_id, or the existing staff_id if CNIC already exists.
    """
    conn = get_connection()
    try:
        app = conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
        if not app:
            raise ValueError("Application not found.")
        now = datetime.now().isoformat()
        try:
            cur = conn.execute(
                "INSERT INTO staff (full_name,cnic,phone,address,designation,institution,created_at) VALUES (?,?,?,?,?,?,?)",
                (app["full_name"], app["cnic"], app["mobile"] or app["phone_res"] or "",
                 app["residential_address"] or "", app["post"] or "", app["institution"] or "", now)
            )
            staff_id = cur.lastrowid
        except Exception:
            staff_id = conn.execute("SELECT id FROM staff WHERE cnic=?", (app["cnic"],)).fetchone()[0]
        conn.execute("UPDATE applications SET status='appointed' WHERE id=?", (app_id,))
        conn.commit()
        audit(conn, "application_promoted", f"app_id={app_id} -> staff_id={staff_id}")
        conn.commit()
        return staff_id
    finally:
        conn.close()
