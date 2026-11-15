"""Quotations with proposals (مقترحات): Opt.1, Opt.2, ...

Ticking "له مقترحات" asks how many (2 to MAX_OPTIONS). Two ways to lay them out:

- Each proposal whole: proposal 1 is the quotation's own items table, so the quotation's
  totals, its advance and its approval are those of proposal 1; every other proposal has its
  own items table (Quotation Option Item).
- Fixed items (custom_options_common_items): the quotation's items table holds the items every
  proposal has, written once, and each proposal, 1 included, has a table of the items it adds.
  A proposal's total is the fixed items plus its own; the quotation's totals are the fixed
  items'.

The proposals' items have the same printed name, grouping and notes as the quotation's items.
Totals are the sum of the items (no discount or tax).

The Sales Order is made for the proposal the customer chose: as ERPNext maps the quotation,
then with that proposal's items (in place of the quotation's when each proposal is whole,
after the fixed items otherwise).

Printed by the "عرض سعر - بالمقترحات (مجمّع)" print format.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt

MODULE = "Gesc App"
MAX_OPTIONS = 5
HAS_OPTIONS = "custom_has_options"
COUNT = "custom_options_count"
COMMON = "custom_options_common_items"
COMMON_TITLE = "custom_common_items_title"
COMMON_TOTAL = "custom_common_items_total"
BY_ITEM = "custom_options_by_item"
# A row printed as if it were another item (rows_by_item).
PRINT_WITH = "custom_print_with_item"


def table(n):
	return f"custom_option_{n}_items"


def title(n):
	return f"custom_option_{n}_title"


def total(n):
	return f"custom_option_{n}_total"


def _shown(n):
	if n == 1:
		return f"eval:doc.{HAS_OPTIONS}"
	return f"eval:doc.{HAS_OPTIONS} && cint(doc.{COUNT}) >= {n}"


def own_table(doc, n):
	"""Whether proposal n has its own table (always but proposal 1 of a whole-proposal quotation)."""
	return n > 1 or bool(doc.get(COMMON))


def setup():
	fields = [
		{
			"fieldname": HAS_OPTIONS,
			"label": "له مقترحات",
			"fieldtype": "Check",
			"insert_after": "items_section",
			"description": "عرض السعر فيه أكثر من مقترح (Opt.1، Opt.2...). جدول الأصناف هو المقترح 1، ولكل مقترح بعده جدول.",
			"module": MODULE,
		},
		{
			"fieldname": COUNT,
			"label": "عدد المقترحات",
			"fieldtype": "Int",
			"insert_after": HAS_OPTIONS,
			"default": "2",
			"depends_on": f"eval:doc.{HAS_OPTIONS}",
			"mandatory_depends_on": f"eval:doc.{HAS_OPTIONS}",
			"description": f"من 2 إلى {MAX_OPTIONS}.",
			"module": MODULE,
		},
		{
			"fieldname": COMMON,
			"label": "أصناف أساسية ثابتة لكل المقترحات",
			"fieldtype": "Check",
			"insert_after": COUNT,
			"depends_on": f"eval:doc.{HAS_OPTIONS}",
			"description": "جدول الأصناف التالي يبقى للأصناف الثابتة في كل المقترحات، وكل مقترح يضيف أصنافه الزيادة بس في جدوله. إجمالي المقترح = الأساسية + أصنافه.",
			"module": MODULE,
		},
		{
			"fieldname": COMMON_TITLE,
			"label": "عنوان الأصناف الأساسية",
			"fieldtype": "Data",
			"insert_after": COMMON,
			"depends_on": f"eval:doc.{HAS_OPTIONS} && doc.{COMMON}",
			"description": "يُطبع فوق الأصناف الأساسية. لو فاضي ما يُطبعش عنوان.",
			"module": MODULE,
		},
		{
			"fieldname": BY_ITEM,
			"label": "طباعة المقترحات تحت كل بند",
			"fieldtype": "Check",
			"insert_after": COMMON_TITLE,
			"depends_on": f"eval:doc.{HAS_OPTIONS}",
			"description": "في الطباعة: كل بند وتحته المقترح 1 والمقترح 2 والمقترح 3 له، ثم البند التالي. البند هو نفس الصنف في المقترحات (الأول مع الأول لو الصنف متكرر).",
			"module": MODULE,
		},
		{
			"fieldname": "custom_options_section",
			"label": "المقترحات",
			"fieldtype": "Section Break",
			"insert_after": "items",
			"depends_on": f"eval:doc.{HAS_OPTIONS}",
			"module": MODULE,
		},
		{
			"fieldname": COMMON_TOTAL,
			"label": "إجمالي الأصناف الأساسية",
			"fieldtype": "Currency",
			"options": "currency",
			"insert_after": "custom_options_section",
			"read_only": 1,
			"depends_on": f"eval:doc.{HAS_OPTIONS} && doc.{COMMON}",
			"module": MODULE,
		},
	]
	after = COMMON_TOTAL
	for n in range(1, MAX_OPTIONS + 1):
		fields += [
			{
				"fieldname": f"custom_option_{n}_section",
				"label": f"المقترح {n}",
				"fieldtype": "Section Break",
				"insert_after": after,
				"depends_on": _shown(n),
				"module": MODULE,
			},
			{
				"fieldname": title(n),
				"label": f"عنوان المقترح {n}",
				"fieldtype": "Data",
				"insert_after": f"custom_option_{n}_section",
				"depends_on": _shown(n),
				"description": (
					"يُطبع فوق بنود المقترح 1، مثل: برجولة 900*400 سم. بنود المقترح 1 هي جدول الأصناف، إلا مع الأصناف الأساسية الثابتة فله جدوله التالي."
					if n == 1
					else ""
				),
				"module": MODULE,
			},
			{
				"fieldname": table(n),
				"label": f"أصناف المقترح {n}" + (" (الزيادة على الأساسية)" if n == 1 else ""),
				"fieldtype": "Table",
				"options": "Quotation Option Item",
				"insert_after": title(n),
				"depends_on": f"eval:doc.{HAS_OPTIONS} && doc.{COMMON}" if n == 1 else _shown(n),
				"module": MODULE,
			},
			{
				"fieldname": total(n),
				"label": f"إجمالي المقترح {n}",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": table(n),
				"read_only": 1,
				"depends_on": _shown(n),
				"module": MODULE,
			},
		]
		after = total(n)
	create_custom_fields(
		{
			"Quotation": fields,
			"Quotation Item": [
				{
					"fieldname": PRINT_WITH,
					"label": "يُطبع مع الصنف",
					"fieldtype": "Link",
					"options": "Item",
					"insert_after": "custom_group_in_print",
					"description": "في طباعة المقترحات تحت كل بند: الصف يُطبع كأنه هذا الصنف، فيظهر تحت نفس البند ونفس الرقم.",
					"module": MODULE,
				}
			],
		},
		update=True,
	)
	frappe.clear_cache(doctype="Quotation")


def validate(doc, method=None):
	if not doc.get(HAS_OPTIONS):
		for n in range(1, MAX_OPTIONS + 1):
			doc.set(total(n), 0)
		return

	count = cint(doc.get(COUNT))
	if not 2 <= count <= MAX_OPTIONS:
		frappe.throw(_("عدد المقترحات من 2 إلى {0}.").format(MAX_OPTIONS), title=_("المقترحات"))

	_set_descriptions(doc)
	common = bool(doc.get(COMMON))
	items_total = sum(flt(row.amount) for row in doc.items)
	doc.set(COMMON_TOTAL, items_total if common else 0)
	for n in range(1, MAX_OPTIONS + 1):
		for row in doc.get(table(n)) or []:
			row.amount = flt(flt(row.qty) * flt(row.rate), row.precision("amount"))
		if n > count:
			# Kept if the count goes back up, but not part of the quotation.
			doc.set(total(n), 0)
			continue
		if not own_table(doc, n):
			doc.set(total(n), items_total)
			continue
		rows = doc.get(table(n)) or []
		# With fixed items a proposal may add nothing to them.
		if not rows and not common:
			frappe.throw(_("أضف أصناف المقترح {0}.").format(n), title=_("المقترحات"))
		doc.set(total(n), (items_total if common else 0) + sum(flt(row.amount) for row in rows))


def _set_descriptions(doc):
	"""A proposal row's saved description is of its own item, and fills its text (as the
	items table, item_description_setup)."""
	for n in range(1, MAX_OPTIONS + 1):
		for row in doc.get(table(n)) or []:
			if not row.get("custom_item_description"):
				continue
			description = frappe.db.get_value(
				"Item Description", row.custom_item_description, ["item_code", "description"], as_dict=True
			)
			if not description:
				frappe.throw(_("التوصيف المحدد غير موجود"))
			if description.item_code != row.item_code:
				frappe.throw(
					_("المقترح {0}، الصف {1}: التوصيف المحدد غير مرتبط بالصنف المختار").format(n, row.idx)
				)
			row.description = description.description


def options(doc):
	"""The quotation's proposals: [(number, title, rows, total)]."""
	if not doc.get(HAS_OPTIONS):
		return [(1, "", doc.items, doc.total)]
	return [
		(n, doc.get(title(n)) or "", (doc.get(table(n)) or []) if own_table(doc, n) else doc.items, flt(doc.get(total(n))))
		for n in range(1, cint(doc.get(COUNT)) + 1)
	]


