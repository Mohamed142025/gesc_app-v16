"""Each execution item had one file from each side; they move to the task's table of item
files, which holds several per side (task_execution.ITEM_ATTACHMENTS)."""

import frappe

from gesc_app.gesc_app.task_execution import (
	ITEM_ATTACHMENTS,
	ITEM_FILE_COUNTS,
	SITE_ENGINEER_ROLE,
	TECHNICAL_OFFICE_ROLE,
)


def execute():
	rows = frappe.get_all(
		"Task Execution Item",
		filters={"parenttype": "Task", "parentfield": "custom_execution_items"},
		fields=[
			"name",
			"parent",
			"idx",
			"item_code",
			"row_key",
			"site_engineer_attachment",
			"technical_office_attachment",
			"attachment_type",
		],
		order_by="parent, idx",
	)
	next_idx = {}
	for row in rows:
		# An item saved before keeps its row name as its key.
		row_key = row.row_key or row.name
		if not row.row_key:
			frappe.db.set_value("Task Execution Item", row.name, "row_key", row_key, update_modified=False)

		for role, file_url, attachment_type in (
			(SITE_ENGINEER_ROLE, row.site_engineer_attachment, None),
			(TECHNICAL_OFFICE_ROLE, row.technical_office_attachment, row.attachment_type),
		):
			if not file_url or frappe.db.exists(
				"Task Execution Item Attachment",
				{"parent": row.parent, "row_key": row_key, "uploaded_by_role": role, "attachment": file_url},
			):
				continue
			if row.parent not in next_idx:
				next_idx[row.parent] = (
					frappe.db.count("Task Execution Item Attachment", {"parent": row.parent, "parenttype": "Task"}) + 1
				)
			frappe.get_doc(
				{
					"doctype": "Task Execution Item Attachment",
					"parent": row.parent,
					"parenttype": "Task",
					"parentfield": ITEM_ATTACHMENTS,
					"idx": next_idx[row.parent],
					"row_key": row_key,
					"row_no": row.idx,
					"item_code": row.item_code,
					"uploaded_by_role": role,
					"attachment": file_url,
					"attachment_type": attachment_type,
				}
			).db_insert()
			next_idx[row.parent] += 1

		for role, fieldname in ITEM_FILE_COUNTS.items():
			count = frappe.db.count(
				"Task Execution Item Attachment",
				{"parent": row.parent, "row_key": row_key, "uploaded_by_role": role},
			)
			frappe.db.set_value("Task Execution Item", row.name, fieldname, count, update_modified=False)
