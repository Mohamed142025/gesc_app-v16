// Execution items on Task: the item filter, edit locks that mirror the server rules, the
// dialogs the Site Engineer fills in before approving or sending notes, and for
// pre-quotation inspections the item descriptions and the Quotation made from the task.
(() => {
	const STATE_OPEN = "مفتوحة";
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
	const RESPONSE_ACTIONS = [
		"رد: Approved",
		"رد: Approved with Comments",
		"رد: Rejected – Corrections Required",
		"رد: Rejected – Rework Required",
	];

	const SITE_ENGINEER_FIELDS = [
		"item_code",
		"site_engineer_attachment",
		"site_engineer_notes",
		"item_description",
		"description",
		"initial_qty",
	];
	const TECHNICAL_OFFICE_FIELDS = ["qty", "technical_office_attachment", "technical_office_notes"];

	keep_replaced_attachments();

	frappe.ui.form.on("Task", {
		setup(frm) {
			frm.set_query("item_code", "custom_execution_items", () => ({
				filters: { is_purchase_item: 1, disabled: 0 },
			}));
			frm.set_query("item_description", "custom_execution_items", (doc, cdt, cdn) => ({
				filters: { item_code: locals[cdt][cdn].item_code || "__no_item_selected__" },
			}));
		},

		refresh(frm) {
			format_execution_grids(frm);
			lock_execution_items(frm);
			show_rejected_items(frm);
			add_quotation_button(frm);
		},

		before_workflow_action(frm) {
			const action = frm.selected_workflow_action;
			if (frm.doc.custom_is_material_submittal && RESPONSE_ACTIONS.includes(action)) {
				return confirm_response(action);
			}
			if (!frm.doc.custom_has_work_items || ![ACTION_APPROVE, ACTION_NOTES].includes(action)) {
				return;
			}

			// The workflow froze the page before asking; the dialog needs it back.
			frappe.dom.unfreeze();
			const ask = action === ACTION_APPROVE ? ask_for_date : ask_for_notes;
			return ask(frm).then((values) => {
				frappe.dom.freeze();
				return frappe
					.xcall("gesc_app.gesc_app.task_execution.save_review", {
						task: frm.doc.name,
						action,
						...values,
					})
					.then((doc) => frappe.model.sync(doc))
					.catch(() => {
						// The server message is already shown; stop here without running the action.
						frappe.dom.unfreeze();
						return new Promise(() => {});
					});
			});
		},
	});

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

	function add_quotation_button(frm) {
		if (
			!frm.doc.custom_is_pre_quotation_inspection ||
			frm.doc.workflow_state !== STATE_INSPECTION_DONE ||
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

	// In a narrow grid column a file path shows as "...g.png/" and a read-only tick is hard
	// to tell from an empty box.
	function format_execution_grids(frm) {
		const items = frm.get_field("custom_execution_items")?.grid;
		if (items) {
			set_grid_property(items, "site_engineer_attachment", "formatter", format_file);
			set_grid_property(items, "technical_office_attachment", "formatter", format_file);
			set_grid_property(items, "is_rejected", "formatter", format_rejected);
		}
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

	function lock_execution_items(frm) {
		const grid = frm.get_field("custom_execution_items")?.grid;
		if (!grid) return;

		const state = frm.doc.workflow_state || STATE_OPEN;
		const is_submittal = !!frm.doc.custom_is_material_submittal;
		const is_open = is_submittal ? SUBMITTAL_PREPARING_STATES.includes(state) : state === STATE_OPEN;
		const with_technical_office = is_submittal ? is_open : TECHNICAL_OFFICE_STATES.includes(state);

		set_grid_property(grid, "manufacturer", "read_only", is_open ? 0 : 1);
		set_grid_property(grid, "site_engineer_section", "label", is_submittal ? __("بيانات المادة") : __("مهندس الموقع"));

		SITE_ENGINEER_FIELDS.forEach((fieldname) =>
			set_grid_property(grid, fieldname, "read_only", is_open ? 0 : 1)
		);
		TECHNICAL_OFFICE_FIELDS.forEach((fieldname) =>
			set_grid_property(grid, fieldname, "read_only", with_technical_office ? 0 : 1)
		);
		frm.set_df_property("custom_execution_items", "cannot_add_rows", is_open ? 0 : 1);
		frm.set_df_property("custom_execution_items", "cannot_delete_rows", is_open ? 0 : 1);
	}

	function show_rejected_items(frm) {
		const rejected = (frm.doc.custom_execution_items || []).filter((row) => row.is_rejected);
		const overdue =
			frm.doc.custom_is_material_submittal &&
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
		} else if (REWORK_STATES.includes(frm.doc.workflow_state) && rejected.length) {
			frm.set_intro(
				__("البنود المرفوضة: {0}. ملاحظات مهندس الموقع موجودة في كل بند.", [
					rejected.map((row) => row.idx).join("، "),
				]),
				"orange"
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

	// Clearing an attachment deletes its file. On execution items the old file is part of
	// the document history, so only the field is emptied and the file stays on the task.
	function keep_replaced_attachments() {
		const proto = frappe.ui.form.ControlAttach.prototype;
		if (proto.__keeps_execution_history) return;

		const clear_attachment = proto.clear_attachment;
		proto.clear_attachment = function () {
			if (this.df?.parent !== "Task Execution Item" || !this.frm) {
				return clear_attachment.call(this);
			}
			frappe.confirm(__("إزالة المرفق من البند؟ سيبقى الملف محفوظاً في سجل المستندات."), async () => {
				await this.parse_validate_and_set_in_model(null);
				this.refresh();
				this.frm.save();
			});
		};
		proto.__keeps_execution_history = true;
	}
})();
