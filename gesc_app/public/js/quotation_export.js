// Quotation: download it as Word or Excel in the layout of one of its print formats
// (gesc_app.gesc_app.quotation_export).
frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (frm.is_new()) return;
		const label = __("تنزيل");
		frm.add_custom_button(__("Word"), () => gesc_download_quotation(frm, "word"), label);
		frm.add_custom_button(__("Excel"), () => gesc_download_quotation(frm, "excel"), label);
	},
});

async function gesc_download_quotation(frm, file_type) {
	const formats = await frappe.db.get_list("Print Format", {
		filters: { doc_type: "Quotation", disabled: 0 },
		pluck: "name",
		order_by: "name asc",
		limit: 0,
	});
	const default_format = frm.meta.default_print_format || formats[0];
	const d = new frappe.ui.Dialog({
		title: file_type === "excel" ? __("تنزيل عرض السعر Excel") : __("تنزيل عرض السعر Word"),
		fields: [
			{
				fieldname: "print_format",
				label: __("نموذج الطباعة"),
				fieldtype: "Select",
				options: formats,
				default: formats.includes(default_format) ? default_format : formats[0],
				reqd: 1,
			},
		],
		primary_action_label: __("تنزيل"),
		primary_action({ print_format }) {
			d.hide();
			const params = new URLSearchParams({ name: frm.doc.name, print_format, file_type });
			window.open(
				frappe.urllib.get_full_url(
					`/api/method/gesc_app.gesc_app.quotation_export.download?${params.toString()}`
				)
			);
		},
	});
	d.show();
}
