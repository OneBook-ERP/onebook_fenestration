"""Dealer-to-Hilux project sharing, manufacturing handover status, and role-scoped visibility."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

HILUX_STAFF_ROLES = frozenset(
	{
		"System Manager",
		"Sales Manager",
		"Sales User",
		"Fenestration Engineer",
		"Manufacturing User",
	}
)
PARTNER_ROLES = frozenset({"Fenestration Dealer", "Fenestration Fabrication Partner"})
VALID_PARTNER_TYPES = ("Dealer", "Fabrication Partner", "Own Client")
HILUX_MANUFACTURING_ROLES = ("Fenestration Engineer", "Manufacturing User", "Sales Manager")
VALID_MANUFACTURING_STATUSES = (
	"Private Draft",
	"Shared with Hilux",
	"Accepted for Manufacturing",
	"Materials Procured",
	"In Fabrication",
	"Dispatched to Dealer",
)


def is_hilux_staff(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	return bool(roles & HILUX_STAFF_ROLES)


def is_partner_only(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if is_hilux_staff(user):
		return False
	roles = set(frappe.get_roles(user))
	return bool(roles & PARTNER_ROLES)


def project_permission_query(user: str | None = None) -> str:
	"""Scope Fenestration Project visibility:
	- Hilux staff see internal projects + any Dealer project shared with Hilux (not unshared dealer private drafts).
	- Partners and other roles only see their own (or explicitly shared) projects.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""

	escaped = frappe.db.escape(user)
	if is_hilux_staff(user):
		return (
			f"(IFNULL(`tabFenestration Project`.fen_is_dealer_private, 0) = 0 "
			f"OR IFNULL(`tabFenestration Project`.fen_shared_with_hilux, 0) = 1 "
			f"OR `tabFenestration Project`.owner = {escaped})"
		)

	return (
		f"(`tabFenestration Project`.owner = {escaped} "
		f"OR EXISTS (SELECT 1 FROM `tabDocShare` ds "
		f"WHERE ds.share_doctype = 'Fenestration Project' "
		f"AND ds.share_name = `tabFenestration Project`.name "
		f"AND ds.user = {escaped} AND ds.read = 1))"
	)


def _docshare_perm_field(ptype: str | None) -> str | None:
	if ptype in (None, "read", "select", "print", "report", "email", "export"):
		return "read"
	if ptype in ("write", "share", "submit"):
		return ptype
	return None


def project_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	if isinstance(doc, str):
		doc = frappe.db.get_value(
			"Fenestration Project",
			doc,
			["name", "owner", "fen_is_dealer_private", "fen_shared_with_hilux"],
			as_dict=True,
		)
		if not doc:
			return True

	if is_hilux_staff(user):
		if (
			cint(doc.get("fen_is_dealer_private"))
			and not cint(doc.get("fen_shared_with_hilux"))
			and doc.get("owner") != user
		):
			return False
		return True

	if doc.get("owner") == user:
		return True
	share_col = _docshare_perm_field(ptype)
	if not share_col:
		return False
	shared = frappe.db.exists(
		"DocShare",
		{"share_doctype": "Fenestration Project", "share_name": doc.get("name"), "user": user, share_col: 1},
	)
	return bool(shared)


def design_permission_query(user: str | None = None) -> str:
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""

	escaped = frappe.db.escape(user)
	if is_hilux_staff(user):
		return (
			f"EXISTS (SELECT 1 FROM `tabFenestration Project` p "
			f"WHERE p.name = `tabWindow Design`.project "
			f"AND (IFNULL(p.fen_is_dealer_private, 0) = 0 "
			f"OR IFNULL(p.fen_shared_with_hilux, 0) = 1 "
			f"OR p.owner = {escaped}))"
		)

	return (
		f"(`tabWindow Design`.owner = {escaped} "
		f"OR EXISTS (SELECT 1 FROM `tabFenestration Project` p "
		f"WHERE p.name = `tabWindow Design`.project AND p.owner = {escaped}) "
		f"OR EXISTS (SELECT 1 FROM `tabDocShare` ds "
		f"WHERE ds.share_doctype = 'Fenestration Project' "
		f"AND ds.share_name = `tabWindow Design`.project "
		f"AND ds.user = {escaped} AND ds.read = 1) "
		f"OR EXISTS (SELECT 1 FROM `tabDocShare` ds "
		f"WHERE ds.share_doctype = 'Window Design' "
		f"AND ds.share_name = `tabWindow Design`.name "
		f"AND ds.user = {escaped} AND ds.read = 1))"
	)


