"""Whoever is assigned a project can read its contracts and their quotations.

The project's contracts are its Sales Orders (the main contract and its addenda, and the one
on the project's own field); their quotations are the ones their items were made from. A
user with an open assignment (ToDo) on the project is given read on them through a share,
when their roles do not let them read them already (a Site Engineer reads only the Sales
Orders they made, say).

The shares given here carry a mark, so they are taken back when no open assignment needs
them any more: the assignment closed or deleted, or the contract moved to another project.
A share that someone widened since (write, submit, share) is left, only unmarked; shares
given any other way are never touched.

Each change is applied as its transaction is committed, once per user.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.share import get_share_name

MODULE = "Gesc App"
MARK = "custom_from_project_assignment"
FLAG = "gesc_project_access_users"
SKIPPED_USERS = ("Administrator", "Guest")


def setup():
	create_custom_fields(
		{
			"DocShare": [
				{
					"fieldname": MARK,
					"label": "من التكليف بالمشروع",
					"fieldtype": "Check",
					"insert_after": "everyone",
					"read_only": 1,
					"description": "مشاركة قراءة أعطاها التكليف بمشروع على عقوده وعروض أسعارها؛ تُسحب بانتهاء التكليف.",
					"module": MODULE,
				}
			]
		},
		update=True,
	)
	users = set(
		frappe.get_all("ToDo", filters={"reference_type": "Project", "status": "Open"}, pluck="allocated_to")
	) | set(frappe.get_all("DocShare", filters={MARK: 1}, pluck="user"))
	for user in users:
		sync_user(user)


# Hooks ------------------------------------------------------------------------------------


def on_todo_change(todo, method=None):
	if todo.reference_type != "Project":
		return
	before = todo.get_doc_before_save()
	_queue({todo.allocated_to, before.allocated_to if before else None})


def on_sales_order_change(doc, method=None):
	before = doc.get_doc_before_save()
	_queue(_assignees({doc.project, before.project if before else None}))


def on_project_change(doc, method=None):
	if doc.has_value_changed("sales_order"):
		_queue(_assignees({doc.name}))


def _assignees(projects):
	projects = [p for p in projects if p]
	if not projects:
		return set()
	return set(
		frappe.get_all(
			"ToDo",
			filters={"reference_type": "Project", "reference_name": ("in", projects), "status": "Open"},
			pluck="allocated_to",
		)
	)


def _queue(users):
	users = {user for user in users if user and user not in SKIPPED_USERS}
	if not users:
		return
	frappe.local.flags.setdefault(FLAG, set()).update(users)
	frappe.db.before_commit.add(_apply_queued)


def _apply_queued():
	for user in frappe.local.flags.pop(FLAG, set()):
		sync_user(user)


# Sharing ----------------------------------------------------------------------------------


def sync_user(user):
	"""Give the user read on their projects' contracts and quotations, and take back what
	this gave and no project needs now."""
	wanted = set() if user in SKIPPED_USERS or not frappe.db.get_value("User", user, "enabled") else documents_for(user)
	marked = {
		(row.share_doctype, row.share_name): row
		for row in frappe.get_all(
			"DocShare",
			filters={"user": user, MARK: 1},
			fields=["name", "share_doctype", "share_name", "write", "submit", "share"],
		)
	}

	for doctype, name in wanted - set(marked):
		if get_share_name(doctype, name, user, 0) or frappe.has_permission(doctype, "read", name, user=user):
			continue
		share = frappe.new_doc("DocShare")
		share.update({"user": user, "share_doctype": doctype, "share_name": name, "read": 1, MARK: 1})
		share.flags.ignore_share_permission = True
		share.insert(ignore_permissions=True)

	for key, row in marked.items():
		if key in wanted:
			continue
		if row.write or row.submit or row.share:
			frappe.db.set_value("DocShare", row.name, MARK, 0, update_modified=False)
			continue
		share = frappe.get_doc("DocShare", row.name)
		share.flags.ignore_share_permission = True
		share.delete(ignore_permissions=True)


def documents_for(user):
	projects = frappe.get_all(
		"ToDo", filters={"reference_type": "Project", "allocated_to": user, "status": "Open"}, pluck="reference_name"
	)
	if not projects:
		return set()
	orders = set(
		frappe.get_all("Sales Order", filters={"project": ("in", projects), "docstatus": ("<", 2)}, pluck="name")
	)
	orders |= {
		order
		for order in frappe.get_all("Project", filters={"name": ("in", projects)}, pluck="sales_order")
		if order and frappe.db.get_value("Sales Order", order, "docstatus") in (0, 1)
	}
	quotations = set()
	if orders:
		quotations = set(
			frappe.get_all(
				"Sales Order Item",
				filters={"parent": ("in", list(orders)), "prevdoc_docname": ("is", "set")},
				pluck="prevdoc_docname",
			)
		)
		quotations = set(frappe.get_all("Quotation", filters={"name": ("in", list(quotations))}, pluck="name")) if quotations else set()
	return {("Sales Order", name) for name in orders} | {("Quotation", name) for name in quotations}
