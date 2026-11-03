# Final fix pass, Plan 2b

Status: DONE (all six items).

1. Limiter / Fly mesh are Selects (Series default / Yes / No); No writes false, Yes true, default removes the key. The effective default appears in the label ("Series default (Yes)") from `series.defaults`, returned by compute_design. Engine already tests explicit false over a default of 1 (test_design_value_overrides_opposite_series_default), so no engine change.
2. Glass picker limited to `series.glasses` (compute_design response, `series_info()` in api/design.py; stored in designer store `seriesInfo`, cleared on reset). Unknown current value labelled "{code} (not in this series version)". Before the first compute the full list shows. get_design was not changed (compute runs on load).
3. check_quotable refuses "{ref} (missing glazing gasket for glass A, B)" from the stored result_json (result_json added to DESIGN_FIELDS).
4. `series_studio/data/__init__.py` has `import_hilux_series()` (merges hilux_glasses.json into cs400_v2/cs4800_v1, requires System Manager / Fenestration Engineer). Choice: new Series Version field `source_hash` (Data, read_only, SHA-256 of merged data); skip when latest submitted version has the same hash. Doc line added to D10 in doc/decisions.md. Migrated dev site.
5. Projects.vue version picker: newest first by creation, "(latest)" per series.
6. CS4800-V03 had no Window Design or Fenestration Project references; cancelled. CS4800 published_version stays V06.

Tests: engine 123 OK; backend 193 OK; vitest 182 OK; yarn build OK.
Notes: failing-first was observed for the series import test and the vitest specs; backend api/quotation tests were written before the implementation but I did not run them separately red. Existing dev versions have no source_hash, so the first import_hilux_series run on dev will create one new version per series.
