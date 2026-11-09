# -*- coding: utf-8 -*-
"""Statistics, filtering, grouping and process capability (stdlib only)."""
from __future__ import print_function, unicode_literals

import math

NUMERIC_FIELDS = ["ys", "uts", "el", "thickness", "hr_thickness", "reduction"]
GROUP_FIELDS = ["grade", "hr_grade", "hr_mark"]
NO_GROUP = u"(none)"


def values(records, field):
    """All non-missing values of a numeric field."""
    out = []
    for r in records:
        v = r.get(field)
        if v is not None:
            out.append(v)
    return out


def percentile(sorted_vals, p):
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * p / 100.0
    f = int(math.floor(k))
    c = min(f + 1, n - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def mean(vals):
    return sum(vals) / float(len(vals)) if vals else None


def std(vals):
    n = len(vals)
    if n < 2:
        return 0.0 if n == 1 else None
    m = sum(vals) / float(n)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1))


def descriptive_stats(vals):
    """count, mean, std, min, max, median, q1, q3, cv (None when empty)."""
    n = len(vals)
    res = {"count": n, "mean": None, "std": None, "min": None, "max": None,
           "median": None, "q1": None, "q3": None, "cv": None}
    if n == 0:
        return res
    sv = sorted(vals)
    m = mean(vals)
    s = std(vals)
    res.update({"mean": m, "std": s, "min": sv[0], "max": sv[-1],
                "median": percentile(sv, 50), "q1": percentile(sv, 25),
                "q3": percentile(sv, 75)})
    res["cv"] = (s / m * 100.0) if (m not in (0, None) and s is not None) else None
    return res


# ---------------------------------------------------------------- filter

def filter_records(records, date_from=None, date_to=None, **equals):
    """Dates are Gregorian 'YYYY-MM-DD' strings. Empty filter = no filter.
    Any other keyword (grade=..., ral=..., supplier=...) is an equality filter."""
    wanted = [(k, v) for k, v in equals.items() if v]
    out = []
    for r in records:
        if date_from or date_to:
            d = r.get("date")
            if not d:
                continue
            if date_from and d < date_from:
                continue
            if date_to and d > date_to:
                continue
        ok = True
        for k, v in wanted:
            if r.get(k) != v:
                ok = False
                break
        if ok:
            out.append(r)
    return out


# ---------------------------------------------------------------- groups

def _natural_key(label):
    if label == NO_GROUP:
        return (2, 0.0, u"")
    try:
        return (0, float(label), u"")
    except ValueError:
        return (1, 0.0, label.lower())


def group_label(value):
    return value if value else NO_GROUP


# Quality grades are listed best first (edit the list if your grading scale differs).
# Grades that are not in the list follow in natural order.
GRADE_ORDER = ["aaa", "aa", "a", "ab", "b", "c", "z"]


def _order_key(key):
    if key in ("qgrade", "grade"):
        def k(label):
            low = label.lower()
            if low in GRADE_ORDER:
                return (-1, GRADE_ORDER.index(low), u"")
            return _natural_key(label)
        return k
    return _natural_key


def group_by(records, key):
    """[(label, [records])] sorted naturally (quality grades by GRADE_ORDER); missing -> '(none)'."""
    groups = {}
    for r in records:
        groups.setdefault(group_label(r.get(key)), []).append(r)
    return [(k, groups[k]) for k in sorted(groups, key=_order_key(key))]


def mean_by_group(records, key, field):
    """[(label, mean or None, n_valid)]."""
    out = []
    for label, recs in group_by(records, key):
        vals = values(recs, field)
        out.append((label, mean(vals), len(vals)))
    return out


def count_by(records, key):
    return [(label, len(recs)) for label, recs in group_by(records, key)]


# ---------------------------------------------------------------- others

def process_capability(vals, lsl=None, usl=None):
    """Cp / Cpk. Limits must come from the user - they are never guessed."""
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError(u"LSL must be lower than USL.")
    n = len(vals)
    res = {"n": n, "mean": None, "std": None, "cp": None, "cpk": None,
           "cpu": None, "cpl": None, "pct_out": None}
    if n == 0:
        return res
    m = mean(vals)
    s = std(vals)
    res["mean"], res["std"] = m, s
    out = 0
    for v in vals:
        if (lsl is not None and v < lsl) or (usl is not None and v > usl):
            out += 1
    if lsl is not None or usl is not None:
        res["pct_out"] = out * 100.0 / n
    if not s or s <= 0:
        return res
    ks = []
    if usl is not None:
        res["cpu"] = (usl - m) / (3.0 * s)
        ks.append(res["cpu"])
    if lsl is not None:
        res["cpl"] = (m - lsl) / (3.0 * s)
        ks.append(res["cpl"])
    if lsl is not None and usl is not None:
        res["cp"] = (usl - lsl) / (6.0 * s)
    if ks:
        res["cpk"] = min(ks)
    return res


def iqr_outliers(vals):
    """Returns (low_fence, high_fence, outlier_values)."""
    if len(vals) < 4:
        return None, None, []
    sv = sorted(vals)
    q1, q3 = percentile(sv, 25), percentile(sv, 75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return lo, hi, [v for v in vals if v < lo or v > hi]


def paired(records, fx, fy):
    xs, ys = [], []
    for r in records:
        a, b = r.get(fx), r.get(fy)
        if a is not None and b is not None:
            xs.append(a)
            ys.append(b)
    return xs, ys


def correlation(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)
