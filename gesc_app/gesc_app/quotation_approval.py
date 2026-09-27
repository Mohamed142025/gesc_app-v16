"""Approval of quotations before they reach the customer, set in Selling Settings.

When it is on, a quotation is submitted only once the approver role has approved it.
The approval holds a fingerprint of the commercial content (party, items, prices,
discounts, taxes, totals, down payment, payment terms, terms and validity); changing any
of it drops the approval. Printing, PDF and email of an unapproved draft can be blocked
for everyone but the approvers. The creator (and whoever asked for approval) is notified
of the decision; a rejection also comes as a ToDo with the reason.
"""

import hashlib

import frappe
from frappe import _
from frappe.utils import flt, get_fullname, now_datetime

STATUS_DRAFT = "مسودة"
STATUS_PENDING = "بانتظار الاعتماد"
STATUS_APPROVED = "معتمد"
STATUS_REJECTED = "مرفوض"

TODO_REQUEST = "طلب اعتماد"
TODO_REWORK = "تعديل مطلوب"

APPROVAL_FIELDS = (
	"custom_approval_status",
	"custom_approval_requested_by",
	"custom_approval_requested_on",
	"custom_approved_by",
	"custom_approved_on",
	"custom_rejected_by",
	"custom_rejected_on",
	"custom_rejection_reason",
	"custom_approval_fingerprint",
)


def get_settings():
	get = lambda field: frappe.db.get_single_value("Selling Settings", field)  # noqa: E731
	return frappe._dict(
		enabled=bool(get("custom_quotation_approval_enabled")),
		approver_role=get("custom_quotation_approver_role"),
		block_print=bool(get("custom_quotation_block_unapproved_print")),
	)


def is_approver(settings=None):
	settings = settings or get_settings()
	return bool(settings.approver_role) and settings.approver_role in frappe.get_roles()


# Hooks --------------------------------------------------------------------------------


def validate_settings(doc, method=None):
	"""Turned on without an approver role, no quotation could ever be submitted."""
	if doc.get("custom_quotation_approval_enabled") and not doc.get("custom_quotation_approver_role"):
		frappe.throw(_("حدد الدور المعتمِد لعروض الأسعار قبل تفعيل دورة الاعتماد."))


def validate(doc, method=None):
	settings = get_settings()
	if not settings.enabled or doc.docstatus != 0:
		return

	before = doc.get_doc_before_save()
	if doc.flags.quotation_approval_action:
		# Taken after ERPNext has recalculated the totals in this same save.
		if doc.custom_approval_status in (STATUS_PENDING, STATUS_APPROVED):
			doc.custom_approval_fingerprint = fingerprint(doc)
		return

	# The approval fields are written by the approval actions only.
	for fieldname in APPROVAL_FIELDS:
		doc.set(fieldname, before.get(fieldname) if before else None)

	if not doc.custom_approval_status:
		doc.custom_approval_status = STATUS_DRAFT

	if doc.custom_approval_status in (STATUS_PENDING, STATUS_APPROVED) and doc.custom_approval_fingerprint != fingerprint(doc):
		was = doc.custom_approval_status
		doc.custom_approval_status = STATUS_DRAFT
		doc.custom_approved_by = doc.custom_approved_on = None
		doc.custom_approval_fingerprint = None
		doc.flags.quotation_approval_dropped = was
		frappe.msgprint(
			_("تغيّر محتوى عرض السعر بعد {0}، فرجع «{1}» ويحتاج طلب اعتماد جديد.").format(
				_("اعتماده") if was == STATUS_APPROVED else _("طلب اعتماده"), STATUS_DRAFT
			),
			indicator="orange",
			alert=True,
		)


def on_update(doc, method=None):
	if doc.flags.quotation_approval_dropped:
		doc.flags.quotation_approval_dropped = None
		_close_todos(doc, TODO_REQUEST)


def before_submit(doc, method=None):
	settings = get_settings()
	if not settings.enabled:
		return
	if doc.custom_approval_status != STATUS_APPROVED or doc.custom_approval_fingerprint != fingerprint(doc):
		frappe.throw(
			_("عرض السعر يحتاج اعتماد ({0}) قبل الـ Submit والإرسال للعميل. الحالة الحالية: {1}.").format(
				_(settings.approver_role or ""), doc.custom_approval_status or STATUS_DRAFT
			),
			title=_("عرض السعر غير معتمد"),
		)


def before_print(doc, method=None, print_settings=None):
	_check_can_send(doc)


