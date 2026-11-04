# Copyright (c) 2026, mohamed sayed and contributors
# For license information, please see license.txt

"""الموقف المالي للعقود: for each customer, their projects, the contracts (Sales Orders) of
each project with their addenda, and the statements (Sales Invoices) of each contract.

- The down payment is what was actually paid on the contract (the Sales Order's advance).
- Each statement recovers its share of the down payment: its value times the contract's
  down payment percentage, until the down payment paid is recovered.
- Due on a statement: its value less the down payment it recovers; collected: what was
  received against it, other than the down payment itself.
- Paid on a contract: its down payment and what was collected on its statements.
- The project's cost: its actual expenses, from the general ledger (each expense once,
  whatever document it came from).

The statement dates filter the statements, and so does "unpaid only" (those with
something left to collect, and the contracts they are on); the contracts' own figures (value, down
payment, paid, balance) are always whole.

"Include projects without contracts": the statements of a project not made from a contract
(no Sales Order on their items), under the project with no contract; they have no down
payment, and the project's margin is then on what was invoiced. "Projects without
contracts only": those alone.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

ADVANCE_PERCENTAGE = "نسبة"
ADVANCE_AMOUNT = "قيمة"

# The amounts, and which rows have them.
CONTRACT_FIGURES = ("contract_value", "advance_paid", "total_paid", "contract_balance")
STATEMENT_FIGURES = ("invoiced", "recovered", "due", "collected", "invoice_balance")
PROJECT_FIGURES = ("cost", "margin")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	contracts = {} if filters.without_contracts_only else get_contracts(filters)
	statements = get_statements(contracts, filters) if contracts else {}
	if filters.unpaid_only:
		contracts = with_unpaid(contracts, statements)
	loose = get_uncontracted(filters)
	if not contracts and not loose:
		return get_columns(), [], None, None, None
	project_names = {c.project for c in contracts.values() if c.project} | {project for _customer, project in loose}
	costs = get_costs(filters.company, project_names)
	data, totals, projects = build_tree(contracts, statements, loose, costs, filters.company)
	return get_columns(), data, None, get_chart(projects), get_summary(totals, data)


def get_columns():
	currency = {"fieldtype": "Currency", "options": "currency", "width": 140}
	return [
		{"fieldname": "label", "label": _("Particulars"), "fieldtype": "Data", "width": 300},
		{"fieldname": "row_type", "label": _("Row Type"), "fieldtype": "Data", "width": 90},
		{"fieldname": "reference_doctype", "label": _("Document Type"), "fieldtype": "Data", "hidden": 1},
		{"fieldname": "reference", "label": _("Reference"), "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 170},
		{"fieldname": "date", "label": _("Entry Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "contract_value", "label": _("Contract Value"), **currency},
		{"fieldname": "advance_percentage", "label": _("Down Payment %"), "fieldtype": "Percent", "width": 110},
		{"fieldname": "advance_paid", "label": _("Down Payment Paid"), **currency},
		{"fieldname": "invoiced", "label": _("Progress Statement Value"), **currency},
		{"fieldname": "recovered", "label": _("Recovered from Down Payment"), **currency},
		{"fieldname": "due", "label": _("Balance Due"), **currency},
		{"fieldname": "collected", "label": _("Collected on Progress Statement"), **currency},
		{"fieldname": "invoice_balance", "label": _("Remaining on Progress Statement"), **currency},
		{"fieldname": "total_paid", "label": _("Total Paid on Contract"), **currency},
		{"fieldname": "contract_balance", "label": _("Balance Due on Contract"), **currency},
		{"fieldname": "cost", "label": _("Project Cost"), **currency},
		{"fieldname": "margin", "label": _("Margin"), **currency},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


# Contracts


def get_contracts(filters):
	"""The main contracts the filters choose, and their addenda (by name)."""
	conditions = ["docstatus = 1", "company = %(company)s", "ifnull(custom_addendum_to, '') = ''"]
	if filters.customer:
		conditions.append("customer = %(customer)s")
	if filters.project:
		conditions.append("project = %(project)s")
	if filters.sales_order:
		# An addendum chosen stands for its contract.
		filters.contract = frappe.db.get_value("Sales Order", filters.sales_order, "custom_addendum_to") or filters.sales_order
		conditions.append("name = %(contract)s")
	if filters.contract_from_date:
		conditions.append("transaction_date >= %(contract_from_date)s")
	if filters.contract_to_date:
		conditions.append("transaction_date <= %(contract_to_date)s")

	fields = """name, customer, customer_name, project, transaction_date, grand_total, base_grand_total,
		advance_paid, custom_advance_type, custom_advance_percentage, custom_advance_amount,
		custom_addendum_to, custom_project_name"""
	main = frappe.db.sql(
		f"select {fields} from `tabSales Order` where {' and '.join(conditions)} order by transaction_date, name",
		filters,
		as_dict=True,
	)
	if not main:
		return {}
	addenda = frappe.db.sql(
		f"""select {fields} from `tabSales Order`
		where docstatus = 1 and custom_addendum_to in %(main)s order by transaction_date, name""",
		{"main": [c.name for c in main]},
		as_dict=True,
	)
	contracts = {}
	for contract in main + addenda:
		rate = flt(contract.base_grand_total) / flt(contract.grand_total) if flt(contract.grand_total) else 1
		contract.update(
			value=flt(contract.base_grand_total),
			# In the party's currency on the order.
			advance=flt(contract.advance_paid) * rate,
			percentage=advance_percentage(contract),
			addenda=[],
		)
		contracts[contract.name] = contract
	for addendum in addenda:
		contracts[addendum.custom_addendum_to].addenda.append(addendum.name)
	return contracts


def advance_percentage(contract):
	if contract.custom_advance_type == ADVANCE_PERCENTAGE:
		return flt(contract.custom_advance_percentage)
	if contract.custom_advance_type == ADVANCE_AMOUNT and flt(contract.grand_total):
		return flt(contract.custom_advance_amount) / flt(contract.grand_total) * 100
	return 0


# Statements


def get_statements(contracts, filters):
	"""Each contract's statements, oldest first, with the down payment each recovers and
	what was collected on it; those the statement dates leave out are marked hidden."""
	rows = frappe.db.sql(
		"""
		select item.sales_order, invoice.name, invoice.posting_date, invoice.custom_statement_title,
			invoice.is_return, invoice.base_grand_total, invoice.base_net_total,
			sum(item.base_net_amount) as net
		from `tabSales Invoice Item` item
		inner join `tabSales Invoice` invoice on invoice.name = item.parent
		where invoice.docstatus = 1 and item.sales_order in %(contracts)s
		group by item.sales_order, invoice.name
		order by invoice.posting_date, invoice.name
		""",
		{"contracts": list(contracts)},
		as_dict=True,
	)
	collected = get_collections({row.name for row in rows})
	advances = get_advance_vouchers(contracts)
	from_date = getdate(filters.statement_from_date) if filters.statement_from_date else None
	to_date = getdate(filters.statement_to_date) if filters.statement_to_date else None

	statements = {name: [] for name in contracts}
	recovered_so_far = {name: 0 for name in contracts}
	for row in rows:
		contract = contracts[row.sales_order]
		# An invoice of several contracts: each its share, by the items' amounts.
		share = flt(row.net) / flt(row.base_net_total) if flt(row.base_net_total) else 1
		value = flt(row.base_grand_total) * share
		# Recovered at the contract's percentage, never beyond the down payment paid.
		before = recovered_so_far[row.sales_order]
		after = min(max(before + value * contract.percentage / 100, 0), contract.advance)
		recovered_so_far[row.sales_order] = after
		received = sum(
			amount for voucher, amount in collected.get(row.name, {}).items() if voucher not in advances[row.sales_order]
		) * share
		row.update(
			value=value,
			recovered=after - before,
			due=value - (after - before),
			collected=received,
			hidden=bool(
				(from_date and getdate(row.posting_date) < from_date)
				or (to_date and getdate(row.posting_date) > to_date)
				or (filters.unpaid_only and value - (after - before) - received < 0.005)
			),
		)
		statements[row.sales_order].append(row)
	return statements


def get_uncontracted(filters):
	"""The visible statements of projects with no contract on them, by (customer, project).
	Not when a contract or contract dates are chosen: they have no contract."""
	if not (filters.without_contracts or filters.without_contracts_only) or filters.sales_order or filters.contract_from_date or filters.contract_to_date:
		return {}
	conditions = ["invoice.docstatus = 1", "invoice.company = %(company)s", "ifnull(item.sales_order, '') = ''"]
	project = "coalesce(nullif(item.project, ''), invoice.project)"
	conditions.append(f"ifnull({project}, '') != ''")
	if filters.customer:
		conditions.append("invoice.customer = %(customer)s")
	if filters.project:
		conditions.append(f"{project} = %(project)s")
	rows = frappe.db.sql(
		f"""
		select {project} as project, invoice.customer, invoice.customer_name, invoice.name, invoice.posting_date,
			invoice.custom_statement_title, invoice.is_return, invoice.base_grand_total, invoice.base_net_total,
			sum(item.base_net_amount) as net
		from `tabSales Invoice Item` item
		inner join `tabSales Invoice` invoice on invoice.name = item.parent
		where {' and '.join(conditions)}
		group by {project}, invoice.name
		order by invoice.posting_date, invoice.name
		""",
		filters,
		as_dict=True,
	)
	collected = get_collections({row.name for row in rows})
	from_date = getdate(filters.statement_from_date) if filters.statement_from_date else None
	to_date = getdate(filters.statement_to_date) if filters.statement_to_date else None

	loose = {}
	for row in rows:
		share = flt(row.net) / flt(row.base_net_total) if flt(row.base_net_total) else 1
		value = flt(row.base_grand_total) * share
		received = sum(collected.get(row.name, {}).values()) * share
		if (
			(from_date and getdate(row.posting_date) < from_date)
			or (to_date and getdate(row.posting_date) > to_date)
			or (filters.unpaid_only and value - received < 0.005)
		):
			continue
		row.update(value=value, recovered=0, due=value, collected=received)
		loose.setdefault((row.customer, row.project), []).append(row)
	return loose


def with_unpaid(contracts, statements):
	"""The main contracts with an unpaid statement on them or on an addendum, and their
	addenda."""
	def unpaid(name):
		return any(not statement.hidden for statement in statements[name])

	keep = {
		name
		for name, contract in contracts.items()
		if not contract.custom_addendum_to and (unpaid(name) or any(unpaid(a) for a in contract.addenda))
	}
	return {
		name: contract for name, contract in contracts.items() if name in keep or contract.custom_addendum_to in keep
	}


def get_collections(invoices):
	"""What was received against each invoice, by the voucher it came with."""
	if not invoices:
		return {}
	collected = {}
	for row in frappe.db.sql(
		"""
		select against_voucher_no, voucher_no, sum(amount) as amount
		from `tabPayment Ledger Entry`
		where against_voucher_type = 'Sales Invoice' and against_voucher_no in %(invoices)s
			and voucher_type in ('Payment Entry', 'Journal Entry') and delinked = 0
		group by against_voucher_no, voucher_no
		""",
		{"invoices": list(invoices)},
		as_dict=True,
	):
		# Received: credited to the customer's account.
		collected.setdefault(row.against_voucher_no, {})[row.voucher_no] = -flt(row.amount)
	return collected


def get_advance_vouchers(contracts):
	"""The payments of each contract's down payment: counted in its down payment, so not
	again when allocated to its statements."""
	vouchers = {name: set() for name in contracts}
	for row in frappe.db.sql(
		"""
		select distinct against_voucher_no, voucher_no from `tabAdvance Payment Ledger Entry`
		where against_voucher_type = 'Sales Order' and against_voucher_no in %(contracts)s and delinked = 0
		""",
		{"contracts": list(contracts)},
		as_dict=True,
	):
		vouchers[row.against_voucher_no].add(row.voucher_no)
	return vouchers


# Costs


def get_costs(company, projects):
	"""Each project's actual expenses: what was booked to its expense accounts."""
	if not projects:
		return {}
	return dict(
		frappe.db.sql(
			"""
			select entry.project, sum(entry.debit - entry.credit)
			from `tabGL Entry` entry
			inner join `tabAccount` account on account.name = entry.account
			where entry.is_cancelled = 0 and entry.company = %(company)s
				and account.root_type = 'Expense' and entry.project in %(projects)s
			group by entry.project
			""",
			{"company": company, "projects": list(projects)},
		)
	)


