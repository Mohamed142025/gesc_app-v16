// Quotation proposals (gesc_app.gesc_app.quotation_options): every proposal has its own table
// and total. Without fixed items the items table is hidden (the server fills it from proposal
// 1); with them it holds the fixed items. The Sales Order is made for the proposal the
// customer chose.
const GESC_MAX_OPTIONS = 5;

frappe.ui.form.on("Quotation", {
	setup(frm) {
		// A saved description of the row's own item (item_description.js fills the text).
		for (let n = 1; n <= GESC_MAX_OPTIONS; n++) {
			frm.set_query("custom_item_description", `custom_option_${n}_items`, (doc, cdt, cdn) => ({
				filters: { item_code: locals[cdt][cdn].item_code || "__no_item_selected__" },
			}));
		}
		// "يُطبع مع الصنف": one of the quotation's other items.
		const print_with_query = (doc, cdt, cdn) => {
			const tables = ["items", ...[1, 2, 3, 4, 5].map((n) => `custom_option_${n}_items`)];
			const own = locals[cdt][cdn].item_code;
			const codes = tables.flatMap((field) => (doc[field] || []).map((row) => row.item_code));
			return { filters: { name: ["in", [...new Set(codes.filter((c) => c && c !== own))]] } };
		};
		["items", ...[1, 2, 3, 4, 5].map((n) => `custom_option_${n}_items`)].forEach((field) =>
			frm.set_query("custom_print_with_item", field, print_with_query)
		);
	},

	onload(frm) {
		gesc_guard_option_rows(frm);
		// ERPNext's "Create > Sales Order" asks for the proposal first.
		if (frm.cscript && !frm.cscript.__gesc_options_patched) {
			const original = frm.cscript.make_sales_order;
			frm.cscript.make_sales_order = function () {
				if (!this.frm.doc.custom_has_options) return original.apply(this, arguments);
				gesc_choose_option(this.frm);
			};
			frm.cscript.__gesc_options_patched = true;
		}
	},

	refresh(frm) {
		gesc_items_label(frm);
		gesc_move_items_to_option_one(frm);
		if (frm.doc.docstatus === 0 && frm.doc.custom_has_options && !frm.doc.custom_options_common_items) {
			frm.add_custom_button(__("نسخ أصناف المقترح 1 إلى مقترح"), () => gesc_copy_option_one(frm), __("المقترحات"));
		}
	},

	custom_has_options(frm) {
		if (frm.doc.custom_has_options && !frm.doc.custom_options_count) {
			frm.set_value("custom_options_count", 2);
		}
		gesc_move_items_to_option_one(frm);
		gesc_items_label(frm);
		gesc_option_totals(frm);
	},

	custom_options_common_items(frm) {
		if (!frm.doc.custom_has_options) return;
		if (frm.doc.custom_options_common_items) {
			// The items table was proposal 1's copy: it now holds the fixed items.
			frm.clear_table("items");
			frm.refresh_field("items");
			frappe.show_alert({ message: __("اكتب الأصناف الثابتة لكل المقترحات في جدول الأصناف الأساسية."), indicator: "blue" });
		} else if ((frm.doc.items || []).length) {
			frappe.confirm(
				__("الأصناف الأساسية هتتشال، وكل مقترح يفضل بأصنافه بس. تكمل؟"),
				() => {
					frm.clear_table("items");
					frm.refresh_field("items");
					gesc_items_label(frm);
					gesc_option_totals(frm);
				},
				() => frm.set_value("custom_options_common_items", 1)
			);
		}
		gesc_items_label(frm);
		gesc_option_totals(frm);
	},

	custom_options_count(frm) {
		const count = cint(frm.doc.custom_options_count);
		if (frm.doc.custom_has_options && (count < 2 || count > GESC_MAX_OPTIONS)) {
			frappe.msgprint(__("عدد المقترحات من 2 إلى {0}.", [GESC_MAX_OPTIONS]));
		}
		gesc_option_totals(frm);
	},

	validate: gesc_option_totals,
});

