// Every item takes the entry's project; on an installation ("تركيب") the project brings
// all the stock in its warehouse (stock_entry_project).
frappe.ui.form.on("Stock Entry", {
	project(frm) {
		(frm.doc.items || []).forEach((d) => frappe.model.set_value(d.doctype, d.name, "project", frm.doc.project));
		if (frm.doc.stock_entry_type === "تركيب" && frm.doc.project) {
			gesc_fill_project_stock(frm);
		}
	},

	stock_entry_type(frm) {
		if (frm.doc.stock_entry_type === "تركيب" && frm.doc.project) {
			gesc_fill_project_stock(frm);
		}
	},
});

frappe.ui.form.on("Stock Entry Detail", {
	items_add(frm, cdt, cdn) {
		if (frm.doc.project) frappe.model.set_value(cdt, cdn, "project", frm.doc.project);
	},
});

function gesc_fill_project_stock(frm) {
	frappe.call({
		method: "gesc_app.gesc_app.stock_entry_project.get_project_stock",
		args: { project: frm.doc.project },
		freeze: true,
	}).then(({ message: r }) => {
		if (!r.warehouse) {
			frappe.msgprint(__("المشروع ليس له مخزن مشروع."));
			return;
		}
		if (!r.items.length) {
			frm.set_value("from_warehouse", r.warehouse);
			frappe.msgprint(__("لا يوجد رصيد في مخزن المشروع {0}.", [r.warehouse]));
			return;
		}
		const fill = () => {
			frm.set_value("from_warehouse", r.warehouse);
			frm.clear_table("items");
			r.items.forEach((it) => {
				const row = frm.add_child("items");
				Object.assign(row, {
					item_code: it.item_code,
					item_name: it.item_name,
					s_warehouse: r.warehouse,
					qty: it.qty,
					transfer_qty: it.qty,
					uom: it.stock_uom,
					stock_uom: it.stock_uom,
					conversion_factor: 1,
					project: frm.doc.project,
				});
			});
			frm.refresh_field("items");
			frappe.show_alert({ message: __("تمت إضافة {0} صنف من {1}", [r.items.length, r.warehouse]), indicator: "green" });
		};
		const has_items = (frm.doc.items || []).some((d) => d.item_code);
		if (has_items) {
			frappe.confirm(__("استبدال الأصناف الحالية بكل أصناف مخزن المشروع ({0} صنف)؟", [r.items.length]), fill, () =>
				frm.set_value("from_warehouse", r.warehouse)
			);
		} else {
			fill();
		}
	});
}