# The tree


def build_tree(contracts, statements, loose, costs, company):
	currency = frappe.get_cached_value("Company", company, "default_currency")
	customers = {}
	for contract in contracts.values():
		if contract.custom_addendum_to:
			continue
		customer = customers.setdefault(contract.customer, {"name": contract.customer_name or contract.customer, "projects": {}})
		customer["projects"].setdefault(contract.project or "", []).append(contract)
	for (customer_id, project), rows in loose.items():
		customer = customers.setdefault(customer_id, {"name": rows[0].customer_name or customer_id, "projects": {}})
		customer["projects"].setdefault(project, [])

	data, projects = [], []
	totals = frappe._dict()
	for customer_id, customer in sorted(customers.items(), key=lambda item: item[1]["name"]):
		customer_row = row(f"c:{customer_id}", None, 0, customer["name"], "Customer", "Customer", customer_id)
		data.append(customer_row)
		for project, members in customer["projects"].items():
			project_row = row(
				f"p:{customer_id}:{project}", customer_row["id"], 1, project_title(project, members), "Project",
				"Project" if project else None, project or None,
			)
			data.append(project_row)
			for contract in members:
				contract_row = contract_rows(contract, contracts, statements, project_row["id"], data)
				add(project_row, contract_row, CONTRACT_FIGURES + STATEMENT_FIGURES)
			for statement in loose.get((customer_id, project), []):
				line = statement_row(statement, f"i:{project}:{statement.name}", project_row["id"], 2)
				data.append(line)
				add(project_row, line, STATEMENT_FIGURES)
				project_row["total_paid"] += statement.collected
			if project:
				project_row["cost"] = flt(costs.get(project))
				# With no contract, on what was invoiced.
				income = project_row["contract_value"] or project_row["invoiced"]
				project_row["margin"] = income - project_row["cost"]
				projects.append(project_row)
			add(customer_row, project_row, CONTRACT_FIGURES + STATEMENT_FIGURES + PROJECT_FIGURES)
		add(totals, customer_row, CONTRACT_FIGURES + STATEMENT_FIGURES + PROJECT_FIGURES)
	for entry in data:
		entry["currency"] = currency
	totals.currency = currency
	return data, totals, projects


