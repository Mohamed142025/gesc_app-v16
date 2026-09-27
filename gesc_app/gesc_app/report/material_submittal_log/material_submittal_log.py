# Copyright (c) 2026, mohamed sayed and contributors
# For license information, please see license.txt

"""Material Submittal Log: one line per submittal with its latest revision, as asked for
in consultant meetings."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, nowdate

from gesc_app.gesc_app.material_submittal import STATE_SUBMITTED


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "submittal_no", "label": _("رقم الـ Submittal"), "fieldtype": "Data", "width": 170},
		{"fieldname": "revision", "label": _("Rev"), "fieldtype": "Data", "width": 60},
		{"fieldname": "task", "label": _("المهمة"), "fieldtype": "Link", "options": "Task", "width": 130},
		{"fieldname": "subject", "label": _("الموضوع"), "fieldtype": "Data", "width": 200},
		{"fieldname": "materials", "label": _("المواد"), "fieldtype": "Data", "width": 220},
		{"fieldname": "project", "label": _("المشروع"), "fieldtype": "Link", "options": "Project", "width": 110},
		{"fieldname": "state", "label": _("الحالة"), "fieldtype": "Data", "width": 190},
		{"fieldname": "response_code", "label": _("الكود"), "fieldtype": "Data", "width": 200},
		{"fieldname": "submitted_on", "label": _("تاريخ الإرسال"), "fieldtype": "Date", "width": 110},
		{"fieldname": "due_date", "label": _("الرد المتوقع"), "fieldtype": "Date", "width": 110},
		{"fieldname": "response_date", "label": _("تاريخ الرد"), "fieldtype": "Date", "width": 110},
		{"fieldname": "days", "label": _("أيام عند الاستشاري"), "fieldtype": "Int", "width": 90},
		{"fieldname": "overdue_days", "label": _("أيام التأخير"), "fieldtype": "Int", "width": 90},
		{"fieldname": "revisions", "label": _("عدد المراجعات"), "fieldtype": "Int", "width": 90},
	]


def get_data(filters):
	conditions = {"custom_is_material_submittal": 1}
	if filters.project:
		conditions["project"] = filters.project
	if filters.state:
		conditions["workflow_state"] = filters.state

	tasks = frappe.get_all(
		"Task",
		filters=conditions,
		fields=[
			"name", "subject", "project", "workflow_state", "custom_submittal_no",
			"custom_submittal_revision", "custom_response_due_date",
		],
		order_by="custom_submittal_no asc, creation asc",
	)
	if not tasks:
		return []

	names = [t.name for t in tasks]
	revisions = {}
	for row in frappe.get_all(
		"Task Submittal Revision",
		filters={"parenttype": "Task", "parent": ["in", names]},
		fields=["parent", "revision", "submitted_on", "response_code", "response_date", "days_with_consultant"],
		order_by="parent, idx",
	):
		revisions.setdefault(row.parent, []).append(row)

	# A material reads best as its description and maker, as submitted.
	materials = {}
	for row in frappe.get_all(
		"Task Execution Item",
		filters={"parenttype": "Task", "parent": ["in", names]},
		fields=["parent", "item_name", "item_code", "description", "manufacturer"],
		order_by="parent, idx",
	):
		label = (row.description or row.item_name or row.item_code).strip()
		if row.manufacturer:
			label = f"{label} ({row.manufacturer})"
		materials.setdefault(row.parent, []).append(label)

	today = getdate(nowdate())
	data = []
	for task in tasks:
		rows = revisions.get(task.name, [])
		last = rows[-1] if rows else frappe._dict()
		if filters.response_code and last.get("response_code") != filters.response_code:
			continue
		if filters.from_date and (not last.get("submitted_on") or getdate(last.submitted_on) < getdate(filters.from_date)):
			continue
		if filters.to_date and (not last.get("submitted_on") or getdate(last.submitted_on) > getdate(filters.to_date)):
			continue

		waiting = task.workflow_state == STATE_SUBMITTED
		days = last.get("days_with_consultant")
		if waiting and last.get("submitted_on"):
			days = date_diff(today, last.submitted_on)
		overdue = 0
		if waiting and task.custom_response_due_date:
			overdue = max(date_diff(today, task.custom_response_due_date), 0)
		if filters.overdue_only and not overdue:
			continue

		data.append(
			{
				"submittal_no": task.custom_submittal_no or "",
				"revision": f"Rev {int(last.revision):02d}" if rows else "",
				"task": task.name,
				"subject": task.subject,
				"materials": "، ".join(materials.get(task.name, [])),
				"project": task.project,
				"state": _(task.workflow_state),
				"response_code": last.get("response_code") or "",
				"submitted_on": last.get("submitted_on"),
				"due_date": task.custom_response_due_date if waiting else None,
				"response_date": last.get("response_date"),
				"days": days,
				"overdue_days": overdue,
				"revisions": len(rows),
			}
		)
	return data
