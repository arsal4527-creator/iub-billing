import os
import sys
import subprocess
import customtkinter as ctk
from tkinter import messagebox
from core.database import get_all_sessions, get_bills_for_session, get_session_by_id
from core.excel_exporter import export_session_excel

IUB_GREEN = "#1a5276"
IUB_LIGHT = "#d6eaf8"


def _open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])


class ReportsScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._session_id = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(self, fg_color=IUB_GREEN, corner_radius=0, height=60)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="Reports",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=15)

        btns = ctk.CTkFrame(hdr, fg_color="transparent")
        btns.pack(side="right", padx=16, pady=10)
        ctk.CTkButton(btns, text="Export to Excel", width=130, height=34,
                      fg_color="white", text_color=IUB_GREEN,
                      hover_color=IUB_LIGHT,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._export).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Print All PDFs", width=120, height=34,
                      fg_color="#1a8754", text_color="white",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._print_all).pack(side="left", padx=4)

        sel = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=0)
        sel.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(sel, text="Session:",
                     font=ctk.CTkFont(size=11)).pack(
            side="left", padx=(16, 4), pady=10)
        self._sess_var = ctk.StringVar()
        self._sess_menu = ctk.CTkOptionMenu(
            sel, variable=self._sess_var, values=[],
            width=300, command=self._on_session_change)
        self._sess_menu.pack(side="left", padx=4, pady=10)

        self._body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._body.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)
        self._body.grid_columnconfigure(0, weight=1)

    def refresh(self):
        sessions = get_all_sessions()
        names = [s["session_name"] for s in sessions]
        self._sessions_data = {s["session_name"]: s["id"] for s in sessions}
        self._sess_menu.configure(values=names or ["No sessions"])
        if names:
            self._sess_var.set(names[0])
            self._on_session_change(names[0])

    def _on_session_change(self, name):
        self._session_id = self._sessions_data.get(name)
        self._render()

    def _render(self):
        for w in self._body.winfo_children():
            w.destroy()
        if not self._session_id:
            return

        bills = get_bills_for_session(self._session_id)
        total_amount = sum(b["amount"] for b in bills)
        total_staff  = len(bills)

        # Summary cards
        card_row = ctk.CTkFrame(self._body, fg_color="transparent")
        card_row.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        for col, (label, val) in enumerate([
            ("Total Staff Billed", str(total_staff)),
            ("Total Amount",       f"Rs. {total_amount:,.0f}"),
            ("Bills Count",        str(total_staff)),
        ]):
            card = ctk.CTkFrame(card_row, corner_radius=8,
                                border_width=1, border_color="#d5d8dc",
                                width=180, height=80)
            card.grid(row=0, column=col, padx=8, pady=4)
            card.grid_propagate(False)
            ctk.CTkLabel(card, text=label,
                         font=ctk.CTkFont(size=10),
                         text_color="gray").pack(pady=(10, 2))
            ctk.CTkLabel(card, text=val,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=IUB_GREEN).pack()

        # Role summary table
        ctk.CTkLabel(self._body, text="Summary by Role",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=1, column=0, sticky="w", pady=(0, 6))

        role_tbl = ctk.CTkFrame(self._body, corner_radius=0)
        role_tbl.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        role_tbl.grid_columnconfigure((0, 1, 2, 3), weight=1)

        for col, h in enumerate(["Role", "No. of Staff",
                                  "Total Amount (Rs.)", "% of Total"]):
            fr = ctk.CTkFrame(role_tbl, fg_color=IUB_GREEN, corner_radius=0)
            fr.grid(row=0, column=col, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(fr, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="white").pack(padx=6, pady=4)

        role_data = {}
        for b in bills:
            r = b["role"]
            if r not in role_data:
                role_data[r] = {"count": 0, "total": 0.0}
            role_data[r]["count"] += 1
            role_data[r]["total"] += b["amount"]

        for i, (role, d) in enumerate(role_data.items()):
            bg = IUB_LIGHT if i % 2 == 0 else "white"
            pct = f"{d['total'] / total_amount * 100:.1f}%" if total_amount else "0%"
            for col, val in enumerate([role, str(d["count"]),
                                        f"Rs. {d['total']:,.0f}", pct]):
                fr = ctk.CTkFrame(role_tbl, fg_color=bg, corner_radius=0)
                fr.grid(row=i + 1, column=col, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(fr, text=val,
                             font=ctk.CTkFont(size=10),
                             text_color="#111111").pack(padx=6, pady=4)

        # Full bill list
        ctk.CTkLabel(self._body, text="All Bills",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=3, column=0, sticky="w", pady=(0, 6))

        bill_tbl = ctk.CTkFrame(self._body, corner_radius=0)
        bill_tbl.grid(row=4, column=0, sticky="ew")
        bill_tbl.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        for col, h in enumerate(["Bill No.", "Name", "Role",
                                  "Centre", "Amount (Rs.)"]):
            fr = ctk.CTkFrame(bill_tbl, fg_color=IUB_GREEN, corner_radius=0)
            fr.grid(row=0, column=col, sticky="ew", padx=1, pady=1)
            ctk.CTkLabel(fr, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="white").pack(padx=6, pady=4)

        for i, b in enumerate(bills):
            bg = IUB_LIGHT if i % 2 == 0 else "white"
            for col, val in enumerate([b["bill_no"] or "—", b["full_name"],
                                        b["role"], b["centre"] or "—",
                                        f"Rs. {b['amount']:,.0f}"]):
                fr = ctk.CTkFrame(bill_tbl, fg_color=bg, corner_radius=0)
                fr.grid(row=i + 1, column=col, sticky="ew", padx=1, pady=1)
                ctk.CTkLabel(fr, text=val, font=ctk.CTkFont(size=10),
                             wraplength=160,
                             text_color="#111111").pack(padx=6, pady=4, anchor="w")

    def _export(self):
        if not self._session_id:
            return
        try:
            path = export_session_excel(self._session_id)
            if messagebox.askyesno("Exported",
                                    f"Saved to:\n{path}\n\nOpen now?"):
                _open_file(path)
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self)

    def _print_all(self):
        if not self._session_id:
            return
        bills = get_bills_for_session(self._session_id)
        opened = 0
        for b in bills:
            if b["pdf_path"] and os.path.exists(b["pdf_path"]):
                _open_file(b["pdf_path"])
                opened += 1
        if opened == 0:
            messagebox.showinfo("No PDFs",
                                "No PDF files found. Generate bills first.")
        else:
            messagebox.showinfo("Done", f"Opened {opened} PDF(s).")
