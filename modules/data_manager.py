# -*- coding: utf-8 -*-
"""Production lines, line types, column mapping, configuration and dataset loading."""
from __future__ import print_function, unicode_literals

import io
import json
import os
import re

from . import profiles
from .csv_reader import read_csv, parse_numeric, normalize_date, clean_text
from .ral import ral_label, ral_code

# ---- steel profile constants (kept for the steel pages)
STANDARD_FIELDS = profiles.FIELDS["steel"]
REQUIRED_FIELDS = profiles.REQUIRED["steel"]
OPTIONAL_FIELDS = [f for f in STANDARD_FIELDS if f not in REQUIRED_FIELDS]
NUMERIC_RAW = ["thickness", "hr_thickness", "ys", "uts", "el"]
TEXT_FIELDS = ["coil", "grade", "hr_grade", "hr_mark"]
FIELD_LABELS = profiles.LABELS["steel"]

_NO_CAUSE = set([u"", u"-", u"--", u"0", u"none", u"no", u"n/a", u"na", u"null",
                 u"\u0646\u062f\u0627\u0631\u062f", u"\u0628\u062f\u0648\u0646 \u0639\u0644\u062a", u"\u0646\u062f\u0627\u0631\u0645"])


def guess_mapping(headers, profile="steel"):
    return profiles.guess_mapping(headers, profile)


def classify_quality(rec, grade, prime):
    """defect     = a main or second defect is recorded for the coil.
    downgraded = the quality grade is NOT one of the prime grades (a defect on a prime-grade coil
                 only marks the coil as having a defect). Without prime grades configured, a coil
                 with a main defect is counted as downgraded (old behaviour)."""
    rec["defect"] = bool(rec.get("cause1") or rec.get("cause2"))
    if prime:
        rec["downgraded"] = bool(grade) and grade.lower() not in prime
    else:
        rec["downgraded"] = bool(rec.get("cause1"))


class Dataset(object):
    """Rows of one line, converted to standard fields."""

    def __init__(self):
        self.records = []
        self.total_rows = 0
        self.rejected = 0
        self.issues = []          # (row number, severity, message)
        self.headers = []
        self.encoding = u""
        self.delimiter = u""
        self.profile = "steel"

    def add_issue(self, rowno, severity, message):
        if len(self.issues) < 1000:
            self.issues.append((rowno, severity, message))


