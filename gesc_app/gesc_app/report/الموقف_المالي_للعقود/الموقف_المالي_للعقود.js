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
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "Link",
			options: "Cost Center",
			get_query: () => ({ filters: { company: frappe.query_report.get_filter_value("company") } }),
		},
		// The period: statements, down payments and costs in it; what is left, as of its end.
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
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

	after_datatable_render(datatable) {
		show_statements(datatable);
		link_summary(frappe.query_report);
	},

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

// A click on a summary card lists the documents its figure comes from, each with its share,
// and opens them as a list.
function link_summary(report) {
	if (!report?.$summary) return;
	if (!document.getElementById("gesc-linked-summary-style")) {
		$(`<style id="gesc-linked-summary-style">
			.gesc-linked-summary .summary-item { cursor: pointer; }
			.gesc-linked-summary .summary-item:hover { outline: 1px solid var(--primary); outline-offset: -1px; }
		</style>`).appendTo(document.head);
	}
	report.$summary
		.addClass("gesc-linked-summary")
		.off("click.gesc")
		.on("click.gesc", ".summary-item", function () {
			const index = report.$summary.find(".summary-item").index(this);
			const card = report.raw_data?.report_summary?.[index];
			if (card) show_documents(card);
		});
}

function show_documents(card) {
	const docs = [...(card.documents || [])];
	const amounts = card.datatype === "Currency";
	if (amounts) docs.sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount));
	const money = (value) => format_currency(value, card.currency);
	const rows = docs
		.map(
			(d) => `<tr>
				<td>${frappe.utils.get_form_link(d.doctype, d.name, true)}</td>
				<td>${d.label && d.label !== d.name ? frappe.utils.escape_html(String(d.label)) : ""}</td>
				${amounts ? `<td class="text-right">${money(d.amount)}</td>` : ""}
			</tr>`
		)
		.join("");
	const total = amounts
		? `<tr><th colspan="2">${__("Total")}</th><th class="text-right">${money(card.value)}</th></tr>`
		: "";
	const dialog = new frappe.ui.Dialog({
		title: `${__(card.label)} (${docs.length})`,
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "documents",
				options: docs.length
					? `<div style="max-height: 60vh; overflow: auto;"><table class="table table-bordered table-sm">
						<thead><tr><th>${__("Reference")}</th><th>${__("Description")}</th>${amounts ? `<th class="text-right">${__("Amount")}</th>` : ""}</tr></thead>
						<tbody>${rows}</tbody><tfoot>${total}</tfoot></table></div>`
					: `<p class="text-muted">${__("No documents make up this figure.")}</p>`,
			},
		],
	});
	const doctypes = [...new Set(docs.map((d) => d.doctype))];
	if (doctypes.length === 1) {
		dialog.set_primary_action(__("View List"), () => {
			dialog.hide();
			frappe.route_options = { name: ["in", docs.map((d) => d.name)] };
			frappe.set_route("List", doctypes[0]);
		});
	}
	dialog.show();
}
