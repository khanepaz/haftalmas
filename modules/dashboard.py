# -*- coding: utf-8 -*-
"""Haft Almas UI: login, sidebar navigation and all pages."""
from __future__ import print_function, unicode_literals

import csv
import datetime
import io
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from . import analytics
from . import color_analytics as ca
from . import profiles
from .auth import ROLE_ADMIN, ROLE_USER, ROLES
from .charts import (ChartCanvas, BG, PANEL, PANEL2, ACCENT, ACCENT2, TEXT, MUTED,
                     GRID, WARN, BAD, GOOD, FONT, FONT_SMALL, FONT_BOLD, FONT_FAMILY, SERIES)
from .csv_reader import normalize_date, format_jalali, parse_date, gregorian_to_jalali
from .data_manager import (STANDARD_FIELDS, REQUIRED_FIELDS, FIELD_LABELS, guess_mapping)

ALL = u"(All)"
NONE_CHOICE = u"(none)"

FIELD_OPTIONS = [(u"YS (MPa)", "ys"), (u"UTS (MPa)", "uts"), (u"EL (%)", "el"),
                 (u"Thickness (mm)", "thickness"), (u"HR Thickness (mm)", "hr_thickness"),
                 (u"Reduction (%)", "reduction")]
GROUP_OPTIONS = [(u"HR Mark", "hr_mark"), (u"HR Grade", "hr_grade"), (u"Product grade", "grade"),
                 (u"Quality grade", "qgrade"), (u"Main cause", "cause1"), (u"Second cause", "cause2")]
COMPARE_METRICS = [(u"Coils", "coils"), (u"Tons", "tons"), (u"Downgrade %", "downgrade"),
                   (u"Defect %", "defect")] + FIELD_OPTIONS + [(u"Quality grade mix", "qg_mix"),
                                                               (u"Quality grade mix %", "qg_pct")]
DECIMALS = {"ys": 1, "uts": 1, "el": 1, "thickness": 3, "hr_thickness": 2, "reduction": 1}


def opt_labels(options):
    return [o[0] for o in options]


def opt_key(options, label):
    for text, key in options:
        if text == label:
            return key
    return options[0][1]


def opt_label(options, key):
    for text, k in options:
        if k == key:
            return text
    return options[0][0]


def fmt(v, d=2):
    if v is None:
        return u"-"
    return u"%.*f" % (d, v)


# ---------------------------------------------------------------- styling

def setup_style(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL2, font=FONT,
                 bordercolor=GRID, lightcolor=PANEL2, darkcolor=PANEL2, troughcolor=PANEL)
    st.configure("TFrame", background=BG)
    st.configure("TLabel", background=BG, foreground=TEXT)
    st.configure("TButton", background=PANEL2, foreground=TEXT, padding=(10, 5), borderwidth=1,
                 focuscolor=PANEL2)
    st.map("TButton", background=[("active", ACCENT2), ("disabled", PANEL)],
           foreground=[("disabled", MUTED)])
    st.configure("Mini.TButton", padding=(5, 4))
    st.configure("Accent.TButton", background=ACCENT, foreground="#04222a", padding=(12, 6))
    st.map("Accent.TButton", background=[("active", "#46c9d6")])
    st.configure("TEntry", fieldbackground=PANEL2, foreground=TEXT, insertcolor=TEXT, padding=3)
    st.map("TEntry", fieldbackground=[("disabled", PANEL)], foreground=[("disabled", MUTED)])
    st.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2, foreground=TEXT,
                 arrowcolor=TEXT, padding=3)
    st.map("TCombobox", fieldbackground=[("readonly", PANEL2), ("disabled", PANEL)],
           foreground=[("readonly", TEXT), ("disabled", MUTED)],
           selectbackground=[("readonly", PANEL2)], selectforeground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", PANEL2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT2)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    st.configure("TRadiobutton", background=BG, foreground=TEXT)
    st.map("TRadiobutton", background=[("active", BG)], foreground=[("active", ACCENT)],
           indicatorcolor=[("selected", ACCENT), ("!selected", PANEL2)])
    st.configure("TCheckbutton", background=BG, foreground=TEXT)
    st.map("TCheckbutton", background=[("active", BG)], foreground=[("active", ACCENT)],
           indicatorcolor=[("selected", ACCENT), ("!selected", PANEL2)])
    st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                 rowheight=24, borderwidth=0)
    st.map("Treeview", background=[("selected", ACCENT2)], foreground=[("selected", TEXT)])
    st.configure("Treeview.Heading", background=PANEL2, foreground=ACCENT, relief="flat",
                 font=FONT_BOLD, padding=4)
    st.map("Treeview.Heading", background=[("active", PANEL2)])
    st.configure("Vertical.TScrollbar", background=PANEL2, arrowcolor=TEXT)


# ---------------------------------------------------------------- widgets

def combo_group(parent, text, values, width=14, default=None):
    f = tk.Frame(parent, bg=BG)
    tk.Label(f, text=text, bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
    cb = ttk.Combobox(f, values=values, width=width, state="readonly")
    cb.pack(side="left")
    if default is not None:
        cb.set(default)
    elif values:
        cb.current(0)
    return f, cb


def _sort_key(v):
    try:
        return (0, float(str(v).replace(u"%", u"")))
    except ValueError:
        return (1, str(v).lower())


def _restripe(tree):
    for i, item in enumerate(tree.get_children()):
        tree.item(item, tags=("odd",) if i % 2 else ("even",))


def sort_tree(tree, col):
    rev = (getattr(tree, "_sort_col", None) == col and not getattr(tree, "_sort_rev", False))
    items = [(_sort_key(tree.set(i, col)), i) for i in tree.get_children()]
    items.sort(reverse=rev)
    for idx, (k, i) in enumerate(items):
        tree.move(i, "", idx)
    tree._sort_col, tree._sort_rev = col, rev
    for c, h in tree._heads.items():
        tree.heading(c, text=h + ((u"  v" if rev else u"  ^") if c == col else u""))
    _restripe(tree)


def make_tree(parent, columns, widths=None, height=8, left_cols=None):
    frame = tk.Frame(parent, bg=BG)
    ids = [c[0] for c in columns]
    tree = ttk.Treeview(frame, columns=ids, show="headings", height=height, selectmode="browse")
    left = set(left_cols or [ids[0]])
    tree._heads = dict(columns)
    tree.tag_configure("even", background=PANEL)
    tree.tag_configure("odd", background="#202a36")
    for cid, head in columns:
        tree.heading(cid, text=head, command=lambda c=cid: sort_tree(tree, c))
        tree.column(cid, width=(widths or {}).get(cid, 80), minwidth=40,
                    anchor="w" if cid in left else "e", stretch=True)
    vs = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    return frame, tree


def fill_tree(tree, rows):
    for item in tree.get_children():
        tree.delete(item)
    for r in rows:
        tree.insert("", "end", values=r)
    tree._sort_col = None
    for c, h in getattr(tree, "_heads", {}).items():
        tree.heading(c, text=h)
    _restripe(tree)


def title_label(parent, text):
    return tk.Label(parent, text=text, bg=BG, fg=ACCENT, font=(FONT_FAMILY, 12, "bold"))


def write_csv(path, header, rows):
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([u"" if c is None else c for c in r])


def scatter_data(recs, fx, fy):
    xs, ys, tips = [], [], []
    for r in recs:
        a, b = r.get(fx), r.get(fy)
        if a is not None and b is not None:
            xs.append(a)
            ys.append(b)
            tips.append(u"Coil %s%s" % (r["coil"], (u"   " + r["date"]) if r.get("date") else u""))
    return xs, ys, tips


def build_insights(recs, dm):
    out = []
    g = [x for x in analytics.mean_by_group(recs, "hr_mark", "ys") if x[1] is not None and x[2] >= 3]
    if len(g) >= 2:
        hi = max(g, key=lambda x: x[1])
        lo = min(g, key=lambda x: x[1])
        out.append(u"Highest YS: mark %s (%.1f MPa), lowest: mark %s (%.1f MPa)" % (hi[0], hi[1], lo[0], lo[1]))
    ys = analytics.values(recs, "ys")
    if len(ys) >= 4:
        n = len(analytics.iqr_outliers(ys)[2])
        if n:
            out.append(u"%d YS outlier(s) by the IQR rule" % n)
    dated = sorted([r for r in recs if r.get("date") and r.get("ys") is not None],
                   key=lambda r: (r["date"], r["_row"]))
    if len(dated) >= 20:
        h = len(dated) // 2
        a = analytics.mean([r["ys"] for r in dated[:h]])
        b = analytics.mean([r["ys"] for r in dated[h:]])
        sd = analytics.std([r["ys"] for r in dated]) or 0
        if sd and abs(b - a) >= 0.2 * sd:
            out.append(u"YS %s by %.1f MPa in the later half of the period" % (
                u"rose" if b > a else u"fell", abs(b - a)))
    lsl, usl = dm.get_spec("ys")
    if (lsl is not None or usl is not None) and len(ys) >= 2:
        try:
            cpk = analytics.process_capability(ys, lsl, usl)["cpk"]
        except ValueError:
            cpk = None
        if cpk is not None:
            out.append(u"YS Cpk = %.2f" % cpk)
    return out


class Page(tk.Frame):
    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent, bg=BG)
        self.app = app

    def refresh(self):
        pass


# ================================================================ Dashboard