@frappe.whitelist()
def get_item_details(item_code, price_list=None, uom=None):
	"""What a proposal's row takes from its item: name, description, unit, group and price."""
	frappe.has_permission("Item", "read", throw=True)
	item = frappe.db.get_value(
		"Item", item_code, ["item_name", "description", "stock_uom", "sales_uom", "item_group"], as_dict=True
	)
	if not item:
		return {}
	uom = uom or item.sales_uom or item.stock_uom
	rate = 0
	if price_list:
		rate = frappe.db.get_value(
			"Item Price", {"item_code": item_code, "price_list": price_list, "uom": uom}, "price_list_rate"
		) or frappe.db.get_value(
			"Item Price", {"item_code": item_code, "price_list": price_list}, "price_list_rate"
		)
	return {
		"item_name": item.item_name,
		"description": item.description,
		"uom": uom,
		"item_group": item.item_group,
		"rate": flt(rate),
	}


@frappe.whitelist()
def make_sales_order(source_name, target_doc=None, args=None):
	"""ERPNext's Sales Order from a quotation, for the proposal chosen in `args.option`."""
	from erpnext.selling.doctype.quotation.quotation import make_sales_order as erpnext_make_sales_order

	args = frappe.parse_json(args) if args else frappe._dict(frappe.flags.args or {})
	quotation = frappe.get_doc("Quotation", source_name)
	option = cint((args or {}).get("gesc_option"))
	if not quotation.get(HAS_OPTIONS):
		return erpnext_make_sales_order(source_name, target_doc, args)
	if not 1 <= option <= cint(quotation.get(COUNT)):
		frappe.throw(_("عرض السعر {0} له مقترحات: اختر المقترح الذي وافق عليه العميل.").format(source_name))

	order = erpnext_make_sales_order(source_name, target_doc, args)
	if not own_table(quotation, option):
		return order

	template = order.items[0].as_dict() if order.items else {}
	# The proposal's items replace the quotation's, or follow the fixed items.
	if not quotation.get(COMMON):
		order.set("items", [])
	for row in quotation.get(table(option)):
		stock_uom = frappe.get_cached_value("Item", row.item_code, "stock_uom")
		conversion = 1.0
		if row.uom and row.uom != stock_uom:
			conversion = flt(
				frappe.db.get_value("UOM Conversion Detail", {"parent": row.item_code, "uom": row.uom}, "conversion_factor")
			) or 1.0
		order.append(
			"items",
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"description": row.description or row.item_name,
				"qty": row.qty,
				"uom": row.uom,
				"stock_uom": stock_uom,
				"conversion_factor": conversion,
				"price_list_rate": row.rate,
				"rate": row.rate,
				"delivery_date": template.get("delivery_date"),
				"warehouse": template.get("warehouse"),
				"prevdoc_docname": source_name,
				"custom_alternative_item_name": row.get("custom_alternative_item_name"),
				"custom_item_description": row.get("custom_item_description"),
				"custom_attachment": row.get("custom_attachment"),
				"custom_item_notes": row.get("custom_item_notes"),
			},
		)
	order.run_method("set_missing_values")
	order.run_method("calculate_taxes_and_totals")
	return order


