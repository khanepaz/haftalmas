# -*- coding: utf-8 -*-
"""Haft Almas - Coil Analytics Platform: entry point.

Python 3.5+, standard library + tkinter only.
"""
from __future__ import print_function, unicode_literals

import os
import sys
import tempfile
import time
import traceback


def _find_root():
    # HaftAlmas.vbs passes the original (possibly UNC) folder in this variable
    env = os.environ.get("HAFT_APP_ROOT")
    if env and os.path.isfile(os.path.join(env, "main.py")):
        return env
    return os.path.dirname(os.path.abspath(__file__))


ROOT = _find_root()
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    os.chdir(ROOT)          # may fail on a UNC path - harmless
except Exception:
    pass


def is_writable(folder):
    try:
        probe = os.path.join(folder, ".write_test_%d" % os.getpid())
        with open(probe, "w") as f:
            f.write("x")
        os.remove(probe)
        return True
    except Exception:
        return False


def get_dirs():
    """Returns (shared_dir, local_dir).

    shared_dir: users.json and config.json (lines, mapping, limits). This is the program
                folder whenever it is writable OR already contains users.json, so normal
                users on a read-only share read the administrator's settings.
    local_dir : %USERPROFILE%\\HaftAlmas_data - per-user, always writable (error log,
                last selected line).
    """
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    local = os.path.join(home, "HaftAlmas_data")
    try:
        os.makedirs(local, exist_ok=True)
    except Exception:
        local = os.path.join(tempfile.gettempdir(), "HaftAlmas_data")
        os.makedirs(local, exist_ok=True)
    if is_writable(ROOT) or os.path.isfile(os.path.join(ROOT, "users.json")):
        return ROOT, local
    return local, local


def log_error(data_dir, text):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    for folder in (data_dir, tempfile.gettempdir()):
        try:
            with open(os.path.join(folder, "error_log.txt"), "a", encoding="utf-8") as f:
                f.write("[%s]\n%s\n\n" % (stamp, text))
            return os.path.join(folder, "error_log.txt")
        except Exception:
            continue
    return None


SAMPLE_LINES = [
    ("Line 1 (sample)", "line1.csv", {
        "coil": "Coil_ID", "date": "Prod_Date", "thickness": "Final_Thickness",
        "hr_thickness": "HR_Thickness", "ys": "Yield_Strength", "uts": "Tensile_Strength",
        "el": "Elongation", "grade": "Product_Grade", "hr_grade": "Hot_Roll_Grade",
        "hr_mark": "Hot_Roll_Mark", "weight": "Weight_kg", "qgrade": "Quality_Grade",
        "cause1": "Main_Cause", "cause2": "Second_Cause"}),
    ("Line 2 (sample)", "line2.csv", {
        "coil": "CoilNo", "date": "ProdDate", "thickness": "Thk", "hr_thickness": "HRThk",
        "ys": "YS_MPa", "uts": "UTS_MPa", "el": "Elong_pct", "grade": "Grade",
        "hr_grade": "HRGrade", "hr_mark": "HRMark", "weight": "Wt_kg", "qgrade": "QGrade",
        "cause1": "Cause1", "cause2": "Cause2"}),
]


COLOR_SAMPLE = ("Color line (sample)", "line3_color.csv", {
    "date": u"\u062a\u0627\u0631\u06cc\u062e", "coil": u"\u0634\u0645\u0627\u0631\u0647 \u06a9\u0648\u06cc\u0644",
    "thickness": u"\u0636\u062e\u0627\u0645\u062a", "ral": u"\u0631\u0627\u0644 \u0631\u0646\u06af",
    "delta_e": u"\u0627\u062e\u062a\u0644\u0627\u0641 \u0641\u0627\u0645", "gloss": u"\u0628\u0631\u0627\u0642\u06cc\u062a",
    "supplier": u"\u062a\u0627\u0645\u06cc\u0646 \u06a9\u0646\u0646\u062f\u0647 \u0631\u0646\u06af \u062a\u0627\u067e \u06a9\u0648\u062a",
    "top_thickness": u"\u0636\u062e\u0627\u0645\u062a \u0644\u0627\u06cc\u0647 \u062a\u0627\u067e",
    "bend": u"\u062a\u0633\u062a \u062e\u0645\u0634", "bend_adhesive": u"\u062a\u0633\u062a \u062e\u0645\u0634 \u0686\u0633\u0628",
    "mek": "MEK", "grade": u"\u062f\u0631\u062c\u0647 \u06a9\u06cc\u0641\u06cc", "weight": u"\u0648\u0632\u0646 \u06a9\u0648\u06cc\u0644",
    "cause1": u"\u0639\u0644\u062a \u0627\u0635\u0644\u06cc \u0627\u0641\u062a \u06af\u0631\u06cc\u062f",
    "cause2": u"\u0639\u0644\u062a \u062f\u0648\u0645 \u0627\u0641\u062a \u06af\u0631\u06cc\u062f"})


def register_samples(dm):
    if not is_writable(dm.data_dir):
        return              # read-only installation: never touch the shared settings
    folder = os.path.join(ROOT, "sample_data")
    if not dm.line_names():
        for name, fname, mapping in SAMPLE_LINES:
            path = os.path.join(folder, fname)
            if os.path.isfile(path):
                try:
                    dm.add_line(name, path, mapping, "steel",
                                {"weight_unit": "kg", "prime_grades": "A", "active": True})
                except Exception:
                    pass
    # the colour-line sample is offered once, also for installations that already have lines
    if not dm.ui_flag("color_sample_added"):
        name, fname, mapping = COLOR_SAMPLE
        path = os.path.join(folder, fname)
        if os.path.isfile(path) and name not in dm.line_names():
            try:
                dm.add_line(name, path, mapping, "color",
                            {"weight_unit": "kg", "prime_grades": "A", "active": True})
            except Exception:
                pass
        dm.set_ui_flag("color_sample_added", True)


def main():
    data_dir, local_dir = get_dirs()
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        print("tkinter is not available in this Python installation.")
        input("Press Enter to exit...")
        return 1

    try:
        root = tk.Tk()
    except Exception:
        log_error(local_dir, traceback.format_exc())
        raise
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root.geometry("1320x800")
    root.minsize(1100, 680)
    try:
        root.state("zoomed")                 # Windows: start maximized
    except Exception:
        try:
            root.attributes("-zoomed", True)  # Linux
        except Exception:
            pass

    def on_callback_error(exc, val, tb):
        text = "".join(traceback.format_exception(exc, val, tb))
        path = log_error(local_dir, text)
        try:
            messagebox.showerror(u"Haft Almas - Error",
                                 u"%s\n\nDetails were written to:\n%s" % (val, path))
        except Exception:
            pass

    root.report_callback_exception = on_callback_error

    try:
        from modules.auth import AuthManager
        from modules.data_manager import DataManager
        from modules.dashboard import HaftAlmasApp
        auth = AuthManager(os.path.join(data_dir, "users.json"))
        dm = DataManager(data_dir, ROOT, local_dir)
        register_samples(dm)
        HaftAlmasApp(root, auth, dm, ROOT)
        root.mainloop()
    except Exception:
        text = traceback.format_exc()
        path = log_error(local_dir, text)
        try:
            messagebox.showerror(u"Haft Almas - Startup error",
                                 u"The program could not start.\n\n%s\n\nLog file:\n%s"
                                 % (text.strip().splitlines()[-1], path))
        except Exception:
            print(text)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
