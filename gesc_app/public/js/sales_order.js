frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		frm.toggle_reqd("custom_addendum_to", frm.doc.custom_is_addendum);
	},

	setup(frm) {
		frm.set_query("custom_addendum_to", function () {
			return {
				filters: {
					custom_is_main_contract: 1,
					customer: frm.doc.customer,
					docstatus: 1,
					name: ["!=", frm.doc.name],
				},
			};
		});
	},

	custom_is_addendum(frm) {
		frm.toggle_reqd("custom_addendum_to", frm.doc.custom_is_addendum);
		if (!frm.doc.custom_is_addendum && frm.doc.custom_addendum_to) {
			frm.set_value("custom_addendum_to", "");
		}
	},

	customer(frm) {
		if (frm.doc.custom_addendum_to) {
			frm.set_value("custom_addendum_to", "");
		}
	},
});