def check_email(communication, method=None):
	"""An email about an unapproved draft quotation is not sent."""
	if communication.reference_doctype != "Quotation" or communication.sent_or_received != "Sent":
		return
	if not communication.reference_name or communication.communication_medium != "Email":
		return
	_check_can_send(frappe.get_doc("Quotation", communication.reference_name))


def _check_can_send(doc):
	settings = get_settings()
	if not (settings.enabled and settings.block_print) or doc.docstatus != 0:
		return
	if doc.get("custom_approval_status") == STATUS_APPROVED or is_approver(settings):
		return
	frappe.throw(
		_("عرض السعر {0} غير معتمد بعد، فلا يمكن طباعته أو تنزيله أو إرساله للعميل.").format(frappe.bold(doc.name)),
		title=_("عرض السعر غير معتمد"),
	)


# Actions ------------------------------------------------------------------------------


@frappe.whitelist()
def get_approval_settings():
	settings = get_settings()
	return {
		"enabled": settings.enabled,
		"approver_role": settings.approver_role,
		"is_approver": is_approver(settings),
		"block_print": settings.block_print,
	}


@frappe.whitelist()
def request_approval(quotation):
	doc = _get_draft(quotation)
	doc.check_permission("write")
	if doc.custom_approval_status in (STATUS_PENDING, STATUS_APPROVED):
		frappe.throw(_("عرض السعر {0} بالفعل.").format(doc.custom_approval_status))

	doc.update(
		{
			"custom_approval_status": STATUS_PENDING,
			"custom_approval_requested_by": frappe.session.user,
			"custom_approval_requested_on": now_datetime(),
			"custom_rejected_by": None,
			"custom_rejected_on": None,
			"custom_rejection_reason": None,
		}
	)
	_save(doc)
	_close_todos(doc, TODO_REWORK)

	settings = get_settings()
	description = _("مطلوب اعتماد عرض السعر {0} للعميل {1} بإجمالي {2}.").format(
		frappe.bold(doc.name), doc.customer_name or doc.party_name, frappe.format(doc.grand_total, {"fieldtype": "Currency", "options": doc.currency})
	)
	for user in _users_with_role(settings.approver_role):
		_create_todo(doc, user, description, TODO_REQUEST)
	doc.add_comment("Info", _("طُلب اعتماد عرض السعر"))
	return doc


@frappe.whitelist()
def approve(quotation):
	doc = _get_draft(quotation)
	_check_approver()
	if doc.custom_approval_status == STATUS_APPROVED:
		frappe.throw(_("عرض السعر معتمد بالفعل."))

	doc.update(
		{
			"custom_approval_status": STATUS_APPROVED,
			"custom_approved_by": frappe.session.user,
			"custom_approved_on": now_datetime(),
			"custom_rejected_by": None,
			"custom_rejected_on": None,
			"custom_rejection_reason": None,
		}
	)
	_save(doc)
	_close_todos(doc, TODO_REQUEST)
	_close_todos(doc, TODO_REWORK)
	doc.add_comment("Info", _("تم اعتماد عرض السعر"))
	_notify(
		doc,
		_("تم اعتماد عرض السعر {0} بواسطة {1}، ويمكن عمل Submit وإرساله للعميل.").format(
			frappe.bold(doc.name), get_fullname(frappe.session.user)
		),
	)
	return doc


@frappe.whitelist()
def reject(quotation, reason):
	doc = _get_draft(quotation)
	_check_approver()
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("اكتب سبب الرفض."))
	if doc.custom_approval_status != STATUS_PENDING:
		frappe.throw(_("الرفض متاح لعرض سعر بانتظار الاعتماد فقط."))

	doc.update(
		{
			"custom_approval_status": STATUS_REJECTED,
			"custom_rejected_by": frappe.session.user,
			"custom_rejected_on": now_datetime(),
			"custom_rejection_reason": reason,
			"custom_approval_fingerprint": None,
		}
	)
	_save(doc)
	_close_todos(doc, TODO_REQUEST)
	doc.add_comment("Info", _("رُفض عرض السعر: {0}").format(frappe.utils.escape_html(reason)))
	message = _("رُفض عرض السعر {0} بواسطة {1}. السبب: {2}").format(
		frappe.bold(doc.name), get_fullname(frappe.session.user), frappe.utils.escape_html(reason)
	)
	_notify(doc, message)
	for user in _people_to_notify(doc):
		_create_todo(doc, user, message, TODO_REWORK)
	return doc


