# -*- coding: utf-8 -*-
"""Jalali (Persian) calendar popup used by the date filters. Pure Tk, no external packages."""
from __future__ import print_function, unicode_literals

import datetime
import tkinter as tk

from .charts import PANEL2, ACCENT, TEXT, MUTED, GRID, BAD, FONT, FONT_SMALL, FONT_BOLD
from .csv_reader import jalali_to_gregorian, gregorian_to_jalali

MONTHS = [u"Farvardin", u"Ordibehesht", u"Khordad", u"Tir", u"Mordad", u"Shahrivar",
          u"Mehr", u"Aban", u"Azar", u"Dey", u"Bahman", u"Esfand"]
WEEKDAYS = [u"Sat", u"Sun", u"Mon", u"Tue", u"Wed", u"Thu", u"Fri"]   # Iranian week starts on Saturday


def month_length(jy, jm):
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    g = jalali_to_gregorian(jy, 12, 30)                  # Esfand has 30 days only in leap years
    return 30 if gregorian_to_jalali(*g) == (jy, 12, 30) else 29


def first_weekday(jy, jm):
    """0 = Saturday ... 6 = Friday for the first day of the month."""
    g = jalali_to_gregorian(jy, jm, 1)
    return (datetime.date(*g).weekday() + 2) % 7


def today_jalali():
    d = datetime.date.today()
    return gregorian_to_jalali(d.year, d.month, d.day)


class JalaliCalendar(tk.Frame):
    """initial: (jy, jm, jd) or None.  on_pick((jy, jm, jd)) / on_clear() are called on selection."""

    def __init__(self, master, initial=None, on_pick=None, on_clear=None):
        tk.Frame.__init__(self, master, bg=PANEL2, highlightbackground=ACCENT, highlightthickness=1,
                          padx=8, pady=8)
        self.on_pick, self.on_clear = on_pick, on_clear
        self.today = today_jalali()
        self.sel = initial
        base = initial or self.today
        self.jy, self.jm = base[0], base[1]
        head = tk.Frame(self, bg=PANEL2)
        head.pack(fill="x", pady=(0, 6))
        for text, step in ((u"\u00ab", -12), (u"\u2039", -1)):
            self._nav_button(head, text, step).pack(side="left")
        for text, step in ((u"\u00bb", 12), (u"\u203a", 1)):
            self._nav_button(head, text, step).pack(side="right")
        self.title = tk.Label(head, text=u"", bg=PANEL2, fg=TEXT, font=FONT_BOLD)
        self.title.pack(side="left", expand=True)
        days = tk.Frame(self, bg=PANEL2)
        days.pack()
        for c, name in enumerate(WEEKDAYS):
            tk.Label(days, text=name, width=4, bg=PANEL2, fg=BAD if c == 6 else MUTED,
                     font=FONT_SMALL).grid(row=0, column=c)
        self.grid_frame = tk.Frame(self, bg=PANEL2)
        self.grid_frame.pack()
        foot = tk.Frame(self, bg=PANEL2)
        foot.pack(fill="x", pady=(6, 0))
        tk.Button(foot, text=u"Today", relief="flat", bd=0, bg=GRID, fg=TEXT, activebackground=ACCENT,
                  highlightthickness=0, font=FONT_SMALL, cursor="hand2", padx=10,
                  command=lambda: self._pick_tuple(self.today)).pack(side="left")
        tk.Button(foot, text=u"Clear", relief="flat", bd=0, bg=GRID, fg=TEXT, activebackground=ACCENT,
                  highlightthickness=0, font=FONT_SMALL, cursor="hand2", padx=10,
                  command=self._clear).pack(side="right")
        self._draw()

    def _nav_button(self, parent, text, step):
        return tk.Button(parent, text=text, width=2, relief="flat", bd=0, bg=PANEL2, fg=TEXT,
                         activebackground=ACCENT, activeforeground="#04222a", highlightthickness=0,
                         font=FONT_BOLD, cursor="hand2", command=lambda: self.shift(step))

    def shift(self, months):
        total = self.jy * 12 + (self.jm - 1) + months
        jy, jm = divmod(total, 12)
        self.jy, self.jm = max(1300, min(1500, jy)), jm + 1
        self._draw()

    def _draw(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.title.configure(text=u"%s %d" % (MONTHS[self.jm - 1], self.jy))
        off = first_weekday(self.jy, self.jm)
        for d in range(1, month_length(self.jy, self.jm) + 1):
            r, c = divmod(off + d - 1, 7)
            cur = (self.jy, self.jm, d)
            is_sel = (self.sel == cur)
            is_today = (self.today == cur)
            bg = ACCENT if is_sel else PANEL2
            fg = "#04222a" if is_sel else (BAD if c == 6 else TEXT)
            lab = tk.Label(self.grid_frame, text=u"%d" % d, width=4, bg=bg, fg=fg, font=FONT,
                           highlightthickness=1 if is_today else 0, highlightbackground=ACCENT,
                           cursor="hand2")
            lab.grid(row=r, column=c, padx=1, pady=1)
            lab.bind("<Button-1>", lambda e, d=d: self._pick_tuple((self.jy, self.jm, d)))
            if not is_sel:
                lab.bind("<Enter>", lambda e, w=lab: w.configure(bg="#2f3b4a"))
                lab.bind("<Leave>", lambda e, w=lab: w.configure(bg=PANEL2))

    def _pick_tuple(self, t):
        if self.on_pick:
            self.on_pick(t)

    def _clear(self):
        if self.on_clear:
            self.on_clear()
