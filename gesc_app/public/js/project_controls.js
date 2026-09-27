// Project creation rules from Projects Settings: only eligible Sales Orders are offered,
// and the exception reason is shown to the exception role (and wherever one was given).
frappe.ui.form.on("Project", {
	onload(frm) {
		frappe.xcall("gesc_app.gesc_app.project_controls.get_project_controls").then((controls) => {
			frm.__project_controls = controls;
			if (controls.enabled) {
				frm.set_query("sales_order", () => ({
					query: "gesc_app.gesc_app.project_controls.sales_order_query",
					filters: { company: frm.doc.company },
				}));
			}
			toggle_exception_reason(frm);
		});
	},

	refresh(frm) {
		toggle_exception_reason(frm);
	},
});

function toggle_exception_reason(frm) {
	const controls = frm.__project_controls || {};
	frm.toggle_display(
		"custom_project_exception_reason",
		!!(controls.is_exception || frm.doc.custom_project_exception_reason)
	);
}
