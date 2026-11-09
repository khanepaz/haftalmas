# -*- coding: utf-8 -*-
"""Chart engine drawn directly on a Tkinter Canvas (no external libraries).

Usage:  chart.show("hist", values=[...], bins=12, title=u"...", xlabel=u"...")
Kinds:  hist, scatter, box, line, bar
The chart redraws itself automatically when the widget is resized.
"""
from __future__ import print_function, unicode_literals

import math
import tkinter as tk

# ---- industrial dark theme
BG = "#12161c"
PANEL = "#1b222b"
PANEL2 = "#252f3b"
ACCENT = "#2bb3c0"
ACCENT2 = "#3b82f6"
TEXT = "#e6edf3"
MUTED = "#8b98a5"
GRID = "#2c3643"
WARN = "#f59e0b"
BAD = "#ef4444"
GOOD = "#22c55e"
SERIES = [ACCENT, ACCENT2, "#a78bfa", "#f472b6", WARN, GOOD, "#fb7185", "#38bdf8"]

FONT_FAMILY = "Segoe UI"
FONT = (FONT_FAMILY, 9)
FONT_SMALL = (FONT_FAMILY, 8)
FONT_BOLD = (FONT_FAMILY, 9, "bold")

# ... (full content truncated for this interaction - the complete file will be uploaded in the next step)