class DashboardPage(Page):
    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        self.content = tk.Frame(self, bg=BG)
        self.empty = tk.Frame(self, bg=BG)
        inner = tk.Frame(self.empty, bg=BG)
        inner.place(relx=0.5, rely=0.4, anchor="center")
        tk.Label(inner, text=u"No data yet", bg=BG, fg=ACCENT, font=(FONT_FAMILY, 20, "bold")).pack()
        tk.Label(inner, text=u"Add a production line (CSV file) to see KPIs and charts.", bg=BG,
                 fg=MUTED, font=FONT).pack(pady=(6, 14))
        self.empty_btn = ttk.Button(inner, text=u"Open Line Manager", style="Accent.TButton",
                                    command=lambda: self.app.navigate("lines"))
        self.kpi = tk.Frame(self.content, bg=BG)
        self.kpi.pack(fill="x", pady=(0, 8))
        self.insight = tk.Label(self.content, text=u"", bg=PANEL, fg=TEXT, font=FONT, anchor="w",
                                justify="left", padx=12, pady=6, highlightbackground=GRID,
                                highlightthickness=1)
        self.insight.pack(fill="x", pady=(0, 8))
        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="both", expand=True)
        for i in (0, 1):
            grid.columnconfigure(i, weight=1, uniform="c")
            grid.rowconfigure(i, weight=1, uniform="r")
        self.c1, self.c2, self.c3, self.c4 = [ChartCanvas(grid) for _ in range(4)]
        self.c1.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
        self.c2.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))
        self.c3.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))
        self.c4.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))

    def refresh(self):
        recs = self.app.filtered
        if self.app.dataset is None:
            self.content.pack_forget()
            if self.app.role == ROLE_ADMIN:
                self.empty_btn.pack()
            self.empty.pack(fill="both", expand=True)
            return
        self.empty.pack_forget()
        if not self.content.winfo_ismapped():
            self.content.pack(fill="both", expand=True)
        tips = build_insights(recs, self.app.dm)
        self.insight.configure(text=(u"Insights     " + u"     |     ".join(tips)) if tips
                               else u"Insights     not enough data yet")
        for w in self.kpi.winfo_children():
            w.destroy()
        lab = sum(1 for r in recs if r.get("has_lab"))
        cards = [(u"Coils", u"%d" % len(recs), u"with lab results: %d" % lab)]
        for f, name, unit in (("ys", u"Avg YS", u"MPa"), ("uts", u"Avg UTS", u"MPa"),
                              ("el", u"Avg EL", u"%"), ("thickness", u"Avg Thickness", u"mm"),
                              ("reduction", u"Avg Reduction", u"%")):
            vals = analytics.values(recs, f)
            if not vals and f in ("thickness", "reduction"):
                continue
            st = analytics.descriptive_stats(vals)
            d = DECIMALS[f]
            sub = unit + (u"    s = " + fmt(st["std"], d) if vals else u"")
            cards.append((name, fmt(st["mean"], d), sub))
        for ci, (name, val, sub) in enumerate(cards):
            card = tk.Frame(self.kpi, bg=PANEL, padx=14, pady=8, highlightbackground=GRID,
                            highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Frame(card, bg=SERIES[ci % len(SERIES)], height=3).pack(fill="x", pady=(0, 6))
            tk.Label(card, text=name, bg=PANEL, fg=MUTED, font=FONT_SMALL).pack(anchor="w")
            tk.Label(card, text=val, bg=PANEL, fg=ACCENT, font=(FONT_FAMILY, 18, "bold")).pack(anchor="w")
            tk.Label(card, text=sub or u" ", bg=PANEL, fg=MUTED, font=FONT_SMALL).pack(anchor="w")

        self.c1.show("hist", values=analytics.values(recs, "ys"), bins=15,
                     title=u"YS Distribution", xlabel=u"YS (MPa)", color=ACCENT)
        self.c2.show("hist", values=analytics.values(recs, "uts"), bins=15,
                     title=u"UTS Distribution", xlabel=u"UTS (MPa)", color=ACCENT2)
        g = analytics.mean_by_group(recs, "hr_mark", "ys")
        self.c3.show("bar", labels=[x[0] for x in g], values=[x[1] for x in g],
                     counts=[x[2] for x in g], title=u"Avg YS by HR Mark", ylabel=u"YS (MPa)",
                     zero_base=self.app.zero_base.get())
        xs, ys, tips = scatter_data(recs, "reduction", "ys")
        if len(xs) >= 3:
            self.c4.show("scatter", xs=xs, ys=ys, tips=tips, title=u"Reduction vs YS",
                         xlabel=u"Reduction (%)", ylabel=u"YS (MPa)")
        else:
            xs, ys, tips = scatter_data(recs, "ys", "uts")
            self.c4.show("scatter", xs=xs, ys=ys, tips=tips, title=u"YS vs UTS",
                         xlabel=u"YS (MPa)", ylabel=u"UTS (MPa)")


# ================================================================ Charts

class ChartsPage(Page):
    TYPES = [u"Histogram", u"Scatter", u"Box Plot", u"Trend", u"Bar by group"]

    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        self.g_type, self.cb_type = combo_group(bar, u"Chart", self.TYPES, 14, u"Histogram")
        self.g_field, self.cb_field = combo_group(bar, u"Field", opt_labels(FIELD_OPTIONS), 16)
        self.g_x, self.cb_x = combo_group(bar, u"X axis", opt_labels(FIELD_OPTIONS), 16,
                                          opt_label(FIELD_OPTIONS, "reduction"))
        self.g_group, self.cb_group = combo_group(bar, u"Group By", opt_labels(GROUP_OPTIONS), 12)
        self.g_bins = tk.Frame(bar, bg=BG)
        tk.Label(self.g_bins, text=u"Bins", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
        self.bins = tk.IntVar(value=15)
        self.sp_bins = tk.Spinbox(self.g_bins, from_=3, to=80, width=5, textvariable=self.bins,
                                  command=self.draw, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                                  buttonbackground=PANEL2, relief="flat", highlightthickness=1,
                                  highlightbackground=GRID, font=FONT)
        self.sp_bins.pack(side="left")
        self.sp_bins.bind("<Return>", lambda e: self.draw())
        self.sp_bins.bind("<FocusOut>", lambda e: self.draw())
        self.g_zero = ttk.Checkbutton(bar, text=u"Zero baseline", variable=app.zero_base,
                                      command=self.app.refresh_current)
        for i, g in enumerate([self.g_type, self.g_field, self.g_x, self.g_group, self.g_bins, self.g_zero]):
            g.grid(row=0, column=i, padx=(0, 14), sticky="w")
        for cb in (self.cb_type, self.cb_field, self.cb_x, self.cb_group):
            cb.bind("<<ComboboxSelected>>", self._on_change)
        self.chart = ChartCanvas(self)
        self.chart.pack(fill="both", expand=True)
        self._update_controls()

    def _on_change(self, event=None):
        self._update_controls()
        self.draw()

    def _update_controls(self):
        t = self.cb_type.get()
        show = {
            u"Histogram": (self.g_field, self.g_bins),
            u"Scatter": (self.g_field, self.g_x),
            u"Box Plot": (self.g_field, self.g_group),
            u"Trend": (self.g_field,),
            u"Bar by group": (self.g_field, self.g_group, self.g_zero),
        }[t]
        for g in (self.g_field, self.g_x, self.g_group, self.g_bins, self.g_zero):
            if g in show:
                g.grid()
            else:
                g.grid_remove()
        self.g_field.winfo_children()[0].configure(text=u"Y axis" if t == u"Scatter" else u"Field")

    def refresh(self):
        self.draw()

    def draw(self):
        recs = self.app.filtered
        t = self.cb_type.get()
        fk = opt_key(FIELD_OPTIONS, self.cb_field.get())
        flabel = self.cb_field.get()
        gk = opt_key(GROUP_OPTIONS, self.cb_group.get())
        if t == u"Histogram":
            try:
                bins = max(3, min(80, int(self.bins.get())))
            except (ValueError, tk.TclError):
                bins = 15
            self.chart.show("hist", values=analytics.values(recs, fk), bins=bins,
                            title=flabel + u" - Distribution", xlabel=flabel)
        elif t == u"Scatter":
            xk = opt_key(FIELD_OPTIONS, self.cb_x.get())
            xs, ys, tips = scatter_data(recs, xk, fk)
            self.chart.show("scatter", xs=xs, ys=ys, tips=tips, title=flabel + u" vs " + self.cb_x.get(),
                            xlabel=self.cb_x.get(), ylabel=flabel)
        elif t == u"Box Plot":
            groups = [(lab, analytics.values(r, fk)) for lab, r in analytics.group_by(recs, gk)]
            self.chart.show("box", groups=groups, title=flabel + u" by " + self.cb_group.get(),
                            ylabel=flabel)
        elif t == u"Trend":
            rows = [r for r in recs if r.get(fk) is not None]
            rows.sort(key=lambda r: (r.get("date") or u"9999", r["_row"]))
            self.chart.show("line", values=[r[fk] for r in rows],
                            labels=[r["coil"] for r in rows],
                            title=flabel + u" - Trend (by date, then file order)", ylabel=flabel)
        else:
            g = analytics.mean_by_group(recs, gk, fk)
            self.chart.show("bar", labels=[x[0] for x in g], values=[x[1] for x in g],
                            counts=[x[2] for x in g], decimals=DECIMALS[fk],
                            title=u"Mean " + flabel + u" by " + self.cb_group.get(),
                            ylabel=flabel, zero_base=self.app.zero_base.get())


# ================================================================ Compare

class ComparePage(Page):
    QUICK = [(u"YS by Mark", "hr_mark", "ys"), (u"UTS by Mark", "hr_mark", "uts"),
             (u"Reduction by Mark", "hr_mark", "reduction"), (u"YS by HR Grade", "hr_grade", "ys"),
             (u"YS by Quality", "qgrade", "ys"), (u"UTS by Quality", "qgrade", "uts"),
             (u"Tons by Quality", "qgrade", "tons"), (u"Downgrade by Mark", "hr_mark", "downgrade")]
    COLS = [("grp", u"Group"), ("n", u"Coils"), ("t", u"Tons"), ("sh", u"Share %"), ("dg", u"Downgrade %"),
            ("ys", u"Avg YS"), ("uts", u"Avg UTS"), ("el", u"Avg EL"), ("thk", u"Avg Thick"),
            ("hrt", u"Avg HR Thick"), ("red", u"Avg Reduction"), ("sd", u"Std YS")]
    MET_DEC = {"coils": 0, "tons": 1, "downgrade": 1, "defect": 1}

    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text=u"Mode", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 6))
        self.mode = tk.StringVar(value="group")
        ttk.Radiobutton(top, text=u"Group", variable=self.mode, value="group",
                        command=self.refresh).pack(side="left", padx=4)
        ttk.Radiobutton(top, text=u"Lines", variable=self.mode, value="lines",
                        command=self.refresh).pack(side="left", padx=(4, 16))
        g, self.cb_group = combo_group(top, u"Group By", opt_labels(GROUP_OPTIONS), 13, u"Quality grade")
        g.pack(side="left", padx=(0, 16))
        g, self.cb_left = combo_group(top, u"Left chart", opt_labels(COMPARE_METRICS), 18,
                                      opt_label(COMPARE_METRICS, "ys"))
        g.pack(side="left", padx=(0, 16))
        g, self.cb_right = combo_group(top, u"Right chart", opt_labels(COMPARE_METRICS), 18,
                                       opt_label(COMPARE_METRICS, "uts"))
        g.pack(side="left", padx=(0, 16))
        ttk.Checkbutton(top, text=u"Zero baseline", variable=app.zero_base,
                        command=self.app.refresh_current).pack(side="left")
        for cb in (self.cb_group, self.cb_left, self.cb_right):
            cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        quick = tk.Frame(self, bg=BG)
        quick.pack(fill="x", pady=8)
        tk.Label(quick, text=u"Quick", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 6))
        for text, grp, fld in self.QUICK:
            ttk.Button(quick, text=text,
                       command=lambda g=grp, f=fld: self.quick(g, f)).pack(side="left", padx=3)

        frame, self.tree = make_tree(self, self.COLS, {"grp": 140, "n": 55, "t": 70, "sh": 65, "dg": 90,
                                                       "ys": 65, "uts": 65, "el": 60, "thk": 75,
                                                       "hrt": 90, "red": 100, "sd": 65}, height=7)
        frame.pack(fill="x")
        charts = tk.Frame(self, bg=BG)
        charts.pack(fill="both", expand=True, pady=(8, 0))
        charts.columnconfigure(0, weight=1, uniform="c")
        charts.columnconfigure(1, weight=1, uniform="c")
        charts.rowconfigure(0, weight=1)
        self.c1, self.c2 = ChartCanvas(charts), ChartCanvas(charts)
        self.c1.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.c2.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

    def quick(self, grp, fld):
        self.mode.set("group")
        self.cb_group.set(opt_label(GROUP_OPTIONS, grp))
        self.cb_left.set(opt_label(COMPARE_METRICS, fld))
        self.refresh()

    def groups(self):
        if self.mode.get() == "lines":
            out = []
            for name in self.app.visible_names("steel"):
                try:
                    ds = self.app.dm.load_dataset(name)
                except Exception:
                    continue
                out.append((name, analytics.filter_records(ds.records, **self.app.applied)))
            return out, None
        key = opt_key(GROUP_OPTIONS, self.cb_group.get())
        return analytics.group_by(self.app.filtered, key), key

    def _metric(self, recs, key, m):
        """(value, n) for one group and one chart metric."""
        if key in self.MET_DEC:
            v = ca.metric_value(recs, key, m)
            if key == "tons" and not v:
                v = None
            if key in ("downgrade", "defect") and not any(r.get("qgrade") or r.get("cause1") for r in recs):
                v = None
            return v, len(recs)
        vals = analytics.values(recs, key)
        return analytics.mean(vals), len(vals)

    def refresh(self):
        groups, key = self.groups()
        tons_selected = self.app.measure.get().lower().startswith("t")
        all_t = sum(ca.total(r, "tons") for _, r in groups)
        rows = []
        for label, recs in groups:
            mean = lambda f: analytics.mean(analytics.values(recs, f))
            t = ca.total(recs, "tons")
            m = "tons" if (t > 0 and tons_selected) else "coils"
            has_q = any(r.get("qgrade") or r.get("cause1") for r in recs)
            rows.append((label, len(recs), fmt(t, 1) if t > 0 else u"-",
                         fmt(t * 100.0 / all_t, 1) if (t > 0 and all_t) else u"-",
                         fmt(ca.downgrade_pct(recs, m), 1) if has_q else u"-",
                         fmt(mean("ys"), 1), fmt(mean("uts"), 1), fmt(mean("el"), 1),
                         fmt(mean("thickness"), 3), fmt(mean("hr_thickness"), 2), fmt(mean("reduction"), 1),
                         fmt(analytics.std(analytics.values(recs, "ys")), 1)))
        fill_tree(self.tree, rows)
        zero = self.app.zero_base.get()
        by = u"Line" if key is None else self.cb_group.get()
        labels = [g[0] for g in groups]
        colors = None
        if key is not None:
            from .color_pages import colors_for          # same colours as the other pages
            colors = colors_for(self.app, key, labels)
        for chart, cb in ((self.c1, self.cb_left), (self.c2, self.cb_right)):
            fk = opt_key(COMPARE_METRICS, cb.get())
            if fk in ("qg_mix", "qg_pct"):
                from .color_pages import quality_mix
                quality_mix(self.app, chart, groups, "qgrade", fk == "qg_pct", tons_selected,
                            u"%s by %s" % (cb.get(), by))
                continue
            data = []
            for _, r in groups:
                t = ca.total(r, "tons")
                m = "tons" if (t > 0 and tons_selected) else "coils"
                data.append(self._metric(r, fk, m))
            lab_field = fk in DECIMALS
            chart.show("bar", labels=labels, values=[d[0] for d in data], counts=[d[1] for d in data],
                       colors=colors, decimals=DECIMALS[fk] if lab_field else self.MET_DEC[fk],
                       title=((u"Avg " if lab_field else u"") + cb.get() + u" by " + by),
                       ylabel=cb.get(), zero_base=zero)


