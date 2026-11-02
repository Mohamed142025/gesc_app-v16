// Copyright (c) 2026, mohamed sayed and contributors
// For license information, please see license.txt

frappe.query_reports["متابعة المشاريع"] = {
	filters: [
		{ fieldname: "employee", label: __("الاسم"), fieldtype: "Link", options: "Employee" },
		{ fieldname: "designation", label: __("الوظيفة"), fieldtype: "Link", options: "Designation" },
	],

	// The name opens the member's projects; each count opens those in its status.
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data || !data.employee) return value;
		const status = { open: "Open", completed: "Completed", cancelled: "Cancelled" }[column.fieldname];
		if (column.fieldname === "employee_name" || column.fieldname === "total" || status) {
			const route = { employee: data.employee };
			if (status) route.status = status;
			return `<a href="/app/project?${new URLSearchParams(route)}">${value}</a>`;
		}
		return value;
	},
};
