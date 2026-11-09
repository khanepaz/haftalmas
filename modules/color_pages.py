# -*- coding: utf-8 -*-
"""Pages for the colour line (tonnage, RAL colours, downgrade analysis)."""
from __future__ import print_function, unicode_literals

import re
import tkinter as tk
from tkinter import ttk

from . import analytics
from . import color_analytics as ca
from . import profiles
from .charts import (ramp, ChartCanvas, BG, PANEL, PANEL2, ACCENT, TEXT, MUTED, GRID, WARN, BAD, GOOD,
                     FONT, FONT_SMALL, FONT_BOLD, FONT_FAMILY, SERIES)
from .csv_reader import format_jalali
from .dashboard import (Page, combo_group, make_tree, fill_tree, title_label, write_csv, fmt,
                        NONE_CHOICE, opt_labels, opt_key, opt_label, StatisticsPage, QualityPage,
                        SpecsPage, ExportPage, LineManagerPage, UserManagerPage, ROLE_ADMIN, FIELD_OPTIONS, DECIMALS)
from .ral import ral_hex, ral_code

DELTA = u"\u0394E"
NUM_OPTIONS = [(DELTA, "delta_e"), (u"Gloss (GU)", "gloss"), (u"Top coat (\u00b5m)", "top_thickness"),
               (u"Thickness (mm)", "thickness"), (u"T-bend", "bend"), (u"T-bend adhesion", "bend_adhesive"),
               (u"MEK (rubs)", "mek")]
STAT_OPTIONS = NUM_OPTIONS + [(u"Weight (t)", "weight_t")]
METRIC_OPTIONS = [(u"Tons", "tons"), (u"Coils", "coils"), (u"Downgrade %", "downgrade"),
                  (u"Defect %", "defect")] + NUM_OPTIONS
GROUP_OPTIONS = [(u"RAL", "ral"), (u"Supplier", "supplier"), (u"Quality grade", "grade"),
                 (u"Main cause", "cause1"), (u"Second cause", "cause2")]
PERIODS = [(u"Month", "month"), (u"Week", "week"), (u"Day", "day")]
DEC = {"delta_e": 2, "gloss": 1, "top_thickness": 1, "thickness": 3, "bend": 1, "bend_adhesive": 1,
       "mek": 1, "weight_t": 2, "tons": 1, "coils": 0, "downgrade": 1, "defect": 1}
DEC.update(dict((k, v) for k, v in DECIMALS.items() if k not in DEC))
NEUTRAL = "#5b6776"

# ---- quality-grade colours (edit here). Keys are lower-case grade names, best grade first.
GRADE_COLORS = {
    "aaa": "#15803d",   # dark green
    "aa": "#22c55e",    # green
    "a": "#a3e635",     # lime
    "ab": "#facc15",    # yellow
    "b": "#f97316",     # orange
    "c": "#ef4444",     # red
    "z": "#a855f7",     # violet
}
PRIME_SHADES = ["#15803d", "#22c55e", "#a3e635", "#2dd4bf", "#38bdf8", "#16a34a"]     # unknown prime grades
WARM_SHADES = ["#facc15", "#f97316", "#ef4444", "#a855f7", "#fb7185", "#e879f9"]      # unknown other grades
PALETTE = SERIES + ["#f97316", "#14b8a6", "#eab308", "#c084fc", "#60a5fa", "#fb923c"]
NO = analytics.NO_GROUP


# ---------------------------------------------------------------- helpers

def meas(app):
    return "tons" if app.measure.get().lower().startswith("t") else "coils"


def munit(app):
    return u"t" if meas(app) == "tons" else u"coils"


def mdec(app):
    return 1 if meas(app) == "tons" else 0


def cmap(app, dim):
    """label -> colour, stable for the whole dataset (RAL labels get their real RAL colour)."""
    ds = app.dataset
    cache = getattr(ds, "_cmaps", None)
    if cache is None:
        cache = {}
        ds._cmaps = cache
    if dim in cache:
        return cache[dim]
    labels = sorted(set(analytics.group_label(r.get(dim)) for r in ds.records))
    m = {NO: NEUTRAL}
    k = 0
    overrides = app.dm.config.get("ral_colors", {})
    if dim == "ral":
        for lab in labels:
            if lab == NO:
                continue
            col = ral_hex(lab, overrides)
            if col is None:
                col = PALETTE[k % len(PALETTE)]
                k += 1
            m[lab] = col
    elif dim == "qgrade" or (dim == "grade" and ds.profile == "color"):
        # every quality grade gets its OWN colour: fixed colours from GRADE_COLORS first, then
        # automatic ones (green shades for prime grades, warm shades for the others)
        prime = getattr(ds, "prime", None) or ()
        pi = wi = 0
        for lab in labels:
            if lab == NO:
                continue
            key = lab.lower()
            if key in GRADE_COLORS:
                m[lab] = GRADE_COLORS[key]
            elif prime and key in prime:
                m[lab] = PRIME_SHADES[pi % len(PRIME_SHADES)]
                pi += 1
            elif prime:
                m[lab] = WARM_SHADES[wi % len(WARM_SHADES)]
                wi += 1
            else:
                m[lab] = PALETTE[k % len(PALETTE)]
                k += 1
    else:
        for lab in labels:
            if lab == NO:
                continue
            m[lab] = PALETTE[k % len(PALETTE)]
            k += 1
    cache[dim] = m
    return m


def colors_for(app, dim, labels):
    m = cmap(app, dim)
    return [m.get(l, NEUTRAL) for l in labels]


def metric_dec(metric):
    return DEC.get(metric, 1)


def metric_title(metric, app=None):
    if metric in ("tons", "coils") and app is not None:
        return u"Tons" if metric == "tons" else u"Coils"
    return opt_label(METRIC_OPTIONS, metric)


def key_or(label, options, default):
    if label == NONE_CHOICE or not label:
        return default
    return opt_key(options, label)


def rows_for_bar(app, recs, key, metric, limit=15):
    rows = ca.sort_rows(ca.group_rows(recs, key, metric, meas(app)), limit)
    return rows


