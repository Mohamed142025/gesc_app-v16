"""Execution items on Task.

Two kinds of task use the items table and the same workflow:

- Execution tasks: the Site Engineer lists the items, the Technical Office fills in
  quantities and documents, and the Site Engineer either approves (which raises a
  purchase Material Request for the project warehouse) or sends the task back with notes.
- Pre-quotation inspections: the Site Engineer records each item with site documents
  and a description, and the Technical Office confirms the quantities. Starting work
  makes a draft Quotation with the same items, in which the quantities and prices are
  finished; submitting that Quotation completes the task.

Submittals (materials, detailed drawings, structural calculations) share the workflow
and are handled in material_submittal.
"""

import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt, get_fullname, get_link_to_form, getdate, now_datetime, nowdate

SITE_ENGINEER = "Site Engineer"
TECHNICAL_OFFICE = "Technical Office"

WORKFLOW_NAME = "تنفيذ بنود المهام"
TASK_TYPE_NAME = "أعمال تنفيذ بنود"
INSPECTION_TYPE_NAME = "معاينة ما قبل عرض السعر"

STATE_OPEN = "مفتوحة"
STATE_PENDING_REVIEW = "في انتظار مراجعة المكتب الفني"
STATE_IN_PROGRESS = "جاري العمل"
STATE_EXECUTED = "تم التنفيذ ورفع المستندات"
STATE_NOTES = "يوجد ملاحظات"
STATE_NOTES_IN_PROGRESS = "جاري العمل على الملاحظات"
STATE_NOTES_DONE = "تم العمل على الملاحظات"
STATE_APPROVED = "معتمد"
STATE_INSPECTED = "تم المعاينة"
STATE_DONE = "تم التنفيذ"

ACTION_SEND = "إرسال للمكتب الفني"
ACTION_START = "بدء العمل"
ACTION_EXECUTED = "تم التنفيذ"
ACTION_APPROVE = "اعتماد"
ACTION_NOTES = "يوجد ملاحظات"
ACTION_START_NOTES = "بدء العمل على الملاحظات"
ACTION_NOTES_DONE = "تم العمل على الملاحظات"
ACTION_INSPECTED = "تم المعاينة"

# The kind of a task comes from a check on its Task Type, fetched onto the task.
SUBMITTAL_FLAGS = (
	"custom_is_material_submittal",
	"custom_is_drawing_submittal",
	"custom_is_calculation_submittal",
)
KIND_FLAGS = ("custom_has_work_items", "custom_is_pre_quotation_inspection", *SUBMITTAL_FLAGS)
# Every kind but the pre-quotation inspection, which comes before there is a project.
PROJECT_FLAGS = ("custom_has_work_items", *SUBMITTAL_FLAGS)

# States in which the Technical Office works on the items, and those waiting for the
# Site Engineer's decision.
TECHNICAL_OFFICE_STATES = (
	STATE_PENDING_REVIEW,
	STATE_IN_PROGRESS,
	STATE_NOTES,
	STATE_NOTES_IN_PROGRESS,
	STATE_INSPECTED,
)
# Once work starts on an inspection, quantities and prices live in its Quotation.
INSPECTION_OFFICE_STATES = (STATE_INSPECTED,)
DECISION_STATES = (STATE_EXECUTED, STATE_NOTES_DONE)

SITE_ENGINEER_FIELDS = (
	"item_code",
	"site_engineer_notes",
	"item_description",
	"description",
	"initial_qty",
)
TECHNICAL_OFFICE_FIELDS = ("qty", "technical_office_notes")
REVIEW_FIELDS = ("is_rejected", "site_engineer_approval_notes")

SITE_ENGINEER_ROLE = "مهندس الموقع"
TECHNICAL_OFFICE_ROLE = "المكتب الفني"

# Each item can have several files from each side. They are rows of one table on the task,
# tied to their item by its row_key; each item shows how many files each side has.
ITEM_ATTACHMENTS = "custom_execution_item_attachments"
ITEM_FILE_COUNTS = {
	SITE_ENGINEER_ROLE: "site_engineer_files",
	TECHNICAL_OFFICE_ROLE: "technical_office_files",
}
ITEM_ATTACHMENT_FIELDS = ("row_key", "uploaded_by_role", "attachment", "attachment_type", "notes")