// Proposal 1 is the items table: its total follows ERPNext's own recalculation.
const gesc_option_one_changed = (frm) => setTimeout(() => gesc_option_totals(frm), 300);
frappe.ui.form.on("Quotation Item", {
	qty: gesc_option_one_changed,
	rate: gesc_option_one_changed,
	item_code: gesc_option_one_changed,
	items_remove: gesc_option_one_changed,
});

frappe.ui.form.on("Quotation Option Item", {
	async item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) return;
		const { message: item } = await frappe.call({
			method: "gesc_app.gesc_app.quotation_options.get_item_details",
			args: { item_code: row.item_code, price_list: frm.doc.selling_price_list },
		});
		if (!item) return;
		await frappe.model.set_value(cdt, cdn, {
			item_name: item.item_name,
			description: item.description,
			uom: item.uom,
			item_group: item.item_group,
		});
		if (!flt(row.rate) && item.rate) await frappe.model.set_value(cdt, cdn, "rate", item.rate);
		gesc_option_amount(frm, cdt, cdn);
	},
	qty: gesc_option_amount,
	rate: gesc_option_amount,
	custom_option_1_items_remove: gesc_option_totals,
	custom_option_2_items_remove: gesc_option_totals,
	custom_option_3_items_remove: gesc_option_totals,
	custom_option_4_items_remove: gesc_option_totals,
	custom_option_5_items_remove: gesc_option_totals,
});

function gesc_option_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
	gesc_option_totals(frm);
}

function gesc_option_totals(frm) {
	if (!frm.doc.custom_has_options) return;
	const sum = (rows) => (rows || []).reduce((total, row) => total + flt(row.amount), 0);
	const common = !!frm.doc.custom_options_common_items;
	const items_total = sum(frm.doc.items);
	// With fixed items, every proposal is those items plus its own; otherwise proposal 1 is
	// the items table and the others their own tables.
	const values = { custom_common_items_total: common ? items_total : 0 };
	for (let n = 1; n <= GESC_MAX_OPTIONS; n++) {
		let value = 0;
		if (n <= cint(frm.doc.custom_options_count)) {
			if (common) value = items_total + sum(frm.doc[`custom_option_${n}_items`]);
			else value = sum(frm.doc[`custom_option_${n}_items`]);
		}
		values[`custom_option_${n}_total`] = value;
	}
	Object.entries(values).forEach(([field, value]) => {
		if (flt(frm.doc[field]) !== value) frm.set_value(field, value);
	});
}

function gesc_option_label(frm, n) {
	const title = frm.doc[`custom_option_${n}_title`];
	const total = format_currency(frm.doc[`custom_option_${n}_total`], frm.doc.currency);
	return `${__("المقترح {0}", [n])}${title ? " — " + title : ""} (${total})`;
}

function gesc_choose_option(frm) {
	const count = cint(frm.doc.custom_options_count);
	const options = [];
	for (let n = 1; n <= count; n++) options.push({ value: String(n), label: gesc_option_label(frm, n) });
	const d = new frappe.ui.Dialog({
		title: __("أمر البيع لأي مقترح؟"),
		fields: [
			{
				fieldname: "option",
				label: __("المقترح الذي وافق عليه العميل"),
				fieldtype: "Select",
				options,
				default: "1",
				reqd: 1,
			},
		],
		primary_action_label: __("إنشاء أمر البيع"),
		primary_action({ option }) {
			d.hide();
			frappe.model.open_mapped_doc({
				method: "erpnext.selling.doctype.quotation.quotation.make_sales_order",
				frm,
				args: { gesc_option: cint(option) },
			});
		},
	});
	d.show();
}