def build_insights(app, recs):
    out = []
    m = meas(app)
    if not getattr(app.dataset, "prime", None):
        out.append(u"Prime grades are not set (Line Manager): every coil with a main defect counts as downgraded")
    dfx, dgx = ca.defect_pct(recs, m), ca.downgrade_pct(recs, m)
    if dfx is not None and dgx is not None:
        out.append(u"Defects on %.1f%% of %s, downgraded: %.1f%%" % (dfx, munit(app), dgx))
    pc = [x for x in ca.pareto(recs, "cause1", m) if x[0] != ca.NOT_RECORDED]
    if pc:
        tot = sum(v for _, v in pc)
        out.append(u"Top downgrade cause: %s (%.1f %s, %.0f%% of causes)" % (pc[0][0], pc[0][1], munit(app),
                                                                         pc[0][1] * 100.0 / tot))
    for key, lab in (("ral", u"RAL"), ("supplier", u"supplier")):
        rows = [r for r in ca.group_rows(recs, key, "downgrade", m) if r[1] is not None and r[2] >= 3 and r[0] != NO]
        if len(rows) >= 2:
            worst = max(rows, key=lambda r: r[1])
            if worst[1] > 0:
                out.append(u"Highest downgrade by %s: %s (%.1f%%)" % (lab, worst[0], worst[1]))
    lsl, usl = app.dm.get_spec("color:delta_e")
    vals = analytics.values(recs, "delta_e")
    if (lsl is not None or usl is not None) and len(vals) >= 2:
        try:
            res = analytics.process_capability(vals, lsl, usl)
        except ValueError:
            res = None
        if res and res["pct_out"] is not None:
            out.append(u"%s out of spec: %.1f%%" % (DELTA, res["pct_out"]))
    return out[:4] if len(out) > 4 else out


def empty_state(page, app_btn=True):
    page.empty = tk.Frame(page, bg=BG)
    inner = tk.Frame(page.empty, bg=BG)
    inner.place(relx=0.5, rely=0.4, anchor="center")
    tk.Label(inner, text=u"No data yet", bg=BG, fg=ACCENT, font=(FONT_FAMILY, 20, "bold")).pack()
    tk.Label(inner, text=u"Add a production line (CSV file) to see tonnage and quality charts.", bg=BG,
             fg=MUTED, font=FONT).pack(pady=(6, 14))
    page.empty_btn = ttk.Button(inner, text=u"Open Line Manager", style="Accent.TButton",
                                command=lambda: page.app.navigate("lines"))


# ================================================================ Dashboard