# Task-level tables of Technical Office files, and how the document history names them.
ATTACHMENT_TABLES = {
	"custom_technical_office_attachments": "مرفقات المهمة",
	"custom_drawings": "جدول الرسومات",
	"custom_calculations": "جدول الحسابات الإنشائية",
}

# The site photos go to the Quotation's attachments table; the Technical Office's file
# goes on the Quotation item itself.
SITE_PHOTOS_TYPE = "صور الموقع"
OTHER_ATTACHMENT_TYPE = "أخرى"


def validate_task(doc, method=None):
	before = doc.get_doc_before_save()
	old_state = (before and before.get("workflow_state")) or STATE_OPEN
	new_state = doc.get("workflow_state") or STATE_OPEN

	# A task that is already in the workflow keeps its execution items even if its
	# type changes or the type stops having work items.
	if before and old_state != STATE_OPEN:
		if doc.type != before.type:
			frappe.throw(_("لا يمكن تغيير نوع المهمة بعد إرسالها للمكتب الفني."))
		for flag in KIND_FLAGS:
			doc.set(flag, before.get(flag))

	sync_item_attachments(doc)
	if item_files_changed(doc, before, TECHNICAL_OFFICE_ROLE) and 1 not in doc.get_permlevel_access("write"):
		frappe.throw(_("مرفقات المكتب الفني على البنود يرفعها ويعدّلها المكتب الفني فقط."))

	if not doc.project and any(doc.get(flag) for flag in PROJECT_FLAGS):
		frappe.throw(
			_("المشروع إلزامي في مهام بنود الأعمال واعتماد المواد والرسومات التفصيلية والحسابات الإنشائية."),
			title=_("المشروع مطلوب"),
		)

	if not _in_workflow(doc) and not (before and _in_workflow(before)):
		return

	is_submittal = _is_submittal(doc) or (before and _is_submittal(before))
	if old_state == STATE_OPEN or (is_submittal and old_state == STATE_IN_PROGRESS):
		_set_item_descriptions(doc)
	_keep_system_fields(doc, before)

	if is_submittal:
		from gesc_app.gesc_app import material_submittal

		material_submittal.validate(doc, before, old_state, new_state)
	else:
		_validate_item_changes(doc, before, old_state)
		if old_state != new_state:
			_apply_transition(doc, new_state)

	_log_documents(doc, before)


def on_task_update(doc, method=None):
	if _is_submittal(doc):
		from gesc_app.gesc_app import material_submittal

		material_submittal.on_update(doc)
		return

	if doc.get("custom_is_pre_quotation_inspection"):
		if doc.flags.make_quotation:
			doc.flags.make_quotation = None
			quotation = _create_task_quotation(doc)
			frappe.msgprint(
				_("تم إنشاء عرض السعر {0} بالبنود؛ أكمل فيه الكميات والأسعار.").format(
					get_link_to_form("Quotation", quotation)
				),
				alert=True,
				indicator="green",
			)
		return

	if not doc.get("custom_has_work_items"):
		return
	if doc.flags.notify_sent_to_office:
		doc.flags.notify_sent_to_office = None
		_notify_sent_to_office(doc)
	if doc.get("workflow_state") != STATE_APPROVED or doc.custom_material_request:
		return

	before = doc.get_doc_before_save()
	if not before or before.get("workflow_state") == STATE_APPROVED:
		return

	material_request = create_material_request(doc)
	doc.db_set("custom_material_request", material_request, update_modified=False)
	frappe.msgprint(
		_("تم إنشاء طلب المواد {0}").format(get_link_to_form("Material Request", material_request)),
		alert=True,
		indicator="green",
	)


