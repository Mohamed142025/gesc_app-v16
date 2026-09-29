// Copyright (c) 2026, mohamed sayed and contributors
// For license information, please see license.txt

frappe.query_reports["Material Submittal Log"] = {
	filters: [
		{ fieldname: "project", label: __("المشروع"), fieldtype: "Link", options: "Project" },
		{
			fieldname: "kind",
			label: __("النوع"),
			fieldtype: "Select",
			options: ["", "مواد", "رسومات تفصيلية", "حسابات إنشائية"].join("\n"),
		},
		{
			fieldname: "state",
			label: __("الحالة"),
			fieldtype: "Select",
			options: [
				"",
				"مفتوحة",
				"جاري العمل",
				"تم الإرسال للاستشاري",
				"معتمد",
				"معتمد بملاحظات",
				"مرفوض – تعديلات مطلوبة",
				"مرفوض – إعادة عمل",
				"ملغي",
			].join("\n"),
		},
		{
			fieldname: "response_code",
			label: __("الكود"),
			fieldtype: "Select",
			options: [
				"",
				"Approved",
				"Approved with Comments",
				"Rejected – Corrections Required",
				"Rejected – Rework Required",
			].join("\n"),
		},
		{ fieldname: "from_date", label: __("أُرسل من"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("أُرسل إلى"), fieldtype: "Date" },
		{ fieldname: "overdue_only", label: __("المتأخرة فقط"), fieldtype: "Check" },
	],

	// Late answers in red, and each code in its status colour.
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "overdue_days" && data.overdue_days > 0) {
			return `<span class="text-danger bold">${value}</span>`;
		}
		if (column.fieldname === "response_code" && data.response_code) {
			const color = {
				Approved: "green",
				"Approved with Comments": "blue",
				"Rejected – Corrections Required": "orange",
				"Rejected – Rework Required": "red",
			}[data.response_code];
			return `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
};
