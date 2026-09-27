"""Rules for creating projects, set in Projects Settings.

When the rules are on, a project needs a submitted Sales Order (not an addendum) whose
recorded advance covers the down payment agreed on the contract, and only the creator
role may create projects. The exception role may skip the contract and advance rules,
with a written reason that is kept on the project.

The down payment is agreed as a percentage or an amount on the Quotation and carried to
the Sales Order, where it has to be set (zero allowed) before the order is submitted.
"""

import frappe
from frappe import _
from frappe.utils import flt, fmt_money

ADVANCE_PERCENTAGE = "نسبة"
ADVANCE_AMOUNT = "قيمة"
ADVANCE_FIELDS = ("custom_advance_type", "custom_advance_percentage", "custom_advance_amount")
BLOCKED_ORDER_STATUSES = ("Closed", "On Hold")


def get_settings():
	return frappe._dict(
		enabled=frappe.db.get_single_value("Projects Settings", "custom_enforce_project_rules"),
		creator_role=frappe.db.get_single_value("Projects Settings", "custom_project_creator_role"),
		exception_role=frappe.db.get_single_value("Projects Settings", "custom_project_exception_role"),
	)


# Quotation and Sales Order -----------------------------------------------------------


def set_required_advance(doc, method=None):
	"""The down payment in money, from the agreed percentage or amount."""
	if doc.get("custom_advance_type") == ADVANCE_PERCENTAGE:
		percentage = flt(doc.custom_advance_percentage)
		if percentage < 0 or percentage > 100:
			frappe.throw(_("نسبة الدفعة المقدمة يجب أن تكون بين 0 و 100."))
		required = flt(doc.grand_total) * percentage / 100
	elif doc.get("custom_advance_type") == ADVANCE_AMOUNT:
		required = flt(doc.custom_advance_amount)
		if required < 0:
			frappe.throw(_("قيمة الدفعة المقدمة لا يمكن أن تكون سالبة."))
		if required > flt(doc.grand_total):
			frappe.throw(_("قيمة الدفعة المقدمة أكبر من إجمالي العقد."))
	else:
		required = 0

	doc.custom_advance_required = flt(required, doc.precision("custom_advance_required"))


def validate_sales_order_advance(doc, method=None):
	"""The down payment has to be agreed, even as zero, before the order is submitted."""
	if get_settings().enabled and not doc.get("custom_advance_type"):
		frappe.throw(
			_("حدد الدفعة المقدمة المطلوبة (نسبة أو قيمة، ولو صفر) قبل اعتماد أمر البيع."),
			title=_("الدفعة المقدمة"),
		)


def check_advance_change_after_submit(doc, method=None):
	"""Only the exception role changes the agreed down payment on a submitted order."""
	before = doc.get_doc_before_save()
	if not before or not any(doc.get(f) != before.get(f) for f in ADVANCE_FIELDS):
		return

	settings = get_settings()
	if settings.enabled and not _has_role(settings.exception_role):
		frappe.throw(_("تعديل الدفعة المقدمة بعد اعتماد أمر البيع متاح لدور الاستثناء فقط."))
	set_required_advance(doc)


# Project ------------------------------------------------------------------------------


def validate_project(doc, method=None):
	settings = get_settings()
	if not settings.enabled:
		return

	is_new = doc.is_new()
	if not is_new and not doc.has_value_changed("sales_order"):
		return

	is_exception = _has_role(settings.exception_role)
	if is_new and not is_exception and settings.creator_role and not _has_role(settings.creator_role):
		frappe.throw(
			_("إنشاء المشاريع متاح لدور {0} فقط.").format(frappe.bold(_(settings.creator_role))),
			frappe.PermissionError,
		)

	problem = get_sales_order_problem(doc.sales_order, doc.company)
	if not problem:
		_set_customer_from_order(doc)
		return

	if not is_exception:
		frappe.throw(problem, title=_("لا يمكن ربط المشروع بأمر البيع"))

	if not (doc.get("custom_project_exception_reason") or "").strip():
		frappe.throw(
			_("{0}<br><br>للمتابعة كاستثناء اكتب «سبب الاستثناء».").format(problem),
			title=_("سبب الاستثناء مطلوب"),
		)
	doc.flags.project_rule_exception = problem
	if doc.sales_order:
		_set_customer_from_order(doc)


def log_project_exception(doc, method=None):
	if doc.flags.project_rule_exception:
		doc.add_comment(
			"Comment",
			_("تم تجاوز ضوابط إنشاء المشاريع بواسطة {0}. السبب: {1}<br>المخالفة: {2}").format(
				frappe.bold(frappe.session.user),
				frappe.bold(doc.custom_project_exception_reason),
				doc.flags.project_rule_exception,
			),
		)
		doc.flags.project_rule_exception = None


