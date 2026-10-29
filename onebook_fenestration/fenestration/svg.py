import re
import xml.etree.ElementTree as ET

import frappe
from frappe import _

SVG_NS = "http://www.w3.org/2000/svg"
MAX_BYTES = 500 * 1024
MAX_DEPTH = 64
BAD_VALUES = ("url(", "javascript:", "expression(")
ELEMENTS = frozenset("svg g rect line path text tspan circle polygon polyline title".split())
ATTRIBUTES = frozenset(
	"x y x1 y1 x2 y2 width height d points cx cy r fill stroke stroke-width stroke-dasharray "
	"font-size font-family font-weight text-anchor transform viewBox role aria-label class "
	"data-path opacity".split()
)
DOCTYPE_OR_ENTITY = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)

ET.register_namespace("", SVG_NS)


def sanitize_svg(svg: str) -> str:
	"""Return svg reduced to allowlisted elements and attributes; reject DTDs, entities and oversize input."""
	if len(svg.encode("utf-8")) > MAX_BYTES:
		frappe.throw(_("SVG too large"))
	if DOCTYPE_OR_ENTITY.search(svg):
		frappe.throw(_("SVG is not valid"))
	try:
		root = ET.fromstring(svg)
	except ET.ParseError:
		frappe.throw(_("SVG is not valid"))
	if _local(root.tag) != "svg":
		frappe.throw(_("SVG is not valid"))
	_clean(root, 1)
	return ET.tostring(root, encoding="unicode")


def _local(name: str) -> str:
	return name.rsplit("}", 1)[-1]


def _clean(element: ET.Element, depth: int) -> None:
	if depth > MAX_DEPTH:
		frappe.throw(_("SVG is not valid"))
	element.tag = f"{{{SVG_NS}}}{_local(element.tag)}"
	element.attrib = {
		k: v for k, v in element.attrib.items() if not k.startswith("{") and k in ATTRIBUTES and _safe_value(v)
	}
	for child in list(element):
		if _local(child.tag) in ELEMENTS and _in_svg_namespace(child.tag):
			_clean(child, depth + 1)
		else:
			element.remove(child)


def _safe_value(value: str) -> bool:
	squashed = "".join(value.split()).lower()
	return not any(bad in squashed for bad in BAD_VALUES)


def _in_svg_namespace(name: str) -> bool:
	return not name.startswith("{") or name.startswith("{" + SVG_NS + "}")
