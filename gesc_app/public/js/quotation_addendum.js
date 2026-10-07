// Quotation addenda: "ملحق عرض سعر" on a submitted main quotation (open or already a
// contract). The server numbers the addendum in the main quotation's family and checks
// the same rules.
(() => {
	const ADDENDUM_ALLOWED = ["Open", "Ordered", "Partially Ordered"];

	frappe.ui.form.on("Quotation", {
		refresh(frm) {
			// The "+" next to the addenda in Connections makes an addendum the same way.
			frm.make_methods = { ...frm.make_methods, Quotation: () => make_addendum(frm) };
			frm.can_make_methods = { ...frm.can_make_methods, Quotation: () => can_add(frm) };

			if (can_add(frm)) {
				frm.add_custom_button(__("ملحق عرض سعر"), () => make_addendum(frm), __("Create"));
			}
		},
	});

	function can_add(frm) {
		return (
			frm.doc.docstatus === 1 &&
			ADDENDUM_ALLOWED.includes(frm.doc.status) &&
			!frm.doc.custom_addendum_to &&
			frappe.model.can_create("Quotation")
		);
	}

	function make_addendum(frm) {
		frappe.model.open_mapped_doc({
			method: "gesc_app.gesc_app.quotation_addendum.make_addendum",
			frm,
		});
	}
})();
