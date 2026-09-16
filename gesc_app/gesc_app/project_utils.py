import frappe
from frappe import _
from frappe.utils import add_days, today


def generate_tasks_from_template(doc, method=None):
	if not doc.custom_task_template:
		return

	if not doc.has_value_changed("custom_task_template"):
		return

	template = frappe.get_doc("Project Task Template", doc.custom_task_template)

	if not template.tasks:
		return

	project_start = doc.expected_start_date or today()
	previous_task_end = project_start
	created = 0

	for row in template.tasks:
		if row.sequential:
			start_date = add_days(previous_task_end, row.start_after_days or 0)
		else:
			start_date = add_days(project_start, row.start_after_days or 0)

		end_date = add_days(start_date, max(row.duration_days or 1, 1) - 1)
		previous_task_end = end_date

		description = row.description or ""
		if row.default_role:
			role_note = _("Suggested responsible role: {0}").format(row.default_role)
			description = f"{description}\n\n{role_note}" if description else role_note

		frappe.get_doc(
			{
				"doctype": "Task",
				"project": doc.name,
				"subject": row.subject,
				"description": description,
				"priority": row.priority or "Medium",
				"is_milestone": row.is_milestone,
				"exp_start_date": start_date,
				"exp_end_date": end_date,
				"status": "Open",
			}
		).insert(ignore_permissions=True)
		created += 1

	if created:
		frappe.msgprint(
			_("{0} tasks were created from template {1}.").format(created, frappe.bold(template.template_name)),
			alert=True,
			indicator="green",
		)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_project_sales_order_items(doctype, txt, searchfield, start, page_len, filters):
	"""Restrict the Item link on Project Item to items actually sold on the
	project's linked Sales Order, so a البند always traces back to a real
	contracted service instead of the full Item master."""

	project = filters.get("project") if filters else None
	sales_order = project and frappe.db.get_value("Project", project, "sales_order")

	if not sales_order:
		# البند must trace back to a real contracted item, so show nothing
		# until the project has a Sales Order linked.
		return []

	return frappe.db.sql(
		"""
		select soi.item_code, soi.item_name
		from `tabSales Order Item` soi
		where soi.parent = %(sales_order)s
			and (soi.item_code like %(txt)s or soi.item_name like %(txt)s)
		limit %(page_len)s offset %(start)s
		""",
		{"sales_order": sales_order, "txt": f"%{txt}%", "page_len": page_len, "start": start},
	)