def design_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	project_name = (
		doc.get("project")
		if not isinstance(doc, str)
		else frappe.db.get_value("Window Design", doc, "project")
	)
	if not project_name:
		return True
	return project_has_permission(project_name, ptype=ptype, user=user)


def share_project_with_hilux(
	project: str,
	notes: str | None = None,
	lock_designs: bool = True,
) -> dict:
	"""Share a Dealer's Fenestration Project, designs, and reports with Hilux for manufacturing."""
	frappe.has_permission("Fenestration Project", "write", project, throw=True)
	frappe.has_permission("Fenestration Project", "share", project, throw=True)
	doc = frappe.get_doc("Fenestration Project", project)

	partner_type = resolve_project_partner_type(doc)
	if partner_type != "Dealer":
		if partner_type == "Own Client":
			frappe.throw(
				_(
					"Own Client projects are already direct Hilux residential/apartment projects "
					"and do not require Dealer-to-Hilux sharing."
				),
				frappe.ValidationError,
			)
		frappe.throw(
			_(
				"Only Dealer projects can be shared with Hilux for window manufacturing. "
				"Fabrication Partner projects order aluminium profiles and raw materials directly."
			),
			frappe.ValidationError,
		)

	designs = frappe.get_all(
		"Window Design",
		filters={"project": project, "superseded_by": ("is", "not set")},
		fields=["name", "design_ref", "qty", "error_count"],
		order_by="design_ref asc",
	)
	if not designs:
		frappe.throw(_("Add at least one Window Design before sharing the project with Hilux."))

	errored = [d.design_ref or d.name for d in designs if cint(d.error_count) > 0]
	if errored:
		frappe.throw(
			_("Fix engineering errors in these designs before sharing with Hilux: {0}").format(
				", ".join(errored)
			)
		)

	shared_on = now_datetime()
	updates = {
		"fen_partner_type": "Dealer",
		"fen_shared_with_hilux": 1,
		"fen_is_dealer_private": 0,
		"fen_shared_on": shared_on,
		"fen_shared_by": frappe.session.user,
		"fen_design_locked": 1 if lock_designs else 0,
	}
	if notes is not None:
		updates["fen_share_notes"] = notes.strip()
	if not doc.fen_manufacturing_status or doc.fen_manufacturing_status == "Private Draft":
		updates["fen_manufacturing_status"] = "Shared with Hilux"

	doc.db_set(updates)
	shared_users = _grant_hilux_docshares(project, [d.name for d in designs])
	_notify_hilux_team(doc, designs, shared_users, notes)

	return {
		"ok": True,
		"project": project,
		"shared_with_hilux": True,
		"shared_on": str(shared_on),
		"shared_by": frappe.session.user,
		"design_locked": bool(updates["fen_design_locked"]),
		"manufacturing_status": updates.get("fen_manufacturing_status") or doc.fen_manufacturing_status,
		"design_count": len(designs),
		"window_qty": sum(max(cint(d.qty), 1) for d in designs),
		"shared_user_count": len(shared_users),
	}


def unlock_project_designs(project: str, reason: str | None = None) -> dict:
	"""Unlock a shared project's window designs for revision."""
	frappe.has_permission("Fenestration Project", "write", project, throw=True)
	doc = frappe.get_doc("Fenestration Project", project)
	if not is_hilux_staff() and doc.fen_manufacturing_status in (
		"Materials Procured",
		"In Fabrication",
		"Dispatched to Dealer",
	):
		frappe.throw(_("Cannot unlock designs once Hilux has started procurement or fabrication."))

	doc.db_set("fen_design_locked", 0)
	if reason:
		doc.add_comment("Comment", _("Designs unlocked for revision: {0}").format(reason.strip()))
	return {
		"ok": True,
		"project": project,
		"design_locked": False,
		"manufacturing_status": doc.fen_manufacturing_status,
	}


