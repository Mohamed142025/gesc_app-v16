"""A warehouse for every new project.

When a project is created it gets its own warehouse, named after it ("مخزن مدينتي مول
الحرفيين"), marked as a project warehouse and linked to it (the fields task_execution reads
when it raises the project's Material Requests). It goes under the group chosen in Projects
Settings, or the company's "مخازن المشاريع" group.

A warehouse of that name already there and linked to no project is linked instead of making
a second one; a name taken by another project's warehouse gets the project's code. A project
that already has a warehouse is left as it is. Should the warehouse fail, the project is still
created and the user is told why.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import get_link_to_form

PARENT_SETTING = "custom_project_warehouse_parent"
PROJECTS_GROUP = "مخازن المشاريع"
MODULE = "Gesc App"


def setup():
	create_custom_fields(
		{
			"Projects Settings": [
				{
					"fieldname": "custom_project_warehouse_section",
					"label": "مخازن المشاريع",
					"fieldtype": "Section Break",
					"insert_after": "custom_execution_send_notify_role",
					"module": MODULE,
				},
				{
					"fieldname": PARENT_SETTING,
					"label": "المجموعة الرئيسية لمخازن المشاريع",
					"fieldtype": "Link",
					"options": "Warehouse",
					"insert_after": "custom_project_warehouse_section",
					"description": "كل مشروع جديد يتعمل له مخزن باسمه تحت المجموعة دي. لو فاضية، بيتعمل تحت «مخازن المشاريع» في شركة المشروع.",
					"module": MODULE,
				},
			]
		},
		update=True,
	)
	if not frappe.db.get_single_value("Projects Settings", PARENT_SETTING):
		group = frappe.db.get_value("Warehouse", {"warehouse_name": PROJECTS_GROUP, "is_group": 1}, "name")
		if group:
			frappe.db.set_single_value("Projects Settings", PARENT_SETTING, group)


def create_project_warehouse(project, method=None):
	"""after_insert of Project."""
	if not project.company or _linked_warehouse(project.name):
		return
	savepoint = "project_warehouse"
	frappe.db.savepoint(savepoint)
	try:
		warehouse = _make_or_link(project)
	except Exception as e:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(title=f"Project warehouse for {project.name}", reference_doctype="Project", reference_name=project.name)
		frappe.msgprint(
			_("اتعمل المشروع، لكن مخزنه ما اتعملش: {0}").format(frappe.utils.strip_html(str(e))),
			title=_("مخزن المشروع"),
			indicator="orange",
		)
		return
	frappe.msgprint(
		_("مخزن المشروع: {0}").format(get_link_to_form("Warehouse", warehouse)), alert=True, indicator="green"
	)


def _linked_warehouse(project):
	return frappe.db.get_value("Warehouse", {"custom_is_project_warehouse": 1, "custom_project": project, "disabled": 0})


def _make_or_link(project):
	title = (project.project_name or project.name).strip()
	# Not translated: the name is the same whoever creates the project.
	warehouse_name = f"مخزن {title}"
	abbr = frappe.get_cached_value("Company", project.company, "abbr")

	existing = frappe.db.get_value(
		"Warehouse",
		{"warehouse_name": warehouse_name, "company": project.company},
		["name", "is_group", "custom_is_project_warehouse", "custom_project"],
		as_dict=True,
	)
	if existing and not existing.is_group and not existing.custom_project:
		# Someone made it by hand already: it becomes this project's warehouse.
		doc = frappe.get_doc("Warehouse", existing.name)
		doc.custom_is_project_warehouse = 1
		doc.custom_project = project.name
		doc.save(ignore_permissions=True)
		return doc.name
	if existing or frappe.db.exists("Warehouse", f"{warehouse_name} - {abbr}"):
		warehouse_name = f"{warehouse_name} ({project.name})"

	doc = frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": warehouse_name,
			"company": project.company,
			"parent_warehouse": _parent(project.company),
			"custom_is_project_warehouse": 1,
			"custom_project": project.name,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _parent(company):
	parent = frappe.db.get_single_value("Projects Settings", PARENT_SETTING)
	if parent and frappe.db.get_value("Warehouse", parent, "company") == company:
		return parent
	return frappe.db.get_value("Warehouse", {"warehouse_name": PROJECTS_GROUP, "is_group": 1, "company": company}) or frappe.db.get_value(
		"Warehouse", {"is_group": 1, "company": company, "parent_warehouse": ["is", "not set"]}
	)


def get_dashboard_data(data):
	"""The project's warehouse among its connections."""
	data.setdefault("non_standard_fieldnames", {})["Warehouse"] = "custom_project"
	for group in data.setdefault("transactions", []):
		if group.get("label") == _("Material"):
			group["items"].insert(0, "Warehouse")
			break
	else:
		data["transactions"].append({"label": _("Warehouse"), "items": ["Warehouse"]})
	return data
