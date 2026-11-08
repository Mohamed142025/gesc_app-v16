# Copyright (c) 2026, mohamed sayed and contributors
# For license information, please see license.txt

"""كشف حساب: what came into an account, what went out, and what is left, from the ledger.

Opens on the custody accounts (the ledgers under group 1205 named عهد); the scope or the
accounts filter takes it to any account. In is a debit, out a credit, the balance in less out.

Each account shows its movements with a running balance, one per voucher, party and side.
Under a movement are the accounts on the other side of its voucher: where the money went or
came from. They are for reading and are not added up. When a voucher has several lines on
both sides nothing says which paid for which, so they show in full with a note; the "where
it went" chart shares them out by the movement's part of its side.

A custody account with an open balance is overdue when nothing has gone out of it for more
than the given days (counted from the first money in if nothing ever has). The overdue days
and the settled share mean nothing on other accounts, so they are for custody accounts only.

The cards and charts come back in the report's chart slot and are drawn by the report's JS.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.desk.query_report import get_report_doc
from frappe.utils import cint, date_diff, flt, getdate

REPORT_NAME = "كشف حساب"
CUSTODY_GROUP_NUMBER = "1205"
CUSTODY_NAME = "عهد"
SCOPE_ALL = "كل الحسابات"
TOP_BALANCES = 8
TOP_DESTINATIONS = 7
MAX_MONTHS = 12
REMARK_LENGTH = 120
VOUCHER_LABELS = {
	"Journal Entry": "قيد يومية",
	"Payment Entry": "سند دفع / قبض",
	"Purchase Invoice": "فاتورة مشتريات",
	"Sales Invoice": "فاتورة مبيعات",
	"Expense Claim": "مطالبة مصروفات",
	"Stock Entry": "حركة مخزنية",
	"Purchase Receipt": "إذن استلام",
	"Delivery Note": "إذن تسليم",
	"Stock Reconciliation": "تسوية مخزون",
	"Period Closing Voucher": "قيد إقفال",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	statements, destinations = get_statements(filters)
	if not statements:
		return get_columns(), []

	return (
		get_columns(),
		build_rows(statements),
		None,
		get_dashboard(filters, statements, destinations),
	)


@frappe.whitelist()
def get_destination_movements(filters, destination=None, others=0):
	"""The movements behind one bar of the "where it went" chart, largest first. "Others"
	is every account the chart does not name."""
	get_report_doc(REPORT_NAME)

	statements, destinations = get_statements(frappe._dict(frappe.parse_json(filters)))
	if cint(others):
		wanted = {label for label, _amount in rank_destinations(destinations)[TOP_DESTINATIONS:]}
	else:
		wanted = {destination}

	movements = [
		{
			"posting_date": movement.posting_date,
			"voucher_type": movement.voucher_type,
			"voucher_no": movement.voucher_no,
			"voucher_label": VOUCHER_LABELS.get(movement.voucher_type, movement.voucher_type),
			"from_account": statement.label,
			"destination": share.label,
			"party": share.party or movement.party,
			"remark": movement.remark,
			"amount": flt(share.amount, 2),
			# Several lines on both sides: the amount is this movement's share, not a line.
			"estimated": movement.several_on_both_sides,
		}
		for statement in statements
		for movement in statement.movements
		for share in movement.shares
		if share.label in wanted
	]
	return sorted(movements, key=lambda row: -row["amount"])


def get_statements(filters):
	"""The accounts' statements, each movement with the accounts on its other side, and
	how much went out to each account."""
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("تاريخ البداية بعد تاريخ النهاية."))

	destinations = defaultdict(float)
	accounts = get_accounts(filters)
	if not accounts:
		return [], destinations
	entries = get_entries(filters, accounts)
	statements = build_statements(filters, accounts, entries, get_custody_accounts(filters.company))
	if not statements:
		return [], destinations
	voucher_lines = get_voucher_lines(filters, statements)
	names = get_account_names({line.account for lines in voucher_lines.values() for line in lines}) | accounts
	for statement in statements:
		for movement in statement.movements:
			add_counter_accounts(movement, statement.account, voucher_lines, names, destinations)
	return statements, destinations


def selected_accounts(filters):
	accounts = filters.get("account") or []
	return frappe.parse_json(accounts) if isinstance(accounts, str) else accounts


def get_accounts(filters):
	"""{ledger: its name} for the chosen accounts (a group brings the ledgers under it), else
	the scope's."""
	account_filters = {"company": filters.company, "is_group": 0}
	selected = selected_accounts(filters)
	if selected:
		ranges = frappe.get_all(
			"Account", filters={"name": ("in", selected)}, fields=["lft", "rgt"], order_by="lft"
		)
		rows = []
		for row in ranges:
			rows += frappe.get_all(
				"Account",
				filters={**account_filters, "lft": (">=", row.lft), "rgt": ("<=", row.rgt)},
				fields=["name", "account_name"],
			)
	elif filters.get("scope") == SCOPE_ALL:
		rows = frappe.get_all("Account", filters=account_filters, fields=["name", "account_name"])
	else:
		return get_custody_accounts(filters.company)
	return {row.name: row.account_name.strip() for row in rows}


