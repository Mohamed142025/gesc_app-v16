// Adds a "Project" filter to the standard Sales Order Analysis report.
// Hooks into QueryReport.setup_filters (instead of polling) so the filter
// is injected deterministically, every time the report loads, with no race condition.
(function () {
	const REPORT_NAME = "Sales Order Analysis";

	function add_project_filter(report_settings) {
		const filters = report_settings.filters || (report_settings.filters = []);
		if (filters.some((filter) => filter.fieldname === "project")) return;

		const warehouse_index = filters.findIndex((filter) => filter.fieldname === "warehouse");
		const insert_at = warehouse_index === -1 ? filters.length : warehouse_index + 1;

		filters.splice(insert_at, 0, {
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
		});
	}

	if (!frappe.views || !frappe.views.QueryReport) return;
	if (frappe.views.QueryReport.prototype.__gesc_project_filter_patched__) return;

	const original_setup_filters = frappe.views.QueryReport.prototype.setup_filters;
	frappe.views.QueryReport.prototype.setup_filters = function (...args) {
		if (this.report_name === REPORT_NAME && this.report_settings) {
			add_project_filter(this.report_settings);
		}
		return original_setup_filters.apply(this, args);
	};
	frappe.views.QueryReport.prototype.__gesc_project_filter_patched__ = true;
})();
