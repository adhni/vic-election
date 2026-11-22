# NYC precinct dots

Open `app/nyc-precinct-dots.html` locally. Every dot represents one mapped
precinct reporting area in the selected mayoral general election. There are
5,720 areas in 2017, 5,697 in 2021 and 4,102 in 2025. These include areas without
votes; unmapped zero-ballot source records are outside this mapped view.
Jointly reported precincts remain a single area, following the existing source
extracts. Boundaries differ by election; this page does not infer a cross-year
precinct correspondence.

The two sides are Bill de Blasio versus Nicole Malliotakis (2017), Eric Adams
versus Curtis Sliwa (2021), and Zohran Mamdani versus **Andrew Cuomo + Curtis
Sliwa** (2025). The latter combination was explicitly requested for this
comparison. Cuomo's Fight and Deliver votes are not reclassified as Republican
ballot-line votes. Fusion ballot lines are already combined by candidate in
the source extracts. Original candidate counts remain visible in details.

Democratic-side share = Democratic nominee votes divided by the sum of the
two selected sides. Other candidates and write-ins are excluded from this
percentage and reported separately. Shading uses this share for each precinct:
50% is grey, 75% or more is dark blue, 25% or less is dark red, with linear
interpolation. Exact ties have an explicit tie label. Zero two-side denominators
are grey in a separate group.

The 2, 3, 4, 5 and 7 group options reuse the county page's political-band
thresholds, applied to the selected election alone. These are descriptive bands,
not a statistical cluster fitted across elections. The 2025 labels identify
Mamdani and Cuomo + Sliwa explicitly. Groups, boroughs and text search filter
the dots and linked map. The URL preserves election, group count, filters and
selection. Keyboard arrows navigate visible dots and map areas.

Rebuild using `.venv/bin/python scripts/build_nyc_precinct_dots.py`.
Check all source counts and arithmetic plus browser behavior using
`.venv/bin/python scripts/test_nyc_precinct_dots.py`.

Sources and limitations: [2025](nyc_mayor_2025.md),
[2017 and 2021](nyc_mayor_history.md).

[Cross-year boundary audit](nyc_precinct_overlap_audit.md): explains why the
current files cannot provide an exact local three-election crosswalk.

[Reference-map comparison](nyc_reference_map_comparison.md): comparing all six
directions favours 2021 for a future estimated three-election view.
