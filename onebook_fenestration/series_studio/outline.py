"""Turning a stored profile outline (SVG path `d`, mm, bbox at 0,0, y down) by a quarter turn.

Pure: no database access. Handles the absolute commands our outlines use: M, L, A and Z, with implicit repeats
("M x y x y ..." as the section importer writes). Positive degrees turn clockwise on screen (y down):
90 maps (x, y) to (-y, x). The result is shifted back so its bbox starts at 0,0.
"""

import re

ROTATIONS = (0, 90, 180, 270)
TOKEN = re.compile(r"[A-Za-z]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
# numbers per repeat of each command, and which of them are an x, y point
ARGS = {"M": 2, "L": 2, "A": 7, "Z": 0}
POINT_AT = {"M": 0, "L": 0, "A": 5}

_ROT_MAT = {
	0: ((1, 0), (0, 1)),
	90: ((0, -1), (1, 0)),
	180: ((-1, 0), (0, -1)),
	270: ((0, 1), (-1, 0)),
}
_CANONICAL_D4 = (
	(0, 0, 0),
	(90, 0, 0),
	(180, 0, 0),
	(270, 0, 0),
	(0, 1, 0),
	(0, 0, 1),
	(90, 1, 0),
	(270, 1, 0),
)


def _d4_matrix(degrees: int, flip_x: bool, flip_y: bool) -> tuple[tuple[int, int], tuple[int, int]]:
	((r00, r01), (r10, r11)) = _ROT_MAT[degrees]
	sx = -1 if flip_x else 1
	sy = -1 if flip_y else 1
	return ((r00 * sx, r01 * sy), (r10 * sx, r11 * sy))


def _as_bool_flag(value) -> bool:
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		return bool(int(value))
	return str(value or "").strip().lower() in ("1", "true", "yes")


def compose_section_transform(
	cur_degrees: int | str = 0,
	cur_flip_x: bool | int | str = False,
	cur_flip_y: bool | int | str = False,
	delta_degrees: int | str = 0,
	delta_flip_x: bool | int | str = False,
	delta_flip_y: bool | int | str = False,
) -> tuple[int, int, int]:
	"""Compose `M(delta) * M(current)` in the 2D dihedral group D4 -> canonical `(degrees, flip_x, flip_y)`."""
	cur_d = _degrees(cur_degrees)
	del_d = _degrees(delta_degrees)
	cur_fx = _as_bool_flag(cur_flip_x)
	cur_fy = _as_bool_flag(cur_flip_y)
	a = _d4_matrix(del_d, _as_bool_flag(delta_flip_x), _as_bool_flag(delta_flip_y))
	b = _d4_matrix(cur_d, cur_fx, cur_fy)
	target = (
		(a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]),
		(a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]),
	)
	for rot, fx, fy in _CANONICAL_D4:
		if _d4_matrix(rot, bool(fx), bool(fy)) == target:
			return rot, fx, fy
	return cur_d, int(cur_fx), int(cur_fy)


def transform_path(
	d: str,
	degrees: int | str = 0,
	flip_x: bool | int | str = False,
	flip_y: bool | int | str = False,
) -> tuple[str, float, float]:
	"""(transformed path, width, depth): flip first (`flip_x`, `flip_y`), then turn CW by `degrees`, renormalised to 0,0."""
	degrees = _degrees(degrees)
	fx = _as_bool_flag(flip_x)
	fy = _as_bool_flag(flip_y)
	commands = _parse(d)
	if degrees == 0 and not fx and not fy:
		return d, *_extents(commands)
	transformed = [
		(cmd, [_turn_args(cmd, _flip_args(cmd, args, fx, fy), degrees) for args in groups])
		for cmd, groups in commands
	]
	xs, ys = _coords(transformed)
	if not xs:
		return d, 0, 0
	min_x, min_y = min(xs), min(ys)
	shifted = [(cmd, [_shift_args(cmd, args, min_x, min_y) for args in groups]) for cmd, groups in transformed]
	return _format(shifted), _round(max(xs) - min_x), _round(max(ys) - min_y)