def contract_rows(contract, contracts, statements, parent, data):
	"""The contract with its addenda under it, each with its statements; the contract's
	figures are its own and its addenda's."""
	main = contract_row(contract, statements, parent, 2, data)
	for name in contract.addenda:
		addendum = contract_row(contracts[name], statements, main["id"], 3, data)
		add(main, addendum, CONTRACT_FIGURES + STATEMENT_FIGURES)
	if main.get("contract_value"):
		main["contract_balance"] = main["contract_value"] - main["total_paid"]
	return main


def contract_row(contract, statements, parent, indent, data):
	entry = row(
		f"s:{contract.name}", parent, indent, contract.name, "Contract Addendum" if contract.custom_addendum_to else "Contract",
		"Sales Order", contract.name, contract.transaction_date,
	)
	entry.update(contract_value=contract.value, advance_percentage=contract.percentage, advance_paid=contract.advance)
	data.append(entry)
	all_collected = 0
	for statement in statements[contract.name]:
		all_collected += statement.collected
		if statement.hidden:
			continue
		line = statement_row(statement, f"i:{contract.name}:{statement.name}", entry["id"], indent + 1)
		data.append(line)
		add(entry, line, STATEMENT_FIGURES)
	# The contract's payments, whatever the statement dates.
	entry["total_paid"] = contract.advance + all_collected
	entry["contract_balance"] = contract.value - entry["total_paid"]
	return entry


