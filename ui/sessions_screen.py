import re
import os
import subprocess
import sys
import customtkinter as ctk
from tkinter import messagebox
from core.database import (
    get_all_sessions, add_session, get_appointments_for_session,
    add_appointment, get_all_staff, get_session_by_id, get_appointment_by_id,
    delete_appointment, delete_session,
)
from core.pdf_generator import generate_appointment_letter
from core.excel_exporter import export_staff_roster

IUB_GREEN = "#1a5276"
IUB_DARK  = "#154360"
IUB_LIGHT = "#d6eaf8"

ROLES = [
    "Resident Inspector", "Distributing Inspector", "Member Inspection Squad",
    "Superintendent", "Deputy Superintendent", "Invigilator", "Paper Checker",
]


def _open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", path])


class SessionsScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._selected_session = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Left panel ─────────────────────────────────────────────────────────
        left = ctk.CTkFrame(self, width=260,
                             fg_color=("gray85", "gray20"), corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        lhdr = ctk.CTkFrame(left, fg_color=IUB_GREEN, corner_radius=0, height=50)
        lhdr.grid(row=0, column=0, sticky="ew")
        lhdr.grid_propagate(False)
        ctk.CTkLabel(lhdr, text="Exam Sessions",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="white").pack(side="left", padx=12, pady=12)
        ctk.CTkButton(lhdr, text="+", width=30, height=30,
                      fg_color="white", text_color=IUB_GREEN,
                      hover_color=IUB_LIGHT,
                      font=ctk.CTkFont(size=16, weight="bold"),
                      command=self._add_session).pack(side="right", padx=8, pady=10)

        self._sess_list = ctk.CTkScrollableFrame(
            left, fg_color=("gray85", "gray20"))
        self._sess_list.grid(row=1, column=0, sticky="nsew")
        self._sess_list.grid_columnconfigure(0, weight=1)

        # ── Right panel ────────────────────────────────────────────────────────
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        rhdr = ctk.CTkFrame(right, fg_color=IUB_GREEN, corner_radius=0, height=60)
        rhdr.grid(row=0, column=0, sticky="ew")
        rhdr.grid_propagate(False)
        self._rhdr_label = ctk.CTkLabel(rhdr, text="Select a session",
                                         font=ctk.CTkFont(size=13, weight="bold"),
                                         text_color="white")
        self._rhdr_label.pack(side="left", padx=20, pady=15)
        ctk.CTkButton(rhdr, text="+ Add Appointment", width=140, height=34,
                      fg_color="white", text_color=IUB_GREEN, hover_color=IUB_LIGHT,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._add_appointment).pack(side="right", padx=8, pady=12)
        ctk.CTkButton(rhdr, text="Export Roster", width=110, height=34,
                      fg_color=IUB_LIGHT, text_color=IUB_GREEN, hover_color="white",
                      font=ctk.CTkFont(size=11),
                      command=self._export_roster).pack(side="right", padx=4, pady=12)
        ctk.CTkButton(rhdr, text="Generate All Letters", width=150, height=34,
                      fg_color=IUB_LIGHT, text_color=IUB_GREEN, hover_color="white",
                      font=ctk.CTkFont(size=11),
                      command=self._gen_all_letters).pack(side="right", padx=4, pady=12)
        ctk.CTkButton(rhdr, text="Delete Session", width=120, height=34,
                      fg_color="#922b21", text_color="white", hover_color="#7b241c",
                      font=ctk.CTkFont(size=11),
                      command=self._delete_session).pack(side="right", padx=4, pady=12)

        self._appt_table = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self._appt_table.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        for col in range(7):
            self._appt_table.grid_columnconfigure(col, weight=1)

    def refresh(self):
        self._render_sessions()
        if self._selected_session:
            self._render_appointments(self._selected_session)

    def set_context(self, session_id=None, **_):
        if session_id:
            self._selected_session = session_id
            self._render_appointments(session_id)

    def _render_sessions(self):
        for w in self._sess_list.winfo_children():
            w.destroy()
        sessions = get_all_sessions()
        if not sessions:
            ctk.CTkLabel(self._sess_list, text="No sessions yet.",
                         font=ctk.CTkFont(size=10),
                         text_color="gray").pack(pady=20)
            return
        for s in sessions:
            selected = self._selected_session == s["id"]
            btn = ctk.CTkButton(
                self._sess_list,
                text=f"{s['session_name']}\n{s['year'] or ''}",
                anchor="w", height=50,
                fg_color=IUB_GREEN if selected else "transparent",
                text_color="white",
                hover_color=IUB_DARK,
                font=ctk.CTkFont(size=11),
                command=lambda sid=s["id"]: self._select_session(sid),
            )
            btn.pack(fill="x", pady=1)

    def _select_session(self, session_id):
        self._selected_session = session_id
        self._render_sessions()
        self._render_appointments(session_id)

    def _render_appointments(self, session_id):
        s = get_session_by_id(session_id)
        if s:
            self._rhdr_label.configure(text=s["session_name"])

        for w in self._appt_table.winfo_children():
            w.destroy()

        headers = ["Name", "CNIC", "Role", "Centre", "Letter No.", "Status", "Actions"]
        for col, h in enumerate(headers):
            f = ctk.CTkFrame(self._appt_table, fg_color=IUB_GREEN, corner_radius=0)
            f.grid(row=0, column=col, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(f, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="white").pack(padx=6, pady=4)

        appts = get_appointments_for_session(session_id)
        if not appts:
            ctk.CTkLabel(self._appt_table, text="No appointments yet.",
                         font=ctk.CTkFont(size=10),
                         text_color="gray").grid(
                row=1, column=0, columnspan=7, pady=20)
            return

        for i, a in enumerate(appts):
            bg           = IUB_LIGHT if i % 2 == 0 else "white"
            status_color = "#1a8754" if a["status"] == "billed" else "gray"
            for col, val in enumerate([a["full_name"], a["cnic"], a["role"],
                                        a["centre"] or "—", a["letter_no"] or "—"]):
                f = ctk.CTkFrame(self._appt_table, fg_color=bg, corner_radius=0)
                f.grid(row=i + 1, column=col, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=10),
                             wraplength=120,
                             text_color="#111111").pack(padx=6, pady=4, anchor="w")
            sf = ctk.CTkFrame(self._appt_table, fg_color=bg, corner_radius=0)
            sf.grid(row=i + 1, column=5, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(sf, text=a["status"].capitalize(),
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=status_color).pack(padx=6, pady=4)
            af = ctk.CTkFrame(self._appt_table, fg_color=bg, corner_radius=0)
            af.grid(row=i + 1, column=6, sticky="ew", padx=1, pady=1)
            ctk.CTkButton(af, text="Preview Letter", width=100, height=26,
                          font=ctk.CTkFont(size=9), fg_color=IUB_GREEN,
                          command=lambda aid=a["id"]: self._gen_letter(aid)
                          ).pack(side="left", padx=3, pady=4)
            ctk.CTkButton(af, text="Delete", width=60, height=26,
                          font=ctk.CTkFont(size=9), fg_color="#922b21",
                          command=lambda aid=a["id"], name=a["full_name"]: self._delete_appt(aid, name)
                          ).pack(side="left", padx=3, pady=4)

    def _delete_session(self):
        if not self._selected_session:
            messagebox.showinfo("No Selection", "Please select a session first.", parent=self)
            return
        s = get_session_by_id(self._selected_session)
        name = s["session_name"] if s else "this session"
        confirmed = messagebox.askyesno(
            "Delete Session",
            f"Delete '{name}'?\n\nThis will also remove all its appointments.\nThis cannot be undone.",
            parent=self)
        if not confirmed:
            return
        try:
            delete_session(self._selected_session)
            self._selected_session = None
            self._rhdr_label.configure(text="Select a session")
            for w in self._appt_table.winfo_children():
                w.destroy()
            self._render_sessions()
        except ValueError as e:
            messagebox.showerror("Cannot Delete", str(e), parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _delete_appt(self, appt_id, name):
        confirmed = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete the appointment for {name}? This cannot be undone.",
            parent=self)
        if not confirmed:
            return
        try:
            delete_appointment(appt_id)
            self._render_appointments(self._selected_session)
        except ValueError as e:
            messagebox.showerror("Cannot Delete", str(e), parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _add_session(self):
        _SessionForm(self)

    def _add_appointment(self):
        if not self._selected_session:
            messagebox.showinfo("Select Session", "Please select a session first.")
            return
        _AppointmentForm(self, self._selected_session)

    def _gen_letter(self, appointment_id):
        try:
            appt = get_appointment_by_id(appointment_id)
            if not appt:
                messagebox.showerror("Error", "Appointment not found.", parent=self)
                return
            s = get_session_by_id(appt["session_id"])
            session_name = s["session_name"] if s else ""
            path = generate_appointment_letter(dict(appt), session_name)
            preview_path = os.path.join(os.path.dirname(path),
                                        "Preview_" + os.path.basename(path))
            os.replace(path, preview_path)
            _open_file(preview_path)
        except Exception as e:
            messagebox.showerror("Letter Error", str(e), parent=self)

    def _gen_all_letters(self):
        if not self._selected_session:
            messagebox.showinfo("Select Session", "Please select a session first.",
                                parent=self)
            return
        s = get_session_by_id(self._selected_session)
        if not s:
            return
        session_name = s["session_name"]
        appts = get_appointments_for_session(self._selected_session)
        if not appts:
            messagebox.showinfo("No Appointments",
                                "No appointments in this session.", parent=self)
            return
        _GenAllLettersDialog(self, [dict(a) for a in appts], session_name)

    def _export_roster(self):
        if not self._selected_session:
            messagebox.showinfo("Select Session", "Please select a session first.",
                                parent=self)
            return
        try:
            path = export_staff_roster(self._selected_session)
            _open_file(path)
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self)

    def on_saved(self):
        self.refresh()


# ── Generate All Letters Dialog ────────────────────────────────────────────────

class _GenAllLettersDialog(ctk.CTkToplevel):
    def __init__(self, parent_screen, appts, session_name):
        super().__init__()
        self.parent_screen = parent_screen
        self._appts        = appts
        self._session_name = session_name
        self.title("Generating All Letters")
        self.geometry("440x160")
        self.resizable(False, False)
        self.grab_set()
        self._idx       = 0
        self._generated = 0
        self._errors    = 0
        self._build()
        self.after(120, self._process_next)

    def _build(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=24, pady=24)
        self._status_label = ctk.CTkLabel(
            f, text="Preparing...", font=ctk.CTkFont(size=12))
        self._status_label.pack(pady=(0, 14))
        self._progress = ctk.CTkProgressBar(f, width=390)
        self._progress.pack()
        self._progress.set(0)

    def _process_next(self):
        total = len(self._appts)
        if self._idx >= total:
            self.destroy()
            msg = f"{self._generated} letter(s) generated. Saved to outputs folder."
            if self._errors:
                msg += f"\n{self._errors} error(s) occurred."
            messagebox.showinfo("Complete", msg)
            outputs_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
            _open_file(outputs_dir)
            return
        self._status_label.configure(
            text=f"Generating letter {self._idx + 1} of {total}...")
        self._progress.set((self._idx + 1) / total)
        appt_data = self._appts[self._idx]
        self._idx += 1
        try:
            generate_appointment_letter(appt_data, self._session_name)
            self._generated += 1
        except Exception:
            self._errors += 1
        self.after(60, self._process_next)


# ── Session Form ───────────────────────────────────────────────────────────────

class _SessionForm(ctk.CTkToplevel):
    def __init__(self, parent_screen):
        super().__init__()
        self.parent = parent_screen
        self.title("New Exam Session")
        self.geometry("400x280")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=20)
        f.grid_columnconfigure(1, weight=1)

        labels = ["Session Name *", "Programs", "Year *"]
        keys   = ["name", "programs", "year"]
        self._vars = {k: ctk.StringVar() for k in keys}
        for i, (lbl, key) in enumerate(zip(labels, keys)):
            ctk.CTkLabel(f, text=lbl,
                         font=ctk.CTkFont(size=11)).grid(
                row=i, column=0, sticky="w", pady=6)
            ctk.CTkEntry(f, textvariable=self._vars[key], width=240).grid(
                row=i, column=1, padx=10, pady=6)

        btn_f = ctk.CTkFrame(f, fg_color="transparent")
        btn_f.grid(row=3, column=0, columnspan=2, pady=12)
        ctk.CTkButton(btn_f, text="Create Session", fg_color=IUB_GREEN,
                      command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_f, text="Cancel", fg_color="gray",
                      command=self.destroy).pack(side="left")

    def _save(self):
        name = self._vars["name"].get().strip()
        year = self._vars["year"].get().strip()
        if not name or not year:
            messagebox.showerror("Validation",
                                  "Session Name and Year are required.", parent=self)
            return
        try:
            add_session(name, self._vars["programs"].get().strip(), year)
            self.parent.on_saved()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


# ── Appointment Form ───────────────────────────────────────────────────────────

class _AppointmentForm(ctk.CTkToplevel):
    def __init__(self, parent_screen, session_id):
        super().__init__()
        self.parent     = parent_screen
        self.session_id = session_id
        self.title("Add Appointment")
        self.geometry("500x420")
        self.resizable(False, False)
        self.grab_set()
        self._all_staff = get_all_staff()
        self._filtered  = list(self._all_staff)
        self._build()

    def _build(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=20)
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Search Staff:",
                     font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, sticky="w", pady=6)
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_staff())
        ctk.CTkEntry(f, textvariable=self._search_var, width=280,
                     placeholder_text="Name or CNIC").grid(
            row=0, column=1, padx=10, pady=6)

        ctk.CTkLabel(f, text="Staff *",
                     font=ctk.CTkFont(size=11)).grid(
            row=1, column=0, sticky="w")
        self._staff_var  = ctk.StringVar()
        self._staff_menu = ctk.CTkOptionMenu(
            f, variable=self._staff_var, values=[], width=300)
        self._staff_menu.grid(row=1, column=1, padx=10, pady=6, sticky="ew")

        labels = ["Role *", "Centre", "Letter No.", "Letter Date"]
        keys   = ["role", "centre", "letter_no", "letter_date"]
        self._vars = {k: ctk.StringVar() for k in keys}
        for i, (lbl, key) in enumerate(zip(labels, keys), start=2):
            ctk.CTkLabel(f, text=lbl,
                         font=ctk.CTkFont(size=11)).grid(
                row=i, column=0, sticky="w", pady=6)
            if key == "role":
                w = ctk.CTkOptionMenu(f, variable=self._vars[key],
                                       values=ROLES, width=300)
                if ROLES:
                    self._vars[key].set(ROLES[0])
            else:
                w = ctk.CTkEntry(f, textvariable=self._vars[key], width=300)
            w.grid(row=i, column=1, padx=10, pady=6)

        btn_f = ctk.CTkFrame(f, fg_color="transparent")
        btn_f.grid(row=6, column=0, columnspan=2, pady=12)
        ctk.CTkButton(btn_f, text="Add Appointment", fg_color=IUB_GREEN,
                      command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_f, text="Cancel", fg_color="gray",
                      command=self.destroy).pack(side="left")

        self._filter_staff()

    def _filter_staff(self):
        q = self._search_var.get().strip().lower()
        self._filtered = [s for s in self._all_staff
                          if q in s["full_name"].lower()
                          or q in s["cnic"].lower()] if q else list(self._all_staff)
        names = [f"{s['full_name']} ({s['cnic']})" for s in self._filtered]
        self._staff_menu.configure(values=names or ["No staff found"])
        if names:
            self._staff_var.set(names[0])

    def _save(self):
        sel = self._staff_var.get()
        if not sel or sel == "No staff found":
            messagebox.showerror("Validation", "Please select a staff member.",
                                  parent=self)
            return
        matching = [s for s in self._filtered
                    if f"{s['full_name']} ({s['cnic']})" == sel]
        if not matching:
            messagebox.showerror("Validation", "Could not find selected staff.",
                                  parent=self)
            return
        staff_id = matching[0]["id"]
        role     = self._vars["role"].get()
        if not role:
            messagebox.showerror("Validation", "Role is required.", parent=self)
            return
        try:
            add_appointment(
                staff_id, self.session_id, role,
                self._vars["centre"].get().strip(),
                self._vars["letter_no"].get().strip(),
                self._vars["letter_date"].get().strip(),
            )
            self.parent.on_saved()
            self.destroy()
        except Exception as e:
            if "UNIQUE" in str(e):
                messagebox.showerror(
                    "Duplicate",
                    "This person already has this role in the session.", parent=self)
            else:
                messagebox.showerror("Error", str(e), parent=self)