def rotate_path(d: str, degrees: int | str) -> tuple[str, float, float]:
	"""(turned path, width, depth): the path turned by `degrees` and renormalised, and its x / y extents.

	0 returns `d` unchanged. Arc radii and large-arc / sweep flags stay as they are (a rotation keeps the
	direction of travel); the arc's x-axis-rotation turns with the outline. Extents come from path points, not
	arc bulges.
	"""
	return transform_path(d, degrees)


def svg_extents(d: str) -> tuple[float, float]:
	"""(width, depth) of a path's points."""
	return _extents(_parse(d))


def _degrees(degrees) -> int:
	try:
		value = int(degrees or 0)
	except (TypeError, ValueError):
		value = -1
	if value not in ROTATIONS:
		raise ValueError(f"outline rotation must be one of {ROTATIONS}, got {degrees!r}")
	return value


def _parse(d: str) -> list[tuple[str, list[list[float]]]]:
	"""[(command, [args per repeat])]; numbers after a command's last full repeat are an error."""
	commands: list[tuple[str, list[list[float]]]] = []
	numbers: list[float] = []

	def close():
		if not commands:
			if numbers:
				raise ValueError("path must start with a command")
			return
		cmd, groups = commands[-1]
		size = ARGS[cmd]
		if (size == 0 and numbers) or (size and len(numbers) % size):
			raise ValueError(f"wrong number of values after {cmd}")
		if size:
			groups.extend(numbers[i : i + size] for i in range(0, len(numbers), size))
		numbers.clear()

	for token in TOKEN.findall(d or ""):
		if token.isalpha():
			close()
			if token not in ARGS:
				raise ValueError(f"unsupported path command {token!r}; outlines use absolute M, L, A, Z")
			commands.append((token, []))
		else:
			numbers.append(float(token))
	close()
	return commands


def _turn(x: float, y: float, degrees: int) -> tuple[float, float]:
	if degrees == 0:
		return x, y
	if degrees == 90:
		return -y, x
	if degrees == 180:
		return -x, -y
	return y, -x


def _flip_args(cmd: str, args: list[float], flip_x: bool, flip_y: bool) -> list[float]:
	if (not flip_x and not flip_y) or cmd not in POINT_AT:
		return args
	i = POINT_AT[cmd]
	out = list(args)
	if flip_x:
		out[i] = -args[i]
	if flip_y:
		out[i + 1] = -args[i + 1]
	if cmd == "A" and (flip_x != flip_y):
		out[2] = (-args[2]) % 360
		out[4] = 0 if args[4] else 1
	return out


def _turn_args(cmd: str, args: list[float], degrees: int) -> list[float]:
	if degrees == 0 or cmd not in POINT_AT:
		return args
	i = POINT_AT[cmd]
	out = list(args)
	out[i], out[i + 1] = _turn(args[i], args[i + 1], degrees)
	if cmd == "A":
		out[2] = (args[2] + degrees) % 360
	return out


def _shift_args(cmd: str, args: list[float], dx: float, dy: float) -> list[float]:
	if cmd not in POINT_AT:
		return args
	i = POINT_AT[cmd]
	out = list(args)
	out[i], out[i + 1] = args[i] - dx, args[i + 1] - dy
	return out


def _coords(commands) -> tuple[list[float], list[float]]:
	xs, ys = [], []
	for cmd, groups in commands:
		if cmd in POINT_AT:
			i = POINT_AT[cmd]
			for args in groups:
				xs.append(args[i])
				ys.append(args[i + 1])
	return xs, ys


def _extents(commands) -> tuple[float, float]:
	xs, ys = _coords(commands)
	if not xs:
		return 0, 0
	return _round(max(xs) - min(xs)), _round(max(ys) - min(ys))


def _format(commands) -> str:
	parts = []
	for cmd, groups in commands:
		parts.append(" ".join([cmd, *(_num(v) for args in groups for v in args)]))
	return " ".join(parts)


def _round(value: float) -> float:
	return round(value, 2)


def _num(value: float) -> str:
	text = f"{value:.2f}".rstrip("0").rstrip(".")
	return "0" if text in ("-0", "") else text
