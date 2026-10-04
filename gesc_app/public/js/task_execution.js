// Execution items on Task: the item filter, edit locks that mirror the server rules, the
// dialogs the Site Engineer fills in before approving or sending notes, and for
// pre-quotation inspections the item descriptions and the Quotation made from the task.
// Submittals (materials, drawings, calculations): the files tables, the rows the
// consultant rejects, and the Material Request of an approved material submittal.
(() => {
	const STATE_OPEN = "مفتوحة";
	const STATE_IN_PROGRESS = "جاري العمل";
	const STATE_INSPECTED = "تم المعاينة";
	const TECHNICAL_OFFICE_STATES = [
		"في انتظار مراجعة المكتب الفني",
		"جاري العمل",
		"يوجد ملاحظات",
		"جاري العمل على الملاحظات",
		"تم المعاينة",
	];
	const REWORK_STATES = ["يوجد ملاحظات", "جاري العمل على الملاحظات"];
	const ACTION_APPROVE = "اعتماد";
	const ACTION_NOTES = "يوجد ملاحظات";
	const STATE_INSPECTION_DONE = "تم التنفيذ";
	// Material submittals: items are prepared while open or in progress, and the
	// consultant's answer is recorded while the submittal is with them.
	const SUBMITTAL_PREPARING_STATES = [STATE_OPEN, "جاري العمل"];
	const STATE_SUBMITTED = "تم الإرسال للاستشاري";
	const STATE_CORRECTIONS = "مرفوض – تعديلات مطلوبة";
	const FINAL_SUBMITTAL_STATES = ["معتمد", "معتمد بملاحظات"];
	const ACTION_CODE_CORRECTIONS = "رد: Rejected – Corrections Required";
	const RESPONSE_ACTIONS = [
		"رد: Approved",
		"رد: Approved with Comments",
		ACTION_CODE_CORRECTIONS,
		"رد: Rejected – Rework Required",
	];

	// Each kind of submittal: the table it sends and the name of its tab.
	const SUBMITTAL_KINDS = {
		custom_is_material_submittal: { table: "custom_execution_items", tab: "بنود التنفيذ" },
		custom_is_drawing_submittal: { table: "custom_drawings", tab: "الرسومات" },
		custom_is_calculation_submittal: { table: "custom_calculations", tab: "الحسابات الإنشائية" },
	};
	const FILE_TABLES = ["custom_technical_office_attachments", "custom_drawings", "custom_calculations"];
	const FILE_FIELDS = ["attachment", "attachment_type", "notes"];

	// Columns of the items grid for each kind of task (sizes add up to 10). The item's
	// name shows under its code and the unit beside the quantity (format_execution_grids).
	const ITEM_COLUMNS = {
		execution: {
			item_code: 2,
			item_description: 2,
			description: 2,
			qty: 1,
			is_rejected: 1,
			site_engineer_files: 1,
			technical_office_files: 1,
		},
		inspection: {
			item_code: 2,
			item_description: 2,
			description: 3,
			qty: 1,
			site_engineer_files: 1,
			technical_office_files: 1,
		},
		submittal: {
			item_code: 2,
			item_description: 2,
			description: 3,
			qty: 1,
			is_rejected: 1,
			technical_office_files: 1,
		},
	};

	const SITE_ENGINEER_FIELDS = ["item_code", "site_engineer_notes", "initial_qty"];
	// The description stays open while the task is with the Technical Office.
	const DESCRIPTION_FIELDS = ["item_description", "description"];
	const TECHNICAL_OFFICE_FIELDS = ["qty", "technical_office_notes"];

	// Each item has several files from each side, kept in one table on the task and tied
	// to the item by its row_key; the item shows how many files each side has.
	const ITEM_ATTACHMENTS = "custom_execution_item_attachments";
	const SITE_ENGINEER_ROLE = "مهندس الموقع";
	const TECHNICAL_OFFICE_ROLE = "المكتب الفني";
	const ITEM_FILE_COUNTS = {
		[SITE_ENGINEER_ROLE]: "site_engineer_files",
		[TECHNICAL_OFFICE_ROLE]: "technical_office_files",
	};

	keep_replaced_attachments();
	add_execution_grid_style();

	// The items grid: descriptions wrap over two lines, counts and ticks sit centred, and
	// rows breathe a little more than Frappe's single-line default.
	function add_execution_grid_style() {
		if (document.getElementById("gesc-execution-grid-style")) return;
		const grid = ".gesc-execution-grid";
		$(`<style id="gesc-execution-grid-style">
			${grid} .grid-body .data-row .grid-static-col { padding-top: 8px; padding-bottom: 8px; }
			${grid} .grid-static-col[data-fieldname="description"] .static-area,
			${grid} .grid-static-col[data-fieldname="item_description"] .static-area {
				white-space: normal; display: -webkit-box; -webkit-line-clamp: 2;
				-webkit-box-orient: vertical; overflow: hidden; line-height: 1.4;
			}
			${grid} .grid-static-col[data-fieldname="item_code"] .static-area { white-space: normal; line-height: 1.35; }
			${grid} .grid-static-col[data-fieldname="site_engineer_files"],
			${grid} .grid-static-col[data-fieldname="technical_office_files"],
			${grid} .grid-static-col[data-fieldname="is_rejected"] { text-align: center; }
			${grid} .gesc-item-files { min-width: 52px; border-radius: 999px; }
			${grid} .grid-heading-row .grid-static-col { font-weight: 600; white-space: normal; line-height: 1.3; }
		</style>`).appendTo(document.head);
	}

	frappe.ui.form.on("Task", {
		setup(frm) {
			// Inspection items end up in a Quotation, so they are items the company sells.
			frm.set_query("item_code", "custom_execution_items", () => ({
				filters: frm.doc.custom_is_pre_quotation_inspection
					? { is_sales_item: 1, disabled: 0 }
					: { is_purchase_item: 1, disabled: 0 },
			}));
			frm.set_query("item_description", "custom_execution_items", (doc, cdt, cdn) => ({
				filters: { item_code: locals[cdt][cdn].item_code || "__no_item_selected__" },
			}));
			["custom_execution_items", ...FILE_TABLES].forEach((table) =>
				frm.set_query("attachment_type", table, () => ({ filters: { disabled: 0 } }))
			);
		},

		custom_execution_items_add(frm, cdt, cdn) {
			locals[cdt][cdn].row_key = frappe.utils.get_random(12);
		},

		refresh(frm) {
			set_item_columns(frm);
			set_tab_label(frm);
			format_execution_grids(frm);
			lock_execution_items(frm);
			lock_file_tables(frm);
			show_intro(frm);
			add_quotation_button(frm);
			add_material_request_button(frm);
		},

		before_workflow_action(frm) {
			const action = frm.selected_workflow_action;
			if (submittal_kind(frm) && action === ACTION_CODE_CORRECTIONS) {
				frappe.dom.unfreeze();
				return ask_for_rejections(frm).then((rows) =>
					save_before_action("gesc_app.gesc_app.material_submittal.save_rejections", {
						task: frm.doc.name,
						rows,
					})
				);
			}
			if (submittal_kind(frm) && RESPONSE_ACTIONS.includes(action)) {
				return confirm_response(action);
			}
			if (!frm.doc.custom_has_work_items || ![ACTION_APPROVE, ACTION_NOTES].includes(action)) {
				return;
			}

			// The workflow froze the page before asking; the dialog needs it back.
			frappe.dom.unfreeze();
			const ask = action === ACTION_APPROVE ? ask_for_date : ask_for_notes;
			return ask(frm).then((values) =>
				save_before_action("gesc_app.gesc_app.task_execution.save_review", {
					task: frm.doc.name,
					action,
					...values,
				})
			);
		},
	});

	// Values chosen in a dialog are saved before the workflow action, which reloads the
	// task from the database.
	function save_before_action(method, args) {
		frappe.dom.freeze();
		return frappe
			.xcall(method, args)
			.then((doc) => frappe.model.sync(doc))
			.catch(() => {
				// The server message is already shown; stop here without running the action.
				frappe.dom.unfreeze();
				return new Promise(() => {});
			});
	}

	function submittal_kind(frm) {
		const flag = Object.keys(SUBMITTAL_KINDS).find((f) => frm.doc[f]);
		return flag ? SUBMITTAL_KINDS[flag] : null;
	}

	// Grid columns follow the kind of task; the grid is rebuilt only when that changes.
	function set_item_columns(frm) {
		const grid = frm.get_field("custom_execution_items")?.grid;
		if (!grid) return;
		const kind = frm.doc.custom_is_pre_quotation_inspection
			? "inspection"
			: frm.doc.custom_is_material_submittal
			? "submittal"
			: "execution";
		const key = `${frm.doc.name}:${kind}`;
		if (grid.__columns_key === key) return;
		grid.__columns_key = key;

		const columns = ITEM_COLUMNS[kind];
		(grid.docfields || []).forEach((df) => {
			if (frappe.model.layout_fields.includes(df.fieldtype)) return;
			df.in_list_view = columns[df.fieldname] ? 1 : 0;
			if (columns[df.fieldname]) df.columns = columns[df.fieldname];
		});
		grid.reset_grid();
	}

	function set_tab_label(frm) {
		const label = submittal_kind(frm)?.tab || "بنود التنفيذ";
		const tab = (frm.layout?.tabs || []).find((t) => t.df?.fieldname === "custom_execution_tab");
		tab?.tab_link?.find(".nav-link").text(__(label));
	}

	frappe.ui.form.on("Task Execution Item", {
		item_code(frm, cdt, cdn) {
			if (locals[cdt][cdn].item_description) {
				frappe.model.set_value(cdt, cdn, "item_description", "");
			}
		},

		// The library text fills the description, which can then be edited.
		item_description(frm, cdt, cdn) {
			const row = locals[cdt][cdn];
			if (!row.item_description) return;
			frappe.db.get_value("Item Description", row.item_description, "description").then(({ message }) => {
				if (message) frappe.model.set_value(cdt, cdn, "description", message.description);
			});
		},
	});

	// The Quotation is made on starting work; the button opens it, or makes it again if
	// it was deleted.
	function add_quotation_button(frm) {
		if (
			!frm.doc.custom_is_pre_quotation_inspection ||
			![STATE_IN_PROGRESS, STATE_INSPECTION_DONE].includes(frm.doc.workflow_state) ||
			!frappe.model.can_create("Quotation")
		) {
			return;
		}
		frm.add_custom_button(
			__("عرض سعر"),
			() => {
				frappe
					.xcall("gesc_app.gesc_app.task_execution.get_task_quotation", { task: frm.doc.name })
					.then((quotation) => {
						if (quotation) {
							frappe.set_route("Form", "Quotation", quotation);
						} else {
							frappe.model.open_mapped_doc({
								method: "gesc_app.gesc_app.task_execution.make_quotation",
								frm,
							});
						}
					});
			},
			__("Create")
		);
	}

	function add_material_request_button(frm) {
		if (
			!frm.doc.custom_is_material_submittal ||
			!FINAL_SUBMITTAL_STATES.includes(frm.doc.workflow_state) ||
			frm.doc.custom_material_request ||
			!(
				frappe.user.has_role(["Site Engineer", "Technical Office", "Projects Manager"]) ||
				frappe.model.can_create("Material Request")
			)
		) {
			return;
		}
		frm.add_custom_button(__("طلب مواد"), () => ask_for_material_request(frm), __("Create"));
	}

	// In a narrow grid column a file path shows as "...g.png/" and a read-only tick is hard
	// to tell from an empty box.
	function format_execution_grids(frm) {
		const items = frm.get_field("custom_execution_items")?.grid;
		if (items) {
			Object.entries(ITEM_FILE_COUNTS).forEach(([role, fieldname]) =>
				set_grid_property(items, fieldname, "formatter", (value, df, options, row) =>
					format_item_files(frm, role, value, row)
				)
			);
			set_grid_property(items, "is_rejected", "formatter", format_rejected);
			set_grid_property(items, "item_code", "formatter", format_item);
			set_grid_property(items, "qty", "formatter", format_qty);
			items.wrapper.addClass("gesc-execution-grid");
			// Caught on the way down, so the click does not open the row as well.
			const wrapper = items.wrapper?.get(0);
			if (wrapper && !wrapper.__item_files_click) {
				wrapper.addEventListener(
					"click",
					(event) => {
						const button = event.target.closest(".gesc-item-files");
						if (!button) return;
						event.preventDefault();
						event.stopPropagation();
						open_item_files(frm, button.dataset.row, button.dataset.role);
					},
					true
				);
				wrapper.__item_files_click = true;
			}
		}
		FILE_TABLES.forEach((table) => {
			const grid = frm.get_field(table)?.grid;
			if (!grid) return;
			set_grid_property(grid, "attachment", "formatter", format_file);
			set_grid_property(grid, "is_rejected", "formatter", format_rejected);
		});
		const history = frm.get_field("custom_execution_documents")?.grid;
		if (history) set_grid_property(history, "file", "formatter", format_file);
		const revisions = frm.get_field("custom_submittal_revisions")?.grid;
		if (revisions) {
			set_grid_property(revisions, "response_code", "formatter", format_response_code);
			set_grid_property(revisions, "response_file", "formatter", format_file);
		}
	}

	// The consultant's code in a narrow column: its number and a short name, coloured.
	const RESPONSE_CODE_LABELS = {
		Approved: [1, "green", "Approved"],
		"Approved with Comments": [2, "blue", "with Comments"],
		"Rejected – Corrections Required": [3, "orange", "Corrections"],
		"Rejected – Rework Required": [4, "red", "Rework"],
	};

	function format_response_code(value) {
		const code = RESPONSE_CODE_LABELS[value];
		if (!code) return value || "";
		return `<span class="indicator-pill ${code[1]}" title="${frappe.utils.escape_html(value)}">${code[0]} · ${code[2]}</span>`;
	}

	function format_file(value) {
		if (!value) return "";
		const name = frappe.utils.escape_html(decodeURIComponent(value.split("/").pop()));
		return `<a href="${encodeURI(value)}" target="_blank" rel="noopener" title="${name}">${frappe.utils.icon(
			"es-line-attachment",
			"xs"
		)} ${__("عرض")}</a>`;
	}

	// The count of an item's files from one side, as a button that opens them.
	function format_item_files(frm, role, value, row) {
		const count = cint(value);
		if (!row?.name || (!count && !can_edit_item_files(frm, role))) return "";
		const label = count ? `${count}` : __("إضافة");
		return `<button type="button" class="btn btn-xs btn-default gesc-item-files"
			data-row="${frappe.utils.escape_html(row.name)}" data-role="${frappe.utils.escape_html(role)}"
			title="${frappe.utils.escape_html(role)}">${frappe.utils.icon("es-line-attachment", "xs")} ${label}</button>`;
	}

	// An item's files from one side: listed with their type and notes, and changed by that
	// side while the task is with it. Several files can be uploaded at once.
	function open_item_files(frm, row_name, role) {
		const row = locals["Task Execution Item"]?.[row_name];
		if (!row) return;
		const editable = can_edit_item_files(frm, role);
		if (editable && frm.is_new()) {
			frappe.msgprint(__("احفظ المهمة أولاً، ثم ارفع المرفقات."));
			return;
		}
		if (!row.row_key) frappe.model.set_value(row.doctype, row.name, "row_key", frappe.utils.get_random(12));

		const upload_to = { doctype: frm.doctype, docname: frm.docname };
		const as_row = (file) => ({
			name: frappe.utils.get_random(10),
			attachment: file.attachment,
			attachment_type: file.attachment_type,
			notes: file.notes,
		});
		const current = (frm.doc[ITEM_ATTACHMENTS] || []).filter(
			(file) => file.row_key === row.row_key && file.uploaded_by_role === role
		);

		const dialog = new frappe.ui.Dialog({
			title: __("{0} – البند {1}: {2}", [role, row.idx, row.item_name || row.item_code || ""]),
			size: "large",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "help",
					options: `<p class="text-muted small">${
						editable
							? __("ارفع ملفاً أو أكثر مرة واحدة، وحدد نوع كل ملف وملاحظاته. الملف المحذوف من البند يبقى في سجل المستندات.")
							: __("عرض فقط؛ المرفقات تُعدَّل من الجهة المسئولة والمهمة في المرحلة الخاصة بها.")
					}</p>`,
				},
				{
					fieldtype: "Button",
					fieldname: "upload",
					label: __("رفع ملفات"),
					hidden: editable ? 0 : 1,
					click: () =>
						new frappe.ui.FileUploader({
							...upload_to,
							allow_multiple: true,
							on_success: (file) => {
								const table = dialog.fields_dict.files;
								table.df.data.push(as_row({ attachment: file.file_url }));
								table.grid.refresh();
							},
						}),
				},
				{
					fieldtype: "Table",
					fieldname: "files",
					label: __("الملفات"),
					cannot_add_rows: editable ? 0 : 1,
					cannot_delete_rows: editable ? 0 : 1,
					in_place_edit: true,
					data: current.map(as_row),
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
							formatter: format_file,
						},
						{
							fieldtype: "Link",
							fieldname: "attachment_type",
							label: __("نوع المرفق"),
							options: "Attachment Type",
							in_list_view: 1,
							columns: 3,
							read_only: editable ? 0 : 1,
							get_query: () => ({ filters: { disabled: 0 } }),
						},
						{
							fieldtype: "Data",
							fieldname: "notes",
							label: __("ملاحظات"),
							in_list_view: 1,
							columns: 4,
							read_only: editable ? 0 : 1,
						},
					],
				},
			],
			primary_action_label: editable ? __("حفظ المرفقات") : __("إغلاق"),
			primary_action: () => {
				dialog.hide();
				if (editable) save_item_files(frm, row, role, dialog.fields_dict.files.df.data);
			},
		});
		dialog.show();
	}

	// The side's files on the item are replaced by the dialog's, and the task is saved.
	function save_item_files(frm, row, role, files) {
		(frm.doc[ITEM_ATTACHMENTS] || [])
			.filter((file) => file.row_key === row.row_key && file.uploaded_by_role === role)
			.forEach((file) => frappe.model.clear_doc(file.doctype, file.name));
		files
			.filter((file) => file.attachment)
			.forEach((file) =>
				frm.add_child(ITEM_ATTACHMENTS, {
					row_key: row.row_key,
					row_no: row.idx,
					item_code: row.item_code,
					uploaded_by_role: role,
					attachment: file.attachment,
					attachment_type: file.attachment_type,
					notes: file.notes,
				})
			);
		const count = (frm.doc[ITEM_ATTACHMENTS] || []).filter(
			(file) => file.row_key === row.row_key && file.uploaded_by_role === role
		).length;
		frappe.model.set_value(row.doctype, row.name, ITEM_FILE_COUNTS[role], count);
		frm.save();
	}

	// The item code with its name beneath it.
	function format_item(value, df, options, row) {
		if (!value) return "";
		const link = frappe.form.formatters.Link(value, { fieldtype: "Link", options: "Item" }, options, row);
		const name = row?.item_name && row.item_name !== value ? row.item_name : "";
		return name
			? `${link}<div class="text-muted small ellipsis" title="${frappe.utils.escape_html(name)}">${frappe.utils.escape_html(name)}</div>`
			: link;
	}

	// The quantity with its unit.
	function format_qty(value, df, options, row) {
		if (value === null || value === undefined || value === "") return "";
		const qty = frappe.form.formatters.Float(value, { fieldtype: "Float" }, { inline: true });
		const uom = row?.uom ? ` <span class="text-muted small">${frappe.utils.escape_html(__(row.uom))}</span>` : "";
		return `<span class="bold">${qty}</span>${uom}`;
	}

	function format_rejected(value) {
		return cint(value) ? `<span class="text-danger bold">${__("مرفوض")}</span>` : "";
	}

	// update_docfield_property skips the grid before its first render, so the template
	// for new rows is set too.
	function set_grid_property(grid, fieldname, property, value) {
		const df = (grid.docfields || []).find((d) => d.fieldname === fieldname);
		if (df) df[property] = value;
		grid.update_docfield_property(fieldname, property, value);
	}

	// The consultant's code is recorded for good, so it is confirmed first.
	function confirm_response(action) {
		frappe.dom.unfreeze();
		return new Promise((resolve) => {
			frappe.confirm(
				__("تسجيل رد الاستشاري بالكود «{0}»؟ سيُحفظ الملف المختوم والملاحظات في سجل المراجعات.", [
					action.replace("رد: ", ""),
				]),
				() => {
					frappe.dom.freeze();
					resolve();
				}
			);
		});
	}

	// When each side can change its part of the items, as the server allows it.
	function item_edit_access(frm) {
		const state = frm.doc.workflow_state || STATE_OPEN;
		const is_submittal = !!frm.doc.custom_is_material_submittal;
		const is_open = is_submittal ? SUBMITTAL_PREPARING_STATES.includes(state) : state === STATE_OPEN;
		// Once work starts on an inspection, quantities and files go in its Quotation.
		const with_technical_office = is_submittal
			? is_open
			: frm.doc.custom_is_pre_quotation_inspection
			? state === STATE_INSPECTED
			: TECHNICAL_OFFICE_STATES.includes(state);
		return { is_submittal, is_open, with_technical_office };
	}

	// Each side changes its own files: the Technical Office's are on field level 1, like
	// its other columns.
	function can_edit_item_files(frm, role) {
		const access = item_edit_access(frm);
		return role === SITE_ENGINEER_ROLE
			? access.is_open
			: access.with_technical_office && !!frm.perm?.[1]?.write;
	}

	function lock_execution_items(frm) {
		const grid = frm.get_field("custom_execution_items")?.grid;
		if (!grid) return;

		const { is_submittal, is_open, with_technical_office } = item_edit_access(frm);

		set_grid_property(grid, "manufacturer", "read_only", is_open ? 0 : 1);
		set_grid_property(grid, "site_engineer_section", "label", is_submittal ? __("بيانات المادة") : __("مهندس الموقع"));

		SITE_ENGINEER_FIELDS.forEach((fieldname) =>
			set_grid_property(grid, fieldname, "read_only", is_open ? 0 : 1)
		);
		DESCRIPTION_FIELDS.forEach((fieldname) =>
			set_grid_property(grid, fieldname, "read_only", is_open || with_technical_office ? 0 : 1)
		);
		TECHNICAL_OFFICE_FIELDS.forEach((fieldname) =>
			set_grid_property(grid, fieldname, "read_only", with_technical_office ? 0 : 1)
		);
		frm.set_df_property("custom_execution_items", "cannot_add_rows", is_open ? 0 : 1);
		frm.set_df_property("custom_execution_items", "cannot_delete_rows", is_open ? 0 : 1);
	}

	// Submittal files are prepared while open or in progress, like the items.
	function lock_file_tables(frm) {
		const editable = SUBMITTAL_PREPARING_STATES.includes(frm.doc.workflow_state || STATE_OPEN);
		FILE_TABLES.forEach((table) => {
			const grid = frm.get_field(table)?.grid;
			if (!grid) return;
			FILE_FIELDS.forEach((fieldname) => set_grid_property(grid, fieldname, "read_only", editable ? 0 : 1));
			frm.set_df_property(table, "cannot_add_rows", editable ? 0 : 1);
			frm.set_df_property(table, "cannot_delete_rows", editable ? 0 : 1);
		});

		// Files for the whole task are not answered by the consultant row by row.
		const task_files = frm.get_field("custom_technical_office_attachments")?.grid;
		if (task_files && !task_files.__answer_hidden && task_files.set_column_disp_in_list_view) {
			task_files.set_column_disp_in_list_view(["is_rejected", "consultant_notes"], false);
			task_files.__answer_hidden = true;
		}
	}

	function show_intro(frm) {
		const rejected = (frm.doc.custom_execution_items || []).filter((row) => row.is_rejected);
		const kind = submittal_kind(frm);
		const rejected_by_consultant = kind
			? (frm.doc[kind.table] || []).filter((row) => row.is_rejected)
			: [];
		const overdue =
			kind &&
			frm.doc.workflow_state === STATE_SUBMITTED &&
			frm.doc.custom_response_due_date &&
			frappe.datetime.get_day_diff(frappe.datetime.get_today(), frm.doc.custom_response_due_date);
		if (overdue > 0) {
			frm.set_intro(
				__("رد الاستشاري متأخر {0} يوم (كان متوقعاً في {1}).", [
					overdue,
					frappe.datetime.str_to_user(frm.doc.custom_response_due_date),
				]),
				"red"
			);
			frm.__execution_intro = true;
		} else if (
			kind &&
			[STATE_CORRECTIONS, STATE_IN_PROGRESS].includes(frm.doc.workflow_state) &&
			rejected_by_consultant.length
		) {
			frm.set_intro(
				__("رفض الاستشاري البنود: {0}. ملاحظته مكتوبة على كل بند مرفوض.", [
					rejected_by_consultant.map((row) => row.idx).join("، "),
				]),
				"orange"
			);
			frm.__execution_intro = true;
		} else if (!kind && REWORK_STATES.includes(frm.doc.workflow_state) && rejected.length) {
			frm.set_intro(
				__("البنود المرفوضة: {0}. ملاحظات مهندس الموقع موجودة في كل بند.", [
					rejected.map((row) => row.idx).join("، "),
				]),
				"orange"
			);
			frm.__execution_intro = true;
		} else if (frm.doc.custom_is_pre_quotation_inspection && frm.doc.workflow_state === STATE_IN_PROGRESS) {
			frm.set_intro(
				frm.doc.custom_quotation
					? __(
							"الكميات والأسعار ومرفقات البنود تُستكمل في عرض السعر {0}، وتكتمل المهمة تلقائياً عند تسجيله نهائياً (Submit).",
							[frm.doc.custom_quotation]
					  )
					: __("لا يوجد عرض سعر للمعاينة؛ أنشئه من «Create > عرض سعر»."),
				"blue"
			);
			frm.__execution_intro = true;
		} else if (frm.__execution_intro) {
			frm.set_intro("");
			frm.__execution_intro = false;
		}
	}

	function ask_for_date(frm) {
		return new Promise((resolve) => {
			const count = (frm.doc.custom_execution_items || []).length;
			const dialog = new frappe.ui.Dialog({
				title: __("اعتماد"),
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "summary",
						options: `<p class="text-muted">${__(
							"سيتم إنشاء طلب مواد (شراء) بعدد {0} بند على مخزن المشروع.",
							[count]
						)}</p>`,
					},
					{
						fieldname: "required_by_date",
						fieldtype: "Date",
						label: __("تاريخ الاحتياج"),
						reqd: 1,
						default: frm.doc.custom_required_by_date || frappe.datetime.get_today(),
					},
				],
				primary_action_label: __("اعتماد"),
				primary_action({ required_by_date }) {
					if (required_by_date < frappe.datetime.get_today()) {
						frappe.msgprint(__("تاريخ الاحتياج لا يمكن أن يكون في الماضي."));
						return;
					}
					dialog.hide();
					resolve({ required_by_date });
				},
			});
			dialog.show();
		});
	}

	function ask_for_notes(frm) {
		return new Promise((resolve) => {
			const dialog = new frappe.ui.Dialog({
				title: __("يوجد ملاحظات"),
				size: "extra-large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "help",
						options: `<p class="text-muted">${__(
							"علّم البنود المرفوضة واكتب ملاحظة لكل بند مرفوض، وسترجع المهمة للمكتب الفني."
						)}</p>`,
					},
					{
						fieldname: "items",
						fieldtype: "Table",
						label: __("البنود"),
						cannot_add_rows: true,
						cannot_delete_rows: true,
						in_place_edit: true,
						data: (frm.doc.custom_execution_items || []).map((row) => ({
							row_name: row.name,
							item_code: row.item_code,
							item_name: row.item_name,
							is_rejected: row.is_rejected,
							notes: row.site_engineer_approval_notes,
						})),
						fields: [
							{ fieldname: "row_name", fieldtype: "Data", hidden: 1 },
							{
								fieldname: "item_code",
								fieldtype: "Link",
								options: "Item",
								label: __("كود الصنف"),
								read_only: 1,
								in_list_view: 1,
								columns: 2,
							},
							{
								fieldname: "item_name",
								fieldtype: "Data",
								label: __("اسم الصنف"),
								read_only: 1,
								in_list_view: 1,
								columns: 3,
							},
							{
								fieldname: "is_rejected",
								fieldtype: "Check",
								label: __("مرفوض"),
								in_list_view: 1,
								columns: 1,
							},
							{
								fieldname: "notes",
								fieldtype: "Small Text",
								label: __("ملاحظات الاعتماد"),
								in_list_view: 1,
								columns: 4,
							},
						],
					},
				],
				primary_action_label: __("إرسال الملاحظات"),
				primary_action({ items }) {
					const rows = items || [];
					if (!rows.some((row) => row.is_rejected)) {
						frappe.msgprint(__("علّم بنداً مرفوضاً واحداً على الأقل."));
						return;
					}
					const without_notes = rows
						.filter((row) => row.is_rejected && !(row.notes || "").trim())
						.map((row) => row.idx);
					if (without_notes.length) {
						frappe.msgprint(
							__("اكتب ملاحظات الاعتماد للبنود المرفوضة: {0}", [without_notes.join("، ")])
						);
						return;
					}
					dialog.hide();
					resolve({
						rows: rows.map((row) => ({
							name: row.row_name,
							is_rejected: row.is_rejected ? 1 : 0,
							notes: row.notes || "",
						})),
					});
				},
			});
			dialog.show();
		});
	}

	// Code 3: the Document Controller marks the rows the consultant rejected, each with
	// the consultant's note, and the task goes back to the Technical Office.
	function ask_for_rejections(frm) {
		const kind = submittal_kind(frm);
		return new Promise((resolve) => {
			const dialog = new frappe.ui.Dialog({
				title: __("Rejected – Corrections Required"),
				size: "extra-large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "help",
						options: `<p class="text-muted">${__(
							"علّم البنود التي رفضها الاستشاري واكتب ملاحظته على كل بند مرفوض، وسترجع المهمة للمكتب الفني للتعديل."
						)}</p>`,
					},
					{
						fieldname: "items",
						fieldtype: "Table",
						label: __("البنود"),
						cannot_add_rows: true,
						cannot_delete_rows: true,
						in_place_edit: true,
						data: (frm.doc[kind.table] || []).map((row) => ({
							row_name: row.name,
							row_no: row.idx,
							label: row_label(row),
							is_rejected: row.is_rejected,
							notes: row.consultant_notes,
						})),
						fields: [
							{ fieldname: "row_name", fieldtype: "Data", hidden: 1 },
							{
								fieldname: "row_no",
								fieldtype: "Int",
								label: __("م"),
								read_only: 1,
								in_list_view: 1,
								columns: 1,
							},
							{
								fieldname: "label",
								fieldtype: "Data",
								label: __("البند"),
								read_only: 1,
								in_list_view: 1,
								columns: 4,
							},
							{
								fieldname: "is_rejected",
								fieldtype: "Check",
								label: __("مرفوض"),
								in_list_view: 1,
								columns: 1,
							},
							{
								fieldname: "notes",
								fieldtype: "Small Text",
								label: __("ملاحظات الاستشاري"),
								in_list_view: 1,
								columns: 4,
							},
						],
					},
				],
				primary_action_label: __("تسجيل الرد"),
				primary_action({ items }) {
					const rows = items || [];
					if (!rows.some((row) => row.is_rejected)) {
						frappe.msgprint(__("علّم بنداً مرفوضاً واحداً على الأقل."));
						return;
					}
					const without_notes = rows
						.filter((row) => row.is_rejected && !(row.notes || "").trim())
						.map((row) => row.row_no);
					if (without_notes.length) {
						frappe.msgprint(
							__("اكتب ملاحظات الاستشاري للبنود المرفوضة: {0}", [without_notes.join("، ")])
						);
						return;
					}
					dialog.hide();
					resolve(
						rows.map((row) => ({
							name: row.row_name,
							is_rejected: row.is_rejected ? 1 : 0,
							notes: row.notes || "",
						}))
					);
				},
			});
			dialog.show();
		});
	}

	function row_label(row) {
		if (row.doctype === "Task Execution Item") {
			return [row.item_code, row.item_name].filter(Boolean).join(": ");
		}
		const name = decodeURIComponent((row.attachment || "").split("/").pop());
		return [row.attachment_type, name].filter(Boolean).join(" - ");
	}

	// An approved material submittal: a purchase request on the project warehouse with the
	// quantity to buy now for each material.
	function ask_for_material_request(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("طلب مواد"),
			size: "large",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "help",
					options: `<p class="text-muted">${__(
						"طلب شراء على مخزن المشروع بالمواد المعتمدة. اكتب الكمية المطلوبة الآن لكل مادة؛ المادة بكمية صفر لا تدخل الطلب."
					)}</p>`,
				},
				{
					fieldname: "required_by_date",
					fieldtype: "Date",
					label: __("تاريخ الاحتياج"),
					reqd: 1,
					default: frappe.datetime.get_today(),
				},
				{
					fieldname: "items",
					fieldtype: "Table",
					label: __("المواد"),
					cannot_add_rows: true,
					cannot_delete_rows: true,
					in_place_edit: true,
					data: (frm.doc.custom_execution_items || []).map((row) => ({
						row_name: row.name,
						item_code: row.item_code,
						item_name: row.item_name,
						uom: row.uom,
						qty: row.qty,
					})),
					fields: [
						{ fieldname: "row_name", fieldtype: "Data", hidden: 1 },
						{
							fieldname: "item_code",
							fieldtype: "Link",
							options: "Item",
							label: __("كود الصنف"),
							read_only: 1,
							in_list_view: 1,
							columns: 3,
						},
						{
							fieldname: "item_name",
							fieldtype: "Data",
							label: __("اسم الصنف"),
							read_only: 1,
							in_list_view: 1,
							columns: 4,
						},
						{
							fieldname: "uom",
							fieldtype: "Link",
							options: "UOM",
							label: __("الوحدة"),
							read_only: 1,
							in_list_view: 1,
							columns: 1,
						},
						{
							fieldname: "qty",
							fieldtype: "Float",
							label: __("الكمية المطلوبة"),
							in_list_view: 1,
							columns: 2,
						},
					],
				},
			],
			primary_action_label: __("إنشاء طلب المواد"),
			primary_action({ required_by_date, items }) {
				if (required_by_date < frappe.datetime.get_today()) {
					frappe.msgprint(__("تاريخ الاحتياج لا يمكن أن يكون في الماضي."));
					return;
				}
				const rows = (items || []).map((row) => ({ name: row.row_name, qty: row.qty || 0 }));
				if (!rows.some((row) => row.qty > 0)) {
					frappe.msgprint(__("أدخل الكمية المطلوبة لمادة واحدة على الأقل."));
					return;
				}
				dialog.hide();
				frappe
					.xcall("gesc_app.gesc_app.material_submittal.make_material_request", {
						task: frm.doc.name,
						required_by_date,
						rows,
					})
					.then((material_request) => {
						frappe.show_alert({
							message: __("تم إنشاء طلب المواد {0}", [material_request]),
							indicator: "green",
						});
						frm.reload_doc();
					});
			},
		});
		dialog.show();
	}

	// Clearing an attachment deletes its file. On execution items and submittal files the
	// old file is part of the document history, so only the field is emptied and the file
	// stays on the task.
	function keep_replaced_attachments() {
		const proto = frappe.ui.form.ControlAttach.prototype;
		if (proto.__keeps_execution_history) return;

		const clear_attachment = proto.clear_attachment;
		proto.clear_attachment = function () {
			// The items' own files are changed in their dialog (open_item_files).
			if (this.df?.parent !== "Task Submittal Attachment" || !this.frm) {
				return clear_attachment.call(this);
			}
			frappe.confirm(__("إزالة المرفق من البند؟ سيبقى الملف محفوظاً في سجل المستندات."), async () => {
				// A submittal file row cannot be saved without its file; the next one is uploaded first.
				await this.parse_validate_and_set_in_model(null);
				this.refresh();
			});
		};
		proto.__keeps_execution_history = true;
	}
})();