def get_sales_order_problem(sales_order, company=None):
	"""Why this Sales Order cannot start a project, or None when it can."""
	if not sales_order:
		return _("اربط المشروع بأمر بيع (عقد) معتمد.")

	order = frappe.db.get_value(
		"Sales Order",
		sales_order,
		[
			"name", "docstatus", "status", "company", "custom_is_addendum", "custom_addendum_to",
			"custom_advance_type", "custom_advance_required", "advance_paid", "currency",
		],
		as_dict=True,
	)
	if not order:
		return _("أمر البيع {0} غير موجود.").format(sales_order)
	if order.docstatus != 1:
		return _("أمر البيع {0} غير معتمد.").format(frappe.bold(order.name))
	if order.status in BLOCKED_ORDER_STATUSES:
		return _("أمر البيع {0} حالته {1}.").format(frappe.bold(order.name), _(order.status))
	if order.custom_is_addendum or order.custom_addendum_to:
		if order.custom_addendum_to:
			return _("أمر البيع {0} ملحق، والملحق يتبع مشروع العقد الأساسي {1}.").format(
				frappe.bold(order.name), frappe.bold(order.custom_addendum_to)
			)
		return _("أمر البيع {0} ملحق، والملحق يتبع مشروع عقده الأساسي.").format(frappe.bold(order.name))
	if company and order.company != company:
		return _("أمر البيع {0} تابع لشركة أخرى ({1}).").format(frappe.bold(order.name), order.company)
	if not order.custom_advance_type:
		return _("لم تُحدد الدفعة المقدمة المطلوبة على أمر البيع {0}.").format(frappe.bold(order.name))

	required = flt(order.custom_advance_required)
	paid = flt(order.advance_paid)
	if paid + 0.005 < required:
		return _("الدفعة المقدمة على أمر البيع {0} غير مكتملة: المدفوع {1} من {2} مطلوبة.").format(
			frappe.bold(order.name),
			fmt_money(paid, currency=order.currency),
			fmt_money(required, currency=order.currency),
		)
	return None


@frappe.whitelist()
def get_project_controls():
	settings = get_settings()
	return {
		"enabled": bool(settings.enabled),
		"is_exception": bool(settings.enabled and _has_role(settings.exception_role)),
	}


@frappe.whitelist()
def check_sales_order_for_project(sales_order):
	"""Checked before "Create > Project" on a Sales Order."""
	frappe.get_doc("Sales Order", sales_order).check_permission("read")
	settings = get_settings()
	if not settings.enabled:
		return {"allowed": True}

	is_exception = _has_role(settings.exception_role)
	if settings.creator_role and not is_exception and not _has_role(settings.creator_role):
		return {"allowed": False, "message": _("إنشاء المشاريع متاح لدور {0} فقط.").format(frappe.bold(_(settings.creator_role)))}

	problem = get_sales_order_problem(sales_order)
	if problem and not is_exception:
		return {"allowed": False, "message": problem}
	return {"allowed": True, "exception": problem}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def sales_order_query(doctype, txt, searchfield, start, page_len, filters):
	"""Sales Orders a project can be linked to: submitted contracts that are not
	addenda, and, unless the user holds the exception role, whose advance is covered."""
	settings = get_settings()
	conditions = ""
	if settings.enabled and not _has_role(settings.exception_role):
		conditions = "and so.custom_advance_type is not null and so.custom_advance_type != '' and so.advance_paid + 0.005 >= so.custom_advance_required"

	company = (filters or {}).get("company")
	return frappe.db.sql(
		f"""
		select so.name, so.customer, so.custom_project_name
		from `tabSales Order` so
		where so.docstatus = 1
			and so.status not in %(blocked)s
			and ifnull(so.custom_is_addendum, 0) = 0
			and ifnull(so.custom_addendum_to, '') = ''
			and (%(company)s is null or so.company = %(company)s)
			and (so.name like %(txt)s or so.customer like %(txt)s or so.custom_project_name like %(txt)s)
			{conditions}
		order by so.transaction_date desc
		limit %(page_len)s offset %(start)s
		""",
		{
			"blocked": BLOCKED_ORDER_STATUSES,
			"company": company,
			"txt": f"%{txt}%",
			"page_len": page_len,
			"start": start,
		},
	)


def _set_customer_from_order(doc):
	customer = frappe.db.get_value("Sales Order", doc.sales_order, "customer")
	if not doc.customer:
		doc.customer = customer
	elif customer and doc.customer != customer:
		frappe.throw(
			_("عميل المشروع ({0}) مختلف عن عميل أمر البيع ({1}).").format(doc.customer, customer)
		)


def _has_role(role):
	return bool(role) and role in frappe.get_roles()
