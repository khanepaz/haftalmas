# -*- coding: utf-8 -*-
"""Line types (profiles): which fields a line has and how columns are guessed."""
from __future__ import print_function, unicode_literals

import re

PROFILE_TITLES = {"steel": u"Steel coil", "color": u"Color line"}
PROFILE_ORDER = ["steel", "color"]

FIELDS = {
    "steel": ["coil", "date", "thickness", "hr_thickness", "ys", "uts", "el",
              "grade", "hr_grade", "hr_mark", "weight", "qgrade", "cause1", "cause2"],
    "color": ["date", "coil", "thickness", "ral", "delta_e", "gloss", "supplier",
              "top_thickness", "bend", "bend_adhesive", "mek", "grade", "weight",
              "cause1", "cause2"],
}
REQUIRED = {"steel": ["coil"], "color": ["coil", "weight"]}

LABELS = {
    "steel": {
        "coil": u"Coil ID", "date": u"Date", "thickness": u"Final Thickness",
        "hr_thickness": u"HR Thickness", "ys": u"Yield Strength (YS)",
        "uts": u"Tensile Strength (UTS)", "el": u"Elongation (EL)",
        "grade": u"Product Grade", "hr_grade": u"HR Grade", "hr_mark": u"HR Mark",
        "reduction": u"Reduction %", "weight": u"Coil weight", "qgrade": u"Quality grade",
        "cause1": u"Main downgrade cause", "cause2": u"Second downgrade cause", "weight_t": u"Weight (t)",
    },
    "color": {
        "date": u"Date", "coil": u"Coil ID", "thickness": u"Thickness (mm)",
        "ral": u"RAL color", "delta_e": u"Color difference (\u0394E)", "gloss": u"Gloss (GU)",
        "supplier": u"Top coat supplier", "top_thickness": u"Top coat thickness (\u00b5m)",
        "bend": u"T-bend test", "bend_adhesive": u"T-bend adhesion test", "mek": u"MEK (rubs)",
        "grade": u"Quality grade", "weight": u"Coil weight", "cause1": u"Main downgrade cause",
        "cause2": u"Second downgrade cause", "weight_t": u"Weight (t)",
    },
}

FILTERS = {
    "steel": [("grade", u"Grade"), ("hr_grade", u"HR Grade"), ("hr_mark", u"Mark")],
    "color": [("ral", u"RAL"), ("supplier", u"Supplier"), ("grade", u"Grade")],
}

# order matters: more specific fields are matched before generic ones
GUESS_ORDER = {
    "steel": ["coil", "date", "hr_thickness", "thickness", "ys", "uts", "el",
              "cause1", "cause2", "qgrade", "weight", "hr_grade", "hr_mark", "grade"],
    "color": ["coil", "date", "delta_e", "top_thickness", "thickness", "ral", "supplier",
              "bend_adhesive", "bend", "mek", "gloss", "cause1", "cause2", "grade", "weight"],
}

