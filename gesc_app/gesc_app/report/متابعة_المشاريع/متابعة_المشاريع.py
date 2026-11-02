# Copyright (c) 2026, mohamed sayed and contributors
# For license information, please see license.txt

"""متابعة المشاريع: for each member of a project team, how many projects and how many in
each status."""

import frappe
from frappe import _

STATUSES = (("Open", "مفتوح"), ("Completed", "مكتمل"), ("Cancelled", "ملغي"))


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "employee_name", "label": _("الاسم"), "fieldtype": "Data", "width": 220},
		{"fieldname": "employee", "label": _("الموظف"), "fieldtype": "Link", "options": "Employee", "width": 130},
		{"fieldname": "designation", "label": _("الوظيفة"), "fieldtype": "Link", "options": "Designation", "width": 180},
		{"fieldname": "total", "label": _("عدد المشاريع"), "fieldtype": "Int", "width": 120},
	] + [
		{"fieldname": status.lower(), "label": _(label), "fieldtype": "Int", "width": 100}
		for status, label in STATUSES
	]


def get_data(filters):
	conditions, values = [], {}
	if filters.employee:
		conditions.append("member.employee = %(employee)s")
		values["employee"] = filters.employee
	if filters.designation:
		conditions.append("employee.designation = %(designation)s")
		values["designation"] = filters.designation
	counts = ", ".join(
		f"count(distinct case when project.status = '{status}' then project.name end) as {status.lower()}"
		for status, _label in STATUSES
	)
	return frappe.db.sql(
		f"""
		select member.employee, employee.employee_name, employee.designation,
			count(distinct project.name) as total, {counts}
		from `tabProject Team Member` member
		inner join `tabProject` project on project.name = member.parent
		left join `tabEmployee` employee on employee.name = member.employee
		where member.parenttype = 'Project' and member.parentfield = 'custom_team_members'
			{"".join(" and " + c for c in conditions)}
		group by member.employee, employee.employee_name, employee.designation
		order by total desc, employee.employee_name
		""",
		values,
		as_dict=True,
	)