def rows_by_item(doc):
	"""For the print format, the proposals' items under each item: [{"title", "rows": [{"n",
	"option_title", "row"}]}], in the order the items first appear (proposal 1 first).

	An item is the same item code in each proposal (a row's "يُطبع مع الصنف" stands in for its
	own code), its first time in one proposal with its
	first time in the others and so on. An item ticked "تجميع في الطباعة" is one item however
	many times it is in a proposal: all its rows of proposal 1, then of proposal 2... Items
	ticked with the same printed name share one title. The fixed items (if any) are not here:
	they print on their own."""
	keys, rows = [], {}
	# Ticked in any proposal is enough.
	def code(row):
		return row.get(PRINT_WITH) or row.item_code

	grouped_items = {code(row) for _n, _t, items, _total in options(doc) for row in items if row.get("custom_group_in_print")}
	for n, option_title, items, _total in options(doc):
		seen = {}
		for row in items:
			if code(row) in grouped_items:
				key = (code(row), "grouped")
			else:
				occurrence = seen.get(code(row), 0)
				seen[code(row)] = occurrence + 1
				key = (code(row), occurrence)
			if key not in rows:
				keys.append(key)
				rows[key] = []
			rows[key].append({"n": n, "option_title": option_title, "row": row})

	blocks = []
	for number, key in enumerate(keys, 1):
		first = rows[key][0]["row"]
		title = first.get("custom_alternative_item_name") or first.item_name
		grouped = key[1] == "grouped"
		item = {"number": number, "rows": rows[key]}
		block = grouped and next((b for b in blocks if b["grouped"] and b["title"] == title), None)
		if block:
			block["items"].append(item)
		else:
			blocks.append({"title": title, "grouped": grouped, "items": [item]})
	return blocks
