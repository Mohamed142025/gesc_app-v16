"""Supply and installation weights on the Sales Order's items.

Each item's progress is supplied qty x supply % + installed qty x installation %, so the
two are a split of the item's 100%: both are entered and add up to 100. An item marked
"بدون نسب إنجاز" (Item > custom_no_progress_weights) is not followed by progress and needs
neither.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt

NO_WEIGHTS = "custom_no_progress_weights"


def setup():
	create_custom_fields(
		{
			"Item": [
				{
					"fieldname": NO_WEIGHTS,
					"label": "بدون نسب إنجاز",
					"fieldtype": "Check",
					"insert_after": "stock_uom",
					"description": "لا يُطلب له نسبة توريد ونسبة تركيب في أمر البيع، ولا تُتابع له نسبة إنجاز.",
					"module": "Gesc App",
				}
			]
		},
		update=True,
	)


def validate_weights(doc, method=None):
	"""Sales Order validate: every item's supply % and installation % add up to 100."""
	items = {row.item_code for row in doc.items if row.item_code}
	exempt = set(
		frappe.get_all("Item", filters={"name": ["in", list(items)], NO_WEIGHTS: 1}, pluck="name")
	) if items else set()

	wrong = []
	for row in doc.items:
		if not row.item_code or row.item_code in exempt:
			continue
		supply, install = flt(row.custom_supply_percent), flt(row.custom_install_percent)
		if supply < 0 or install < 0 or abs(supply + install - 100) > 0.01:
			wrong.append(
				_("الصف {0} ({1}): توريد {2}% + تركيب {3}%").format(
					row.idx, frappe.bold(row.item_code), frappe.format(supply), frappe.format(install)
				)
			)
	if wrong:
		frappe.throw(
			_("مجموع نسبة التوريد ونسبة التركيب لكل بند يجب أن يكون 100%:")
			+ "<br>"
			+ "<br>".join(wrong)
			+ "<br><br>"
			+ _("الصنف الذي لا تُتابع له نسبة إنجاز: علّم عليه «بدون نسب إنجاز» في شاشة الصنف."),
			title=_("نسب الإنجاز"),
		)
