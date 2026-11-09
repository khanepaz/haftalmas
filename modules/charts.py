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


# ---------------------------------------------------------------- helpers

def _nice_num(x, rounded):
    if x <= 0:
        return 1.0
    exp = math.floor(math.log10(x))
    f = x / (10 ** exp)
    if rounded:
        nf = 1 if f < 1.5 else 2 if f < 3 else 5 if f < 7 else 10
    else:
        nf = 1 if f <= 1 else 2 if f <= 2 else 5 if f <= 5 else 10
    return nf * (10 ** exp)


def nice_ticks(lo, hi, count=5):
    """Returns (ticks, nice_lo, nice_hi)."""
    if hi == lo:
        pad = abs(lo) * 0.05 or 1.0
        lo, hi = lo - pad, hi + pad
    rng = _nice_num(hi - lo, False)
    step = _nice_num(rng / float(max(count - 1, 1)), True)
    nlo = math.floor(lo / step + 1e-9) * step
    nhi = math.ceil(hi / step - 1e-9) * step
    ticks = []
    k = 0
    while k < 60:
        v = nlo + k * step
        if v > nhi + step * 0.5:
            break
        ticks.append(round(v, 10))
        k += 1
    return ticks, ticks[0], ticks[-1]


def decimals_for(ticks):
    if len(ticks) < 2:
        return 0
    step = abs(ticks[1] - ticks[0])
    d = 0
    while d < 6 and abs(step * (10 ** d) - round(step * (10 ** d))) > 1e-7:
        d += 1
    return d


def fmt(v, d=1):
    if v is None:
        return u"-"
    return u"%.*f" % (d, v)


def _percentile(sv, p):
    n = len(sv)
    if n == 1:
        return sv[0]
    k = (n - 1) * p / 100.0
    f = int(math.floor(k))
    c = min(f + 1, n - 1)
    return sv[f] + (sv[c] - sv[f]) * (k - f)


def _lum(color):
    try:
        c = color.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    except (ValueError, IndexError, AttributeError):
        return 0.5


def edge_for(color):
    """Outline colour: very dark fills (e.g. RAL 9005) get a light edge so they stay visible."""
    return "#6b7a8c" if _lum(color) < 0.2 else color


def text_on(color):
    return "#0b1117" if _lum(color) > 0.55 else "#f1f5f9"


_RAMP = [(0.0, (30, 58, 95)), (0.45, (43, 179, 192)), (0.75, (245, 158, 11)), (1.0, (239, 68, 68))]


def ramp(t):
    t = min(max(t, 0.0), 1.0)
    for (a, ca), (b, cb) in zip(_RAMP, _RAMP[1:]):
        if t <= b:
            f = (t - a) / (b - a)
            return "#%02x%02x%02x" % tuple(int(ca[i] + (cb[i] - ca[i]) * f) for i in range(3))
    return "#ef4444"


def _short(text, n):
    text = u"%s" % text
    return text if len(text) <= n else text[:max(n - 2, 1)] + u".."


# ---------------------------------------------------------------- canvas

