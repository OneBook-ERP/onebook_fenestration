"""Hilux series data files and the deploy entry point that loads them into a site."""

import hashlib
import json
from pathlib import Path

import frappe

from onebook_fenestration.series_studio.importer import import_snapshot_json

DATA_DIR = Path(__file__).parent
# (series code, data file, title)
HILUX_SERIES = (
	("CS400", "cs400_v2.json", "CS400 Economical Casement"),
	("CS4800", "cs4800_v1.json", "CS4800 Premium Casement"),
)


def load_series_data(filename: str) -> dict:
	"""A series data file with the Hilux glass catalogue merged in (the file's own glasses win)."""
	data = json.loads((DATA_DIR / filename).read_text())
	catalogue = json.loads((DATA_DIR / "hilux_glasses.json").read_text())["glasses"]
	glasses = {g["code"]: {k: v for k, v in g.items() if k != "code"} for g in catalogue}
	return {**data, "glasses": {**glasses, **data.get("glasses", {})}}


def data_hash(data: dict) -> str:
	return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def import_hilux_series() -> dict[str, str]:
	"""Import the Hilux series data; run with `bench --site X execute onebook_fenestration.series_studio.data.import_hilux_series`.

	Idempotent: a series whose latest submitted version carries the same data hash is skipped.
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
	return imported


def _latest_hash(series: str) -> str | None:
	return frappe.db.get_value(
		"Series Version", {"series": series, "docstatus": 1}, "source_hash", order_by="creation desc"
	)
