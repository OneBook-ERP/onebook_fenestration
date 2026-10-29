"""Walk the design tree into leaf cells and the bars (mullions/transoms) that split them."""

from dataclasses import dataclass

from onebook_fenestration.engine.types import DesignError

LEAF_TYPES = {"sash", "fixed", "louver"}
BAR_KIND = {"v": "mullion", "h": "transom"}


@dataclass(frozen=True)
class Cell:
	path: str
	x: float
	y: float
	w: float
	h: float
	sides: dict[str, str]
	node: dict


@dataclass(frozen=True)
class Bar:
	kind: str
	id: str
	length_span: float
	ends: tuple[str, str]


def layout(design: dict) -> tuple[list[Cell], list[Bar]]:
	width, height = design.get("width"), design.get("height")
	if not (isinstance(width, int | float) and isinstance(height, int | float)) or width <= 0 or height <= 0:
		raise DesignError(f"F1: width and height must be positive numbers, got {width!r} x {height!r}")

	cells: list[Cell] = []
	bars: list[Bar] = []
	counters = {"mullion": 0, "transom": 0}
	frame_sides = {"L": "frame", "R": "frame", "B": "frame", "T": "frame"}
	_walk(design["root"], "F1", 0, 0, width, height, frame_sides, cells, bars, counters)
	return cells, bars


def _walk(node, path, x, y, w, h, sides, cells, bars, counters):
	kind = node.get("type")
	if kind in LEAF_TYPES:
		cells.append(Cell(path=path, x=x, y=y, w=w, h=h, sides=dict(sides), node=node))
		return
	if kind != "split":
		raise DesignError(f"{path}: unknown node type {kind!r}")

	direction = node.get("dir")
	if direction not in BAR_KIND:
		raise DesignError(f"{path}: split dir must be 'v' or 'h', got {direction!r}")

	children = node.get("children") or []
	span = w if direction == "v" else h
	bounds = _split_bounds(path, node.get("at") or [], span, len(children))

	bar_kind = BAR_KIND[direction]
	for _ in bounds[1:-1]:
		counters[bar_kind] += 1
		prefix = "M" if bar_kind == "mullion" else "T"
		if direction == "v":
			bars.append(Bar(bar_kind, f"{prefix}{counters[bar_kind]}", h, (sides["B"], sides["T"])))
		else:
			bars.append(Bar(bar_kind, f"{prefix}{counters[bar_kind]}", w, (sides["L"], sides["R"])))

	last = len(children) - 1
	for i, child in enumerate(children):
		start, size = bounds[i], bounds[i + 1] - bounds[i]
		child_sides = dict(sides)
		if direction == "v":
			child_sides["L"] = sides["L"] if i == 0 else bar_kind
			child_sides["R"] = sides["R"] if i == last else bar_kind
			_walk(child, f"{path}.{i}", x + start, y, size, h, child_sides, cells, bars, counters)
		else:
			child_sides["B"] = sides["B"] if i == 0 else bar_kind
			child_sides["T"] = sides["T"] if i == last else bar_kind
			_walk(child, f"{path}.{i}", x, y + start, w, size, child_sides, cells, bars, counters)


def _split_bounds(path: str, at: list, span: float, child_count: int) -> list[float]:
	if child_count < 2 or len(at) != child_count - 1:
		raise DesignError(f"{path}: split needs at least 2 children and len(at) == children - 1")
	bounds = [0, *at, span]
	if any(not (a < b) for a, b in zip(bounds, bounds[1:])):
		raise DesignError(f"{path}: split positions {at} must increase strictly inside (0, {span})")
	return bounds
