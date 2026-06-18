# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Desktop billing application for the Examinations Branch of The Islamia University of Bahawalpur (IUB). It tracks examination staff, their per-session appointments and duties, then generates official remuneration bills (PDF) and session exports (Excel). It is a single-user, local-first desktop app built with `customtkinter` (Tkinter) on top of a local SQLite database — there is no server, network, or auth backend beyond an optional local PIN gate on the billing section.

## Commands

```bash
# Setup (Python 3.11+ recommended)
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the app (creates/seeds iub_billing.db on first launch)
python main.py
```

There is no test suite, linter, or build configuration in this repo. The app is run directly; it requires a display (Tkinter GUI) and cannot run headless.

## Architecture

Two layers, strictly separated:

- **`core/`** — all data and document logic. No GUI imports. Every DB call goes through `core/database.py`.
- **`ui/`** — `customtkinter` screens. Screens call `core` functions; they never write SQL directly.

`main.py` initializes the schema (`init_db`), seeds sample data on a fresh DB (`seed_sample_data`), then launches `ui.app.App`.

### Database (`core/database.py`)

- Single SQLite file `iub_billing.db` at the repo root (gitignored — **never commit it**). WAL mode, foreign keys ON.
- The full schema lives in the `SCHEMA` string and is applied idempotently with `CREATE TABLE IF NOT EXISTS`. **There is no migration framework.** Additive column changes are done by ad-hoc functions like `_migrate_applications()` (PRAGMA `table_info` check + `ALTER TABLE`) called from `init_db()`. Follow that pattern for new columns; do not assume a table-rebuild is safe.
- Every public function opens its own connection via `get_connection()` and closes it in a `finally`. Mutations call `audit(conn, action, detail)` to write the `audit_log`, then commit. Preserve this per-call connection + audit convention.
- `INITIAL_RATES` seeds the `rates` table (role → `rate_single`, `rate_double`, `unit`). Rates are editable at runtime via Settings.

### Data model & flow

The core entity chain is:

```
applications ──(promote/appoint)──> staff ──> appointments ──> duty_log ──> bills
                                                  (per exam_session)
```

- **applications** — prospective staff imported from CSV (e.g. Google Form exports). Status: `applied` → `shortlisted` → `appointed` / `rejected`. Promoted into `staff` (by CNIC) via `promote_application_to_staff` or `appoint_from_application`.
- **staff** — people, uniquely keyed by `cnic`.
- **exam_sessions** — an exam period (e.g. "Annual Examination 2025").
- **appointments** — a staff member's role at a centre for one session. `UNIQUE(staff_id, session_id, role)`.
- **duty_log** — individual duty rows. Each row has a `session_type` of `Single` or `Double`. Rows get `locked=1` once a bill is generated and can no longer be edited/deleted.
- **bills** — one bill per appointment (`appointment_id` UNIQUE). Generating a bill flips the appointment status to `billed` and locks its duties.

### Billing logic (`core/billing_engine.py`)

`calculate_bill(appointment_id, extra_items)` is the single source of truth for amounts. Key rules:

- Rate `unit == "per_script"` (Paper Checker): amount = number of duty rows × `rate_single`.
- Otherwise (`per_session`): **singles** = count of `Single` rows; **doubles** = count of *unique dates* having `Double` rows (a Morning+Evening Double on the same date is stored as two rows but bills as **one** double unit). `amount = singles*rate_single + doubles*rate_double`.
- **Superintendent** bills add contingent items (`collection_qp`, `dispatch_ab`, `menial`, `stationery`, `ice`) and subtract `advance`, passed via `extra_items` and persisted as JSON in `bills.extra_items`.

When changing amount math, update both `calculate_bill` and the corresponding PDF template so the printed breakdown matches the stored total.

### Document generation

- **`core/pdf_generator.py`** — `generate_bill_pdf(...)` dispatches by role to one of four ReportLab templates: `generate_inspector_bill` (`INSPECTOR_ROLES`), `generate_form95a_bill` (`FORM95A_ROLES` — Invigilator/Deputy Superintendent), `generate_superintendent_bill`, `generate_paper_checker_bill`. Also generates appointment letters. Output goes to `outputs/` (gitignored).
- **`core/excel_exporter.py`** — `export_session_excel` and `export_staff_roster` produce styled `openpyxl` workbooks into `outputs/`.
- **`core/sheets_importer.py`** — `import_from_csv_file(filepath, session_id)` maps messy CSV headers to DB fields via `COLUMN_MAP` (prefix match, case-insensitive), normalizes CNIC to `#####-#######-#` and `tax_filer` to 0/1, and dedupes by CNIC. Add new accepted column header spellings to `COLUMN_MAP`.

### UI (`ui/`)

- `ui/app.py` `App` builds a fixed sidebar and instantiates **all** screens once into a stacked content frame; navigation just calls `tkraise()`. Screens are keyed: `dashboard`, `applications`, `staff`, `sessions`, `duties`, `billing`, `reports`, `settings`.
- Each screen is a `ctk.CTkFrame` subclass given `(parent, app)`. Two optional hooks the framework calls: `refresh()` (invoked every time the screen is shown — reload data here) and `set_context(**kwargs)` (invoked when navigated to via `app.navigate(key, **kwargs)` to pass state, e.g. a selected session). New screens should follow this `refresh()`/`set_context()` contract.
- The **billing screen is PIN-gated**: if `has_billing_pin()` is true, `refresh()` shows a lock prompt and only reveals content after `verify_billing_pin(pin)`. PINs are PBKDF2-HMAC-SHA256 hashed (`set_billing_pin`/`verify_billing_pin` in `core/database.py`); set/changed in Settings.
- Brand colors (`IUB_GREEN = #1a5276`, etc.) are repeated in `ui/app.py`, `core/pdf_generator.py`, and `core/excel_exporter.py` — keep them consistent if restyling.

## Conventions

- Pure-Python only; no ORM. Stick to parameterized `sqlite3` queries through `core.database`.
- Deletes are guarded by referential checks that raise `ValueError` (e.g. can't delete staff with appointments, an appointment with a bill, or a session with bills). Surface these as user-facing messages, don't suppress them.
- `cnic` is the natural key for people across `applications` and `staff` — dedupe and look up by it.
