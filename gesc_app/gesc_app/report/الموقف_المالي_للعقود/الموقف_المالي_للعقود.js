// Copyright (c) 2026, mohamed sayed and contributors
// For license information, please see license.txt

frappe.query_reports["الموقف المالي للعقود"] = {
	filters: [
		{
			fieldname: "company",
			label: __("الشركة"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{ fieldname: "customer", label: __("العميل"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "project",
			label: __("المشروع"),
			fieldtype: "Link",
			options: "Project",
			get_query: () => {
				const customer = frappe.query_report.get_filter_value("customer");
				return { filters: customer ? { customer } : {} };
			},
		},
		{
			fieldname: "sales_order",
			label: __("العقد"),
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
		{ fieldname: "contract_from_date", label: __("تاريخ العقد من"), fieldtype: "Date" },
		{ fieldname: "contract_to_date", label: __("تاريخ العقد إلى"), fieldtype: "Date" },
		{ fieldname: "statement_from_date", label: __("تاريخ المستخلص من"), fieldtype: "Date" },
		{ fieldname: "statement_to_date", label: __("تاريخ المستخلص إلى"), fieldtype: "Date" },
	],

	// Customer > project > contract > addendum > statement, opened one level at a time.
	tree: true,
	name_field: "id",
	parent_field: "parent_id",
	initial_depth: 1,

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		// The levels above the statements in bold, and amounts left owing in red.
		if (data.indent < 3 && data.row_type !== "ملحق") value = `<b>${value}</b>`;
		const owing = ["contract_balance", "invoice_balance"].includes(column.fieldname) && data[column.fieldname] > 0.005;
		const loss = column.fieldname === "margin" && data.margin < -0.005;
		if (owing || loss) value = `<span style="color: var(--red-600)">${value}</span>`;
		return value;
	},
};
