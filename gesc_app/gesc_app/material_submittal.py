"""Material submittals on Task.

The Technical Office prepares the materials and sends them to the consultant; the
consultant's answer comes back outside the system and the Document Controller records it
with the stamped file. Every submission is a revision (Rev 00, Rev 01, ...) kept with its
answer. Code 2 sends the comments to the execution and operations roles as ToDos, whose
closing by each user is recorded as having read them; code 4 goes to the Projects
Managers for a decision.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, now_datetime, nowdate

from gesc_app.gesc_app.task_execution import (
	STATE_APPROVED,
	STATE_IN_PROGRESS,
	STATE_OPEN,
	_changed,
)

DOCUMENT_CONTROLLER = "Document Controller"
OPERATIONS = "Operations"
PROJECTS_MANAGER = "Projects Manager"
SUBMITTAL_TYPE_NAME = "اعتماد مواد (Material Submittal)"

STATE_SUBMITTED = "تم الإرسال للاستشاري"
STATE_APPROVED_COMMENTS = "معتمد بملاحظات"
STATE_CORRECTIONS = "مرفوض – تعديلات مطلوبة"
STATE_REWORK = "مرفوض – إعادة عمل"
STATE_CANCELLED = "ملغي"

ACTION_SUBMIT = "إرسال للاستشاري"
ACTION_CODE_APPROVED = "رد: Approved"
ACTION_CODE_COMMENTS = "رد: Approved with Comments"
ACTION_CODE_CORRECTIONS = "رد: Rejected – Corrections Required"
ACTION_CODE_REWORK = "رد: Rejected – Rework Required"
ACTION_START_CORRECTIONS = "بدء التعديل"
ACTION_RESUBMIT = "إعادة التقديم"
ACTION_CANCEL = "إلغاء"

CODE_APPROVED = "Approved"
CODE_COMMENTS = "Approved with Comments"
CODE_CORRECTIONS = "Rejected – Corrections Required"
CODE_REWORK = "Rejected – Rework Required"

# The state each answer leads to, and its code.
RESPONSE_CODES = {
	STATE_APPROVED: CODE_APPROVED,
	STATE_APPROVED_COMMENTS: CODE_COMMENTS,
	STATE_CORRECTIONS: CODE_CORRECTIONS,
	STATE_REWORK: CODE_REWORK,
}

PREPARING_STATES = (STATE_OPEN, STATE_IN_PROGRESS)
ITEM_FIELDS = (
	"item_code",
	"item_description",
	"description",
	"manufacturer",
	"qty",
	"technical_office_attachment",
	"technical_office_notes",
	"site_engineer_attachment",
	"site_engineer_notes",
)
RESPONSE_FIELDS = ("custom_response_file", "custom_response_date", "custom_consultant_ref", "custom_response_comments")
SYSTEM_FIELDS = ("custom_submittal_no", "custom_submittal_revision", "custom_submitted_on", "custom_response_due_date")


def get_settings():
	get = lambda field: frappe.db.get_single_value("Projects Settings", field)  # noqa: E731
	return frappe._dict(
		execution_role=get("custom_submittal_execution_role"),
		operations_role=get("custom_submittal_operations_role"),
		response_days=cint(get("custom_submittal_response_days")) or 14,
	)


def validate(doc, before, old_state, new_state):
	_keep_system_fields(doc, before)
	_validate_item_changes(doc, before, old_state)
	_validate_field_changes(doc, before, old_state)
	if old_state != new_state:
		_apply_transition(doc, old_state, new_state)


def on_update(doc):
	notify = doc.flags.submittal_notify
	doc.flags.submittal_notify = None
	if notify == CODE_COMMENTS:
		_assign_comments(doc)
	elif notify == CODE_REWORK:
		_assign_rework_decision(doc)


def acknowledge(todo, method=None):
	"""A user closing their own ToDo for code 2 comments has read them. ERPNext also
	closes a task's open ToDos when the task is saved as Completed; that is done under
	whoever saved it, so it is not taken as reading."""
	if not todo.get("custom_submittal_ack") or todo.status != "Closed" or not todo.has_value_changed("status"):
		return
	if frappe.session.user != todo.allocated_to:
		return
	frappe.db.set_value(
		"Task Submittal Acknowledgement",
		todo.custom_submittal_ack,
		{"acknowledged": 1, "acknowledged_on": now_datetime()},
		update_modified=False,
	)


def response_overdue_days(task):
	"""Days the consultant's answer is late, for a task waiting on it."""
	if task.get("workflow_state") != STATE_SUBMITTED or not task.get("custom_response_due_date"):
		return 0
	return max(date_diff(nowdate(), task.custom_response_due_date), 0)


