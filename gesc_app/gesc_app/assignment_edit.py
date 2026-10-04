"""Assignees may edit what they are assigned, when System Settings says so.

Frappe shares an assigned document with its assignee for reading only, and only when they
cannot read it already. With "السماح للمعيَّن له بتعديل المستند المسند" on, an open
assignment (ToDo) also lets its assignee edit the document: write is added to their share
of it. The ToDo keeps a mark that it gave write, so only that write is taken back - when the
assignment is closed, cancelled or deleted, and no other open assignment of theirs on the
same document still needs it. Reading stays, as Frappe leaves it.

Turning the setting on gives write on the open assignments; turning it off takes back
what it gave. Roles, workflow states and field levels still apply as usual.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.share import add_docshare, get_share_name

SETTING = "custom_assignee_can_edit"
MARK = "custom_edit_shared"
MODULE = "Gesc App"


def setup():
	create_custom_fields(
		{
			"System Settings": [
				{
					"fieldname": SETTING,
					"label": "السماح للمعيَّن له بتعديل المستند المسند",
					"fieldtype": "Check",
					"insert_after": "disable_document_sharing",
					"description": "من يُسنَد له مستند (Assign To) يقدر يعدّله ما دام الإسناد مفتوحاً، ولو لم يكن دوره يسمح بالتعديل. تُسحب صلاحية التعديل عند إغلاق الإسناد أو إلغائه.",
					"module": MODULE,
				}
			],
			"ToDo": [
				{
					"fieldname": MARK,
					"label": "منح صلاحية التعديل",
					"fieldtype": "Check",
					"insert_after": "assigned_by",
					"read_only": 1,
					"hidden": 1,
					"no_copy": 1,
					"module": MODULE,
				}
			],
		},
		update=True,
	)


def is_enabled():
	return bool(frappe.db.get_single_value("System Settings", SETTING))


# ToDo hooks -----------------------------------------------------------------------------


def sync_edit_share(todo, method=None):
	if not (todo.reference_type and todo.reference_name and todo.allocated_to):
		return
	if todo.status == "Open" and not todo.get(MARK) and is_enabled():
		if _grant(todo):
			todo.db_set(MARK, 1, update_modified=False)
	elif todo.status != "Open" and todo.get(MARK):
		_revoke(todo)
		todo.db_set(MARK, 0, update_modified=False)


def revoke_on_delete(todo, method=None):
	if todo.get(MARK):
		_revoke(todo)


# System Settings hook -------------------------------------------------------------------


def apply_setting(settings, method=None):
	"""Turned on: the open assignments give write. Turned off: what was given is taken back."""
	if not settings.has_value_changed(SETTING):
		return
	if settings.get(SETTING):
		todos = frappe.get_all(
			"ToDo",
			filters={"status": "Open", MARK: 0, "reference_type": ["is", "set"], "reference_name": ["is", "set"]},
			pluck="name",
		)
		for name in todos:
			sync_edit_share(frappe.get_doc("ToDo", name))
	else:
		for name in frappe.get_all("ToDo", filters={MARK: 1}, pluck="name"):
			todo = frappe.get_doc("ToDo", name)
			_revoke(todo)
			todo.db_set(MARK, 0, update_modified=False)


# Sharing --------------------------------------------------------------------------------


def _grant(todo):
	"""Write on the document for its assignee, when their roles do not already give it."""
	doctype, name, user = todo.reference_type, todo.reference_name, todo.allocated_to
	if not frappe.db.exists(doctype, name) or not frappe.db.get_value("User", user, "enabled"):
		return False
	# Write already given by another open assignment of theirs: this one needs it too, so
	# closing the other one does not take it away.
	if _other_marked_open(todo):
		return True
	if frappe.has_permission(doctype, "write", doc=name, user=user):
		return False
	if frappe.get_system_settings("disable_document_sharing"):
		frappe.msgprint(
			_("مشاركة المستندات معطّلة في System Settings، فلا يمكن منح {0} صلاحية تعديل {1}.").format(
				frappe.bold(user), frappe.bold(name)
			),
			alert=True,
			indicator="orange",
		)
		return False

	share_name = get_share_name(doctype, name, user, 0)
	if share_name:
		# Only write is turned on; whatever else the share gives is kept.
		share = frappe.get_doc("DocShare", share_name)
		share.write = 1
		share.read = 1
		share.flags.ignore_share_permission = True
		share.save(ignore_permissions=True)
	else:
		add_docshare(doctype, name, user, read=1, write=1, flags={"ignore_share_permission": True})
	return True


def _revoke(todo):
	"""Take back the write this assignment gave, unless another open one still needs it."""
	doctype, name, user = todo.reference_type, todo.reference_name, todo.allocated_to
	if _other_marked_open(todo):
		return
	share_name = get_share_name(doctype, name, user, 0)
	if not share_name:
		return
	share = frappe.get_doc("DocShare", share_name)
	share.write = 0
	share.flags.ignore_share_permission = True
	share.save(ignore_permissions=True)


def _other_marked_open(todo):
	"""Another open assignment of the same user on the same document that gave write."""
	return frappe.db.exists(
		"ToDo",
		{
			"name": ["!=", todo.name],
			"reference_type": todo.reference_type,
			"reference_name": todo.reference_name,
			"allocated_to": todo.allocated_to,
			"status": "Open",
			MARK: 1,
		},
	)
