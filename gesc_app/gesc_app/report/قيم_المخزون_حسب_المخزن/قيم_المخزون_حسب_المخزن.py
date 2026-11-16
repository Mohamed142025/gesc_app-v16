# Copyright (c) 2026, mohamed sayed and contributors
# For license information, please see license.txt

"""قيم المخزون حسب المخزن: each warehouse's stock value, with its project.

From the stock ledger (the value each entry adds or takes away): what came in is debit, what
went out credit, and the balance is debit less credit. Opening is everything before the
"from" date, the period is from - to, and closing is opening and period together (the
warehouse's stock value on the "to" date).

A group warehouse chooses the warehouses under it. A warehouse with no value in any column
is left out unless "show empty warehouses" is ticked.
"""

import frappe
from frappe import _
from frappe.utils import flt

PARTS = (("opening", "افتتاحي"), ("period", "الفترة"), ("closing", "ختامي"))


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.from_date and filters.to_date and filters.from_date > filters.to_date:
		frappe.throw(_("تاريخ البداية بعد تاريخ النهاية."))
	return get_columns(), get_data(filters)


def get_columns():
	columns = [
		{"fieldname": "warehouse", "label": _("المخزن"), "fieldtype": "Link", "options": "Warehouse", "width": 260},
		{"fieldname": "project_name", "label": _("اسم المشروع"), "fieldtype": "Data", "width": 220},
	]
	for key, label in PARTS:
		for side, side_label in (("debit", "مدين"), ("credit", "دائن"), ("balance", "رصيد")):
			columns.append(
				{
					"fieldname": f"{key}_{side}",
					"label": f"{label} {side_label}",
					"fieldtype": "Currency",
					"options": "currency",
					"width": 130,
				}
			)
	columns.append({"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1})
	return columns


def get_warehouses(filters):
	conditions = {"company": filters.company, "is_group": 0}
	if filters.warehouse:
		lft, rgt = frappe.db.get_value("Warehouse", filters.warehouse, ["lft", "rgt"])
		conditions.update({"lft": (">=", lft), "rgt": ("<=", rgt)})
	if filters.project:
		conditions["custom_project"] = filters.project
	return frappe.get_all("Warehouse", filters=conditions, fields=["name", "custom_project"], order_by="lft asc")


def get_data(filters):
	warehouses = get_warehouses(filters)
	if not warehouses:
		return []
	sle = frappe.qb.DocType("Stock Ledger Entry")
	from frappe.query_builder.functions import Sum
	from pypika.terms import Case

	value = sle.stock_value_difference
	before = sle.posting_date < filters.from_date
	rows = (
		frappe.qb.from_(sle)
		.select(
			sle.warehouse,
			Sum(Case().when(before & (value > 0), value).else_(0)).as_("opening_debit"),
			Sum(Case().when(before & (value < 0), -value).else_(0)).as_("opening_credit"),
			Sum(Case().when(~before & (value > 0), value).else_(0)).as_("period_debit"),
			Sum(Case().when(~before & (value < 0), -value).else_(0)).as_("period_credit"),
		)
		.where(
			(sle.is_cancelled == 0)
			& (sle.company == filters.company)
			& (sle.posting_date <= filters.to_date)
			& (sle.warehouse.isin([w.name for w in warehouses]))
		)
		.groupby(sle.warehouse)
		.run(as_dict=True)
	)
	values = {row.warehouse: row for row in rows}
	projects = {w.custom_project for w in warehouses if w.custom_project}
	project_names = dict(
		frappe.get_all("Project", filters={"name": ("in", list(projects))}, fields=["name", "project_name"], as_list=True)
	) if projects else {}
	currency = frappe.get_cached_value("Company", filters.company, "default_currency")

	data = []
	for warehouse in warehouses:
		v = values.get(warehouse.name) or frappe._dict()
		row = {
			"project_name": project_names.get(warehouse.custom_project, warehouse.custom_project or ""),
			"warehouse": warehouse.name,
			"currency": currency,
			"opening_debit": flt(v.opening_debit),
			"opening_credit": flt(v.opening_credit),
			"period_debit": flt(v.period_debit),
			"period_credit": flt(v.period_credit),
		}
		row["closing_debit"] = row["opening_debit"] + row["period_debit"]
		row["closing_credit"] = row["opening_credit"] + row["period_credit"]
		for key, _label in PARTS:
			row[f"{key}_balance"] = row[f"{key}_debit"] - row[f"{key}_credit"]
		if not filters.show_empty and not any(
			abs(row[f"{key}_{side}"]) >= 0.005 for key, _l in PARTS for side in ("debit", "credit", "balance")
		):
			continue
		data.append(row)
	return data
