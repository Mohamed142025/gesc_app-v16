"""Who an HR Announcement (ms_hrms) goes to: all employees, or those selected by any of
departments, designations, grades and employees by name; each employee once.

ms_hrms sends to all employees, or to one department. Here, without changing ms_hrms: the
"Selected" audience and its tables (custom fields), and a mixin on the announcement's
class whose on_submit sends to the employees this module finds (extend_doctype_class).
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

DOCTYPE = "HR Announcement"
ALL = "All Employees"
SELECTED = "Selected Employees"
# ms_hrms's own audience, for announcements made before.
DEPARTMENT = "Department"
IS_SELECTED = f'eval:doc.audience === "{SELECTED}"'

# The audience's tables: (field on the announcement, its child doctype, the child's field,
# the Employee field it matches).
TABLES = (
	("custom_departments", "HR Announcement Department", "department", "department"),
	("custom_designations", "HR Announcement Designation", "designation", "designation"),
	("custom_grades", "HR Announcement Grade", "grade", "grade"),
	("custom_employees", "HR Announcement Employee", "employee", "name"),
)
LABELS = {
	"custom_departments": "Departments",
	"custom_designations": "Designations",
	"custom_grades": "Grades",
	"custom_employees": "Employees",
}


def setup():
	previous = "audience"
	fields = []
	for fieldname, child, _field, _employee_field in TABLES:
		fields.append(
			{
				"fieldname": fieldname,
				"label": LABELS[fieldname],
				"fieldtype": "Table MultiSelect",
				"options": child,
				"insert_after": previous,
				"depends_on": IS_SELECTED,
				"module": "Gesc App",
			}
		)
		previous = fieldname
	create_custom_fields({DOCTYPE: fields}, update=True)
	# "Department" stays for the announcements made with it, not offered for new ones.
	make_property_setter(DOCTYPE, "audience", "options", f"{ALL}\n{SELECTED}", "Text", validate_fields_for_doctype=False)
	make_property_setter(
		DOCTYPE, "department", "depends_on", f'eval:doc.audience === "{DEPARTMENT}"', "Data", validate_fields_for_doctype=False
	)
	make_property_setter(DOCTYPE, "department", "read_only", 1, "Check", validate_fields_for_doctype=False)
	frappe.clear_cache(doctype=DOCTYPE)


def get_recipients(doc):
	"""The users of the active employees the announcement is for, each once."""
	conditions = ["status = 'Active'", "ifnull(user_id, '') != ''"]
	values = {}
	if doc.get("company"):
		conditions.append("company = %(company)s")
		values["company"] = doc.company

	if doc.audience == DEPARTMENT:
		conditions.append("department = %(department)s")
		values["department"] = doc.department
	elif doc.audience == SELECTED:
		matches = []
		for fieldname, _child, field, employee_field in TABLES:
			chosen = [row.get(field) for row in doc.get(fieldname) or [] if row.get(field)]
			if chosen:
				matches.append(f"`{employee_field}` in %({fieldname})s")
				values[fieldname] = chosen
		if not matches:
			return []
		conditions.append(f"({' or '.join(matches)})")

	return frappe.db.sql_list(
		f"select distinct user_id from `tabEmployee` where {' and '.join(conditions)} order by employee_name",
		values,
	)


class AudienceMixin:
	def validate(self):
		if hasattr(super(), "validate"):
			super().validate()
		if self.audience == SELECTED and not any(self.get(fieldname) for fieldname, *_rest in TABLES):
			frappe.throw(_("Choose who the announcement is for: departments, designations, grades or employees."))

	def on_submit(self):
		from frappe.utils import now_datetime
		from ms_hrms.app_notifications import excerpt, notify

		users = get_recipients(self)
		if not users:
			frappe.throw(_("No active employee with a user matches the announcement's audience."))
		# As ms_hrms.app_notifications.send_announcement: its title, and the beginning of its
		# text; its page in the app shows it whole.
		text = frappe.utils.escape_html(excerpt(self.message)).replace("\n", "<br>")
		body = f"<b>{frappe.utils.escape_html(self.title)}</b><br>{text}"
		for user in users:
			notify(user, body, DOCTYPE, self.name)
		self.db_set({"recipients": len(users), "sent_on": now_datetime()})


@frappe.whitelist()
def preview_recipients(doc):
	"""The employees the announcement on the form would go to."""
	frappe.has_permission(DOCTYPE, "write", throw=True)
	doc = frappe.get_doc(frappe.parse_json(doc))
	users = get_recipients(doc)
	if not users:
		return []
	return frappe.get_all(
		"Employee",
		filters={"user_id": ["in", users], "status": "Active"},
		fields=["name", "employee_name", "department", "designation"],
		order_by="employee_name",
	)
