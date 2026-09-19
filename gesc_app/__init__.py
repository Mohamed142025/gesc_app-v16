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
