// Material Request: "الغرض" stands in for ERPNext's purpose and fills it, so ERPNext's own
// behaviour for that purpose follows (buttons, warehouses, issuing). "طلب عينة" is a Material
// Issue for a customer, a project or both (gesc_app.gesc_app.sample_request): a project brings
// its customer, a customer narrows the projects to its own, and changing the customer clears
// the project.
frappe.ui.form.on("Material Request", {
	setup(frm) {
		frm.set_query("custom_sample_project", () =>
			frm.doc.custom_sample_customer ? { filters: { customer: frm.doc.custom_sample_customer } } : {}
		);
	},

	onload(frm) {
		if (!frm.doc.custom_request_purpose) {
			frm.set_value("custom_request_purpose", frm.doc.material_request_type || "Purchase");
		}
	},

	custom_request_purpose(frm) {
		const purpose = frm.doc.custom_request_purpose;
		const type = purpose === "طلب عينة" ? "Material Issue" : purpose;
		if (type && frm.doc.material_request_type !== type) {
			frm.set_value("material_request_type", type);
		}
		if (purpose !== "طلب عينة") {
			if (frm.doc.custom_sample_customer) frm.set_value("custom_sample_customer", "");
			if (frm.doc.custom_sample_project) frm.set_value("custom_sample_project", "");
		}
	},

	custom_sample_customer(frm) {
		// The customer set from a project keeps that project.
		if (frm.__customer_from_project) {
			frm.__customer_from_project = false;
			return;
		}
		if (frm.doc.custom_sample_project) frm.set_value("custom_sample_project", "");
	},

	async custom_sample_project(frm) {
		const project = frm.doc.custom_sample_project;
		if (!project) return;
		const { message } = await frappe.db.get_value("Project", project, "customer");
		const customer = message?.customer;
		if (customer && customer !== frm.doc.custom_sample_customer) {
			frm.__customer_from_project = true;
			frm.set_value("custom_sample_customer", customer);
		}
	},
});
