"""A Material Request for a project, and one raised from a task.

- The project's contract: a request with a project shows the project's main Sales Order and
  the main quotation it was made from.
- The project's warehouse: a purchase or transfer request for a project, with no target
  warehouse chosen, goes to the project's warehouse. A request made from a task takes the
  task's project.
- The Technical Office's notes on the task's execution items go on the request's items.
- A submitted request made from a task is assigned to the role and/or the department chosen
  in Projects Settings.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import escape_html, get_fullname

MODULE = "Gesc App"
PROJECT = "custom_sample_project"
SALES_ORDER = "custom_project_sales_order"
QUOTATION = "custom_project_quotation"
NOTES = "custom_technical_office_notes"
ROLE_SETTING = "custom_task_material_request_role"
DEPARTMENT_SETTING = "custom_task_material_request_department"
# Purposes whose target warehouse is the project's.
TO_PROJECT_WAREHOUSE = ("Purchase", "Material Transfer")


def setup():
	create_custom_fields(
		{
			"Material Request": [
				{
					"fieldname": SALES_ORDER,
					"label": "أمر البيع (عقد المشروع)",
					"fieldtype": "Link",
					"options": "Sales Order",
					"insert_after": "custom_sample_project_title",
					"read_only": 1,
					"no_copy": 1,
					"depends_on": f"eval:doc.{PROJECT}",
					"module": MODULE,
				},
				{
					"fieldname": QUOTATION,
					"label": "عرض السعر الأساسي",
					"fieldtype": "Link",
					"options": "Quotation",
					"insert_after": SALES_ORDER,
					"read_only": 1,
					"no_copy": 1,
					"in_standard_filter": 1,
					"depends_on": f"eval:doc.{PROJECT}",
					"description": "عرض السعر الذي عُمل منه أمر البيع الذي عُمل منه المشروع.",
					"module": MODULE,
				},
			],
			"Material Request Item": [
				{
					"fieldname": NOTES,
					"label": "ملاحظات المكتب الفني",
					"fieldtype": "Small Text",
					"insert_after": "description",
					"read_only": 1,
					"no_copy": 1,
					"in_list_view": 1,
					"columns": 2,
					"module": MODULE,
				},
			],
			"Projects Settings": [
				{
					"fieldname": "custom_task_material_request_section",
					"label": "طلبات المواد من المهام",
					"fieldtype": "Section Break",
					"insert_after": "custom_project_warehouse_parent",
					"module": MODULE,
				},
				{
					"fieldname": ROLE_SETTING,
					"label": "الدور الذي تُسند له طلبات المواد",
					"fieldtype": "Link",
					"options": "Role",
					"insert_after": "custom_task_material_request_section",
					"description": "كل طلب مواد معمول من مهمة يُسند عند اعتماده لكل مستخدمي هذا الدور.",
					"module": MODULE,
				},
				{
					"fieldname": DEPARTMENT_SETTING,
					"label": "القسم الذي تُسند له طلبات المواد",
					"fieldtype": "Link",
					"options": "Department",
					"insert_after": ROLE_SETTING,
					"description": "ولموظفي هذا القسم (وأقسامه الفرعية) اللي لهم مستخدم. يمكن اختيار الدور أو القسم أو الاثنين.",
					"module": MODULE,
				},
			],
		},
		update=True,
	)
	frappe.clear_cache(doctype="Material Request")
	_backfill()


def _backfill():
	"""Requests made before this: their project, contract and the office's notes."""
	for name, task in frappe.db.sql(
		f"""select name, custom_task from `tabMaterial Request`
		where docstatus < 2 and ifnull({PROJECT}, '') = ''"""
	):
		project = task and frappe.db.get_value("Task", task, "project")
		if not project:
			projects = frappe.db.sql_list(
				"""select distinct project from `tabMaterial Request Item`
				where parent = %s and ifnull(project, '') != ''""",
				name,
			)
			project = projects[0] if len(projects) == 1 else None
		if project:
			frappe.db.set_value(
				"Material Request",
				name,
				{PROJECT: project, "custom_sample_project_title": frappe.db.get_value("Project", project, "project_name")},
				update_modified=False,
			)

	for name, project in frappe.db.sql(
		f"""select name, {PROJECT} from `tabMaterial Request`
		where docstatus < 2 and ifnull({PROJECT}, '') != '' and ifnull({QUOTATION}, '') = ''"""
	):
		sales_order, quotation = get_project_contract(project)
		if sales_order or quotation:
			frappe.db.set_value(
				"Material Request", name, {SALES_ORDER: sales_order, QUOTATION: quotation}, update_modified=False
			)

	for name, task in frappe.db.sql(
		"""select name, custom_task from `tabMaterial Request`
		where docstatus < 2 and ifnull(custom_task, '') != ''"""
	):
		doc = frappe.get_doc("Material Request", name)
		before = [row.get(NOTES) for row in doc.items]
		_copy_task_notes(doc)
		for row, old in zip(doc.items, before, strict=False):
			if row.get(NOTES) != old:
				row.db_set(NOTES, row.get(NOTES), update_modified=False)


