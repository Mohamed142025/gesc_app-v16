const ITEM_DESCRIPTION_CHILD_TABLES = [
	"Quotation Item",
	"Sales Order Item",
	"Sales Invoice Item",
	"Delivery Note Item",
	"POS Invoice Item",
	"Request for Quotation Item",
	"Supplier Quotation Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Material Request Item",
	"Stock Entry Detail",
	"Pick List Item",
];

const ITEM_DESCRIPTION_PARENT_DOCTYPES = [
	"Quotation",
	"Sales Order",
	"Sales Invoice",
	"Delivery Note",
	"POS Invoice",
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Material Request",
	"Stock Entry",
	"Pick List",
];

ITEM_DESCRIPTION_PARENT_DOCTYPES.forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		setup(frm) {
			if (!frm.fields_dict.items) return;

			frm.set_query("custom_item_description", "items", (doc, cdt, cdn) => {
				const row = locals[cdt][cdn];
				return {
					filters: {
						item_code: row.item_code || "__no_item_selected__",
					},
				};
			});
		},
	});
});

ITEM_DESCRIPTION_CHILD_TABLES.forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		item_code(frm, cdt, cdn) {
			frappe.model.set_value(cdt, cdn, "custom_item_description", "");
		},

		custom_item_description(frm, cdt, cdn) {
			const row = locals[cdt][cdn];
			if (!row.custom_item_description) return;

			frappe.db.get_value(
				"Item Description",
				row.custom_item_description,
				["item_code", "description"],
			).then(({ message }) => {
				if (!message) return;
				if (message.item_code !== row.item_code) {
					frappe.model.set_value(cdt, cdn, "custom_item_description", "");
					frappe.throw(__("The selected description does not belong to this item."));
					return;
				}
				frappe.model.set_value(cdt, cdn, "description", message.description);
			});
		},
	});
});