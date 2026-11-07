frappe.ui.form.on("Quotation", {
	setup(frm) {
		// An attachment belongs to one of this quotation's items.
		frm.set_query("item_code", "custom_attachments", (doc) => ({
			filters: { name: ["in", (doc.items || []).map((d) => d.item_code).filter(Boolean)] },
		}));
	},

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

// An item's files: its main file (custom_attachment, the drawing it is priced on, which the
// Sales Order and the print keep reading) and any number of extra files, kept as rows of
// the quotation's attachments table linked to the item and to its row (row_key). In the
// table the column is a button with the count; it opens the item's files, where several
// files can be picked from the device at once.
const GESC_ITEM_FILES_TABLE = "custom_attachments";
const GESC_ITEM_FILE_TYPE = "مخطط / رسم هندسي";

frappe.ui.form.on("Quotation", {
	items_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "custom_row_key", frappe.utils.get_random(12));
	},
});

frappe.ui.form.on("Quotation Item", {
	// The item's own form (the row opened): its files button under the main file.
	form_render(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const form = frm.fields_dict.items.grid.grid_rows_by_docname[cdn]?.grid_form;
		const field = form?.fields_dict?.custom_attachment;
		if (!field) return;
		let button = field.$wrapper.find(".gesc-item-files-open");
		if (!button.length) {
			button = $(`<button type="button" class="btn btn-default btn-sm gesc-item-files-open"></button>`).appendTo(field.$wrapper);
			button.on("click", () => gesc_open_item_files(frm, cdn));
		}
		button.html(`${frappe.utils.icon("es-line-attachment", "xs")} ${__("مرفقات الصنف")} (${gesc_item_files(frm, row).length})`);
	},
});

// The extra files of a row: linked to its row, or (older rows, before row keys) to its
// item without a row.
function gesc_extra_files(frm, row) {
	return (frm.doc[GESC_ITEM_FILES_TABLE] || []).filter(
		(file) =>
			file.linked_to_item &&
			(file.row_key ? file.row_key === row.custom_row_key : file.item_code && file.item_code === row.item_code)
	);
}

function gesc_item_files(frm, row) {
	return [...(row.custom_attachment ? [row.custom_attachment] : []), ...gesc_extra_files(frm, row).map((f) => f.attachment)];
}

function gesc_file_name(url) {
	return decodeURIComponent(String(url || "").split("/").pop());
}

// The column: a button with the count, which opens the item's files. It is read-only in
// the grid, so a tap opens the files instead of a single-file picker.
function gesc_format_item_attachments(frm) {
	const grid = frm.get_field("items")?.grid;
	if (!grid) return;
	const formatter = (value, df, options, row) => {
		const count = row ? gesc_item_files(frm, row).length : value ? 1 : 0;
		if (!row?.name) return "";
		const label = count ? `${count}` : __("إضافة");
		return `<button type="button" class="btn btn-xs btn-default gesc-item-files" data-row="${row.name}" title="${__("مرفقات الصنف")}">${frappe.utils.icon(
			"es-line-attachment",
			"xs"
		)} ${label}</button>`;
	};
	grid.update_docfield_property("custom_attachment", "formatter", formatter);
	grid.update_docfield_property("custom_attachment", "read_only", 1);
	// The table is drawn before the form's refresh event: drawn again once, with the button.
	if (!grid.__gesc_files_drawn) {
		grid.__gesc_files_drawn = true;
		grid.refresh();
	}
	const wrapper = grid.wrapper?.[0];
	if (wrapper && !wrapper.__gesc_item_files) {
		wrapper.__gesc_item_files = true;
		// Captured before Frappe's own cell click (which would start editing the cell).
		wrapper.addEventListener(
			"click",
			(event) => {
				const button = event.target.closest(".gesc-item-files");
				if (!button) return;
				event.preventDefault();
				event.stopPropagation();
				gesc_open_item_files(frm, button.dataset.row);
			},
			true
		);
	}
}