def get_custody_accounts(company):
	"""{ledger: its name} for the ledgers named عهد under the custody and advances group."""
	group = frappe.db.get_value(
		"Account",
		{"company": company, "account_number": CUSTODY_GROUP_NUMBER, "is_group": 1},
		["lft", "rgt"],
		as_dict=True,
	)
	if not group:
		return {}
	rows = frappe.get_all(
		"Account",
		filters={
			"company": company,
			"is_group": 0,
			"lft": (">", group.lft),
			"rgt": ("<", group.rgt),
			"account_name": ("like", f"%{CUSTODY_NAME}%"),
		},
		fields=["name", "account_name"],
	)
	return {row.name: row.account_name.strip() for row in rows}


def get_entries(filters, accounts):
	conditions = {
		"company": filters.company,
		"is_cancelled": 0,
		"account": ("in", list(accounts)),
		"posting_date": ("<=", filters.to_date),
	}
	if filters.get("party_type") and filters.get("party"):
		conditions.update(party_type=filters.party_type, party=filters.party)
	return frappe.get_all(
		"GL Entry",
		filters=conditions,
		fields=[
			"account",
			"posting_date",
			"voucher_type",
			"voucher_no",
			"party_type",
			"party",
			"debit",
			"credit",
			"remarks",
			"is_opening",
		],
		order_by="posting_date, creation",
	)


def build_statements(filters, accounts, entries, custody_accounts):
	"""A statement per account with anything to show, the largest open balance first."""
	from_date, to_date = getdate(filters.from_date), getdate(filters.to_date)
	statements = {}
	for entry in entries:
		statement = statements.setdefault(
			entry.account,
			frappe._dict(
				account=entry.account,
				label=accounts[entry.account],
				opening=0,
				total_in=0,
				total_out=0,
				groups={},
				first_in=None,
				last_out=None,
			),
		)
		debit, credit = flt(entry.debit), flt(entry.credit)
		if debit and not statement.first_in:
			statement.first_in = entry.posting_date
		if credit:
			statement.last_out = entry.posting_date

		if getdate(entry.posting_date) < from_date or entry.is_opening == "Yes":
			statement.opening += debit - credit
			continue

		for side, amount in (("in", debit), ("out", credit)):
			if not amount:
				continue
			key = (entry.voucher_type, entry.voucher_no, entry.party_type, entry.party, side)
			movement = statement.groups.setdefault(
				key,
				frappe._dict(
					posting_date=entry.posting_date,
					voucher_type=entry.voucher_type,
					voucher_no=entry.voucher_no,
					party_type=entry.party_type,
					party=entry.party,
					side=side,
					amount=0,
					remark=short_remark(entry.remarks),
				),
			)
			movement.amount += amount
			statement["total_" + side] += amount

	overdue_after = cint(filters.overdue_days)
	result = []
	for statement in statements.values():
		statement.movements = list(statement.groups.values())
		statement.closing = flt(statement.opening + statement.total_in - statement.total_out, 2)
		if not statement.movements and not flt(statement.opening, 2):
			continue
		since = statement.last_out or statement.first_in
		statement.is_custody = statement.account in custody_accounts
		statement.days_open = (
			date_diff(to_date, since) if statement.is_custody and statement.closing > 0 and since else None
		)
		statement.overdue = statement.days_open is not None and statement.days_open > overdue_after
		result.append(statement)
	return sorted(result, key=lambda s: -s.closing)


