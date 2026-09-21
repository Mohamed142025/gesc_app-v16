import frappe


ITEM_CHILD_TABLES = (
	"Quotation Item",
	"Sales Order Item",
	"Sales Invoice Item",
	"Delivery Note Item",
	"POS Invoice Item",
	"Request for Quotation Item",
	"Supplier Quotation Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Material Request Item",
	"Stock Entry Detail",
	"Pick List Item",
)


PARENT_DOCTYPES = (
	"Quotation",
	"Sales Order",
	"Sales Invoice",
	"Delivery Note",
	"POS Invoice",
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Material Request",
	"Stock Entry",
	"Pick List",
)


def setup_item_description_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	custom_fields = {}
	for child_doctype in ITEM_CHILD_TABLES:
		custom_fields[child_doctype] = [
			{
				"fieldname": "custom_item_description",
				"label": "وصف البند",
				"fieldtype": "Link",
				"options": "Item Description",
				"insert_after": "item_code",
				"module": "Gesc App",
				"in_list_view": 0,
				"allow_on_submit": 0,
			}
		]

	create_custom_fields(custom_fields, update=True)


def validate_item_descriptions(doc, method=None):
	for row in doc.get("items") or []:
		if not row.get("custom_item_description"):
			continue

		description = frappe.db.get_value(
			"Item Description",
			row.custom_item_description,
			["item_code", "description"],
			as_dict=True,
		)
		if not description:
			frappe.throw("التوصيف المحدد غير موجود")
		if description.item_code != row.item_code:
			frappe.throw("التوصيف المحدد غير مرتبط بالصنف المختار")

		row.description = description.description