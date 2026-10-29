"""Plain data shapes the engine consumes and produces. No DB access here."""

from dataclasses import MISSING, dataclass, field, fields

SIDES = ("frame", "mullion", "transom")
REQUIRED_DEDUCTIONS = (
	*(f"bar_end_{s}" for s in SIDES),
	*(f"sash_side_{s}" for s in SIDES),
	"sash_glass",
	*(f"fixed_glass_side_{s}" for s in SIDES),
	"glazing_gasket",
)
SNAPSHOT_SECTIONS = ("deductions", "profiles", "member_rules", "hardware_rules", "validation_rules", "glasses", "constants")
HARDWARE_PER = ("frame_member", "sash_member", "mullion", "transom_member", "sash", "glass", "window")


class EngineError(Exception):
	pass


class DesignError(EngineError):
	"""The design tree itself is malformed."""


class RuleError(EngineError):
	"""A series rule formula could not be evaluated."""


class SectionError(EngineError):
	"""A profile DXF could not be turned into a section."""


@dataclass(frozen=True)
class ProfileSpec:
	code: str
	name: str
	kg_per_m: float
	bar_lengths: tuple[float, ...]
	visible_perimeter_mm: float = 0.0
	total_perimeter_mm: float = 0.0


@dataclass(frozen=True)
class MemberRule:
	id: str
	role: str
	profile: str
	angles: tuple[int, int]
	length: str


@dataclass(frozen=True)
class HardwareRule:
	id: str
	item: str
	name: str
	per: str
	qty: str
	uom: str = "Nos"
	when: str = "True"
	length: str | None = None
	group: str = "Fabrication Hardware"


@dataclass(frozen=True)
class ValidationRule:
	id: str
	when: str
	severity: str
	message: str
	hint: str = ""


@dataclass(frozen=True)
class GlassSpec:
	code: str
	name: str
	thickness_mm: float


@dataclass(frozen=True)
class SeriesSnapshot:
	code: str
	version: str
	deductions: dict[str, float]
	profiles: dict[str, ProfileSpec]
	member_rules: tuple[MemberRule, ...]
	hardware_rules: tuple[HardwareRule, ...]
	validation_rules: tuple[ValidationRule, ...]
	glasses: dict[str, GlassSpec]
	constants: dict[str, float]

	@classmethod
	def from_dict(cls, data: dict) -> "SeriesSnapshot":
		"""Build from plain dicts (fixture JSON or DB rows); unknown keys in rows are ignored."""
		try:
			code, version = data["code"], data["version"]
			sections = {key: data[key] for key in SNAPSHOT_SECTIONS}
		except KeyError as exc:
			raise RuleError(f"series snapshot is missing {exc.args[0]!r}") from exc
		profiles = {}
		for pcode, p in sections["profiles"].items():
			spec = _row(ProfileSpec, {**p, "code": pcode}, f"profile {pcode}")
			profiles[pcode] = ProfileSpec(
				spec.code, spec.name, spec.kg_per_m, tuple(spec.bar_lengths), spec.visible_perimeter_mm, spec.total_perimeter_mm
			)
		member_rules = []
		for r in sections["member_rules"]:
			rule = _row(MemberRule, r, f"member rule {r.get('id')}")
			member_rules.append(MemberRule(rule.id, rule.role, rule.profile, tuple(rule.angles), rule.length))
		return cls(
			code=code,
			version=version,
			deductions=dict(sections["deductions"]),
			profiles=profiles,
			member_rules=tuple(member_rules),
			hardware_rules=tuple(_row(HardwareRule, r, f"hardware rule {r.get('id')}") for r in sections["hardware_rules"]),
			validation_rules=tuple(_row(ValidationRule, r, f"validation rule {r.get('id')}") for r in sections["validation_rules"]),
			glasses={gcode: _row(GlassSpec, {**g, "code": gcode}, f"glass {gcode}") for gcode, g in sections["glasses"].items()},
			constants=dict(sections["constants"]),
		)

	def check(self) -> None:
		"""Raise RuleError listing every missing deduction, profile, constant or bad hardware `per`."""
		problems = [f"deduction {key!r} missing" for key in REQUIRED_DEDUCTIONS if key not in self.deductions]
		problems += [
			f"{rule.id}: profile {rule.profile!r} not in series" for rule in self.member_rules if rule.profile not in self.profiles
		]
		if "glass_density" not in self.constants:
			problems.append("constant 'glass_density' missing")
		problems += [
			f"{rule.id}: unknown per {rule.per!r} (allowed: {', '.join(HARDWARE_PER)})"
			for rule in self.hardware_rules
			if rule.per not in HARDWARE_PER
		]
		if problems:
			raise RuleError(f"series {self.code} snapshot is incomplete: " + "; ".join(problems))


def _row(cls, row: dict, label: str):
	"""Construct dataclass `cls` from the keys of `row` it knows, naming any required key that is missing."""
	known = {f.name for f in fields(cls)}
	required = {f.name for f in fields(cls) if f.default is MISSING and f.default_factory is MISSING}
	missing = sorted(required - row.keys())
	if missing:
		raise RuleError(f"{label}: missing {', '.join(missing)}")
	return cls(**{k: v for k, v in row.items() if k in known})


@dataclass(frozen=True)
class CutMember:
	panel: str
	role: str
	position: str
	profile: str
	length: float
	angles: tuple[int, int]
	path: str = ""


@dataclass(frozen=True)
class GlassPane:
	panel: str
	number: int
	glass: str
	width: float
	height: float
	path: str = ""


@dataclass(frozen=True)
class BomLine:
	item: str
	name: str
	qty: float
	uom: str
	panel: str = ""
	position: str = ""
	length: float | None = None
	group: str = ""


@dataclass(frozen=True)
class Issue:
	severity: str
	code: str
	message: str
	panel: str = ""
	hint: str = ""
	path: str = ""


@dataclass
class EngineResult:
	members: list[CutMember]
	glass: list[GlassPane]
	bom: list[BomLine]
	shutter_kg: dict[str, float]
	window_kg: float
	area_m2: float
	area_sqft: float
	issues: list[Issue] = field(default_factory=list)
