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

	if doc.custom_is_addendum and not doc.custom_addendum_to:
		frappe.throw(_("Please select the Main Contract for this addendum."))

	if not doc.custom_addendum_to:
		return

	if not doc.is_new() and not doc.has_value_changed("custom_addendum_to"):
		return

	main_contract = frappe.db.get_value(
		"Sales Order",
		doc.custom_addendum_to,
		["customer", "custom_is_main_contract"],
		as_dict=True,
	)

	if not main_contract or not main_contract.custom_is_main_contract:
		frappe.throw(_("{0} is not marked as a Main Contract.").format(doc.custom_addendum_to))

	if main_contract.customer != doc.customer:
		frappe.throw(
			_("The addendum must have the same Customer as the Main Contract {0}.").format(
				doc.custom_addendum_to
			)
		)

	if doc.is_new():
		# Already named by set_addendum_name; an amended addendum keeps the reference of
		# the one it amends.
		doc.custom_addendum_reference_no = doc.custom_addendum_reference_no or doc.name
		return

	doc.custom_addendum_reference_no = get_next_addendum_name(doc)


def set_addendum_name(doc, method=None):
	"""Name a new addendum after its Main Contract ({contract}-M1, -M2 ...) while the
	document is being named. Renaming it later, in validate, left its item and payment
	schedule rows under the discarded name."""
	if doc.get("custom_addendum_to"):
		doc.name = doc.custom_addendum_reference_no = get_next_addendum_name(doc)


def get_next_addendum_name(doc):
	filters = {"custom_addendum_to": doc.custom_addendum_to}
	if doc.name:
		filters["name"] = ["!=", doc.name]

	addendum_number = frappe.db.count("Sales Order", filters) + 1
	addendum_name = f"{doc.custom_addendum_to}-M{addendum_number}"
	while frappe.db.exists("Sales Order", addendum_name):
		addendum_number += 1
		addendum_name = f"{doc.custom_addendum_to}-M{addendum_number}"

	return addendum_name