def short_remark(remarks):
	lines = (remarks or "").strip().splitlines()
	return lines[0][:REMARK_LENGTH] if lines else None


def get_voucher_lines(filters, statements):
	vouchers = {m.voucher_no for s in statements for m in s.movements}
	lines = defaultdict(list)
	if not vouchers:
		return lines
	for row in frappe.get_all(
		"GL Entry",
		filters={"company": filters.company, "is_cancelled": 0, "voucher_no": ("in", list(vouchers))},
		fields=["voucher_type", "voucher_no", "account", "party", "debit", "credit"],
	):
		lines[(row.voucher_type, row.voucher_no)].append(row)
	return lines


def get_account_names(accounts):
	return {
		row.name: row.account_name.strip()
		for row in frappe.get_all(
			"Account", filters={"name": ("in", list(accounts))}, fields=["name", "account_name"]
		)
	}


def add_counter_accounts(movement, account, voucher_lines, names, destinations):
	"""The accounts on the other side of the movement's voucher, as movement.counters."""
	lines = voucher_lines[(movement.voucher_type, movement.voucher_no)]
	own_field, other_field = ("debit", "credit") if movement.side == "in" else ("credit", "debit")
	own = defaultdict(float)
	other = defaultdict(float)
	for line in lines:
		own[(line.account, line.party)] += flt(line.get(own_field))
		if line.account != account:
			other[(line.account, line.party)] += flt(line.get(other_field))
	own = {key: amount for key, amount in own.items() if amount}
	other = {key: amount for key, amount in other.items() if amount}

	movement.several_on_both_sides = len(own) > 1 and len(other) > 1
	own_total = sum(own.values())
	movement.counters = [
		frappe._dict(
			label=names.get(key[0], key[0]),
			party=key[1],
			# The only line on the other side paid for this movement's part of it.
			amount=movement.amount if len(other) == 1 else amount,
		)
		for key, amount in sorted(other.items(), key=lambda item: -item[1])
	]
	movement.shares = []
	if movement.side == "out" and own_total:
		for key, amount in other.items():
			share = frappe._dict(
				label=names.get(key[0], key[0]), party=key[1], amount=amount * movement.amount / own_total
			)
			movement.shares.append(share)
			destinations[share.label] += share.amount


def build_rows(statements):
	rows = []
	totals = frappe._dict(opening=0, total_in=0, total_out=0, closing=0)
	for statement in statements:
		for field in totals:
			totals[field] += statement[field]
		rows.append(
			frappe._dict(
				description=statement.label,
				account=statement.account,
				row_kind="account",
				indent=0,
				amount_in=statement.total_in,
				amount_out=statement.total_out,
				balance=statement.closing,
				days_open=statement.days_open,
				overdue=statement.overdue,
			)
		)
		balance = statement.opening
		if flt(statement.opening, 2):
			rows.append(
				frappe._dict(description="رصيد أول المدة", row_kind="opening", indent=1, balance=flt(balance, 2))
			)
		for movement in statement.movements:
			amount_field = "amount_in" if movement.side == "in" else "amount_out"
			balance += movement.amount if movement.side == "in" else -movement.amount
			rows.append(
				frappe._dict(
					description=VOUCHER_LABELS.get(movement.voucher_type, movement.voucher_type),
					row_kind="movement",
					indent=1,
					posting_date=movement.posting_date,
					voucher_type=movement.voucher_type,
					voucher_no=movement.voucher_no,
					party=movement.party,
					remarks=(
						"⚠ القيد موزّع على أكثر من حساب في الجانبين؛ المبالغ أدناه كاملة."
						if movement.several_on_both_sides
						else movement.remark
					),
					balance=flt(balance, 2),
					**{amount_field: movement.amount},
				)
			)
			for counter in movement.counters:
				rows.append(
					frappe._dict(
						description=counter.label,
						row_kind="counter",
						indent=2,
						party=counter.party,
						**{amount_field: counter.amount},
					)
				)
	rows.append(
		frappe._dict(
			description="الإجمالي العام",
			row_kind="total",
			indent=0,
			amount_in=totals.total_in,
			amount_out=totals.total_out,
			balance=flt(totals.closing, 2),
		)
	)
	return rows


