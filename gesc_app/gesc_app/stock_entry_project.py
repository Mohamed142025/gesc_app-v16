"""The project on a Stock Entry.

The standard project field shows right after the entry type instead of under the accounting
dimensions, and every item takes the entry's project. An installation ("تركيب", a Material
Issue) needs a project: choosing it fills the items with all the stock in the project's
warehouse, which the installed materials are issued from.
"""

import json

import frappe
from frappe import _
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

INSTALLATION = "تركيب"


def setup():
	if not frappe.db.exists("Stock Entry Type", INSTALLATION):
		frappe.get_doc({"doctype": "Stock Entry Type", "name": INSTALLATION, "purpose": "Material Issue"}).insert(
			ignore_permissions=True
		)

	order = [d.fieldname for d in frappe.get_doc("DocType", "Stock Entry").fields if d.fieldname != "project"]
	order.insert(order.index("stock_entry_type") + 1, "project")
	for fieldname, prop, value, prop_type, doctype_or_field in (
		("project", "mandatory_depends_on", f"eval:doc.stock_entry_type == '{INSTALLATION}'", "Code", "DocField"),
		(None, "field_order", json.dumps(order), "Data", "DocType"),
	):
		filters = {"doc_type": "Stock Entry", "property": prop}
		if fieldname:
			filters["field_name"] = fieldname
		if frappe.db.get_value("Property Setter", filters, "value") != value:
			make_property_setter(
				"Stock Entry",
				fieldname,
				prop,
				value,
				prop_type,
				for_doctype=doctype_or_field == "DocType",
				validate_fields_for_doctype=False,
			)
	frappe.clear_cache(doctype="Stock Entry")


def validate(doc, method=None):
	"""before_validate of Stock Entry."""
	if doc.stock_entry_type == INSTALLATION and not doc.project:
		frappe.throw(_("حدد المشروع لحركة التركيب."), title=_("المشروع مطلوب"))
	if doc.project:
		for item in doc.items:
			item.project = doc.project


@frappe.whitelist()
def get_project_stock(project):
	"""The project's warehouse and every item with stock in it, at its full quantity."""
	frappe.has_permission("Stock Entry", "create", throw=True)
	warehouse = frappe.db.get_value(
		"Warehouse", {"custom_is_project_warehouse": 1, "custom_project": project, "disabled": 0}
	)
	if not warehouse:
		return {"warehouse": None, "items": []}
	items = frappe.db.sql(
		"""
		select bin.item_code, item.item_name, item.stock_uom, bin.actual_qty as qty
		from `tabBin` bin
		inner join `tabItem` item on item.name = bin.item_code
		where bin.warehouse = %s and bin.actual_qty > 0
		order by item.item_name
		""",
		warehouse,
		as_dict=True,
	)
	return {"warehouse": warehouse, "items": items}
