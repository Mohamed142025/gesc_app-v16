// Quotation addenda: "ملحق عرض سعر" on a submitted main quotation (open or already a
// contract), or ticked on a new quotation once its customer is chosen, picking one of the
// customer's main quotations. The server numbers the addendum in the main quotation's
// family and checks the same rules.
(() => {
	const ADDENDUM_ALLOWED = ["Open", "Ordered", "Partially Ordered"];

	frappe.ui.form.on("Quotation", {
		setup(frm) {
			frm.set_query("custom_addendum_to", (doc) => ({
				query: "gesc_app.gesc_app.quotation_addendum.main_quotation_query",
				filters: { customer: doc.quotation_to === "Customer" ? doc.party_name : "" },
			}));
		},

		// The main quotation belongs to the customer, so a new customer starts over.
		party_name(frm) {
			if (frm.is_new() && !frm.doc.amended_from && frm.doc.custom_addendum_to) {
				frm.set_value("custom_addendum_to", "");
			}
		},

		quotation_to(frm) {
			if (frm.is_new() && !frm.doc.amended_from && frm.doc.quotation_to !== "Customer") {
				frm.set_value({ custom_is_addendum: 0, custom_addendum_to: "" });
			}
		},

		// The addendum starts from its main quotation, as "Create" makes it: the fields left
		// empty here and the taxes; the items stay what was entered.
		custom_addendum_to(frm) {
			const main = frm.doc.custom_addendum_to;
			if (!frm.is_new() || frm.doc.amended_from || !main) return;
			frappe
				.xcall("gesc_app.gesc_app.quotation_addendum.make_addendum", { source_name: main })
				.then((mapped) => {
					if (mapped && frm.doc.custom_addendum_to === main) return fill_from_main(frm, mapped);
				});
		},

		custom_is_addendum(frm) {
			if (!frm.doc.custom_is_addendum && frm.doc.custom_addendum_to && frm.is_new()) {
				frm.set_value("custom_addendum_to", "");
			}
		},

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

	const NOT_COPIED = new Set([
		"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "naming_series",
		"amended_from", "quotation_to", "party_name", "custom_is_addendum", "custom_addendum_to",
		"transaction_date", "valid_till", "status", "taxes_and_charges",
	]);
	const ROW_META = new Set([
		"name", "idx", "parent", "parentfield", "parenttype", "doctype", "owner", "creation",
		"modified", "modified_by", "docstatus", "__islocal", "__unsaved",
	]);

	async function fill_from_main(frm, mapped) {
		const values = {};
		frappe.meta.get_docfields(frm.doctype).forEach((df) => {
			if (
				NOT_COPIED.has(df.fieldname) ||
				df.read_only ||
				frappe.model.no_value_type.includes(df.fieldtype) ||
				frappe.model.table_fields.includes(df.fieldtype)
			) {
				return;
			}
			const value = mapped[df.fieldname];
			if (value !== undefined && value !== null && value !== "" && !frm.doc[df.fieldname]) {
				values[df.fieldname] = value;
			}
		});
		if (Object.keys(values).length) await frm.set_value(values);

		if ((mapped.taxes || []).length) {
			// Set as they are on the main quotation, not fetched again from the template.
			frm.doc.taxes_and_charges = mapped.taxes_and_charges;
			frm.clear_table("taxes");
			mapped.taxes.forEach((tax) => {
				const row = frm.add_child("taxes");
				Object.keys(tax).forEach((key) => {
					if (!ROW_META.has(key)) row[key] = tax[key];
				});
			});
			frm.refresh_fields();
			frm.cscript.calculate_taxes_and_totals?.();
		}
		frappe.show_alert({ message: __("تم نقل بيانات عرض السعر الأساسي"), indicator: "green" });
	}

	function make_addendum(frm) {
		frappe.model.open_mapped_doc({
			method: "gesc_app.gesc_app.quotation_addendum.make_addendum",
			frm,
		});
	}
})();
