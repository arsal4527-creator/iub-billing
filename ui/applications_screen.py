import re
import customtkinter as ctk
from tkinter import messagebox, filedialog
from core.database import (
    get_all_applications, get_all_sessions, add_application,
    update_application_status, promote_application_to_staff,
    get_application_by_id, delete_application, get_connection,
)

IUB_GREEN = "#1a5276"
IUB_LIGHT = "#d6eaf8"
CNIC_RE   = re.compile(r"^\d{5}-\d{7}-\d$")

STATUS_COLORS = {
    "applied":     "#b7950b",
    "shortlisted": "#1a5276",
    "appointed":   "#1a8754",
    "rejected":    "#922b21",
}

ROLES = [
    "Resident Inspector", "Distributing Inspector", "Member Inspection Squad",
    "Superintendent", "Deputy Superintendent", "Invigilator", "Paper Checker",
]

APPLY_FOR_OPTIONS = ["Superintendent", "Deputy Superintendent", "Invigilator"]

PAGE_SIZE = 25


def _ensure_app_columns():
    """Add session_tag column to applications if it doesn't exist yet."""
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE applications ADD COLUMN session_tag TEXT")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


class ApplicationsScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._page = 0
        _ensure_app_columns()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=IUB_GREEN, corner_radius=0, height=60)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="Applications",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=15)
        ctk.CTkButton(hdr, text="+ New Application", width=150, height=34,
                      fg_color="white", text_color=IUB_GREEN,
                      hover_color=IUB_LIGHT,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._open_add).pack(side="right", padx=8, pady=12)
        ctk.CTkButton(hdr, text="Import CSV", width=110, height=34,
                      fg_color=IUB_LIGHT, text_color=IUB_GREEN,
                      hover_color="white",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._import_csv).pack(side="right", padx=8, pady=12)

        # Filter bar
        fbar = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=0)
        fbar.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(fbar, text="Search:",
                     font=ctk.CTkFont(size=11)).pack(
            side="left", padx=(16, 4), pady=10)
        self._debounce_id = None
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        ctk.CTkEntry(fbar, textvariable=self._search_var, width=220,
                     placeholder_text="Name or CNIC").pack(
            side="left", padx=4, pady=10)
        ctk.CTkLabel(fbar, text="Status:",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(16, 4))
        self._status_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(fbar, variable=self._status_var,
                          values=["All", "applied", "shortlisted", "appointed"],
                          width=130,
                          command=lambda _: self._reset_page()).pack(
            side="left", padx=4)

        # Table — 8 columns: Name, CNIC, Apply For, Institution, Mobile, Session, Status, Actions
        self._table = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._table.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)
        for col in range(8):
            self._table.grid_columnconfigure(col, weight=1)
        self._rows = []

        # Pagination bar
        pbar = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=0)
        pbar.grid(row=3, column=0, sticky="ew")
        self._prev_btn = ctk.CTkButton(
            pbar, text="← Prev", width=80, height=28,
            fg_color=IUB_GREEN, hover_color=IUB_LIGHT,
            text_color="white", font=ctk.CTkFont(size=10),
            command=self._prev_page)
        self._prev_btn.pack(side="left", padx=8, pady=6)
        self._page_label = ctk.CTkLabel(
            pbar, text="Page 1 of 1",
            font=ctk.CTkFont(size=10), text_color="gray")
        self._page_label.pack(side="left", padx=8)
        self._next_btn = ctk.CTkButton(
            pbar, text="Next →", width=80, height=28,
            fg_color=IUB_GREEN, hover_color=IUB_LIGHT,
            text_color="white", font=ctk.CTkFont(size=10),
            command=self._next_page)
        self._next_btn.pack(side="left", padx=8, pady=6)

    def _on_search_change(self, *_):
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(300, self._reset_page)

    def _reset_page(self):
        self._page = 0
        self.refresh()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self.refresh()

    def _next_page(self):
        self._page += 1
        self.refresh()

    def refresh(self):
        for w in self._rows:
            w.destroy()
        self._rows.clear()

        headers = ["Name", "CNIC", "Apply For", "Institution",
                   "Mobile", "Session", "Status", "Actions"]
        for col, h in enumerate(headers):
            f = ctk.CTkFrame(self._table, fg_color=IUB_GREEN, corner_radius=0)
            f.grid(row=0, column=col, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(f, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="white").pack(padx=6, pady=4)

        search = self._search_var.get().strip()
        status = self._status_var.get()
        all_apps = get_all_applications(
            search=search,
            status_filter="" if status == "All" else status
        )

        total = len(all_apps)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._page = min(self._page, total_pages - 1)
        start = self._page * PAGE_SIZE
        apps = all_apps[start:start + PAGE_SIZE]

        self._page_label.configure(
            text=f"Page {self._page + 1} of {total_pages}  ({total} total)")
        self._prev_btn.configure(state="normal" if self._page > 0 else "disabled")
        self._next_btn.configure(
            state="normal" if self._page < total_pages - 1 else "disabled")

        if not apps:
            lbl = ctk.CTkLabel(self._table, text="No applications found.",
                               font=ctk.CTkFont(size=11), text_color="gray")
            lbl.grid(row=1, column=0, columnspan=8, pady=20)
            self._rows.append(lbl)
            return

        for i, a in enumerate(apps):
            bg = IUB_LIGHT if i % 2 == 0 else "white"
            row_widgets = []
            a_dict = dict(a)

            for col, val in enumerate([
                a["full_name"], a["cnic"], a["apply_for"] or "—",
                a["institution"] or "—", a["mobile"] or "—",
                a_dict.get("session_tag") or "—",
            ]):
                f = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=0)
                f.grid(row=i + 1, column=col, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=10),
                             wraplength=130,
                             text_color="#111111").pack(padx=6, pady=4, anchor="w")
                row_widgets.append(f)

            # Status column
            sf = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=0)
            sf.grid(row=i + 1, column=6, sticky="ew", padx=1, pady=1)
            status_text = a["status"].capitalize()
            ctk.CTkLabel(sf, text=status_text,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=STATUS_COLORS.get(a["status"], "gray")
                         ).pack(padx=6, pady=4)
            row_widgets.append(sf)

            # Actions column
            af = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=0)
            af.grid(row=i + 1, column=7, sticky="ew", padx=1, pady=1)
            ctk.CTkButton(af, text="View", width=48, height=24,
                          font=ctk.CTkFont(size=9), fg_color=IUB_GREEN,
                          command=lambda aid=a["id"]: self._view(aid)
                          ).pack(side="left", padx=2, pady=4)

            if a["status"] == "applied":
                # Role dropdown + Shortlist button
                role_var = ctk.StringVar(value=ROLES[0])
                ctk.CTkOptionMenu(af, variable=role_var, values=ROLES,
                                  width=130, height=24,
                                  font=ctk.CTkFont(size=9)
                                  ).pack(side="left", padx=2, pady=4)
                ctk.CTkButton(af, text="Shortlist", width=64, height=24,
                              font=ctk.CTkFont(size=9), fg_color="#1a5276",
                              command=lambda aid=a["id"], rv=role_var: self._shortlist(aid, rv.get())
                              ).pack(side="left", padx=2, pady=4)
                ctk.CTkButton(af, text="Reject", width=50, height=24,
                              font=ctk.CTkFont(size=9), fg_color="#922b21",
                              command=lambda aid=a["id"]: self._set_status(aid, "rejected")
                              ).pack(side="left", padx=2, pady=4)
            elif a["status"] == "shortlisted":
                ctk.CTkButton(af, text="→ Staff", width=58, height=24,
                              font=ctk.CTkFont(size=9), fg_color="#1a8754",
                              command=lambda aid=a["id"]: self._promote(aid)
                              ).pack(side="left", padx=2, pady=4)

            ctk.CTkButton(af, text="Delete", width=50, height=24,
                          font=ctk.CTkFont(size=9), fg_color="#922b21",
                          command=lambda aid=a["id"], name=a["full_name"]: self._delete(aid, name)
                          ).pack(side="left", padx=2, pady=4)
            row_widgets.append(af)
            self._rows.extend(row_widgets)

    # ── Actions ────────────────────────────────────────────────────────────────

    def _shortlist(self, app_id, role):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE applications SET status=?, apply_for=? WHERE id=?",
                ("shortlisted", role, app_id))
            conn.commit()
        finally:
            conn.close()
        self.refresh()

    def _set_status(self, app_id, status):
        update_application_status(app_id, status)
        self.refresh()

    def _promote(self, app_id):
        try:
            staff_id = promote_application_to_staff(app_id)
            messagebox.showinfo(
                "Promoted",
                f"Application moved to Staff Register (staff ID: {staff_id}).\n"
                "You can now appoint them from the Sessions screen.",
                parent=self)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _delete(self, app_id, name):
        if not messagebox.askyesno(
                "Confirm Delete",
                f"Delete the application for {name}? This cannot be undone.",
                parent=self):
            return
        try:
            delete_application(app_id)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _view(self, app_id):
        a = get_application_by_id(app_id)
        if a:
            _ApplicationForm(self, dict(a))

    def _open_add(self):
        _ApplicationForm(self, None)

    def on_saved(self):
        self.refresh()

    # ── CSV Import ─────────────────────────────────────────────────────────────

    def _import_csv(self):
        sessions = get_all_sessions()
        _SessionPickerDialog(self, sessions, self._pick_file_and_import)

    def _pick_file_and_import(self, session_tag):
        path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            parent=self)
        if not path:
            return
        try:
            from core.sheets_importer import import_from_csv_file
            imported, skipped, error = import_from_csv_file(path, session_tag=session_tag)
        except Exception as e:
            messagebox.showerror("Import Error", str(e), parent=self)
            return
        if error:
            messagebox.showerror("Import Error", error, parent=self)
            return
        messagebox.showinfo(
            "Import Complete",
            f"Session: {session_tag}\n\nImported: {imported}\n"
            f"Skipped (duplicate or invalid): {skipped}",
            parent=self)
        self.refresh()


