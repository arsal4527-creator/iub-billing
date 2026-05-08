import os
import sys
import subprocess
from collections import OrderedDict
import customtkinter as ctk
from tkinter import messagebox
from core.database import (
    get_all_sessions, get_appointments_for_session,
    get_duties_for_appointment, get_bill_for_appointment,
    get_session_by_id, get_appointment_by_id, get_connection,
    has_billing_pin, verify_billing_pin, delete_bill,
)
from core.billing_engine import calculate_bill
from core.pdf_generator import generate_bill_pdf
from core.excel_exporter import export_session_excel

IUB_GREEN = "#1a5276"
IUB_DARK  = "#154360"
IUB_LIGHT = "#d6eaf8"
PAGE_SIZE = 25


def _open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])


def _compute_bill_preview(appointment_id):
    """Read duties and rates and return a preview dict WITHOUT writing to DB."""
    appt    = dict(get_appointment_by_id(appointment_id))
    duties  = [dict(d) for d in get_duties_for_appointment(appointment_id)]
    session = get_session_by_id(appt["session_id"])
    conn = get_connection()
    try:
        rate_row = conn.execute("SELECT * FROM rates WHERE role=?",
                                (appt["role"],)).fetchone()
    finally:
        conn.close()
    if not rate_row:
        raise ValueError(f"No rate configured for role: {appt['role']}")
    if not duties:
        raise ValueError(f"No duties logged for {appt['full_name']}.")
    rs   = rate_row["rate_single"]
    rd   = rate_row["rate_double"]
    unit = rate_row["unit"]
    if unit == "per_script":
        total_days   = len(duties)
        total_double = 0
        base_amount  = total_days * rs
    else:
        total_days   = len([d for d in duties if d["session_type"] == "Single"])
        total_double = len(set(d["duty_date"] for d in duties if d["session_type"] == "Double"))
        base_amount  = (total_days * rs) + (total_double * rd)
    return {
        "appt":        appt,
        "duties":      duties,
        "session_name": session["session_name"] if session else "",
        "rate_single": rs,
        "rate_double": rd,
        "unit":        unit,
        "total_days":  total_days,
        "total_double": total_double,
        "base_amount": base_amount,
    }


class BillingScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._session_id = None
        self._sessions_data = {}
        self._view_mode = "group"
        self._bill_page = 0
        self._appts_cache = []
        self._group_states = []
        self._expand_all_btn = None
        self._unlocked = False
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(self, fg_color=IUB_GREEN, corner_radius=0, height=60)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="Generate Bills",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=15)

        # Lock toggle button (shown when unlocked)
        self._lock_btn = ctk.CTkButton(
            hdr, text="🔒 Lock", width=90, height=34,
            fg_color="#922b21", text_color="white",
            hover_color="#7b241c",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._do_lock)
        self._lock_btn.pack(side="right", padx=8, pady=12)
        self._lock_btn.pack_forget()  # hidden until unlocked

        btns = ctk.CTkFrame(hdr, fg_color="transparent")
        btns.pack(side="right", padx=16, pady=10)
        ctk.CTkButton(btns, text="Preview All", width=100, height=34,
                      fg_color=IUB_LIGHT, text_color=IUB_GREEN,
                      hover_color="white",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._preview_all).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Generate All Bills", width=150, height=34,
                      fg_color="white", text_color=IUB_GREEN,
                      hover_color=IUB_LIGHT,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._gen_all).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Export Excel", width=120, height=34,
                      fg_color="#1a8754", text_color="white",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._export_excel).pack(side="left", padx=4)

        sel = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=0)
        sel.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(sel, text="Session:",
                     font=ctk.CTkFont(size=11)).pack(
            side="left", padx=(16, 4), pady=10)
        self._sess_var  = ctk.StringVar()
        self._sess_menu = ctk.CTkOptionMenu(
            sel, variable=self._sess_var, values=[],
            width=300, command=self._on_session_change)
        self._sess_menu.pack(side="left", padx=4, pady=10)

        # View toggle buttons
        tframe = ctk.CTkFrame(sel, fg_color="transparent")
        tframe.pack(side="right", padx=16, pady=8)
        self._grp_btn = ctk.CTkButton(
            tframe, text="Group View", width=100, height=28,
            fg_color=IUB_GREEN, text_color="white",
            hover_color=IUB_DARK,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._switch_to_group)
        self._grp_btn.pack(side="left", padx=2)
        self._ind_btn = ctk.CTkButton(
            tframe, text="Individual View", width=120, height=28,
            fg_color="transparent", text_color=IUB_GREEN,
            hover_color=IUB_LIGHT,
            font=ctk.CTkFont(size=10),
            command=self._switch_to_individual)
        self._ind_btn.pack(side="left", padx=2)

        self._table = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._table.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)
        for col in range(6):
            self._table.grid_columnconfigure(col, weight=1)

        # Pagination bar (individual view only)
        self._pbar = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=0)
        self._pbar.grid(row=3, column=0, sticky="ew")
        self._bill_prev_btn = ctk.CTkButton(
            self._pbar, text="← Prev", width=80, height=28,
            fg_color=IUB_GREEN, hover_color=IUB_LIGHT,
            text_color="white", font=ctk.CTkFont(size=10),
            command=self._bill_prev_page)
        self._bill_prev_btn.pack(side="left", padx=8, pady=6)
        self._bill_page_label = ctk.CTkLabel(
            self._pbar, text="Page 1 of 1",
            font=ctk.CTkFont(size=10), text_color="gray")
        self._bill_page_label.pack(side="left", padx=8)
        self._bill_next_btn = ctk.CTkButton(
            self._pbar, text="Next →", width=80, height=28,
            fg_color=IUB_GREEN, hover_color=IUB_LIGHT,
            text_color="white", font=ctk.CTkFont(size=10),
            command=self._bill_next_page)
        self._bill_next_btn.pack(side="left", padx=8, pady=6)
        self._pbar.grid_remove()  # hidden until individual view

        # Lock overlay — shown over the table area when PIN is set and not unlocked
        self._lock_frame = ctk.CTkFrame(self, fg_color=("gray92", "gray14"), corner_radius=0)
        self._lock_frame.grid(row=2, column=0, sticky="nsew")
        self._lock_frame.grid_columnconfigure(0, weight=1)
        self._lock_frame.grid_rowconfigure(0, weight=1)
        self._build_lock_ui()

    def _build_lock_ui(self):
        centre = ctk.CTkFrame(self._lock_frame, fg_color="transparent")
        centre.grid(row=0, column=0)

        ctk.CTkLabel(centre, text="🔐",
                     font=ctk.CTkFont(size=48)).pack(pady=(0, 8))
        ctk.CTkLabel(centre, text="Billing Section Locked",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=IUB_GREEN).pack(pady=(0, 4))
        ctk.CTkLabel(centre, text="Enter your PIN to access billing and bill management.",
                     font=ctk.CTkFont(size=11),
                     text_color="gray").pack(pady=(0, 20))

        self._pin_var = ctk.StringVar()
        self._pin_entry = ctk.CTkEntry(
            centre, textvariable=self._pin_var,
            width=160, height=40, show="●",
            placeholder_text="Enter PIN",
            font=ctk.CTkFont(size=16),
            justify="center")
        self._pin_entry.pack(pady=(0, 8))
        self._pin_entry.bind("<Return>", lambda _: self._attempt_unlock())

        ctk.CTkButton(centre, text="Unlock", width=160, height=38,
                      fg_color=IUB_GREEN, hover_color=IUB_DARK,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._attempt_unlock).pack(pady=(0, 8))

        self._pin_error = ctk.CTkLabel(centre, text="",
                                        font=ctk.CTkFont(size=10),
                                        text_color="#e74c3c")
        self._pin_error.pack()

        ctk.CTkLabel(centre,
                     text="No PIN set yet? Configure one in Settings → Security.",
                     font=ctk.CTkFont(size=9), text_color="gray").pack(pady=(16, 0))

    def refresh(self):
        # Re-lock whenever navigating to this screen (security: require re-auth each visit)
        if has_billing_pin():
            self._unlocked = False
            self._lock_frame.tkraise()
            self._lock_btn.pack_forget()
            self._pin_var.set("")
            self._pin_error.configure(text="")
            self._pbar.grid_remove()
        else:
            self._unlocked = True
            self._table.tkraise()
            self._lock_btn.pack_forget()  # no PIN set — no lock button needed

        sessions = get_all_sessions()
        names = [s["session_name"] for s in sessions]
        self._sessions_data = {s["session_name"]: s["id"] for s in sessions}
        self._sess_menu.configure(values=names or ["No sessions"])
        if names:
            self._sess_var.set(names[0])
            self._on_session_change(names[0])

    def _attempt_unlock(self):
        pin = self._pin_var.get().strip()
        if not pin:
            self._pin_error.configure(text="Please enter your PIN.")
            return
        if verify_billing_pin(pin):
            self._unlocked = True
            self._pin_var.set("")
            self._pin_error.configure(text="")
            self._table.tkraise()
            self._lock_btn.pack(side="right", padx=8, pady=12)
        else:
            self._pin_error.configure(text="Incorrect PIN. Try again.")
            self._pin_var.set("")
            self._pin_entry.focus()

    def _do_lock(self):
        self._unlocked = False
        self._lock_btn.pack_forget()
        self._pbar.grid_remove()
        self._pin_var.set("")
        self._pin_error.configure(text="")
        self._lock_frame.tkraise()

    def _on_session_change(self, name):
        self._session_id = self._sessions_data.get(name)
        self._bill_page = 0
        self._render_table()

    # ── View switching ─────────────────────────────────────────────────────────

    def _switch_to_group(self):
        if self._view_mode == "group":
            return
        self._view_mode = "group"
        self._grp_btn.configure(fg_color=IUB_GREEN, text_color="white")
        self._ind_btn.configure(fg_color="transparent", text_color=IUB_GREEN)
        self._render_table()

    def _switch_to_individual(self):
        if self._view_mode == "individual":
            return
        self._view_mode = "individual"
        self._grp_btn.configure(fg_color="transparent", text_color=IUB_GREEN)
        self._ind_btn.configure(fg_color=IUB_GREEN, text_color="white")
        self._bill_page = 0
        self._render_table()

    def _render_table(self):
        if self._view_mode == "group":
            self._pbar.grid_remove()
            self._render_group_view()
        else:
            self._pbar.grid()
            self._render_individual_view()

    # ── Group View ─────────────────────────────────────────────────────────────

    def _render_group_view(self):
        for w in self._table.winfo_children():
            w.destroy()
        self._group_states = []
        self._expand_all_btn = None

        if not self._session_id:
            return

        all_appts = list(get_appointments_for_session(self._session_id))
        self._appts_cache = all_appts

        if not all_appts:
            ctk.CTkLabel(self._table, text="No appointments in this session.",
                         font=ctk.CTkFont(size=11), text_color="gray").pack(pady=20)
            return

        # Fetch bills for all appointments to compute totals
        bills = {a["id"]: get_bill_for_appointment(a["id"]) for a in all_appts}
        grand_total = sum(b["amount"] for b in bills.values() if b)

        # Grand total bar
        gt_bar = ctk.CTkFrame(self._table, fg_color=IUB_LIGHT, corner_radius=6)
        gt_bar.pack(fill="x", pady=(0, 8), padx=2)
        ctk.CTkLabel(gt_bar, text=f"Grand Total (Billed): Rs. {grand_total:,.0f}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=IUB_GREEN).pack(side="left", padx=12, pady=8)
        self._expand_all_btn = ctk.CTkButton(
            gt_bar, text="Expand All", width=100, height=28,
            fg_color=IUB_GREEN, text_color="white",
            font=ctk.CTkFont(size=10),
            command=self._toggle_expand_all)
        self._expand_all_btn.pack(side="right", padx=8, pady=4)

        # Group appointments by role (preserving encounter order)
        groups = OrderedDict()
        for a in all_appts:
            role = a["role"]
            if role not in groups:
                groups[role] = []
            groups[role].append(a)

        for role, role_appts in groups.items():
            role_total = sum(bills[a["id"]]["amount"] for a in role_appts if bills[a["id"]])
            pending_count = sum(1 for a in role_appts if not bills[a["id"]])

            group_frame = ctk.CTkFrame(self._table, fg_color="transparent", corner_radius=0)
            group_frame.pack(fill="x", pady=2)

            hdr = ctk.CTkFrame(group_frame, fg_color=IUB_GREEN, corner_radius=6)
            hdr.pack(fill="x")

            content = ctk.CTkFrame(group_frame, fg_color=("gray95", "gray18"), corner_radius=0)
            for col in range(5):
                content.grid_columnconfigure(col, weight=1)

            arrow_var = ctk.StringVar(value="▶")
            state = {
                "expanded": False,
                "rendered": False,
                "content": content,
                "arrow_var": arrow_var,
                "appts": role_appts,
            }
            self._group_states.append(state)

            toggle_fn = self._make_group_toggle(state)

            ctk.CTkButton(hdr, textvariable=arrow_var, width=36, height=32,
                          fg_color="transparent", hover_color=IUB_DARK,
                          text_color="white", font=ctk.CTkFont(size=11),
                          command=toggle_fn).pack(side="left", padx=4, pady=4)

            lbl_text = f"{role}  ({len(role_appts)})"
            if pending_count > 0:
                lbl_text += f"  •  {pending_count} pending"
            ctk.CTkLabel(hdr, text=lbl_text,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="white").pack(side="left", padx=4, pady=8)

            if role != "Superintendent":
                ctk.CTkButton(hdr, text="Generate All", width=100, height=26,
                              fg_color="white", text_color=IUB_GREEN,
                              hover_color=IUB_LIGHT,
                              font=ctk.CTkFont(size=9, weight="bold"),
                              command=lambda r=role: self._gen_all_for_role(r)
                              ).pack(side="right", padx=4, pady=4)
            else:
                ctk.CTkLabel(hdr, text="generate individually →",
                             font=ctk.CTkFont(size=9),
                             text_color=IUB_LIGHT).pack(side="right", padx=8)

            if role_total > 0:
                ctk.CTkLabel(hdr, text=f"Rs. {role_total:,.0f}",
                             font=ctk.CTkFont(size=11),
                             text_color="white").pack(side="right", padx=8, pady=8)

    def _make_group_toggle(self, state):
        def toggle():
            if not state["rendered"]:
                self._render_group_rows(state["content"], state["appts"])
                state["rendered"] = True
            if state["expanded"]:
                state["content"].pack_forget()
                state["expanded"] = False
                state["arrow_var"].set("▶")
            else:
                state["content"].pack(fill="x", padx=4, pady=2)
                state["expanded"] = True
                state["arrow_var"].set("▼")
            # Sync expand-all button label
            if self._expand_all_btn:
                all_exp = all(s["expanded"] for s in self._group_states)
                self._expand_all_btn.configure(
                    text="Collapse All" if all_exp else "Expand All")
        return toggle

    def _toggle_expand_all(self):
        if not self._group_states:
            return
        all_exp = all(s["expanded"] for s in self._group_states)
        if all_exp:
            for s in self._group_states:
                s["content"].pack_forget()
                s["expanded"] = False
                s["arrow_var"].set("▶")
            self._expand_all_btn.configure(text="Expand All")
        else:
            for s in self._group_states:
                if not s["rendered"]:
                    self._render_group_rows(s["content"], s["appts"])
                    s["rendered"] = True
                if not s["expanded"]:
                    s["content"].pack(fill="x", padx=4, pady=2)
                    s["expanded"] = True
                    s["arrow_var"].set("▼")
            self._expand_all_btn.configure(text="Collapse All")

    def _render_group_rows(self, container, role_appts):
        headers = ["Name", "Duties", "Bill Status", "Amount (Rs.)", "Actions"]
        for col, h in enumerate(headers):
            fr = ctk.CTkFrame(container, fg_color=IUB_GREEN, corner_radius=0)
            fr.grid(row=0, column=col, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(fr, text=h, font=ctk.CTkFont(size=9, weight="bold"),
                         text_color="white").pack(padx=6, pady=3)

        for i, a in enumerate(role_appts):
            bg      = IUB_LIGHT if i % 2 == 0 else "white"
            duties  = get_duties_for_appointment(a["id"])
            bill    = get_bill_for_appointment(a["id"])
            status  = "Generated" if bill else "Pending"
            amount  = f"{bill['amount']:,.0f}" if bill else "—"
            s_color = "#1a8754" if bill else "#b7950b"

            for col, val in enumerate([a["full_name"], str(len(duties))]):
                fr = ctk.CTkFrame(container, fg_color=bg, corner_radius=0)
                fr.grid(row=i + 1, column=col, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(fr, text=val, font=ctk.CTkFont(size=9),
                             wraplength=160,
                             text_color="#111111").pack(padx=6, pady=3, anchor="w")

            sf = ctk.CTkFrame(container, fg_color=bg, corner_radius=0)
            sf.grid(row=i + 1, column=2, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(sf, text=status, font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=s_color).pack(padx=6, pady=3)

            af = ctk.CTkFrame(container, fg_color=bg, corner_radius=0)
            af.grid(row=i + 1, column=3, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(af, text=amount, font=ctk.CTkFont(size=9),
                         text_color="#111111").pack(padx=6, pady=3)

            act = ctk.CTkFrame(container, fg_color=bg, corner_radius=0)
            act.grid(row=i + 1, column=4, sticky="ew", padx=1, pady=1)
            if not bill:
                ctk.CTkButton(act, text="Preview", width=60, height=24,
                              font=ctk.CTkFont(size=8),
                              fg_color=IUB_LIGHT, text_color=IUB_GREEN,
                              hover_color="white",
                              command=lambda aid=a["id"], r=a["role"]: self._preview_bill(aid, r)
                              ).pack(side="left", padx=2, pady=3)
                ctk.CTkButton(act, text="Generate", width=70, height=24,
                              font=ctk.CTkFont(size=8), fg_color=IUB_GREEN,
                              command=lambda aid=a["id"], r=a["role"]: self._gen_bill(aid, r)
                              ).pack(side="left", padx=2, pady=3)
            else:
                ctk.CTkButton(act, text="Open PDF", width=70, height=24,
                              font=ctk.CTkFont(size=8), fg_color="#1a8754",
                              command=lambda p=bill["pdf_path"]: _open_file(p) if p else None
                              ).pack(side="left", padx=2, pady=3)
                ctk.CTkLabel(act, text=f"#{bill['bill_no']}",
                             font=ctk.CTkFont(size=8), text_color="gray").pack(side="left")
                if self._unlocked:
                    ctk.CTkButton(act, text="Delete", width=55, height=24,
                                  font=ctk.CTkFont(size=8), fg_color="#922b21",
                                  command=lambda bid=bill["id"], bno=bill["bill_no"]: self._delete_bill(bid, bno)
                                  ).pack(side="left", padx=2, pady=3)

    def _gen_all_for_role(self, role):
        if not self._session_id:
            return
        role_appts = [a for a in self._appts_cache if a["role"] == role]
        pending    = [a for a in role_appts if not get_bill_for_appointment(a["id"])]
        if not pending:
            messagebox.showinfo("All Done", f"All {role} appointments already have bills.")
            return
        session = get_session_by_id(self._session_id)
        session_name = session["session_name"] if session else ""
        _GenAllBillsDialog(self, pending, session_name)

    # ── Individual View ────────────────────────────────────────────────────────

    def _render_individual_view(self):
        for w in self._table.winfo_children():
            w.destroy()

        if not self._session_id:
            return

        all_appts = list(get_appointments_for_session(self._session_id))
        self._appts_cache = all_appts

        total       = len(all_appts)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._bill_page = min(self._bill_page, total_pages - 1)
        start = self._bill_page * PAGE_SIZE
        appts = all_appts[start:start + PAGE_SIZE]

        self._bill_page_label.configure(
            text=f"Page {self._bill_page + 1} of {total_pages}  ({total} total)")
        self._bill_prev_btn.configure(
            state="normal" if self._bill_page > 0 else "disabled")
        self._bill_next_btn.configure(
            state="normal" if self._bill_page < total_pages - 1 else "disabled")

        headers = ["Name", "Role", "Duties", "Bill Status", "Amount (Rs.)", "Actions"]
        for col, h in enumerate(headers):
            fr = ctk.CTkFrame(self._table, fg_color=IUB_GREEN, corner_radius=0)
            fr.grid(row=0, column=col, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(fr, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="white").pack(padx=6, pady=4)

        if not appts:
            ctk.CTkLabel(self._table,
                         text="No appointments in this session.",
                         font=ctk.CTkFont(size=11),
                         text_color="gray").grid(
                row=1, column=0, columnspan=6, pady=20)
            return

        for i, a in enumerate(appts):
            bg      = IUB_LIGHT if i % 2 == 0 else "white"
            duties  = get_duties_for_appointment(a["id"])
            bill    = get_bill_for_appointment(a["id"])
            status  = "Generated" if bill else "Pending"
            amount  = f"{bill['amount']:,.0f}" if bill else "—"
            s_color = "#1a8754" if bill else "#b7950b"

            for col, val in enumerate([a["full_name"], a["role"], str(len(duties))]):
                fr = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=0)
                fr.grid(row=i + 1, column=col, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(fr, text=val, font=ctk.CTkFont(size=10),
                             wraplength=160,
                             text_color="#111111").pack(padx=6, pady=4, anchor="w")

            sf = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=0)
            sf.grid(row=i + 1, column=3, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(sf, text=status,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=s_color).pack(padx=6, pady=4)

            af = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=0)
            af.grid(row=i + 1, column=4, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(af, text=amount,
                         font=ctk.CTkFont(size=10),
                         text_color="#111111").pack(padx=6, pady=4)

            act = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=0)
            act.grid(row=i + 1, column=5, sticky="ew", padx=1, pady=1)
            if not bill:
                ctk.CTkButton(act, text="Preview", width=66, height=26,
                              font=ctk.CTkFont(size=9),
                              fg_color=IUB_LIGHT, text_color=IUB_GREEN,
                              hover_color="white",
                              command=lambda aid=a["id"], r=a["role"]: self._preview_bill(aid, r)
                              ).pack(side="left", padx=2, pady=4)
                ctk.CTkButton(act, text="Generate", width=78, height=26,
                              font=ctk.CTkFont(size=9), fg_color=IUB_GREEN,
                              command=lambda aid=a["id"], r=a["role"]: self._gen_bill(aid, r)
                              ).pack(side="left", padx=2, pady=4)
            else:
                ctk.CTkButton(act, text="Open PDF", width=78, height=26,
                              font=ctk.CTkFont(size=9), fg_color="#1a8754",
                              command=lambda p=bill["pdf_path"]: _open_file(p) if p else None
                              ).pack(side="left", padx=2, pady=4)
                ctk.CTkLabel(act, text=f"#{bill['bill_no']}",
                             font=ctk.CTkFont(size=8),
                             text_color="gray").pack(side="left")
                if self._unlocked:
                    ctk.CTkButton(act, text="Delete", width=58, height=26,
                                  font=ctk.CTkFont(size=9), fg_color="#922b21",
                                  command=lambda bid=bill["id"], bno=bill["bill_no"]: self._delete_bill(bid, bno)
                                  ).pack(side="left", padx=2, pady=4)

    def _bill_prev_page(self):
        if self._bill_page > 0:
            self._bill_page -= 1
            self._render_table()

    def _bill_next_page(self):
        self._bill_page += 1
        self._render_table()

    def _delete_bill(self, bill_id, bill_no):
        confirmed = messagebox.askyesno(
            "Delete Bill",
            f"Permanently delete Bill #{bill_no}?\n\n"
            "The appointment will return to Pending status.\n"
            "This action is recorded in the audit log.",
            parent=self)
        if not confirmed:
            return
        try:
            delete_bill(bill_id)
            self._render_table()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    # ── Preview ────────────────────────────────────────────────────────────────

    def _preview_bill(self, appointment_id, role):
        if role == "Superintendent":
            def _open_preview(extra_items):
                self._do_preview_pdf(appointment_id, extra_items)
            _ContingentDialog(self, appointment_id, on_submit=_open_preview)
        else:
            self._do_preview_pdf(appointment_id, None)

    def _do_preview_pdf(self, appointment_id, extra_items):
        try:
            data = _compute_bill_preview(appointment_id)
            appt = data["appt"]
            duties = data["duties"]
            session_name = data["session_name"]

            if appt.get("role") == "Superintendent" and extra_items:
                ei = dict(extra_items)
                contingent = sum(float(ei.get(k, 0) or 0) for k in
                                 ["menial", "stationery", "collection_qp", "dispatch_ab", "ice"])
                gross = data["base_amount"] + contingent
                advance = float(ei.get("advance", 0) or 0)
                amount = max(0.0, gross - advance)
                ei["gross"] = gross
            else:
                amount = data["base_amount"]
                ei = None

            bill_data = {
                "bill_no": "PREVIEW",
                "amount": amount,
                "rate_single": data["rate_single"],
                "rate_double": data["rate_double"],
                "total_days": data["total_days"],
                "total_double": data["total_double"],
                "total_qty": data["total_days"],
            }

            path = generate_bill_pdf(bill_data, appt, duties, session_name, ei)
            preview_path = os.path.join(os.path.dirname(path),
                                        "Preview_" + os.path.basename(path))
            os.replace(path, preview_path)
            _open_file(preview_path)
        except Exception as e:
            messagebox.showerror("Preview Error", str(e), parent=self)

    def _preview_all(self):
        if not self._session_id:
            messagebox.showinfo("No Session", "Please select a session.")
            return
        _PreviewAllDialog(self, self._session_id)

    # ── Generate ───────────────────────────────────────────────────────────────

    def _gen_bill(self, appointment_id, role):
        if role == "Superintendent":
            _ContingentDialog(self, appointment_id)
        else:
            self._do_generate(appointment_id, None)

    def _do_generate(self, appointment_id, extra_items):
        try:
            result  = calculate_bill(appointment_id, extra_items)
            appt    = dict(get_appointment_by_id(appointment_id))
            session = get_session_by_id(appt["session_id"])
            duties  = [dict(d) for d in get_duties_for_appointment(appointment_id)]
            path    = generate_bill_pdf(result, appt, duties,
                                        session["session_name"], extra_items)
            conn = get_connection()
            try:
                conn.execute("UPDATE bills SET pdf_path=? WHERE bill_no=?",
                             (path, result["bill_no"]))
                conn.commit()
            finally:
                conn.close()
            self._render_table()
            if messagebox.askyesno("Bill Generated",
                                    f"Bill {result['bill_no']} generated.\n"
                                    f"Amount: Rs. {result['amount']:,.0f}\n\n"
                                    "Open PDF now?"):
                _open_file(path)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _gen_all(self):
        if not self._session_id:
            return
        appts   = get_appointments_for_session(self._session_id)
        pending = [a for a in appts if not get_bill_for_appointment(a["id"])]
        supers  = [a for a in pending if a["role"] == "Superintendent"]
        others  = [a for a in pending if a["role"] != "Superintendent"]
        if not pending:
            messagebox.showinfo("All Done", "All appointments already have bills.")
            return
        if supers:
            messagebox.showinfo("Superintendent",
                                "Superintendent requires contingent items. "
                                "Please generate their bill individually.")
        if others:
            session = get_session_by_id(self._session_id)
            session_name = session["session_name"] if session else ""
            _GenAllBillsDialog(self, others, session_name)

    def _export_excel(self):
        if not self._session_id:
            messagebox.showinfo("No Session", "Please select a session.")
            return
        try:
            path = export_session_excel(self._session_id)
            if messagebox.askyesno("Exported",
                                    f"Excel report saved.\n{path}\n\nOpen now?"):
                _open_file(path)
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self)


# ── Bill Preview Dialog ────────────────────────────────────────────────────────

class _BillPreviewDialog(ctk.CTkToplevel):
    def __init__(self, parent_screen, appointment_id, extra_items=None):
        super().__init__()
        self.parent_screen = parent_screen
        self.appt_id       = appointment_id
        self.extra_items   = extra_items
        self.title("Bill Preview")
        self.geometry("680x640")
        self.minsize(600, 500)
        self.resizable(True, True)
        self.grab_set()
        try:
            data = _compute_bill_preview(appointment_id)
            self._build(data)
        except Exception as e:
            self.destroy()
            messagebox.showerror("Preview Error", str(e))

    def _build(self, data):
        appt    = data["appt"]
        duties  = data["duties"]
        role    = appt.get("role", "")
        rs      = data["rate_single"]
        rd      = data["rate_double"]
        singles = data["total_days"]
        doubles = data["total_double"]
        base    = data["base_amount"]

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(16, 4))
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll, text="BILL PREVIEW",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=IUB_GREEN).grid(row=0, column=0, pady=(0, 8))

        # ── info block ────────────────────────────────────────────────────────
        info = ctk.CTkFrame(scroll, fg_color=IUB_LIGHT, corner_radius=6)
        info.grid(row=1, column=0, sticky="ew", pady=4)
        info.grid_columnconfigure((1, 3), weight=1)
        fields = [
            ("Name:",       appt.get("full_name", "")),
            ("Role:",       appt.get("role", "")),
            ("Centre:",     appt.get("centre", "") or "—"),
            ("Letter No.:", appt.get("letter_no", "") or "—"),
            ("Session:",    data["session_name"]),
            ("Duties:",     str(len(duties))),
        ]
        for idx, (lbl, val) in enumerate(fields):
            r, c = divmod(idx, 2)
            ctk.CTkLabel(info, text=lbl,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=IUB_GREEN).grid(
                row=r, column=c * 2, sticky="w", padx=(10, 4), pady=3)
            ctk.CTkLabel(info, text=val,
                         font=ctk.CTkFont(size=10)).grid(
                row=r, column=c * 2 + 1, sticky="w", padx=(0, 10), pady=3)

        # ── duties table ──────────────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="Duties Logged",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=IUB_GREEN).grid(row=2, column=0, sticky="w", pady=(12, 4))
        dtbl = ctk.CTkFrame(scroll, fg_color="transparent")
        dtbl.grid(row=3, column=0, sticky="ew")
        dtbl.grid_columnconfigure((0, 1, 2), weight=1)
        for c, hdr in enumerate(["Date", "Session", "Type"]):
            h = ctk.CTkFrame(dtbl, fg_color=IUB_GREEN, corner_radius=0)
            h.grid(row=0, column=c, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(h, text=hdr,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color="white").pack(padx=6, pady=3)
        for i, d in enumerate(duties):
            bg = IUB_LIGHT if i % 2 == 0 else "white"
            for c, val in enumerate([d.get("duty_date", ""),
                                     d.get("session", ""),
                                     d.get("session_type", "")]):
                f = ctk.CTkFrame(dtbl, fg_color=bg, corner_radius=0)
                f.grid(row=i + 1, column=c, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=9)).pack(padx=6, pady=2)

        # ── amount breakdown ──────────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="Amount Breakdown",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=IUB_GREEN).grid(row=4, column=0, sticky="w", pady=(12, 4))
        calc = ctk.CTkFrame(scroll, fg_color=IUB_LIGHT, corner_radius=6)
        calc.grid(row=5, column=0, sticky="ew")
        calc.grid_columnconfigure(1, weight=1)

        if data["unit"] == "per_script":
            rows_calc = [
                ("Total Scripts × Rate:",
                 f"{singles} × Rs. {rs:,.0f} = Rs. {base:,.0f}"),
                ("TOTAL:", f"Rs. {base:,.0f}"),
            ]
        else:
            rows_calc = [
                ("Single sessions:",
                 f"{singles} × Rs. {rs:,.0f} = Rs. {singles * rs:,.0f}"),
                ("Double sessions:",
                 f"{doubles} × Rs. {rd:,.0f} = Rs. {doubles * rd:,.0f}"),
            ]
            if role == "Superintendent" and self.extra_items:
                ei = self.extra_items
                remun = base
                contingent = sum(float(ei.get(k, 0) or 0) for k in
                                 ["menial", "stationery", "collection_qp", "dispatch_ab", "ice"])
                gross   = remun + contingent
                advance = float(ei.get("advance", 0) or 0)
                net     = max(0.0, gross - advance)
                rows_calc += [
                    ("Remuneration (subtotal):",        f"Rs. {remun:,.0f}"),
                    ("Collection of Question Papers:",  f"Rs. {float(ei.get('collection_qp', 0) or 0):,.0f}"),
                    ("Dispatch of Answer Books:",       f"Rs. {float(ei.get('dispatch_ab', 0) or 0):,.0f}"),
                    ("Menial Establishment:",           f"Rs. {float(ei.get('menial', 0) or 0):,.0f}"),
                    ("Stationery for Centre:",          f"Rs. {float(ei.get('stationery', 0) or 0):,.0f}"),
                    ("Ice for Centre:",                 f"Rs. {float(ei.get('ice', 0) or 0):,.0f}"),
                    ("Gross Total:",                    f"Rs. {gross:,.0f}"),
                    ("Less Advance:",                   f"Rs. {advance:,.0f}"),
                    ("NET PAYABLE:",                    f"Rs. {net:,.0f}"),
                ]
            else:
                rows_calc.append(("TOTAL:", f"Rs. {base:,.0f}"))

        for i, (lbl, val) in enumerate(rows_calc):
            is_total = lbl.startswith(("TOTAL", "NET"))
            font  = ctk.CTkFont(size=10, weight="bold") if is_total else ctk.CTkFont(size=10)
            color = IUB_GREEN if is_total else "#333333"
            ctk.CTkLabel(calc, text=lbl, font=font, text_color=color, anchor="w"
                         ).grid(row=i, column=0, sticky="w", padx=(12, 4), pady=2)
            ctk.CTkLabel(calc, text=val, font=font, text_color=color, anchor="e"
                         ).grid(row=i, column=1, sticky="e", padx=(4, 12), pady=2)

        # ── buttons ───────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=10)
        ctk.CTkButton(btn_frame, text="Generate This Bill",
                      fg_color=IUB_GREEN, width=160,
                      command=self._generate).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Close",
                      fg_color="gray", width=80,
                      command=self.destroy).pack(side="left", padx=4)

    def _generate(self):
        self.destroy()
        self.parent_screen._do_generate(self.appt_id, self.extra_items)


# ── Preview All Dialog ─────────────────────────────────────────────────────────

class _PreviewAllDialog(ctk.CTkToplevel):
    def __init__(self, parent_screen, session_id):
        super().__init__()
        self.parent_screen = parent_screen
        self.session_id    = session_id
        self.title("Preview All Bills")
        self.geometry("720x660")
        self.minsize(600, 500)
        self.resizable(True, True)
        self.grab_set()
        self._build()

    def _build(self):
        appts   = get_appointments_for_session(self.session_id)
        pending = [a for a in appts if not get_bill_for_appointment(a["id"])]

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(16, 4))

        ctk.CTkLabel(scroll, text="PREVIEW — ALL PENDING BILLS",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=IUB_GREEN).pack(pady=(0, 12))

        if not pending:
            ctk.CTkLabel(scroll, text="No pending bills in this session.",
                         font=ctk.CTkFont(size=11), text_color="gray").pack()
        else:
            for a in pending:
                self._render_card(scroll, a)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=10)
        ctk.CTkButton(btn_frame, text="Generate All Bills",
                      fg_color=IUB_GREEN, width=160,
                      command=self._gen_all).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Close",
                      fg_color="gray", width=80,
                      command=self.destroy).pack(side="left", padx=4)

    def _render_card(self, parent, a):
        card = ctk.CTkFrame(parent, fg_color=IUB_LIGHT, corner_radius=6)
        card.pack(fill="x", pady=4)

        if a["role"] == "Superintendent":
            hdr = ctk.CTkFrame(card, fg_color=IUB_GREEN, corner_radius=0)
            hdr.pack(fill="x")
            ctk.CTkLabel(hdr,
                         text=f"{a['full_name']}  —  Superintendent",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="white").pack(side="left", padx=8, pady=4)
            ctk.CTkLabel(card,
                         text="Requires contingent items — generate this bill individually.",
                         font=ctk.CTkFont(size=9), text_color="gray").pack(
                padx=8, pady=4, anchor="w")
            return

        try:
            data = _compute_bill_preview(a["id"])
        except Exception as e:
            hdr = ctk.CTkFrame(card, fg_color="#922b21", corner_radius=0)
            hdr.pack(fill="x")
            ctk.CTkLabel(hdr, text=f"{a['full_name']}  —  {a['role']}",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="white").pack(side="left", padx=8, pady=4)
            ctk.CTkLabel(card, text=f"Error: {e}",
                         font=ctk.CTkFont(size=9), text_color="#922b21").pack(
                padx=8, pady=4, anchor="w")
            return

        hdr = ctk.CTkFrame(card, fg_color=IUB_GREEN, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=f"{a['full_name']}  —  {a['role']}",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="white").pack(side="left", padx=8, pady=4)
        ctk.CTkLabel(hdr, text=f"Duties: {len(data['duties'])}",
                     font=ctk.CTkFont(size=9), text_color="white").pack(
            side="right", padx=8, pady=4)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=8, pady=6)

        rs      = data["rate_single"]
        rd      = data["rate_double"]
        singles = data["total_days"]
        doubles = data["total_double"]
        base    = data["base_amount"]

        if data["unit"] == "per_script":
            lines = [
                f"Total Scripts: {singles} × Rs. {rs:,.0f} = Rs. {base:,.0f}",
                f"Total:  Rs. {base:,.0f}",
            ]
        else:
            lines = [
                f"Single sessions:  {singles} × Rs. {rs:,.0f} = Rs. {singles * rs:,.0f}",
                f"Double sessions:  {doubles} × Rs. {rd:,.0f} = Rs. {doubles * rd:,.0f}",
                f"Total:  Rs. {base:,.0f}",
            ]

        for i, line in enumerate(lines):
            is_last = (i == len(lines) - 1)
            ctk.CTkLabel(body, text=line,
                         font=ctk.CTkFont(size=10, weight="bold" if is_last else "normal"),
                         text_color=IUB_GREEN if is_last else "#333333",
                         anchor="w").pack(anchor="w")

    def _gen_all(self):
        self.destroy()
        self.parent_screen._gen_all()