# ================================================================ Statistics

class StatisticsPage(Page):
    FIELDS, GROUPS, DEC, DEFAULT_GROUP = FIELD_OPTIONS, GROUP_OPTIONS, DECIMALS, u"HR Mark"
    COLS = [("f", u"Field"), ("n", u"Count"), ("mean", u"Mean"), ("std", u"Std"),
            ("min", u"Min"), ("q1", u"Q1"), ("med", u"Median"), ("q3", u"Q3"),
            ("max", u"Max"), ("cv", u"CV %"), ("out", u"Outliers")]

    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        frame, self.tree = make_tree(self, self.COLS, {"f": 140, "n": 60, "out": 70}, height=7)
        frame.pack(fill="x")
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", pady=8)
        g, self.cb_field = combo_group(bar, u"Box plot of", opt_labels(self.FIELDS), 16)
        g.pack(side="left", padx=(0, 16))
        g, self.cb_group = combo_group(bar, u"by", [NONE_CHOICE] + opt_labels(self.GROUPS), 12,
                                       self.DEFAULT_GROUP)
        g.pack(side="left")
        for cb in (self.cb_field, self.cb_group):
            cb.bind("<<ComboboxSelected>>", lambda e: self.draw())
        self.chart = ChartCanvas(self)
        self.chart.pack(fill="both", expand=True)

    def refresh(self):
        recs = self.app.filtered
        rows = []
        for label, key in self.FIELDS:
            vals = analytics.values(recs, key)
            st = analytics.descriptive_stats(vals)
            d = self.DEC[key]
            out = len(analytics.iqr_outliers(vals)[2])
            rows.append((label, st["count"], fmt(st["mean"], d), fmt(st["std"], d + 1),
                         fmt(st["min"], d), fmt(st["q1"], d), fmt(st["median"], d),
                         fmt(st["q3"], d), fmt(st["max"], d), fmt(st["cv"], 1), out))
        fill_tree(self.tree, rows)
        self.draw()

    def draw(self):
        recs = self.app.filtered
        fk = opt_key(self.FIELDS, self.cb_field.get())
        g = self.cb_group.get()
        if g == NONE_CHOICE:
            groups = [(u"All coils", analytics.values(recs, fk))]
            title = self.cb_field.get() + u" - Box Plot"
        else:
            groups = [(lab, analytics.values(r, fk))
                      for lab, r in analytics.group_by(recs, opt_key(self.GROUPS, g))]
            title = self.cb_field.get() + u" by " + g
        self.chart.show("box", groups=groups, title=title, ylabel=self.cb_field.get())


# ================================================================ Data quality

class QualityPage(Page):
    FIELD_LIST = ("coil", "date", "thickness", "hr_thickness", "ys", "uts", "el",
                  "grade", "hr_grade", "hr_mark", "reduction", "weight_t", "qgrade", "cause1", "cause2")
    LABELS = FIELD_LABELS
    NUMERIC = analytics.NUMERIC_FIELDS

    def extra_summary(self, ds):
        recs = ds.records
        if ds.profile != "steel" or not recs:
            return u""
        lab = sum(1 for r in recs if r.get("has_lab"))
        text = u"Lab results present for %d of %d coils (%.1f%%)" % (lab, len(recs), lab * 100.0 / len(recs))
        if getattr(ds, "has_weight", False):
            tons = sum(r["weight_t"] or 0 for r in recs)
            dg = sum(r["weight_t"] or 0 for r in recs if r["downgraded"])
            text += u"     Total weight: %.1f t     Downgraded: %.1f t (%.1f%%)" % (
                tons, dg, dg * 100.0 / tons if tons else 0.0)
        nd = sum(1 for r in recs if r.get("defect"))
        text += u"     Coils with a defect: %d     Prime grades: %s" % (
            nd, u", ".join(sorted(getattr(ds, "prime", []))) or u"not set (defect = downgrade)")
        return text

    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        self.summary = tk.Label(self, text=u"", bg=PANEL, fg=TEXT, font=FONT, justify="left",
                                anchor="w", padx=12, pady=10, highlightbackground=GRID,
                                highlightthickness=1)
        self.summary.pack(fill="x")
        cols = tk.Frame(self, bg=BG)
        cols.pack(fill="both", expand=True, pady=(8, 0))
        cols.columnconfigure(0, weight=2, uniform="q")
        cols.columnconfigure(1, weight=3, uniform="q")
        cols.rowconfigure(1, weight=1)
        tk.Label(cols, text=u"Field completeness", bg=BG, fg=ACCENT,
                 font=FONT_BOLD).grid(row=0, column=0, sticky="w")
        tk.Label(cols, text=u"Row issues (first 1000)", bg=BG, fg=ACCENT,
                 font=FONT_BOLD).grid(row=0, column=1, sticky="w", padx=(8, 0))
        f1, self.t_fields = make_tree(cols, [("f", u"Field"), ("ok", u"Valid"), ("miss", u"Missing"),
                                             ("pct", u"Missing %"), ("out", u"Outliers")],
                                      {"f": 130, "ok": 60, "miss": 65, "pct": 75, "out": 70})
        f1.grid(row=1, column=0, sticky="nsew")
        f2, self.t_issues = make_tree(cols, [("row", u"Row"), ("sev", u"Type"), ("msg", u"Message")],
                                      {"row": 55, "sev": 70, "msg": 380}, left_cols=["row", "sev", "msg"])
        f2.grid(row=1, column=1, sticky="nsew", padx=(8, 0))

    def refresh(self):
        ds = self.app.dataset
        if ds is None:
            self.summary.configure(text=u"No data loaded.")
            fill_tree(self.t_fields, [])
            fill_tree(self.t_issues, [])
            return
        recs = ds.records
        n = len(recs)
        seen, dup = set(), set()
        for r in recs:
            if r["coil"] in seen:
                dup.add(r["coil"])
            seen.add(r["coil"])
        dates = sorted(r["date"] for r in recs if r.get("date"))
        if dates:
            rng = u"%s  to  %s   (Jalali %s  to  %s)" % (dates[0], dates[-1],
                                                         format_jalali(dates[0]), format_jalali(dates[-1]))
        else:
            rng = u"-"
        self.summary.configure(text=(
            u"Whole file (filters not applied)\n"
            u"Rows in file: %d     Accepted: %d     Rejected: %d     Duplicate coil IDs: %d\n"
            u"Encoding: %s     Delimiter: %s\n"
            u"Date range: %s") % (ds.total_rows, n, ds.rejected, len(dup), ds.encoding,
                                  u"TAB" if ds.delimiter == u"\t" else ds.delimiter, rng))
        extra = self.extra_summary(ds)
        if extra:
            self.summary.configure(text=self.summary.cget("text") + u"\n" + extra)
        rows = []
        for f in [x for x in self.FIELD_LIST if x in getattr(ds, "mapped", self.FIELD_LIST)]:
            ok = sum(1 for r in recs if r.get(f) not in (None, u""))
            miss = n - ok
            out = len(analytics.iqr_outliers(analytics.values(recs, f))[2]) \
                if f in self.NUMERIC else u""
            rows.append((self.LABELS[f], ok, miss, fmt(miss * 100.0 / n if n else 0, 1), out))
        fill_tree(self.t_fields, rows)
        fill_tree(self.t_issues, ds.issues)