function gesc_open_item_files(frm, row_name) {
	const row = locals["Quotation Item"]?.[row_name];
	if (!row) return;
	const editable = frm.doc.docstatus === 0 && frappe.model.can_write("Quotation");
	if (editable && frm.is_new()) {
		frappe.msgprint(__("احفظ عرض السعر أولاً، ثم ارفع المرفقات."));
		return;
	}
	if (editable && !row.custom_row_key) frappe.model.set_value(row.doctype, row.name, "custom_row_key", frappe.utils.get_random(12));

	const upload_to = { doctype: frm.doctype, docname: frm.docname };
	const as_row = (file) => ({
		name: frappe.utils.get_random(10),
		attachment: file.attachment,
		attachment_type: file.attachment_type || GESC_ITEM_FILE_TYPE,
		show_in_print: file.show_in_print || 0,
		remarks: file.remarks,
	});

	const dialog = new frappe.ui.Dialog({
		title: __("مرفقات البند {0}: {1}", [row.idx, row.item_name || row.item_code || ""]),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "help",
				options: `<p class="text-muted small">${
					editable
						? __("اختر ملفاً أو أكثر من الجهاز مرة واحدة. أول ملف هو الملف الرئيسي للصنف (يُنقل لأمر البيع)، والباقي ملفات إضافية.")
						: __("عرض فقط؛ المرفقات تُعدَّل في عرض السعر المسودّة.")
				}</p>`,
			},
			{
				fieldtype: "Button",
				fieldname: "upload",
				label: __("اختيار ملفات من الجهاز"),
				hidden: editable ? 0 : 1,
				click: () =>
					new frappe.ui.FileUploader({
						...upload_to,
						allow_multiple: true,
						on_success: (file) => {
							// The first file fills the main file when it is empty; the rest are extras.
							if (!dialog.get_value("main")) {
								dialog.set_value("main", file.file_url);
								return;
							}
							const table = dialog.fields_dict.files;
							table.df.data.push(as_row({ attachment: file.file_url }));
							table.grid.refresh();
						},
					}),
			},
			{
				fieldtype: "Attach",
				fieldname: "main",
				label: __("الملف الرئيسي"),
				default: row.custom_attachment,
				read_only: editable ? 0 : 1,
				options: upload_to,
			},
			{
				fieldtype: "Table",
				fieldname: "files",
				label: __("ملفات إضافية"),
				cannot_add_rows: editable ? 0 : 1,
				cannot_delete_rows: editable ? 0 : 1,
				in_place_edit: true,
				data: gesc_extra_files(frm, row).map(as_row),
				fields: [
					{
						fieldtype: "Attach",
						fieldname: "attachment",
						label: __("الملف"),
						in_list_view: 1,
						columns: 3,
						reqd: 1,
						read_only: editable ? 0 : 1,
						options: upload_to,
					},
					{
						fieldtype: "Link",
						fieldname: "attachment_type",
						label: __("نوع المرفق"),
						options: "Attachment Type",
						in_list_view: 1,
						columns: 3,
						reqd: 1,
						read_only: editable ? 0 : 1,
						get_query: () => ({ filters: { disabled: 0 } }),
					},
					{
						fieldtype: "Check",
						fieldname: "show_in_print",
						label: __("يظهر في الطباعة"),
						in_list_view: 1,
						columns: 1,
						read_only: editable ? 0 : 1,
					},
					{
						fieldtype: "Data",
						fieldname: "remarks",
						label: __("ملاحظات"),
						in_list_view: 1,
						columns: 3,
						read_only: editable ? 0 : 1,
					},
				],
			},
		],
		primary_action_label: editable ? __("حفظ المرفقات") : __("إغلاق"),
		primary_action: () => {
			dialog.hide();
			if (editable) gesc_save_item_files(frm, row, dialog.get_value("main"), dialog.fields_dict.files.df.data);
		},
	});
	dialog.show();
}

// The row's main file and its extra files are replaced by the dialog's, and the
// quotation is saved (the files are already uploaded to it).
function gesc_save_item_files(frm, row, main, files) {
	gesc_extra_files(frm, row).forEach((file) => frappe.model.clear_doc(file.doctype, file.name));
	const extras = (files || []).filter((file) => file.attachment);
	// No main file but extras: the first extra becomes the main file.
	if (!main && extras.length) main = extras.shift().attachment;
	extras.forEach((file) =>
		frm.add_child(GESC_ITEM_FILES_TABLE, {
			linked_to_item: 1,
			item_code: row.item_code,
			row_key: row.custom_row_key,
			attachment: file.attachment,
			attachment_type: file.attachment_type || GESC_ITEM_FILE_TYPE,
			show_in_print: file.show_in_print || 0,
			remarks: file.remarks || __("البند {0}: {1}", [row.idx, row.item_name || row.item_code || ""]),
		})
	);
	frappe.model.set_value(row.doctype, row.name, "custom_attachment", main || "");
	frm.refresh_field(GESC_ITEM_FILES_TABLE);
	frm.refresh_field("items");
	frm.save();
}