# ── Generate All Bills Dialog ─────────────────────────────────────────────────

class _GenAllBillsDialog(ctk.CTkToplevel):
    def __init__(self, parent_screen, pending_appts, session_name):
        super().__init__()
        self.parent_screen = parent_screen
        self._appts        = pending_appts
        self._session_name = session_name
        self.title("Generating All Bills")
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
            msg = f"{self._generated} bill(s) generated. Saved to outputs folder."
            if self._errors:
                msg += f"\n{self._errors} error(s) occurred."
            messagebox.showinfo("Complete", msg)
            outputs_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
            _open_file(outputs_dir)
            self.parent_screen._render_table()
            return
        a = self._appts[self._idx]
        self._status_label.configure(
            text=f"Generating bill {self._idx + 1} of {total}...")
        self._progress.set((self._idx + 1) / total)
        self._idx += 1
        try:
            result = calculate_bill(a["id"], None)
            appt   = result["appt"]
            duties = result["duties"]
            path   = generate_bill_pdf(result, appt, duties, self._session_name)
            conn = get_connection()
            try:
                conn.execute("UPDATE bills SET pdf_path=? WHERE bill_no=?",
                             (path, result["bill_no"]))
                conn.commit()
            finally:
                conn.close()
            self._generated += 1
        except Exception:
            self._errors += 1
        self.after(60, self._process_next)


