"""The project's team (فريق العمل).

Each project has a table of the employees working on it, with their name and designation.
Every member with a user is assigned the project; a member taken out of the table is no
longer assigned (assignments made by hand, outside the table, are left alone). The
"متابعة المشاريع" report counts each member's projects by status.
"""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.desk.form.assign_to import _add, _remove

MODULE = "Gesc App"
TABLE = "custom_team_members"


def setup():
	create_custom_fields(
		{
			"Project": [
				{
					"fieldname": "custom_team_section",
					"label": "فريق العمل",
					"fieldtype": "Section Break",
					"insert_after": "percent_complete",
					"module": MODULE,
				},
				{
					"fieldname": TABLE,
					"label": "فريق العمل",
					"fieldtype": "Table",
					"options": "Project Team Member",
					"insert_after": "custom_team_section",
					"description": "كل موظف له مستخدم يُكلَّف بالمشروع تلقائياً، ومن يُحذف من الجدول يُلغى تكليفه.",
					"module": MODULE,
				},
			],
		},
		update=True,
	)


def sync_assignments(doc, method=None):
	"""on_update of Project: the team's users are assigned the project."""
	users = _team_users(doc)
	before = doc.get_doc_before_save()
	removed = (_team_users(before) if before else set()) - users
	assigned = set(
		frappe.get_all(
			"ToDo",
			filters={"reference_type": "Project", "reference_name": doc.name, "status": "Open"},
			pluck="allocated_to",
		)
	)
	for user in sorted(users - assigned):
		_add(
			{"assign_to": [user], "doctype": "Project", "name": doc.name, "description": doc.project_name},
			ignore_permissions=True,
		)
	for user in sorted(removed & assigned):
		_remove("Project", doc.name, user, ignore_permissions=True)


def _team_users(doc):
	employees = [row.employee for row in doc.get(TABLE) or [] if row.employee]
	if not employees:
		return set()
	return set(
		frappe.get_all(
			"User",
			filters={
				"name": ["in", frappe.get_all("Employee", filters={"name": ["in", employees]}, pluck="user_id")],
				"enabled": 1,
			},
			pluck="name",
		)
	)


def add_assigned_employees():
	"""Each project's current assignees join its team, active employees only."""
	employees = {
		e.user_id: e
		for e in frappe.get_all(
			"Employee",
			filters={"status": "Active", "user_id": ["is", "set"]},
			fields=["name", "user_id", "employee_name", "designation"],
		)
	}
	for project, assign in frappe.get_all(
		"Project", filters={"_assign": ["is", "set"]}, fields=["name", "_assign"], as_list=True
	):
		members = frappe.get_all(
			"Project Team Member",
			filters={"parent": project, "parenttype": "Project", "parentfield": TABLE},
			pluck="employee",
		)
		idx = len(members)
		for user in json.loads(assign or "[]"):
			employee = employees.get(user)
			if not employee or employee.name in members:
				continue
			idx += 1
			members.append(employee.name)
			frappe.get_doc(
				{
					"doctype": "Project Team Member",
					"parent": project,
					"parenttype": "Project",
					"parentfield": TABLE,
					"idx": idx,
					"employee": employee.name,
					"employee_name": employee.employee_name,
					"designation": employee.designation,
					"user_id": user,
				}
			).db_insert()