def update_manufacturing_status(project: str, status: str) -> dict:
	"""Allow Hilux manufacturing/sales staff to update the manufacturing progress stage."""
	if not is_hilux_staff():
		frappe.throw(_("Only Hilux staff can update the manufacturing status."), frappe.PermissionError)
	if status not in VALID_MANUFACTURING_STATUSES:
		frappe.throw(_("Invalid manufacturing status: {0}").format(status))

	frappe.has_permission("Fenestration Project", "write", project, throw=True)
	doc = frappe.get_doc("Fenestration Project", project)
	updates = {"fen_manufacturing_status": status}
	if status in (
		"Accepted for Manufacturing",
		"Materials Procured",
		"In Fabrication",
		"Dispatched to Dealer",
	):
		updates["fen_design_locked"] = 1
	doc.db_set(updates)
	return {
		"ok": True,
		"project": project,
		"manufacturing_status": status,
		"design_locked": bool(updates.get("fen_design_locked", doc.fen_design_locked)),
	}


def resolve_project_partner_type(project_doc) -> str:
	partner_type = project_doc.get("fen_partner_type")
	if partner_type in VALID_PARTNER_TYPES:
		return partner_type
	customer = project_doc.get("customer")
	if customer and frappe.db.has_column("Customer", "fen_partner_type"):
		cust_type = frappe.db.get_value("Customer", customer, "fen_partner_type")
		if cust_type in VALID_PARTNER_TYPES:
			return cust_type
	return "Dealer"


def _grant_hilux_docshares(project: str, design_names: list[str]) -> list[str]:
	role_users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", list(HILUX_MANUFACTURING_ROLES)], "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	if not role_users:
		return []
	active_users = frappe.get_all(
		"User",
		filters={"name": ["in", role_users], "enabled": 1, "user_type": "System User"},
		pluck="name",
		limit=25,
	)
	shared = []
	for user in active_users:
		if user in ("Administrator", frappe.session.user):
			continue
		can_write_proj = 1 if frappe.has_permission("Fenestration Project", "write", user=user) else 0
		can_share_proj = 1 if frappe.has_permission("Fenestration Project", "share", user=user) else 0
		can_write_design = 1 if frappe.has_permission("Window Design", "write", user=user) else 0
		frappe.share.add_docshare(
			"Fenestration Project",
			project,
			user,
			read=1,
			write=can_write_proj,
			share=can_share_proj,
			flags={"ignore_share_permission": True},
		)
		for design_name in design_names:
			frappe.share.add_docshare(
				"Window Design",
				design_name,
				user,
				read=1,
				write=can_write_design,
				flags={"ignore_share_permission": True},
			)
		shared.append(user)
	return shared


def _notify_hilux_team(project_doc, designs: list[dict], users: list[str], notes: str | None) -> None:
	if not users:
		return
	total_qty = sum(max(cint(d.qty), 1) for d in designs)
	subject = _("Dealer shared project {0} ({1} designs, {2} windows) with Hilux").format(
		project_doc.project_title or project_doc.name,
		len(designs),
		total_qty,
	)
	body = (
		notes.strip()
		if notes
		else _(
			"Window designs, cutting sheets, assembly details, and BOM takeoff are ready for manufacturing."
		)
	)
	for user in users:
		try:
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"subject": subject,
					"email_content": body,
					"for_user": user,
					"type": "Share",
					"document_type": "Fenestration Project",
					"document_name": project_doc.name,
					"from_user": frappe.session.user,
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(
				title=f"Failed notifying {user} for shared project {project_doc.name}",
				message=frappe.get_traceback(),
			)