# Helpers ------------------------------------------------------------------------------


def fingerprint(doc):
	"""The commercial content of the quotation; approval holds only while it is unchanged."""

	def num(value):
		return round(flt(value), 6)

	content = {
		"party": [doc.quotation_to, doc.party_name],
		"currency": [doc.currency, doc.selling_price_list],
		"items": [
			[row.item_code, num(row.qty), row.uom, num(row.rate), num(row.discount_percentage), num(row.discount_amount), row.description]
			for row in doc.items
		],
		"taxes": [doc.taxes_and_charges, [[t.charge_type, t.account_head, num(t.rate), num(t.tax_amount)] for t in doc.get("taxes") or []]],
		"discount": [doc.apply_discount_on, num(doc.additional_discount_percentage), num(doc.discount_amount)],
		"totals": [num(doc.grand_total), num(doc.rounded_total)],
		"advance": [doc.get("custom_advance_type"), num(doc.get("custom_advance_percentage")), num(doc.get("custom_advance_amount"))],
		"payment": [
			doc.payment_terms_template,
			[[p.payment_term, str(p.due_date), num(p.invoice_portion), num(p.payment_amount)] for p in doc.get("payment_schedule") or []],
		],
		"terms": [doc.tc_name, doc.terms],
		"valid_till": str(doc.valid_till or ""),
	}
	return hashlib.sha256(frappe.as_json(content).encode()).hexdigest()[:32]


def _get_draft(quotation):
	doc = frappe.get_doc("Quotation", quotation)
	doc.check_permission("read")
	if not get_settings().enabled:
		frappe.throw(_("دورة اعتماد عروض الأسعار غير مفعّلة من Selling Settings."))
	if doc.docstatus != 0:
		frappe.throw(_("الاعتماد يكون على عرض السعر قبل الـ Submit."))
	return doc


def _check_approver():
	settings = get_settings()
	if not is_approver(settings):
		frappe.throw(_("اعتماد عروض الأسعار متاح لدور {0} فقط.").format(frappe.bold(_(settings.approver_role or ""))), frappe.PermissionError)


def _save(doc):
	doc.flags.quotation_approval_action = True
	# The approver may not hold write rights on quotations; the decision is theirs to record.
	doc.flags.ignore_permissions = True
	doc.save()
	doc.flags.quotation_approval_action = False


def _people_to_notify(doc):
	users = []
	for user in (doc.owner, doc.custom_approval_requested_by):
		if user and user not in users and user not in ("Guest",) and frappe.db.get_value("User", user, "enabled"):
			users.append(user)
	return users


def _notify(doc, message):
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	users = [u for u in _people_to_notify(doc) if u != frappe.session.user]
	if users:
		enqueue_create_notification(
			users,
			{
				"type": "Alert",
				"document_type": doc.doctype,
				"document_name": doc.name,
				"subject": message,
				"from_user": frappe.session.user,
			},
		)


def _users_with_role(role):
	if not role:
		return []
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	return frappe.get_all(
		"User",
		filters=[
			["name", "in", users or ["-"]],
			["name", "not in", ["Administrator", "Guest"]],
			["enabled", "=", 1],
			["user_type", "=", "System User"],
		],
		pluck="name",
	)


def _create_todo(doc, user, description, kind):
	from frappe.desk.form.assign_to import notify_assignment
	from frappe.share import add_docshare

	if frappe.db.exists(
		"ToDo",
		{"reference_type": doc.doctype, "reference_name": doc.name, "allocated_to": user, "status": "Open", "custom_approval_todo": kind},
	):
		return
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": user,
			"reference_type": doc.doctype,
			"reference_name": doc.name,
			"description": description,
			"priority": "High",
			"assigned_by": frappe.session.user,
			"custom_approval_todo": kind,
		}
	).insert(ignore_permissions=True)
	if not frappe.has_permission(doc.doctype, "read", doc=doc, user=user):
		add_docshare(doc.doctype, doc.name, user, read=1, flags={"ignore_share_permission": True})
	notify_assignment(frappe.session.user, user, doc.doctype, doc.name, action="ASSIGN", description=description)


def _close_todos(doc, kind):
	for name in frappe.get_all(
		"ToDo",
		filters={"reference_type": doc.doctype, "reference_name": doc.name, "status": "Open", "custom_approval_todo": kind},
		pluck="name",
	):
		todo = frappe.get_doc("ToDo", name)
		todo.status = "Closed"
		todo.save(ignore_permissions=True)
