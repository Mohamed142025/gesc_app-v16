import frappe
from frappe import _

from gesc_app.gesc_app.progress_utils import refresh_project_items_for_sales_order


def refresh_linked_project_items(doc, method=None):
	item_codes = {row.item_code for row in doc.items}
	if item_codes:
		refresh_project_items_for_sales_order(doc.project, list(item_codes))


def validate_contract_relation(doc, method=None):
	if doc.custom_is_main_contract and doc.custom_addendum_to:
		frappe.throw(_("A contract cannot be both a Main Contract and an addendum to another contract."))

	if not doc.custom_addendum_to:
		return

	if not doc.has_value_changed("custom_addendum_to"):
		return

	main_contract = frappe.db.get_value(
		"Sales Order",
		doc.custom_addendum_to,
		["customer", "project", "custom_is_main_contract"],
		as_dict=True,
	)

	if not main_contract or not main_contract.custom_is_main_contract:
		frappe.throw(_("{0} is not marked as a Main Contract.").format(doc.custom_addendum_to))

	if main_contract.customer != doc.customer or main_contract.project != doc.project:
		frappe.throw(
			_("The addendum must have the same Customer and Project as the Main Contract {0}.").format(
				doc.custom_addendum_to
			)
		)

	existing_addenda = frappe.db.count(
		"Sales Order", {"custom_addendum_to": doc.custom_addendum_to, "name": ["!=", doc.name]}
	)
	doc.custom_addendum_reference_no = f"{doc.custom_addendum_to}-M{existing_addenda + 1}"
