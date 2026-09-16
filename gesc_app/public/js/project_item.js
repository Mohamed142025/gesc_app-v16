frappe.ui.form.on("Project Item", {
	setup(frm) {
		frm.set_query("item", function () {
			return {
				query: "gesc_app.gesc_app.project_utils.get_project_sales_order_items",
				filters: { project: frm.doc.project },
			};
		});

		frm.set_query("building", function () {
			return {
				filters: { project: frm.doc.project },
			};
		});
	},

	refresh(frm) {
		warn_if_no_sales_order(frm);
	},

	project(frm) {
		frm.set_value("item", "");
		warn_if_no_sales_order(frm);
	},
});

function warn_if_no_sales_order(frm) {
	if (!frm.doc.project) {
		frm.set_df_property("item", "description", "");
		return;
	}

	frappe.db.get_value("Project", frm.doc.project, "sales_order").then((r) => {
		const has_sales_order = r.message && r.message.sales_order;
		frm.set_df_property(
			"item",
			"description",
			has_sales_order
				? ""
				: __("This project has no Sales Order linked yet, so no items are available to select here.")
		);
	});
}