# Validation -----------------------------------------------------------------------------


def _keep_system_fields(doc, before):
	for fieldname in SYSTEM_FIELDS:
		doc.set(fieldname, before.get(fieldname) if before else None)

	for table, key in (
		("custom_submittal_revisions", ("name", "revision", "response_code", "response_file", "decision")),
		("custom_submittal_acknowledgements", ("name", "user", "acknowledged")),
	):
		current = [tuple(row.get(k) for k in key) for row in doc.get(table)]
		previous = [tuple(row.get(k) for k in key) for row in before.get(table)] if before else []
		if current != previous:
			frappe.throw(_("سجل المراجعات والاطلاع يُحدَّثان تلقائياً ولا يمكن تعديلهما."))


def _validate_item_changes(doc, before, old_state):
	previous = {row.name: row for row in before.custom_execution_items} if before else {}
	current = {row.name for row in doc.custom_execution_items}
	changed = bool(set(previous) - current) or any(
		row.name not in previous or _changed(row, previous[row.name], ITEM_FIELDS)
		for row in doc.custom_execution_items
	)
	if changed and old_state not in PREPARING_STATES:
		frappe.throw(_("بنود الـ Submittal تُعدَّل أثناء الإعداد فقط (الحالة الحالية: {0}).").format(old_state))


def _validate_field_changes(doc, before, old_state):
	def changed(fieldname):
		return (doc.get(fieldname) or None) != ((before.get(fieldname) if before else None) or None)

	if any(changed(f) for f in RESPONSE_FIELDS):
		if old_state != STATE_SUBMITTED or not _has_role(DOCUMENT_CONTROLLER):
			frappe.throw(_("رد الاستشاري يسجّله مراقب الوثائق فقط، والمهمة في حالة «{0}».").format(STATE_SUBMITTED))

	if changed("custom_rework_decision") and (old_state != STATE_REWORK or not _has_role(PROJECTS_MANAGER)):
		frappe.throw(_("قرار الرفض التام يكتبه مدير المشاريع والمهمة في حالة «{0}».").format(STATE_REWORK))

	if changed("custom_transmittal_no") and old_state not in PREPARING_STATES:
		frappe.throw(_("رقم خطاب الإرسال يُكتب أثناء الإعداد فقط."))


def _apply_transition(doc, old_state, new_state):
	if new_state == STATE_IN_PROGRESS:
		if old_state == STATE_REWORK:
			_record_decision(doc)
		# Files uploaded from now on belong to the next revision in the document history.
		doc.custom_review_round = len(doc.custom_submittal_revisions)

	elif new_state == STATE_SUBMITTED:
		_submit(doc)

	elif new_state in RESPONSE_CODES:
		_record_response(doc, RESPONSE_CODES[new_state])

	elif new_state == STATE_CANCELLED:
		_record_decision(doc)
		if not doc.completed_on:
			doc.completed_on = nowdate()


def _submit(doc):
	if not doc.project:
		frappe.throw(_("اربط المهمة بمشروع قبل الإرسال للاستشاري."))
	rows = doc.custom_execution_items
	if not rows:
		frappe.throw(_("أضف مادة واحدة على الأقل قبل الإرسال للاستشاري."))
	missing = [str(row.idx) for row in rows if not row.technical_office_attachment]
	if missing:
		frappe.throw(_("ارفع الـ Data Sheet (مرفق المكتب الفني) لكل المواد. البنود الناقصة: {0}").format(", ".join(missing)))

	if not doc.custom_submittal_no:
		from frappe.model.naming import getseries

		prefix = f"{doc.project}-MS-"
		doc.custom_submittal_no = prefix + getseries(prefix, 3)

	revision = len(doc.custom_submittal_revisions)
	today = nowdate()
	doc.append(
		"custom_submittal_revisions",
		{
			"revision": revision,
			"submitted_on": today,
			"transmittal_no": doc.custom_transmittal_no,
			"submitted_by": frappe.session.user,
		},
	)
	doc.custom_submittal_revision = revision
	doc.custom_submitted_on = today
	doc.custom_response_due_date = add_days(today, get_settings().response_days)
	doc.custom_transmittal_no = None


