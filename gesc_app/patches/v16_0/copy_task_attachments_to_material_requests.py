"""Material Requests raised from a task before they carried its files get them now
(task_execution.copy_task_attachments)."""

import frappe

from gesc_app.gesc_app.task_execution import copy_task_attachments


def execute():
	for name, task in frappe.get_all(
		"Material Request",
		filters={"custom_task": ("is", "set"), "docstatus": ("<", 2)},
		fields=["name", "custom_task"],
		as_list=True,
	):
		if frappe.db.exists("Task", task):
			copy_task_attachments(frappe.get_doc("Task", task), frappe.get_doc("Material Request", name))