def statement_row(statement, id, parent, indent):
	line = row(
		id, parent, indent, statement.custom_statement_title or statement.name,
		"Statement Return" if statement.is_return else "Progress Statement",
		"Sales Invoice", statement.name, statement.posting_date,
	)
	line.update(
		invoiced=statement.value,
		recovered=statement.recovered,
		due=statement.due,
		collected=statement.collected,
		invoice_balance=statement.due - statement.collected,
	)
	return line


def row(id, parent, indent, label, kind, doctype=None, name=None, date=None):
	return {
		"id": id,
		"parent_id": parent,
		"indent": indent,
		"label": label,
		# kind: Customer, Project, Contract, Contract Addendum, Progress Statement or Statement
		# Return; row_type: shown.
		"kind": kind,
		"row_type": _(kind),
		"reference_doctype": doctype,
		"reference": name,
		"date": date,
		**{field: 0 for field in CONTRACT_FIGURES + STATEMENT_FIGURES},
	}


def add(to, source, fields):
	for field in fields:
		to[field] = flt(to.get(field)) + flt(source.get(field))


def project_title(project, contracts):
	if not project:
		return _("No Project")
	title = frappe.db.get_value("Project", project, ["custom_project_name", "project_name"], as_dict=True) or {}
	return title.get("custom_project_name") or title.get("project_name") or project


