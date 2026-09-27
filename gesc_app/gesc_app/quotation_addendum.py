"""Quotation addenda and the family numbering of quotations.

Every main quotation opens a family, and its addenda and amendments are numbered inside it:

    SAL-QTN-000009-2026-001       the main quotation
    SAL-QTN-000009-2026-001-01    its first amendment (-02, -03 ...)
    SAL-QTN-000009-2026-002       the first addendum
    SAL-QTN-000009-2026-002-01    the addendum's first amendment

The family number never resets and the year is the main quotation's, so an addendum made
in a later year stays in its family. Numbers are not reused, even for a deleted draft. A
quotation numbered before this scheme (SAL-QTN-2026-00006) keeps its name and its
amendments keep Frappe's -1, -2; its addenda are SAL-QTN-2026-00006-002, -003 ...

An addendum is made from a main quotation that has become a contract (Ordered), for the
same customer. The sales order made from it becomes an addendum to that contract.
"""

import re

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.naming import getseries
from frappe.utils import cint, get_link_to_form, getdate, nowdate

MODULE = "Gesc App"
PREFIX = "SAL-QTN-"
FAMILY_DIGITS = 6
INDEX_DIGITS = 3
AMENDMENT_DIGITS = 2
ORDERED = ("Ordered", "Partially Ordered")

# A name in a family: its base ends with the three-digit number in the family, and an
# amendment adds a two-digit counter.
FAMILY_NAME = re.compile(r"^(?P<base>.+-\d{3})(?:-(?P<amendment>\d{2}))?$")


# Naming -------------------------------------------------------------------------------


def autoname(doc, method=None):
	if doc.amended_from:
		doc.name = _amended_name(doc.amended_from)
	elif doc.get("custom_addendum_to"):
		family = _family(doc.custom_addendum_to)
		doc.name = f"{family}-{_next_in_family(family)}"
	else:
		year = getdate(doc.transaction_date or nowdate()).year
		family = f"{PREFIX}{getseries(PREFIX, FAMILY_DIGITS)}-{year}"
		doc.name = f"{family}-{_next_in_family(family, is_main=True)}"


def _family(main):
	match = FAMILY_NAME.match(main)
	if match:
		return match["base"].rsplit("-", 1)[0]
	# Numbered before the families: the family is its first version.
	while previous := frappe.db.get_value("Quotation", main, "amended_from"):
		main = previous
	return main


def _next_in_family(family, is_main=False):
	key = f"{family}-"
	if not is_main and not frappe.db.sql("select 1 from `tabSeries` where name = %s", key):
		# A family numbered before this scheme: its main quotation counts as 001.
		frappe.db.sql("insert into `tabSeries` (name, current) values (%s, 1)", key)
	return getseries(key, INDEX_DIGITS)


def _amended_name(source):
	match = FAMILY_NAME.match(source)
	if match:
		base, number, digits = match["base"], cint(match["amendment"]) + 1, AMENDMENT_DIGITS
	elif frappe.db.get_value("Quotation", source, "amended_from"):
		# Numbered before the families: Frappe's own counter (-1, -2 ...).
		base, _sep, last = source.rpartition("-")
		number, digits = cint(last) + 1, 1
	else:
		base, number, digits = source, 1, 1

	name = f"{base}-{number:0{digits}d}"
	while frappe.db.exists("Quotation", name):
		number += 1
		name = f"{base}-{number:0{digits}d}"
	return name


# Quotation hooks ----------------------------------------------------------------------


def validate(doc, method=None):
	if doc.is_new() and doc.amended_from:
		# An amendment stays an addendum of the same main quotation.
		doc.custom_addendum_to = frappe.db.get_value("Quotation", doc.amended_from, "custom_addendum_to")
	elif not doc.is_new() and doc.has_value_changed("custom_addendum_to"):
		frappe.throw(_("لا يتغير عرض السعر الأساسي للملحق بعد إنشائه."))

	doc.custom_is_addendum = 1 if doc.custom_addendum_to else 0
	if not doc.custom_addendum_to or doc.docstatus != 0:
		return

	main = _get_main(doc.custom_addendum_to)
	if doc.is_new() and not doc.amended_from:
		_check_main(main)
	customer = _main_customer(main)
	if customer and (doc.quotation_to != "Customer" or doc.party_name != customer):
		frappe.throw(
			_("الملحق يكون لنفس عميل عرض السعر الأساسي {0}: {1}.").format(frappe.bold(main.name), frappe.bold(customer))
		)


def on_submit(doc, method=None):
	"""A main quotation amended after its addenda were made keeps them: they point at this
	version from now on."""
	if doc.amended_from and not doc.custom_addendum_to:
		frappe.db.set_value(
			"Quotation", {"custom_addendum_to": doc.amended_from}, "custom_addendum_to", doc.name, update_modified=False
		)


@frappe.whitelist()
def make_addendum(source_name, target_doc=None):
	from frappe.model.mapper import get_mapped_doc

	main = _get_main(source_name)
	_check_main(main)
	customer = _main_customer(main)

	def set_missing_values(source, target):
		target.custom_addendum_to = source.name
		target.custom_is_addendum = 1
		target.transaction_date = nowdate()
		if customer:
			target.quotation_to = "Customer"
			target.party_name = customer
		for tax in source.get("taxes"):
			target.append("taxes", tax.as_dict(no_default_fields=True))
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	# Of the tables only the taxes are carried over: the items start empty, since the
	# addendum holds only the additional work, and it gets its own attachments and team.
	return get_mapped_doc(
		"Quotation",
		source_name,
		{
			"Quotation": {
				"doctype": "Quotation",
				"field_no_map": [
					"status",
					"transaction_date",
					"valid_till",
					"opportunity",
					"supplier_quotation",
					"order_lost_reason",
				],
			},
		},
		target_doc,
		set_missing_values,
		ignore_child_tables=True,
	)


