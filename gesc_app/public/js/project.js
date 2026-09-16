frappe.ui.form.on("Project", {
	setup(frm) {
		frm.set_query("custom_task_template", function () {
			return {
				filters: {
					project_type: frm.doc.project_type,
					is_active: 1,
				},
			};
		});
	},

	refresh(frm) {
		frm.toggle_display("custom_task_template", !!frm.doc.project_type);
	},

	project_type(frm) {
		frm.toggle_display("custom_task_template", !!frm.doc.project_type);

		if (frm.doc.custom_task_template) {
			frm.set_value("custom_task_template", "");
		}
	},
});