# ── Contingent Items Dialog ────────────────────────────────────────────────────

class _ContingentDialog(ctk.CTkToplevel):
    def __init__(self, parent_screen, appointment_id, on_submit=None):
        super().__init__()
        self.parent    = parent_screen
        self.appt_id   = appointment_id
        self.on_submit = on_submit   # None → generate; callable → custom (e.g. show preview)
        self.title("Superintendent Contingent Items")
        self.geometry("440x420")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        duties        = get_duties_for_appointment(self.appt_id)
        session_count = len(duties)
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=16)
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Enter Contingent Items for Superintendent",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=0, column=0, columnspan=2, pady=(0, 12))

        fields = [
            ("Menial Establishment (Rs.)",             "menial",        "0"),
            ("Stationery for Centre (Rs.)",            "stationery",    "0"),
            (f"Collection of Question Papers (Rs.)\n"
             f"(auto: {session_count}×150 = {session_count * 150})",
                                                        "collection_qp", str(session_count * 150)),
            (f"Dispatch of Answer Books (Rs.)\n"
             f"(auto: {session_count}×150 = {session_count * 150})",
                                                        "dispatch_ab",   str(session_count * 150)),
            ("Ice for Centre (Rs.)",                   "ice",           "0"),
            ("Advance Already Paid (Rs.)",             "advance",       "0"),
        ]
        self._vars = {}
        for i, (lbl, key, default) in enumerate(fields, start=1):
            ctk.CTkLabel(f, text=lbl, font=ctk.CTkFont(size=10),
                         justify="left").grid(row=i, column=0, sticky="w", pady=4)
            var = ctk.StringVar(value=default)
            ctk.CTkEntry(f, textvariable=var, width=160).grid(
                row=i, column=1, padx=8, pady=4, sticky="w")
            self._vars[key] = var

        btn_label = "Preview Bill" if self.on_submit else "Generate Bill"
        btn_f = ctk.CTkFrame(f, fg_color="transparent")
        btn_f.grid(row=len(fields) + 1, column=0, columnspan=2, pady=14)
        ctk.CTkButton(btn_f, text=btn_label, fg_color=IUB_GREEN,
                      command=self._submit).pack(side="left", padx=8)
        ctk.CTkButton(btn_f, text="Cancel", fg_color="gray",
                      command=self.destroy).pack(side="left")

    def _submit(self):
        try:
            extra = {k: float(v.get() or 0) for k, v in self._vars.items()}
        except ValueError:
            messagebox.showerror("Validation",
                                  "All amounts must be numbers.", parent=self)
            return
        self.destroy()
        if self.on_submit:
            self.on_submit(extra)
        else:
            self.parent._do_generate(self.appt_id, extra)
