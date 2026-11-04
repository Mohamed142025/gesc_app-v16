// Copyright (c) 2026, mohamed sayed and contributors
// For license information, please see license.txt

frappe.query_reports["الموقف المالي للعقود"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
			get_query: () => {
				const customer = frappe.query_report.get_filter_value("customer");
				return { filters: customer ? { customer } : {} };
			},
		},
		{
			fieldname: "sales_order",
			label: __("Contract"),
			fieldtype: "Link",
			options: "Sales Order",
			get_query: () => {
				const filters = { docstatus: 1 };
				for (const field of ["company", "customer", "project"]) {
					const value = frappe.query_report.get_filter_value(field);
					if (value) filters[field] = value;
				}
				return { filters };
			},
		},
		{ fieldname: "contract_from_date", label: __("Contract From Date"), fieldtype: "Date" },
		{ fieldname: "contract_to_date", label: __("Contract To Date"), fieldtype: "Date" },
		{ fieldname: "statement_from_date", label: __("Progress Statement From Date"), fieldtype: "Date" },
		{ fieldname: "statement_to_date", label: __("Progress Statement To Date"), fieldtype: "Date" },
		{ fieldname: "without_contracts", label: __("Include Projects Without Contracts"), fieldtype: "Check" },
		{ fieldname: "without_contracts_only", label: __("Projects Without Contracts Only"), fieldtype: "Check" },
		{ fieldname: "unpaid_only", label: __("Unpaid Progress Statements Only"), fieldtype: "Check" },
		{
			// Only how the tree is shown: no new data.
			fieldname: "show_statements",
			label: __("Show Progress Statements"),
			fieldtype: "Check",
			on_change: () => show_statements(frappe.query_report.datatable),
		},
	],

	// Customer > project > contract > addendum > statement, opened one level at a time.
	tree: true,
	name_field: "id",
	parent_field: "parent_id",
	initial_depth: 1,

	after_datatable_render: show_statements,

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		// The levels above the statements in bold, and amounts left owing in red.
		if (["Customer", "Project", "Contract"].includes(data.kind)) value = `<b>${value}</b>`;
		const owing = ["contract_balance", "invoice_balance"].includes(column.fieldname) && data[column.fieldname] > 0.005;
		const loss = column.fieldname === "margin" && data.margin < -0.005;
		if (owing || loss) value = `<span style="color: var(--red-600)">${value}</span>`;
		return value;
	},
};

// "Show Progress Statements": every level opened, down to the statements; unchecked, as the report opens.
function show_statements(datatable) {
	if (!datatable) return;
	if (frappe.query_report.get_filter_value("show_statements")) datatable.rowmanager.expandAllNodes();
	else datatable.rowmanager.setTreeDepth(frappe.query_reports["الموقف المالي للعقود"].initial_depth);
}
