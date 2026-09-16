frappe.ui.form.on("Task", {
	setup(frm) {
		frm.set_query("custom_project_item", function () {
			return {
				filters: { project: frm.doc.project },
			};
		});
	},
});
