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
    # HaftAlmas.vbs passes the real folder (including UNC) via this env var.
    env = os.environ.get("HAFT_APP_ROOT")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    # Frozen / pyinstaller
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # Script location
    return os.path.dirname(os.path.abspath(__file__))


def main():
    root = _find_root()
    os.chdir(root)
    if root not in sys.path:
        sys.path.insert(0, root)

    # Late imports so the path is correct
    from modules import dashboard

    try:
        app = dashboard.App(root)
        app.run()
        return 0
    except Exception:
        text = traceback.format_exc()
        try:
            path = os.path.join(root, "error_log.txt")
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n" + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
                f.write(text)
                f.write("\n")
            print("Fatal error written to %s" % path)
            print(text)
            # On Windows show a simple message box if possible
            try:
                import tkinter as tk
                from tkinter import messagebox
                root_tk = tk.Tk()
                root_tk.withdraw()
                messagebox.showerror("Haft Almas", "Fatal error.\nSee error_log.txt")
                root_tk.destroy()
            except Exception:
                pass
        except Exception:
            print(text)
        return 1


if __name__ == "__main__":
    sys.exit(main())