def _notify_sent_to_office(doc):
	"""Everyone with the role chosen in Projects Settings hears that the task is waiting for
	the Technical Office."""
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	role = frappe.db.get_single_value("Projects Settings", "custom_execution_send_notify_role")
	users = [user for user in users_with_role(role) if user != frappe.session.user]
	if not users:
		return

	project = doc.project and (frappe.db.get_value("Project", doc.project, "project_name") or doc.project)
	subject = _("📋 {0} أرسل مهمة بنود الأعمال {1} «{2}» للمكتب الفني{3}.").format(
		escape_html(get_fullname(frappe.session.user)),
		doc.name,
		escape_html(doc.subject or ""),
		_(" — المشروع {0}").format(escape_html(project)) if project else "",
	)
	items = []
	for row in doc.custom_execution_items:
		qty = flt(row.qty) or flt(row.initial_qty)
		line = row.item_name or row.item_code
		if qty:
			line = f"{line} — {frappe.format(qty, 'Float')} {row.uom or ''}".strip()
		items.append(f"<li>{escape_html(line)}</li>")
	enqueue_create_notification(
		users,
		{
			"type": "Alert",
			"document_type": doc.doctype,
			"document_name": doc.name,
			"subject": subject,
			"email_content": _("البنود ({0}):").format(len(items)) + f"<ul>{''.join(items)}</ul>",
			"from_user": frappe.session.user,
		},
	)


def users_with_role(role):
	"""Active desk users who have the role."""
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


@frappe.whitelist()
def save_review(task, action, rows=None, required_by_date=None):
	"""Store the Site Engineer's decision before the workflow action runs.

	The workflow reloads the task from the database, so values chosen in the approval
	and notes dialogs have to be saved first.
	"""
	doc = frappe.get_doc("Task", task)
	doc.check_permission("write")

	if doc.get("workflow_state") not in DECISION_STATES:
		frappe.throw(_("المهمة ليست في مرحلة اعتماد مهندس الموقع."))
	if not _is_site_engineer():
		frappe.throw(_("الاعتماد أو تسجيل الملاحظات متاح لمهندس الموقع فقط."))

	if action == ACTION_APPROVE:
		doc.custom_required_by_date = required_by_date
	elif action == ACTION_NOTES:
		decisions = {row.get("name"): row for row in frappe.parse_json(rows) or []}
		for row in doc.custom_execution_items:
			decision = decisions.get(row.name) or {}
			row.is_rejected = cint(decision.get("is_rejected"))
			row.site_engineer_approval_notes = (decision.get("notes") or "").strip() if row.is_rejected else ""
	else:
		frappe.throw(_("إجراء غير معروف: {0}").format(action))

	doc.save()
	return doc


@frappe.whitelist()
def get_task_quotation(task):
	"""The Quotation made from this task, if one is still active."""
	frappe.get_doc("Task", task).check_permission("read")
	return _get_task_quotation(task)


@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	"""Opened by hand when the Quotation made on starting work was deleted, or for an
	inspection finished before Quotations were made automatically."""
	task = frappe.get_doc("Task", source_name)
	task.check_permission("read")
	if not task.get("custom_is_pre_quotation_inspection"):
		frappe.throw(_("عرض السعر يُنشأ من مهام معاينة ما قبل التسعير فقط."))
	if task.get("workflow_state") not in (STATE_IN_PROGRESS, STATE_DONE):
		frappe.throw(_("عرض السعر يُنشأ بعد بدء المكتب الفني العمل على المعاينة."))
	existing = _get_task_quotation(task.name)
	if existing:
		frappe.throw(_("للمهمة عرض سعر بالفعل: {0}").format(get_link_to_form("Quotation", existing)))
	return _map_quotation(source_name, target_doc)


def _map_quotation(source_name, target_doc=None):
	from frappe.model.mapper import get_mapped_doc

	def set_missing_values(source, target):
		if source.get("custom_customer"):
			target.quotation_to = "Customer"
			target.party_name = source.custom_customer
		# The items are mapped in order, so each Quotation item stands for the task item
		# at the same position.
		for row, item in zip(source.custom_execution_items, target.items):
			label = _("البند {0}: {1}").format(row.idx, row.item_name or row.item_code)
			for file in get_item_files(source, row, SITE_ENGINEER_ROLE):
				_append_quotation_file(target, file, file.attachment_type or SITE_PHOTOS_TYPE, label)
			office_files = get_item_files(source, row, TECHNICAL_OFFICE_ROLE)
			if office_files:
				item.custom_attachment = office_files[0].attachment
			for file in office_files[1:]:
				_append_quotation_file(
					target, file, file.attachment_type, _("{0} (المكتب الفني)").format(label)
				)
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	return get_mapped_doc(
		"Task",
		source_name,
		{
			# The Quotation's link back to the task (custom_task) is filled by the mapper.
			"Task": {"doctype": "Quotation", "field_no_map": ["status"]},
			"Task Execution Item": {
				"doctype": "Quotation Item",
				"field_map": {"item_description": "custom_item_description"},
			},
		},
		target_doc,
		set_missing_values,
	)


