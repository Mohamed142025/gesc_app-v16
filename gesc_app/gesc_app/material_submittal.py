"""Submittals on Task: materials, detailed drawings and structural calculations.

The Technical Office prepares the submittal and sends it to the consultant: a material
submittal sends its items with their data sheets (or files for the whole task), a drawing
or calculation submittal sends the files in its own table. The consultant's answer comes
back outside the system and the Document Controller records it with the stamped file.
Every submission is a revision (Rev 00, Rev 01, ...) kept with its answer. Code 2 sends
the comments to the execution and operations roles as ToDos, whose closing by each user
is recorded as having read them; code 3 marks the rejected rows with the consultant's
note on each; code 4 goes to the Projects Managers for a decision. An approved material
submittal can then raise a purchase Material Request for the project warehouse.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, get_link_to_form, getdate, now_datetime, nowdate

from gesc_app.gesc_app.task_execution import (
	SITE_ENGINEER,
	STATE_APPROVED,
	STATE_IN_PROGRESS,
	STATE_OPEN,
	TECHNICAL_OFFICE,
	_changed,
	_get_company,
	create_material_request,
	get_project_warehouse,
)

DOCUMENT_CONTROLLER = "Document Controller"
OPERATIONS = "Operations"
PROJECTS_MANAGER = "Projects Manager"
SUBMITTAL_TYPE_NAME = "اعتماد مواد (Material Submittal)"
DRAWING_TYPE_NAME = "اعتماد الرسومات التفصيلية (Shop Drawings)"
CALCULATION_TYPE_NAME = "اعتماد الحسابات الإنشائية (Calculation)"

# Each kind of submittal: the table it sends, the code in its number and the table's name.
KINDS = {
	"custom_is_material_submittal": frappe._dict(table="custom_execution_items", code="MS", label="بنود التنفيذ"),
	"custom_is_drawing_submittal": frappe._dict(table="custom_drawings", code="SD", label="جدول الرسومات"),
	"custom_is_calculation_submittal": frappe._dict(
		table="custom_calculations", code="CALC", label="جدول الحسابات الإنشائية"
	),
}
# Files the Technical Office adds for a whole material submittal.
TASK_ATTACHMENTS = "custom_technical_office_attachments"

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
# The consultant's code is kept once the submittal is approved.
FINAL_STATES = (STATE_APPROVED, STATE_APPROVED_COMMENTS)
ITEM_FIELDS = (
	"item_code",
	"item_description",
	"description",
	"manufacturer",
	"qty",
	"technical_office_attachment",
	"attachment_type",
	"technical_office_notes",
	"site_engineer_attachment",
	"site_engineer_notes",
)
FILE_FIELDS = ("attachment", "attachment_type", "notes")
# Set on the rows of the sent table when the consultant rejects some of them (code 3).
REJECTION_FIELDS = ("is_rejected", "consultant_notes")
RESPONSE_FIELDS = (
	"custom_response_file",
	"custom_response_date",
	"custom_consultant_ref",
	"custom_response_comments",
	"custom_response_comments_file",
)
SYSTEM_FIELDS = ("custom_submittal_no", "custom_submittal_revision", "custom_submitted_on", "custom_response_due_date")


def get_settings():
	get = lambda field: frappe.db.get_single_value("Projects Settings", field)  # noqa: E731
	return frappe._dict(
		execution_role=get("custom_submittal_execution_role"),
		operations_role=get("custom_submittal_operations_role"),
		response_days=cint(get("custom_submittal_response_days")) or 14,
	)


def get_kind(doc):
	return next((kind for flag, kind in KINDS.items() if doc.get(flag)), None)


def validate(doc, before, old_state, new_state):
	_keep_system_fields(doc, before)
	_validate_table_changes(doc, before, old_state)
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


@frappe.whitelist()
def save_rejections(task, rows):
	"""Mark the rows the consultant rejected (code 3), each with the consultant's note,
	before the workflow action records the answer; the action reloads the task from the
	database, so the marks have to be saved first."""
	doc = frappe.get_doc("Task", task)
	doc.check_permission("write")
	if not get_kind(doc) or doc.get("workflow_state") != STATE_SUBMITTED:
		frappe.throw(_("المهمة ليست في انتظار رد الاستشاري."))
	if not _has_role(DOCUMENT_CONTROLLER):
		frappe.throw(_("رد الاستشاري يسجّله مراقب الوثائق فقط."), frappe.PermissionError)
	_check_response(doc)

	decisions = {row.get("name"): row for row in frappe.parse_json(rows) or []}
	table = doc.get(get_kind(doc).table)
	for row in table:
		decision = decisions.get(row.name) or {}
		row.is_rejected = cint(decision.get("is_rejected"))
		row.consultant_notes = (decision.get("notes") or "").strip() if row.is_rejected else None
	_check_rejections(table)

	# The tables are the Technical Office's (field level 1); only the two marks change here.
	doc.flags.ignore_permissions = True
	doc.save()
	return doc


@frappe.whitelist()
def make_material_request(task, required_by_date, rows):
	"""A purchase Material Request for an approved material submittal, with the
	quantities to buy now for each material."""
	doc = frappe.get_doc("Task", task)
	doc.check_permission("read")
	if not doc.get("custom_is_material_submittal"):
		frappe.throw(_("طلب المواد يُنشأ من مهام اعتماد المواد فقط."))
	if doc.get("workflow_state") not in FINAL_STATES:
		frappe.throw(_("طلب المواد يُنشأ بعد اعتماد الاستشاري (Approved أو Approved with Comments)."))
	if not can_request_materials():
		frappe.throw(_("ليست لديك صلاحية إنشاء طلب مواد."), frappe.PermissionError)
	existing = frappe.db.get_value("Material Request", {"custom_task": doc.name, "docstatus": ("<", 2)})
	if existing:
		frappe.throw(_("للمهمة طلب مواد بالفعل: {0}").format(get_link_to_form("Material Request", existing)))
	if not doc.project:
		frappe.throw(_("اربط المهمة بمشروع قبل طلب المواد."))
	if not required_by_date:
		frappe.throw(_("حدد تاريخ الاحتياج."))
	if getdate(required_by_date) < getdate(nowdate()):
		frappe.throw(_("تاريخ الاحتياج لا يمكن أن يكون في الماضي."))
	get_project_warehouse(doc.project, _get_company(doc))

	quantities = {row.get("name"): flt(row.get("qty")) for row in frappe.parse_json(rows) or []}
	lines = [row for row in doc.custom_execution_items if quantities.get(row.name, 0) > 0]
	if not lines:
		frappe.throw(_("أدخل الكمية المطلوبة لمادة واحدة على الأقل."))
	fractional = [
		str(row.idx)
		for row in lines
		if row.uom
		and frappe.get_cached_value("UOM", row.uom, "must_be_whole_number")
		and quantities[row.name] != cint(quantities[row.name])
	]
	if fractional:
		frappe.throw(_("وحدة القياس في البنود {0} لا تقبل كسوراً.").format(", ".join(fractional)))

	doc.custom_required_by_date = required_by_date
	material_request = create_material_request(doc, quantities)
	doc.db_set({"custom_material_request": material_request, "custom_required_by_date": required_by_date})
	doc.add_comment("Info", _("طلب المواد {0}").format(get_link_to_form("Material Request", material_request)))
	return material_request


def can_request_materials():
	roles = set(frappe.get_roles())
	return bool(roles & {SITE_ENGINEER, TECHNICAL_OFFICE, PROJECTS_MANAGER}) or frappe.has_permission(
		"Material Request", "create"
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


def _validate_table_changes(doc, before, old_state):
	tables = {"custom_execution_items": ITEM_FIELDS, **{t: FILE_FIELDS for t in (TASK_ATTACHMENTS, *_file_tables())}}
	for table, fieldnames in tables.items():
		if _rows_changed(doc, before, table, fieldnames) and old_state not in PREPARING_STATES:
			frappe.throw(
				_("بنود ومرفقات الـ Submittal تُعدَّل أثناء الإعداد فقط (الحالة الحالية: {0}).").format(old_state)
			)

	# The rejected rows are marked by the Document Controller with the consultant's answer.
	kind = get_kind(doc)
	if kind and _rows_changed(doc, before, kind.table, REJECTION_FIELDS, rows_only=True):
		if old_state != STATE_SUBMITTED or not _has_role(DOCUMENT_CONTROLLER):
			frappe.throw(_("البنود المرفوضة يحددها مراقب الوثائق عند تسجيل رد الاستشاري فقط."))


def _file_tables():
	return [kind.table for kind in KINDS.values() if kind.table != "custom_execution_items"]


def _rows_changed(doc, before, table, fieldnames, rows_only=False):
	"""Whether rows were added or removed, or the given fields changed. With `rows_only`,
	only the given fields of existing rows count."""
	previous = {row.name: row for row in before.get(table)} if before else {}
	current = {row.name for row in doc.get(table)}
	if not rows_only and set(previous) - current:
		return True
	for row in doc.get(table):
		old = previous.get(row.name)
		if old is None:
			if not rows_only or any(row.get(f) for f in fieldnames):
				return True
		elif _changed(row, old, fieldnames):
			return True
	return False


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

	# The submittal number carries the project, and a material request goes to its warehouse.
	if changed("project") and before and before.get("custom_submittal_no"):
		frappe.throw(_("لا يمكن تغيير المشروع أو حذفه بعد إرسال الـ Submittal للاستشاري."))


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
	kind = get_kind(doc)
	rows = doc.get(kind.table)
	if kind.table == "custom_execution_items":
		if not rows:
			frappe.throw(_("أضف مادة واحدة على الأقل قبل الإرسال للاستشاري."))
		# Files for the whole task stand in for the files of each item.
		missing = [str(row.idx) for row in rows if not row.technical_office_attachment]
		if missing and not doc.get(TASK_ATTACHMENTS):
			frappe.throw(
				_(
					"ارفع الـ Data Sheet (مرفق المكتب الفني) لكل المواد، أو ارفع مرفقات المكتب الفني على مستوى المهمة. البنود الناقصة: {0}"
				).format(", ".join(missing))
			)
	elif not rows:
		frappe.throw(_("أضف ملفاً واحداً على الأقل في «{0}» قبل الإرسال للاستشاري.").format(kind.label))

	# The last answer's rejections were worked on; they stay in the revision history.
	for row in rows:
		row.is_rejected = 0
		row.consultant_notes = None

	if not doc.custom_submittal_no:
		from frappe.model.naming import getseries

		prefix = f"{doc.project}-{kind.code}-"
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
	_check_response(doc)
	comments = (doc.custom_response_comments or "").strip()
	comments_file = doc.get("custom_response_comments_file")

	rows = doc.get(get_kind(doc).table)
	rejected = []
	if code == CODE_CORRECTIONS:
		# The notes on each rejected row are the consultant's comments here.
		rejected = _check_rejections(rows)
	else:
		for row in rows:
			row.is_rejected = 0
			row.consultant_notes = None
		if code != CODE_APPROVED and not comments and not comments_file:
			frappe.throw(_("اكتب ملاحظات الاستشاري أو ارفع ملف الملاحظات؛ أحدهما مطلوب مع الكود «{0}».").format(code))

	revision = doc.custom_submittal_revisions[-1]
	revision.update(
		{
			"response_code": code,
			"response_date": doc.custom_response_date,
			"consultant_ref": doc.custom_consultant_ref,
			"response_comments": comments,
			"response_comments_file": comments_file,
			"rejected_items": "\n".join(f"{row.idx}. {_row_label(row)}: {row.consultant_notes}" for row in rejected),
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


def _check_response(doc):
	if not doc.custom_response_file:
		frappe.throw(_("ارفع ملف رد الاستشاري المختوم في قسم «رد الاستشاري»."))
	if not doc.custom_response_date:
		frappe.throw(_("اكتب تاريخ رد الاستشاري."))
	if getdate(doc.custom_response_date) > getdate(nowdate()):
		frappe.throw(_("تاريخ رد الاستشاري لا يمكن أن يكون في المستقبل."))
	if doc.custom_submitted_on and getdate(doc.custom_response_date) < getdate(doc.custom_submitted_on):
		frappe.throw(_("تاريخ رد الاستشاري قبل تاريخ الإرسال."))


def _check_rejections(rows):
	rejected = [row for row in rows if row.is_rejected]
	if not rejected:
		frappe.throw(_("حدد البنود المرفوضة مع الكود «{0}».").format(CODE_CORRECTIONS))
	without_notes = [str(row.idx) for row in rejected if not (row.consultant_notes or "").strip()]
	if without_notes:
		frappe.throw(_("اكتب ملاحظات الاستشاري للبنود المرفوضة: {0}").format(", ".join(without_notes)))
	return rejected


def _row_label(row):
	if row.doctype == "Task Execution Item":
		return row.item_name or row.item_code
	name = (row.attachment or "").rsplit("/", 1)[-1]
	return f"{row.attachment_type} - {name}" if row.attachment_type else name


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


def _comments_html(revision):
	html = frappe.utils.escape_html(revision.response_comments or "")
	if revision.get("response_comments_file"):
		link = f'<a href="{frappe.utils.escape_html(revision.response_comments_file)}" target="_blank">{_("ملف ملاحظات الاستشاري")}</a>'
		html = f"{html}<br>{link}" if html else link
	return html


def _assign_comments(doc):
	revision = doc.custom_submittal_revisions[-1]
	description = _("ملاحظات الاستشاري على {0} (Rev {1:02d}) الواجب مراعاتها في التنفيذ:<br>{2}").format(
		frappe.bold(doc.custom_submittal_no), cint(revision.revision), _comments_html(revision)
	)
	for row in doc.custom_submittal_acknowledgements:
		if cint(row.revision) == cint(revision.revision) and not row.acknowledged:
			_create_todo(doc, row.user, description, ack_row=row.name)


def _assign_rework_decision(doc):
	revision = doc.custom_submittal_revisions[-1]
	description = _("رفض تام لـ {0} (Rev {1:02d}): مطلوب قرار الإدارة.<br>{2}").format(
		frappe.bold(doc.custom_submittal_no), cint(revision.revision), _comments_html(revision)
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
