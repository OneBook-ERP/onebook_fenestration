"""Normalize legacy 135-degree mitre end angles to 45 degrees across rules, snapshots, and saved designs."""

import json

import frappe

from onebook_fenestration.series_studio.snapshot import clear_snapshot


def _norm_angle(val):
	try:
		return 45 if int(val) == 135 else val
	except (TypeError, ValueError):
		return val


def execute():
	frappe.db.sql("update `tabSeries Member Rule` set angle_start = 45 where angle_start = 135")
	frappe.db.sql("update `tabSeries Member Rule` set angle_end = 45 where angle_end = 135")

	for row in frappe.get_all(
		"Series Version",
		filters={"snapshot_json": ("like", "%135%")},
		fields=["name", "snapshot_json"],
	):
		try:
			data = json.loads(row.snapshot_json)
		except (TypeError, ValueError):
			continue
		changed = False
		for rule in data.get("member_rules") or []:
			angles = rule.get("angles")
			if isinstance(angles, list) and any(a == 135 for a in angles):
				rule["angles"] = [_norm_angle(a) for a in angles]
				changed = True
		if changed:
			frappe.db.set_value("Series Version", row.name, "snapshot_json", json.dumps(data), update_modified=False)
			clear_snapshot(row.name)

	for row in frappe.get_all(
		"Window Design",
		filters={"result_json": ("like", "%135%")},
		fields=["name", "result_json"],
	):
		try:
			data = json.loads(row.result_json)
		except (TypeError, ValueError):
			continue
		changed = False
		for member in data.get("members") or []:
			angles = member.get("angles")
			if isinstance(angles, list) and any(a == 135 for a in angles):
				member["angles"] = [_norm_angle(a) for a in angles]
				changed = True
		if changed:
			frappe.db.set_value("Window Design", row.name, "result_json", json.dumps(data), update_modified=False)

