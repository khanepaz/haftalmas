# -*- coding: utf-8 -*-
"""CSV reading, number parsing and Jalali/Gregorian date handling.

Pure standard library. Compatible with Python 3.5+.
"""
from __future__ import print_function, unicode_literals

import csv
import datetime
import io
import re

ENCODINGS = ["utf-8-sig", "utf-8", "cp1256", "cp1252", "latin-1"]
DELIMITERS = [",", ";", "\t", "|"]

# Persian / Arabic-Indic digits and separators -> ASCII
_DIGITS = {}
for _i, _ch in enumerate(u"\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"):
    _DIGITS[ord(_ch)] = ord(u"0123456789"[_i])
for _i, _ch in enumerate(u"\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"):
    _DIGITS[ord(_ch)] = ord(u"0123456789"[_i])
_DIGITS[0x066B] = ord(u".")      # Arabic decimal separator
_DIGITS[0x066C] = None           # Arabic thousands separator
_DIGITS[0x2212] = ord(u"-")      # unicode minus

# invisible formatting characters that often hide in Persian text
_STRIP = {}
for _cp in (0x200B, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
            0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF, 0x00A0):
    _STRIP[_cp] = None


def normalize_digits(value):
    """Convert Persian/Arabic digits (and decimal marks) to ASCII."""
    if value is None:
        return u""
    return str(value).translate(_DIGITS)


_FA_FIX = {0x064A: u"\u06cc", 0x0643: u"\u06a9", 0x0649: u"\u06cc"}
_FA_FIX.update(_STRIP)


def clean_text(value):
    """Safe text for Tk: no invisible marks, no chars outside the BMP.
    Arabic yeh/kaf are converted to the Persian forms so labels group correctly."""
    if value is None:
        return u""
    s = str(value).translate(_FA_FIX)
    out = []
    for ch in s:
        o = ord(ch)
        if o > 0xFFFF:
            continue
        if o < 32 and ch != u"\t":
            continue
        out.append(ch)
    return u"".join(out).strip()


# ---------------------------------------------------------------- reading

def read_text(path):
    """Read a file trying several encodings. Returns (text, encoding)."""
    with io.open(path, "rb") as f:
        raw = f.read()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1", "replace"), "latin-1"


def detect_delimiter(text):
    lines = []
    for ln in text.splitlines():
        if ln.strip():
            lines.append(ln)
            if len(lines) >= 8:
                break
    best = u","
    best_score = (-1, -1)
    for d in DELIMITERS:
        try:
            rows = list(csv.reader(lines, delimiter=d))
        except csv.Error:
            continue
        if not rows:
            continue
        n = len(rows[0])
        if n < 2:
            continue
        consistent = sum(1 for r in rows if len(r) == n)
        score = (consistent, n)
        if score > best_score:
            best_score = score
            best = d
    return best


def read_csv(path):
    """Read a CSV file.

    Returns (headers, rows, encoding, delimiter); rows is a list of lists of
    strings. Fully blank rows are dropped.
    """
    text, enc = read_text(path)
    if text.startswith(u"\ufeff"):
        text = text[1:]
    delim = detect_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=None), delimiter=delim)
    headers = None
    rows = []
    for row in reader:
        if not any(c.strip() for c in row):
            continue
        if headers is None:
            headers = [clean_text(c) for c in row]
            continue
        rows.append(row)
    if headers is None:
        raise ValueError(u"The CSV file is empty.")
    return headers, rows, enc, delim


# ---------------------------------------------------------------- numbers

_NA = set([u"", u"nan", u"na", u"n/a", u"null", u"none", u"-", u"--", u"#n/a", u"#div/0!"])


def parse_numeric(value):
    """Parse a number from text. Returns float or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if v == v and abs(v) != float("inf") else None
    s = normalize_digits(value).translate(_STRIP).strip()
    if s.lower() in _NA:
        return None
    s = s.replace(u" ", u"")
    if u"," in s and u"." in s:
        if s.rfind(u",") > s.rfind(u"."):
            s = s.replace(u".", u"").replace(u",", u".")
        else:
            s = s.replace(u",", u"")
    elif u"," in s:
        parts = s.split(u",")
        if len(parts) == 2:
            s = parts[0] + u"." + parts[1]
        else:
            s = s.replace(u",", u"")
    s = s.rstrip(u"%")
    try:
        v = float(s)
    except ValueError:
        return None
    if v != v or abs(v) == float("inf"):
        return None
    return v


# ---------------------------------------------------------------- dates

def jalali_to_gregorian(jy, jm, jd):
    """Jalali (Persian) date -> Gregorian (gy, gm, gd)."""
    jy += 1595
    days = -355668 + (365 * jy) + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    sal_a = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm, gd


def gregorian_to_jalali(gy, gm, gd):
    """Gregorian date -> Jalali (jy, jm, jd)."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
            + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1])
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def parse_date(value):
    """Parse a Jalali or Gregorian date. Returns (gy, gm, gd) or None."""
    if value is None:
        return None
    s = normalize_digits(value).translate(_STRIP).strip()
    if not s:
        return None
    s = re.split(r"[ T]", s)[0]
    parts = re.split(r"[/\-\.]", s)
    if len(parts) != 3:
        return None
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if len(parts[0]) == 4 or nums[0] > 31:
        y, m, d = nums
    elif len(parts[2]) == 4 or nums[2] > 31:
        d, m, y = nums
    else:
        return None
    if 1200 <= y <= 1600:
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        if m > 6 and d > 30:
            return None
        try:
            gy, gm, gd = jalali_to_gregorian(y, m, d)
            datetime.date(gy, gm, gd)
        except (ValueError, IndexError):
            return None
        return gy, gm, gd
    if 1700 <= y <= 2300:
        try:
            datetime.date(y, m, d)
        except ValueError:
            return None
        return y, m, d
    return None


def normalize_date(value):
    """Return the date as Gregorian 'YYYY-MM-DD', or None if unparseable."""
    t = parse_date(value)
    if t is None:
        return None
    return u"%04d-%02d-%02d" % t


def format_jalali(greg_text):
    """'2024-01-15' -> '1402/10/25' (empty string if input is invalid)."""
    t = parse_date(greg_text)
    if t is None:
        return u""
    jy, jm, jd = gregorian_to_jalali(*t)
    return u"%04d/%02d/%02d" % (jy, jm, jd)
