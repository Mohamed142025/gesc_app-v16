__version__ = "0.0.1"


def patch_sales_order_analysis_report():
	"""Add Project filtering to ERPNext's Sales Order Analysis report (Script Report) without editing core."""
	try:
		from erpnext.selling.report.sales_order_analysis import sales_order_analysis
	except Exception:
		return

	if getattr(sales_order_analysis, "__gesc_project_filter_patched__", False):
		return

	original_get_conditions = sales_order_analysis.get_conditions

	def get_conditions(filters):
		conditions = original_get_conditions(filters)
		if filters.get("project"):
			conditions += " and so.project = %(project)s"
		return conditions

	sales_order_analysis.get_conditions = get_conditions
	sales_order_analysis.__gesc_project_filter_patched__ = True


patch_sales_order_analysis_report()


def patch_trial_balance_for_party():
	"""ERPNext's Trial Balance for Party nets a party's opening into one column. Its
	"show_opening_both_sides" checkbox (public/js/trial_balance_for_party.js) shows the debit
	and the credit instead, without editing core. The closing is the net either way."""
	try:
		from erpnext.accounts.report.trial_balance_for_party import trial_balance_for_party
	except Exception:
		return

	if getattr(trial_balance_for_party, "__gesc_gross_opening_patched__", False):
		return

	original_get_opening_balances = trial_balance_for_party.get_opening_balances

	def get_opening_balances(filters, account_filter=None):
		if not filters.get("show_opening_both_sides"):
			return original_get_opening_balances(filters, account_filter)

		import frappe
		from frappe.query_builder.functions import Sum

		gl_entry = frappe.qb.DocType("GL Entry")
		query = (
			frappe.qb.from_(gl_entry)
			.select(gl_entry.party, Sum(gl_entry.debit).as_("debit"), Sum(gl_entry.credit).as_("credit"))
			.where(
				(gl_entry.company == filters.company)
				& (gl_entry.is_cancelled == 0)
				& (gl_entry.party_type == filters.party_type)
				& (gl_entry.party != "")
				& (
					(gl_entry.posting_date < filters.from_date)
					| ((gl_entry.is_opening == "Yes") & (gl_entry.posting_date <= filters.to_date))
				)
			)
			.groupby(gl_entry.party)
		)
		if account_filter:
			query = query.where(gl_entry.account.isin(account_filter))
		return frappe._dict({row.party: [row.debit, row.credit] for row in query.run(as_dict=True)})

	trial_balance_for_party.get_opening_balances = get_opening_balances
	trial_balance_for_party.__gesc_gross_opening_patched__ = True


patch_trial_balance_for_party()