ALIASES = {
    "steel": {
        "coil": ["coilid", "coil", "coilno", "coilnumber", "coilnum", "serial", u"\u06a9\u0648\u06cc\u0644",
                 u"\u0634\u0645\u0627\u0631\u0647 \u06a9\u0648\u06cc\u0644"],
        "date": ["proddate", "productiondate", "date", "datetime", u"\u062a\u0627\u0631\u06cc\u062e"],
        "hr_thickness": ["hrthickness", "hotrollthickness", "hrthk", "hrthick", "hotrolledthickness",
                         "entrythickness", "inthickness", "hrgauge"],
        "thickness": ["finalthickness", "thickness", "thk", "thick", "finalthk", "outthickness",
                      "exitthickness", "gauge", u"\u0636\u062e\u0627\u0645\u062a"],
        "ys": ["yieldstrength", "ys", "yield", "ysmpa", "yp", "rp02", "reh"],
        "uts": ["tensilestrength", "uts", "tensile", "utsmpa", "rm"],
        "el": ["elongation", "el", "elong", "elongpct", "elongationpct", "elongationpercent", "a80"],
        "hr_grade": ["hotrollgrade", "hrgrade", "hotrolledgrade", "hrsteelgrade", u"\u06af\u0631\u06cc\u062f \u0647\u0627\u062a \u0631\u0648\u0644"],
        "hr_mark": ["hotrollmark", "hrmark", "hotrolledmark", "mark", "hrcode", "hrbrand",
                    u"\u0645\u0627\u0631\u06a9 \u0647\u0627\u062a \u0631\u0648\u0644", u"\u0645\u0627\u0631\u06a9"],
        "grade": ["productgrade", "grade", "finalgrade", "steelgrade", "crgrade"],
        "weight": ["weight", "coilweight", "tonnage", "kg", "ton", u"\u0648\u0632\u0646",
                   u"\u0648\u0632\u0646 \u06a9\u0648\u06cc\u0644"],
        "qgrade": ["qualitygrade", "qgrade", "quality", u"\u062f\u0631\u062c\u0647 \u06a9\u06cc\u0641\u06cc",
                   u"\u062f\u0631\u062c\u0647"],
        "cause1": ["cause1", "maincause", "primarycause", "firstcause", u"\u0639\u0644\u062a \u0627\u0635\u0644\u06cc",
                   u"\u0639\u0644\u062a \u0627\u0635\u0644\u06cc \u0627\u0641\u062a \u06af\u0631\u06cc\u062f"],
        "cause2": ["cause2", "secondcause", "secondarycause", u"\u0639\u0644\u062a \u062f\u0648\u0645",
                   u"\u0639\u0644\u062a \u062f\u0648\u0645 \u0627\u0641\u062a \u06af\u0631\u06cc\u062f"],
    },
    "color": {
        "coil": ["coilid", "coil", "coilno", "coilnumber", "coilnum", "serial",
                 u"\u0634\u0645\u0627\u0631\u0647 \u06a9\u0648\u06cc\u0644", u"\u06a9\u0648\u06cc\u0644"],
        "date": ["date", "proddate", "productiondate", u"\u062a\u0627\u0631\u06cc\u062e"],
        "delta_e": ["deltae", "de", "colordiff", "colourdiff", "colordifference", "colourdifference",
                    u"\u0627\u062e\u062a\u0644\u0627\u0641 \u0641\u0627\u0645",
                    u"\u0627\u062e\u062a\u0644\u0627\u0641 \u0631\u0646\u06af", u"\u0641\u0627\u0645"],
        "top_thickness": ["topthickness", "topcoatthickness", "dft", "dryfilm",
                          u"\u0636\u062e\u0627\u0645\u062a \u0644\u0627\u06cc\u0647 \u062a\u0627\u067e",
                          u"\u0636\u062e\u0627\u0645\u062a \u062a\u0627\u067e", u"\u0636\u062e\u0627\u0645\u062a \u0644\u0627\u06cc\u0647"],
        "thickness": ["thickness", "thk", "thick", "finalthickness", u"\u0636\u062e\u0627\u0645\u062a"],
        "ral": ["ral", "ralcolor", "ralcode", "color", "colour", u"\u0631\u0627\u0644",
                u"\u0631\u0627\u0644 \u0631\u0646\u06af", u"\u0631\u0646\u06af"],
        "supplier": ["supplier", "topcoatsupplier", "paintsupplier", "vendor",
                     u"\u062a\u0627\u0645\u06cc\u0646 \u06a9\u0646\u0646\u062f\u0647",
                     u"\u062a\u0627\u0645\u06cc\u0646 \u06a9\u0646\u0646\u062f\u0647 \u0631\u0646\u06af \u062a\u0627\u067e \u06a9\u0648\u062a",
                     u"\u062a\u0627\u0645\u06cc\u0646"],
        "bend_adhesive": ["bendadhesive", "bendadhesion", "adhesivebend", "adhesionbend", "tbendadhesion",
                          u"\u062a\u0633\u062a \u062e\u0645\u0634 \u0686\u0633\u0628", u"\u062e\u0645\u0634 \u0686\u0633\u0628"],
        "bend": ["bend", "tbend", "bendtest", u"\u062a\u0633\u062a \u062e\u0645\u0634", u"\u062e\u0645\u0634"],
        "mek": ["mek", "mekrubs", "mektest"],
        "gloss": ["gloss", "gu", u"\u0628\u0631\u0627\u0642\u06cc\u062a"],
        "cause1": ["cause1", "maincause", "primarycause", "firstcause", u"\u0639\u0644\u062a \u0627\u0635\u0644\u06cc",
                   u"\u0639\u0644\u062a \u0627\u0635\u0644\u06cc \u0627\u0641\u062a \u06af\u0631\u06cc\u062f"],
        "cause2": ["cause2", "secondcause", "secondarycause", u"\u0639\u0644\u062a \u062f\u0648\u0645",
                   u"\u0639\u0644\u062a \u062f\u0648\u0645 \u0627\u0641\u062a \u06af\u0631\u06cc\u062f"],
        "grade": ["qualitygrade", "grade", "quality", u"\u062f\u0631\u062c\u0647 \u06a9\u06cc\u0641\u06cc", u"\u062f\u0631\u062c\u0647"],
        "weight": ["weight", "coilweight", "tonnage", "kg", "ton", u"\u0648\u0632\u0646",
                   u"\u0648\u0632\u0646 \u06a9\u0648\u06cc\u0644"],
    },
}

_FA_FIX = {ord(u"\u064a"): u"\u06cc", ord(u"\u0643"): u"\u06a9", ord(u"\u0623"): u"\u0627",
           ord(u"\u0625"): u"\u0627", ord(u"\u0629"): u"\u0647", ord(u"\u0649"): u"\u06cc"}


def norm_header(text):
    t = (text or u"").translate(_FA_FIX).lower()
    return re.sub(r"[\W_]+", u"", t, flags=re.UNICODE)


def guess_mapping(headers, profile="steel"):
    """Guess {field: column} from header names for the given line type."""
    used = set()
    mapping = {}
    norm = [(h, norm_header(h)) for h in headers]
    for field in GUESS_ORDER[profile]:
        aliases = [norm_header(a) for a in ALIASES[profile][field]]
        found = None
        for h, n in norm:
            if h not in used and n in aliases:
                found = h
                break
        if found is None:
            for h, n in norm:
                if h in used:
                    continue
                if any(len(a) >= 5 and a in n for a in aliases):
                    found = h
                    break
        if found is not None:
            mapping[field] = found
            used.add(found)
    return mapping


def match_score(headers, profile):
    m = guess_mapping(headers, profile)
    return sum(2 if f in REQUIRED[profile] else 1 for f in m)


def guess_profile(headers):
    best, best_score = "steel", -1
    for p in PROFILE_ORDER:
        sc = match_score(headers, p)
        if sc > best_score:
            best, best_score = p, sc
    return best
