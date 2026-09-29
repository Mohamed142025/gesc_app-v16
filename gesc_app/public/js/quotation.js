frappe.ui.form.on("Quotation", {
	refresh(frm) {
		gesc_format_item_attachments(frm);

		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(
			__("Task"),
			function () {
				frappe.model.open_mapped_doc({
					method: "gesc_app.gesc_app.quotation_utils.make_task",
					frm: frm,
				});
			},
			__("Create")
		);
	},
});

// In the narrow grid column the item's file shows as a link instead of its path.
function gesc_format_item_attachments(frm) {
	const grid = frm.get_field("items")?.grid;
	const df = (grid?.docfields || []).find((d) => d.fieldname === "custom_attachment");
	if (!df || df.formatter) return;
	df.formatter = (value) => {
		if (!value) return "";
		const name = frappe.utils.escape_html(decodeURIComponent(value.split("/").pop()));
		return `<a href="${encodeURI(value)}" target="_blank" rel="noopener" title="${name}">${frappe.utils.icon(
			"es-line-attachment",
			"xs"
		)} ${__("عرض")}</a>`;
	};
	grid.update_docfield_property("custom_attachment", "formatter", df.formatter);
}
