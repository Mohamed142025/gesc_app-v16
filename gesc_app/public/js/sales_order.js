frappe.ui.form.on("Sales Order", {
	setup(frm) {
		frm.set_query("custom_addendum_to", function () {
			return {
				filters: {
					custom_is_main_contract: 1,
					customer: frm.doc.customer,
					project: frm.doc.project,
					name: ["!=", frm.doc.name],
				},
			};
		});
	},

	customer(frm) {
		if (frm.doc.custom_addendum_to) {
			frm.set_value("custom_addendum_to", "");
		}
	},

	project(frm) {
		if (frm.doc.custom_addendum_to) {
			frm.set_value("custom_addendum_to", "");
		}
	},
});
