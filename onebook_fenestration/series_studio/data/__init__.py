"""Hilux series data files and the deploy entry point that loads them into a site."""

import hashlib
import json
from pathlib import Path

import frappe

from onebook_fenestration.series_studio.importer import import_snapshot_json

DATA_DIR = Path(__file__).parent
# (series code, data file, title). cs4800_v1.json stays as the record of the placeholder version; v2 is imported.
HILUX_SERIES = (
	("CS400", "cs400_v2.json", "CS400 Economical Casement"),
	("CS4800", "cs4800_v2.json", "CS4800 Premium Casement"),
)
# DXF profile perimeters for both series; profile master data, not series data, so never part of a source_hash.
PERIMETERS_FILE = "hilux_profile_perimeters.json"


def load_series_data(filename: str) -> dict:
	"""A series data file with the Hilux glass catalogue merged in (the file's own glasses win)."""
	data = json.loads((DATA_DIR / filename).read_text())
	catalogue = json.loads((DATA_DIR / "hilux_glasses.json").read_text())["glasses"]
	glasses = {g["code"]: {k: v for k, v in g.items() if k != "code"} for g in catalogue}
	return {**data, "glasses": {**glasses, **data.get("glasses", {})}}


def load_profile_perimeters() -> dict[str, dict]:
	"""{profile code: {"perimeter_mm": n}} from the Hilux DXFs."""
	return json.loads((DATA_DIR / PERIMETERS_FILE).read_text())


def fill_profile_perimeters(perimeters: dict[str, dict]) -> None:
	"""Set visible_perimeter_mm on existing Fenestration Profiles where it is empty or 0; never overwrite a value."""
	existing = frappe.get_all(
		"Fenestration Profile",
		filters={"name": ("in", list(perimeters))},
		fields=["name", "visible_perimeter_mm"],
	)
	for row in existing:
		if not row.visible_perimeter_mm:
			value = perimeters[row.name]["perimeter_mm"]
			frappe.db.set_value("Fenestration Profile", row.name, "visible_perimeter_mm", value)


def data_hash(data: dict) -> str:
	return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def import_hilux_series() -> dict[str, str]:
	"""Import the Hilux series data; run with `bench --site X execute onebook_fenestration.series_studio.data.import_hilux_series`.

	Idempotent: a series whose latest submitted version carries the same data hash is skipped. DXF perimeters then
	fill any profile whose visible perimeter is still empty.
	Returns {series code: new version name} for the series imported by this call.
	"""
	frappe.only_for(("System Manager", "Fenestration Engineer"))
	imported = {}
	for series, filename, title in HILUX_SERIES:
		data = load_series_data(filename)
		digest = data_hash(data)
		if digest == _latest_hash(series):
			continue
		imported[series] = import_snapshot_json(series, data, title, source_hash=digest)
	fill_profile_perimeters(load_profile_perimeters())
	return imported


def _latest_hash(series: str) -> str | None:
	return frappe.db.get_value(
		"Series Version", {"series": series, "docstatus": 1}, "source_hash", order_by="creation desc"
	)
