import tkinter as tk
import customtkinter as ctk
from core.database import get_dashboard_stats, get_recent_sessions, get_billing_by_role

IUB_GREEN = "#1a5276"
IUB_DARK  = "#154360"
IUB_LIGHT = "#d6eaf8"


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(self, fg_color=IUB_GREEN, corner_radius=0, height=60)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="Dashboard",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=15)

        self._body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._body.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        self._body.grid_columnconfigure(0, weight=1)

    def refresh(self):
        for w in self._body.winfo_children():
            w.destroy()
        self._render()

    def _render(self):
        stats  = get_dashboard_stats()
        recent = get_recent_sessions(5)
        roles  = get_billing_by_role()

        # ── ROW 1: stat cards ─────────────────────────────────────────────────
        cards_row = ctk.CTkFrame(self._body, fg_color="transparent")
        cards_row.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        for col in range(4):
            cards_row.grid_columnconfigure(col, weight=1)

        for col, (title, value) in enumerate([
            ("Total Sessions",      str(stats["sessions"])),
            ("Staff in Register",   str(stats["staff"])),
            ("Bills Generated",     str(stats["bills"])),
            ("Total Amount Billed", f"Rs. {stats['amount']:,.0f}"),
        ]):
            card = ctk.CTkFrame(cards_row, fg_color=IUB_GREEN, corner_radius=10)
            card.grid(row=0, column=col, padx=8, sticky="nsew")
            ctk.CTkLabel(card, text=title,
                         font=ctk.CTkFont(size=11),
                         text_color="white").pack(pady=(16, 4), padx=16)
            ctk.CTkLabel(card, text=value,
                         font=ctk.CTkFont(size=24, weight="bold"),
                         text_color="white",
                         wraplength=200).pack(pady=(0, 16), padx=16)

        # ── ROW 2: two panels ─────────────────────────────────────────────────
        panels = ctk.CTkFrame(self._body, fg_color="transparent")
        panels.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        panels.grid_columnconfigure(0, weight=1)
        panels.grid_columnconfigure(1, weight=1)

        self._build_recent_sessions(panels, recent)
        self._build_role_chart(panels, roles)

        # ── ROW 3: quick actions ──────────────────────────────────────────────
        qa = ctk.CTkFrame(self._body, fg_color="transparent")
        qa.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for label, screen in [
            ("+ New Session",  "sessions"),
            ("Enter Duties",   "duties"),
            ("Generate Bills", "billing"),
            ("View Reports",   "reports"),
        ]:
            btn = ctk.CTkButton(qa, text=label, width=140, height=38,
                                fg_color="white", text_color=IUB_GREEN,
                                hover_color=IUB_LIGHT,
                                font=ctk.CTkFont(size=11, weight="bold"),
                                command=lambda s=screen: self.app.navigate(s))
            btn.pack(side="left", padx=8, pady=4)

    def _build_recent_sessions(self, parent, recent):
        panel = ctk.CTkFrame(parent, corner_radius=8,
                              border_width=1, border_color="#d5d8dc")
        panel.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="Recent Sessions",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=0, column=0, padx=14, pady=(12, 8), sticky="w")

        if not recent:
            ctk.CTkLabel(panel, text="No sessions yet.",
                         font=ctk.CTkFont(size=10), text_color="gray").grid(
                row=1, column=0, padx=14, pady=20)
            return

        for r, item in enumerate(recent, start=1):
            s   = item["session"]
            bg  = IUB_LIGHT if r % 2 == 0 else "transparent"
            rf  = ctk.CTkFrame(panel, fg_color=bg, corner_radius=4)
            rf.grid(row=r, column=0, sticky="ew", padx=8, pady=2)
            rf.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(rf,
                         text=f"{s['session_name']} ({s['year'] or '—'})",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         wraplength=200, justify="left",
                         anchor="w").grid(row=0, column=0, padx=8, pady=(4, 0), sticky="w")
            ctk.CTkLabel(rf,
                         text=f"Appts: {item['appt_count']}   Bills: {item['bill_count']}",
                         font=ctk.CTkFont(size=9), text_color="gray",
                         anchor="w").grid(row=1, column=0, padx=8, pady=(0, 4), sticky="w")
            ctk.CTkLabel(rf,
                         text=f"Rs. {item['total_amount']:,.0f}",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#1a8754").grid(row=0, column=1, rowspan=2, padx=8)
            ctk.CTkButton(rf, text="View", width=52, height=26,
                          font=ctk.CTkFont(size=9), fg_color=IUB_GREEN,
                          command=lambda sid=s["id"]: self.app.navigate(
                              "sessions", session_id=sid)
                          ).grid(row=0, column=2, rowspan=2, padx=8, pady=4)

    def _build_role_chart(self, parent, roles):
        panel = ctk.CTkFrame(parent, corner_radius=8,
                              border_width=1, border_color="#d5d8dc")
        panel.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="Amount Billed by Role",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=0, column=0, padx=14, pady=(12, 8), sticky="w")

        canvas_wrap = ctk.CTkFrame(panel, fg_color=IUB_LIGHT, corner_radius=6)
        canvas_wrap.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")

        n_bars  = max(len(roles), 1)
        bar_h   = 26
        gap     = 8
        height  = 24 + n_bars * (bar_h + gap)

        canvas = tk.Canvas(canvas_wrap, bg=IUB_LIGHT,
                           highlightthickness=0, height=height)
        canvas.pack(fill="both", expand=True, padx=6, pady=6)

        if not roles:
            canvas.create_text(12, 12, text="No billing data yet.",
                               anchor="nw", fill="gray", font=("Arial", 10))
            return

        canvas._chart_data = roles

        def draw(event=None, c=canvas):
            c.delete("all")
            data = getattr(c, "_chart_data", [])
            if not data:
                return
            w = c.winfo_width()
            if w <= 1:
                return
            max_val      = max(r["total"] for r in data) or 1
            left_margin  = 165
            right_margin = 110
            top_margin   = 12

            for i, row in enumerate(data):
                y     = top_margin + i * (bar_h + gap)
                avail = max(w - left_margin - right_margin, 4)
                bw    = max(4, (row["total"] / max_val) * avail)
                c.create_text(left_margin - 8, y + bar_h // 2,
                              text=row["role"], anchor="e",
                              fill=IUB_GREEN, font=("Arial", 9))
                c.create_rectangle(left_margin, y,
                                   left_margin + bw, y + bar_h,
                                   fill=IUB_GREEN, outline="")
                c.create_text(left_margin + bw + 6, y + bar_h // 2,
                              text=f"Rs. {row['total']:,.0f}",
                              anchor="w", fill=IUB_GREEN, font=("Arial", 9))

        canvas.bind("<Configure>", draw)
        canvas.after(80, draw)
