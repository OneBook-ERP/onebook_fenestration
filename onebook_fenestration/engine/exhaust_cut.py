"""Circular exhaust openings, measured from the panel's left and top edges."""
from math import isfinite


def exhaust_cut(node: dict, width: float, height: float) -> dict | None:
	if not node.get("fan"):
		return None
	if node.get("type") == "louver":
		raise ValueError("Exhaust cuts require a fixed or sash glass pane")
	config = node.get("fanCut") or {}
	if not isinstance(config, dict):
		raise ValueError("Exhaust cut dimensions must be an object")
	diameter = config.get("diameter", 180)
	if not isinstance(diameter, (int, float)) or isinstance(diameter, bool) or not isfinite(diameter) or diameter <= 0:
		raise ValueError("Exhaust cut diameter must be a positive number")
	x = config.get("centerX", width / 2)
	y = config.get("centerY", height / 2)
	if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not isfinite(v) for v in (x, y)):
		raise ValueError("Exhaust cut centre must contain finite numbers")
	r = diameter / 2
	if x - r <= 0 or x + r >= width or y - r <= 0 or y + r >= height:
		raise ValueError("Exhaust cut must fit entirely inside the panel")
	return {"diameter": diameter, "centerX": x, "centerY": y}
