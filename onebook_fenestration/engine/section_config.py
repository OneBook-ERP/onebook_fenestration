"""Series-level Auto Section Configuration schema, normalization, and lookup helpers.

Pure Python (no DB access) so both the engine and Series Studio APIs share the exact same rules.
A Profile Series stores `section_config_json` containing per-(opening_type, application) presets:
- opening_type: "fixed" | "openable" | "sliding"
- application:  "window" | "door"

Each preset configures:
1. `frame`: default frame profile + groove coordinates for frame gasket, bead seat, and glass pocket.
2. `sash`: default sash profile (+ sliding interlock/tracks) + groove coordinates for rebate gasket,
   glazing gasket, bead seat, glass pocket, and sash-to-frame seating offsets.
3. `bead_gasket_rules`: ordered rules matching `(glass_t, host)` to automatically choose bead profile,
   glazing side (`inside` / `outside`), groove seat, orientation, and inner/outer gasket items.
"""

from __future__ import annotations

import json
import math
from typing import Any

OPENING_TYPES = ("fixed", "openable", "sliding")
APPLICATIONS = ("window", "door")
PRESET_KEYS = tuple(f"{ot}:{app}" for ot in OPENING_TYPES for app in APPLICATIONS)
TEMPLATE_KEYS = (
	"fixed_window",
	"fixed_door",
	"fixed_window_mullion",
	"fixed_door_mullion",
	"openable_window",
	"openable_door",
	"openable_window_mullion",
	"openable_door_mullion",
	"sliding_window",
	"sliding_door",
)
VALID_SIDES = ("inside", "outside")
VALID_HOSTS = ("frame", "sash", "both")
VALID_PROFILE_TYPES = ("both", "window", "door")
VALID_ROTATIONS = (0, 90, 180, 270)
VALID_GLASS_DOMAIN_ALIGNS = ("center", "top", "bottom")
SUPPORTED_PRODUCT_OPTIONS = ("Window", "Door", "Sliding Window", "Sliding Door")
_PRODUCT_ALIAS_MAP = {
	"window": "Window",
	"windows": "Window",
	"door": "Door",
	"doors": "Door",
	"sliding window": "Sliding Window",
	"sliding windows": "Sliding Window",
	"sliding_window": "Sliding Window",
	"sliding door": "Sliding Door",
	"sliding doors": "Sliding Door",
	"sliding_door": "Sliding Door",
}


def normalize_supported_products(raw: Any) -> list[str]:
	"""Normalize Profile Series `supported_products` (JSON list, Python list, or CSV) into canonical options."""
	if not raw:
		return []
	items: list[Any]
	if isinstance(raw, str):
		text = raw.strip()
		if not text:
			return []
		if text.startswith("["):
			try:
				parsed = json.loads(text)
				items = parsed if isinstance(parsed, list) else []
			except ValueError:
				items = [p.strip() for p in text.split(",")]
		else:
			items = [p.strip() for p in text.split(",")]
	elif isinstance(raw, (list, tuple, set)):
		items = list(raw)
	else:
		return []

	seen: set[str] = set()
	for entry in items:
		canon = _PRODUCT_ALIAS_MAP.get(str(entry or "").strip().lower())
		if canon:
			seen.add(canon)
	return [opt for opt in SUPPORTED_PRODUCT_OPTIONS if opt in seen]


