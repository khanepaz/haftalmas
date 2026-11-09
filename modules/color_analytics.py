# -*- coding: utf-8 -*-
"""Analytics for the colour line: tonnage, downgrade share, periods, pareto, matrices."""
from __future__ import print_function, unicode_literals

import datetime

from . import analytics
from .csv_reader import format_jalali, gregorian_to_jalali

NO = analytics.NO_GROUP
ADDITIVE = ("tons", "coils")


def amount(rec, measure):
    return (rec.get("weight_t") or 0.0) if measure == "tons" else 1.0


def total(recs, measure="tons"):
    return sum(amount(r, measure) for r in recs)


def downgrade_pct(recs, measure="tons"):
    t = total(recs, measure)
    if t <= 0:
        return None
    return total([r for r in recs if r.get("downgraded")], measure) * 100.0 / t


def defect_pct(recs, measure="tons"):
    """Share of coils (or tons) that have a recorded defect, whatever their grade."""
    t = total(recs, measure)
    if t <= 0:
        return None
    return total([r for r in recs if r.get("defect")], measure) * 100.0 / t


def metric_value(recs, metric, measure="tons"):
    if metric == "tons":
        return total(recs, "tons")
    if metric == "coils":
        return float(len(recs))
    if not recs:
        return None
    if metric == "downgrade":
        return downgrade_pct(recs, measure)
    if metric == "defect":
        return defect_pct(recs, measure)
    return analytics.mean(analytics.values(recs, metric))


def group_rows(recs, key, metric, measure="tons"):
    """[(label, value, coils, tons)]"""
    return [(lab, metric_value(rs, metric, measure), len(rs), total(rs, "tons"))
            for lab, rs in analytics.group_by(recs, key)]


def sort_rows(rows, limit=None):
    """Largest value first, empty values last."""
    rows = sorted(rows, key=lambda r: (r[1] is None, -(r[1] or 0)))
    return rows[:limit] if limit else rows


def top_labels(recs, key, measure, n):
    totals = {}
    for r in recs:
        lab = analytics.group_label(r.get(key))
        totals[lab] = totals.get(lab, 0.0) + amount(r, measure)
    return [k for k, _ in sorted(totals.items(), key=lambda kv: -kv[1])][:n]


# ---------------------------------------------------------------- periods

def _week_start(d):
    return d - datetime.timedelta(days=(d.weekday() + 2) % 7)   # weeks start on Saturday


def period_of(date_text, mode):
    """Returns (sort_key, label) - labels are Jalali."""
    y, m, d = [int(x) for x in date_text.split("-")]
    if mode == "day":
        return date_text, format_jalali(date_text)
    if mode == "week":
        ws = _week_start(datetime.date(y, m, d)).isoformat()
        return ws, format_jalali(ws)
    jy, jm, jd = gregorian_to_jalali(y, m, d)
    return u"%04d%02d" % (jy, jm), u"%04d/%02d" % (jy, jm)


def period_groups(recs, mode):
    groups = {}
    for r in recs:
        if not r.get("date"):
            continue
        k, lab = period_of(r["date"], mode)
        groups.setdefault(k, (lab, []))[1].append(r)
    return [(k, groups[k][0], groups[k][1]) for k in sorted(groups)]


def auto_period(recs):
    dates = sorted(r["date"] for r in recs if r.get("date"))
    if len(dates) < 2:
        return "month"
    a = datetime.date(*[int(x) for x in dates[0].split("-")])
    b = datetime.date(*[int(x) for x in dates[-1].split("-")])
    span = (b - a).days
    return "day" if span <= 45 else ("week" if span <= 200 else "month")


def period_series(recs, mode, split_key, metric, measure, top_n=7):
    """labels, [(name, values)] - one value per period for each series."""
    periods = period_groups(recs, mode)
    labels = [p[1] for p in periods]
    if not split_key:
        return labels, [(u"All", [metric_value(p[2], metric, measure) for p in periods])]
    tops = top_labels(recs, split_key, measure, top_n)
    series = []
    for lab in tops:
        vals = []
        for p in periods:
            sub = [r for r in p[2] if analytics.group_label(r.get(split_key)) == lab]
            vals.append(metric_value(sub, metric, measure))
        series.append((lab, vals))
    if metric in ADDITIVE:
        extra = [[r for r in p[2] if analytics.group_label(r.get(split_key)) not in tops] for p in periods]
        if any(extra):
            series.append((u"Other", [metric_value(e, metric, measure) for e in extra]))
    return labels, series


# ---------------------------------------------------------------- causes / matrix

NOT_RECORDED = u"(not recorded)"


def pareto(recs, source, measure, scope="downgraded"):
    """Causes ranked by tons (or coils).

    source: cause1 | cause2 | both
    scope : "downgraded" - only coils whose grade was downgraded (a downgraded coil without a recorded
                           main cause is listed as "(not recorded)")
            "defects"    - every coil with a recorded cause, whatever its grade
    """
    keys = ("cause1", "cause2") if source == "both" else (source,)
    sums = {}
    for r in recs:
        if scope == "downgraded" and not r.get("downgraded"):
            continue
        found = False
        for k in keys:
            c = r.get(k)
            if c:
                sums[c] = sums.get(c, 0.0) + amount(r, measure)
                found = True
        if scope == "downgraded" and not found and source != "cause2":
            sums[NOT_RECORDED] = sums.get(NOT_RECORDED, 0.0) + amount(r, measure)
    return sorted(sums.items(), key=lambda kv: -kv[1])


def matrix(recs, row_key, col_key, metric, measure, max_rows=12, max_cols=8):
    rows = top_labels(recs, row_key, measure, max_rows)
    cols = top_labels(recs, col_key, measure, max_cols)
    out = []
    for rl in rows:
        line = []
        for cl in cols:
            sub = [r for r in recs if analytics.group_label(r.get(row_key)) == rl
                   and analytics.group_label(r.get(col_key)) == cl]
            line.append(metric_value(sub, metric, measure) if sub else None)
        out.append(line)
    return rows, cols, out
