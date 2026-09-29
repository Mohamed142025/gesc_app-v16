from frappe import _


def get_data(data):
	# Quotations made from a pre-quotation inspection, and Material Requests raised from
	# execution items or an approved material submittal, point back to the task.
	fieldnames = data.setdefault("non_standard_fieldnames", {})
	fieldnames["Quotation"] = "custom_task"
	fieldnames["Material Request"] = "custom_task"
	data.setdefault("transactions", []).append({"label": _("Quotation"), "items": ["Quotation"]})
	data["transactions"].append({"label": _("Material Request"), "items": ["Material Request"]})
	return data