class ChartCanvas(tk.Canvas):
    PAD_LEFT = 58      # room for Y axis numbers
    PAD_BOTTOM = 48    # room for X axis labels
    PAD_TOP = 32       # title + Y axis name
    PAD_RIGHT = 18

    def __init__(self, master, **kw):
        kw.setdefault("bg", PANEL)
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("highlightbackground", GRID)
        kw.setdefault("width", 320)
        kw.setdefault("height", 220)
        tk.Canvas.__init__(self, master, **kw)
        self._spec = None
        self._hot = []
        self._pl = self.PAD_LEFT
        self._pr = self.PAD_RIGHT
        self._last_size = (0, 0)
        self.bind("<Configure>", self._on_resize)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self.delete("tip"))

    # -- public
    def show(self, kind, **params):
        self._spec = (kind, params)
        self._render()

    def clear(self):
        self._spec = None
        self.delete("all")

    def plot_box(self):
        """Drawing area (x0, y0, x1, y1) inside the asymmetric padding."""
        w = max(self.winfo_width(), 120)
        h = max(self.winfo_height(), 100)
        return (self._pl, self.PAD_TOP, w - self._pr, h - self.PAD_BOTTOM)

    # -- internals
    def _on_resize(self, event):
        size = (event.width, event.height)
        if size != self._last_size:
            self._last_size = size
            self._render()

    # -- hover tooltips
    def _hotspot(self, x0, y0, x1, y1, text):
        self._hot.append((x0, y0, x1, y1, text))

    def _on_motion(self, e):
        self.delete("tip")
        hit = None
        for h in reversed(self._hot):
            if h[0] == "arc":
                _, cx, cy, ri, ro, a0, a1, t = h
                dx, dy = e.x - cx, e.y - cy
                dist = math.hypot(dx, dy)
                ang = math.degrees(math.atan2(dx, -dy)) % 360.0
                if ri <= dist <= ro and a0 <= ang < a1:
                    hit = t
                    break
            elif h[0] <= e.x <= h[2] and h[1] <= e.y <= h[3]:
                hit = h[4]
                break
        if hit is None:
            return
        w = self.winfo_width()
        txt = self.create_text(e.x + 12, e.y - 10, text=hit, anchor="sw", fill=TEXT,
                               font=FONT_SMALL, justify="left", tags="tip")
        bb = self.bbox(txt)
        dx = 0
        if bb[2] + 6 > w:
            dx = -(bb[2] + 6 - w) - 24
        dy = 0
        if bb[1] - 4 < 0:
            dy = 24 - bb[1]
        self.move(txt, dx, dy)
        bb = self.bbox(txt)
        rect = self.create_rectangle(bb[0] - 5, bb[1] - 3, bb[2] + 5, bb[3] + 3,
                                     fill=PANEL2, outline=ACCENT, tags="tip")
        self.tag_raise(txt)

    def _render(self):
        self._hot = []
        self._pl, self._pr = self.PAD_LEFT, self.PAD_RIGHT
        self.delete("all")
        if self._spec is None:
            return
        kind, p = self._spec
        min_h = 20 if kind == "ribbon" else 100
        if self.winfo_width() < 120 or self.winfo_height() < min_h:
            return
        fn = getattr(self, "_draw_" + kind)
        fn(**p)

    def _empty(self, title=u""):
        w, h = self.winfo_width(), self.winfo_height()
        if title:
            self.create_text(w / 2.0, 10, text=title, fill=TEXT, font=FONT_BOLD)
        self.create_text(w / 2.0, h / 2.0, text=u"No data", fill=MUTED, font=FONT)

    def _frame(self, title, ylabel, ymin, ymax, yticks):
        """Title, Y axis name (top-left), Y grid + numbers. Returns y mapper."""
        x0, y0, x1, y1 = self.plot_box()
        w = self.winfo_width()
        if title:
            self.create_text(w / 2.0, 10, text=title, fill=TEXT, font=FONT_BOLD)
        if ylabel:
            self.create_text(x0, y0 - 11, text=ylabel, fill=MUTED, font=FONT_SMALL, anchor="w")
        d = decimals_for(yticks)
        span = float(ymax - ymin) or 1.0

        def ymap(v):
            return y1 - (v - ymin) / span * (y1 - y0)

        for t in yticks:
            y = ymap(t)
            self.create_line(x0, y, x1, y, fill=GRID)
            self.create_text(x0 - 6, y, text=fmt(t, d), fill=MUTED, font=FONT_SMALL, anchor="e")
        self.create_line(x0, y0, x0, y1, fill=MUTED)
        self.create_line(x0, y1, x1, y1, fill=MUTED)
        return ymap

    def _xaxis_numeric(self, xmin, xmax, xticks, xlabel):
        x0, y0, x1, y1 = self.plot_box()
        span = float(xmax - xmin) or 1.0

        def xmap(v):
            return x0 + (v - xmin) / span * (x1 - x0)

        d = decimals_for(xticks)
        for t in xticks:
            x = xmap(t)
            self.create_line(x, y1, x, y1 + 4, fill=MUTED)
            self.create_text(x, y1 + 6, text=fmt(t, d), fill=MUTED, font=FONT_SMALL, anchor="n")
        if xlabel:
            self.create_text((x0 + x1) / 2.0, y1 + 30, text=xlabel, fill=MUTED,
                             font=FONT_SMALL, anchor="n")
        return xmap

    def _category_labels(self, labels, xs, slot):
        """X labels (<= ~14 chars); angled when they do not fit."""
        x0, y0, x1, y1 = self.plot_box()
        n = len(labels)
        longest = max([len(u"%s" % l) for l in labels] + [1])
        longest = min(longest, 14)
        rotate = (longest * 6 + 4) > slot
        if rotate:
            texts = [_short(l, 12) for l in labels]
            skip = int(math.ceil(17.0 / max(slot, 1.0)))
        else:
            texts = [_short(l, 14) for l in labels]
            skip = 1
        for i in range(n):
            if i % skip:
                continue
            x = xs[i]
            self.create_line(x, y1, x, y1 + 4, fill=MUTED)
            if rotate:
                try:
                    self.create_text(x + 4, y1 + 7, text=texts[i], fill=MUTED, font=FONT_SMALL,
                                     anchor="ne", angle=35)
                except tk.TclError:
                    self.create_text(x, y1 + 6, text=texts[i][:6], fill=MUTED,
                                     font=FONT_SMALL, anchor="n")
            else:
                self.create_text(x, y1 + 6, text=texts[i], fill=MUTED, font=FONT_SMALL, anchor="n")

    # -- Histogram
    def _draw_hist(self, values, bins=12, title=u"", xlabel=u"", ylabel=u"Count",
                   color=ACCENT, vlines=None):
        vals = [v for v in values if v is not None]
        if not vals:
            return self._empty(title)
        lo, hi = min(vals), max(vals)
        if lo == hi:
            lo, hi = lo - 0.5, hi + 0.5
        bins = max(1, int(bins))
        counts = [0] * bins
        for v in vals:
            i = int((v - lo) / (hi - lo) * bins)
            counts[min(max(i, 0), bins - 1)] += 1
        xt, xmin, xmax = nice_ticks(lo, hi, 6)
        for vl in (vlines or []):
            xmin, xmax = min(xmin, vl[0]), max(xmax, vl[0])
        if vlines:
            xt, xmin, xmax = nice_ticks(xmin, xmax, 6)
        yt, ymin, ymax = nice_ticks(0, max(counts), 5)
        ymap = self._frame(title, ylabel, 0, ymax, yt)
        xmap = self._xaxis_numeric(xmin, xmax, xt, xlabel)
        x0, y0, x1, y1 = self.plot_box()
        bw = (hi - lo) / float(bins)
        dd = decimals_for(xt) + 1
        for i, c in enumerate(counts):
            self._hotspot(xmap(lo + i * bw), y0, xmap(lo + (i + 1) * bw), y1,
                          u"%s to %s\nCount: %d" % (fmt(lo + i * bw, dd), fmt(lo + (i + 1) * bw, dd), c))
            if c <= 0:
                continue
            a = xmap(lo + i * bw)
            b = xmap(lo + (i + 1) * bw)
            self.create_rectangle(a + 1, ymap(c), max(b - 1, a + 2), y1, fill=color, outline=color)
        for k, vl in enumerate(vlines or []):
            x = xmap(vl[0])
            col = vl[1]
            self.create_line(x, y0, x, y1, fill=col, dash=(5, 3), width=2)
            self.create_text(x + 3, y0 + 2 + 11 * (k % 3), text=vl[2], fill=col,
                             font=FONT_SMALL, anchor="nw")

    # -- Scatter
    def _draw_scatter(self, xs, ys, title=u"", xlabel=u"", ylabel=u"", color=ACCENT, fit=True,
                      tips=None, point_colors=None, legend=None):
        pts = []
        for i, (x, y) in enumerate(zip(xs, ys)):
            if x is not None and y is not None:
                pts.append((x, y, tips[i] if tips and i < len(tips) else None,
                            point_colors[i] if point_colors and i < len(point_colors) else None))
        if not pts:
            return self._empty(title)
        if len(pts) > 4000:
            shown = pts[::int(math.ceil(len(pts) / 4000.0))]
        else:
            shown = pts
        xv = [p[0] for p in pts]
        yv = [p[1] for p in pts]
        xt, xmin, xmax = nice_ticks(min(xv), max(xv), 6)
        yt, ymin, ymax = nice_ticks(min(yv), max(yv), 5)
        ymap = self._frame(title, ylabel, ymin, ymax, yt)
        xmap = self._xaxis_numeric(xmin, xmax, xt, xlabel)
        x0, y0, x1, y1 = self.plot_box()
        for x, y, tip, pc in shown:
            px, py = xmap(x), ymap(y)
            self.create_oval(px - 2.5, py - 2.5, px + 2.5, py + 2.5, fill=pc or color,
                             outline=edge_for(pc or color) if pc else BG)
            self._hotspot(px - 6, py - 6, px + 6, py + 6,
                          (tip + u"\n" if tip else u"") + u"%s: %s\n%s: %s" % (
                              xlabel or u"x", fmt(x, 2), ylabel or u"y", fmt(y, 2)))
        n = len(pts)
        if legend:
            self._legend(legend)
        if fit and n >= 3:
            mx, my = sum(xv) / n, sum(yv) / n
            sxx = sum((x - mx) ** 2 for x in xv)
            syy = sum((y - my) ** 2 for y in yv)
            if sxx > 0:
                sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
                b = sxy / sxx
                a = my - b * mx
                xa, xb = min(xv), max(xv)
                self.create_line(xmap(xa), ymap(a + b * xa), xmap(xb), ymap(a + b * xb),
                                 fill=WARN, width=2)
                if syy > 0 and not legend:
                    r = sxy / math.sqrt(sxx * syy)
                    self.create_text(x1, y0 - 11, text=u"r = %.2f   n = %d" % (r, n),
                                     fill=MUTED, font=FONT_SMALL, anchor="e")

    # -- Box plot
    def _draw_box(self, groups, title=u"", ylabel=u"", color=ACCENT, colors=None):
        groups = [(l, sorted(v for v in vs if v is not None)) for l, vs in groups]
        keep = [i for i, (l, v) in enumerate(groups) if v]
        if colors:
            colors = [colors[i] for i in keep if i < len(colors)]
        groups = [groups[i] for i in keep]
        if not groups:
            return self._empty(title)
        allv = [v for _, vs in groups for v in vs]
        yt, ymin, ymax = nice_ticks(min(allv), max(allv), 6)
        ymap = self._frame(title, ylabel, ymin, ymax, yt)
        x0, y0, x1, y1 = self.plot_box()
        n = len(groups)
        slot = (x1 - x0) / float(n)
        bw = max(6.0, min(60.0, slot * 0.5))
        xs = []
        for i, (label, sv) in enumerate(groups):
            cx = x0 + slot * (i + 0.5)
            xs.append(cx)
            col = (colors[i] if colors and i < len(colors) and colors[i] else None) or (SERIES[i % len(SERIES)] if n > 1 else color)
            q1, med, q3 = _percentile(sv, 25), _percentile(sv, 50), _percentile(sv, 75)
            iqr = q3 - q1
            lo_f, hi_f = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            wl = min([v for v in sv if v >= lo_f] or [sv[0]])
            wh = max([v for v in sv if v <= hi_f] or [sv[-1]])
            self.create_line(cx, ymap(wl), cx, ymap(q1), fill=MUTED)
            self.create_line(cx, ymap(q3), cx, ymap(wh), fill=MUTED)
            self.create_line(cx - bw / 4, ymap(wl), cx + bw / 4, ymap(wl), fill=MUTED)
            self.create_line(cx - bw / 4, ymap(wh), cx + bw / 4, ymap(wh), fill=MUTED)
            self.create_rectangle(cx - bw / 2, ymap(q3), cx + bw / 2, ymap(q1),
                                  fill=col, outline=TEXT, stipple="")
            self.create_line(cx - bw / 2, ymap(med), cx + bw / 2, ymap(med), fill=BG, width=2)
            self._hotspot(cx - slot / 2, y0, cx + slot / 2, y1,
                          u"%s  (n=%d)\nmax %s\nQ3 %s\nmedian %s\nQ1 %s\nmin %s" % (
                              label, len(sv), fmt(sv[-1], 2), fmt(q3, 2), fmt(med, 2), fmt(q1, 2), fmt(sv[0], 2)))
            for v in sv:
                if v < lo_f or v > hi_f:
                    py = ymap(v)
                    self.create_oval(cx - 2.5, py - 2.5, cx + 2.5, py + 2.5, outline=WARN)
        self._category_labels([g[0] for g in groups], xs, slot)

    # -- Line / trend
    def _draw_line(self, values, labels=None, title=u"", ylabel=u"", color=ACCENT, show_mean=True,
                   hlines=None, tick_labels=None):
        vals = [v for v in values]
        pts = [(i, v) for i, v in enumerate(vals) if v is not None]
        if not pts:
            return self._empty(title)
        yv = [p[1] for p in pts]
        yr = yv + [h[0] for h in (hlines or [])]
        yt, ymin, ymax = nice_ticks(min(yr), max(yr), 5)
        ymap = self._frame(title, ylabel, ymin, ymax, yt)
        x0, y0, x1, y1 = self.plot_box()
        n = len(vals)
        span = float(max(n - 1, 1))

        def xmap(i):
            return x0 + (i / span) * (x1 - x0) if n > 1 else (x0 + x1) / 2.0

        for hv, hc, hl in (hlines or []):
            self.create_line(x0, ymap(hv), x1, ymap(hv), fill=hc, dash=(6, 3))
            self.create_text(x1 - 2, ymap(hv) - 2, text=hl, fill=hc, font=FONT_SMALL, anchor="se")
        if show_mean:
            m = sum(yv) / len(yv)
            self.create_line(x0, ymap(m), x1, ymap(m), fill=WARN, dash=(5, 3))
            self.create_text(x1, ymap(m) - 2, text=u"mean %.1f" % m, fill=WARN,
                             font=FONT_SMALL, anchor="se")
        coords = []
        half = max((x1 - x0) / float(max(n - 1, 1)) / 2.0, 3.0)
        for i, v in pts:
            coords.extend([xmap(i), ymap(v)])
            head = (u"%s\n" % labels[i]) if labels else u"#%d\n" % (i + 1)
            if tick_labels and labels:
                head += u"%s\n" % tick_labels[i]
            self._hotspot(xmap(i) - half, y0, xmap(i) + half, y1, head + u"Value: %s" % fmt(v, 2))
        if len(pts) > 1:
            self.create_line(*coords, fill=color, width=1.5)
        if len(pts) <= 80:
            for i, v in pts:
                self.create_oval(xmap(i) - 2.5, ymap(v) - 2.5, xmap(i) + 2.5, ymap(v) + 2.5,
                                 fill=color, outline=BG)
        tl = tick_labels or labels
        if tl:
            # show only as many tick labels as fit side by side (never touching each other)
            maxlen = min(12, max(len(u"%s" % t) for t in tl))
            k = max(2, min(7, n, int((x1 - x0) / (maxlen * 6.0 + 22))))
            idxs = sorted(set(int(round(j * (n - 1) / float(max(k - 1, 1)))) for j in range(k)))
            w_ = self.winfo_width()
            for i in idxs:
                x = xmap(i)
                self.create_line(x, y1, x, y1 + 4, fill=MUTED)
                anc = "ne" if x > w_ - 36 else ("nw" if x < x0 + 14 else "n")
                self.create_text(x, y1 + 6, text=_short(tl[i], 12), fill=MUTED, font=FONT_SMALL, anchor=anc)

    # -- Bar
    def _draw_bar(self, labels, values, title=u"", ylabel=u"", zero_base=True,
                  decimals=1, counts=None, color=ACCENT, colors=None):
        valid = [v for v in values if v is not None]
        if not labels or not valid:
            return self._empty(title)
        hi, lo = max(valid), min(valid)
        if zero_base or len(valid) == 1:
            yt, ymin, ymax = nice_ticks(min(0, lo), max(0, hi), 5)
        else:
            span = (hi - lo) or abs(hi) * 0.1 or 1.0
            yt, ymin, ymax = nice_ticks(lo - span * 0.6, hi + span * 0.15, 5)
        ymap = self._frame(title, ylabel, ymin, ymax, yt)
        x0, y0, x1, y1 = self.plot_box()
        n = len(labels)
        slot = (x1 - x0) / float(n)
        bw = max(4.0, min(70.0, slot * 0.62))
        base_val = 0 if ymin <= 0 <= ymax else ymin
        xs = []
        for i, (lab, v) in enumerate(zip(labels, values)):
            cx = x0 + slot * (i + 0.5)
            xs.append(cx)
            if v is None:
                continue
            col = (colors[i] if colors and i < len(colors) and colors[i] else None) or (SERIES[i % len(SERIES)] if n > 1 else color)
            self._hotspot(cx - slot / 2, y0, cx + slot / 2, y1,
                          u"%s\nValue: %s%s" % (lab, fmt(v, decimals + 1),
                                                u"\nCoils: %d" % counts[i] if counts is not None else u""))
            top, base = ymap(v), ymap(base_val)
            self.create_rectangle(cx - bw / 2, min(top, base), cx + bw / 2, max(top, base),
                                  fill=col, outline=edge_for(col))
            if slot >= 26:
                self.create_text(cx, min(top, base) - 3, text=fmt(v, decimals), fill=TEXT,
                                 font=FONT_SMALL, anchor="s")
            if counts is not None and slot >= 40 and abs(base - top) > 16:
                self.create_text(cx, max(top, base) - 3, text=u"n=%d" % counts[i], fill=text_on(col),
                                 font=FONT_SMALL, anchor="s")
        self._category_labels(labels, xs, slot)

    # ------------------------------------------------------------ colour-line charts
    def _legend(self, items):
        x0, y0, x1, y1 = self.plot_box()
        x = x1
        y = y0 - 11
        for label, col in reversed(list(items)[:12]):
            t = _short(label, 12)
            tw = len(t) * 6 + 12
            if x - tw < x0 + 70:
                break
            x -= tw
            self.create_rectangle(x, y - 4, x + 8, y + 4, fill=col, outline=edge_for(col))
            self.create_text(x + 11, y, text=t, fill=MUTED, font=FONT_SMALL, anchor="w")
            x -= 6

    def _draw_ribbon(self, items, title=u""):
        """Full-width strip, one segment per item, width proportional to value."""
        w, h = self.winfo_width(), self.winfo_height()
        items = [(l, v, c) for l, v, c in items if v and v > 0]
        tot = float(sum(i[1] for i in items))
        if tot <= 0:
            return self._empty()
        x = 0.0
        for label, v, col in items:
            ww = w * v / tot
            self.create_rectangle(x, 0, x + ww, h, fill=col, outline=PANEL)
            if ww > 64:
                self.create_text(x + ww / 2.0, h / 2.0, text=_short(label, int(ww / 7)),
                                 fill=text_on(col), font=FONT_SMALL)
            self._hotspot(x, 0, x + ww, h, u"%s\n%s  (%.1f%%)" % (label, fmt(v, 1), v * 100.0 / tot))
            x += ww

    def _draw_stack(self, labels, series, title=u"", ylabel=u"", decimals=1, show_totals=True):
        n = len(labels)
        totals = [sum((s_[1][i] or 0) for s_ in series) for i in range(n)]
        if n == 0 or not totals or max(totals) <= 0:
            return self._empty(title)
        yt, ymin, ymax = nice_ticks(0, max(totals), 5)
        ymap = self._frame(title, ylabel, 0, ymax, yt)
        x0, y0, x1, y1 = self.plot_box()
        slot = (x1 - x0) / float(n)
        bw = max(4.0, min(64.0, slot * 0.72))
        xs = []
        for i in range(n):
            cx = x0 + slot * (i + 0.5)
            xs.append(cx)
            cum = 0.0
            parts = []
            for name, vals, col in series:
                v = vals[i] or 0
                if v <= 0:
                    continue
                self.create_rectangle(cx - bw / 2, ymap(cum + v), cx + bw / 2, ymap(cum),
                                      fill=col, outline=edge_for(col))
                cum += v
                parts.append((v, name))
            if show_totals and slot >= 30 and totals[i] > 0:
                self.create_text(cx, ymap(totals[i]) - 3, text=fmt(totals[i], decimals),
                                 fill=TEXT, font=FONT_SMALL, anchor="s")
            parts.sort(reverse=True)
            tip = u"%s\nTotal: %s" % (labels[i], fmt(totals[i], decimals))
            for v, name in parts[:8]:
                tip += u"\n%s: %s" % (_short(name, 18), fmt(v, decimals))
            self._hotspot(cx - slot / 2, y0, cx + slot / 2, y1, tip)
        self._category_labels(labels, xs, slot)
        self._legend([(s_[0], s_[2]) for s_ in series])

    def _draw_mline(self, labels, series, title=u"", ylabel=u"", decimals=1):
        allv = [v for s_ in series for v in s_[1] if v is not None]
        if not allv or not labels:
            return self._empty(title)
        yt, ymin, ymax = nice_ticks(min(allv), max(allv), 5)
        ymap = self._frame(title, ylabel, ymin, ymax, yt)
        x0, y0, x1, y1 = self.plot_box()
        n = len(labels)
        slot = (x1 - x0) / float(n)
        xs = [x0 + slot * (i + 0.5) for i in range(n)]
        for name, vals, col in series:
            pts = [(xs[i], ymap(v)) for i, v in enumerate(vals) if v is not None]
            if len(pts) > 1:
                flat = []
                for px, py in pts:
                    flat.extend([px, py])
                self.create_line(*flat, fill=col, width=2)
            for px, py in pts:
                self.create_oval(px - 3, py - 3, px + 3, py + 3, fill=col, outline=BG)
        for i in range(n):
            tip = u"%s" % labels[i]
            for name, vals, col in series:
                if vals[i] is not None:
                    tip += u"\n%s: %s" % (_short(name, 18), fmt(vals[i], decimals))
            self._hotspot(xs[i] - slot / 2, y0, xs[i] + slot / 2, y1, tip)
        self._category_labels(labels, xs, slot)
        self._legend([(s_[0], s_[2]) for s_ in series])

    def _draw_donut(self, items, title=u"", center=u"", sub=u"", decimals=1):
        items = [(l, v, c) for l, v, c in items if v and v > 0]
        total = float(sum(i[1] for i in items))
        w, h = self.winfo_width(), self.winfo_height()
        if title:
            self.create_text(w / 2.0, 10, text=title, fill=TEXT, font=FONT_BOLD)
        if total <= 0:
            return self._empty(title)
        d = max(60.0, min(h - 46.0, w * 0.46))
        cx = 16 + d / 2.0
        cy = 22 + (h - 22) / 2.0
        ro, ri = d / 2.0, d / 2.0 * 0.6
        cur = 0.0
        for label, v, col in items:
            ext = 360.0 * v / total
            self.create_arc(cx - ro, cy - ro, cx + ro, cy + ro, start=90 - cur,
                            extent=-min(ext, 359.99), style="pieslice", fill=col,
                            outline=PANEL, width=2)
            self._hot.append(("arc", cx, cy, ri, ro, cur, cur + ext,
                              u"%s\n%s  (%.1f%%)" % (label, fmt(v, decimals), v * 100.0 / total)))
            cur += ext
        self.create_oval(cx - ri, cy - ri, cx + ri, cy + ri, fill=PANEL, outline=PANEL)
        if center:
            self.create_text(cx, cy - 8, text=center, fill=TEXT, font=(FONT_FAMILY, 13, "bold"))
        if sub:
            self.create_text(cx, cy + 11, text=sub, fill=MUTED, font=FONT_SMALL)
        lx = cx + ro + 22
        rowh = 17
        for k, (label, v, col) in enumerate(items[:max(int((h - 40) / rowh), 1)]):
            y = 34 + k * rowh
            self.create_rectangle(lx, y - 5, lx + 10, y + 5, fill=col, outline=edge_for(col))
            self.create_text(lx + 15, y, text=u"%s   %.1f%%" % (_short(label, 15), v * 100.0 / total),
                             anchor="w", fill=TEXT, font=FONT_SMALL)

    def _draw_pareto(self, labels, values, title=u"", ylabel=u"", decimals=1, color=WARN):
        pairs = [(l, v) for l, v in zip(labels, values) if v and v > 0]
        if not pairs:
            return self._empty(title)
        self._pr = 46
        labels = [p[0] for p in pairs]
        values = [p[1] for p in pairs]
        tot = float(sum(values))
        yt, ymin, ymax = nice_ticks(0, max(values), 5)
        ymap = self._frame(title, ylabel, 0, ymax, yt)
        x0, y0, x1, y1 = self.plot_box()
        n = len(values)
        slot = (x1 - x0) / float(n)
        bw = max(4.0, min(56.0, slot * 0.62))
        cum = 0.0
        pts, xs = [], []
        for i, v in enumerate(values):
            cx = x0 + slot * (i + 0.5)
            xs.append(cx)
            self.create_rectangle(cx - bw / 2, ymap(v), cx + bw / 2, y1, fill=color, outline=color)
            cum += v
            pts.append((cx, y1 - cum / tot * (y1 - y0)))
            if slot >= 30:
                self.create_text(cx, ymap(v) - 3, text=fmt(v, decimals), fill=TEXT,
                                 font=FONT_SMALL, anchor="s")
            self._hotspot(cx - slot / 2, y0, cx + slot / 2, y1,
                          u"%s\n%s  (%.1f%%)\nCumulative: %.1f%%" % (
                              labels[i], fmt(v, decimals), v * 100.0 / tot, cum * 100.0 / tot))
        y80 = y1 - 0.8 * (y1 - y0)
        self.create_line(x0, y80, x1, y80, fill=GRID, dash=(4, 3))
        flat = []
        for px, py in pts:
            flat.extend([px, py])
        if len(pts) > 1:
            self.create_line(*flat, fill=ACCENT, width=2)
        for px, py in pts:
            self.create_oval(px - 3, py - 3, px + 3, py + 3, fill=ACCENT, outline=BG)
        for pct in (0, 25, 50, 75, 100):
            y = y1 - pct / 100.0 * (y1 - y0)
            self.create_text(x1 + 6, y, text=u"%d%%" % pct, fill=ACCENT, font=FONT_SMALL, anchor="w")
        self._category_labels(labels, xs, slot)

    def _draw_heat(self, rows, cols, matrix, title=u"", decimals=1, row_colors=None):
        flat = [v for r in matrix for v in r if v is not None]
        if not rows or not cols or not flat:
            return self._empty(title)
        self._pl = 100
        x0, y0, x1, y1 = self.plot_box()
        w = self.winfo_width()
        if title:
            self.create_text(w / 2.0, 10, text=title, fill=TEXT, font=FONT_BOLD)
        lo, hi = min(flat), max(flat)
        span = (hi - lo) or 1.0
        cw = (x1 - x0) / float(len(cols))
        ch = (y1 - y0) / float(len(rows))
        for ri, row in enumerate(rows):
            self.create_text(x0 - 6, y0 + ch * (ri + 0.5), text=_short(row, 15), anchor="e",
                             fill=MUTED, font=FONT_SMALL)
            if row_colors and ri < len(row_colors):
                yc = y0 + ch * (ri + 0.5)
                self.create_rectangle(6, yc - 6, 18, yc + 6, fill=row_colors[ri], outline=edge_for(row_colors[ri]))
            for ci, col in enumerate(cols):
                v = matrix[ri][ci]
                xa, ya = x0 + cw * ci, y0 + ch * ri
                if v is None:
                    self.create_rectangle(xa + 1, ya + 1, xa + cw - 1, ya + ch - 1, fill=PANEL2, outline=BG)
                    continue
                c = ramp((v - lo) / span)
                self.create_rectangle(xa + 1, ya + 1, xa + cw - 1, ya + ch - 1, fill=c, outline=BG)
                if cw >= 34 and ch >= 15:
                    self.create_text(xa + cw / 2.0, ya + ch / 2.0, text=fmt(v, decimals),
                                     fill=text_on(c), font=FONT_SMALL)
                self._hotspot(xa, ya, xa + cw, ya + ch,
                              u"%s  /  %s\n%s" % (row, col, fmt(v, decimals + 1)))
        self._category_labels(cols, [x0 + cw * (i + 0.5) for i in range(len(cols))], cw)
        gx, gy, gw = x1 - 130, y0 - 14, 90
        for k in range(gw):
            self.create_line(gx + k, gy, gx + k, gy + 8, fill=ramp(k / float(gw)))
        self.create_text(gx - 4, gy + 4, text=fmt(lo, decimals), fill=MUTED, font=FONT_SMALL, anchor="e")
        self.create_text(gx + gw + 4, gy + 4, text=fmt(hi, decimals), fill=MUTED, font=FONT_SMALL, anchor="w")
