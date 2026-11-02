"""Quotation fields read by the GESC quotation print formats.

On each item: an alternative name printed in place of the item's name, notes printed under
its description, and whether it is grouped with the items of the same title in the grouped
print format. On the quotation: the customer's name as printed; left empty, the customer is
not printed. Which attachments are printed, and the item each belongs to, are on the
Quotation Attachment rows.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Gesc App"


def setup():
	create_custom_fields(
		{
			"Quotation": [
				{
					"fieldname": "custom_print_customer_name",
					"label": "اسم العميل في الطباعة",
					"fieldtype": "Data",
					"insert_after": "custom_submitted_to",
					"description": "يظهر في خانة العميل في الطباعة. اتركه فارغاً فلا يُطبع العميل.",
					"module": MODULE,
				},
			],
			"Quotation Item": [
				{
					"fieldname": "custom_alternative_item_name",
					"label": "الاسم البديل للصنف",
					"fieldtype": "Data",
					"insert_after": "custom_attachment",
					"description": "يُطبع مكان اسم الصنف. اتركه فارغاً فيُطبع اسم الصنف.",
					"module": MODULE,
				},
				{
					"fieldname": "custom_group_in_print",
					"label": "تجميع في الطباعة",
					"fieldtype": "Check",
					"insert_after": "custom_alternative_item_name",
					"description": "في نموذج الطباعة المجمّع: يُطبع تحت عنوان واحد مع البنود المعلَّمة التي لها نفس الاسم.",
					"module": MODULE,
				},
				{
					"fieldname": "custom_item_notes",
					"label": "ملاحظات",
					"fieldtype": "Small Text",
					"insert_after": "description",
					"description": "تُطبع تحت توصيف البند.",
					"module": MODULE,
				},
			],
		},
		update=True,
	)
