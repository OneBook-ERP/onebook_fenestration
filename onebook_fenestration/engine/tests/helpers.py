import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
	return str(FIXTURES / name)


def load(name: str) -> dict:
	return json.loads((FIXTURES / name).read_text())