def _record_response(doc, code):
	if not doc.custom_response_file:
		frappe.throw(_("ارفع ملف رد الاستشاري المختوم في قسم «رد الاستشاري»."))
	if not doc.custom_response_date:
		frappe.throw(_("اكتب تاريخ رد الاستشاري."))
	if getdate(doc.custom_response_date) > getdate(nowdate()):
		frappe.throw(_("تاريخ رد الاستشاري لا يمكن أن يكون في المستقبل."))
	if doc.custom_submitted_on and getdate(doc.custom_response_date) < getdate(doc.custom_submitted_on):
		frappe.throw(_("تاريخ رد الاستشاري قبل تاريخ الإرسال."))
	comments = (doc.custom_response_comments or "").strip()
	if code != CODE_APPROVED and not comments:
		frappe.throw(_("اكتب ملاحظات الاستشاري؛ هي مطلوبة مع الكود «{0}».").format(code))

	revision = doc.custom_submittal_revisions[-1]
	revision.update(
		{
			"response_code": code,
			"response_date": doc.custom_response_date,
			"consultant_ref": doc.custom_consultant_ref,
			"response_comments": comments,
			"response_file": doc.custom_response_file,
			"recorded_by": frappe.session.user,
			"days_with_consultant": date_diff(doc.custom_response_date, revision.submitted_on),
		}
	)
	for fieldname in RESPONSE_FIELDS:
		doc.set(fieldname, None)
	doc.custom_response_due_date = None

	if code in (CODE_APPROVED, CODE_COMMENTS) and not doc.completed_on:
		doc.completed_on = nowdate()
		doc.completed_by = doc.completed_by or frappe.session.user

	if code == CODE_COMMENTS:
		for user, role in _users_to_inform():
			doc.append(
				"custom_submittal_acknowledgements",
				{"user": user, "role": role, "revision": revision.revision, "acknowledged": 0},
			)
		doc.flags.submittal_notify = CODE_COMMENTS
	elif code == CODE_REWORK:
		doc.flags.submittal_notify = CODE_REWORK


def _record_decision(doc):
	decision = (doc.custom_rework_decision or "").strip()
	if not decision:
		frappe.throw(_("اكتب قرار الإدارة (الاجتماع أو تغيير آلية التنفيذ أو المواصفات) قبل المتابعة."))
	doc.custom_submittal_revisions[-1].update(
		{"decision": decision, "decided_by": frappe.session.user, "decided_on": now_datetime()}
	)
	doc.custom_rework_decision = None


# Notifications --------------------------------------------------------------------------


def _users_to_inform():
	settings = get_settings()
	seen, users = set(), []
	for role in (settings.execution_role, settings.operations_role):
		for user in _users_with_role(role):
			if user not in seen:
				seen.add(user)
				users.append((user, role))
	return users


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


def _assign_comments(doc):
	revision = doc.custom_submittal_revisions[-1]
	description = _("ملاحظات الاستشاري على {0} (Rev {1:02d}) الواجب مراعاتها في التنفيذ:<br>{2}").format(
		frappe.bold(doc.custom_submittal_no), cint(revision.revision), frappe.utils.escape_html(revision.response_comments)
	)
	for row in doc.custom_submittal_acknowledgements:
		if cint(row.revision) == cint(revision.revision) and not row.acknowledged:
			_create_todo(doc, row.user, description, ack_row=row.name)


def _assign_rework_decision(doc):
	revision = doc.custom_submittal_revisions[-1]
	description = _("رفض تام لـ {0} (Rev {1:02d}): مطلوب قرار الإدارة.<br>{2}").format(
		frappe.bold(doc.custom_submittal_no), cint(revision.revision), frappe.utils.escape_html(revision.response_comments)
	)
	for user in _users_with_role(PROJECTS_MANAGER):
		_create_todo(doc, user, description)


def _create_todo(doc, user, description, ack_row=None):
	from frappe.desk.form.assign_to import notify_assignment
	from frappe.share import add_docshare

	frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": user,
			"reference_type": doc.doctype,
			"reference_name": doc.name,
			"description": description,
			"priority": "High",
			"date": nowdate(),
			"assigned_by": frappe.session.user,
			"custom_submittal_ack": ack_row,
		}
	).insert(ignore_permissions=True)
	if not frappe.has_permission(doc.doctype, "read", doc=doc, user=user):
		add_docshare(doc.doctype, doc.name, user, read=1, flags={"ignore_share_permission": True})
	notify_assignment(frappe.session.user, user, doc.doctype, doc.name, action="ASSIGN", description=description)


def _has_role(role):
	return role in frappe.get_roles()
