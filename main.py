import sys
import os

# Ensure project root is on the path so `core` and `ui` imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# macOS compatibility: initialise Tk once before customtkinter loads,
# which works around the "macOS 15 (1507) or later required" crash.
if sys.platform == "darwin":
    os.environ["TK_SILENCE_DEPRECATION"] = "1"
    try:
        import tkinter
        tkinter.Tk().destroy()
    except Exception:
        pass

from core.database import init_db, seed_sample_data


def main():
    init_db()
    seed_sample_data()

    from ui.app import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