# ── Session Picker Dialog ──────────────────────────────────────────────────────

class _SessionPickerDialog(ctk.CTkToplevel):
    def __init__(self, parent_screen, sessions, on_confirm):
        super().__init__()
        self.parent_screen = parent_screen
        self.sessions      = sessions
        self.on_confirm    = on_confirm
        self.title("Select Session for Import")
        self.geometry("440x240")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=16)
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Which session is this import for?",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=0, column=0, columnspan=2, pady=(0, 12))

        session_names = [s["session_name"] for s in self.sessions]
        ctk.CTkLabel(f, text="Existing session:",
                     font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", pady=4)
        self._sess_var = ctk.StringVar(value=session_names[0] if session_names else "")
        self._sess_menu = ctk.CTkOptionMenu(
            f, variable=self._sess_var,
            values=session_names or ["(No sessions yet)"],
            width=260)
        self._sess_menu.grid(row=1, column=1, padx=8, pady=4)

        ctk.CTkLabel(f, text="Or new session:",
                     font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="w", pady=4)
        self._new_var = ctk.StringVar()
        ctk.CTkEntry(f, textvariable=self._new_var, width=260,
                     placeholder_text="Type a new session name...").grid(
            row=2, column=1, padx=8, pady=4)

        btn_f = ctk.CTkFrame(f, fg_color="transparent")
        btn_f.grid(row=3, column=0, columnspan=2, pady=14)
        ctk.CTkButton(btn_f, text="Select File & Import",
                      fg_color=IUB_GREEN,
                      command=self._confirm).pack(side="left", padx=8)
        ctk.CTkButton(btn_f, text="Cancel", fg_color="gray",
                      command=self.destroy).pack(side="left")

    def _confirm(self):
        new = self._new_var.get().strip()
        tag = new if new else self._sess_var.get().strip()
        if not tag or tag == "(No sessions yet)":
            messagebox.showerror("Validation",
                                  "Please select or enter a session name.", parent=self)
            return
        self.destroy()
        self.on_confirm(tag)


# ── Application Form ───────────────────────────────────────────────────────────

class _ApplicationForm(ctk.CTkToplevel):
    """Full application form matching the IUB Invigilation Performa fields."""

    def __init__(self, parent_screen, existing=None):
        super().__init__()
        self.parent   = parent_screen
        self.existing = existing
        self.title("View Application" if existing else "New Application")
        self.geometry("620x700")
        self.resizable(True, True)
        self.grab_set()
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=16)
        scroll.grid_columnconfigure(1, weight=1)
        scroll.grid_columnconfigure(3, weight=1)

        e = self.existing or {}
        readonly = self.existing is not None

        def field(row, col, label, key, width=200, col_span=1):
            ctk.CTkLabel(scroll, text=label,
                         font=ctk.CTkFont(size=10)).grid(
                row=row, column=col * 2, sticky="w", padx=6, pady=3)
            var = ctk.StringVar(value=str(e.get(key, "") or ""))
            entry = ctk.CTkEntry(scroll, textvariable=var, width=width,
                                  state="disabled" if readonly else "normal")
            entry.grid(row=row, column=col * 2 + 1, padx=6, pady=3,
                       sticky="ew", columnspan=col_span)
            return var

        # Apply For
        ctk.CTkLabel(scroll, text="Apply For *",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=0, column=0, sticky="w", padx=6, pady=(6, 2))
        self._apply_var = ctk.StringVar(
            value=e.get("apply_for", APPLY_FOR_OPTIONS[0]))
        if not readonly:
            ctk.CTkOptionMenu(scroll, variable=self._apply_var,
                              values=APPLY_FOR_OPTIONS, width=200).grid(
                row=0, column=1, padx=6, pady=3, sticky="w")
        else:
            ctk.CTkLabel(scroll, text=e.get("apply_for", ""),
                         font=ctk.CTkFont(size=10)).grid(
                row=0, column=1, sticky="w", padx=6)

        self._vars = {}
        self._vars["full_name"]    = field(1, 0, "Full Name *",             "full_name")
        self._vars["father_name"]  = field(1, 1, "Father's Name",           "father_name")
        self._vars["cnic"]         = field(2, 0, "CNIC *",                  "cnic")
        self._vars["gender"]       = field(2, 1, "Gender",                  "gender",         width=100)
        self._vars["ntn"]          = field(3, 0, "NTN #",                   "ntn")
        self._vars["tax_filer"]    = field(3, 1, "Tax Filer (1=Yes, 0=No)", "tax_filer",      width=100)
        self._vars["qualification"]= field(4, 0, "Qualification",           "qualification")
        self._vars["post"]         = field(4, 1, "Post/Designation",        "post")
        self._vars["basic_pay_scale"] = field(5, 0, "Basic Pay Scale",      "basic_pay_scale")
        self._vars["district"]     = field(5, 1, "District",                "district")
        self._vars["institution"]  = field(6, 0, "Institution",             "institution",    width=400, col_span=3)
        self._vars["residential_address"] = field(7, 0, "Residential Address", "residential_address", width=400, col_span=3)
        self._vars["phone_office"] = field(8, 0, "Phone (Office)",          "phone_office")
        self._vars["phone_res"]    = field(8, 1, "Phone (Res)",             "phone_res")
        self._vars["mobile"]       = field(9, 0, "Mobile (WhatsApp)",       "mobile")
        self._vars["email"]        = field(9, 1, "Email",                   "email")

        # Experience
        ctk.CTkLabel(scroll, text="Experience",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=10, column=0, sticky="w", padx=6, pady=(10, 2), columnspan=4)
        for r, (label, yr_key, inst_key) in enumerate([
            ("Teaching",       "exp_teaching_years", "exp_teaching_inst"),
            ("Superintendent", "exp_supt_years",     "exp_supt_inst"),
            ("Deputy Supt.",   "exp_dy_supt_years",  "exp_dy_supt_inst"),
            ("Invigilator",    "exp_invig_years",    "exp_invig_inst"),
        ], start=11):
            ctk.CTkLabel(scroll, text=label,
                         font=ctk.CTkFont(size=10)).grid(
                row=r, column=0, sticky="w", padx=6, pady=2)
            yr_var   = ctk.StringVar(value=str(e.get(yr_key,   0) or 0))
            inst_var = ctk.StringVar(value=str(e.get(inst_key, "") or ""))
            ctk.CTkEntry(scroll, textvariable=yr_var, width=60,
                         placeholder_text="Yrs",
                         state="disabled" if readonly else "normal").grid(
                row=r, column=1, padx=4, pady=2, sticky="w")
            ctk.CTkEntry(scroll, textvariable=inst_var, width=280,
                         placeholder_text="Last institution",
                         state="disabled" if readonly else "normal").grid(
                row=r, column=2, padx=4, pady=2, sticky="ew", columnspan=2)
            self._vars[yr_key]   = yr_var
            self._vars[inst_key] = inst_var

        # Proposed stations
        ctk.CTkLabel(scroll, text="Proposed Stations",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=15, column=0, sticky="w", padx=6, pady=(10, 2), columnspan=4)
        self._vars["proposed_station_1"] = field(16, 0, "Station 1", "proposed_station_1")
        self._vars["proposed_station_2"] = field(16, 1, "Station 2", "proposed_station_2")
        self._vars["proposed_station_3"] = field(17, 0, "Station 3", "proposed_station_3")

        if not readonly:
            btn_f = ctk.CTkFrame(scroll, fg_color="transparent")
            btn_f.grid(row=18, column=0, columnspan=4, pady=16)
            ctk.CTkButton(btn_f, text="Submit Application",
                          fg_color=IUB_GREEN,
                          command=self._save).pack(side="left", padx=8)
            ctk.CTkButton(btn_f, text="Cancel", fg_color="gray",
                          command=self.destroy).pack(side="left")
        else:
            ctk.CTkButton(scroll, text="Close", fg_color="gray",
                          command=self.destroy).grid(
                row=18, column=0, columnspan=4, pady=16)

    def _save(self):
        vals = {k: v.get().strip() for k, v in self._vars.items()}
        vals["apply_for"] = self._apply_var.get()

        if not vals.get("full_name"):
            messagebox.showerror("Validation", "Full Name is required.", parent=self)
            return
        cnic = vals.get("cnic", "")
        if not re.match(r"^\d{5}-\d{7}-\d$", cnic):
            messagebox.showerror("Validation",
                                  "CNIC must be in format XXXXX-XXXXXXX-X",
                                  parent=self)
            return
        for k in ("exp_teaching_years", "exp_supt_years",
                  "exp_dy_supt_years", "exp_invig_years"):
            try:
                vals[k] = int(vals.get(k, 0) or 0)
            except ValueError:
                vals[k] = 0
        try:
            vals["tax_filer"] = int(vals.get("tax_filer", 0) or 0)
        except ValueError:
            vals["tax_filer"] = 0

        try:
            add_application(vals)
            self.parent.on_saved()
            self.destroy()
        except Exception as ex:
            if "UNIQUE" in str(ex):
                messagebox.showerror(
                    "Duplicate CNIC",
                    "An application with this CNIC already exists.", parent=self)
            else:
                messagebox.showerror("Error", str(ex), parent=self)
