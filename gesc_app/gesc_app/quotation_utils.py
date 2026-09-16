import frappe
from frappe.model.mapper import get_mapped_doc


@frappe.whitelist()
def make_task(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.subject = source.custom_project_name or source.name
		target.custom_quotation = source.name

	target_doc = get_mapped_doc(
		"Quotation",
		source_name,
		{
			"Quotation": {
				"doctype": "Task",
			}
		},
		target_doc,
		set_missing_values,
	)
	return target_doc
