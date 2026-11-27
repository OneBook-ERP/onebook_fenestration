"""Normalize legacy 135-degree mitre end angles to 45 degrees across rules, snapshots, and saved designs."""

import json

import frappe

from onebook_fenestration.series_studio.snapshot import clear_snapshot


def _norm_angle(val):
	return 45 if int(val) == 135 else val


def execute():
	frappe.db.sql("update `tabSeries Member Rule` set angle_start = 45 where angle_start = 135")
	frappe.db.sql("update `tabSeries Member Rule` set angle_end = 45 where angle_end = 135")

	for row in frappe.get_all("Series Version", fields=["name", "snapshot_json"]):
		if not row.snapshot_json or "135" not in row.snapshot_json:
			continue
		data = json.loads(row.snapshot_json)
		changed = False
		for rule in data.get("member_rules") or []:
			angles = rule.get("angles")
			if isinstance(angles, list) and any(a == 135 for a in angles):
				rule["angles"] = [_norm_angle(a) for a in angles]
				changed = True
		if changed:
			frappe.db.set_value("Series Version", row.name, "snapshot_json", json.dumps(data), update_modified=False)
			clear_snapshot(row.name)

	for row in frappe.get_all("Window Design", fields=["name", "result_json"]):
		if not row.result_json or "135" not in row.result_json:
			continue
		data = json.loads(row.result_json)
		changed = False
		for member in data.get("members") or []:
			angles = member.get("angles")
			if isinstance(angles, list) and any(a == 135 for a in angles):
				member["angles"] = [_norm_angle(a) for a in angles]
				changed = True
		if changed:
			frappe.db.set_value("Window Design", row.name, "result_json", json.dumps(data), update_modified=False)

