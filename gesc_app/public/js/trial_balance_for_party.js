// Adds a checkbox to the standard Trial Balance for Party report: the opening's debit and credit
// each in its own column, or their net as ERPNext shows it (gesc_app.patch_trial_balance_for_party).
(function () {
	const REPORT_NAME = "Trial Balance for Party";
	const FIELDNAME = "show_opening_both_sides";

	function add_filter(report_settings) {
		const filters = report_settings.filters || (report_settings.filters = []);
		if (filters.some((filter) => filter.fieldname === FIELDNAME)) return;
		filters.push({
			fieldname: FIELDNAME,
			label: __("إظهار مدين ودائن الافتتاحي"),
			fieldtype: "Check",
			default: 1,
		});
	}

	if (!frappe.views || !frappe.views.QueryReport) return;
	if (frappe.views.QueryReport.prototype.__gesc_opening_filter_patched__) return;

	const original_setup_filters = frappe.views.QueryReport.prototype.setup_filters;
	frappe.views.QueryReport.prototype.setup_filters = function (...args) {
		if (this.report_name === REPORT_NAME && this.report_settings) {
			add_filter(this.report_settings);
		}
		return original_setup_filters.apply(this, args);
	};
	frappe.views.QueryReport.prototype.__gesc_opening_filter_patched__ = true;
})();
