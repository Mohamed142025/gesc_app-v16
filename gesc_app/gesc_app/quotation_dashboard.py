from frappe import _


def get_data(data):
	data.setdefault("non_standard_fieldnames", {})["Task"] = "custom_quotation"
	data.setdefault("transactions", []).append({"label": _("Tasks"), "items": ["Task"]})
	return data