def _get_main(name):
	main = frappe.db.get_value(
		"Quotation",
		name,
		["name", "docstatus", "status", "quotation_to", "party_name", "custom_addendum_to"],
		as_dict=True,
	)
	if not main:
		frappe.throw(_("عرض السعر {0} غير موجود.").format(name))
	return main


def _check_main(main):
	if main.custom_addendum_to:
		frappe.throw(
			_("{0} ملحق، والملحق يُعمل من عرض السعر الأساسي {1}.").format(
				frappe.bold(main.name), get_link_to_form("Quotation", main.custom_addendum_to)
			)
		)
	if main.docstatus != 1 or main.status not in ORDERED:
		frappe.throw(
			_("يُعمل الملحق بعد تحويل عرض السعر الأساسي {0} لأمر بيع. حالته الآن: {1}.").format(
				frappe.bold(main.name), _(main.status)
			)
		)


def _main_customer(main):
	if main.quotation_to == "Customer":
		return main.party_name
	# A quotation to a lead: ERPNext made the customer from the lead when it was ordered.
	return frappe.db.get_value("Customer", {"lead_name": main.party_name})


# Sales Order hook ---------------------------------------------------------------------


def link_sales_order(doc, method=None):
	"""A sales order made from an addendum quotation is an addendum to the contract made from
	its main quotation, on the contract's project."""
	if doc.get("custom_addendum_to") or doc.get("amended_from"):
		return
	quotations = {row.prevdoc_docname for row in doc.items if row.get("prevdoc_docname")}
	if not quotations:
		return
	addenda = frappe.get_all(
		"Quotation",
		filters={"name": ["in", list(quotations)], "custom_addendum_to": ["is", "set"]},
		fields=["name", "custom_addendum_to"],
	)
	if not addenda:
		return
	if len(quotations) > 1:
		frappe.throw(_("أمر البيع لملحق عرض سعر يُعمل من ملحق واحد فقط: {0}.").format(addenda[0].name))

	main = addenda[0].custom_addendum_to
	contracts = frappe.db.sql(
		"""
		select distinct so.name, so.project, so.custom_is_main_contract, so.creation
		from `tabSales Order` so
		inner join `tabSales Order Item` soi on soi.parent = so.name
		where soi.prevdoc_docname = %s and so.docstatus = 1 and ifnull(so.custom_addendum_to, '') = ''
		order by so.custom_is_main_contract desc, so.creation asc
		""",
		main,
		as_dict=True,
	)
	if not contracts:
		frappe.throw(
			_("عرض السعر الأساسي {0} ليس له أمر بيع معتمد، فلا يُربط أمر بيع الملحق {1} بعقد.").format(
				get_link_to_form("Quotation", main), frappe.bold(addenda[0].name)
			)
		)

	contract = contracts[0]
	if not contract.custom_is_main_contract:
		# The order made from the main quotation is the contract its addenda belong to.
		frappe.db.set_value("Sales Order", contract.name, "custom_is_main_contract", 1, update_modified=False)
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "Sales Order",
				"reference_name": contract.name,
				"content": _("عُلّم «عقد أساسي» تلقائياً عند عمل أمر بيع لملحق عرض السعر {0}.").format(addenda[0].name),
			}
		).insert(ignore_permissions=True)

	doc.custom_is_addendum = 1
	doc.custom_addendum_to = contract.name
	if not doc.project and contract.project:
		doc.project = contract.project


# Setup --------------------------------------------------------------------------------


def setup_quotation_addendum():
	create_custom_fields(
		{
			"Quotation": [
				{
					"fieldname": "custom_is_addendum",
					"label": "ملحق عرض سعر",
					"fieldtype": "Check",
					"insert_after": "custom_approval_status",
					"depends_on": "eval:doc.custom_is_addendum",
					"read_only": 1,
					"no_copy": 1,
					"in_standard_filter": 1,
					"module": MODULE,
				},
				{
					"fieldname": "custom_addendum_to",
					"label": "ملحق لعرض السعر",
					"fieldtype": "Link",
					"options": "Quotation",
					"insert_after": "custom_is_addendum",
					"depends_on": "eval:doc.custom_addendum_to",
					"read_only": 1,
					"no_copy": 1,
					"search_index": 1,
					"module": MODULE,
				},
			]
		},
		update=True,
	)

	# Amendments are named here (-01, -02) instead of by Frappe's counter (-1, -2). Left
	# alone once the rule for Quotation exists, so a change in Document Naming Settings holds.
	if not frappe.db.exists("Amended Document Naming Settings", {"document_type": "Quotation"}):
		frappe.get_doc(
			{
				"doctype": "Amended Document Naming Settings",
				"parenttype": "Document Naming Settings",
				"parent": "Document Naming Settings",
				"parentfield": "amend_naming_override",
				"document_type": "Quotation",
				"action": "Default Naming",
			}
		).insert(ignore_permissions=True)

	# The family numbers continue after the quotations numbered before them.
	if not frappe.db.sql("select 1 from `tabSeries` where name = %s", PREFIX):
		last = frappe.db.sql("select max(current) from `tabSeries` where name like 'SAL-QTN-____-'")[0][0]
		frappe.db.sql("insert into `tabSeries` (name, current) values (%s, %s)", (PREFIX, cint(last)))
