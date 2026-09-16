frappe.ui.form.on("Delivery Note Item", {
	item_code(frm, cdt, cdn) {
		update_completion_preview(frm, cdt, cdn);
	},
	custom_supply_qty(frm, cdt, cdn) {
		update_completion_preview(frm, cdt, cdn);
	},
	custom_install_qty(frm, cdt, cdn) {
		update_completion_preview(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Delivery Note", {
	refresh(frm) {
		warn_if_no_project(frm);
	},

	project(frm) {
		warn_if_no_project(frm);
		(frm.doc.items || []).forEach((row) => update_completion_preview(frm, row.doctype, row.name));
	},
});

function warn_if_no_project(frm) {
	frm.fields_dict.items.grid.update_docfield_property(
		"custom_supply_qty",
		"description",
		frm.doc.project
			? ""
			: __("Set the Project above first - otherwise supply/install quantities won't affect any البند.")
	);
}

const PREVIEW_FIELD_MAP = {
	qty: "qty",
	custom_supply_percent: "supply_percent",
	custom_install_percent: "install_percent",
	custom_previous_supply_percent: "previous_supply_percent",
	custom_previous_install_percent: "previous_install_percent",
	custom_previous_completion_percent: "previous",
	custom_item_completion_percent: "current",
};

function update_completion_preview(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.item_code || !frm.doc.project) {
		Object.keys(PREVIEW_FIELD_MAP).forEach((fieldname) => {
			if (fieldname !== "qty") frappe.model.set_value(cdt, cdn, fieldname, 0);
		});
		return;
	}

	frappe.call({
		method: "gesc_app.gesc_app.delivery_note_utils.preview_project_item_completion",
		args: {
			project: frm.doc.project,
			item_code: row.item_code,
			supply_qty: row.custom_supply_qty || 0,
			install_qty: row.custom_install_qty || 0,
			delivery_note: frm.doc.name,
		},
		callback(r) {
			const data = r.message || {};
			Object.entries(PREVIEW_FIELD_MAP).forEach(([fieldname, key]) => {
				frappe.model.set_value(cdt, cdn, fieldname, data[key] || 0);
			});
		},
	});
}