# ================================================================ Specs / Cp-Cpk

class SpecsPage(Page):
    FIELDS, DEC, SPEC_PREFIX = FIELD_OPTIONS, DECIMALS, u""
    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        self.is_admin = app.role == ROLE_ADMIN
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        g, self.cb_field = combo_group(bar, u"Field", opt_labels(self.FIELDS), 16)
        g.pack(side="left", padx=(0, 16))
        self.v_lsl, self.v_usl = tk.StringVar(), tk.StringVar()
        state = "normal" if self.is_admin else "disabled"
        tk.Label(bar, text=u"LSL", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.v_lsl, width=10, state=state).pack(side="left", padx=(0, 12))
        tk.Label(bar, text=u"USL", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.v_usl, width=10, state=state).pack(side="left", padx=(0, 12))
        ttk.Button(bar, text=u"Calculate" if self.is_admin else u"Recalculate",
                   command=self.calculate).pack(side="left", padx=4)
        if self.is_admin:
            ttk.Button(bar, text=u"Save limits", style="Accent.TButton",
                       command=self.save).pack(side="left", padx=4)
        else:
            tk.Label(bar, text=u"Limits are set by an administrator (read only).", bg=BG,
                     fg=MUTED, font=FONT_SMALL).pack(side="left", padx=10)
        self.cb_field.bind("<<ComboboxSelected>>", lambda e: self.load_limits())
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2, uniform="s")
        body.columnconfigure(1, weight=3, uniform="s")
        body.rowconfigure(0, weight=1)
        frame, self.tree = make_tree(body, [("m", u"Metric"), ("v", u"Value")],
                                     {"m": 160, "v": 120}, height=14)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.chart = ChartCanvas(body)
        self.chart.grid(row=0, column=1, sticky="nsew")
        self.verdict = tk.Label(self, text=u"", bg=BG, fg=TEXT, font=FONT_BOLD, anchor="w")
        self.verdict.pack(fill="x", pady=(6, 0))
        self._loaded_field = None

    def field_key(self):
        return opt_key(self.FIELDS, self.cb_field.get())

    def load_limits(self):
        lsl, usl = self.app.dm.get_spec(self.SPEC_PREFIX + self.field_key())
        self.v_lsl.set(u"" if lsl is None else u"%g" % lsl)
        self.v_usl.set(u"" if usl is None else u"%g" % usl)
        self.calculate()

    def _read_limits(self):
        from .csv_reader import parse_numeric
        out = []
        for var, name in ((self.v_lsl, u"LSL"), (self.v_usl, u"USL")):
            t = var.get().strip()
            if not t:
                out.append(None)
                continue
            v = parse_numeric(t)
            if v is None:
                raise ValueError(u"%s is not a valid number." % name)
            out.append(v)
        return out[0], out[1]

    def save(self):
        try:
            lsl, usl = self._read_limits()
            self.app.dm.set_spec(self.SPEC_PREFIX + self.field_key(), lsl, usl)
        except ValueError as e:
            messagebox.showerror(u"Specification limits", str(e), parent=self.app.root)
            return
        self.app.toast(u"Limits saved for %s" % self.cb_field.get())
        self.calculate()

    def refresh(self):
        self.load_limits()

    def calculate(self):
        fk = self.field_key()
        d = self.DEC[fk]
        try:
            lsl, usl = self._read_limits()
            vals = analytics.values(self.app.filtered, fk)
            res = analytics.process_capability(vals, lsl, usl)
        except ValueError as e:
            messagebox.showerror(u"Cp / Cpk", str(e), parent=self.app.root)
            return
        st = analytics.descriptive_stats(vals)
        rows = [(u"Count", res["n"]), (u"Mean", fmt(res["mean"], d + 1)),
                (u"Std dev", fmt(res["std"], d + 2)), (u"Min", fmt(st["min"], d)),
                (u"Max", fmt(st["max"], d)), (u"LSL", fmt(lsl, d)), (u"USL", fmt(usl, d)),
                (u"Cp", fmt(res["cp"], 2)), (u"Cpu", fmt(res["cpu"], 2)),
                (u"Cpl", fmt(res["cpl"], 2)), (u"Cpk", fmt(res["cpk"], 2)),
                (u"Out of spec %", fmt(res["pct_out"], 2))]
        fill_tree(self.tree, rows)
        cpk = res["cpk"]
        if lsl is None and usl is None:
            msg, col = u"No limits defined for this field. Ask an administrator to set LSL / USL.", MUTED
        elif cpk is None:
            msg, col = u"Not enough data (or zero variation) to compute capability.", MUTED
        elif cpk >= 1.33:
            msg, col = u"Cpk %.2f - process is capable (>= 1.33)" % cpk, GOOD
        elif cpk >= 1.0:
            msg, col = u"Cpk %.2f - marginal (1.00 to 1.33)" % cpk, WARN
        else:
            msg, col = u"Cpk %.2f - not capable (< 1.00)" % cpk, BAD
        self.verdict.configure(text=msg, fg=col)
        vl = []
        if lsl is not None:
            vl.append((lsl, BAD, u"LSL"))
        if usl is not None:
            vl.append((usl, BAD, u"USL"))
        if res["mean"] is not None:
            vl.append((res["mean"], WARN, u"Mean"))
        self.chart.show("hist", values=vals, bins=15, vlines=vl,
                        title=self.cb_field.get() + u" vs limits", xlabel=self.cb_field.get())


# ================================================================ Export

class ExportPage(Page):
    FIELDS, GROUPS = FIELD_OPTIONS, GROUP_OPTIONS
    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        title_label(self, u"Export (current line and filters)").pack(anchor="w", pady=(0, 10))
        self.info = tk.Label(self, text=u"", bg=BG, fg=MUTED, font=FONT, anchor="w")
        self.info.pack(fill="x", pady=(0, 14))
        row = tk.Frame(self, bg=BG)
        row.pack(anchor="w", pady=4)
        ttk.Button(row, text=u"Export filtered data (CSV)", style="Accent.TButton",
                   command=self.export_data).pack(side="left")
        tk.Label(row, text=u"  All standard fields, reduction, Gregorian and Jalali dates.",
                 bg=BG, fg=MUTED, font=FONT_SMALL).pack(side="left")
        row = tk.Frame(self, bg=BG)
        row.pack(anchor="w", pady=4)
        ttk.Button(row, text=u"Export statistics (CSV)", command=self.export_stats).pack(side="left")
        tk.Label(row, text=u"  Descriptive statistics for every numeric field.",
                 bg=BG, fg=MUTED, font=FONT_SMALL).pack(side="left")
        row = tk.Frame(self, bg=BG)
        row.pack(anchor="w", pady=4)
        ttk.Button(row, text=u"Export group summary (CSV)", command=self.export_groups).pack(side="left", padx=(0, 10))
        g, self.cb_group = combo_group(row, u"Group By", opt_labels(self.GROUPS), 12)
        g.pack(side="left")
        self.status = tk.Label(self, text=u"", bg=BG, fg=GOOD, font=FONT, anchor="w", justify="left")
        self.status.pack(fill="x", pady=(16, 0))

    def refresh(self):
        self.info.configure(text=u"Line: %s     Records to export: %d" % (
            self.app.line_name or u"-", len(self.app.filtered)))

    def _ask(self, default):
        return filedialog.asksaveasfilename(parent=self.app.root, defaultextension=".csv",
                                            initialfile=default, filetypes=[(u"CSV files", "*.csv")])

    def _save(self, default, header, rows):
        path = self._ask(default)
        if not path:
            return
        try:
            write_csv(path, header, rows)
        except (IOError, OSError) as e:
            messagebox.showerror(u"Export", u"Could not write the file:\n%s" % e, parent=self.app.root)
            return
        self.status.configure(text=u"Saved: %s  (%d rows)" % (path, len(rows)))
        self.app.toast(u"Exported %d rows" % len(rows))

    def export_data(self):
        header = [u"coil", u"date", u"date_jalali", u"thickness", u"hr_thickness", u"ys", u"uts",
                  u"el", u"grade", u"hr_grade", u"hr_mark", u"reduction_pct", u"weight_t",
                  u"quality_grade", u"cause1", u"cause2", u"defect", u"downgraded"]
        rows = []
        for r in self.app.filtered:
            rows.append([r["coil"], r.get("date"), format_jalali(r.get("date")) if r.get("date") else u"",
                         r.get("thickness"), r.get("hr_thickness"), r["ys"], r["uts"], r["el"],
                         r.get("grade"), r.get("hr_grade"), r.get("hr_mark"),
                         None if r.get("reduction") is None else round(r["reduction"], 3),
                         None if r.get("weight_t") is None else round(r["weight_t"], 4), r.get("qgrade"),
                         r.get("cause1"), r.get("cause2"), u"yes" if r.get("defect") else u"no",
                         u"yes" if r.get("downgraded") else u"no"])
        self._save(u"coil_data.csv", header, rows)

    def export_stats(self):
        header = [u"field", u"count", u"mean", u"std", u"min", u"q1", u"median", u"q3", u"max", u"cv_pct"]
        rows = []
        for label, key in self.FIELDS:
            st = analytics.descriptive_stats(analytics.values(self.app.filtered, key))
            rows.append([label] + [st[k] for k in ("count", "mean", "std", "min", "q1", "median",
                                                   "q3", "max", "cv")])
        self._save(u"statistics.csv", header, rows)

    def export_groups(self):
        gk = opt_key(self.GROUPS, self.cb_group.get())
        header = [self.cb_group.get(), u"coils", u"avg_ys", u"avg_uts", u"avg_el", u"avg_thickness",
                  u"avg_reduction", u"std_ys"]
        rows = []
        for label, recs in analytics.group_by(self.app.filtered, gk):
            m = lambda f: analytics.mean(analytics.values(recs, f))
            rows.append([label, len(recs), m("ys"), m("uts"), m("el"), m("thickness"),
                         m("reduction"), analytics.std(analytics.values(recs, "ys"))])
        self._save(u"group_summary.csv", header, rows)