class ColorDashboardPage(Page):
    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        self.content = tk.Frame(self, bg=BG)
        empty_state(self)
        self.ribbon = ChartCanvas(self.content, height=38, highlightthickness=0)
        self.ribbon.pack(fill="x", pady=(0, 8))
        self.kpi = tk.Frame(self.content, bg=BG)
        self.kpi.pack(fill="x", pady=(0, 8))
        self.insight = tk.Label(self.content, text=u"", bg=PANEL, fg=TEXT, font=FONT, anchor="w",
                                justify="left", padx=12, pady=6, highlightbackground=GRID,
                                highlightthickness=1)
        self.insight.pack(fill="x", pady=(0, 8))
        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="both", expand=True)
        for i in (0, 1, 2):
            grid.columnconfigure(i, weight=1, uniform="c")
        for i in (0, 1):
            grid.rowconfigure(i, weight=1, uniform="r")
        self.c = [ChartCanvas(grid) for _ in range(6)]
        for i, ch in enumerate(self.c):
            ch.grid(row=i // 3, column=i % 3, sticky="nsew", padx=(0 if i % 3 == 0 else 4, 0 if i % 3 == 2 else 4),
                    pady=(0 if i < 3 else 4, 4 if i < 3 else 0))

    def refresh(self):
        app = self.app
        recs = app.filtered
        if app.dataset is None:
            self.content.pack_forget()
            if app.role == ROLE_ADMIN:
                self.empty_btn.pack()
            self.empty.pack(fill="both", expand=True)
            return
        self.empty.pack_forget()
        if not self.content.winfo_ismapped():
            self.content.pack(fill="both", expand=True)
        m = meas(app)
        unit = munit(app)
        # ribbon of RAL colours by amount
        rows = ca.sort_rows(ca.group_rows(recs, "ral", m, m), 18)
        rows = [r for r in rows if r[1]]
        self.ribbon.show("ribbon", items=[(r[0], r[1], c) for r, c in
                                          zip(rows, colors_for(app, "ral", [r[0] for r in rows]))])
        # KPI cards
        for w in self.kpi.winfo_children():
            w.destroy()
        tons = ca.total(recs, "tons")
        dg = ca.downgrade_pct(recs, m)
        dg_t = ca.total([r for r in recs if r.get("downgraded")], "tons")
        dfx = ca.defect_pct(recs, m)
        cards = [(u"Production", fmt(tons, 1), u"tons    %d coils" % len(recs), ACCENT),
                 (u"Downgrade", (fmt(dg, 1) + u" %") if dg is not None else u"-",
                  u"%.1f t downgraded" % dg_t, BAD),
                 (u"With defect", (fmt(dfx, 1) + u" %") if dfx is not None else u"-",
                  u"%d coils" % sum(1 for r in recs if r.get("defect")), WARN)]
        for lab, f, d, u in ((DELTA + u" avg", "delta_e", 2, u""), (u"Gloss avg", "gloss", 1, u"GU"),
                             (u"Top coat avg", "top_thickness", 1, u"\u00b5m"), (u"MEK avg", "mek", 0, u"rubs"),
                             (u"T-bend avg", "bend", 1, u"")):
            vals = analytics.values(recs, f)
            if vals:
                st = analytics.descriptive_stats(vals)
                cards.append((lab, fmt(st["mean"], d), (u + u"    s = " + fmt(st["std"], d)).strip(), None))
        for i, (name, val, sub, col) in enumerate(cards[:7]):
            card = tk.Frame(self.kpi, bg=PANEL, padx=14, pady=8, highlightbackground=GRID, highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Frame(card, bg=col or SERIES[(i + 1) % len(SERIES)], height=3).pack(fill="x", pady=(0, 6))
            tk.Label(card, text=name, bg=PANEL, fg=MUTED, font=FONT_SMALL).pack(anchor="w")
            tk.Label(card, text=val, bg=PANEL, fg=ACCENT, font=(FONT_FAMILY, 18, "bold")).pack(anchor="w")
            tk.Label(card, text=sub or u" ", bg=PANEL, fg=MUTED, font=FONT_SMALL).pack(anchor="w")
        tips = build_insights(app, recs)
        self.insight.configure(text=(u"Insights     " + u"     |     ".join(tips)) if tips
                               else u"Insights     not enough data yet")
        # charts
        mode = ca.auto_period(recs)
        labels, series = ca.period_series(recs, mode, "ral", m, m, 8)
        cols = colors_for(app, "ral", [s_[0] for s_ in series])
        self.c[0].show("stack", labels=labels, series=[(s_[0], s_[1], c) for s_, c in zip(series, cols)],
                       title=u"%s by %s, per RAL" % (u"Tons" if m == "tons" else u"Coils",
                                                     dict((x[1], x[0]) for x in PERIODS)[mode].lower()),
                       ylabel=unit, decimals=mdec(app))
        for ch, key, ttl in ((self.c[1], "ral", u"RAL"), (self.c[2], "supplier", u"Supplier")):
            r = rows_for_bar(app, recs, key, m, 12)
            ch.show("bar", labels=[x[0] for x in r], values=[x[1] for x in r], counts=[x[2] for x in r],
                    colors=colors_for(app, key, [x[0] for x in r]), decimals=mdec(app),
                    title=u"%s by %s" % (u"Tons" if m == "tons" else u"Coils", ttl), ylabel=unit,
                    zero_base=True)
        g = ca.group_rows(recs, "grade", m, m)
        g = ca.sort_rows(g, 8)
        self.c[3].show("donut", items=[(x[0], x[1], c) for x, c in zip(g, colors_for(app, "grade", [x[0] for x in g]))],
                       title=u"Quality grade mix", center=fmt(ca.total(recs, m), mdec(app)), sub=unit,
                       decimals=mdec(app))
        pc = ca.pareto(recs, "cause1", m)[:10]
        self.c[4].show("pareto", labels=[x[0] for x in pc], values=[x[1] for x in pc],
                       title=u"Downgrade causes (main)", ylabel=unit, decimals=mdec(app))
        vals, labs, hl, ticks = control_data(app, recs, "delta_e")
        self.c[5].show("line", values=vals, labels=labs, tick_labels=ticks, title=DELTA + u" control chart",
                       ylabel=DELTA, hlines=hl, show_mean=False, color=ACCENT)


ONE_SIDED = ("delta_e",)


def control_data(app, recs, field, prefix=u"color:", one_sided=ONE_SIDED):
    rows = [r for r in recs if r.get(field) is not None]
    rows.sort(key=lambda r: (r.get("date") or u"9999", r["_row"]))
    vals = [r[field] for r in rows]
    hl = []
    if len(vals) >= 5:
        mu = analytics.mean(vals)
        sd = analytics.std(vals) or 0.0
        lcl = mu - 3 * sd
        hl = [(mu, WARN, u"mean"), (mu + 3 * sd, BAD, u"UCL")]
        # all these parameters are non-negative, and for delta E lower is simply better:
        # a lower limit is shown only when it is above zero and the metric is two-sided
        if field not in one_sided and lcl > 0:
            hl.append((lcl, BAD, u"LCL"))
    lsl, usl = app.dm.get_spec(prefix + field)
    if usl is not None:
        hl.append((usl, GOOD, u"USL"))
    if lsl is not None:
        hl.append((lsl, GOOD, u"LSL"))
    ticks = [format_jalali(r["date"]) if r.get("date") else r["coil"] for r in rows]
    return vals, [r["coil"] for r in rows], hl, ticks


# ================================================================ Charts

class ColorChartsPage(Page):
    # per line type configuration - the steel page only overrides these
    NUMS, GROUPS, METRICS = NUM_OPTIONS, GROUP_OPTIONS, METRIC_OPTIONS
    SPEC_PREFIX, ONE_SIDED = u"color:", ONE_SIDED
    DEFAULT_GROUP, DEFAULT_GROUP2, DEFAULT_X = u"RAL", u"Supplier", 1
    FALLBACK_GROUP, FALLBACK_GROUP2 = "ral", "supplier"

    def measure(self):
        return meas(self.app)

    def mtitle(self, metric):
        if metric in ("tons", "coils"):
            return u"Tons" if metric == "tons" else u"Coils"
        return opt_label(self.METRICS, metric)

    def tip(self, r):
        return u"Coil %s\nRAL: %s\nSupplier: %s" % (r["coil"], r.get("ral") or u"-", r.get("supplier") or u"-")

    TYPES = [u"Production over time", u"Metric trend", u"Bar by group", u"Share (donut)",
             u"Pareto of causes", u"Box plot", u"Scatter", u"Histogram", u"Heatmap", u"Control chart"]
    SHOW = {
        u"Production over time": {"period": None, "group": u"Stack by"},
        u"Metric trend": {"metric": None, "period": None, "group2": u"Split by"},
        u"Bar by group": {"metric": None, "group": u"Group by"},
        u"Share (donut)": {"group": u"Group by"},
        u"Pareto of causes": {"cause": None, "scope": None},
        u"Box plot": {"field": None, "group": u"Group by"},
        u"Scatter": {"field": u"Y axis", "x": None, "group2": u"Color by"},
        u"Histogram": {"field": None, "bins": None},
        u"Heatmap": {"metric": None, "group": u"Rows", "group2": u"Columns"},
        u"Control chart": {"field": None},
    }

    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        nums = opt_labels(self.NUMS)
        specs = [("type", u"Chart", self.TYPES, 20, self.TYPES[0]),
                 ("metric", u"Metric", opt_labels(self.METRICS), 14, u"Tons"),
                 ("field", u"Field", nums, 13, nums[0]),
                 ("x", u"X axis", nums, 13, nums[self.DEFAULT_X]),
                 ("group", u"Group by", [NONE_CHOICE] + opt_labels(self.GROUPS), 13, self.DEFAULT_GROUP),
                 ("group2", u"Split by", [NONE_CHOICE] + opt_labels(self.GROUPS), 13, self.DEFAULT_GROUP2),
                 ("period", u"Period", opt_labels(PERIODS), 8, u"Month"),
                 ("cause", u"Causes", [u"Main cause", u"Second cause", u"Both"], 12, u"Main cause"),
                 ("scope", u"Causes of", [u"Downgraded coils", u"All coils with defect"], 20, u"Downgraded coils")]
        self.ctl = {}
        for i, (name, label, values, width, default) in enumerate(specs):
            f, cb = combo_group(bar, label, values, width, default)
            f.grid(row=i // 4, column=i % 4, padx=(0, 14), pady=2, sticky="w")
            cb.bind("<<ComboboxSelected>>", self._on_change)
            self.ctl[name] = (f, cb)
        f = tk.Frame(bar, bg=BG)
        tk.Label(f, text=u"Bins", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
        self.bins = tk.IntVar(value=15)
        sp = tk.Spinbox(f, from_=3, to=80, width=5, textvariable=self.bins, command=self.draw, bg=PANEL2,
                        fg=TEXT, insertbackground=TEXT, buttonbackground=PANEL2, relief="flat",
                        highlightthickness=1, highlightbackground=GRID, font=FONT)
        sp.pack(side="left")
        sp.bind("<Return>", lambda e: self.draw())
        f.grid(row=2, column=1, padx=(0, 14), pady=2, sticky="w")
        self.ctl["bins"] = (f, None)
        self.zero = ttk.Checkbutton(bar, text=u"Zero baseline", variable=app.zero_base, command=app.refresh_current)
        self.zero.grid(row=2, column=2, sticky="w")
        self.chart = ChartCanvas(self)
        self.chart.pack(fill="both", expand=True)
        self._update_controls()

    def _on_change(self, event=None):
        self._update_controls()
        self.draw()

    def _update_controls(self):
        spec = self.SHOW[self.ctl["type"][1].get()]
        for name, (f, cb) in self.ctl.items():
            if name == "type":
                continue
            if name in spec:
                f.grid()
                if spec[name]:
                    f.winfo_children()[0].configure(text=spec[name])
            else:
                f.grid_remove()
        if self.ctl["type"][1].get() == u"Bar by group":
            self.zero.grid()
        else:
            self.zero.grid_remove()

    def val(self, name):
        return self.ctl[name][1].get()

    def refresh(self):
        self.draw()

    def draw(self):
        app = self.app
        recs = app.filtered
        t = self.val("type")
        m = self.measure()
        unit = u"t" if m == "tons" else u"coils"
        dec = 1 if m == "tons" else 0
        ch = self.chart
        gk = key_or(self.val("group"), self.GROUPS, None)
        gk2 = key_or(self.val("group2"), self.GROUPS, None)
        metric = opt_key(self.METRICS, self.val("metric"))
        field = opt_key(self.NUMS, self.val("field"))
        flabel = self.val("field")
        period = opt_key(PERIODS, self.val("period"))
        if app.dataset is None:
            ch.show("bar", labels=[], values=[])
            return
        if t == u"Production over time":
            labels, series = ca.period_series(recs, period, gk, m, m, 8)
            cols = colors_for(app, gk, [s_[0] for s_ in series]) if gk else [ACCENT]
            ch.show("stack", labels=labels, series=[(s_[0], s_[1], c) for s_, c in zip(series, cols)],
                    title=u"%s per %s%s" % (u"Tons" if m == "tons" else u"Coils", self.val("period").lower(),
                                            (u", by " + self.val("group")) if gk else u""),
                    ylabel=unit, decimals=dec)
        elif t == u"Metric trend":
            labels, series = ca.period_series(recs, period, gk2, metric, m, 6)
            cols = colors_for(app, gk2, [s_[0] for s_ in series]) if gk2 else [ACCENT]
            ch.show("mline", labels=labels, series=[(s_[0], s_[1], c) for s_, c in zip(series, cols)],
                    title=u"%s per %s" % (self.mtitle(metric), self.val("period").lower()),
                    ylabel=self.mtitle(metric), decimals=metric_dec(metric))
        elif t == u"Bar by group":
            key = gk or self.FALLBACK_GROUP
            r = rows_for_bar(app, recs, key, metric)
            ch.show("bar", labels=[x[0] for x in r], values=[x[1] for x in r], counts=[x[2] for x in r],
                    colors=colors_for(app, key, [x[0] for x in r]), decimals=metric_dec(metric),
                    title=u"%s by %s" % (self.mtitle(metric), opt_label(self.GROUPS, key)),
                    ylabel=self.mtitle(metric), zero_base=app.zero_base.get())
        elif t == u"Share (donut)":
            key = gk or self.FALLBACK_GROUP
            r = ca.sort_rows(ca.group_rows(recs, key, m, m))
            top, rest = r[:8], r[8:]
            items = [(x[0], x[1]) for x in top]
            if rest:
                items.append((u"Other", sum(x[1] or 0 for x in rest)))
            cols = colors_for(app, key, [i[0] for i in items])
            if rest:
                cols[-1] = NEUTRAL
            ch.show("donut", items=[(i[0], i[1], c) for i, c in zip(items, cols)],
                    title=u"%s share by %s" % (u"Tons" if m == "tons" else u"Coils", opt_label(self.GROUPS, key)),
                    center=fmt(ca.total(recs, m), dec), sub=unit, decimals=dec)
        elif t == u"Pareto of causes":
            src = {u"Main cause": "cause1", u"Second cause": "cause2", u"Both": "both"}[self.val("cause")]
            scope = "downgraded" if self.val("scope").startswith(u"Downgraded") else "defects"
            pc = ca.pareto(recs, src, m, scope)[:12]
            ch.show("pareto", labels=[x[0] for x in pc], values=[x[1] for x in pc],
                    title=u"%s - %s" % (u"Downgrade causes" if scope == "downgraded" else u"Defects (all grades)",
                                        self.val("cause").lower()), ylabel=unit, decimals=dec)
        elif t == u"Box plot":
            if gk:
                groups = [(lab, analytics.values(r, field)) for lab, r in analytics.group_by(recs, gk)]
                cols = colors_for(app, gk, [g[0] for g in groups])
            else:
                groups, cols = [(u"All coils", analytics.values(recs, field))], None
            ch.show("box", groups=groups, colors=cols, title=u"%s by %s" % (flabel, self.val("group")),
                    ylabel=flabel)
        elif t == u"Scatter":
            xk = opt_key(self.NUMS, self.val("x"))
            xs, ys, tips, pcs = [], [], [], []
            cm = cmap(app, gk2) if gk2 else None
            used = {}
            for r in recs:
                a, b = r.get(xk), r.get(field)
                if a is None or b is None:
                    continue
                xs.append(a)
                ys.append(b)
                tips.append(self.tip(r))
                if cm:
                    lab = analytics.group_label(r.get(gk2))
                    pcs.append(cm.get(lab, NEUTRAL))
                    used[lab] = cm.get(lab, NEUTRAL)
            legend = sorted(used.items()) if cm else None
            ch.show("scatter", xs=xs, ys=ys, tips=tips, point_colors=pcs or None, legend=legend,
                    title=u"%s vs %s" % (flabel, self.val("x")), xlabel=self.val("x"), ylabel=flabel)
        elif t == u"Histogram":
            try:
                bins = max(3, min(80, int(self.bins.get())))
            except (ValueError, tk.TclError):
                bins = 15
            ch.show("hist", values=analytics.values(recs, field), bins=bins,
                    title=flabel + u" - Distribution", xlabel=flabel)
        elif t == u"Heatmap":
            rk, ck = gk or self.FALLBACK_GROUP, gk2 or self.FALLBACK_GROUP2
            rows, cols, mat = ca.matrix(recs, rk, ck, metric, m)
            ch.show("heat", rows=rows, cols=cols, matrix=mat, decimals=metric_dec(metric),
                    row_colors=colors_for(app, rk, rows),
                    title=u"%s: %s x %s" % (self.mtitle(metric), opt_label(self.GROUPS, rk),
                                            opt_label(self.GROUPS, ck)))
        else:
            vals, labs, hl, ticks = control_data(app, recs, field, self.SPEC_PREFIX, self.ONE_SIDED)
            ch.show("line", values=vals, labels=labs, tick_labels=ticks,
                    title=flabel + u" - Control chart (mean, 3-sigma limits)",
                    ylabel=flabel, hlines=hl, show_mean=False)


# ================================================================ Compare

MIX_OPTIONS = [(u"Quality grade mix", "qg_mix"), (u"Quality grade mix %", "qg_pct")]
CMP_METRICS = METRIC_OPTIONS + MIX_OPTIONS


def quality_mix(app, chart, groups, qkey, pct, tons_selected, title):
    """Stacked chart: one column per group, one segment per quality grade (absolute or % of the group)."""
    recs_all = [r for _, rs in groups for r in rs]
    if not any(r.get(qkey) for r in recs_all):
        chart.show("bar", labels=[], values=[], title=title)
        return
    grades = [g[0] for g in analytics.group_by(recs_all, qkey)]       # best grade first
    cols = colors_for(app, qkey, grades)
    m = "tons" if (tons_selected and any(ca.total(rs, "tons") > 0 for _, rs in groups)) else "coils"
    totals = [ca.total(rs, m) for _, rs in groups]
    series = []
    for gr, col in zip(grades, cols):
        vals = []
        for (lab, rs), tot in zip(groups, totals):
            amt = ca.total([r for r in rs if analytics.group_label(r.get(qkey)) == gr], m)
            vals.append(amt * 100.0 / tot if (pct and tot) else amt)
        series.append((gr, vals, col))
    chart.show("stack", labels=[g[0] for g in groups], series=series, title=title,
               ylabel=u"%" if pct else (u"t" if m == "tons" else u"coils"),
               decimals=1 if (pct or m == "tons") else 0, show_totals=not pct)


class ColorComparePage(Page):
    QUICK = [(u"Tons by RAL", "ral", "tons"), (u"Downgrade by RAL", "ral", "downgrade"),
             (u"Defect by RAL", "ral", "defect"), (u"Downgrade by Supplier", "supplier", "downgrade"),
             (DELTA + u" by Supplier", "supplier", "delta_e"), (u"Gloss by Supplier", "supplier", "gloss"),
             (u"Top coat by RAL", "ral", "top_thickness")]
    COLS = [("grp", u"Group"), ("n", u"Coils"), ("t", u"Tons"), ("sh", u"Share %"), ("dg", u"Downgrade %"),
            ("df", u"Defect %"), ("de", DELTA), ("gl", u"Gloss"), ("tc", u"Top \u00b5m"), ("mek", u"MEK"), ("bd", u"T-bend")]

    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text=u"Mode", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 6))
        self.mode = tk.StringVar(value="group")
        ttk.Radiobutton(top, text=u"Group", variable=self.mode, value="group", command=self.refresh).pack(side="left", padx=4)
        ttk.Radiobutton(top, text=u"Lines", variable=self.mode, value="lines", command=self.refresh).pack(side="left", padx=(4, 16))
        g, self.cb_group = combo_group(top, u"Group By", opt_labels(GROUP_OPTIONS), 12, u"RAL")
        g.pack(side="left", padx=(0, 16))
        g, self.cb_left = combo_group(top, u"Left chart", opt_labels(CMP_METRICS), 18, u"Tons")
        g.pack(side="left", padx=(0, 16))
        g, self.cb_right = combo_group(top, u"Right chart", opt_labels(CMP_METRICS), 18, u"Downgrade %")
        g.pack(side="left", padx=(0, 16))
        ttk.Checkbutton(top, text=u"Zero baseline", variable=app.zero_base, command=app.refresh_current).pack(side="left")
        for cb in (self.cb_group, self.cb_left, self.cb_right):
            cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        quick = tk.Frame(self, bg=BG)
        quick.pack(fill="x", pady=8)
        tk.Label(quick, text=u"Quick", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 6))
        for text, grp, met in self.QUICK:
            ttk.Button(quick, text=text, command=lambda g=grp, f=met: self.quick(g, f)).pack(side="left", padx=3)
        frame, self.tree = make_tree(self, self.COLS, {"grp": 150, "n": 55, "t": 75, "sh": 70, "dg": 95, "df": 80,
                                                       "de": 60, "gl": 60, "tc": 65, "mek": 60, "bd": 65}, height=6)
        frame.pack(fill="x")
        charts = tk.Frame(self, bg=BG)
        charts.pack(fill="both", expand=True, pady=(8, 0))
        charts.columnconfigure(0, weight=1, uniform="c")
        charts.columnconfigure(1, weight=1, uniform="c")
        charts.rowconfigure(0, weight=1)
        self.c1, self.c2 = ChartCanvas(charts), ChartCanvas(charts)
        self.c1.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.c2.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

    def quick(self, grp, met):
        self.mode.set("group")
        self.cb_group.set(opt_label(GROUP_OPTIONS, grp))
        self.cb_left.set(opt_label(CMP_METRICS, met))
        self.refresh()

    def groups(self):
        if self.mode.get() == "lines":
            out = []
            for name in self.app.visible_names("color"):
                try:
                    ds = self.app.dm.load_dataset(name)
                except Exception:
                    continue
                out.append((name, analytics.filter_records(ds.records, **self.app.applied)))
            return out, None
        key = opt_key(GROUP_OPTIONS, self.cb_group.get())
        return analytics.group_by(self.app.filtered, key), key

    def refresh(self):
        app = self.app
        m = meas(app)
        groups, key = self.groups()
        all_t = sum(ca.total(r, "tons") for _, r in groups) or 1.0
        rows = []
        for lab, recs in groups:
            mean = lambda f: analytics.mean(analytics.values(recs, f))
            t = ca.total(recs, "tons")
            rows.append((lab, len(recs), fmt(t, 1), fmt(t * 100.0 / all_t, 1), fmt(ca.downgrade_pct(recs, m), 1),
                         fmt(ca.defect_pct(recs, m), 1), fmt(mean("delta_e"), 2), fmt(mean("gloss"), 1), fmt(mean("top_thickness"), 1),
                         fmt(mean("mek"), 0), fmt(mean("bend"), 1)))
        fill_tree(self.tree, rows)
        by = u"Line" if key is None else self.cb_group.get()
        for chart, cb in ((self.c1, self.cb_left), (self.c2, self.cb_right)):
            met = opt_key(CMP_METRICS, cb.get())
            if met in ("qg_mix", "qg_pct"):
                quality_mix(app, chart, groups, "grade", met == "qg_pct", m == "tons",
                            u"%s by %s" % (cb.get(), by))
                continue
            data = [(lab, ca.metric_value(r, met, m), len(r)) for lab, r in groups]
            data = sorted(data, key=lambda x: (x[1] is None, -(x[1] or 0)))[:15]
            labels = [d[0] for d in data]
            cols = colors_for(app, key, labels) if key else [PALETTE[i % len(PALETTE)] for i in range(len(labels))]
            chart.show("bar", labels=labels, values=[d[1] for d in data], counts=[d[2] for d in data],
                       colors=cols, decimals=metric_dec(met), title=u"%s by %s" % (metric_title(met, app), by),
                       ylabel=metric_title(met, app), zero_base=app.zero_base.get())