def template_keys_for_products(products: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
	"""Return the Section Template keys applicable to `products` (all templates if empty)."""
	norm = normalize_supported_products(products)
	if not norm:
		return TEMPLATE_KEYS
	allowed: list[str] = []
	if "Window" in norm:
		allowed.extend(("fixed_window", "fixed_window_mullion", "openable_window", "openable_window_mullion"))
	if "Door" in norm:
		allowed.extend(("fixed_door", "fixed_door_mullion", "openable_door", "openable_door_mullion"))
	if "Sliding Window" in norm:
		allowed.append("sliding_window")
	if "Sliding Door" in norm:
		allowed.append("sliding_door")
	return tuple(k for k in TEMPLATE_KEYS if k in allowed)


def _num(value: Any, default: float = 0.0) -> float:
	try:
		v = float(value)
		return v if math.isfinite(v) else default
	except TypeError, ValueError:
		return default


def _int_rot(value: Any) -> int:
	try:
		v = float(value)
		if not math.isfinite(v):
			return 0
		r = (((int(v)) % 360) + 360) % 360
	except TypeError, ValueError, OverflowError:
		return 0
	return r if r in VALID_ROTATIONS else 0


def _bool(value: Any) -> bool:
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		return bool(int(value))
	return str(value or "").strip().lower() in ("1", "true", "yes")


def _side(value: Any, default: str = "inside") -> str:
	s = str(value or "").strip().lower()
	return s if s in VALID_SIDES else default


def _host(value: Any, default: str = "both") -> str:
	h = str(value or "").strip().lower()
	return h if h in VALID_HOSTS else default


def _str(value: Any) -> str:
	return str(value or "").strip()


def _normalize_anchor_point(raw: Any) -> dict:
	d = raw if isinstance(raw, dict) else {}
	x = round(_num(d.get("x"), 0.0), 2)
	y = round(_num(d.get("y"), 0.0), 2)
	w = max(0.0, round(_num(d.get("w"), 0.0), 2))
	h = max(0.0, round(_num(d.get("h"), 0.0), 2))
	return {
		"x": x,
		"y": y,
		"w": w,
		"h": h,
		"configured": bool(d.get("configured")) or (x != 0.0 or y != 0.0 or w > 0.0 or h > 0.0),
	}


def normalize_profile_anchors(raw: Any) -> dict:
	"""Parse and normalize `section_anchors_json` stored on a Fenestration Profile."""
	if isinstance(raw, str):
		raw = raw.strip()
		if not raw:
			raw = {}
		else:
			try:
				raw = json.loads(raw)
			except ValueError:
				raw = {}
	d = raw if isinstance(raw, dict) else {}
	return {
		"bead_groove_seat": _normalize_anchor_point(d.get("bead_groove_seat")),
		"bead_glass_face": _normalize_anchor_point(d.get("bead_glass_face")),
		"bead_side": _side(d.get("bead_side"), "inside"),
		"gasket_groove_root": _normalize_anchor_point(d.get("gasket_groove_root")),
		"gasket_seal_tip": _normalize_anchor_point(d.get("gasket_seal_tip")),
		"frame_gasket_groove": _normalize_anchor_point(d.get("frame_gasket_groove")),
		"frame_bead_groove": _normalize_anchor_point(d.get("frame_bead_groove")),
		"frame_glass_pocket": _normalize_anchor_point(d.get("frame_glass_pocket")),
		"sash_rebate_gasket_groove": _normalize_anchor_point(d.get("sash_rebate_gasket_groove")),
		"sash_glazing_gasket_groove": _normalize_anchor_point(d.get("sash_glazing_gasket_groove")),
		"sash_bead_groove": _normalize_anchor_point(d.get("sash_bead_groove")),
		"sash_glass_pocket": _normalize_anchor_point(d.get("sash_glass_pocket")),
	}


def normalize_glass_glazing_rules(raw: Any) -> list[dict]:
	"""Parse and normalize `glazing_rules_json` stored on a Fenestration Glass."""
	if isinstance(raw, str):
		raw = raw.strip()
		if not raw:
			return []
		try:
			raw = json.loads(raw)
		except ValueError:
			return []
	if not isinstance(raw, list):
		return []
	out: list[dict] = []
	for item in raw:
		if not isinstance(item, dict):
			continue
		series = _str(item.get("series"))
		if not series:
			continue
		out.append(
			{
				"series": series,
				"host": _host(item.get("host"), "both"),
				"bead_profile": _str(item.get("bead_profile")),
				"bead_side": _side(item.get("bead_side"), "inside"),
				"inner_gasket_item": _str(item.get("inner_gasket_item")),
				"inner_gasket_name": _str(item.get("inner_gasket_name")),
				"outer_gasket_item": _str(item.get("outer_gasket_item")),
				"outer_gasket_name": _str(item.get("outer_gasket_name")),
			}
		)
	return out


def match_glass_glazing_rule(glazing_rules: Any, series_code: str, host: str) -> dict | None:
	"""Return the matching bead/gasket rule on a Fenestration Glass for `(series_code, host)`."""
	if not glazing_rules or not series_code:
		return None
	series_l = series_code.strip().lower()
	host_l = host.strip().lower()
	for rule in glazing_rules:
		if not isinstance(rule, dict):
			continue
		if _str(rule.get("series")).lower() != series_l:
			continue
		r_host = _host(rule.get("host"), "both")
		if r_host != "both" and r_host != host_l:
			continue
		return rule
	return None


def _profile_type(value: Any, default: str = "both") -> str:
	p = str(value or "").strip().lower()
	return p if p in VALID_PROFILE_TYPES else default


def normalize_global_glazing_rules(raw: Any) -> list[dict]:
	"""Parse and normalize series-independent global Bead & Gasket rules keyed by glass thickness range."""
	if isinstance(raw, str):
		raw = raw.strip()
		if not raw:
			return []
		try:
			raw = json.loads(raw)
		except ValueError:
			return []
	if not isinstance(raw, list):
		return []
	out: list[dict] = []
	for idx, item in enumerate(raw):
		if not isinstance(item, dict):
			continue
		min_g = max(0.0, round(_num(item.get("min_glass_mm"), 0.0), 2))
		max_g = max(min_g, round(_num(item.get("max_glass_mm"), max(min_g, 6.0)), 2))
		bead_prof = _str(item.get("bead_profile"))
		no_bead = _bool(item.get("no_bead")) or not bool(bead_prof)
		out.append(
			{
				"id": _str(item.get("id")) or f"global_rule_{idx + 1}",
				"label": _str(item.get("label")),
				"profile_type": _profile_type(item.get("profile_type"), "both"),
				"min_glass_mm": min_g,
				"max_glass_mm": max_g,
				"host": _host(item.get("host"), "frame"),
				"bead_profile": "" if no_bead else bead_prof,
				"no_bead": no_bead,
				"bead_side": _side(item.get("bead_side"), "inside"),
				"inner_gasket_hardware": _str(item.get("inner_gasket_hardware")),
				"inner_gasket_item": _str(item.get("inner_gasket_item")),
				"inner_gasket_name": _str(item.get("inner_gasket_name")),
				"outer_gasket_hardware": _str(item.get("outer_gasket_hardware")),
				"outer_gasket_item": _str(item.get("outer_gasket_item")),
				"outer_gasket_name": _str(item.get("outer_gasket_name")),
			}
		)
	return out


def match_global_glazing_rule(
	global_rules: Any,
	glass_t: float,
	host: str = "both",
	application: str = "both",
) -> dict | None:
	"""Return the most specific global Bead & Gasket rule matching `(glass_t, host, application)`.

	Specificity priority:
	1. Exact `(profile_type == application, host == host)`
	2. Shared `profile_type == 'both'` with exact `host`
	3. Shared `host == 'both'` fallback
	"""
	if not global_rules or glass_t <= 0:
		return None
	host_l = (host or "both").strip().lower()
	app_l = (application or "both").strip().lower()
	best_rule: dict | None = None
	best_score = -1
	for rule in global_rules:
		if not isinstance(rule, dict):
			continue
		r_host = _host(rule.get("host"), "both")
		if r_host != "both" and host_l != "both" and r_host != host_l:
			continue
		r_type = _profile_type(rule.get("profile_type"), "both")
		if r_type != "both" and app_l != "both" and r_type != app_l:
			continue
		min_g = _num(rule.get("min_glass_mm"), 0.0)
		max_g = _num(rule.get("max_glass_mm"), 999.0)
		if not (min_g - 1e-6 <= glass_t <= max_g + 1e-6):
			continue
		type_score = 2 if (app_l != "both" and r_type == app_l) else 1
		host_score = 2 if (host_l != "both" and r_host == host_l) else 1
		score = type_score * 10 + host_score
		if score > best_score:
			best_score = score
			best_rule = rule
	return best_rule


DEFAULT_MAX_GASKET_COMPRESSION_MM = 1.0
DEFAULT_LOOSE_TOLERANCE_MM = 0.05


def default_glazing_auto_config() -> dict:
	"""Default configuration for width-driven Bead & Gasket selection (BW - GT = R)."""
	return {
		"enabled": True,
		"max_compression_mm": DEFAULT_MAX_GASKET_COMPRESSION_MM,
		"loose_tolerance_mm": DEFAULT_LOOSE_TOLERANCE_MM,
		"thicker_gasket_side": "outer",
		"gasket_pool": [],
		"channels": [],
	}


def normalize_glazing_auto_config(raw: Any) -> dict:
	"""Parse and normalize auto Bead & Gasket width configuration (`BW - GT = R`)."""
	base = default_glazing_auto_config()
	if isinstance(raw, str):
		raw = raw.strip()
		if not raw:
			return base
		try:
			raw = json.loads(raw)
		except ValueError:
			return base
	if not isinstance(raw, dict):
		return base

	thicker = str(raw.get("thicker_gasket_side") or "outer").strip().lower()
	if thicker not in ("outer", "inner"):
		thicker = "outer"

	pool_raw = raw.get("gasket_pool")
	gasket_pool: list[str] = []
	if isinstance(pool_raw, (list, tuple)):
		seen_pool: set[str] = set()
		for entry in pool_raw:
			code = _str(entry)
			if code and code not in seen_pool:
				seen_pool.add(code)
				gasket_pool.append(code)

	channels_raw = raw.get("channels")
	channels: list[dict] = []
	if isinstance(channels_raw, list):
		for idx, ch in enumerate(channels_raw):
			if not isinstance(ch, dict):
				continue
			bw = round(max(0.0, _num(ch.get("bead_width_mm"), 0.0)), 2)
			bead_prof = _str(ch.get("bead_profile"))
			no_bead = _bool(ch.get("no_bead")) or not bool(bead_prof)
			channels.append(
				{
					"id": _str(ch.get("id")) or f"glazing_ch_{idx + 1}",
					"series": _str(ch.get("series")),
					"label": _str(ch.get("label")),
					"profile_type": _profile_type(ch.get("profile_type"), "both"),
					"host": _host(ch.get("host"), "frame"),
					"bead_profile": "" if no_bead else bead_prof,
					"no_bead": no_bead,
					"bead_width_mm": bw,
					"bead_side": _side(ch.get("bead_side"), "inside"),
				}
			)

	return {
		"enabled": _bool(raw.get("enabled")) if "enabled" in raw else True,
		"max_compression_mm": round(
			max(0.0, _num(raw.get("max_compression_mm"), DEFAULT_MAX_GASKET_COMPRESSION_MM)), 2
		),
		"loose_tolerance_mm": round(
			max(0.0, _num(raw.get("loose_tolerance_mm"), DEFAULT_LOOSE_TOLERANCE_MM)), 3
		),
		"thicker_gasket_side": thicker,
		"gasket_pool": gasket_pool,
		"channels": channels,
	}


def _normalize_gasket_catalog(gaskets: Any, gasket_pool: list[str] | None = None) -> list[dict]:
	"""Return active gaskets with positive thickness_mm, sorted by thickness ascending."""
	if not gaskets:
		return []
	allowed = {str(c).strip().lower() for c in (gasket_pool or []) if str(c).strip()}
	out: list[dict] = []
	for g in gaskets:
		if not isinstance(g, dict):
			continue
		thk = round(_num(g.get("thickness_mm"), 0.0), 3)
		if thk <= 0:
			continue
		code = _str(g.get("hardware_code") or g.get("code") or g.get("name"))
		item = _str(g.get("item") or code)
		name = _str(g.get("hardware_name") or g.get("name") or code)
		if allowed and code.lower() not in allowed and item.lower() not in allowed:
			continue
		out.append({"code": code, "item": item or code, "name": name or code, "thickness_mm": thk})
	out.sort(key=lambda x: (x["thickness_mm"], x["code"]))
	return out


def _matching_auto_channels(
	channels: list[dict],
	series: str = "",
	host: str = "frame",
	application: str = "window",
) -> list[dict]:
	"""Filter auto-width channels by (series, host, application), enforcing no-bead on window sashes."""
	host_l = (host or "frame").strip().lower()
	app_l = (application or "window").strip().lower()
	series_l = (series or "").strip().lower()
	window_sash = host_l == "sash" and app_l == "window"

	def _matches(ch: dict, want_series: str) -> bool:
		if _num(ch.get("bead_width_mm"), 0.0) <= 0:
			return False
		c_series = _str(ch.get("series")).lower()
		if c_series != want_series:
			return False
		c_host = _host(ch.get("host"), "both")
		if c_host != "both" and host_l != "both" and c_host != host_l:
			return False
		c_type = _profile_type(ch.get("profile_type"), "both")
		if c_type != "both" and app_l != "both" and c_type != app_l:
			return False
		if window_sash and not _bool(ch.get("no_bead")):
			return False
		return True

	matched = [ch for ch in channels if series_l and _matches(ch, series_l)]
	if not matched:
		matched = [ch for ch in channels if _matches(ch, "")]

	# Sort by BW ascending; on equal BW prefer exact profile_type/host match and beaded before no_bead.
	def _sort_key(ch: dict) -> tuple:
		c_type = _profile_type(ch.get("profile_type"), "both")
		c_host = _host(ch.get("host"), "both")
		type_rank = 0 if (app_l != "both" and c_type == app_l) else 1
		host_rank = 0 if (host_l != "both" and c_host == host_l) else 1
		no_bead_rank = 1 if _bool(ch.get("no_bead")) else 0
		return (round(_num(ch.get("bead_width_mm"), 0.0), 4), no_bead_rank, type_rank, host_rank)

	matched.sort(key=_sort_key)
	return matched


def _best_gasket_pair(
	bw: float,
	glass_t: float,
	gaskets: list[dict],
	max_compression_mm: float = DEFAULT_MAX_GASKET_COMPRESSION_MM,
	loose_tolerance_mm: float = DEFAULT_LOOSE_TOLERANCE_MM,
	thicker_side: str = "outer",
) -> dict | None:
	"""Pick the best (outer, inner) gasket pair satisfying:
	- Not loose: (GT + g_outer + g_inner) >= BW - loose_tolerance_mm
	- Not over-compressed: (GT + g_outer + g_inner) - BW <= max_compression_mm (default 1.0 mm)
	- Thicker gasket goes on `thicker_side` ('outer' by default).
	"""
	if glass_t <= 0 or bw <= 0 or glass_t >= bw - 1e-6 or not gaskets:
		return None

	remaining = bw - glass_t
	best: tuple[tuple, dict] | None = None
	for i in range(len(gaskets)):
		for j in range(i, len(gaskets)):
			g_thin = gaskets[i]
			g_thick = gaskets[j]
			total_g = g_thick["thickness_mm"] + g_thin["thickness_mm"]
			compression = (glass_t + total_g) - bw
			if compression < -(loose_tolerance_mm + 1e-6):
				continue
			if compression > max_compression_mm + 1e-6:
				continue
			is_exact = 0 if abs(compression) <= loose_tolerance_mm + 1e-6 else 1
			over_comp = round(max(0.0, compression), 4)
			spread = round(g_thick["thickness_mm"] - g_thin["thickness_mm"], 4)
			score = (is_exact, over_comp, spread, round(abs(compression), 4))
			if best is None or score < best[0]:
				if thicker_side == "inner":
					inner_g, outer_g = g_thick, g_thin
				else:
					outer_g, inner_g = g_thick, g_thin
				best = (
					score,
					{
						"inner": inner_g,
						"outer": outer_g,
						"remaining_mm": round(remaining, 2),
						"compression_mm": round(compression, 2),
						"total_gasket_mm": round(total_g, 2),
					},
				)
	return best[1] if best else None


def resolve_glazing_by_width(
	auto_config: Any,
	gasket_catalog: Any,
	glass_t: float,
	series: str = "",
	host: str = "frame",
	application: str = "window",
) -> dict | None:
	"""Resolve bead/pocket + (outer, inner) gaskets using BW - GT = R.

	Returns:
	- None when auto width resolution is disabled or no channels apply to `(series, host, application)`.
	- A normalized rule dict (`ok=True`, `source='auto_width'`) when a channel & gasket pair fit.
	- A diagnostic dict (`ok=False`, `reason=...`) when channels exist for this context but `glass_t`
	  cannot fit any configured bead/pocket width within `max_compression_mm`.
	"""
	if glass_t <= 0 or not auto_config:
		return None
	cfg = normalize_glazing_auto_config(auto_config)
	if not cfg["enabled"] or not cfg["channels"]:
		return None

	candidates = _matching_auto_channels(cfg["channels"], series=series, host=host, application=application)
	if not candidates:
		return None

	gaskets = _normalize_gasket_catalog(gasket_catalog, cfg["gasket_pool"])
	if not gaskets:
		return {
			"ok": False,
			"source": "auto_width",
			"reason": "no_gaskets",
			"message": "No gaskets with thickness_mm > 0 are configured for automatic bead & gasket resolution.",
			"glass_t": round(glass_t, 2),
			"candidate_widths": [ch["bead_width_mm"] for ch in candidates],
		}

	max_comp = cfg["max_compression_mm"]
	loose_tol = cfg["loose_tolerance_mm"]
	thicker_side = cfg["thicker_gasket_side"]

	for ch in candidates:
		bw = ch["bead_width_mm"]
		if glass_t >= bw - 1e-6:
			continue
		pair = _best_gasket_pair(
			bw=bw,
			glass_t=glass_t,
			gaskets=gaskets,
			max_compression_mm=max_comp,
			loose_tolerance_mm=loose_tol,
			thicker_side=thicker_side,
		)
		if pair is None:
			continue
		no_bead = bool(ch["no_bead"]) or not bool(ch["bead_profile"])
		return {
			"ok": True,
			"source": "auto_width",
			"id": ch["id"],
			"label": ch["label"] or (f"No Bead ({bw} mm)" if no_bead else f"{ch['bead_profile']} ({bw} mm)"),
			"series": ch["series"],
			"profile_type": ch["profile_type"],
			"host": ch["host"],
			"bead_profile": "" if no_bead else ch["bead_profile"],
			"no_bead": no_bead,
			"bead_side": ch["bead_side"],
			"bead_width_mm": bw,
			"remaining_mm": pair["remaining_mm"],
			"compression_mm": pair["compression_mm"],
			"total_gasket_mm": pair["total_gasket_mm"],
			"inner_gasket_hardware": pair["inner"]["code"],
			"inner_gasket_item": pair["inner"]["item"],
			"inner_gasket_name": pair["inner"]["name"],
			"inner_gasket_mm": pair["inner"]["thickness_mm"],
			"outer_gasket_hardware": pair["outer"]["code"],
			"outer_gasket_item": pair["outer"]["item"],
			"outer_gasket_name": pair["outer"]["name"],
			"outer_gasket_mm": pair["outer"]["thickness_mm"],
		}

	max_bw = max(ch["bead_width_mm"] for ch in candidates)
	widths_str = ", ".join(f"{ch['bead_width_mm']:g} mm" for ch in candidates)
	if glass_t >= max_bw - 1e-6:
		reason = "exceeds_max_bw"
		msg = f"Glass thickness {glass_t:g} mm exceeds maximum configured bead/pocket width ({max_bw:g} mm)."
	else:
		reason = "no_gasket_combo"
		msg = (
			f"Glass thickness {glass_t:g} mm has no valid gasket pair (within {max_comp:g} mm compression) "
			f"for configured widths [{widths_str}]."
		)
	return {
		"ok": False,
		"source": "auto_width",
		"reason": reason,
		"message": msg,
		"glass_t": round(glass_t, 2),
		"candidate_widths": [ch["bead_width_mm"] for ch in candidates],
	}


def _normalize_gasket_slot(raw: Any, default_side: str = "outside") -> dict:
	d = raw if isinstance(raw, dict) else {}
	x = round(_num(d.get("x"), 0.0), 2)
	y = round(_num(d.get("y"), 0.0), 2)
	w = max(0.0, round(_num(d.get("w"), 0.0), 2))
	h = max(0.0, round(_num(d.get("h"), 0.0), 2))
	return {
		"x": x,
		"y": y,
		"w": w,
		"h": h,
		"side": _side(d.get("side"), default_side),
		"gasket_item": _str(d.get("gasket_item")),
		"gasket_name": _str(d.get("gasket_name")),
		"thickness_mm": max(0.0, round(_num(d.get("thickness_mm"), 3.0), 2)),
		"configured": bool(d.get("configured"))
		or bool(_str(d.get("gasket_item")))
		or (x != 0.0 or y != 0.0 or w > 0.0 or h > 0.0),
	}


def _normalize_bead_slot(raw: Any, default_side: str = "inside") -> dict:
	d = raw if isinstance(raw, dict) else {}
	x = round(_num(d.get("x"), 0.0), 2)
	y = round(_num(d.get("y"), 0.0), 2)
	w = max(0.0, round(_num(d.get("w"), 0.0), 2))
	h = max(0.0, round(_num(d.get("h"), 0.0), 2))
	return {
		"x": x,
		"y": y,
		"w": w,
		"h": h,
		"side": _side(d.get("side"), default_side),
		"rotation": _int_rot(d.get("rotation")),
		"flip_x": _bool(d.get("flip_x")),
		"flip_y": _bool(d.get("flip_y")),
		"configured": bool(d.get("configured")) or (x != 0.0 or y != 0.0 or w > 0.0 or h > 0.0),
	}


def _normalize_glass_slot(raw: Any) -> dict:
	d = raw if isinstance(raw, dict) else {}
	x = round(_num(d.get("x"), 0.0), 2)
	y = round(_num(d.get("y"), 0.0), 2)
	w = max(0.0, round(_num(d.get("w"), 0.0), 2))
	h = max(0.0, round(_num(d.get("h"), 0.0), 2))
	return {
		"x": x,
		"y": y,
		"w": w,
		"h": h,
		"rebate_depth_mm": max(0.0, round(_num(d.get("rebate_depth_mm"), 12.0), 2)),
		"clearance_mm": max(0.0, round(_num(d.get("clearance_mm"), 4.0), 2)),
		"configured": bool(d.get("configured")) or (x != 0.0 or y != 0.0 or w > 0.0 or h > 0.0),
	}


def _normalize_rule(raw: Any, index: int) -> dict | None:
	if not isinstance(raw, dict):
		return None
	min_g = max(0.0, round(_num(raw.get("min_glass_mm"), 0.0), 2))
	max_g = max(min_g, round(_num(raw.get("max_glass_mm"), max(min_g, 24.0)), 2))
	return {
		"id": _str(raw.get("id")) or f"rule_{index + 1}",
		"min_glass_mm": min_g,
		"max_glass_mm": max_g,
		"host": _host(raw.get("host"), "both"),
		"bead_profile": _str(raw.get("bead_profile")),
		"bead_side": _side(raw.get("bead_side"), "inside"),
		"bead_groove": _str(raw.get("bead_groove")) or "bead_slot",
		"bead_offset_along": round(_num(raw.get("bead_offset_along"), 0.0), 2),
		"bead_offset_depth": round(_num(raw.get("bead_offset_depth"), 0.0), 2),
		"bead_rotation": _int_rot(raw.get("bead_rotation")),
		"bead_flip_x": _bool(raw.get("bead_flip_x")),
		"bead_flip_y": _bool(raw.get("bead_flip_y")),
		"inner_gasket_item": _str(raw.get("inner_gasket_item")),
		"inner_gasket_name": _str(raw.get("inner_gasket_name")),
		"outer_gasket_item": _str(raw.get("outer_gasket_item")),
		"outer_gasket_name": _str(raw.get("outer_gasket_name")),
		"gasket_groove": _str(raw.get("gasket_groove")) or "gasket_slot",
	}


def default_preset() -> dict:
	return {
		"frame": {
			"profile": "",
			"gasket_slot": _normalize_gasket_slot(None, "outside"),
			"bead_slot": _normalize_bead_slot(None, "inside"),
			"glass_slot": _normalize_glass_slot(None),
		},
		"sash": {
			"profile": "",
			"rebate_gasket_slot": _normalize_gasket_slot(None, "outside"),
			"glazing_gasket_slot": _normalize_gasket_slot(None, "outside"),
			"bead_slot": _normalize_bead_slot(None, "inside"),
			"glass_slot": _normalize_glass_slot(None),
			"seat_offset_along": 0.0,
			"seat_offset_depth": 0.0,
			"interlock_profile": "",
			"track_count": 2,
		},
		"bead_gasket_rules": [],
	}


def normalize_preset(raw: Any) -> dict:
	d = raw if isinstance(raw, dict) else {}
	frame_raw = d.get("frame") if isinstance(d.get("frame"), dict) else {}
	sash_raw = d.get("sash") if isinstance(d.get("sash"), dict) else {}
	rules_raw = d.get("bead_gasket_rules") if isinstance(d.get("bead_gasket_rules"), list) else []
	rules = [r for idx, item in enumerate(rules_raw) if (r := _normalize_rule(item, idx)) is not None]
	track_count = int(_num(sash_raw.get("track_count"), 2))
	if track_count not in (2, 3):
		track_count = 2
	return {
		"frame": {
			"profile": _str(frame_raw.get("profile")),
			"gasket_slot": _normalize_gasket_slot(frame_raw.get("gasket_slot"), "outside"),
			"bead_slot": _normalize_bead_slot(frame_raw.get("bead_slot"), "inside"),
			"glass_slot": _normalize_glass_slot(frame_raw.get("glass_slot")),
		},
		"sash": {
			"profile": _str(sash_raw.get("profile")),
			"rebate_gasket_slot": _normalize_gasket_slot(sash_raw.get("rebate_gasket_slot"), "outside"),
			"glazing_gasket_slot": _normalize_gasket_slot(sash_raw.get("glazing_gasket_slot"), "outside"),
			"bead_slot": _normalize_bead_slot(sash_raw.get("bead_slot"), "inside"),
			"glass_slot": _normalize_glass_slot(sash_raw.get("glass_slot")),
			"seat_offset_along": round(_num(sash_raw.get("seat_offset_along"), 0.0), 2),
			"seat_offset_depth": round(_num(sash_raw.get("seat_offset_depth"), 0.0), 2),
			"interlock_profile": _str(sash_raw.get("interlock_profile")),
			"track_count": track_count,
		},
		"bead_gasket_rules": rules,
	}


def _normalize_piece_transform(raw: Any) -> dict:
	d = raw if isinstance(raw, dict) else {}
	out: dict[str, Any] = {
		"offsetAlong": round(_num(d.get("offsetAlong"), 0.0), 2),
		"offsetDepth": round(_num(d.get("offsetDepth"), 0.0), 2),
		"rotation": _int_rot(d.get("rotation")),
		"flipX": _bool(d.get("flipX")),
		"flipY": _bool(d.get("flipY")),
	}
	if d.get("originU") is not None:
		out["originU"] = round(_num(d.get("originU"), 0.0), 2)
	if d.get("originDepth") is not None:
		out["originDepth"] = round(_num(d.get("originDepth"), 0.0), 2)
	return out


def _normalize_transform_map(raw: Any) -> dict[str, dict]:
	if not isinstance(raw, dict):
		return {}
	out: dict[str, dict] = {}
	for key, val in raw.items():
		k = _str(key)
		if k and isinstance(val, dict):
			out[k] = _normalize_piece_transform(val)
	return out


def _normalize_raycast_domain(raw: Any) -> dict | None:
	if not isinstance(raw, dict) or not _bool(raw.get("enabled")):
		return None
	p_min = round(_num(raw.get("pocketMinY"), 0.0), 2)
	p_max = round(_num(raw.get("pocketMaxY"), 0.0), 2)
	if p_max < p_min:
		p_min, p_max = p_max, p_min
	if p_max - p_min < 1.0:
		return None
	p_low = round(_num(raw.get("pocketInsetLow"), 0.0), 2)
	p_high = round(_num(raw.get("pocketInsetHigh"), p_low), 2)
	raw_mul = raw.get("pocketInsetMullion")
	p_mul = round(_num(raw_mul, 0.0), 2) if raw_mul is not None and str(raw_mul).strip() != "" else None
	probe_off = max(0.5, round(_num(raw.get("probeOffsetFromLow"), 4.0), 2))
	return {
		"enabled": True,
		"pocketMinY": p_min,
		"pocketMaxY": p_max,
		"pocketInsetLow": p_low,
		"pocketInsetHigh": p_high,
		"pocketInsetMullion": p_mul,
		"probeOffsetFromLow": probe_off,
	}


def _normalize_glass_domain(raw: Any) -> dict:
	d = raw if isinstance(raw, dict) else {}
	min_y = round(_num(d.get("minY"), 0.0), 2)
	max_y = round(_num(d.get("maxY"), 0.0), 2)
	if max_y < min_y:
		min_y, max_y = max_y, min_y
	inset_low = round(_num(d.get("insetLow"), 0.0), 2)
	inset_high = round(_num(d.get("insetHigh"), inset_low), 2)
	raw_mullion = d.get("insetMullion")
	inset_mullion = (
		round(_num(raw_mullion, 0.0), 2)
		if raw_mullion is not None and str(raw_mullion).strip() != ""
		else None
	)
	align = str(d.get("align") or "center").strip().lower()
	if align not in VALID_GLASS_DOMAIN_ALIGNS:
		align = "center"
	configured = bool(d.get("configured")) and (max_y - min_y >= 1.0)
	out: dict[str, Any] = {
		"configured": configured,
		"minY": min_y,
		"maxY": max_y,
		"insetLow": inset_low,
		"insetHigh": inset_high,
		"insetMullion": inset_mullion,
		"align": align,
	}
	raycast = _normalize_raycast_domain(d.get("raycast"))
	if raycast:
		out["raycast"] = raycast
	return out


def _normalize_template_axis(raw: Any) -> dict:
	d = raw if isinstance(raw, dict) else {}
	return {
		"sectionMap": _normalize_transform_map(d.get("sectionMap")),
		"roleTransforms": _normalize_transform_map(d.get("roleTransforms")),
		"beadByCode": _normalize_transform_map(d.get("beadByCode")),
		"glassDomain": _normalize_glass_domain(d.get("glassDomain")),
	}


def default_template() -> dict:
	return {
		"configured": False,
		"glass": "",
		"profiles": {},
		"axis_h": _normalize_template_axis(None),
		"axis_v": _normalize_template_axis(None),
	}


def normalize_template(raw: Any) -> dict:
	d = raw if isinstance(raw, dict) else {}
	axis_h = _normalize_template_axis(d.get("axis_h"))
	axis_v = _normalize_template_axis(d.get("axis_v"))
	raw_profiles = d.get("profiles") if isinstance(d.get("profiles"), dict) else {}
	profiles = {_str(k): _str(v) for k, v in raw_profiles.items() if _str(k) and _str(v)}
	has_data = bool(
		axis_h["roleTransforms"]
		or axis_h["beadByCode"]
		or axis_h["sectionMap"]
		or axis_h["glassDomain"]["configured"]
		or axis_v["roleTransforms"]
		or axis_v["beadByCode"]
		or axis_v["sectionMap"]
		or axis_v["glassDomain"]["configured"]
	)
	return {
		"configured": bool(d.get("configured")) or has_data,
		"glass": _str(d.get("glass")),
		"profiles": profiles,
		"axis_h": axis_h,
		"axis_v": axis_v,
	}


def normalize_section_config(raw: Any) -> dict:
	"""Parse and normalize a raw JSON string or dict into a complete section configuration."""
	empty = {
		"version": 1,
		"presets": {k: default_preset() for k in PRESET_KEYS},
		"templates": {k: default_template() for k in TEMPLATE_KEYS},
	}
	if isinstance(raw, str):
		raw = raw.strip()
		if not raw:
			return empty
		try:
			raw = json.loads(raw)
		except ValueError:
			return empty
	if not isinstance(raw, dict):
		return empty
	raw_presets = raw.get("presets") if isinstance(raw.get("presets"), dict) else {}
	presets = {key: normalize_preset(raw_presets.get(key)) for key in PRESET_KEYS}
	raw_templates = raw.get("templates") if isinstance(raw.get("templates"), dict) else {}
	templates = {key: normalize_template(raw_templates.get(key)) for key in TEMPLATE_KEYS}
	return {"version": 1, "presets": presets, "templates": templates}


def _candidate_template_keys(
	opening_type: str,
	application: str,
	role: str,
	has_mullion: bool,
	design_has_sash: bool,
) -> list[str]:
	app = application if application in APPLICATIONS else "window"
	other_app = "door" if app == "window" else "window"
	if opening_type == "sliding":
		keys = [f"sliding_{app}", f"sliding_{other_app}", "sliding_window", "sliding_door"]
	elif opening_type == "openable" or (design_has_sash and role in ("frame", "mullion", "transom")):
		if has_mullion:
			keys = [
				f"openable_{app}_mullion",
				f"openable_{app}",
				f"openable_{other_app}_mullion",
				f"openable_{other_app}",
				f"fixed_{app}_mullion",
				f"fixed_{app}",
				f"fixed_{other_app}_mullion",
				f"fixed_{other_app}",
			]
		else:
			keys = [
				f"openable_{app}",
				f"openable_{app}_mullion",
				f"openable_{other_app}",
				f"openable_{other_app}_mullion",
				f"fixed_{app}",
				f"fixed_{app}_mullion",
				f"fixed_{other_app}",
				f"fixed_{other_app}_mullion",
			]
	else:
		if has_mullion:
			keys = [
				f"fixed_{app}_mullion",
				f"fixed_{app}",
				f"fixed_{other_app}_mullion",
				f"fixed_{other_app}",
			]
		else:
			keys = [
				f"fixed_{app}",
				f"fixed_{app}_mullion",
				f"fixed_{other_app}",
				f"fixed_{other_app}_mullion",
			]
		if role in ("frame", "mullion", "transom"):
			keys.extend(
				[
					f"openable_{app}_mullion",
					f"openable_{app}",
					f"openable_{other_app}_mullion",
					f"openable_{other_app}",
				]
			)
	# Deduplicate while preserving priority order
	seen: set[str] = set()
	ordered: list[str] = []
	for k in keys:
		if k in TEMPLATE_KEYS and k not in seen:
			seen.add(k)
			ordered.append(k)
	return ordered


def _rank_candidate_templates(
	templates: dict[str, Any],
	candidate_keys: list[str],
	active_profiles: dict[str, str] | None,
	role: str,
) -> list[str]:
	"""Prefer templates whose saved profile codes match the cut's active profiles.

	Prevents e.g. a Door template tuned for a 92 mm door shutter (CS4804) from applying
	its large offsets onto a 78 mm window shutter (CS4803) when a window profile is given
	a door sash configuration, and ensures door frames/mullions pick the door template.
	"""
	if not active_profiles:
		return candidate_keys
	clean = {k: str(v).strip() for k, v in active_profiles.items() if v and str(v).strip()}
	if not clean:
		return candidate_keys

	owner_role = "sash" if role in ("sash", "glass", "bead", "glass_adaptor") and "sash" in clean else role
	if owner_role in ("glass", "bead", "glass_adaptor"):
		owner_role = "frame"

	def _score(idx_key: tuple[int, str]) -> tuple[int, int]:
		idx, key = idx_key
		tpl = templates.get(key)
		if not isinstance(tpl, dict) or not tpl.get("configured"):
			return (-1000, -idx)
		tpl_profiles = tpl.get("profiles") if isinstance(tpl.get("profiles"), dict) else {}
		if not tpl_profiles:
			return (0, -idx)

		score = 0
		for p_role, active_code in clean.items():
			tpl_code = str(tpl_profiles.get(p_role) or "").strip()
			if not tpl_code:
				continue
			if tpl_code == active_code:
				score += 100 if p_role == owner_role else 25
			else:
				score -= 80 if p_role == owner_role else 15
		return (score, -idx)

	ranked = sorted(enumerate(candidate_keys), key=_score, reverse=True)
	return [k for _, k in ranked]


def _lookup_axis_role_transform(axis_data: dict, role: str, code: str, adjacent: str) -> dict | None:
	if not isinstance(axis_data, dict):
		return None
	roles = axis_data.get("roleTransforms") if isinstance(axis_data.get("roleTransforms"), dict) else {}
	beads = axis_data.get("beadByCode") if isinstance(axis_data.get("beadByCode"), dict) else {}
	adj = "mullion" if adjacent in ("mullion", "transom") else ("frame" if adjacent == "frame" else "")

	if role in ("bead", "glass_adaptor"):
		if code and adj != "" and isinstance(beads.get(f"{code}:{adj}"), dict):
			return beads[f"{code}:{adj}"]
		if code and isinstance(beads.get(code), dict):
			return beads[code]
		if adj != "" and isinstance(roles.get(f"{role}_{adj}"), dict):
			return roles[f"{role}_{adj}"]
		if isinstance(roles.get(role), dict):
			return roles[role]
		if role == "glass_adaptor":
			if adj != "" and isinstance(roles.get(f"bead_{adj}"), dict):
				return roles[f"bead_{adj}"]
			if isinstance(roles.get("bead"), dict):
				return roles["bead"]
		return None

	if role == "sash":
		if adj != "" and isinstance(roles.get(f"sash_{adj}"), dict):
			return roles[f"sash_{adj}"]
		return roles.get("sash") if isinstance(roles.get("sash"), dict) else None

	if role == "transom":
		return (
			roles.get("transom")
			if isinstance(roles.get("transom"), dict)
			else (roles.get("mullion") if isinstance(roles.get("mullion"), dict) else None)
		)

	if role == "mullion":
		return (
			roles.get("mullion")
			if isinstance(roles.get("mullion"), dict)
			else (roles.get("transom") if isinstance(roles.get("transom"), dict) else None)
		)

	return roles.get(role) if isinstance(roles.get(role), dict) else None


def resolve_template_glass_domain(
	section_config: dict | None,
	opening_type: str,
	application: str,
	axis: str,
	has_mullion: bool = False,
	low_side: str = "",
	high_side: str = "",
	active_profiles: dict[str, str] | None = None,
) -> dict | None:
	"""Resolve a configured Glass Domain for a glass piece from Series Section Templates.

	Returns `{ source: 'series_section_template_glass_domain', template, axis, minY, maxY, insetLow, insetHigh, align }`
	or None if no matching template has a configured glass domain.
	"""
	if not isinstance(section_config, dict):
		return None
	templates = section_config.get("templates")
	if not isinstance(templates, dict):
		return None

	primary_axis = "axis_h" if axis == "h" else "axis_v"
	fallback_axis = "axis_v" if axis == "h" else "axis_h"

	candidates = _rank_candidate_templates(
		templates,
		_candidate_template_keys(opening_type, application, "glass", has_mullion, False),
		active_profiles,
		"glass",
	)
	for tpl_key in candidates:
		tpl = templates.get(tpl_key)
		if not isinstance(tpl, dict) or not tpl.get("configured"):
			continue
		for ax_key in (primary_axis, fallback_axis):
			ax_data = tpl.get(ax_key)
			if not isinstance(ax_data, dict):
				continue
			gd = ax_data.get("glassDomain")
			if not isinstance(gd, dict) or not gd.get("configured"):
				continue
			min_y = round(_num(gd.get("minY"), 0.0), 2)
			max_y = round(_num(gd.get("maxY"), 0.0), 2)
			if max_y - min_y < 1.0:
				continue
			inset_frame = round(_num(gd.get("insetLow"), 0.0), 2)
			inset_other = round(_num(gd.get("insetHigh"), inset_frame), 2)
			raw_mullion = gd.get("insetMullion")
			inset_mullion = (
				round(_num(raw_mullion, inset_other), 2)
				if raw_mullion is not None and str(raw_mullion).strip() != ""
				else inset_other
			)
			# Map cell side adjacency so multi-bay designs use frame inset at jambs and mullion inset at dividers
			eff_low = inset_mullion if low_side in ("mullion", "transom") else inset_frame
			eff_high = (
				inset_mullion
				if high_side in ("mullion", "transom")
				else (
					inset_frame
					if high_side == "frame" and low_side in ("mullion", "transom")
					else inset_other
				)
			)
			align = str(gd.get("align") or "center").strip().lower()
			if align not in VALID_GLASS_DOMAIN_ALIGNS:
				align = "center"
			out: dict[str, Any] = {
				"source": "series_section_template_glass_domain",
				"template": tpl_key,
				"axis": "h" if ax_key == "axis_h" else "v",
				"minY": min_y,
				"maxY": max_y,
				"insetLow": eff_low,
				"insetHigh": eff_high,
				"align": align,
			}
			raycast = _normalize_raycast_domain(gd.get("raycast"))
			if raycast:
				p_frame = raycast["pocketInsetLow"]
				p_other = raycast["pocketInsetHigh"]
				p_mul = (
					raycast["pocketInsetMullion"] if raycast["pocketInsetMullion"] is not None else p_other
				)
				eff_p_low = p_mul if low_side in ("mullion", "transom") else p_frame
				eff_p_high = (
					p_mul
					if high_side in ("mullion", "transom")
					else (p_frame if high_side == "frame" and low_side in ("mullion", "transom") else p_other)
				)
				out["raycast"] = {
					**raycast,
					"pocketInsetLow": eff_p_low,
					"pocketInsetHigh": eff_p_high,
				}
			return out
	return None


def resolve_pane_glazing_gaskets(
	snapshot: Any,
	glass_t: float,
	host: str,
	opening_type: str,
	application: str,
	glass_code: str = "",
) -> dict | None:
	"""Resolve outer & inner gasket codes and thicknesses (mm) for cross-section visualization."""
	if glass_t <= 0 or snapshot is None:
		return None
	catalog = getattr(snapshot, "gasket_catalog", ()) or ()
	thk_by_code: dict[str, float] = {}
	for g in catalog:
		if isinstance(g, dict) and _num(g.get("thickness_mm"), 0.0) > 0:
			c = _str(g.get("code"))
			it = _str(g.get("item"))
			t = round(_num(g.get("thickness_mm"), 0.0), 2)
			if c:
				thk_by_code[c.lower()] = t
			if it:
				thk_by_code[it.lower()] = t

	auto_res = resolve_glazing_by_width(
		getattr(snapshot, "global_glazing_auto", None),
		catalog,
		glass_t,
		getattr(snapshot, "code", ""),
		host,
		application,
	)
	rule = auto_res if (auto_res and auto_res.get("ok")) else None
	if not rule:
		rule = match_global_glazing_rule(
			getattr(snapshot, "global_glazing_rules", ()), glass_t, host, application
		)
	if not rule and glass_code:
		glasses = getattr(snapshot, "glasses", {}) or {}
		gspec = glasses.get(glass_code)
		if gspec is not None:
			rule = match_glass_glazing_rule(
				getattr(gspec, "glazing_rules", None), getattr(snapshot, "code", ""), host
			)
	if not rule and getattr(snapshot, "section_config", None):
		rule = match_bead_gasket_rule(snapshot.section_config, opening_type, application, glass_t, host)
	if not rule:
		return None

	outer_code = _str(rule.get("outer_gasket_hardware") or rule.get("outer_gasket_item"))
	inner_code = _str(rule.get("inner_gasket_hardware") or rule.get("inner_gasket_item"))
	if not outer_code and not inner_code:
		return None

	def _infer_mm(code: str, explicit: Any) -> float:
		val = _num(explicit, 0.0)
		if val > 0:
			return round(val, 2)
		if code and code.lower() in thk_by_code:
			return thk_by_code[code.lower()]
		return 3.0

	return {
		"outer_code": outer_code,
		"outer_name": _str(rule.get("outer_gasket_name") or outer_code),
		"outer_mm": _infer_mm(outer_code, rule.get("outer_gasket_mm")),
		"inner_code": inner_code,
		"inner_name": _str(rule.get("inner_gasket_name") or inner_code),
		"inner_mm": _infer_mm(inner_code, rule.get("inner_gasket_mm")),
		"bead_side": _side(rule.get("bead_side"), "inside"),
		"no_bead": bool(rule.get("no_bead")) or not bool(_str(rule.get("bead_profile"))),
	}


def resolve_template_placement(
	section_config: dict | None,
	opening_type: str,
	application: str,
	axis: str,
	role: str,
	code: str = "",
	mirrored: bool = False,
	has_mullion: bool = False,
	adjacent: str = "",
	design_has_sash: bool = False,
	active_profiles: dict[str, str] | None = None,
) -> dict | None:
	"""Resolve canonical profile transform from the Series Section Templates Studio.

	Glass uses `resolve_template_glass_domain` so it stays strictly inside its glazing domain.
	"""
	if role == "glass" or not isinstance(section_config, dict):
		return None
	templates = section_config.get("templates")
	if not isinstance(templates, dict):
		return None

	primary_axis = "axis_h" if axis == "h" else "axis_v"
	fallback_axis = "axis_v" if axis == "h" else "axis_h"

	candidates = _rank_candidate_templates(
		templates,
		_candidate_template_keys(opening_type, application, role, has_mullion, design_has_sash),
		active_profiles,
		role,
	)
	for tpl_key in candidates:
		tpl = templates.get(tpl_key)
		if not isinstance(tpl, dict) or not tpl.get("configured"):
			continue
		for ax_key in (primary_axis, fallback_axis):
			ax_data = tpl.get(ax_key)
			transform = _lookup_axis_role_transform(ax_data, role, code, adjacent)
			if not transform:
				continue
			beads = (
				ax_data.get("beadByCode")
				if isinstance(ax_data, dict) and isinstance(ax_data.get("beadByCode"), dict)
				else {}
			)
			adj = (
				"mullion" if adjacent in ("mullion", "transom") else ("frame" if adjacent == "frame" else "")
			)
			matched_code = bool(code and (f"{code}:{adj}" in beads or code in beads))
			along = _num(transform.get("offsetAlong"), 0.0)
			depth = _num(transform.get("offsetDepth"), 0.0)
			res: dict[str, Any] = {
				"source": "series_section_template",
				"template": tpl_key,
				"axis": "h" if ax_key == "axis_h" else "v",
				"offsetAlong": round(-along if mirrored else along, 2),
				"offsetDepth": round(depth, 2),
				"rotation": _int_rot(transform.get("rotation")),
				"flipX": _bool(transform.get("flipX")),
				"flipY": _bool(transform.get("flipY")),
				"matchedCode": matched_code,
			}
			if transform.get("originU") is not None:
				res["originU"] = round(_num(transform.get("originU"), 0.0), 2)
			if transform.get("originDepth") is not None:
				res["originDepth"] = round(_num(transform.get("originDepth"), 0.0), 2)
			return res
	return None


def detect_design_context(
	design: dict | None, cell_node: dict | None = None, is_sash_pane: bool = False
) -> tuple[str, str]:
	"""Infer `(opening_type, application)` from design & optional cell/sash node."""
	design = design if isinstance(design, dict) else {}
	node = cell_node if isinstance(cell_node, dict) else {}
	is_sliding = bool(design.get("isSliding")) or str(node.get("type") or "").lower() == "sliding"
	sash_cfg = str(node.get("sashConfig") or "").strip().lower()
	frame_cfg = str(design.get("frameConfig") or "").strip().lower()
	application = (
		"door"
		if (
			sash_cfg == "door"
			or frame_cfg
			in ("3-side", "3-side-threshold", "3sideouterframe", "3 side outer with low threshold")
		)
		else "window"
	)
	if is_sliding:
		return "sliding", application
	if is_sash_pane or str(node.get("type") or "").lower() == "sash":
		return "openable", application
	return "fixed", application


def get_preset(section_config: dict | None, opening_type: str, application: str) -> dict | None:
	if not isinstance(section_config, dict):
		return None
	presets = section_config.get("presets")
	if not isinstance(presets, dict):
		return None
	key = f"{opening_type}:{application}"
	preset = presets.get(key)
	if isinstance(preset, dict):
		return preset
	return presets.get(f"{opening_type}:window")


def match_bead_gasket_rule(
	section_config: dict | None,
	opening_type: str,
	application: str,
	glass_t: float,
	host: str,
) -> dict | None:
	"""Return the first matching `bead_gasket_rule` for `(opening_type, application, glass_t, host)`."""
	preset = get_preset(section_config, opening_type, application)
	if not preset:
		return None
	rules = preset.get("bead_gasket_rules")
	if not isinstance(rules, list):
		return None
	host_l = host.lower()
	for rule in rules:
		if not isinstance(rule, dict):
			continue
		r_host = str(rule.get("host") or "both").lower()
		if r_host != "both" and r_host != host_l:
			continue
		min_g = _num(rule.get("min_glass_mm"), 0.0)
		max_g = _num(rule.get("max_glass_mm"), 999.0)
		if min_g - 1e-6 <= glass_t <= max_g + 1e-6:
			return rule
	return None


def resolve_piece_config_placement(
	section_config: dict | None,
	opening_type: str,
	application: str,
	role: str,
	glass_t: float = 0.0,
	in_sash: bool = False,
	mirrored: bool = False,
) -> dict | None:
	"""Compute configured section placement metadata for a cut piece, or None if unconfigured."""
	preset = get_preset(section_config, opening_type, application)
	if not preset:
		return None
	frame_cfg = preset.get("frame") if isinstance(preset.get("frame"), dict) else {}
	sash_cfg = preset.get("sash") if isinstance(preset.get("sash"), dict) else {}

	if role == "frame":
		gasket = frame_cfg.get("gasket_slot") if isinstance(frame_cfg.get("gasket_slot"), dict) else {}
		bead = frame_cfg.get("bead_slot") if isinstance(frame_cfg.get("bead_slot"), dict) else {}
		glass = frame_cfg.get("glass_slot") if isinstance(frame_cfg.get("glass_slot"), dict) else {}
		if not (gasket.get("configured") or bead.get("configured") or glass.get("configured")):
			return None
		return {
			"source": "series_section_config",
			"preset": f"{opening_type}:{application}",
			"gasket_slot": gasket if gasket.get("configured") else None,
			"bead_slot": bead if bead.get("configured") else None,
			"glass_slot": glass if glass.get("configured") else None,
		}

	if role == "sash":
		rebate_g = (
			sash_cfg.get("rebate_gasket_slot") if isinstance(sash_cfg.get("rebate_gasket_slot"), dict) else {}
		)
		glazing_g = (
			sash_cfg.get("glazing_gasket_slot")
			if isinstance(sash_cfg.get("glazing_gasket_slot"), dict)
			else {}
		)
		bead = sash_cfg.get("bead_slot") if isinstance(sash_cfg.get("bead_slot"), dict) else {}
		glass = sash_cfg.get("glass_slot") if isinstance(sash_cfg.get("glass_slot"), dict) else {}
		along = _num(sash_cfg.get("seat_offset_along"), 0.0)
		depth = _num(sash_cfg.get("seat_offset_depth"), 0.0)
		has_any = (
			along != 0.0
			or depth != 0.0
			or rebate_g.get("configured")
			or glazing_g.get("configured")
			or bead.get("configured")
			or glass.get("configured")
		)
		if not has_any:
			return None
		return {
			"source": "series_section_config",
			"preset": f"{opening_type}:{application}",
			"offsetAlong": -along if mirrored else along,
			"offsetDepth": depth,
			"rebate_gasket_slot": rebate_g if rebate_g.get("configured") else None,
			"glazing_gasket_slot": glazing_g if glazing_g.get("configured") else None,
			"bead_slot": bead if bead.get("configured") else None,
			"glass_slot": glass if glass.get("configured") else None,
		}

	if role in ("bead", "glass_adaptor"):
		host = "sash" if in_sash else "frame"
		host_cfg = sash_cfg if in_sash else frame_cfg
		bead_slot = host_cfg.get("bead_slot") if isinstance(host_cfg.get("bead_slot"), dict) else {}
		rule = match_bead_gasket_rule(section_config, opening_type, application, glass_t, host)
		if not rule and not bead_slot.get("configured"):
			return None
		along = _num(rule.get("bead_offset_along"), 0.0) if rule else 0.0
		depth = _num(rule.get("bead_offset_depth"), 0.0) if rule else 0.0
		rotation = _int_rot(rule.get("bead_rotation")) if rule else _int_rot(bead_slot.get("rotation"))
		flip_x = _bool(rule.get("bead_flip_x")) if rule else _bool(bead_slot.get("flip_x"))
		flip_y = _bool(rule.get("bead_flip_y")) if rule else _bool(bead_slot.get("flip_y"))
		side = _side(rule.get("bead_side") if rule else bead_slot.get("side"), "inside")
		return {
			"source": "series_section_config",
			"preset": f"{opening_type}:{application}",
			"host": host,
			"side": side,
			"groove": (rule.get("bead_groove") if rule else "bead_slot") or "bead_slot",
			"slot_x": _num(bead_slot.get("x"), 0.0),
			"slot_y": _num(bead_slot.get("y"), 0.0),
			"slot_w": _num(bead_slot.get("w"), 0.0),
			"slot_h": _num(bead_slot.get("h"), 0.0),
			"offsetAlong": -along if mirrored else along,
			"offsetDepth": depth,
			"rotation": rotation,
			"flipX": flip_x,
			"flipY": flip_y,
			"inner_gasket_item": _str(rule.get("inner_gasket_item")) if rule else "",
			"outer_gasket_item": _str(rule.get("outer_gasket_item")) if rule else "",
		}

	if role == "glass":
		host_cfg = sash_cfg if in_sash else frame_cfg
		glass_slot = host_cfg.get("glass_slot") if isinstance(host_cfg.get("glass_slot"), dict) else {}
		if not glass_slot.get("configured"):
			return None
		return {
			"source": "series_section_config",
			"preset": f"{opening_type}:{application}",
			"host": "sash" if in_sash else "frame",
			"slot_x": _num(glass_slot.get("x"), 0.0),
			"slot_y": _num(glass_slot.get("y"), 0.0),
			"slot_w": _num(glass_slot.get("w"), 0.0),
			"slot_h": _num(glass_slot.get("h"), 0.0),
			"rebate_depth_mm": _num(glass_slot.get("rebate_depth_mm"), 12.0),
			"clearance_mm": _num(glass_slot.get("clearance_mm"), 4.0),
		}

	return None