# ================================================================ Line Manager (admin)

class LineManagerPage(Page):
    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        self.editing = None
        self.profile = "steel"
        self.headers = []
        self.map_boxes = {}
        self.columnconfigure(0, weight=2, uniform="l")
        self.columnconfigure(1, weight=4, uniform="l")
        self.rowconfigure(1, weight=1)
        title_label(self, u"Lines").grid(row=0, column=0, sticky="w")
        title_label(self, u"Line details and column mapping (set once by the administrator)").grid(
            row=0, column=1, sticky="w", padx=(12, 0))
        left = tk.Frame(self, bg=BG)
        left.grid(row=1, column=0, sticky="nsew")
        frame, self.tree = make_tree(left, [("name", u"Name"), ("type", u"Type"), ("vis", u"Users"),
                                            ("path", u"CSV file")],
                                     {"name": 110, "type": 80, "vis": 60, "path": 220},
                                     left_cols=["name", "type", "vis", "path"])
        frame.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        btns = tk.Frame(left, bg=BG)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text=u"New line", command=self.new_line).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text=u"Delete line", command=self.delete_line).pack(side="left")

        right = tk.Frame(self, bg=PANEL, padx=14, pady=12, highlightbackground=GRID, highlightthickness=1)
        right.grid(row=1, column=1, sticky="nsew", padx=(12, 0))
        right.columnconfigure(1, weight=1)
        self.v_name, self.v_path = tk.StringVar(), tk.StringVar()
        tk.Label(right, text=u"Line name", bg=PANEL, fg=MUTED, font=FONT).grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(right, textvariable=self.v_name).grid(row=0, column=1, columnspan=2, sticky="ew", pady=3)
        tk.Label(right, text=u"Line type", bg=PANEL, fg=MUTED, font=FONT).grid(row=1, column=0, sticky="w", pady=3)
        self.cb_type = ttk.Combobox(right, values=[profiles.PROFILE_TITLES[p] for p in profiles.PROFILE_ORDER],
                                    state="readonly", width=24)
        self.cb_type.set(profiles.PROFILE_TITLES["steel"])
        self.cb_type.grid(row=1, column=1, sticky="w", pady=3)
        self.cb_type.bind("<<ComboboxSelected>>", self.on_type)
        tk.Label(right, text=u"CSV file", bg=PANEL, fg=MUTED, font=FONT).grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(right, textvariable=self.v_path).grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Button(right, text=u"Browse...", command=self.browse).grid(row=2, column=2, padx=(6, 0))
        ttk.Button(right, text=u"Read columns + auto-map", command=self.read_columns).grid(
            row=3, column=1, sticky="w", pady=(4, 8))
        self.map_frame = tk.Frame(right, bg=PANEL)
        self.map_frame.grid(row=4, column=0, columnspan=3, sticky="ew")
        self.opt_frame = tk.Frame(right, bg=PANEL)
        self.opt_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.v_unit, self.v_prime = tk.StringVar(value="kg"), tk.StringVar()
        self.v_active = tk.BooleanVar(value=True)
        self.color_opts = tk.Frame(self.opt_frame, bg=PANEL)
        tk.Label(self.color_opts, text=u"Weight unit in CSV", bg=PANEL, fg=MUTED, font=FONT).pack(side="left")
        ttk.Combobox(self.color_opts, values=["kg", "ton"], textvariable=self.v_unit, state="readonly",
                     width=6).pack(side="left", padx=(6, 18))
        tk.Label(self.color_opts, text=u"Prime quality grade(s), comma separated", bg=PANEL, fg=MUTED,
                 font=FONT).pack(side="left")
        ttk.Entry(self.color_opts, textvariable=self.v_prime, width=12).pack(side="left", padx=(6, 0))
        tk.Checkbutton(self.opt_frame, text=u"Visible to normal users", variable=self.v_active, bg=PANEL,
                       fg=TEXT, selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT,
                       highlightthickness=0, font=FONT).pack(anchor="w", pady=(6, 0))
        self.note = tk.Label(right, text=u"", bg=PANEL, fg=MUTED, font=FONT_SMALL, justify="left", anchor="w")
        self.note.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 4))
        ttk.Button(right, text=u"Save line", style="Accent.TButton", command=self.save).grid(
            row=7, column=1, sticky="w", pady=6)
        self._build_mapping()

    # -- helpers
    def _profile_from_title(self, title):
        for p, t in profiles.PROFILE_TITLES.items():
            if t == title:
                return p
        return "steel"

    def _build_mapping(self, current=None):
        for w in self.map_frame.winfo_children():
            w.destroy()
        self.map_boxes = {}
        fields = profiles.FIELDS[self.profile]
        labels = profiles.LABELS[self.profile]
        per_col = (len(fields) + 1) // 2
        for i, f in enumerate(fields):
            req = f in profiles.REQUIRED[self.profile]
            r, c = i % per_col, (i // per_col) * 2
            tk.Label(self.map_frame, text=labels[f] + (u"  *" if req else u""), bg=PANEL,
                     fg=ACCENT if req else MUTED, font=FONT).grid(row=r, column=c, sticky="w", pady=2, padx=(0, 8))
            cb = ttk.Combobox(self.map_frame, values=[NONE_CHOICE] + self.headers, state="readonly", width=22)
            cb.set((current or {}).get(f, NONE_CHOICE))
            cb.grid(row=r, column=c + 1, sticky="w", pady=2, padx=(0, 16))
            self.map_boxes[f] = cb
        self.color_opts.pack(anchor="w")
        if self.profile == "color":
            self.note.configure(text=u"* required. Weight turns coil counts into tonnage. Enter the PRIME grades "
                                     u"(e.g. Aaa, AA, a): a coil is downgraded only when its grade is not one of "
                                     u"them. A defect on a prime-grade coil is counted as a defect, not a downgrade.")
        else:
            self.note.configure(text=u"* required. Lab results (YS, UTS, EL) are optional - coils without them are kept. "
                                     u"Weight, quality grade and causes add tonnage and downgrade analysis. "
                                     u"Enter the PRIME grades (e.g. Aaa, AA, a): only other grades count as downgrade.")

    def _current_mapping(self):
        m = {}
        for f, cb in self.map_boxes.items():
            v = cb.get()
            if v and v != NONE_CHOICE:
                m[f] = v
        return m

    def _set_headers(self, headers):
        self.headers = headers
        for cb in self.map_boxes.values():
            cb.configure(values=[NONE_CHOICE] + headers)

    def on_type(self, event=None):
        self.profile = self._profile_from_title(self.cb_type.get())
        if self.headers:
            self._build_mapping(profiles.guess_mapping(self.headers, self.profile))
        else:
            self._build_mapping()

    # -- list
    def refresh(self):
        rows = []
        for l in self.app.dm.config["lines"]:
            rows.append((l["name"], profiles.PROFILE_TITLES.get(l.get("profile", "steel"), u""),
                         u"visible" if l.get("active", True) else u"hidden", l["csv_path"]))
        fill_tree(self.tree, rows)

    def new_line(self):
        self.editing = None
        self.v_name.set(u"")
        self.v_path.set(u"")
        self.v_unit.set("kg")
        self.v_prime.set(u"")
        self.v_active.set(True)
        self.headers = []
        self.profile = "steel"
        self.cb_type.set(profiles.PROFILE_TITLES["steel"])
        self._build_mapping()
        for item in self.tree.selection():
            self.tree.selection_remove(item)

    def on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "values")[0]
        line = self.app.dm.get_line(name)
        if line is None:
            return
        self.editing = name
        self.v_name.set(line["name"])
        self.v_path.set(line["csv_path"])
        self.profile = line.get("profile", "steel")
        self.cb_type.set(profiles.PROFILE_TITLES[self.profile])
        self.v_unit.set(line.get("weight_unit", "kg"))
        self.v_prime.set(line.get("prime_grades", u""))
        self.v_active.set(line.get("active", True))
        path = self.app.dm.resolve_path(line["csv_path"])
        try:
            self.headers = self.app.dm.read_headers(path)
        except Exception:
            self.headers = sorted(set(line["mapping"].values()))
        self._build_mapping(line["mapping"])

    def browse(self):
        path = filedialog.askopenfilename(parent=self.app.root, title=u"Select CSV file",
                                          filetypes=[(u"CSV files", "*.csv *.txt"), (u"All files", "*.*")])
        if path:
            self.v_path.set(os.path.abspath(path))
            if not self.v_name.get().strip():
                self.v_name.set(os.path.splitext(os.path.basename(path))[0])
            self.read_columns()

    def read_columns(self):
        path = self.v_path.get().strip()
        try:
            headers = self.app.dm.read_headers(path)
        except Exception as e:
            messagebox.showerror(u"CSV", u"Could not read the CSV file:\n%s" % e, parent=self.app.root)
            return
        self.headers = headers
        guessed = profiles.guess_profile(headers)
        if (guessed != self.profile and profiles.match_score(headers, guessed)
                > profiles.match_score(headers, self.profile)):
            if messagebox.askyesno(u"Line type", u"The columns look like a '%s'.\nSwitch the line type?"
                                   % profiles.PROFILE_TITLES[guessed], parent=self.app.root):
                self.profile = guessed
                self.cb_type.set(profiles.PROFILE_TITLES[guessed])
        self._build_mapping(profiles.guess_mapping(headers, self.profile))

    def save(self):
        mapping = self._current_mapping()
        options = {"weight_unit": self.v_unit.get(), "prime_grades": self.v_prime.get(),
                   "active": self.v_active.get()}
        try:
            if self.editing:
                name = self.app.dm.update_line(self.editing, self.v_name.get(), self.v_path.get().strip(),
                                               mapping, self.profile, options)
            else:
                name = self.app.dm.add_line(self.v_name.get(), self.v_path.get().strip(), mapping,
                                            self.profile, options)
            self.app.dm.load_dataset(name)      # validate the mapping now
        except ValueError as e:
            messagebox.showerror(u"Line Manager", str(e), parent=self.app.root)
            self.app.on_lines_changed(select=self.v_name.get().strip() or None)
            self.refresh()
            return
        self.editing = name
        self.app.on_lines_changed(select=name)
        self.refresh()
        self.app.toast(u"Line '%s' saved" % name)

    def delete_line(self):
        if not self.editing:
            messagebox.showinfo(u"Line Manager", u"Select a line first.", parent=self.app.root)
            return
        if not messagebox.askyesno(u"Delete line", u"Delete line '%s'?\nThe CSV file itself is not deleted."
                                   % self.editing, parent=self.app.root):
            return
        try:
            self.app.dm.remove_line(self.editing)
        except ValueError as e:
            messagebox.showerror(u"Line Manager", str(e), parent=self.app.root)
            return
        self.new_line()
        self.app.on_lines_changed()
        self.refresh()