# ================================================================ Statistics / Quality / Specs / Export

class ColorStatsPage(StatisticsPage):
    FIELDS, GROUPS, DEC, DEFAULT_GROUP = STAT_OPTIONS, GROUP_OPTIONS, DEC, u"RAL"

    def draw(self):
        recs = self.app.filtered
        fk = opt_key(self.FIELDS, self.cb_field.get())
        g = self.cb_group.get()
        if g == NONE_CHOICE:
            groups, cols = [(u"All coils", analytics.values(recs, fk))], None
            title = self.cb_field.get() + u" - Box Plot"
        else:
            gk = opt_key(self.GROUPS, g)
            groups = [(lab, analytics.values(r, fk)) for lab, r in analytics.group_by(recs, gk)]
            cols = colors_for(self.app, gk, [x[0] for x in groups])
            title = self.cb_field.get() + u" by " + g
        self.chart.show("box", groups=groups, colors=cols, title=title, ylabel=self.cb_field.get())


class ColorQualityPage(QualityPage):
    FIELD_LIST = ("coil", "date", "thickness", "ral", "delta_e", "gloss", "supplier", "top_thickness",
                  "bend", "bend_adhesive", "mek", "grade", "weight_t", "cause1", "cause2")
    LABELS = profiles.LABELS["color"]
    NUMERIC = set(["thickness", "delta_e", "gloss", "top_thickness", "bend", "bend_adhesive", "mek", "weight_t"])

    def extra_summary(self, ds):
        recs = ds.records
        tons = sum(r["weight_t"] for r in recs)
        dg = sum(r["weight_t"] for r in recs if r["downgraded"])
        nd = sum(1 for r in recs if r.get("defect"))
        unknown = len(set(r["ral"] for r in recs if r.get("ral") and not ral_code(r["ral"])))
        return (u"Total weight: %.1f t     Downgraded: %.1f t (%.1f%%)     Coils with a defect: %d (%.1f%%)\n"
                u"Prime grades: %s     RAL values without a code: %d     Weight unit in CSV: %s") % (
            tons, dg, dg * 100.0 / tons if tons else 0.0, nd, nd * 100.0 / len(recs) if recs else 0.0,
            u", ".join(sorted(getattr(ds, "prime", []))) or u"not set (defect = downgrade)", unknown,
            getattr(ds, "weight_unit", u"kg"))


