import base64

from onebook_fenestration.fenestration.print_context import company_header, design_rows, quote_totals


def fen_svg_data_uri(svg: str | None) -> str:
	"""A data URI for an SVG string, so print formats embed drawings as images, never inline markup."""
	if not svg:
		return ""
	return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def fen_design_rows(doc) -> list[dict]:
	return design_rows(doc)


def fen_quote_totals(doc, rows: list[dict]) -> dict:
	return quote_totals(doc, rows)


def fen_company_header(company: str | None) -> dict:
	return company_header(company)
