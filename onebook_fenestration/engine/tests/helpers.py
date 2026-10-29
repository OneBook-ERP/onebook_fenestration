import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
	return str(FIXTURES / name)


def load(name: str) -> dict:
	return json.loads((FIXTURES / name).read_text())


def snapshot():
	from onebook_fenestration.engine.types import SeriesSnapshot

	return SeriesSnapshot.from_dict(load("cs400_snapshot.json"))


def snapshot_with(mutate):
	"""Snapshot built from the CS400 fixture after `mutate(data)` edits the raw dict."""
	from onebook_fenestration.engine.types import SeriesSnapshot

	data = load("cs400_snapshot.json")
	mutate(data)
	return SeriesSnapshot.from_dict(data)