class DataManager(object):
    def __init__(self, data_dir, root_dir=None, state_dir=None):
        self.data_dir = data_dir
        self.root_dir = root_dir
        self.config_path = os.path.join(data_dir, "config.json")
        self.state_path = os.path.join(state_dir or data_dir, "ui_state.json")
        self.state = {}
        self.config = {"lines": [], "specs": {}, "ui": {}}
        self.load_error = None
        self._cache = {}
        self.load()
        self._load_state()

    # ------------------------------------------------------------ config
    def load(self):
        if not os.path.isfile(self.config_path):
            return
        try:
            with io.open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            lines = data.get("lines", [])
            specs = data.get("specs", {})
            if not isinstance(lines, list) or not isinstance(specs, dict):
                raise ValueError("bad structure")
            self.config = {"lines": lines, "specs": specs, "ui": data.get("ui", {})}
            if data.get("ral_colors"):
                self.config["ral_colors"] = data["ral_colors"]
        except (ValueError, IOError, OSError) as e:
            self.load_error = u"config.json could not be read: %s" % e

    def save(self):
        try:
            tmp = self.config_path + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as f:
                f.write(json.dumps(self.config, indent=2, ensure_ascii=False))
            os.replace(tmp, self.config_path)
        except (IOError, OSError) as e:
            raise ValueError(u"Cannot save configuration:\n%s\n%s" % (self.config_path, e))

    # ------------------------------------------------------------ ui memory (per user, never shared)
    def _load_state(self):
        try:
            with io.open(self.state_path, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        except (ValueError, IOError, OSError):
            self.state = dict(self.config.get("ui", {}))   # migrate old versions

    def _save_state(self):
        try:
            with io.open(self.state_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(self.state, indent=2, ensure_ascii=False))
        except (IOError, OSError):
            pass

    def get_last_line(self, user):
        return self.state.get("last_line", {}).get((user or u"").lower())

    def set_last_line(self, user, name):
        if not user:
            return
        last = self.state.setdefault("last_line", {})
        if last.get(user.lower()) != name:
            last[user.lower()] = name
            self._save_state()

    def ui_flag(self, key):
        return self.config.get("ui", {}).get(key)

    def set_ui_flag(self, key, value):
        self.config.setdefault("ui", {})[key] = value
        try:
            self.save()
        except ValueError:
            pass

    # ------------------------------------------------------------ lines
    def line_names(self, profile=None):
        return [l["name"] for l in self.config["lines"]
                if profile is None or l.get("profile", "steel") == profile]

    def get_line(self, name):
        for l in self.config["lines"]:
            if l["name"] == name:
                return l
        return None

    def line_profile(self, name):
        l = self.get_line(name)
        return l.get("profile", "steel") if l else "steel"

    def _validate_line(self, name, csv_path, mapping, profile, old_name=None):
        if profile not in profiles.FIELDS:
            raise ValueError(u"Unknown line type.")
        name = (name or u"").strip()
        if not name:
            raise ValueError(u"Line name is required.")
        for l in self.config["lines"]:
            if l["name"].lower() == name.lower() and l["name"] != old_name:
                raise ValueError(u"A line named '%s' already exists." % name)
        if not csv_path or not os.path.isfile(csv_path):
            raise ValueError(u"CSV file was not found:\n%s" % csv_path)
        clean = {}
        for k, v in mapping.items():
            if k in profiles.FIELDS[profile] and v:
                clean[k] = v
        for f in profiles.REQUIRED[profile]:
            if f not in clean:
                raise ValueError(u"Column mapping is missing the required field: %s"
                                 % profiles.LABELS[profile][f])
        return name, os.path.abspath(csv_path), clean

    @staticmethod
    def _apply_options(line, options):
        options = options or {}
        line["active"] = bool(options.get("active", True))
        line["weight_unit"] = options.get("weight_unit", "kg")
        line["prime_grades"] = (options.get("prime_grades") or u"").strip()

    def add_line(self, name, csv_path, mapping, profile="steel", options=None):
        name, path, clean = self._validate_line(name, csv_path, mapping, profile)
        line = {"name": name, "profile": profile, "csv_path": path, "mapping": clean}
        self._apply_options(line, options)
        self.config["lines"].append(line)
        self.save()
        return name

    def update_line(self, old_name, name, csv_path, mapping, profile="steel", options=None):
        line = self.get_line(old_name)
        if line is None:
            raise ValueError(u"Line not found.")
        name, path, clean = self._validate_line(name, csv_path, mapping, profile, old_name)
        line["name"], line["csv_path"], line["mapping"], line["profile"] = name, path, clean, profile
        self._apply_options(line, options)
        self._cache.pop(old_name, None)
        self.save()
        return name

    def remove_line(self, name):
        line = self.get_line(name)
        if line is not None:
            self.config["lines"].remove(line)
            self._cache.pop(name, None)
            self.save()

    # ------------------------------------------------------------ specs
    def get_spec(self, field):
        s = self.config["specs"].get(field) or {}
        return s.get("lsl"), s.get("usl")

    def set_spec(self, field, lsl, usl):
        if lsl is not None and usl is not None and lsl >= usl:
            raise ValueError(u"LSL must be lower than USL.")
        if lsl is None and usl is None:
            self.config["specs"].pop(field, None)
        else:
            self.config["specs"][field] = {"lsl": lsl, "usl": usl}
        self.save()

    # ------------------------------------------------------------ data
    def resolve_path(self, path):
        if os.path.isfile(path):
            return path
        if self.root_dir:   # folder was moved: try the bundled sample folder
            alt = os.path.join(self.root_dir, "sample_data", os.path.basename(path))
            if os.path.isfile(alt):
                return alt
        return path

    def read_headers(self, path):
        headers, rows, enc, delim = read_csv(path)
        return headers

    def load_dataset(self, name):
        line = self.get_line(name)
        if line is None:
            raise ValueError(u"Line not found: %s" % name)
        path = self.resolve_path(line["csv_path"])
        if not os.path.isfile(path):
            raise ValueError(u"CSV file not found:\n%s" % line["csv_path"])
        key = (path, os.path.getmtime(path), json.dumps(line, sort_keys=True))
        cached = self._cache.get(name)
        if cached and cached[0] == key:
            return cached[1]
        if line.get("profile", "steel") == "color":
            ds = self._build_color(path, line)
        else:
            ds = self._build_steel(path, line)
        self._cache[name] = (key, ds)
        return ds

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _index_map(headers, mapping, profile):
        idx = {}
        labels = profiles.LABELS[profile]
        for field in profiles.FIELDS[profile]:
            col = mapping.get(field)
            if not col:
                continue
            if col not in headers:
                if field in profiles.REQUIRED[profile]:
                    raise ValueError(u"Mapped column '%s' (%s) was not found in the CSV header.\n"
                                     u"Open Line Manager and fix the column mapping."
                                     % (col, labels[field]))
                continue
            idx[field] = headers.index(col)
        for field in profiles.REQUIRED[profile]:
            if field not in idx:
                raise ValueError(u"Required field is not mapped: %s" % labels[field])
        return idx

    @staticmethod
    def _cell(row, idx, field):
        i = idx.get(field)
        if i is None or i >= len(row):
            return u""
        return row[i]

    # ------------------------------------------------------------ shared quality helpers
    @staticmethod
    def _prime_set(line):
        return set(clean_text(x).lower() for x in re.split(r"[,;\u060c]", line.get("prime_grades") or u"")
                   if clean_text(x))

    # ------------------------------------------------------------ steel
    def _build_steel(self, path, line):
        """Steel line: lab results (YS/UTS/EL ...) and, optionally, quality data in the same row.
        Only the coil id is required - a coil without lab results is kept."""
        mapping = line["mapping"]
        headers, rows, enc, delim = read_csv(path)
        ds = Dataset()
        ds.headers, ds.encoding, ds.delimiter, ds.profile = headers, enc, delim, "steel"
        idx = self._index_map(headers, mapping, "steel")
        cell = self._cell
        div = 1000.0 if (line.get("weight_unit") or "kg").lower() == "kg" else 1.0
        prime = self._prime_set(line)
        ds.prime, ds.weight_unit = prime, (line.get("weight_unit") or "kg").lower()
        ds.mapped = set(idx)
        if "thickness" in idx and "hr_thickness" in idx:
            ds.mapped.add("reduction")
        if "weight" in idx:
            ds.mapped.add("weight_t")
        ds.has_weight = "weight" in idx
        ds.has_lab = any(f in idx for f in ("ys", "uts", "el"))
        labels = FIELD_LABELS
        for n, row in enumerate(rows):
            rowno = n + 2
            ds.total_rows += 1
            coil = clean_text(cell(row, idx, "coil"))
            if not coil:
                ds.rejected += 1
                ds.add_issue(rowno, u"Rejected", u"Missing coil ID")
                continue
            rec = {"_row": rowno, "coil": coil}
            for f in ("ys", "uts", "el", "thickness", "hr_thickness"):
                raw = cell(row, idx, f)
                v = parse_numeric(raw)
                if v is None and clean_text(raw):
                    ds.add_issue(rowno, u"Warning", u"Invalid %s '%s' (coil %s)"
                                 % (labels[f], clean_text(raw)[:20], coil))
                rec[f] = v
            rec["has_lab"] = any(rec[f] is not None for f in ("ys", "uts", "el"))
            raw = cell(row, idx, "date")
            d = normalize_date(raw)
            if d is None and clean_text(raw):
                ds.add_issue(rowno, u"Warning", u"Unrecognized date '%s' (coil %s)"
                             % (clean_text(raw)[:24], coil))
            rec["date"] = d
            for f in ("grade", "hr_grade", "hr_mark", "qgrade"):
                t = clean_text(cell(row, idx, f))
                rec[f] = t if t else None
            for f in ("cause1", "cause2"):
                t = clean_text(cell(row, idx, f))
                rec[f] = None if t.lower() in _NO_CAUSE else t
            w = None
            if "weight" in idx:
                raw = cell(row, idx, "weight")
                wv = parse_numeric(raw)
                if wv is not None and wv > 0:
                    w = wv / div
                elif clean_text(raw):
                    ds.add_issue(rowno, u"Warning", u"Invalid coil weight '%s' (coil %s)"
                                 % (clean_text(raw)[:20], coil))
            rec["weight_t"] = w
            classify_quality(rec, rec["qgrade"], prime)
            t, h = rec["thickness"], rec["hr_thickness"]
            if t is not None and h is not None and h > 0:
                rec["reduction"] = (h - t) / h * 100.0
                if rec["reduction"] < 0:
                    ds.add_issue(rowno, u"Warning",
                                 u"Final thickness is larger than HR thickness (coil %s)" % coil)
            else:
                rec["reduction"] = None
            ds.records.append(rec)
        return ds

    # ------------------------------------------------------------ color
    def _build_color(self, path, line):
        mapping = line["mapping"]
        labels = profiles.LABELS["color"]
        headers, rows, enc, delim = read_csv(path)
        ds = Dataset()
        ds.headers, ds.encoding, ds.delimiter, ds.profile = headers, enc, delim, "color"
        idx = self._index_map(headers, mapping, "color")
        cell = self._cell
        div = 1000.0 if (line.get("weight_unit") or "kg").lower() == "kg" else 1.0
        prime = set(clean_text(x).lower() for x in re.split(r"[,;\u060c]", line.get("prime_grades") or u"")
                    if clean_text(x))
        ds.prime = prime
        ds.weight_unit = (line.get("weight_unit") or "kg").lower()
        ds.mapped = set(idx) | set(["weight_t"])
        ds.has_weight, ds.has_lab = True, True
        for n, row in enumerate(rows):
            rowno = n + 2
            ds.total_rows += 1
            coil = clean_text(cell(row, idx, "coil"))
            if not coil:
                ds.rejected += 1
                ds.add_issue(rowno, u"Rejected", u"Missing coil ID")
                continue
            w = parse_numeric(cell(row, idx, "weight"))
            if w is None or w <= 0:
                ds.rejected += 1
                ds.add_issue(rowno, u"Rejected", u"Missing or invalid coil weight (coil %s)" % coil)
                continue
            rec = {"_row": rowno, "coil": coil, "weight_t": w / div}
            for f in ("thickness", "delta_e", "gloss", "top_thickness", "bend", "bend_adhesive", "mek"):
                raw = cell(row, idx, f)
                v = parse_numeric(raw)
                if v is None and clean_text(raw):
                    ds.add_issue(rowno, u"Warning", u"Invalid %s '%s' (coil %s)"
                                 % (labels[f], clean_text(raw)[:20], coil))
                rec[f] = v
            raw = cell(row, idx, "date")
            d = normalize_date(raw)
            if d is None and clean_text(raw):
                ds.add_issue(rowno, u"Warning", u"Unrecognized date '%s' (coil %s)"
                             % (clean_text(raw)[:24], coil))
            rec["date"] = d
            raw = cell(row, idx, "ral")
            lab = ral_label(raw)
            rec["ral"] = lab if lab else None
            if lab and not ral_code(lab):
                ds.add_issue(rowno, u"Warning", u"RAL value has no 4-digit code: '%s' (colour will be generic)"
                             % lab[:24])
            for f in ("supplier", "grade"):
                t = clean_text(cell(row, idx, f))
                rec[f] = t if t else None
            for f in ("cause1", "cause2"):
                t = clean_text(cell(row, idx, f))
                rec[f] = None if t.lower() in _NO_CAUSE else t
            classify_quality(rec, rec["grade"], prime)
            ds.records.append(rec)
        return ds
