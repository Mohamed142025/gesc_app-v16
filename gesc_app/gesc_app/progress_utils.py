import frappe
from frappe.utils import flt


def get_contract_values(project, item_code):
	"""Read quantity and the manually-set supply/install percentages for this
	item from the project's submitted Sales Order(s) - the percentages are
	entered by hand on the Sales Order Item, never auto-calculated."""

	rows = frappe.db.sql(
		"""
		select soi.qty, soi.custom_supply_percent, soi.custom_install_percent
		from `tabSales Order Item` soi
		inner join `tabSales Order` so on so.name = soi.parent
		where so.project = %(project)s and soi.item_code = %(item_code)s and so.docstatus = 1
		order by so.creation asc
		""",
		{"project": project, "item_code": item_code},
		as_dict=True,
	)

	if not rows:
		return 0.0, 0.0, 0.0

	total_qty = sum(flt(r.qty) for r in rows)
	# the percentages are set once on the main contract line and carried by any
	# addenda for the same item; use the first (main contract) row's split
	first = rows[0]
	return total_qty, flt(first.custom_supply_percent), flt(first.custom_install_percent)


def refresh_project_item_contract_values(project_item_name):
	pi = frappe.db.get_value("Project Item", project_item_name, ["project", "item"], as_dict=True)
	if not pi:
		return

	quantity, supply_weight, install_weight = get_contract_values(pi.project, pi.item)
	frappe.db.set_value(
		"Project Item",
		project_item_name,
		{
			"quantity": quantity,
			"supply_weight_percent": supply_weight,
			"installation_weight_percent": install_weight,
		},
	)
	update_project_item_progress(project_item_name)


def refresh_project_items_for_sales_order(sales_order_project, item_codes):
	if not sales_order_project:
		return

	project_items = frappe.get_all(
		"Project Item",
		filters={"project": sales_order_project, "item": ["in", item_codes]},
		pluck="name",
	)
	for project_item_name in project_items:
		refresh_project_item_contract_values(project_item_name)


def get_delivered_totals(project_item_name, exclude_delivery_note=None):
	"""Sum supplied/installed quantities from submitted Work Completion Notes
	(Delivery Note) for this البند. البند isn't picked on the row directly -
	it's resolved the same way the Delivery Note does: by (project, item).
	`exclude_delivery_note` lets a draft preview its own resulting percentage
	without double-counting itself."""

	pi = frappe.db.get_value("Project Item", project_item_name, ["project", "item"], as_dict=True)
	if not pi:
		return 0.0, 0.0

	conditions = [
		"dn.project = %(project)s",
		"dni.item_code = %(item_code)s",
		"dn.docstatus = 1",
	]
	values = {"project": pi.project, "item_code": pi.item}

	if exclude_delivery_note:
		conditions.append("dn.name != %(exclude)s")
		values["exclude"] = exclude_delivery_note

	result = frappe.db.sql(
		f"""
		select sum(dni.custom_supply_qty) as supplied, sum(dni.custom_install_qty) as installed
		from `tabDelivery Note Item` dni
		inner join `tabDelivery Note` dn on dn.name = dni.parent
		where {" and ".join(conditions)}
		""",
		values,
		as_dict=True,
	)[0]

	return flt(result.supplied), flt(result.installed)


def calculate_line_qty(supply_qty, install_qty, supply_percent, install_percent):
	"""qty = (كمية التوريد × نسبة التوريد%) + (كمية التركيب × نسبة التركيب%)"""

	return flt(supply_qty) * flt(supply_percent) / 100 + flt(install_qty) * flt(install_percent) / 100


def calculate_component_percent(committed_qty, quantity):
	"""نسبة إنجاز مكون واحد (توريد أو تركيب) لوحده، بدون وزن - كام % من
	الكمية المتعاقد عليها اتنفذ فعلياً لهذا المكون."""

	if not quantity:
		return 0.0
	return min(flt(committed_qty) / flt(quantity) * 100, 100.0)


def calculate_percent_complete(quantity, supply_weight_percent, installation_weight_percent, supplied, installed):
	if not quantity:
		return 0.0

	supply_pct = (supplied / quantity) * flt(supply_weight_percent)
	install_pct = (installed / quantity) * flt(installation_weight_percent)
	return min(supply_pct + install_pct, 100.0)


def update_project_item_progress(project_item_name):
	pi = frappe.db.get_value(
		"Project Item",
		project_item_name,
		["quantity", "supply_weight_percent", "installation_weight_percent", "building"],
		as_dict=True,
	)
	if not pi:
		return

	supplied, installed = get_delivered_totals(project_item_name)
	percent_complete = calculate_percent_complete(
		pi.quantity, pi.supply_weight_percent, pi.installation_weight_percent, supplied, installed
	)

	frappe.db.set_value(
		"Project Item",
		project_item_name,
		{
			"total_supplied_qty": supplied,
			"total_installed_qty": installed,
			"percent_complete": percent_complete,
		},
	)

	if pi.building:
		update_building_progress(pi.building)


def update_building_progress(building_name):
	if not frappe.db.exists("Project Building", building_name):
		return

	items_progress = frappe.get_all(
		"Project Item", filters={"building": building_name}, pluck="percent_complete"
	)
	percent_complete = flt(sum(items_progress) / len(items_progress)) if items_progress else 0

	frappe.db.set_value("Project Building", building_name, "percent_complete", percent_complete)