# ================================================================ User Manager (admin)

class UserManagerPage(Page):
    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        title_label(self, u"Users").grid(row=0, column=0, sticky="w")
        title_label(self, u"Add / modify user").grid(row=0, column=1, sticky="w", padx=(12, 0))
        frame, self.tree = make_tree(self, [("u", u"Username"), ("r", u"Role")], {"u": 180, "r": 120},
                                     left_cols=["u", "r"])
        frame.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        box = tk.Frame(self, bg=PANEL, padx=14, pady=12, highlightbackground=GRID, highlightthickness=1)
        box.grid(row=1, column=1, sticky="nsew", padx=(12, 0))
        self.v_user, self.v_pass = tk.StringVar(), tk.StringVar()
        tk.Label(box, text=u"Username", bg=PANEL, fg=MUTED, font=FONT).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(box, textvariable=self.v_user, width=26).grid(row=0, column=1, sticky="w", pady=4)
        tk.Label(box, text=u"Password", bg=PANEL, fg=MUTED, font=FONT).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(box, textvariable=self.v_pass, width=26, show="*").grid(row=1, column=1, sticky="w", pady=4)
        tk.Label(box, text=u"Role", bg=PANEL, fg=MUTED, font=FONT).grid(row=2, column=0, sticky="w", pady=4)
        self.cb_role = ttk.Combobox(box, values=ROLES, state="readonly", width=23)
        self.cb_role.set(ROLE_USER)
        self.cb_role.grid(row=2, column=1, sticky="w", pady=4)
        btns = tk.Frame(box, bg=PANEL)
        btns.grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Button(btns, text=u"Add user", style="Accent.TButton", command=self.add).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text=u"Set role", command=self.set_role).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text=u"Reset password", command=self.reset).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text=u"Delete", command=self.delete).pack(side="left")
        tk.Label(box, text=u"Password: at least 4 characters. Select a user in the list to modify it.",
                 bg=PANEL, fg=MUTED, font=FONT_SMALL).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def refresh(self):
        fill_tree(self.tree, self.app.auth.list_users())

    def on_select(self, event=None):
        sel = self.tree.selection()
        if sel:
            u, r = self.tree.item(sel[0], "values")[:2]
            self.v_user.set(u)
            self.cb_role.set(r)

    def _run(self, fn, ok_text=None):
        try:
            fn()
        except ValueError as e:
            messagebox.showerror(u"User Manager", str(e), parent=self.app.root)
            return False
        self.refresh()
        return True

    def add(self):
        if self._run(lambda: self.app.auth.add_user(self.v_user.get(), self.v_pass.get(), self.cb_role.get())):
            self.v_pass.set(u"")

    def set_role(self):
        name = self.v_user.get().strip()
        if self._run(lambda: self.app.auth.set_role(name, self.cb_role.get())):
            if name.lower() == self.app.user.lower() and self.cb_role.get() != ROLE_ADMIN:
                messagebox.showinfo(u"User Manager", u"Your own role changed. Please log in again.",
                                    parent=self.app.root)
                self.app.logout()

    def reset(self):
        if self._run(lambda: self.app.auth.reset_password(self.v_user.get(), self.v_pass.get())):
            self.v_pass.set(u"")
            self.app.toast(u"Password updated")

    def delete(self):
        name = self.v_user.get().strip()
        if name.lower() == self.app.user.lower():
            messagebox.showerror(u"User Manager", u"You cannot delete the account you are logged in with.",
                                 parent=self.app.root)
            return
        if messagebox.askyesno(u"Delete user", u"Delete user '%s'?" % name, parent=self.app.root):
            self._run(lambda: self.app.auth.delete_user(name))


# ================================================================ Application shell

PAGE_CLASSES = {
    "dashboard": DashboardPage, "charts": ChartsPage, "compare": ComparePage,
    "stats": StatisticsPage, "quality": QualityPage, "specs": SpecsPage,
    "export": ExportPage, "lines": LineManagerPage, "users": UserManagerPage,
}
NAV_COMMON = [("dashboard", u"Dashboard"), ("charts", u"Charts"), ("compare", u"Compare / Pivot"),
              ("stats", u"Statistics"), ("quality", u"Data Quality"), ("specs", u"Specs / Cp-Cpk"),
              ("export", u"Export")]
NAV_STEEL = [NAV_COMMON[0], ("qc", u"Production & QC")] + NAV_COMMON[1:]
NAV_ADMIN = [("lines", u"Line Manager"), ("users", u"User Manager")]