def _append_quotation_file(quotation, file, attachment_type, remarks):
	# "أخرى" on a Quotation asks for the type in words.
	attachment_type = attachment_type or OTHER_ATTACHMENT_TYPE
	quotation.append(
		"custom_attachments",
		{
			"attachment_type": attachment_type,
			"attachment_type_other": (file.notes or remarks) if attachment_type == OTHER_ATTACHMENT_TYPE else None,
			"attachment": file.attachment,
			"remarks": "\n".join(filter(None, (remarks, file.notes))),
		},
	)


def _create_task_quotation(task):
	"""The draft Quotation made when the Technical Office starts work on an inspection."""
	existing = _get_task_quotation(task.name)
	if existing:
		return existing
	quotation = _map_quotation(task.name)
	# Made by the workflow itself, whoever starts the work.
	quotation.flags.ignore_permissions = True
	quotation.insert()
	return quotation.name


def link_quotation_to_task(doc, method=None):
	"""Point the task at its Quotation, so the Quotation lists the task in its connections."""
	if not doc.get("custom_task") or doc.docstatus == 2 or doc.get("custom_is_addendum"):
		return
	if frappe.db.get_value("Task", doc.custom_task, "custom_quotation") != doc.name:
		frappe.db.set_value("Task", doc.custom_task, "custom_quotation", doc.name, update_modified=False)


def complete_inspection(doc, method=None):
	"""Submitting the Quotation made from an inspection completes the inspection.

	The task is written directly: whoever submits the Quotation (usually sales) holds no
	workflow transition on the task, and the Quotation must not be held up by it."""
	if not doc.get("custom_task") or doc.get("custom_is_addendum"):
		return
	task = frappe.get_doc("Task", doc.custom_task)
	if not task.get("custom_is_pre_quotation_inspection") or task.get("workflow_state") != STATE_IN_PROGRESS:
		return

	task.db_set(
		{
			"workflow_state": STATE_DONE,
			"status": "Completed",
			"completed_on": task.completed_on or nowdate(),
			"completed_by": task.completed_by or frappe.session.user,
		}
	)
	# What ERPNext does when a task is saved as Completed: the project's progress and the
	# task's open assignments.
	task.update_project()
	task.unassign_todo()
	task.add_comment("Info", _("اكتملت المهمة تلقائياً بتسجيل عرض السعر {0} نهائياً.").format(doc.name))
	frappe.msgprint(
		_("اكتملت مهمة المعاينة {0}.").format(get_link_to_form("Task", task.name)), alert=True, indicator="green"
	)


def validate_task_type(doc, method=None):
	if len([f for f in KIND_FLAGS if doc.get(f)]) > 1:
		frappe.throw(
			_(
				"نوع المهمة يكون نوعاً واحداً فقط: «له بنود أعمال» أو «معاينة ما قبل التسعير» أو «is Material Submittal» أو «اعتماد الرسومات التفصيلية» أو «اعتماد الحسابات الإنشائية»."
			)
		)


def create_material_request(task, quantities=None):
	"""A purchase Material Request for the task's items on the project warehouse, with
	each item's quantity, or the quantity given for its row in `quantities`."""
	existing = frappe.db.get_value("Material Request", {"custom_task": task.name, "docstatus": ("<", 2)})
	if existing:
		return existing

	company = _get_company(task)
	warehouse = get_project_warehouse(task.project, company)

	material_request = frappe.new_doc("Material Request")
	material_request.update(
		{
			"material_request_type": "Purchase",
			"company": company,
			"transaction_date": nowdate(),
			"schedule_date": task.custom_required_by_date,
			"set_warehouse": warehouse,
			"custom_task": task.name,
		}
	)

	for row in task.custom_execution_items:
		qty = flt(quantities.get(row.name)) if quantities is not None else flt(row.qty)
		if qty <= 0:
			continue
		item = frappe.get_cached_value("Item", row.item_code, ["stock_uom", "description"], as_dict=True)
		uom = row.uom or item.stock_uom
		material_request.append(
			"items",
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				# The description written on the task tells purchasing what exactly to buy.
				"description": (row.description or "").strip() or item.description or row.item_name,
				"qty": qty,
				"uom": uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": _get_conversion_factor(row.item_code, uom),
				"schedule_date": task.custom_required_by_date,
				"warehouse": warehouse,
				"project": task.project,
			},
		)

	# The request is raised by the approval itself, so the Site Engineer does not need
	# rights to create or submit purchase requests.
	material_request.flags.ignore_permissions = True
	material_request.insert()
	material_request.submit()
	return material_request.name


