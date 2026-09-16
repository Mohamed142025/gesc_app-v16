import frappe

from gesc_app.gesc_app.progress_utils import (
	calculate_component_percent,
	calculate_line_qty,
	calculate_percent_complete,
	get_delivered_totals,
	refresh_project_item_contract_values,
	update_project_item_progress,
)


def get_project_item_for_row(project, item_code):
	"""البند is resolved automatically from the item already on the row plus
	the document's own project - no separate selection field needed."""

	if not project or not item_code:
		return None

	return frappe.db.get_value("Project Item", {"project": project, "item": item_code})


def calculate_line_values(doc, method=None):
	"""Runs on before_validate (ahead of ERPNext's own qty-not-zero check) so
	qty can be fully derived here: qty = (كمية التوريد × نسبة التوريد%) +
	(كمية التركيب × نسبة التركيب%). Also shows the البند's supply/install
	percentages and its previous/current completion breakdown per line."""

	for row in doc.items:
		project_item_name = get_project_item_for_row(doc.project, row.item_code)
		if not project_item_name:
			row.custom_supply_percent = 0
			row.custom_install_percent = 0
			row.custom_previous_supply_percent = 0
			row.custom_previous_install_percent = 0
			row.custom_previous_completion_percent = 0
			row.custom_item_completion_percent = 0
			continue

		refresh_project_item_contract_values(project_item_name)

		pi = frappe.db.get_value(
			"Project Item",
			project_item_name,
			["quantity", "supply_weight_percent", "installation_weight_percent", "percent_complete"],
			as_dict=True,
		)

		row.custom_supply_percent = pi.supply_weight_percent
		row.custom_install_percent = pi.installation_weight_percent

		row.qty = calculate_line_qty(
			row.custom_supply_qty, row.custom_install_qty, pi.supply_weight_percent, pi.installation_weight_percent
		)

		committed_supplied, committed_installed = get_delivered_totals(
			project_item_name, exclude_delivery_note=doc.name
		)

		row.custom_previous_supply_percent = calculate_component_percent(committed_supplied, pi.quantity)
		row.custom_previous_install_percent = calculate_component_percent(committed_installed, pi.quantity)
		row.custom_previous_completion_percent = pi.percent_complete
		row.custom_item_completion_percent = calculate_percent_complete(
			pi.quantity,
			pi.supply_weight_percent,
			pi.installation_weight_percent,
			committed_supplied + frappe.utils.flt(row.custom_supply_qty),
			committed_installed + frappe.utils.flt(row.custom_install_qty),
		)


def sync_project_item_progress_on_submit(doc, method=None):
	_sync_affected_project_items(doc)


def sync_project_item_progress_on_cancel(doc, method=None):
	_sync_affected_project_items(doc)


def _sync_affected_project_items(doc):
	project_items = set()
	for row in doc.items:
		project_item_name = get_project_item_for_row(doc.project, row.item_code)
		if project_item_name:
			project_items.add(project_item_name)

	for project_item_name in project_items:
		update_project_item_progress(project_item_name)


@frappe.whitelist()
def preview_project_item_completion(project, item_code, supply_qty, install_qty, delivery_note=None):
	"""Live preview as the user types quantities on a draft Work Completion
	Note line. البند is resolved from item_code + project; refreshed from the
	live contract first so the preview is never based on a stale record."""

	project_item_name = get_project_item_for_row(project, item_code)
	if not project_item_name:
		return {
			"qty": 0,
			"supply_percent": 0,
			"install_percent": 0,
			"previous_supply_percent": 0,
			"previous_install_percent": 0,
			"previous": 0,
			"current": 0,
		}

	refresh_project_item_contract_values(project_item_name)

	pi = frappe.db.get_value(
		"Project Item",
		project_item_name,
		["quantity", "supply_weight_percent", "installation_weight_percent", "percent_complete"],
		as_dict=True,
	)

	committed_supplied, committed_installed = get_delivered_totals(
		project_item_name, exclude_delivery_note=delivery_note
	)

	current = calculate_percent_complete(
		pi.quantity,
		pi.supply_weight_percent,
		pi.installation_weight_percent,
		committed_supplied + frappe.utils.flt(supply_qty),
		committed_installed + frappe.utils.flt(install_qty),
	)
	qty = calculate_line_qty(supply_qty, install_qty, pi.supply_weight_percent, pi.installation_weight_percent)

	return {
		"qty": qty,
		"supply_percent": pi.supply_weight_percent,
		"install_percent": pi.installation_weight_percent,
		"previous_supply_percent": calculate_component_percent(committed_supplied, pi.quantity),
		"previous_install_percent": calculate_component_percent(committed_installed, pi.quantity),
		"previous": pi.percent_complete,
		"current": current,
	}
