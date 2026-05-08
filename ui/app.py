import customtkinter as ctk
from ui.dashboard_screen import DashboardScreen
from ui.applications_screen import ApplicationsScreen
from ui.staff_screen import StaffScreen
from ui.sessions_screen import SessionsScreen
from ui.duties_screen import DutiesScreen
from ui.billing_screen import BillingScreen
from ui.reports_screen import ReportsScreen
from ui.settings_screen import SettingsScreen

IUB_GREEN = "#1a5276"
IUB_DARK  = "#154360"
NAV_W     = 210


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IUB Billing System — Examinations Branch")
        self.geometry("1200x750")
        self.minsize(1200, 750)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self._build_ui()
        self._show_screen("dashboard")

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ────────────────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=NAV_W, corner_radius=0,
                                     fg_color=IUB_GREEN)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(9, weight=1)

        # Logo block
        logo = ctk.CTkFrame(self.sidebar, fg_color=IUB_DARK, corner_radius=0)
        logo.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(logo, text="IUB",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="white").pack(pady=(14, 0))
        ctk.CTkLabel(logo, text="Examinations Branch\nBilling System",
                     font=ctk.CTkFont(size=10), text_color="#aed6f1",
                     justify="center").pack(pady=(2, 12))

        nav_items = [
            ("dashboard",    "  Dashboard"),
            ("applications", "  Applications"),
            ("staff",        "  Staff Register"),
            ("sessions",     "  Sessions & Appts"),
            ("duties",       "  Duty Entry"),
            ("billing",      "  Generate Bills"),
            ("reports",      "  Reports"),
            ("settings",     "  Settings"),
        ]
        self._nav_buttons = {}
        for i, (key, label) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self.sidebar, text=label,
                font=ctk.CTkFont(size=12),
                fg_color="transparent", text_color="white",
                hover_color=IUB_DARK, anchor="w",
                command=lambda k=key: self._show_screen(k),
            )
            btn.grid(row=i + 1, column=0, sticky="ew", padx=4, pady=2)
            self._nav_buttons[key] = btn

        # Footer
        footer = ctk.CTkFrame(self.sidebar, fg_color=IUB_DARK, corner_radius=0)
        footer.grid(row=10, column=0, sticky="ew")
        ctk.CTkLabel(footer, text="IUB Billing System v1.0",
                     font=ctk.CTkFont(size=9), text_color="#aed6f1").pack(pady=8)

        # ── Content frame ──────────────────────────────────────────────────────
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self._screens = {}
        screen_classes = {
            "dashboard":    DashboardScreen,
            "applications": ApplicationsScreen,
            "staff":        StaffScreen,
            "sessions":     SessionsScreen,
            "duties":       DutiesScreen,
            "billing":      BillingScreen,
            "reports":      ReportsScreen,
            "settings":     SettingsScreen,
        }
        for key, cls in screen_classes.items():
            frame = cls(self.content, self)
            frame.grid(row=0, column=0, sticky="nsew")
            self._screens[key] = frame

        self._current = None

    def _show_screen(self, key):
        for k, btn in self._nav_buttons.items():
            btn.configure(fg_color=IUB_DARK if k == key else "transparent")
        screen = self._screens[key]
        screen.tkraise()
        if hasattr(screen, "refresh"):
            screen.refresh()
        self._current = key

    def navigate(self, key, **kwargs):
        self._show_screen(key)
        screen = self._screens[key]
        if kwargs and hasattr(screen, "set_context"):
            screen.set_context(**kwargs)