def get_project_warehouse(project, company=None):
	if not project:
		frappe.throw(_("اربط المهمة بمشروع قبل الاعتماد."))

	warehouse = frappe.db.get_value(
		"Warehouse",
		{"custom_is_project_warehouse": 1, "custom_project": project, "disabled": 0},
		["name", "company"],
		as_dict=True,
	)
	if not warehouse:
		frappe.throw(
			_("لا يوجد مخزن مربوط بالمشروع {0}. من شاشة المخزن علّم (هل هو مخزن مشروع) واختر المشروع، ثم أعد الاعتماد.").format(
				frappe.bold(project)
			),
			title=_("حدد مخزن المشروع"),
		)
	if company and warehouse.company != company:
		frappe.throw(
			_("مخزن المشروع {0} تابع لشركة {1} والمهمة تابعة لشركة {2}.").format(
				frappe.bold(warehouse.name), warehouse.company, company
			)
		)
	return warehouse.name


def validate_warehouse(doc, method=None):
	if not doc.get("custom_is_project_warehouse"):
		doc.custom_project = None
		return

	if doc.is_group:
		frappe.throw(_("مخزن المشروع لا يمكن أن يكون مجموعة."))
	if not doc.custom_project:
		frappe.throw(_("اختر المشروع المربوط بالمخزن."))

	project_company = frappe.db.get_value("Project", doc.custom_project, "company")
	if project_company and doc.company != project_company:
		frappe.throw(
			_("المشروع {0} تابع لشركة {1}، والمخزن تابع لشركة {2}.").format(
				frappe.bold(doc.custom_project), project_company, doc.company
			)
		)

	other = frappe.db.get_value(
		"Warehouse",
		{
			"custom_is_project_warehouse": 1,
			"custom_project": doc.custom_project,
			"disabled": 0,
			"name": ("!=", doc.name),
		},
	)
	if other:
		frappe.throw(
			_("المشروع {0} مربوط بالفعل بالمخزن {1}.").format(frappe.bold(doc.custom_project), frappe.bold(other))
		)


def _keep_system_fields(doc, before):
	"""Fields only this module writes: the request link, the round counter and the history."""
	doc.custom_material_request = before.custom_material_request if before else None
	doc.custom_review_round = cint(before.custom_review_round) if before else 0

	history = [(d.name, d.file) for d in doc.custom_execution_documents]
	previous = [(d.name, d.file) for d in before.custom_execution_documents] if before else []
	if history != previous:
		frappe.throw(_("سجل المستندات يُحدَّث تلقائياً ولا يمكن تعديله."))


