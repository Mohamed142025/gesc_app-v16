// "Create > Project" on a Sales Order checks the project creation rules first, so the
// reason shows before a project form opens that could not be saved.
frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		const cscript = frm.cscript;
		if (!cscript.make_project || cscript.make_project.__checks_project_rules) return;

		const make_project = cscript.make_project;
		cscript.make_project = function () {
			frappe
				.xcall("gesc_app.gesc_app.project_controls.check_sales_order_for_project", {
					sales_order: frm.doc.name,
				})
				.then((result) => {
					if (!result.allowed) {
						frappe.msgprint({ title: __("لا يمكن إنشاء مشروع"), message: result.message, indicator: "red" });
						return;
					}
					if (result.exception) {
						frappe.show_alert({ message: __("استثناء: {0}", [result.exception]), indicator: "orange" }, 8);
					}
					make_project.call(this);
				});
		};
		cscript.make_project.__checks_project_rules = true;
	},
});
