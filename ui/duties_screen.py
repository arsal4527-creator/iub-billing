import re
import customtkinter as ctk
from tkinter import messagebox
from core.database import (
    get_all_sessions, get_appointments_for_session,
    get_duties_for_appointment, add_duty, delete_duty, is_appointment_locked,
    get_connection,
)

IUB_GREEN  = "#1a5276"
IUB_LIGHT  = "#d6eaf8"
DATE_RE    = re.compile(r"^\d{2}-\d{2}-\d{4}$")

SESSIONS      = ["Morning", "Evening"]
SESSION_TYPES = ["Single", "Double"]


class DutiesScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._appt_id = None
        self._locked = False
        self._sessions_data = {}
        self._current_session_id = None
        self._appts_data = {}
        self._grp_appts = []
        self._mode = "individual"
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Row 0: Header
        hdr = ctk.CTkFrame(self, fg_color=IUB_GREEN, corner_radius=0, height=60)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="Duty Entry",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=15)

        # Row 1: Mode toggle
        tbar = ctk.CTkFrame(self, fg_color=("gray85", "gray20"), corner_radius=0, height=40)
        tbar.grid(row=1, column=0, sticky="ew")
        tbar.grid_propagate(False)
        self._indiv_btn = ctk.CTkButton(
            tbar, text="Individual Entry", width=140, height=28,
            fg_color=IUB_GREEN, text_color="white",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._show_individual)
        self._indiv_btn.pack(side="left", padx=(12, 4), pady=6)
        self._grp_mode_btn = ctk.CTkButton(
            tbar, text="Group Entry", width=120, height=28,
            fg_color="transparent", text_color=IUB_GREEN,
            font=ctk.CTkFont(size=11),
            command=self._show_group_entry)
        self._grp_mode_btn.pack(side="left", padx=4, pady=6)

        # Row 2: Session selector (shared between both modes)
        sel = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=0)
        sel.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(sel, text="Session:",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(16, 4), pady=10)
        self._sess_var = ctk.StringVar()
        self._sess_menu = ctk.CTkOptionMenu(
            sel, variable=self._sess_var, values=[], width=240,
            command=self._on_session_change)
        self._sess_menu.pack(side="left", padx=4, pady=10)

        # Row 3: Body — both panels live here, one shown at a time
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_individual_panel(body)
        self._build_group_panel(body)

    def _build_individual_panel(self, body):
        self._indiv_panel = ctk.CTkFrame(body, fg_color="transparent")
        self._indiv_panel.grid(row=0, column=0, sticky="nsew")
        self._indiv_panel.grid_columnconfigure(0, weight=1)
        self._indiv_panel.grid_rowconfigure(2, weight=1)

        # Appointment selector
        asel = ctk.CTkFrame(self._indiv_panel, fg_color=("gray90", "gray20"), corner_radius=0)
        asel.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(asel, text="Appointment:",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(16, 4), pady=10)
        self._appt_var = ctk.StringVar()
        self._appt_menu = ctk.CTkOptionMenu(
            asel, variable=self._appt_var, values=[], width=300,
            command=self._on_appt_change)
        self._appt_menu.pack(side="left", padx=4, pady=10)

        # Lock banner
        self._lock_banner = ctk.CTkFrame(
            self._indiv_panel, fg_color="#f9ebea", corner_radius=0, height=36)
        self._lock_banner.grid(row=1, column=0, sticky="ew")
        self._lock_banner.grid_propagate(False)
        ctk.CTkLabel(self._lock_banner,
                     text="🔒  LOCKED — Bill has been generated. Duties cannot be edited.",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#922b21").pack(pady=8)
        self._lock_banner.grid_remove()

        # Duty table + add form
        inner = ctk.CTkFrame(self._indiv_panel, fg_color="transparent")
        inner.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_rowconfigure(0, weight=1)

        self._duty_table = ctk.CTkScrollableFrame(
            inner, label_text="Duty Records",
            label_font=ctk.CTkFont(size=12, weight="bold"))
        self._duty_table.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        for col in range(5):
            self._duty_table.grid_columnconfigure(col, weight=1)

        self._form = ctk.CTkFrame(inner, border_width=1,
                                   border_color="#d5d8dc", corner_radius=8)
        self._form.grid(row=1, column=0, sticky="ew")
        self._form.grid_columnconfigure((1, 3, 5), weight=1)
        self._build_form()

    def _build_group_panel(self, body):
        self._group_panel = ctk.CTkFrame(body, fg_color="transparent")
        self._group_panel.grid(row=0, column=0, sticky="nsew")
        self._group_panel.grid_columnconfigure(0, weight=1)
        self._group_panel.grid_rowconfigure(2, weight=1)
        self._group_panel.grid_remove()

        # Group controls row
        gctl = ctk.CTkFrame(self._group_panel, fg_color=("gray90", "gray20"), corner_radius=0)
        gctl.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(gctl, text="Role:",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(16, 4), pady=10)
        self._grp_role_var = ctk.StringVar(value="")
        self._grp_role_menu = ctk.CTkOptionMenu(
            gctl, variable=self._grp_role_var,
            values=["(select session first)"],
            width=220, command=self._on_group_role_change)
        self._grp_role_menu.pack(side="left", padx=4, pady=10)

        ctk.CTkLabel(gctl, text="Date:",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(16, 4))
        self._grp_date_var = ctk.StringVar()
        ctk.CTkEntry(gctl, textvariable=self._grp_date_var, width=110,
                     placeholder_text="dd-mm-yyyy").pack(side="left", padx=4, pady=10)

        ctk.CTkLabel(gctl, text="Session:",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(12, 4))
        self._grp_sess_var = ctk.StringVar(value="Morning")
        ctk.CTkOptionMenu(gctl, variable=self._grp_sess_var,
                          values=SESSIONS, width=110).pack(side="left", padx=4, pady=10)

        ctk.CTkLabel(gctl, text="Type:",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(12, 4))
        self._grp_type_var = ctk.StringVar(value="Single")
        ctk.CTkOptionMenu(gctl, variable=self._grp_type_var,
                          values=SESSION_TYPES, width=110).pack(side="left", padx=4, pady=10)

        # Preview label
        plbl_frame = ctk.CTkFrame(self._group_panel, fg_color="transparent")
        plbl_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 2))
        self._grp_preview_label = ctk.CTkLabel(
            plbl_frame,
            text="Select a session and role to preview affected appointments.",
            font=ctk.CTkFont(size=11), text_color="gray")
        self._grp_preview_label.pack(anchor="w")

        # Preview table
        self._grp_preview = ctk.CTkScrollableFrame(
            self._group_panel, label_text="Affected Appointments",
            label_font=ctk.CTkFont(size=11, weight="bold"),
            height=220)
        self._grp_preview.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        for c in range(3):
            self._grp_preview.grid_columnconfigure(c, weight=1)

        # Add Duty for All button
        self._grp_add_btn = ctk.CTkButton(
            self._group_panel, text="Add Duty for All",
            fg_color=IUB_GREEN, height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._group_add_duties)
        self._grp_add_btn.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")

    def _build_form(self):
        f = self._form
        ctk.CTkLabel(f, text="Date (dd-mm-yyyy):",
                     font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, padx=10, pady=10)
        self._date_var = ctk.StringVar()
        ctk.CTkEntry(f, textvariable=self._date_var, width=120,
                     placeholder_text="29-12-2025").grid(
            row=0, column=1, padx=4, pady=10)

        ctk.CTkLabel(f, text="Session:",
                     font=ctk.CTkFont(size=11)).grid(
            row=0, column=2, padx=(12, 4), pady=10)
        self._session_var = ctk.StringVar(value="Morning")
        ctk.CTkOptionMenu(f, variable=self._session_var,
                           values=SESSIONS, width=120).grid(
            row=0, column=3, padx=4)

        ctk.CTkLabel(f, text="Type:",
                     font=ctk.CTkFont(size=11)).grid(
            row=0, column=4, padx=(12, 4), pady=10)
        self._type_var = ctk.StringVar(value="Single")
        ctk.CTkOptionMenu(f, variable=self._type_var,
                           values=SESSION_TYPES, width=120).grid(
            row=0, column=5, padx=4)

        self._add_btn = ctk.CTkButton(f, text="Add Duty", width=100,
                                       fg_color=IUB_GREEN,
                                       command=self._add_duty)
        self._add_btn.grid(row=0, column=6, padx=12, pady=10)

    # ── Mode toggle ───────────────────────────────────────────────────────────

    def _show_individual(self):
        self._mode = "individual"
        self._indiv_btn.configure(fg_color=IUB_GREEN, text_color="white",
                                   font=ctk.CTkFont(size=11, weight="bold"))
        self._grp_mode_btn.configure(fg_color="transparent", text_color=IUB_GREEN,
                                      font=ctk.CTkFont(size=11))
        self._group_panel.grid_remove()
        self._indiv_panel.grid()

    def _show_group_entry(self):
        self._mode = "group"
        self._grp_mode_btn.configure(fg_color=IUB_GREEN, text_color="white",
                                      font=ctk.CTkFont(size=11, weight="bold"))
        self._indiv_btn.configure(fg_color="transparent", text_color=IUB_GREEN,
                                   font=ctk.CTkFont(size=11))
        self._indiv_panel.grid_remove()
        self._group_panel.grid()
        if self._current_session_id:
            self._on_group_role_change(self._grp_role_var.get())

    # ── Session / appointment loading ─────────────────────────────────────────

    def refresh(self):
        self._load_sessions()

    def set_context(self, **_):
        pass

    def _load_sessions(self):
        sessions = get_all_sessions()
        names = [s["session_name"] for s in sessions]
        self._sessions_data = {s["session_name"]: s["id"] for s in sessions}
        self._sess_menu.configure(values=names or ["No sessions"])
        if names:
            self._sess_var.set(names[0])
            self._on_session_change(names[0])

    def _on_session_change(self, name):
        sid = self._sessions_data.get(name)
        if not sid:
            return
        self._current_session_id = sid

        # Update individual mode appointment list
        appts = get_appointments_for_session(sid)
        self._appts_data = {}
        labels = []
        for a in appts:
            label = f"{a['full_name']} — {a['role']}"
            self._appts_data[label] = a["id"]
            labels.append(label)
        self._appt_menu.configure(values=labels or ["No appointments"])
        if labels:
            self._appt_var.set(labels[0])
            self._on_appt_change(labels[0])
        else:
            self._appt_var.set("")
            self._render_duties([])

        # Update group mode role dropdown
        conn = get_connection()
        try:
            roles = conn.execute(
                "SELECT DISTINCT role FROM appointments WHERE session_id=? ORDER BY role",
                (sid,)
            ).fetchall()
        finally:
            conn.close()
        role_list = [r["role"] for r in roles]
        self._grp_role_menu.configure(values=role_list or ["No appointments"])
        if role_list:
            self._grp_role_var.set(role_list[0])
            self._on_group_role_change(role_list[0])
        else:
            self._grp_role_var.set("")
            self._grp_appts = []
            self._render_group_preview()

    def _on_appt_change(self, label):
        aid = self._appts_data.get(label)
        if not aid:
            return
        self._appt_id = aid
        self._locked = is_appointment_locked(aid)
        if self._locked:
            self._lock_banner.grid()
            self._form.grid_remove()
        else:
            self._lock_banner.grid_remove()
            self._form.grid()
        duties = get_duties_for_appointment(aid)
        self._render_duties(duties)

    # ── Group entry ───────────────────────────────────────────────────────────

    def _on_group_role_change(self, role):
        if not self._current_session_id or not role or role in (
                "", "(select session first)", "No appointments"):
            return
        conn = get_connection()
        try:
            appts = conn.execute(
                "SELECT a.id, s.full_name, s.cnic "
                "FROM appointments a JOIN staff s ON a.staff_id=s.id "
                "WHERE a.session_id=? AND a.role=? ORDER BY s.full_name",
                (self._current_session_id, role)
            ).fetchall()
        finally:
            conn.close()
        self._grp_appts = [dict(a) for a in appts]
        self._render_group_preview()

    def _render_group_preview(self):
        for w in self._grp_preview.winfo_children():
            w.destroy()
        appts = self._grp_appts
        if not appts:
            self._grp_preview_label.configure(
                text="No appointments found for this role.", text_color="gray")
            ctk.CTkLabel(self._grp_preview, text="No appointments.",
                         font=ctk.CTkFont(size=10), text_color="gray").grid(
                row=0, column=0, columnspan=3, pady=12)
            return

        locked_ids = {a["id"] for a in appts if is_appointment_locked(a["id"])}
        eligible = len(appts) - len(locked_ids)
        self._grp_preview_label.configure(
            text=f"This will add a duty to {eligible} appointment(s) "
                 f"({len(locked_ids)} locked — will be skipped).",
            text_color=IUB_GREEN if eligible > 0 else "gray")

        for ci, ch in enumerate(["Name", "CNIC", "Status"]):
            fr = ctk.CTkFrame(self._grp_preview, fg_color=IUB_GREEN, corner_radius=0)
            fr.grid(row=0, column=ci, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(fr, text=ch, font=ctk.CTkFont(size=9, weight="bold"),
                         text_color="white").pack(padx=6, pady=3)

        for j, a in enumerate(appts):
            bg = IUB_LIGHT if j % 2 == 0 else "white"
            is_locked = a["id"] in locked_ids
            status_text  = "Locked" if is_locked else "Will Add"
            status_color = "#922b21" if is_locked else "#1a8754"
            for ci, val in enumerate([a["full_name"], a["cnic"], status_text]):
                fr = ctk.CTkFrame(self._grp_preview, fg_color=bg, corner_radius=0)
                fr.grid(row=j + 1, column=ci, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(fr, text=val, font=ctk.CTkFont(size=10),
                             text_color=status_color if ci == 2 else "#111111",
                             wraplength=180).pack(padx=6, pady=3, anchor="w")

    def _group_add_duties(self):
        if not self._current_session_id:
            messagebox.showinfo("Select Session", "Please select a session first.",
                                parent=self)
            return
        role = self._grp_role_var.get()
        if not role or role in ("(select session first)", "No appointments"):
            messagebox.showinfo("Select Role", "Please select a role.", parent=self)
            return
        date = self._grp_date_var.get().strip()
        parts = date.split("-")
        if len(parts) == 3:
            try:
                d, m, y = parts
                date = f"{int(d):02d}-{int(m):02d}-{y.zfill(4)}"
                self._grp_date_var.set(date)
            except ValueError:
                pass
        if not DATE_RE.match(date):
            messagebox.showerror("Validation", "Date must be in format dd-mm-yyyy",
                                  parent=self)
            return
        session_val = self._grp_sess_var.get()
        type_val    = self._grp_type_var.get()
        added = skipped = 0
        for a in self._grp_appts:
            if is_appointment_locked(a["id"]):
                skipped += 1
                continue
            try:
                add_duty(a["id"], date, session_val, type_val)
                added += 1
            except Exception:
                skipped += 1
        self._grp_date_var.set("")
        self._on_group_role_change(role)
        messagebox.showinfo(
            "Done",
            f"Added {added} duty record(s). Skipped {skipped} (locked or duplicate).",
            parent=self)

    # ── Individual duty table ─────────────────────────────────────────────────

    def _render_duties(self, duties):
        for w in self._duty_table.winfo_children():
            w.destroy()
        headers = ["Date", "Session", "Type", "Locked", "Action"]
        for col, h in enumerate(headers):
            fr = ctk.CTkFrame(self._duty_table, fg_color=IUB_GREEN, corner_radius=0)
            fr.grid(row=0, column=col, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(fr, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="white").pack(padx=6, pady=4)
        if not duties:
            ctk.CTkLabel(self._duty_table, text="No duties logged yet.",
                         font=ctk.CTkFont(size=11),
                         text_color="gray").grid(
                row=1, column=0, columnspan=5, pady=16)
            return
        for i, d in enumerate(duties):
            bg = IUB_LIGHT if i % 2 == 0 else "white"
            for col, val in enumerate([d["duty_date"], d["session"], d["session_type"],
                                        "Yes" if d["locked"] else "No"]):
                fr = ctk.CTkFrame(self._duty_table, fg_color=bg, corner_radius=0)
                fr.grid(row=i + 1, column=col, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(fr, text=val, font=ctk.CTkFont(size=10),
                             text_color="#111111").pack(padx=6, pady=4)
            af = ctk.CTkFrame(self._duty_table, fg_color=bg, corner_radius=0)
            af.grid(row=i + 1, column=4, sticky="ew", padx=1, pady=1)
            if not d["locked"]:
                ctk.CTkButton(af, text="Delete", width=60, height=24,
                              fg_color="#922b21", font=ctk.CTkFont(size=9),
                              command=lambda did=d["id"]: self._delete_duty(did)
                              ).pack(padx=6, pady=4)

    def _normalize_date(self):
        raw = self._date_var.get().strip()
        parts = raw.split("-")
        if len(parts) == 3:
            try:
                d, m, y = parts
                self._date_var.set(f"{int(d):02d}-{int(m):02d}-{y.zfill(4)}")
            except ValueError:
                pass

    def _add_duty(self):
        if not self._appt_id:
            messagebox.showinfo("Select Appointment",
                                "Please select an appointment first.")
            return
        self._normalize_date()
        date = self._date_var.get().strip()
        if not DATE_RE.match(date):
            messagebox.showerror("Validation",
                                  "Date must be in format dd-mm-yyyy", parent=self)
            return
        try:
            add_duty(self._appt_id, date,
                     self._session_var.get(), self._type_var.get())
            duties = get_duties_for_appointment(self._appt_id)
            self._render_duties(duties)
            self._date_var.set("")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _delete_duty(self, duty_id):
        if not messagebox.askyesno("Confirm", "Delete this duty record?", parent=self):
            return
        try:
            delete_duty(duty_id)
            duties = get_duties_for_appointment(self._appt_id)
            self._render_duties(duties)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