def _validate_item_changes(doc, before, old_state):
	previous = {row.name: row for row in before.custom_execution_items} if before else {}
	current = {row.name for row in doc.custom_execution_items}

	site_engineer_changed = bool(set(previous) - current)
	technical_office_changed = review_changed = False
	for row in doc.custom_execution_items:
		old = previous.get(row.name)
		site_engineer_changed |= old is None or _changed(row, old, SITE_ENGINEER_FIELDS)
		technical_office_changed |= _changed(row, old, TECHNICAL_OFFICE_FIELDS)
		review_changed |= _changed(row, old, REVIEW_FIELDS)
	site_engineer_changed |= item_files_changed(doc, before, SITE_ENGINEER_ROLE)
	technical_office_changed |= item_files_changed(doc, before, TECHNICAL_OFFICE_ROLE)

	date_changed = _as_date(doc.custom_required_by_date) != _as_date(
		before.custom_required_by_date if before else None
	)

	if site_engineer_changed and old_state != STATE_OPEN:
		frappe.throw(_("لا يمكن إضافة أو حذف البنود أو تعديل بيانات مهندس الموقع بعد إرسال المهمة للمكتب الفني."))

	if technical_office_changed and doc.get("custom_is_pre_quotation_inspection") and old_state == STATE_IN_PROGRESS:
		frappe.throw(
			_("بدأ العمل على المعاينة، فالكميات والمرفقات تُستكمل في عرض السعر {0}.").format(
				doc.get("custom_quotation") or ""
			)
		)
	office_states = INSPECTION_OFFICE_STATES if doc.get("custom_is_pre_quotation_inspection") else TECHNICAL_OFFICE_STATES
	if technical_office_changed and old_state not in office_states:
		frappe.throw(
			_("الكمية ومرفقات وملاحظات المكتب الفني تُعدَّل فقط والمهمة عند المكتب الفني (الحالة الحالية: {0}).").format(
				old_state
			)
		)

	if (review_changed or date_changed) and (old_state not in DECISION_STATES or not _is_site_engineer()):
		frappe.throw(_("المرفوض وملاحظات الاعتماد وتاريخ الاحتياج يحددها مهندس الموقع عند الاعتماد فقط."))


def _apply_transition(doc, new_state):
	if not (doc.get("custom_has_work_items") or doc.get("custom_is_pre_quotation_inspection")):
		frappe.throw(_("نوع المهمة ليس له بنود أعمال ولا معاينة."))

	rows = doc.custom_execution_items
	if doc.get("custom_is_pre_quotation_inspection"):
		_apply_inspection_transition(doc, new_state)

	elif new_state == STATE_PENDING_REVIEW:
		if not rows:
			frappe.throw(_("أضف بند تنفيذ واحد على الأقل قبل الإرسال للمكتب الفني."))
		# Told once the task is saved in its new state.
		doc.flags.notify_sent_to_office = True

	elif new_state in (STATE_EXECUTED, STATE_NOTES_DONE):
		_validate_quantities_and_documents(rows)

	elif new_state == STATE_NOTES:
		rejected = [row for row in rows if row.is_rejected]
		if not rejected:
			frappe.throw(_("علّم بنداً مرفوضاً واحداً على الأقل."))
		without_notes = [str(row.idx) for row in rejected if not (row.site_engineer_approval_notes or "").strip()]
		if without_notes:
			frappe.throw(_("اكتب ملاحظات الاعتماد للبنود المرفوضة: {0}").format(", ".join(without_notes)))
		doc.custom_review_round = cint(doc.custom_review_round) + 1

	elif new_state == STATE_APPROVED:
		_validate_quantities_and_documents(rows)
		if not doc.custom_required_by_date:
			frappe.throw(_("حدد تاريخ الاحتياج قبل الاعتماد."))
		if getdate(doc.custom_required_by_date) < getdate(nowdate()):
			frappe.throw(_("تاريخ الاحتياج لا يمكن أن يكون في الماضي."))
		get_project_warehouse(doc.project, _get_company(doc))

		for row in rows:
			row.is_rejected = 0
		_set_completed(doc)


def _apply_inspection_transition(doc, new_state):
	rows = doc.custom_execution_items
	if new_state == STATE_INSPECTED:
		if not rows:
			frappe.throw(_("أضف بنداً واحداً على الأقل قبل تسجيل المعاينة."))
		missing = [
			str(row.idx)
			for row in rows
			if not cint(row.site_engineer_files) or not (row.description or "").strip()
		]
		if missing:
			frappe.throw(
				_("ارفع مرفق مهندس الموقع واكتب التوصيف لكل البنود. البنود الناقصة: {0}").format(", ".join(missing))
			)
		if not (doc.get("custom_project_name") or "").strip():
			frappe.throw(_("اكتب اسم المشروع في «بيانات المشروع / الموقع»."))
		_check_customer(doc)
		_check_sales_items(rows)

	elif new_state == STATE_IN_PROGRESS:
		# The Technical Office starts from the Site Engineer's figures.
		for row in rows:
			if not flt(row.qty) and flt(row.initial_qty):
				row.qty = row.initial_qty
		_check_customer(doc)
		_check_sales_items(rows)
		_validate_quantities_and_documents(rows, documents=False)
		# The Quotation is made once the task is saved in its new state.
		doc.flags.make_quotation = True

	elif new_state == STATE_DONE:
		_validate_quantities_and_documents(rows, documents=False)
		_set_completed(doc)


