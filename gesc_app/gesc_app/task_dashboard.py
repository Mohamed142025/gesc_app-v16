from frappe import _


def get_data(data):
	# Quotations made from a pre-quotation inspection point back to it.
	data.setdefault("non_standard_fieldnames", {})["Quotation"] = "custom_task"
	data.setdefault("transactions", []).append({"label": _("Quotation"), "items": ["Quotation"]})
	return data