class ColorSpecsPage(SpecsPage):
    FIELDS, DEC, SPEC_PREFIX = NUM_OPTIONS, DEC, u"color:"


class ColorExportPage(ExportPage):
    FIELDS, GROUPS = STAT_OPTIONS, GROUP_OPTIONS

    def export_data(self):
        header = [u"coil", u"date", u"date_jalali", u"thickness_mm", u"ral", u"delta_e", u"gloss", u"supplier",
                  u"top_coat_um", u"t_bend", u"t_bend_adhesion", u"mek", u"grade", u"weight_t", u"cause1",
                  u"cause2", u"defect", u"downgraded"]
        rows = []
        for r in self.app.filtered:
            rows.append([r["coil"], r.get("date"), format_jalali(r["date"]) if r.get("date") else u"",
                         r.get("thickness"), r.get("ral"), r.get("delta_e"), r.get("gloss"), r.get("supplier"),
                         r.get("top_thickness"), r.get("bend"), r.get("bend_adhesive"), r.get("mek"),
                         r.get("grade"), round(r["weight_t"], 4), r.get("cause1"), r.get("cause2"),
                         u"yes" if r.get("defect") else u"no", u"yes" if r["downgraded"] else u"no"])
        self._save(u"color_line_data.csv", header, rows)

    def export_groups(self):
        gk = opt_key(self.GROUPS, self.cb_group.get())
        m = meas(self.app)
        header = [self.cb_group.get(), u"coils", u"tons", u"share_pct", u"downgrade_pct", u"defect_pct", u"avg_delta_e",
                  u"avg_gloss", u"avg_top_coat_um", u"avg_mek", u"avg_t_bend"]
        groups = analytics.group_by(self.app.filtered, gk)
        all_t = sum(ca.total(r, "tons") for _, r in groups) or 1.0
        rows = []
        for lab, recs in groups:
            mean = lambda f: analytics.mean(analytics.values(recs, f))
            t = ca.total(recs, "tons")
            rows.append([lab, len(recs), round(t, 3), round(t * 100.0 / all_t, 2), ca.downgrade_pct(recs, m),
                         ca.defect_pct(recs, m), mean("delta_e"), mean("gloss"), mean("top_thickness"), mean("mek"), mean("bend")])
        self._save(u"color_group_summary.csv", header, rows)