def get_dashboard(filters, statements, destinations):
	"""What the report's cards and charts show."""
	opening = sum(s.opening for s in statements)
	total_in = sum(s.total_in for s in statements)
	total_out = sum(s.total_out for s in statements)
	open_accounts = [s for s in statements if s.closing > 0]
	overdue = [s for s in statements if s.overdue]
	available = opening + total_in
	return {
		"closing": flt(sum(s.closing for s in statements), 2),
		"open_count": len(open_accounts),
		"negative_count": len([s for s in statements if s.closing < 0]),
		"total_in": flt(total_in, 2),
		"total_out": flt(total_out, 2),
		"settled_percent": (
			flt(total_out * 100 / available, 1) if available > 0 and all(s.is_custody for s in statements) else None
		),
		"overdue_count": len(overdue),
		"overdue_amount": flt(sum(s.closing for s in overdue), 2),
		"overdue_days": cint(filters.overdue_days),
		"balances": get_balances(open_accounts),
		"monthly": get_monthly(filters, statements),
		"destinations": get_destinations(destinations),
	}


def get_balances(open_accounts):
	balances = [
		{"account": s.account, "label": s.label, "amount": s.closing, "days": s.days_open, "overdue": s.overdue}
		for s in open_accounts[:TOP_BALANCES]
	]
	rest = open_accounts[TOP_BALANCES:]
	if rest:
		balances.append({"label": f"أخرى ({len(rest)})", "amount": flt(sum(s.closing for s in rest), 2)})
	return balances


def get_monthly(filters, statements):
	"""In and out for each month of the period, its last months when it is a long one."""
	months = defaultdict(lambda: [0, 0])
	for statement in statements:
		for movement in statement.movements:
			date = getdate(movement.posting_date)
			months[(date.year, date.month)][0 if movement.side == "in" else 1] += movement.amount

	first, last = getdate(filters.from_date), getdate(filters.to_date)
	year, month = first.year, first.month
	result = []
	while (year, month) <= (last.year, last.month):
		values = months[(year, month)]
		result.append(
			{"label": f"{month:02d}/{year % 100:02d}", "in": flt(values[0], 2), "out": flt(values[1], 2)}
		)
		year, month = (year + 1, 1) if month == 12 else (year, month + 1)
	return result[-MAX_MONTHS:]


def get_destinations(destinations):
	ranked = rank_destinations(destinations)
	result = [{"label": label, "amount": flt(amount, 2)} for label, amount in ranked[:TOP_DESTINATIONS]]
	rest = ranked[TOP_DESTINATIONS:]
	if rest:
		result.append({"label": f"أخرى ({len(rest)})", "amount": flt(sum(a for _label, a in rest), 2), "others": 1})
	return result


def rank_destinations(destinations):
	return sorted(destinations.items(), key=lambda item: -item[1])


def get_columns():
	amount = {"fieldtype": "Float", "precision": 2, "width": 125}
	return [
		{"label": "الحساب / الحركة", "fieldname": "description", "fieldtype": "Data", "width": 280},
		{"label": "التاريخ", "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
		{
			"label": "السند",
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 165,
		},
		{"label": "الطرف", "fieldname": "party", "fieldtype": "Data", "width": 130},
		{"label": "القيمة الداخلة", "fieldname": "amount_in", **amount},
		{"label": "القيمة الخارجة", "fieldname": "amount_out", **amount},
		{"label": "الرصيد", "fieldname": "balance", **amount},
		{"label": "أيام بلا تسوية", "fieldname": "days_open", "fieldtype": "Int", "width": 110},
		{"label": "البيان", "fieldname": "remarks", "fieldtype": "Data", "width": 300},
	]
