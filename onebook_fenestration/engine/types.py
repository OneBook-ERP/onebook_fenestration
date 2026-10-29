"""Plain data shapes the engine consumes and produces. No DB access here."""

from dataclasses import dataclass, field


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
		return cls(
			code=data["code"],
			version=data["version"],
			deductions=dict(data["deductions"]),
			profiles={
				code: ProfileSpec(code=code, name=p["name"], kg_per_m=p["kg_per_m"], bar_lengths=tuple(p["bar_lengths"]))
				for code, p in data["profiles"].items()
			},
			member_rules=tuple(MemberRule(**{**r, "angles": tuple(r["angles"])}) for r in data["member_rules"]),
			hardware_rules=tuple(HardwareRule(**r) for r in data["hardware_rules"]),
			validation_rules=tuple(ValidationRule(**r) for r in data["validation_rules"]),
			glasses={code: GlassSpec(code=code, **g) for code, g in data["glasses"].items()},
			constants=dict(data["constants"]),
		)


@dataclass(frozen=True)
class CutMember:
	panel: str
	role: str
	position: str
	profile: str
	length: float
	angles: tuple[int, int]


@dataclass(frozen=True)
class GlassPane:
	panel: str
	number: int
	glass: str
	width: float
	height: float


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