def get_project_contract(project):
	"""The project's main Sales Order and the main quotation it was made from."""
	if not project:
		return None, None
	sales_order = frappe.db.get_value("Project", project, "sales_order")
	if not sales_order:
		orders = frappe.get_all(
			"Sales Order",
			filters={"project": project, "docstatus": 1},
			fields=["name", "custom_addendum_to"],
			order_by="custom_is_main_contract desc, transaction_date asc, creation asc",
			limit=1,
		)
		if orders:
			sales_order = orders[0].custom_addendum_to or orders[0].name
	if not sales_order:
		return None, None
	# An addendum's main contract.
	sales_order = frappe.db.get_value("Sales Order", sales_order, "custom_addendum_to") or sales_order

	quotation = frappe.db.get_value(
		"Sales Order Item",
		{"parent": sales_order, "prevdoc_docname": ("is", "set")},
		"prevdoc_docname",
		order_by="idx asc",
	)
	if quotation:
		quotation = frappe.db.get_value("Quotation", quotation, "custom_addendum_to") or quotation
	return sales_order, quotation


@frappe.whitelist()
def get_project_details(project=None, task=None):
	"""For the form: the task's project, its warehouse and its contract."""
	if task and not project:
		frappe.get_doc("Task", task).check_permission("read")
		project = frappe.db.get_value("Task", task, "project")
	if not project:
		return {}
	sales_order, quotation = get_project_contract(project)
	return {
		"project": project,
		"warehouse": _project_warehouse(project),
		"sales_order": sales_order,
		"quotation": quotation,
	}


def _project_warehouse(project):
	return frappe.db.get_value(
		"Warehouse", {"custom_is_project_warehouse": 1, "custom_project": project, "disabled": 0}
	)


def set_task_project(doc, method=None):
	"""before_validate, before sample_request's: a request from a task takes its project."""
	if doc.get("custom_task") and not doc.get(PROJECT):
		project = frappe.db.get_value("Task", doc.custom_task, "project")
		if project:
			doc.set(PROJECT, project)


def validate(doc, method=None):
	"""before_validate, after sample_request's (the project is on the request by now)."""
	project = doc.get(PROJECT)
	sales_order, quotation = get_project_contract(project)
	doc.set(SALES_ORDER, sales_order)
	doc.set(QUOTATION, quotation)

	if project and doc.material_request_type in TO_PROJECT_WAREHOUSE and not doc.get("set_warehouse"):
		warehouse = _project_warehouse(project)
		if warehouse and frappe.db.get_value("Warehouse", warehouse, "company") == doc.company:
			doc.set_warehouse = warehouse
			for row in doc.items:
				if not row.project or row.project == project:
					row.warehouse = warehouse

	_copy_task_notes(doc)


def _copy_task_notes(doc):
	"""Each item without notes takes the office's notes of the task's row for the same item,
	in order when the item is on the task more than once."""
	if not doc.get("custom_task"):
		return
	rows = frappe.get_all(
		"Task Execution Item",
		filters={"parent": doc.custom_task, "parenttype": "Task"},
		fields=["item_code", "technical_office_notes"],
		order_by="idx asc",
	)
	notes = {}
	for row in rows:
		notes.setdefault(row.item_code, []).append(row.technical_office_notes or "")
	for item in doc.items:
		queue = notes.get(item.item_code)
		if not queue:
			continue
		note = queue.pop(0)
		if not item.get(NOTES) and note:
			item.set(NOTES, note)


def assign_to_department(doc, method=None):
	"""on_submit: a request from a task goes to the role and department in Projects Settings."""
	if not doc.get("custom_task"):
		return
	users = sorted(set(_recipients()) - {"Administrator", "Guest"})
	if not users:
		return

	from frappe.desk.form.assign_to import _add

	# The assignees read the request even without a role for it (the one submitting may not
	# be allowed to share, so it is shared here).
	for user in users:
		if not frappe.has_permission(doc=doc, user=user):
			frappe.share.add_docshare(doc.doctype, doc.name, user, read=1, flags={"ignore_share_permission": 1})

	project = doc.get(PROJECT)
	description = _("طلب مواد من المهمة {0}{1} — {2}").format(
		doc.custom_task,
		_(" للمشروع {0}").format(escape_html(doc.get("custom_sample_project_title") or project)) if project else "",
		escape_html(get_fullname(frappe.session.user)),
	)
	muted = frappe.flags.mute_messages
	frappe.flags.mute_messages = True
	try:
		_add(
			{"assign_to": users, "doctype": doc.doctype, "name": doc.name, "description": description},
			ignore_permissions=True,
		)
	finally:
		frappe.flags.mute_messages = muted


def _recipients():
	from gesc_app.gesc_app.task_execution import users_with_role

	users = list(users_with_role(frappe.db.get_single_value("Projects Settings", ROLE_SETTING)))
	department = frappe.db.get_single_value("Projects Settings", DEPARTMENT_SETTING)
	if department:
		lft, rgt = frappe.db.get_value("Department", department, ["lft", "rgt"]) or (0, 0)
		departments = frappe.get_all("Department", filters={"lft": (">=", lft), "rgt": ("<=", rgt)}, pluck="name")
		employee_users = frappe.get_all(
			"Employee",
			filters={"department": ("in", departments or [department]), "status": "Active", "user_id": ("is", "set")},
			pluck="user_id",
		)
		users += frappe.get_all("User", filters={"name": ("in", employee_users or ["-"]), "enabled": 1}, pluck="name")
	return users


def get_project_dashboard_data(data):
	"""A project's Material Requests are those with its project; one made from the project's
	page gets it."""
	data.setdefault("non_standard_fieldnames", {})["Material Request"] = PROJECT
	return data