def _check_sales_items(rows):
	"""A Quotation takes sales items only; said here in the inspection's terms."""
	codes = {row.item_code for row in rows}
	not_for_sale = frappe.get_all("Item", filters={"name": ["in", list(codes) or [""]], "is_sales_item": 0}, pluck="name")
	if not_for_sale:
		frappe.throw(
			_("الأصناف التالية ليست أصناف بيع فلا تدخل عرض السعر: {0}. فعّل «Is Sales Item» في شاشة الصنف أو اختر صنفاً آخر.").format(
				", ".join(sorted(not_for_sale))
			)
		)


def _check_customer(doc):
	if not doc.get("custom_customer"):
		frappe.throw(_("اختر العميل في «بيانات المشروع / الموقع»؛ عرض السعر يُنشأ باسمه عند بدء العمل."))


def _set_completed(doc):
	if doc.status == "Completed" and not doc.completed_on:
		doc.completed_on = nowdate()
		doc.completed_by = doc.completed_by or frappe.session.user


def _validate_quantities_and_documents(rows, documents=True):
	if not rows:
		frappe.throw(_("لا توجد بنود تنفيذ."))

	if documents:
		missing = [str(row.idx) for row in rows if flt(row.qty) <= 0 or not cint(row.technical_office_files)]
		if missing:
			frappe.throw(
				_("أدخل الكمية وارفع مرفق المكتب الفني لكل البنود. البنود الناقصة: {0}").format(", ".join(missing))
			)
	else:
		missing = [str(row.idx) for row in rows if flt(row.qty) <= 0]
		if missing:
			frappe.throw(_("أدخل الكمية لكل البنود. البنود الناقصة: {0}").format(", ".join(missing)))

	fractional = [
		str(row.idx)
		for row in rows
		if row.uom
		and frappe.get_cached_value("UOM", row.uom, "must_be_whole_number")
		and flt(row.qty) != cint(row.qty)
	]
	if fractional:
		frappe.throw(_("وحدة القياس في البنود {0} لا تقبل كسوراً.").format(", ".join(fractional)))


def _log_documents(doc, before):
	review_round = cint(doc.custom_review_round) + 1
	# A file put back after being removed from its item is already in the history.
	logged = {(d.row_no, d.uploaded_by_role, d.file) for d in doc.custom_execution_documents}

	items = {row.row_key: row for row in doc.custom_execution_items}
	previous = {(f.row_key, f.uploaded_by_role, f.attachment) for f in before.get(ITEM_ATTACHMENTS)} if before else set()
	for file in doc.get(ITEM_ATTACHMENTS):
		row = items.get(file.row_key)
		if (
			not row
			or (file.row_key, file.uploaded_by_role, file.attachment) in previous
			or (row.idx, file.uploaded_by_role, file.attachment) in logged
		):
			continue
		logged.add((row.idx, file.uploaded_by_role, file.attachment))
		doc.append(
			"custom_execution_documents",
			{
				"row_no": row.idx,
				"item_code": row.item_code,
				"item_name": " - ".join(filter(None, (row.item_name, file.attachment_type))),
				"uploaded_by_role": file.uploaded_by_role,
				"review_round": review_round,
				"file": file.attachment,
				"uploaded_by": frappe.session.user,
				"uploaded_on": now_datetime(),
			},
		)

	for table, source in ATTACHMENT_TABLES.items():
		previous_files = {row.name: row.attachment for row in before.get(table)} if before else {}
		for row in doc.get(table):
			role = TECHNICAL_OFFICE_ROLE
			if (
				row.attachment
				and row.attachment != previous_files.get(row.name)
				and (row.idx, role, row.attachment) not in logged
			):
				doc.append(
					"custom_execution_documents",
					{
						"row_no": row.idx,
						"item_name": f"{source}: {row.attachment_type}" if row.attachment_type else source,
						"uploaded_by_role": role,
						"review_round": review_round,
						"file": row.attachment,
						"uploaded_by": frappe.session.user,
						"uploaded_on": now_datetime(),
					},
				)


