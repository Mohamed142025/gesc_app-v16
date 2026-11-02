"""Sales Invoice fields read by the progress statement print format (مستخلص).

On the invoice: the statement's title; left empty, the print says it is a cumulative
statement of the works sold. On each item: its completion percentage as printed; left
empty, the print reads the item's completion on the project (Project Item, from the Work
Completion Notes).
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Gesc App"


def setup():
	create_custom_fields(
		{
			"Sales Invoice": [
				{
					"fieldname": "custom_statement_title",
					"label": "عنوان المستخلص",
					"fieldtype": "Data",
					"insert_after": "customer_name",
					"description": "يُطبع عنواناً للمستخلص، مثل «مستخلص رقم 2». اتركه فارغاً فيُطبع «مستخلص مجمع» ونوع الأعمال.",
					"module": MODULE,
				},
			],
			"Sales Invoice Item": [
				{
					"fieldname": "custom_completion_percent",
					"label": "نسبة الإنجاز %",
					"fieldtype": "Percent",
					"insert_after": "qty",
					"description": "تُطبع في المستخلص. اتركها فارغة فتُطبع نسبة إنجاز البند في المشروع.",
					"module": MODULE,
				},
			],
		},
		update=True,
	)
