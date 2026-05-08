import customtkinter as ctk
from tkinter import messagebox
from core.database import (
    get_all_rates, update_rate,
    has_billing_pin, set_billing_pin, delete_billing_pin,
)

IUB_GREEN = "#1a5276"
IUB_DARK  = "#154360"
IUB_LIGHT = "#d6eaf8"


class SettingsScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._rows = []
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(self, fg_color=IUB_GREEN, corner_radius=0, height=60)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="Settings",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=15)
        ctk.CTkButton(hdr, text="Save Rates", width=120, height=34,
                      fg_color="white", text_color=IUB_GREEN,
                      hover_color=IUB_LIGHT,
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._save).pack(side="right", padx=16, pady=12)

        warn = ctk.CTkFrame(self, fg_color="#fef9e7", corner_radius=0, height=36)
        warn.grid(row=1, column=0, sticky="ew")
        warn.grid_propagate(False)
        ctk.CTkLabel(warn,
                     text="⚠  Changing rates will only affect new bills. "
                          "Existing bills are not retroactively affected.",
                     font=ctk.CTkFont(size=10),
                     text_color="#7d6608").pack(pady=8)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=40, pady=20)
        body.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._body = body
        self._render()

    def refresh(self):
        self._render()

    def _render(self):
        for w in self._body.winfo_children():
            w.destroy()
        self._rows.clear()

        # ── Rate Management ────────────────────────────────────────────────────
        ctk.CTkLabel(self._body, text="Rate Management",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        for col, h in enumerate(["Role", "Single Session Rate (Rs.)",
                                  "Double Session Rate (Rs.)", "Last Updated"]):
            fr = ctk.CTkFrame(self._body, fg_color=IUB_GREEN, corner_radius=0)
            fr.grid(row=1, column=col, sticky="ew", padx=2, pady=2)
            ctk.CTkLabel(fr, text=h, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="white").pack(padx=10, pady=6)

        rates = get_all_rates()
        for i, r in enumerate(rates):
            bg = IUB_LIGHT if i % 2 == 0 else "white"

            fr0 = ctk.CTkFrame(self._body, fg_color=bg, corner_radius=0)
            fr0.grid(row=i + 2, column=0, sticky="ew", padx=2, pady=2)
            ctk.CTkLabel(fr0, text=r["role"],
                         font=ctk.CTkFont(size=11),
                         text_color="#111111").pack(
                padx=10, pady=6, anchor="w")

            single_var = ctk.StringVar(value=str(int(r["rate_single"])))
            double_var = ctk.StringVar(value=str(int(r["rate_double"])))

            for col, var in [(1, single_var), (2, double_var)]:
                fr = ctk.CTkFrame(self._body, fg_color=bg, corner_radius=0)
                fr.grid(row=i + 2, column=col, sticky="ew", padx=2, pady=2)
                ctk.CTkEntry(fr, textvariable=var, width=140,
                             justify="right").pack(padx=10, pady=4)

            fr3 = ctk.CTkFrame(self._body, fg_color=bg, corner_radius=0)
            fr3.grid(row=i + 2, column=3, sticky="ew", padx=2, pady=2)
            updated = r["updated_at"][:10] if r["updated_at"] else "—"
            ctk.CTkLabel(fr3, text=updated, font=ctk.CTkFont(size=10),
                         text_color="gray").pack(padx=10, pady=6)

            self._rows.append((r["role"], single_var, double_var))

        # ── Security — Billing PIN ─────────────────────────────────────────────
        sep_row = len(rates) + 2
        ctk.CTkFrame(self._body, fg_color=("gray70", "gray35"),
                     height=1, corner_radius=0).grid(
            row=sep_row, column=0, columnspan=4, sticky="ew", pady=(24, 0))

        ctk.CTkLabel(self._body, text="Security — Billing PIN",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=sep_row + 1, column=0, columnspan=4, sticky="w", pady=(12, 4))

        pin_info = (
            "The billing PIN locks the Generate Bills section. "
            "A correct PIN is required to view bills, delete a bill, or re-generate one. "
            "All unlock attempts and deletions are recorded in the audit log."
        )
        ctk.CTkLabel(self._body, text=pin_info,
                     font=ctk.CTkFont(size=10), text_color="gray",
                     wraplength=600, justify="left").grid(
            row=sep_row + 2, column=0, columnspan=4, sticky="w", pady=(0, 12))

        pin_card = ctk.CTkFrame(self._body, fg_color=IUB_LIGHT, corner_radius=8)
        pin_card.grid(row=sep_row + 3, column=0, columnspan=4, sticky="ew", pady=4)
        pin_card.grid_columnconfigure(1, weight=1)

        has_pin = has_billing_pin()
        status_text = "Active — billing section is locked" if has_pin else "Not set — billing section is open"
        status_color = "#1a8754" if has_pin else "#b7950b"

        ctk.CTkLabel(pin_card, text="PIN Status:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=IUB_GREEN).grid(
            row=0, column=0, sticky="w", padx=16, pady=12)
        ctk.CTkLabel(pin_card, text=status_text,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=status_color).grid(
            row=0, column=1, sticky="w", padx=8, pady=12)

        btn_frame = ctk.CTkFrame(pin_card, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=12, pady=8)

        if has_pin:
            ctk.CTkButton(btn_frame, text="Change PIN", width=110, height=32,
                          fg_color=IUB_GREEN, text_color="white",
                          hover_color=IUB_DARK,
                          font=ctk.CTkFont(size=10, weight="bold"),
                          command=self._change_pin).pack(side="left", padx=4)
            ctk.CTkButton(btn_frame, text="Remove PIN", width=110, height=32,
                          fg_color="#922b21", text_color="white",
                          hover_color="#7b241c",
                          font=ctk.CTkFont(size=10),
                          command=self._remove_pin).pack(side="left", padx=4)
        else:
            ctk.CTkButton(btn_frame, text="Set PIN", width=110, height=32,
                          fg_color=IUB_GREEN, text_color="white",
                          hover_color=IUB_DARK,
                          font=ctk.CTkFont(size=10, weight="bold"),
                          command=self._set_pin).pack(side="left", padx=4)

    def _save(self):
        errors = []
        updates = []
        for role, sv, dv in self._rows:
            try:
                rs = float(sv.get())
                rd = float(dv.get())
                if rs < 0 or rd < 0:
                    raise ValueError
                updates.append((role, rs, rd))
            except ValueError:
                errors.append(role)

        if errors:
            messagebox.showerror(
                "Validation",
                f"Invalid rates for: {', '.join(errors)}\n"
                "All rates must be non-negative numbers.",
                parent=self)
            return

        for role, rs, rd in updates:
            update_rate(role, rs, rd)

        messagebox.showinfo("Saved", "Rates updated successfully.", parent=self)
        self._render()

    def _set_pin(self):
        _PinSetupDialog(self, existing=False)

    def _change_pin(self):
        _PinSetupDialog(self, existing=True)

    def _remove_pin(self):
        _PinRemoveDialog(self)

    def on_pin_saved(self):
        self._render()


# ── PIN Setup Dialog ───────────────────────────────────────────────────────────

class _PinSetupDialog(ctk.CTkToplevel):
    def __init__(self, parent_screen, existing=False):
        super().__init__()
        self.parent_screen = parent_screen
        self.existing = existing
        self.title("Change PIN" if existing else "Set Billing PIN")
        self.geometry("380x320")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(f, text="Change Billing PIN" if self.existing else "Set Billing PIN",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=IUB_GREEN).pack(pady=(0, 4))
        ctk.CTkLabel(f, text="Use a 4–8 digit numeric PIN.",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(pady=(0, 16))

        if self.existing:
            ctk.CTkLabel(f, text="Current PIN:",
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
            self._old_var = ctk.StringVar()
            ctk.CTkEntry(f, textvariable=self._old_var, show="●",
                         width=240, placeholder_text="Current PIN").pack(pady=(2, 12))
        else:
            self._old_var = None

        ctk.CTkLabel(f, text="New PIN:",
                     font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._new_var = ctk.StringVar()
        ctk.CTkEntry(f, textvariable=self._new_var, show="●",
                     width=240, placeholder_text="New PIN (4–8 digits)").pack(pady=(2, 8))

        ctk.CTkLabel(f, text="Confirm PIN:",
                     font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._confirm_var = ctk.StringVar()
        ctk.CTkEntry(f, textvariable=self._confirm_var, show="●",
                     width=240, placeholder_text="Repeat new PIN").pack(pady=(2, 12))

        self._err = ctk.CTkLabel(f, text="", font=ctk.CTkFont(size=10),
                                  text_color="#e74c3c")
        self._err.pack()

        btn_f = ctk.CTkFrame(f, fg_color="transparent")
        btn_f.pack(pady=(8, 0))
        ctk.CTkButton(btn_f, text="Save PIN", fg_color=IUB_GREEN,
                      width=110, command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(btn_f, text="Cancel", fg_color="gray",
                      width=80, command=self.destroy).pack(side="left")

    def _save(self):
        new = self._new_var.get().strip()
        confirm = self._confirm_var.get().strip()
        old = self._old_var.get().strip() if self._old_var else None

        if not new.isdigit() or not (4 <= len(new) <= 8):
            self._err.configure(text="PIN must be 4–8 digits (numbers only).")
            return
        if new != confirm:
            self._err.configure(text="PINs do not match.")
            return
        try:
            set_billing_pin(new, old_pin=old)
            self.destroy()
            messagebox.showinfo("PIN Saved", "Billing PIN has been saved.\n"
                                "The billing section is now locked.")
            self.parent_screen.on_pin_saved()
        except ValueError as e:
            self._err.configure(text=str(e))


# ── PIN Remove Dialog ──────────────────────────────────────────────────────────

class _PinRemoveDialog(ctk.CTkToplevel):
    def __init__(self, parent_screen):
        super().__init__()
        self.parent_screen = parent_screen
        self.title("Remove Billing PIN")
        self.geometry("360x220")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(f, text="Remove Billing PIN",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#922b21").pack(pady=(0, 4))
        ctk.CTkLabel(f, text="Enter your current PIN to confirm removal.\n"
                              "The billing section will become open to all users.",
                     font=ctk.CTkFont(size=10), text_color="gray",
                     justify="center").pack(pady=(0, 16))

        self._pin_var = ctk.StringVar()
        ctk.CTkEntry(f, textvariable=self._pin_var, show="●",
                     width=200, placeholder_text="Current PIN").pack(pady=(0, 8))

        self._err = ctk.CTkLabel(f, text="", font=ctk.CTkFont(size=10),
                                  text_color="#e74c3c")
        self._err.pack()

        btn_f = ctk.CTkFrame(f, fg_color="transparent")
        btn_f.pack(pady=(8, 0))
        ctk.CTkButton(btn_f, text="Remove PIN", fg_color="#922b21",
                      width=110, command=self._remove).pack(side="left", padx=6)
        ctk.CTkButton(btn_f, text="Cancel", fg_color="gray",
                      width=80, command=self.destroy).pack(side="left")

    def _remove(self):
        pin = self._pin_var.get().strip()
        if not pin:
            self._err.configure(text="Please enter your current PIN.")
            return
        try:
            delete_billing_pin(pin)
            self.destroy()
            messagebox.showinfo("PIN Removed", "Billing PIN has been removed.")
            self.parent_screen.on_pin_saved()
        except ValueError as e:
            self._err.configure(text=str(e))