function gesc_copy_option_one(frm) {
	const count = cint(frm.doc.custom_options_count);
	const options = [];
	for (let n = 2; n <= count; n++) options.push({ value: String(n), label: __("المقترح {0}", [n]) });
	const d = new frappe.ui.Dialog({
		title: __("نسخ أصناف المقترح 1"),
		fields: [
			{ fieldname: "option", label: __("إلى"), fieldtype: "Select", options, default: "2", reqd: 1 },
			{
				fieldname: "replace",
				label: __("استبدال أصناف المقترح الحالية"),
				fieldtype: "Check",
				default: 0,
			},
		],
		primary_action_label: __("نسخ"),
		primary_action({ option, replace }) {
			const field = `custom_option_${option}_items`;
			if (replace) frm.clear_table(field);
			(frm.doc.custom_option_1_items || []).forEach((item) => {
				const row = frm.add_child(field);
				[
					"item_code",
					"item_name",
					"custom_item_description",
					"custom_attachment",
					"custom_alternative_item_name",
					"custom_group_in_print",
					"uom",
					"qty",
					"rate",
					"amount",
					"description",
					"custom_item_notes",
					"item_group",
				].forEach((key) => (row[key] = item[key]));
				row.custom_row_key = frappe.utils.get_random(12);
			});
			frm.refresh_field(field);
			gesc_option_totals(frm);
			frm.dirty();
			d.hide();
		},
	});
	d.show();
}

// With fixed items the items table holds what every proposal has; with each proposal whole
// it is hidden behind proposal 1's own table.
function gesc_items_label(frm) {
	const options = !!frm.doc.custom_has_options;
	const common = options && !!frm.doc.custom_options_common_items;
	frm.set_df_property("items", "label", common ? __("الأصناف الأساسية (ثابتة لكل المقترحات)") : __("Items"));
	frm.set_df_property("items", "hidden", options && !common ? 1 : 0);
	frm.set_df_property(
		"custom_option_1_items",
		"label",
		common ? __("أصناف المقترح 1 (الزيادة على الأساسية)") : __("أصناف المقترح 1")
	);
}

// Each proposal whole and proposal 1 still in the items table (a quotation from before, or
// proposals just ticked): its items move to proposal 1's own table.
const GESC_MOVED_FIELDS = [
	"item_code", "item_name", "description", "custom_item_description", "uom", "qty", "rate", "amount",
	"custom_alternative_item_name", "custom_group_in_print", "custom_item_notes", "custom_attachment",
	"custom_row_key", "custom_print_with_item", "item_group",
];
function gesc_move_items_to_option_one(frm) {
	const d = frm.doc;
	if (d.docstatus !== 0 || !d.custom_has_options || d.custom_options_common_items) return;
	if ((d.custom_option_1_items || []).length || !(d.items || []).filter((r) => r.item_code).length) return;
	d.items.filter((r) => r.item_code).forEach((item) => {
		const row = frm.add_child("custom_option_1_items");
		GESC_MOVED_FIELDS.forEach((key) => (row[key] = item[key]));
		if (!row.custom_row_key) row.custom_row_key = frappe.utils.get_random(12);
	});
	frm.refresh_field("custom_option_1_items");
	gesc_option_totals(frm);
	frm.dirty();
}

// Frappe calls the form controller's handlers (ERPNext's item_code, qty, rate, uom...) for a
// field of that name in any table. Those are for the items table: on a proposal's row they
// fetch prices into it and ask the server for an items row that is not there. A proposal's
// rows have their own handlers above, so ERPNext's skip them.
function gesc_guard_option_rows(frm) {
	const cscript = frm.cscript;
	if (!cscript || cscript.__gesc_option_rows_guarded) return;
	const fields = frappe.get_meta("Quotation Option Item")?.fields.map((df) => df.fieldname) || [
		"item_code", "item_name", "uom", "qty", "rate", "amount", "description", "item_group",
	];
	fields.forEach((fieldname) => {
		const original = cscript[fieldname];
		if (typeof original !== "function") return;
		cscript[fieldname] = function (doc, cdt) {
			if (cdt === "Quotation Option Item") return;
			return original.apply(this, arguments);
		};
	});
	cscript.__gesc_option_rows_guarded = true;
}