# Charts


def get_chart(projects):
	if not projects:
		return None
	projects = sorted(projects, key=lambda p: p["contract_value"], reverse=True)[:12]
	return {
		"data": {
			"labels": [p["label"] for p in projects],
			"datasets": [
				{"name": _("Contract Values"), "values": [flt(p["contract_value"], 2) for p in projects]},
				{"name": _("Progress Statements"), "values": [flt(p["invoiced"], 2) for p in projects]},
				{"name": _("Paid"), "values": [flt(p["total_paid"], 2) for p in projects]},
				{"name": _("Project Costs"), "values": [flt(p["cost"], 2) for p in projects]},
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"colors": ["#0E3B2E", "#197B57", "#34D399", "#C2413B"],
		"barOptions": {"spaceRatio": 0.4},
	}


def get_summary(totals, data):
	currency = totals.currency

	def card(label, value, indicator="Blue"):
		return {"label": _(label), "value": flt(value, 2), "datatype": "Currency", "currency": currency, "indicator": indicator}

	def owing(value):
		# Frappe colours a card green, red or blue only.
		return "Red" if flt(value) > 0.005 else "Green"

	def count(label, kind, only_linked=False):
		# The "No Project" rows group contracts without a project: not a project.
		value = sum(1 for entry in data if entry["kind"] == kind and (entry["reference"] or not only_linked))
		return {"label": _(label), "value": value, "datatype": "Int", "indicator": "Grey"}

	return [
		count("No. of Customers", "Customer"),
		count("No. of Projects", "Project", only_linked=True),
		count("No. of Contracts", "Contract"),
		count("No. of Progress Statements", "Progress Statement"),
		card("Contract Values", totals.contract_value),
		card("Down Payments Paid", totals.advance_paid, "Green"),
		card("Progress Statements", totals.invoiced),
		card("Collected on Progress Statements", totals.collected, "Green"),
		card("Remaining on Progress Statements", totals.invoice_balance, owing(totals.invoice_balance)),
		card("Balance Due on Contracts", totals.contract_balance, owing(totals.contract_balance)),
		card("Projects Cost", totals.cost, "Red"),
		card("Margin", totals.margin, "Green" if flt(totals.margin) >= 0 else "Red"),
	]