def _changed(row, old, fieldnames):
	for fieldname in fieldnames:
		value = row.get(fieldname)
		old_value = old.get(fieldname) if old else None
		if fieldname in ("qty", "initial_qty", "is_rejected"):
			if flt(value) != flt(old_value):
				return True
		elif (value or "").strip() != (old_value or "").strip():
			return True
	return False


def sync_item_attachments(doc):
	"""Tie each item file to its item: give new items their key, drop the files of removed
	items, and count each side's files on the item."""
	if not doc.meta.has_field(ITEM_ATTACHMENTS):
		return

	items = {}
	for row in doc.get("custom_execution_items"):
		# A copied row comes with the key of the row it was copied from.
		if not row.row_key or row.row_key in items:
			row.row_key = frappe.generate_hash(length=12)
		items[row.row_key] = row

	files = [file for file in doc.get(ITEM_ATTACHMENTS) if file.row_key in items]
	doc.set(ITEM_ATTACHMENTS, files)
	counts = {}
	for idx, file in enumerate(files, 1):
		if file.uploaded_by_role not in ITEM_FILE_COUNTS:
			frappe.throw(_("جهة المرفق غير معروفة: {0}").format(file.uploaded_by_role))
		row = items[file.row_key]
		file.idx = idx
		file.row_no = row.idx
		file.item_code = row.item_code
		key = (file.row_key, file.uploaded_by_role)
		counts[key] = counts.get(key, 0) + 1

	for row in items.values():
		for role, fieldname in ITEM_FILE_COUNTS.items():
			row.set(fieldname, counts.get((row.row_key, role), 0))


def get_item_files(doc, row, role):
	return [
		file
		for file in doc.get(ITEM_ATTACHMENTS)
		if file.row_key == row.row_key and file.uploaded_by_role == role
	]


def item_files_changed(doc, before, role):
	"""Whether one side's files on the task's current items were added, removed or edited.
	The files of a removed item go with it, and removing items is checked on its own."""
	keys = {row.row_key for row in doc.get("custom_execution_items")}

	def files(task):
		return sorted(
			tuple((file.get(f) or "").strip() for f in ITEM_ATTACHMENT_FIELDS)
			for file in (task.get(ITEM_ATTACHMENTS) if task else [])
			if file.uploaded_by_role == role and file.row_key in keys
		)

	return files(doc) != files(before)


def _in_workflow(doc):
	return any(doc.get(flag) for flag in KIND_FLAGS)


def _is_submittal(doc):
	return any(doc.get(flag) for flag in SUBMITTAL_FLAGS)


def _set_item_descriptions(doc):
	"""An item's description comes from the chosen library entry unless one was written."""
	for row in doc.custom_execution_items:
		if not row.get("item_description"):
			continue
		entry = frappe.db.get_value("Item Description", row.item_description, ["item_code", "description"], as_dict=True)
		if not entry or entry.item_code != row.item_code:
			frappe.throw(_("التوصيف المختار في البند {0} غير مرتبط بالصنف.").format(row.idx))
		if not (row.description or "").strip():
			row.description = entry.description


def _get_task_quotation(task):
	# An addendum copies the link from its main Quotation but is not the inspection's.
	return frappe.db.get_value(
		"Quotation",
		{"custom_task": task, "docstatus": ("<", 2), "custom_is_addendum": 0},
		"name",
		order_by="creation desc",
	)


def _as_date(value):
	# getdate(None) returns today, so an empty date has to stay empty here.
	return getdate(value) if value else None


def _get_company(task):
	company = task.company or frappe.db.get_value("Project", task.project, "company")
	if not company:
		frappe.throw(_("حدد الشركة في المهمة أو المشروع."))
	return company


def _get_conversion_factor(item_code, uom):
	from erpnext.stock.get_item_details import get_conversion_factor

	conversion_factor = flt(get_conversion_factor(item_code, uom).get("conversion_factor"))
	if not conversion_factor:
		frappe.throw(_("لا يوجد معامل تحويل للوحدة {0} في الصنف {1}.").format(uom, item_code))
	return conversion_factor


def _is_site_engineer():
	return SITE_ENGINEER in frappe.get_roles()
