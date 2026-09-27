// Copyright (c) 2026, mohamed sayed and contributors
// For license information, please see license.txt

frappe.ui.form.on("Private Comment Settings", {
	setup(frm) {
		// Only documents with their own form: no child tables or settings pages.
		frm.set_query("document_type", "document_types", () => ({ filters: { istable: 0, issingle: 0 } }));
	},
});
