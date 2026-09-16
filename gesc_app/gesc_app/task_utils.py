import frappe
from frappe import _
from frappe.desk.form.assign_to import _add as assign_to_add
from frappe.desk.form.assign_to import _remove as assign_to_remove


def sync_responsible_assignment(doc, method=None):
	if not doc.has_value_changed("custom_responsible_person"):
		return

	doc_before_save = doc.get_doc_before_save()
	old_employee = doc_before_save.get("custom_responsible_person") if doc_before_save else None

	if old_employee and old_employee != doc.custom_responsible_person:
		old_user = frappe.db.get_value("Employee", old_employee, "user_id")
		if old_user:
			assign_to_remove(doc.doctype, doc.name, old_user, ignore_permissions=True)

	if not doc.custom_responsible_person:
		return

	new_user = frappe.db.get_value("Employee", doc.custom_responsible_person, "user_id")
	if not new_user:
		frappe.msgprint(
			_("Employee {0} has no linked User account, so no assignment/notification was created.").format(
				doc.custom_responsible_person
			),
			alert=True,
			indicator="orange",
		)
		return

	already_assigned = frappe.db.exists(
		"ToDo",
		{
			"reference_type": doc.doctype,
			"reference_name": doc.name,
			"allocated_to": new_user,
			"status": "Open",
		},
	)
	if already_assigned:
		return

	assign_to_add(
		{
			"assign_to": [new_user],
			"doctype": doc.doctype,
			"name": doc.name,
			"description": _("You have been assigned as the person responsible for task: {0}").format(
				doc.subject or doc.name
			),
		},
		ignore_permissions=True,
	)
