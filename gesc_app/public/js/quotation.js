frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(
			__("Task"),
			function () {
				frappe.model.open_mapped_doc({
					method: "gesc_app.gesc_app.quotation_utils.make_task",
					frm: frm,
				});
			},
			__("Create")
		);
	},
});