class HaftAlmasApp(object):
    def __init__(self, root, auth, dm, app_root=None):
        self.root = root
        self.auth = auth
        self.dm = dm
        self.app_root = app_root
        self.user = u""
        self.role = ROLE_USER
        self.line_name = None
        self.dataset = None
        self.filtered = []
        self.applied = {}
        self.pages = {}
        self.current_page = None
        self.current_key = None
        self.nav_buttons = {}
        self.profile = "steel"
        self.line_cfg = {}
        self.filter_boxes = {}
        self._disp = {}
        self._cal = None
        self._cal_for = None
        self._cal_buttons = set()
        root.bind_all("<Button-1>", self._on_global_click, add="+")
        root.title(u"Haft Almas - Coil Analytics")
        root.configure(bg=BG)
        setup_style(root)
        self.zero_base = tk.BooleanVar(value=True)
        self.measure = tk.StringVar(value=u"Tons")
        self.container = tk.Frame(root, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.show_login()
        if dm.load_error:
            root.after(300, lambda: messagebox.showwarning(u"Configuration", dm.load_error, parent=root))

    def _clear(self):
        self.close_calendar()
        for w in self.container.winfo_children():
            w.destroy()

    # ------------------------------------------------------------ login
    def show_login(self):
        self._clear()
        self.pages, self.current_page, self.current_key = {}, None, None
        outer = tk.Frame(self.container, bg=BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")
        box = tk.Frame(outer, bg=PANEL, padx=40, pady=32, highlightbackground=GRID, highlightthickness=1)
        box.pack()
        tk.Label(box, text=u"HAFT ALMAS", bg=PANEL, fg=ACCENT, font=(FONT_FAMILY, 24, "bold")).pack()
        tk.Label(box, text=u"Coil Analytics Platform", bg=PANEL, fg=MUTED, font=FONT).pack(pady=(0, 20))
        form = tk.Frame(box, bg=PANEL)
        form.pack()
        self.v_login_user, self.v_login_pass = tk.StringVar(), tk.StringVar()
        tk.Label(form, text=u"Username", bg=PANEL, fg=MUTED, font=FONT).grid(row=0, column=0, sticky="w", pady=5)
        e1 = ttk.Entry(form, textvariable=self.v_login_user, width=24)
        e1.grid(row=0, column=1, padx=(10, 0), pady=5)
        tk.Label(form, text=u"Password", bg=PANEL, fg=MUTED, font=FONT).grid(row=1, column=0, sticky="w", pady=5)
        e2 = ttk.Entry(form, textvariable=self.v_login_pass, width=24, show="*")
        e2.grid(row=1, column=1, padx=(10, 0), pady=5)
        self.v_show = tk.BooleanVar(value=False)
        tk.Checkbutton(box, text=u"Show password", variable=self.v_show, bg=PANEL, fg=MUTED,
                       selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT,
                       highlightthickness=0, font=FONT_SMALL,
                       command=lambda: e2.configure(show="" if self.v_show.get() else "*")
                       ).pack(anchor="w", pady=(6, 0))
        self.login_msg = tk.Label(box, text=u"", bg=PANEL, fg=BAD, font=FONT_SMALL)
        self.login_msg.pack(pady=(10, 4))
        if not self.auth.users:
            self.login_msg.configure(text=u"users.json was not found next to the program.\n"
                                          u"Ask the administrator to start it once with write access.")
        ttk.Button(box, text=u"Log in", style="Accent.TButton", command=self.do_login).pack(fill="x")
        if self.auth.uses_default_password():
            tk.Label(box, text=u"First run: log in as admin / admin, then change the password.",
                     bg=PANEL, fg=MUTED, font=FONT_SMALL).pack(pady=(12, 0))
        for e in (e1, e2):
            e.bind("<Return>", lambda ev: self.do_login())
        self.v_login_pass.set(u"")
        self.root.after(150, lambda: self._safe_focus(e1))

    @staticmethod
    def _safe_focus(widget):
        try:
            widget.focus_set()
        except tk.TclError:
            pass

    def do_login(self):
        name = self.v_login_user.get().strip()
        role = self.auth.authenticate(name, self.v_login_pass.get())
        if role is None:
            self.login_msg.configure(text=u"Wrong username or password.")
            self.v_login_pass.set(u"")
            return
        self.user = self.auth.canonical_name(name)
        self.role = role
        self.build_shell()

    def logout(self):
        self.user, self.role = u"", ROLE_USER
        self.show_login()

    def change_password(self):
        p1 = simpledialog.askstring(u"Change password", u"New password:", show="*", parent=self.root)
        if not p1:
            return
        p2 = simpledialog.askstring(u"Change password", u"Repeat new password:", show="*", parent=self.root)
        if p1 != p2:
            messagebox.showerror(u"Change password", u"The passwords do not match.", parent=self.root)
            return
        try:
            self.auth.reset_password(self.user, p1)
        except ValueError as e:
            messagebox.showerror(u"Change password", str(e), parent=self.root)
            return
        self.toast(u"Password changed")

    # ------------------------------------------------------------ shell
    def nav_items(self):
        base = NAV_STEEL if self.profile == "steel" else NAV_COMMON
        return base + (NAV_ADMIN if self.role == ROLE_ADMIN else [])

    def build_shell(self):
        self._clear()
        self.hint_lbl = None
        self.pages, self.current_page, self.current_key = {}, None, None
        side = tk.Frame(self.container, bg=PANEL, width=210)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text=u"HAFT ALMAS", bg=PANEL, fg=ACCENT, font=(FONT_FAMILY, 16, "bold")).pack(
            anchor="w", padx=18, pady=(18, 0))
        tk.Label(side, text=u"Coil Analytics", bg=PANEL, fg=MUTED, font=FONT_SMALL).pack(
            anchor="w", padx=18, pady=(0, 16))
        self.nav_box = tk.Frame(side, bg=PANEL)
        self.nav_box.pack(fill="x")
        self._build_nav()
        bottom = tk.Frame(side, bg=PANEL)
        bottom.pack(side="bottom", fill="x", pady=12)
        tk.Label(bottom, text=u"%s  (%s)" % (self.user, self.role), bg=PANEL, fg=MUTED,
                 font=FONT_SMALL).pack(anchor="w", padx=18, pady=(0, 6))
        ttk.Button(bottom, text=u"Change password", command=self.change_password).pack(fill="x", padx=14, pady=2)
        ttk.Button(bottom, text=u"Log out", command=self.logout).pack(fill="x", padx=14, pady=2)

        main = tk.Frame(self.container, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=12, pady=10)
        self.topbar = tk.Frame(main, bg=BG)
        self.topbar.pack(fill="x")
        self._build_line_bar()
        self._build_filter_bar()
        self.statusbar = tk.Frame(main, bg=PANEL, highlightbackground=GRID, highlightthickness=1)
        self.statusbar.pack(side="bottom", fill="x", pady=(8, 0))
        self.toast_lbl = tk.Label(self.statusbar, text=u"", bg=PANEL, fg=MUTED, font=FONT_SMALL,
                                  anchor="w", padx=10, pady=4)
        self.toast_lbl.pack(side="left")
        self.hint_lbl = tk.Label(self.statusbar, text=u"", bg=PANEL, fg=MUTED, font=FONT_SMALL, padx=10)
        self.hint_lbl.pack(side="right")
        self._build_nav()
        self._toast_job = None
        self._clear_toast()
        self.page_area = tk.Frame(main, bg=BG)
        self.page_area.pack(fill="both", expand=True, pady=(8, 0))
        self.reload_lines()
        self.navigate("dashboard")

    def _build_line_bar(self):
        bar = tk.Frame(self.topbar, bg=BG)
        bar.pack(fill="x", pady=(0, 6))
        tk.Label(bar, text=u"Line", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 6))
        self.cb_line = ttk.Combobox(bar, values=[], width=32, state="readonly")
        self.cb_line.pack(side="left")
        self.cb_line.bind("<<ComboboxSelected>>", lambda e: self.on_line_selected())
        self.badge = tk.Label(bar, text=u"", font=FONT_BOLD, padx=8, pady=1)
        self.badge.pack(side="left", padx=(10, 0))
        self.status = tk.Label(bar, text=u"", bg=BG, fg=MUTED, font=FONT)
        self.status.pack(side="left", padx=16)
        tk.Label(bar, text=u"Dates are Jalali (1402/10/25)", bg=BG, fg=MUTED,
                 font=FONT_SMALL).pack(side="right")
        self.measure_frame = tk.Frame(bar, bg=BG)
        tk.Label(self.measure_frame, text=u"Measure", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
        cbm = ttk.Combobox(self.measure_frame, values=[u"Tons", u"Coils"], width=7, state="readonly",
                           textvariable=self.measure)
        cbm.pack(side="left")
        cbm.bind("<<ComboboxSelected>>", lambda e: self.refresh_current())

    def _build_filter_bar(self):
        self.filter_bar = tk.Frame(self.topbar, bg=PANEL, padx=10, pady=8,
                                   highlightbackground=GRID, highlightthickness=1)
        self.filter_bar.pack(fill="x")
        fb = tk.Frame(self.filter_bar, bg=PANEL)
        fb.pack(fill="x")
        self.v_from, self.v_to = tk.StringVar(), tk.StringVar()
        tk.Label(fb, text=u"From", bg=PANEL, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
        e1 = ttk.Entry(fb, textvariable=self.v_from, width=9)
        e1.pack(side="left", padx=(0, 2))
        b1 = ttk.Button(fb, text=u"\u25bc", width=2, style="Mini.TButton",
                        command=lambda: self.open_calendar(self.v_from, b1))
        b1.pack(side="left", padx=(0, 10))
        tk.Label(fb, text=u"To", bg=PANEL, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
        e2 = ttk.Entry(fb, textvariable=self.v_to, width=9)
        e2.pack(side="left", padx=(0, 2))
        b2 = ttk.Button(fb, text=u"\u25bc", width=2, style="Mini.TButton",
                        command=lambda: self.open_calendar(self.v_to, b2))
        b2.pack(side="left", padx=(0, 10))
        self._cal_buttons = set([str(b1), str(b2)])
        for e in (e1, e2):
            e.bind("<Return>", lambda ev: self.apply_filters())
        self.combo_frame = tk.Frame(fb, bg=PANEL)
        self.combo_frame.pack(side="left")
        self._rebuild_filter_combos()
        ttk.Button(fb, text=u"Apply", style="Accent.TButton", width=7, command=self.apply_filters).pack(side="left", padx=(4, 4))
        ttk.Button(fb, text=u"Reset", width=7, command=self.reset_filters).pack(side="left")
        row2 = tk.Frame(self.filter_bar, bg=PANEL)
        row2.pack(fill="x", pady=(8, 0))
        tk.Label(row2, text=u"Quick range (from newest coil)", bg=PANEL, fg=MUTED,
                 font=FONT_SMALL).pack(side="left", padx=(0, 8))
        for text, days in ((u"All time", None), (u"Last 7 days", 7), (u"Last 30 days", 30),
                           (u"Last 90 days", 90)):
            ttk.Button(row2, text=text, width=11, command=lambda d=days: self.preset(d)).pack(
                side="left", padx=(0, 4))
        self.chips = tk.Label(row2, text=u"No filters active", bg=PANEL, fg=MUTED, font=FONT_SMALL)
        self.chips.pack(side="right")

    def _filter_combo(self, parent, text):
        tk.Label(parent, text=text, bg=PANEL, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
        cb = ttk.Combobox(parent, values=[ALL], width=11, state="readonly")
        cb.set(ALL)
        cb.pack(side="left", padx=(0, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())
        return cb

    # ------------------------------------------------------------ lines / data
    def visible_lines(self):
        return [l for l in self.dm.config["lines"] if self.role == ROLE_ADMIN or l.get("active", True)]

    def visible_names(self, profile=None):
        return [l["name"] for l in self.visible_lines()
                if profile is None or l.get("profile", "steel") == profile]

    @staticmethod
    def _display(line):
        title = profiles.PROFILE_TITLES.get(line.get("profile", "steel"), u"")
        return u"%s   (%s)%s" % (line["name"], title, u"" if line.get("active", True) else u"  [hidden]")

    def _page_class(self, key):
        if key == "qc":
            from .color_pages import SteelQCPage
            return SteelQCPage
        if key == "charts" and self.profile == "steel":
            from .color_pages import SteelChartsPage
            return SteelChartsPage
        if self.profile == "color" and key not in ("lines", "users"):
            from .color_pages import COLOR_PAGES
            return COLOR_PAGES[key]
        return PAGE_CLASSES[key]

    def reload_lines(self, select=None):
        lines = self.visible_lines()
        self._disp = dict((self._display(l), l["name"]) for l in lines)
        self.cb_line.configure(values=[self._display(l) for l in lines])
        names = [l["name"] for l in lines]
        target = None
        for cand in (select, self.line_name, self.dm.get_last_line(self.user)):
            if cand in names:
                target = cand
                break
        if target is None and names:
            target = names[0]
        if target is None:
            self.cb_line.set(u"")
            self.line_name, self.dataset, self.filtered, self.applied = None, None, [], {}
            self._set_profile("steel")
            self._update_filter_choices()
            self._update_status()
            self.refresh_current()
            return
        for d, n in self._disp.items():
            if n == target:
                self.cb_line.set(d)
        self.load_line(target)

    def on_line_selected(self):
        name = self._disp.get(self.cb_line.get())
        if name:
            self.load_line(name)

    def on_lines_changed(self, select=None):
        self.reload_lines(select)

    def _set_profile(self, profile):
        changed = (profile != self.profile) or not self.filter_boxes
        self.profile = profile
        if changed:
            self._rebuild_filter_combos()
        if profile == "color":
            self.badge.configure(text=u"COLOR LINE", bg="#7c3aed", fg="#ffffff")
        else:
            self.badge.configure(text=u"STEEL", bg=PANEL2, fg=ACCENT)
        self.measure_frame.pack(side="right", padx=14)
        if changed:
            for k in list(self.pages):
                if k not in ("lines", "users"):
                    self.pages[k].destroy()
                    del self.pages[k]
            if self.current_key not in ("lines", "users"):
                self.current_page = None
            if getattr(self, "nav_box", None) is not None and getattr(self, "hint_lbl", None) is not None:
                self._build_nav()
                if self.current_key and self.current_key not in [k for k, _ in self.nav_items()]:
                    self.current_key, self.current_page = "dashboard", None
                for k in self.nav_buttons:
                    self._style_nav(k, k == self.current_key, False)

    def load_line(self, name):
        self.line_name = name
        self.line_cfg = self.dm.get_line(name) or {}
        profile = self.line_cfg.get("profile", "steel")
        self.dm.set_last_line(self.user, name)
        try:
            self.dataset = self.dm.load_dataset(name)
        except Exception as e:
            self.dataset = None
            msg = str(e) if self.role == ROLE_ADMIN else (
                u"The data file for this line is not available.\nPlease contact the system administrator.")
            messagebox.showerror(u"Load error", msg, parent=self.root)
        was_profile = self.profile
        self._set_profile(profile)
        self._update_filter_choices()
        self.reset_filters(apply=False)
        self.apply_filters(silent=True)
        if self.current_page is None and self.current_key and self.nav_buttons:
            self.navigate(self.current_key)

    def _rebuild_filter_combos(self):
        for w in self.combo_frame.winfo_children():
            w.destroy()
        self.filter_boxes = {}
        for key, label in profiles.FILTERS[self.profile]:
            self.filter_boxes[key] = self._filter_combo(self.combo_frame, label)

    def _update_filter_choices(self):
        recs = self.dataset.records if self.dataset else []
        for key, cb in self.filter_boxes.items():
            labels = [g[0] for g in analytics.group_by([r for r in recs if r.get(key)], key)]
            cb.configure(values=[ALL] + labels)

    # ------------------------------------------------------------ jalali calendar popup
    def close_calendar(self):
        cal = getattr(self, "_cal", None)
        if cal is not None:
            try:
                cal.destroy()
            except tk.TclError:
                pass
        self._cal = None
        self._cal_for = None

    def _on_global_click(self, e):
        if self._cal is None:
            return
        w = str(e.widget)
        if w.startswith(str(self._cal)) or w in self._cal_buttons:
            return
        self.close_calendar()

    def open_calendar(self, var, anchor):
        if self._cal is not None:
            same = self._cal_for is var
            self.close_calendar()
            if same:
                return
        from .calendar_widget import JalaliCalendar
        g = parse_date(var.get())
        if g is None and self.dataset:
            dates = [r["date"] for r in self.dataset.records if r.get("date")]
            g = parse_date(max(dates)) if dates else None
        initial = gregorian_to_jalali(*g) if g else None
        cal = JalaliCalendar(self.root, initial,
                             on_pick=lambda t: self._calendar_pick(var, t),
                             on_clear=lambda: self._calendar_pick(var, None))
        cal.update_idletasks()
        x = anchor.winfo_rootx() - self.root.winfo_rootx() - 60
        x = max(8, min(x, self.root.winfo_width() - cal.winfo_reqwidth() - 8))
        y = anchor.winfo_rooty() - self.root.winfo_rooty() + anchor.winfo_height() + 4
        cal.place(x=x, y=y)
        cal.lift()
        self._cal, self._cal_for = cal, var

    def _calendar_pick(self, var, jal):
        var.set(u"" if jal is None else u"%04d/%02d/%02d" % jal)
        self.close_calendar()
        self.apply_filters()

    def preset(self, days):
        if days is None or not self.dataset:
            self.v_from.set(u"")
            self.v_to.set(u"")
        else:
            dates = [r["date"] for r in self.dataset.records if r.get("date")]
            if not dates:
                self.toast(u"This line has no dates", "warn")
                return
            latest = max(dates)
            d = datetime.date(*[int(x) for x in latest.split("-")])
            self.v_from.set(format_jalali((d - datetime.timedelta(days=days - 1)).isoformat()))
            self.v_to.set(format_jalali(latest))
        self.apply_filters()

    def reset_filters(self, apply=True):
        self.v_from.set(u"")
        self.v_to.set(u"")
        for cb in self.filter_boxes.values():
            cb.set(ALL)
        if apply:
            self.apply_filters()

    def apply_filters(self, silent=False):
        df = dt = None
        try:
            if self.v_from.get().strip():
                df = normalize_date(self.v_from.get())
                if df is None:
                    raise ValueError(u"Invalid 'From' date. Type a Jalali date like 1402/10/25 or pick it from the calendar.")
            if self.v_to.get().strip():
                dt = normalize_date(self.v_to.get())
                if dt is None:
                    raise ValueError(u"Invalid 'To' date. Type a Jalali date like 1402/10/25 or pick it from the calendar.")
            if df and dt and df > dt:
                raise ValueError(u"'From' date is after 'To' date.")
        except ValueError as e:
            messagebox.showerror(u"Filter", str(e), parent=self.root)
            return
        if df:
            self.v_from.set(format_jalali(df))      # always show Jalali, whatever was typed
        if dt:
            self.v_to.set(format_jalali(dt))
        self.applied = {"date_from": df, "date_to": dt}
        for key, cb in self.filter_boxes.items():
            self.applied[key] = None if cb.get() in (ALL, u"") else cb.get()
        recs = self.dataset.records if self.dataset else []
        self.filtered = analytics.filter_records(recs, **self.applied)
        self._update_status()
        self.refresh_current()

    def _update_status(self):
        if self.dataset is None:
            text = u"No line loaded. " + (u"Open Line Manager to add one." if self.role == ROLE_ADMIN
                                          else u"Ask an administrator to add a line.")
        else:
            text = u"Coils: %d of %d   |   Rejected: %d" % (len(self.filtered), len(self.dataset.records),
                                                           self.dataset.rejected)
            if getattr(self.dataset, "has_weight", False):
                text += u"   |   %.1f t" % sum((r.get("weight_t") or 0) for r in self.filtered)
        self.status.configure(text=text)
        parts = []
        if self.applied.get("date_from"):
            parts.append(u"From " + format_jalali(self.applied["date_from"]))
        if self.applied.get("date_to"):
            parts.append(u"To " + format_jalali(self.applied["date_to"]))
        for key, lab in profiles.FILTERS[self.profile]:
            if self.applied.get(key):
                parts.append(u"%s = %s" % (lab, self.applied[key]))
        self.chips.configure(text=(u"Active:  " + u"   |   ".join(parts)) if parts else u"No filters active",
                             fg=ACCENT if parts else MUTED)

    # ------------------------------------------------------------ navigation
    def navigate(self, key):
        if key not in self.pages:
            self.pages[key] = self._page_class(key)(self.page_area, self)
        if self.current_page is not None:
            self.current_page.pack_forget()
        page = self.pages[key]
        page.pack(fill="both", expand=True)
        self.current_page, self.current_key = page, key
        for k in self.nav_buttons:
            self._style_nav(k, k == key, False)
        if key in ("lines", "users"):
            self.filter_bar.pack_forget()
        elif not self.filter_bar.winfo_ismapped():
            self.filter_bar.pack(fill="x")
        page.refresh()

    def _build_nav(self):
        for w in self.nav_box.winfo_children():
            w.destroy()
        self.nav_buttons = {}
        items = self.nav_items()
        for n, (key, label) in enumerate(items):
            row = tk.Frame(self.nav_box, bg=PANEL)
            row.pack(fill="x")
            strip = tk.Frame(row, bg=PANEL, width=4)
            strip.pack(side="left", fill="y")
            b = tk.Button(row, text=label, anchor="w", relief="flat", bd=0, padx=14, pady=9,
                          bg=PANEL, fg=TEXT, activebackground=PANEL2, activeforeground=ACCENT,
                          font=FONT, cursor="hand2", highlightthickness=0,
                          command=lambda k=key: self.navigate(k))
            b.pack(side="left", fill="x", expand=True)
            hint = tk.Label(row, text=(u"Ctrl+%d" % (n + 1)) if n < 9 else u"", bg=PANEL, fg="#56657a",
                            font=FONT_SMALL, padx=8)
            hint.pack(side="right")
            self.nav_buttons[key] = (strip, b, hint)
            for w in (b, hint):
                w.bind("<Enter>", lambda e, k=key: self._style_nav(k, k == self.current_key, True))
                w.bind("<Leave>", lambda e, k=key: self._style_nav(k, k == self.current_key, False))
        for i in range(9):
            self.root.bind_all("<Control-Key-%d>" % (i + 1), lambda e, i=i: self._shortcut(i))
        self.root.bind_all("<F5>", lambda e: self.reload_data())
        if getattr(self, "hint_lbl", None) is not None:
            self.hint_lbl.configure(text=u"F5 reload data   |   Ctrl+1..%d switch pages" % min(9, len(items)))

    def _style_nav(self, key, active, hover):
        strip, b, hint = self.nav_buttons[key]
        bg = PANEL2 if (active or hover) else PANEL
        strip.configure(bg=ACCENT if active else PANEL)
        b.configure(bg=bg, fg=ACCENT if active else TEXT)
        hint.configure(bg=bg)

    def _shortcut(self, i):
        items = self.nav_items() if self.user else []
        if 0 <= i < len(items) and self.nav_buttons:
            self.navigate(items[i][0])

    def reload_data(self):
        if not self.user or not self.line_name:
            return
        self.dm._cache.pop(self.line_name, None)
        self.load_line(self.line_name)
        self.toast(u"Data reloaded from disk")

    def toast(self, text, kind="ok"):
        try:
            col = {"ok": GOOD, "warn": WARN, "err": BAD}.get(kind, GOOD)
            self.toast_lbl.configure(text=u"  " + text, fg=col)
            if self._toast_job:
                self.root.after_cancel(self._toast_job)
            self._toast_job = self.root.after(5000, self._clear_toast)
        except tk.TclError:
            pass

    def _clear_toast(self):
        try:
            self.toast_lbl.configure(text=u"  Ready", fg=MUTED)
        except tk.TclError:
            pass

    def refresh_current(self):
        if self.current_page is not None:
            self.current_page.refresh()
