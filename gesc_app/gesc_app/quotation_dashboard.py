from frappe import _


def get_data(data):
	non_standard_fieldnames = data.setdefault("non_standard_fieldnames", {})
	non_standard_fieldnames["Task"] = "custom_quotation"
	non_standard_fieldnames["Quotation"] = "custom_addendum_to"
	transactions = data.setdefault("transactions", [])
	transactions.append({"label": _("Tasks"), "items": ["Task"]})
	transactions.append({"label": _("ملاحق"), "items": ["Quotation"]})
	return data
