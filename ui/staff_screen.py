import re
import customtkinter as ctk
from tkinter import messagebox
from core.database import get_all_staff, add_staff, update_staff, delete_staff, get_connection

IUB_GREEN = "#1a5276"
IUB_LIGHT = "#d6eaf8"
CNIC_RE   = re.compile(r"^\d{5}-\d{7}-\d$")

STATUS_ORDER  = ["applied", "shortlisted", "appointed"]
STATUS_LABELS = {"applied": "Applicants", "shortlisted": "Shortlisted", "appointed": "Appointed"}
STATUS_COLORS = {"applied": "#2874a6", "shortlisted": "#1a8754", "appointed": "#7d6608"}


def _validate_cnic(cnic):
    return bool(CNIC_RE.match(cnic.strip()))


def _load_grouped_data():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT full_name, cnic, apply_for, institution, status, session_tag "
            "FROM applications ORDER BY session_tag, full_name"
        ).fetchall()
    except Exception:
        return {}
    finally:
        conn.close()
    groups = {}
    for row in rows:
        tag = row["session_tag"] or "— No Session —"
        if tag not in groups:
            groups[tag] = {s: [] for s in STATUS_ORDER}
        status = row["status"] or "applied"
        if status in groups[tag]:
            groups[tag][status].append(dict(row))
    return groups


class StaffScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._mode = "list"
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=IUB_GREEN, corner_radius=0, height=60)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="Staff Register",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=15)
        ctk.CTkButton(hdr, text="+ Add Staff", width=120, height=34,
                      fg_color="white", text_color=IUB_GREEN,
                      hover_color=IUB_LIGHT,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._open_add).pack(side="right", padx=16, pady=12)

        # Toggle bar
        tbar = ctk.CTkFrame(self, fg_color=("gray85", "gray20"), corner_radius=0, height=40)
        tbar.grid(row=1, column=0, sticky="ew")
        tbar.grid_propagate(False)
        self._list_btn = ctk.CTkButton(
            tbar, text="List", width=80, height=28,
            fg_color=IUB_GREEN, text_color="white",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._show_list)
        self._list_btn.pack(side="left", padx=(12, 4), pady=6)
        self._group_btn = ctk.CTkButton(
            tbar, text="Group", width=80, height=28,
            fg_color="transparent", text_color=IUB_GREEN,
            font=ctk.CTkFont(size=11),
            command=self._show_group)
        self._group_btn.pack(side="left", padx=4, pady=6)

        # Body container
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ── List panel ─────────────────────────────────────────────────────────
        self._list_panel = ctk.CTkFrame(body, fg_color="transparent")
        self._list_panel.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self._list_panel.grid_columnconfigure(0, weight=1)
        self._list_panel.grid_rowconfigure(1, weight=1)

        sf = ctk.CTkFrame(self._list_panel, fg_color="transparent")
        sf.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(sf, text="Search:", font=ctk.CTkFont(size=12)).pack(side="left")
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter())
        ctk.CTkEntry(sf, textvariable=self._search_var, width=300,
                     placeholder_text="Name or CNIC").pack(side="left", padx=8)

        self._table = ctk.CTkScrollableFrame(self._list_panel, fg_color="transparent")
        self._table.grid(row=1, column=0, sticky="nsew")
        for col in range(6):
            self._table.grid_columnconfigure(col, weight=1 if col < 5 else 0)
        self._render_list_headers()
        self._rows = []

        # ── Group panel ────────────────────────────────────────────────────────
        self._group_panel = ctk.CTkScrollableFrame(body, fg_color="transparent")
        self._group_panel.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self._group_panel.grid_columnconfigure(0, weight=1)
        self._group_panel.grid_remove()

    def _render_list_headers(self):
        for col, h in enumerate(["Full Name", "CNIC", "Phone",
                                  "Designation", "Institution", "Action"]):
            f = ctk.CTkFrame(self._table, fg_color=IUB_GREEN, corner_radius=0)
            f.grid(row=0, column=col, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(f, text=h, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="white").pack(padx=6, pady=5)

    def _show_list(self):
        self._mode = "list"
        self._list_btn.configure(fg_color=IUB_GREEN, text_color="white",
                                  font=ctk.CTkFont(size=11, weight="bold"))
        self._group_btn.configure(fg_color="transparent", text_color=IUB_GREEN,
                                   font=ctk.CTkFont(size=11))
        self._group_panel.grid_remove()
        self._list_panel.grid()
        self._filter()

    def _show_group(self):
        self._mode = "group"
        self._group_btn.configure(fg_color=IUB_GREEN, text_color="white",
                                   font=ctk.CTkFont(size=11, weight="bold"))
        self._list_btn.configure(fg_color="transparent", text_color=IUB_GREEN,
                                  font=ctk.CTkFont(size=11))
        self._list_panel.grid_remove()
        self._group_panel.grid()
        self._render_group()

    def refresh(self):
        if self._mode == "list":
            self._filter()
        else:
            self._render_group()

    def _filter(self):
        q = self._search_var.get().strip()
        staff = get_all_staff(q)
        for w in self._rows:
            w.destroy()
        self._rows.clear()
        for i, s in enumerate(staff):
            bg = IUB_LIGHT if i % 2 == 0 else "white"
            row_widgets = []
            for col, val in enumerate([s["full_name"], s["cnic"],
                                        s["phone"] or "—",
                                        s["designation"] or "—",
                                        s["institution"] or "—"]):
                f = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=0)
                f.grid(row=i + 1, column=col, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=10),
                             wraplength=180,
                             text_color="#111111").pack(padx=6, pady=4, anchor="w")
                row_widgets.append(f)
            act = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=0)
            act.grid(row=i + 1, column=5, sticky="ew", padx=1, pady=1)
            ctk.CTkButton(act, text="Edit", width=60, height=26,
                          font=ctk.CTkFont(size=9), fg_color=IUB_GREEN,
                          command=lambda sid=s["id"]: self._open_edit(sid)
                          ).pack(side="left", padx=(6, 2), pady=4)
            ctk.CTkButton(act, text="Delete", width=60, height=26,
                          font=ctk.CTkFont(size=9), fg_color="#922b21",
                          command=lambda sid=s["id"], name=s["full_name"]: self._delete(sid, name)
                          ).pack(side="left", padx=(2, 6), pady=4)
            row_widgets.append(act)
            self._rows.extend(row_widgets)

    def _render_group(self):
        for w in self._group_panel.winfo_children():
            w.destroy()
        groups = _load_grouped_data()
        if not groups:
            ctk.CTkLabel(self._group_panel, text="No application data found.",
                         font=ctk.CTkFont(size=12), text_color="gray").pack(pady=40)
            return

        for session_tag, sub in groups.items():
            total = sum(len(sub[s]) for s in STATUS_ORDER)
            sess_hdr = ctk.CTkFrame(self._group_panel, fg_color=IUB_GREEN, corner_radius=6)
            sess_hdr.pack(fill="x", pady=(10, 2))
            ctk.CTkLabel(sess_hdr,
                         text=f"  Session: {session_tag}   ({total} total)",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color="white").pack(side="left", padx=12, pady=8)

            for status in STATUS_ORDER:
                people = sub.get(status, [])
                color  = STATUS_COLORS[status]
                sub_hdr = ctk.CTkFrame(self._group_panel, fg_color=color, corner_radius=4)
                sub_hdr.pack(fill="x", padx=16, pady=(4, 1))
                ctk.CTkLabel(sub_hdr,
                             text=f"  {STATUS_LABELS[status]}  ({len(people)})",
                             font=ctk.CTkFont(size=11, weight="bold"),
                             text_color="white").pack(side="left", padx=8, pady=4)

                if not people:
                    ctk.CTkLabel(self._group_panel, text="(none)",
                                 font=ctk.CTkFont(size=10),
                                 text_color="gray").pack(anchor="w", padx=48, pady=2)
                    continue

                tbl = ctk.CTkFrame(self._group_panel, fg_color="transparent")
                tbl.pack(fill="x", padx=32, pady=(0, 4))
                for ci in range(4):
                    tbl.grid_columnconfigure(ci, weight=1)

                col_hdr = ctk.CTkFrame(tbl, fg_color=IUB_LIGHT, corner_radius=0)
                col_hdr.grid(row=0, column=0, columnspan=4, sticky="ew")
                col_hdr.grid_columnconfigure((0, 1, 2, 3), weight=1)
                for ci, ch in enumerate(["Name", "CNIC", "Role", "Institution"]):
                    ctk.CTkLabel(col_hdr, text=ch,
                                 font=ctk.CTkFont(size=9, weight="bold"),
                                 text_color=IUB_GREEN).grid(
                        row=0, column=ci, padx=6, pady=3, sticky="w")

                for j, person in enumerate(people):
                    bg = "white" if j % 2 == 0 else IUB_LIGHT
                    pf = ctk.CTkFrame(tbl, fg_color=bg, corner_radius=0)
                    pf.grid(row=j + 1, column=0, columnspan=4, sticky="ew")
                    pf.grid_columnconfigure((0, 1, 2, 3), weight=1)
                    for ci, val in enumerate([
                        person.get("full_name", ""),
                        person.get("cnic", ""),
                        person.get("apply_for", "") or "—",
                        person.get("institution", "") or "—",
                    ]):
                        ctk.CTkLabel(pf, text=val,
                                     font=ctk.CTkFont(size=10),
                                     text_color="#111111",
                                     wraplength=200).grid(
                            row=0, column=ci, padx=6, pady=3, sticky="w")

    def _delete(self, staff_id, name):
        confirmed = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete {name}? This cannot be undone.",
            parent=self)
        if not confirmed:
            return
        try:
            delete_staff(staff_id)
            self.refresh()
        except ValueError as e:
            messagebox.showerror("Cannot Delete", str(e), parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _open_add(self):
        _StaffForm(self, None)

    def _open_edit(self, staff_id):
        from core.database import get_staff_by_id
        s = get_staff_by_id(staff_id)
        _StaffForm(self, s)

    def _on_save(self):
        self.refresh()


class _StaffForm(ctk.CTkToplevel):
    def __init__(self, parent_screen, staff_row):
        super().__init__()
        self.parent_screen = parent_screen
        self.staff = staff_row
        self.title("Edit Staff" if staff_row else "Add Staff")
        self.geometry("480x460")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=20)
        f.grid_columnconfigure(1, weight=1)

        fields = [
            ("Full Name *",              "full_name"),
            ("CNIC * (XXXXX-XXXXXXX-X)", "cnic"),
            ("Phone",                    "phone"),
            ("Address",                  "address"),
            ("Designation",              "designation"),
            ("Institution",              "institution"),
        ]
        self._vars = {}
        for i, (label, key) in enumerate(fields):
            ctk.CTkLabel(f, text=label,
                         font=ctk.CTkFont(size=11)).grid(
                row=i, column=0, sticky="w", pady=4)
            var = ctk.StringVar(
                value=self.staff[key] if self.staff and self.staff[key] else "")
            ctk.CTkEntry(f, textvariable=var, width=280).grid(
                row=i, column=1, padx=10, pady=4, sticky="ew")
            self._vars[key] = var

        btn_f = ctk.CTkFrame(f, fg_color="transparent")
        btn_f.grid(row=len(fields), column=0, columnspan=2, pady=16)
        ctk.CTkButton(btn_f, text="Save", fg_color=IUB_GREEN,
                      command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_f, text="Cancel", fg_color="gray",
                      command=self.destroy).pack(side="left")

    def _save(self):
        vals = {k: v.get().strip() for k, v in self._vars.items()}
        if not vals["full_name"]:
            messagebox.showerror("Validation", "Full Name is required.", parent=self)
            return
        if not _validate_cnic(vals["cnic"]):
            messagebox.showerror(
                "Validation", "CNIC must be in format XXXXX-XXXXXXX-X", parent=self)
            return
        try:
            if self.staff:
                update_staff(self.staff["id"], **vals)
            else:
                add_staff(**vals)
            self.parent_screen._on_save()
            self.destroy()
        except Exception as e:
            if "UNIQUE" in str(e):
                messagebox.showerror(
                    "Duplicate CNIC",
                    "A staff member with this CNIC already exists.", parent=self)
            else:
                messagebox.showerror("Error", str(e), parent=self)