# ================================================================ Steel: production and quality

STEEL_GROUPS = [(u"HR Mark", "hr_mark"), (u"HR Grade", "hr_grade"), (u"Product grade", "grade"),
                (u"Quality grade", "qgrade"), (u"Main cause", "cause1"), (u"Second cause", "cause2")]
BAND_OPTIONS = [(u"YS (MPa)", "ys"), (u"UTS (MPa)", "uts"), (u"EL (%)", "el"), (u"Thickness (mm)", "thickness")]
SHOW_OPTIONS = [u"All coils", u"Prime only", u"Downgraded only", u"With defect"]


class SteelQCPage(Page):
    """Production and quality view of a steel line: tonnage, grades, causes, and the link to lab results."""

    def __init__(self, parent, app):
        Page.__init__(self, parent, app)
        self.content = tk.Frame(self, bg=BG)
        empty_state(self)
        bar = tk.Frame(self.content, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        g, self.cb_group = combo_group(bar, u"Group by", opt_labels(STEEL_GROUPS), 14, u"HR Mark")
        g.pack(side="left", padx=(0, 16))
        g, self.cb_band = combo_group(bar, u"Lab value", opt_labels(BAND_OPTIONS), 14, u"YS (MPa)")
        g.pack(side="left", padx=(0, 16))
        g, self.cb_show = combo_group(bar, u"Show", SHOW_OPTIONS, 15, SHOW_OPTIONS[0])
        g.pack(side="left", padx=(0, 16))
        g, self.cb_scope = combo_group(bar, u"Causes of", [u"Downgrades", u"All defects"], 12, u"Downgrades")
        g.pack(side="left", padx=(0, 16))
        for cb in (self.cb_group, self.cb_band, self.cb_show, self.cb_scope):
            cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.note = tk.Label(bar, text=u"", bg=BG, fg=WARN, font=FONT_SMALL)
        self.note.pack(side="right")
        self.kpi = tk.Frame(self.content, bg=BG)
        self.kpi.pack(fill="x", pady=(0, 8))
        self.insight = tk.Label(self.content, text=u"", bg=PANEL, fg=TEXT, font=FONT, anchor="w", justify="left",
                                padx=12, pady=6, highlightbackground=GRID, highlightthickness=1)
        self.insight.pack(fill="x", pady=(0, 8))
        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="both", expand=True)
        for i in (0, 1, 2):
            grid.columnconfigure(i, weight=1, uniform="c")
        for i in (0, 1):
            grid.rowconfigure(i, weight=1, uniform="r")
        self.c = [ChartCanvas(grid) for _ in range(6)]
        for i, ch in enumerate(self.c):
            ch.grid(row=i // 3, column=i % 3, sticky="nsew", padx=(0 if i % 3 == 0 else 4, 0 if i % 3 == 2 else 4),
                    pady=(0 if i < 3 else 4, 4 if i < 3 else 0))

    def refresh(self):
        app = self.app
        ds = app.dataset
        if ds is None:
            self.content.pack_forget()
            if app.role == ROLE_ADMIN:
                self.empty_btn.pack()
            self.empty.pack(fill="both", expand=True)
            return
        self.empty.pack_forget()
        if not self.content.winfo_ismapped():
            self.content.pack(fill="both", expand=True)
        recs = app.filtered
        show = self.cb_show.get()
        if show == SHOW_OPTIONS[1]:
            recs = [r for r in recs if not r["downgraded"]]
        elif show == SHOW_OPTIONS[2]:
            recs = [r for r in recs if r["downgraded"]]
        elif show == SHOW_OPTIONS[3]:
            recs = [r for r in recs if r.get("defect")]
        has_w = getattr(ds, "has_weight", False)
        m = meas(app) if has_w else "coils"
        unit = u"t" if m == "tons" else u"coils"
        dec = 1 if m == "tons" else 0
        notes = []
        if not has_w:
            notes.append(u"No weight column mapped: counting coils")
        if not getattr(ds, "prime", None):
            notes.append(u"Prime grades not set: a main defect counts as downgrade")
        self.note.configure(text=u"   |   ".join(notes))
        scope = "downgraded" if self.cb_scope.get() == u"Downgrades" else "defects"
        gk = opt_key(STEEL_GROUPS, self.cb_group.get())
        band_field = opt_key(BAND_OPTIONS, self.cb_band.get())
        n = len(recs)
        tons = ca.total(recs, "tons")
        dg = ca.downgrade_pct(recs, m)
        dg_n = sum(1 for r in recs if r["downgraded"])
        dg_t = ca.total([r for r in recs if r["downgraded"]], "tons")
        dfx = ca.defect_pct(recs, m)
        df_n = sum(1 for r in recs if r.get("defect"))
        lab = sum(1 for r in recs if r.get("has_lab"))
        cards = [(u"Production", fmt(tons, 1) if has_w else u"%d" % n,
                  (u"tons    %d coils" % n) if has_w else u"coils", ACCENT),
                 (u"Downgrade", (fmt(dg, 1) + u" %") if dg is not None else u"-",
                  (u"%.1f t downgraded" % dg_t) if has_w else u"%d coils downgraded" % dg_n, BAD),
                 (u"With defect", (fmt(dfx, 1) + u" %") if dfx is not None else u"-",
                  u"%d coils" % df_n, WARN),
                 (u"Lab coverage", (fmt(lab * 100.0 / n, 1) + u" %") if n else u"-",
                  u"%d of %d coils tested" % (lab, n), GOOD)]
        for name, f, d, u in ((u"YS avg", "ys", 1, u"MPa"), (u"UTS avg", "uts", 1, u"MPa"), (u"EL avg", "el", 1, u"%")):
            vals = analytics.values(recs, f)
            if vals:
                st = analytics.descriptive_stats(vals)
                cards.append((name, fmt(st["mean"], d), u + u"    s = " + fmt(st["std"], d), None))
        for w in self.kpi.winfo_children():
            w.destroy()
        for i, (name, val, sub, col) in enumerate(cards):
            card = tk.Frame(self.kpi, bg=PANEL, padx=14, pady=8, highlightbackground=GRID, highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Frame(card, bg=col or SERIES[(i + 1) % len(SERIES)], height=3).pack(fill="x", pady=(0, 6))
            tk.Label(card, text=name, bg=PANEL, fg=MUTED, font=FONT_SMALL).pack(anchor="w")
            tk.Label(card, text=val, bg=PANEL, fg=ACCENT, font=(FONT_FAMILY, 18, "bold")).pack(anchor="w")
            tk.Label(card, text=sub or u" ", bg=PANEL, fg=MUTED, font=FONT_SMALL).pack(anchor="w")
        # insights
        tips = []
        pc = ca.pareto(recs, "cause1", m, scope)
        named = [x for x in pc if x[0] != ca.NOT_RECORDED]
        if named:
            tot = sum(v for _, v in pc)
            tips.append(u"Top %s cause: %s (%.1f %s, %.0f%% of causes)" % (
                u"downgrade" if scope == "downgraded" else u"defect", named[0][0], named[0][1], unit,
                named[0][1] * 100.0 / tot))
        if dfx is not None and dg is not None:
            tips.append(u"Defects on %.1f%% of %s, downgraded: %.1f%%" % (dfx, unit, dg))
        rows = [r for r in ca.group_rows(recs, gk, "downgrade", m) if r[1] is not None and r[2] >= 3 and r[0] != NO]
        if len(rows) >= 2:
            worst = max(rows, key=lambda r: r[1])
            if worst[1] > 0:
                tips.append(u"Highest downgrade by %s: %s (%.1f%%)" % (self.cb_group.get().lower(), worst[0], worst[1]))
        if n and lab < n:
            tips.append(u"%d coils have no lab results" % (n - lab))
        self.insight.configure(text=(u"Insights     " + u"     |     ".join(tips[:3])) if tips
                               else u"Insights     not enough data yet")
        # charts
        mode = ca.auto_period(recs)
        labels, series = ca.period_series(recs, mode, gk, m, m, 8)
        cols = colors_for(app, gk, [s_[0] for s_ in series])
        self.c[0].show("stack", labels=labels, series=[(s_[0], s_[1], c) for s_, c in zip(series, cols)],
                       title=u"%s by %s, per %s" % (u"Tons" if m == "tons" else u"Coils", dict((x[1], x[0]) for x in PERIODS)[mode].lower(), self.cb_group.get()),
                       ylabel=unit, decimals=dec)
        r = rows_for_bar(app, recs, gk, m, 12)
        self.c[1].show("bar", labels=[x[0] for x in r], values=[x[1] for x in r], counts=[x[2] for x in r],
                       colors=colors_for(app, gk, [x[0] for x in r]), decimals=dec,
                       title=u"%s by %s" % (u"Tons" if m == "tons" else u"Coils", self.cb_group.get()), ylabel=unit)
        r = ca.sort_rows(ca.group_rows(recs, gk, "downgrade", m), 12)
        self.c[2].show("bar", labels=[x[0] for x in r], values=[x[1] for x in r], counts=[x[2] for x in r],
                       colors=colors_for(app, gk, [x[0] for x in r]), decimals=1,
                       title=u"Downgrade %% by %s" % self.cb_group.get(), ylabel=u"%")
        g = ca.sort_rows(ca.group_rows(recs, "qgrade", m, m), 8)
        self.c[3].show("donut", items=[(x[0], x[1], c) for x, c in zip(g, colors_for(app, "qgrade", [x[0] for x in g]))],
                       title=u"Quality grade mix", center=fmt(ca.total(recs, m), dec), sub=unit, decimals=dec)
        pc = pc[:10]
        self.c[4].show("pareto", labels=[x[0] for x in pc], values=[x[1] for x in pc],
                       title=(u"Downgrade causes (main)" if scope == "downgraded" else u"Defect causes (main, all grades)"),
                       ylabel=unit, decimals=dec)
        vals = analytics.values(recs, band_field)
        vl = [(analytics.mean(vals), WARN, u"mean")] if vals else []
        self.c[5].show("hist", values=vals, bins=15, vlines=vl, color=ACCENT,
                       title=u"%s distribution" % self.cb_band.get(), xlabel=self.cb_band.get())

# ================================================================ Steel: all chart types

STEEL_METRICS = [(u"Tons", "tons"), (u"Coils", "coils"), (u"Downgrade %", "downgrade"),
                 (u"Defect %", "defect")] + FIELD_OPTIONS


class SteelChartsPage(ColorChartsPage):
    """Same ten chart types as the colour line, built from the steel fields."""
    NUMS, GROUPS, METRICS = FIELD_OPTIONS, STEEL_GROUPS, STEEL_METRICS
    SPEC_PREFIX, ONE_SIDED = u"", ()
    DEFAULT_GROUP, DEFAULT_GROUP2, DEFAULT_X = u"HR Mark", u"HR Grade", 5      # X = Reduction (%)
    FALLBACK_GROUP, FALLBACK_GROUP2 = "hr_mark", "hr_grade"

    def measure(self):
        # without a weight column everything is counted in coils
        return meas(self.app) if getattr(self.app.dataset, "has_weight", False) else "coils"

    def tip(self, r):
        return u"Coil %s\nHR Mark: %s\nHR Grade: %s" % (r["coil"], r.get("hr_mark") or u"-", r.get("hr_grade") or u"-")

    def refresh(self):
        ds = self.app.dataset
        if ds is not None and not getattr(ds, "has_weight", False) and self.val("metric") == u"Tons":
            self.ctl["metric"][1].set(u"Coils")
        ColorChartsPage.refresh(self)


COLOR_PAGES = {
    "dashboard": ColorDashboardPage, "charts": ColorChartsPage, "compare": ColorComparePage,
    "stats": ColorStatsPage, "quality": ColorQualityPage, "specs": ColorSpecsPage,
    "export": ColorExportPage, "lines": LineManagerPage, "users": UserManagerPage,
}
