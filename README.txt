HAFT ALMAS - Coil Analytics Platform
(formerly STEEL INSIGHT)

Portable desktop application for steel coil production and quality analysis from CSV files.
Python 3.5+, standard library + tkinter only. Charts are drawn on a Tk Canvas.

Line types
  Each line has a type, chosen once by the administrator in Line Manager:
    Steel coil  - lab results (YS / UTS / EL), thickness, HR thickness, reduction %, and in the same
                  row quality data: coil weight, quality grade, main/second downgrade cause.
                  Only the coil id is required; coils without lab results are kept.
    Color line  - tonnage (coil weight), RAL, supplier, delta E, gloss, top coat thickness,
                  T-bend, T-bend adhesion, MEK, quality grade, main/second downgrade cause
  All pages (dashboard, charts, compare, statistics, data quality, Cp/Cpk, export) are built
  from the type of the selected line. Normal users only pick a line; they cannot see paths or mappings.
  Colour line: chart colours follow the RAL colour (approximate screen colours, editable via
  "ral_colors" in config.json). A coil counts as downgraded when it has a main cause, or when its
  quality grade is not one of the "prime grades" typed in Line Manager.

Layout
  main.py                 entry point, path handling, error logging
  run.bat / HaftAlmas.vbs / run.ps1   launchers (vbs works from UNC shares)
  config.json             lines, column mapping, LSL/USL limits (absolute CSV paths)
  users.json              created on first run
  sample_data/            line1.csv (comma, Gregorian dates), line2.csv (semicolon, Jalali dates,
                          decimal commas, Persian digits)
  modules/
    profiles.py           line types, field lists, column auto-mapping
    ral.py                RAL code -> colour table
    color_analytics.py    tonnage, downgrade %, periods, pareto, heatmap data
    color_pages.py        colour-line pages, steel Production & QC and steel Charts
    calendar_widget.py    Jalali calendar for the date filters
    csv_reader.py         encoding/delimiter detection, numbers, Jalali <-> Gregorian
    data_manager.py       lines, mapping, dataset loading, reduction = (HR - final) / HR * 100
    analytics.py          statistics, filters, grouping, Cp/Cpk, IQR outliers
    charts.py             Canvas chart engine (histogram, scatter, box, trend, bar)
    auth.py               login, roles, sha256 salted passwords, last-admin protection
    dashboard.py          complete UI

Notes
  - Required fields: coil, ys, uts, el. Rows missing any of them are rejected and listed in
    Data Quality. Optional: date, thickness, hr_thickness, grade, hr_grade, hr_mark.
  - Cp/Cpk use only the LSL/USL entered by an administrator; limits are never guessed.
  - The UI contains no emoji (Tcl cannot render characters outside the BMP on Windows).
