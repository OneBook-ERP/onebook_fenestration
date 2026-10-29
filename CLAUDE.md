# onebook_fenestration

Frappe v16 app (bench also has erpnext, india_compliance, raven). Fenestration CAD, estimation, manufacturing and franchise dealer platform for Hilux System Windows. It replaces EvA WinOptimize and Orgadata Logikal.

## Read first

- `doc/context.md`: client, EvA analysis, rules reverse-engineered from sample PDFs, engine model, doctypes, ERPNext mapping, phases, open questions.
- `doc/app-map.md`: Vue SPA vs Desk split, screens, navigation, user journeys J1–J7.
- `doc/decisions.md`: decision log. D1 frontend = Vue 3 + frappe-ui. D2 engine server-side Python. D3 rules as data. D4 single SVG renderer. D5–D8 still open.

## Ground rules

- The engine (geometry, rules, weights, validation, price) is pure Python and deterministic. It must not touch the DB inside calculations; it receives a series snapshot and returns results.
- Series rules are doctype data evaluated with `frappe.safe_eval`. Never hardcode series-specific numbers in code.
- Golden tests: the engine must reproduce the EvA outputs for W01/W02/123 described in `doc/context.md`.
- `doc/*.pdf` contains customer PII. It is git-ignored; never commit it.
- Update `doc/decisions.md` whenever a decision is made or changed.
