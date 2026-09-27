"""Setup for execution items and pre-quotation inspections on Task: fields, roles,
permissions, workflow and task types.

Runs after every migrate. Custom fields follow the code. Roles, permission rules and task
types are only created when missing, and the workflow only gets the states and transitions
it lacks, so changes made to them from the UI are kept.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from gesc_app.gesc_app.task_execution import (
	ACTION_APPROVE,
	ACTION_EXECUTED,
	ACTION_INSPECTED,
	ACTION_NOTES,
	ACTION_NOTES_DONE,
	ACTION_SEND,
	ACTION_START,
	ACTION_START_NOTES,
	INSPECTION_TYPE_NAME,
	SITE_ENGINEER,
	STATE_APPROVED,
	STATE_DONE,
	STATE_EXECUTED,
	STATE_IN_PROGRESS,
	STATE_INSPECTED,
	STATE_NOTES,
	STATE_NOTES_DONE,
	STATE_NOTES_IN_PROGRESS,
	STATE_OPEN,
	STATE_PENDING_REVIEW,
	TASK_TYPE_NAME,
	TECHNICAL_OFFICE,
	WORKFLOW_NAME,
)
from gesc_app.gesc_app.material_submittal import (
	ACTION_CANCEL,
	ACTION_CODE_APPROVED,
	ACTION_CODE_COMMENTS,
	ACTION_CODE_CORRECTIONS,
	ACTION_CODE_REWORK,
	ACTION_RESUBMIT,
	ACTION_START_CORRECTIONS,
	ACTION_SUBMIT,
	DOCUMENT_CONTROLLER,
	OPERATIONS,
	PROJECTS_MANAGER,
	STATE_APPROVED_COMMENTS,
	STATE_CANCELLED,
	STATE_CORRECTIONS,
	STATE_REWORK,
	STATE_SUBMITTED,
	SUBMITTAL_TYPE_NAME,
)

MODULE = "Gesc App"
USES_ITEMS = "eval:doc.custom_has_work_items || doc.custom_is_pre_quotation_inspection || doc.custom_is_material_submittal"
IS_INSPECTION = "eval:doc.custom_is_pre_quotation_inspection"
IS_SUBMITTAL = "eval:doc.custom_is_material_submittal"

# Transition conditions keep the two kinds of task apart.
EXECUTION = "doc.custom_has_work_items"
INSPECTION = "doc.custom_is_pre_quotation_inspection"
SUBMITTAL = "doc.custom_is_material_submittal"

ROLE_TRANSLATIONS = {
	SITE_ENGINEER: "مهندس الموقع",
	TECHNICAL_OFFICE: "المكتب الفني",
	DOCUMENT_CONTROLLER: "مراقب الوثائق",
	OPERATIONS: "إدارة العمليات",
}

# state, style, who may edit it, task status it sets
STATES = (
	(STATE_OPEN, "", "All", None),
	(STATE_PENDING_REVIEW, "Warning", TECHNICAL_OFFICE, "Open"),
	(STATE_IN_PROGRESS, "Primary", TECHNICAL_OFFICE, "Working"),
	(STATE_EXECUTED, "Info", SITE_ENGINEER, "Pending Review"),
	(STATE_NOTES, "Danger", TECHNICAL_OFFICE, "Working"),
	(STATE_NOTES_IN_PROGRESS, "Primary", TECHNICAL_OFFICE, "Working"),
	(STATE_NOTES_DONE, "Info", SITE_ENGINEER, "Pending Review"),
	(STATE_APPROVED, "Success", "System Manager", "Completed"),
	(STATE_INSPECTED, "Warning", TECHNICAL_OFFICE, "Open"),
	(STATE_DONE, "Success", "System Manager", "Completed"),
	(STATE_SUBMITTED, "Warning", DOCUMENT_CONTROLLER, "Pending Review"),
	(STATE_APPROVED_COMMENTS, "Success", "System Manager", "Completed"),
	(STATE_CORRECTIONS, "Danger", TECHNICAL_OFFICE, "Working"),
	(STATE_REWORK, "Danger", PROJECTS_MANAGER, "Working"),
	(STATE_CANCELLED, "Inverse", "System Manager", "Cancelled"),
)

# state, action, next state, who may do it, condition
TRANSITIONS = (
	(STATE_OPEN, ACTION_SEND, STATE_PENDING_REVIEW, SITE_ENGINEER, EXECUTION),
	(STATE_PENDING_REVIEW, ACTION_START, STATE_IN_PROGRESS, TECHNICAL_OFFICE, EXECUTION),
	(STATE_IN_PROGRESS, ACTION_EXECUTED, STATE_EXECUTED, TECHNICAL_OFFICE, EXECUTION),
	(STATE_EXECUTED, ACTION_APPROVE, STATE_APPROVED, SITE_ENGINEER, EXECUTION),
	(STATE_EXECUTED, ACTION_NOTES, STATE_NOTES, SITE_ENGINEER, EXECUTION),
	(STATE_NOTES, ACTION_START_NOTES, STATE_NOTES_IN_PROGRESS, TECHNICAL_OFFICE, EXECUTION),
	(STATE_NOTES_IN_PROGRESS, ACTION_NOTES_DONE, STATE_NOTES_DONE, TECHNICAL_OFFICE, EXECUTION),
	(STATE_NOTES_DONE, ACTION_APPROVE, STATE_APPROVED, SITE_ENGINEER, EXECUTION),
	(STATE_NOTES_DONE, ACTION_NOTES, STATE_NOTES, SITE_ENGINEER, EXECUTION),
	(STATE_OPEN, ACTION_INSPECTED, STATE_INSPECTED, SITE_ENGINEER, INSPECTION),
	(STATE_INSPECTED, ACTION_START, STATE_IN_PROGRESS, TECHNICAL_OFFICE, INSPECTION),
	(STATE_IN_PROGRESS, ACTION_EXECUTED, STATE_DONE, TECHNICAL_OFFICE, INSPECTION),
	(STATE_OPEN, ACTION_START, STATE_IN_PROGRESS, TECHNICAL_OFFICE, SUBMITTAL),
	(STATE_IN_PROGRESS, ACTION_SUBMIT, STATE_SUBMITTED, TECHNICAL_OFFICE, SUBMITTAL),
	(STATE_SUBMITTED, ACTION_CODE_APPROVED, STATE_APPROVED, DOCUMENT_CONTROLLER, SUBMITTAL),
	(STATE_SUBMITTED, ACTION_CODE_COMMENTS, STATE_APPROVED_COMMENTS, DOCUMENT_CONTROLLER, SUBMITTAL),
	(STATE_SUBMITTED, ACTION_CODE_CORRECTIONS, STATE_CORRECTIONS, DOCUMENT_CONTROLLER, SUBMITTAL),
	(STATE_SUBMITTED, ACTION_CODE_REWORK, STATE_REWORK, DOCUMENT_CONTROLLER, SUBMITTAL),
	(STATE_CORRECTIONS, ACTION_START_CORRECTIONS, STATE_IN_PROGRESS, TECHNICAL_OFFICE, SUBMITTAL),
	(STATE_REWORK, ACTION_RESUBMIT, STATE_IN_PROGRESS, PROJECTS_MANAGER, SUBMITTAL),
	(STATE_REWORK, ACTION_CANCEL, STATE_CANCELLED, PROJECTS_MANAGER, SUBMITTAL),
)

# doctype, role, permlevel, rights
PERMISSIONS = (
	("Task", SITE_ENGINEER, 0, {"read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "print": 1, "email": 1, "share": 1}),
	("Task", SITE_ENGINEER, 1, {"read": 1}),
	# Create: the Technical Office opens material submittals itself.
	("Task", TECHNICAL_OFFICE, 0, {"read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "print": 1, "email": 1}),
	("Task", TECHNICAL_OFFICE, 1, {"read": 1, "write": 1}),
	("Task", "Projects User", 1, {"read": 1}),
	("Project", SITE_ENGINEER, 0, {"read": 1}),
	("Project", TECHNICAL_OFFICE, 0, {"read": 1}),
	("Task Type", SITE_ENGINEER, 0, {"read": 1}),
	("Task Type", TECHNICAL_OFFICE, 0, {"read": 1}),
	("Item", SITE_ENGINEER, 0, {"read": 1}),
	("Item", TECHNICAL_OFFICE, 0, {"read": 1}),
	("Material Request", SITE_ENGINEER, 0, {"read": 1}),
	("Material Request", TECHNICAL_OFFICE, 0, {"read": 1}),
	("Item Description", SITE_ENGINEER, 0, {"read": 1}),
	("Item Description", TECHNICAL_OFFICE, 0, {"read": 1}),
	("Customer", SITE_ENGINEER, 0, {"read": 1}),
	("Task", DOCUMENT_CONTROLLER, 0, {"read": 1, "write": 1, "report": 1, "export": 1, "print": 1, "email": 1}),
	("Task", DOCUMENT_CONTROLLER, 1, {"read": 1}),
	("Project", DOCUMENT_CONTROLLER, 0, {"read": 1}),
	("Item", DOCUMENT_CONTROLLER, 0, {"read": 1}),
	("Item Description", DOCUMENT_CONTROLLER, 0, {"read": 1}),
)


def setup_task_execution():
	setup_custom_fields()
	setup_roles()
	setup_permissions()
	setup_workflow()
	setup_task_types()
	setup_submittal_settings()
	frappe.clear_cache(doctype="Task")


def setup_custom_fields():
	create_custom_fields(
		{
			"Task Type": [
				{
					"fieldname": "custom_has_work_items",
					"label": "هل له بنود أعمال",
					"fieldtype": "Check",
					"insert_after": "weight",
					"module": MODULE,
				},
				{
					"fieldname": "custom_is_pre_quotation_inspection",
					"label": "معاينة ما قبل التسعير",
					"fieldtype": "Check",
					"insert_after": "custom_has_work_items",
					"module": MODULE,
				},
				{
					"fieldname": "custom_is_material_submittal",
					"label": "is Material Submittal",
					"fieldtype": "Check",
					"insert_after": "custom_is_pre_quotation_inspection",
					"description": "اعتماد مواد من الاستشاري أو المالك بالأكواد: Approved / Approved with Comments / Rejected – Corrections Required / Rejected – Rework Required.",
					"module": MODULE,
				},
			],
			"Warehouse": [
				{
					"fieldname": "custom_is_project_warehouse",
					"label": "هل هو مخزن مشروع",
					"fieldtype": "Check",
					"insert_after": "customer",
					"module": MODULE,
				},
				{
					"fieldname": "custom_project",
					"label": "المشروع",
					"fieldtype": "Link",
					"options": "Project",
					"insert_after": "custom_is_project_warehouse",
					"depends_on": "eval:doc.custom_is_project_warehouse",
					"mandatory_depends_on": "eval:doc.custom_is_project_warehouse",
					"module": MODULE,
				},
			],
			"Task": [
				{
					"fieldname": "custom_has_work_items",
					"label": "له بنود أعمال",
					"fieldtype": "Check",
					"fetch_from": "type.custom_has_work_items",
					"insert_after": "type",
					"read_only": 1,
					"hidden": 1,
					"module": MODULE,
				},
				{
					"fieldname": "custom_is_pre_quotation_inspection",
					"label": "معاينة ما قبل التسعير",
					"fieldtype": "Check",
					"fetch_from": "type.custom_is_pre_quotation_inspection",
					"insert_after": "custom_has_work_items",
					"read_only": 1,
					"hidden": 1,
					"module": MODULE,
				},
				{
					"fieldname": "custom_is_material_submittal",
					"label": "is Material Submittal",
					"fieldtype": "Check",
					"fetch_from": "type.custom_is_material_submittal",
					"insert_after": "custom_is_pre_quotation_inspection",
					"read_only": 1,
					"hidden": 1,
					"module": MODULE,
				},
				# Project and site details, named as on the Quotation so they carry over. The
				# section goes before the Details section: Frappe moves a section placed after
				# "description" past the next tab break.
				{
					"fieldname": "custom_project_site_section",
					"label": "بيانات المشروع / الموقع",
					"fieldtype": "Section Break",
					"insert_after": "is_milestone",
					"depends_on": IS_INSPECTION,
					"module": MODULE,
				},
				{
					"fieldname": "custom_customer",
					"label": "العميل",
					"fieldtype": "Link",
					"options": "Customer",
					"insert_after": "custom_project_site_section",
					"module": MODULE,
				},
				{
					"fieldname": "custom_project_name",
					"label": "اسم المشروع",
					"fieldtype": "Data",
					"insert_after": "custom_customer",
					"module": MODULE,
				},
				{
					"fieldname": "custom_city",
					"label": "اسم المدينة",
					"fieldtype": "Data",
					"insert_after": "custom_project_name",
					"module": MODULE,
				},
				{
					"fieldname": "custom_project_site_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_city",
					"module": MODULE,
				},
				{
					"fieldname": "custom_district_street",
					"label": "اسم المجموعة / الشارع",
					"fieldtype": "Data",
					"insert_after": "custom_project_site_column",
					"module": MODULE,
				},
				{
					"fieldname": "custom_villa_apartment_no",
					"label": "رقم الفيلا / الشقة",
					"fieldtype": "Data",
					"insert_after": "custom_district_street",
					"module": MODULE,
				},
				{
					"fieldname": "custom_execution_tab",
					"label": "بنود التنفيذ",
					"fieldtype": "Tab Break",
					"insert_after": "description",
					"depends_on": USES_ITEMS,
					"module": MODULE,
				},
				{
					"fieldname": "custom_execution_items",
					"label": "بنود التنفيذ",
					"fieldtype": "Table",
					"options": "Task Execution Item",
					"insert_after": "custom_execution_tab",
					"no_copy": 1,
					"module": MODULE,
				},
				{
					"fieldname": "custom_execution_approval_section",
					"label": "الاعتماد",
					"fieldtype": "Section Break",
					"insert_after": "custom_execution_items",
					"module": MODULE,
				},
				{
					"fieldname": "custom_required_by_date",
					"label": "تاريخ الاحتياج",
					"fieldtype": "Date",
					"insert_after": "custom_execution_approval_section",
					"read_only": 1,
					"no_copy": 1,
					"module": MODULE,
				},
				{
					"fieldname": "custom_review_round",
					"label": "عدد جولات الملاحظات",
					"fieldtype": "Int",
					"insert_after": "custom_required_by_date",
					"depends_on": "eval:doc.custom_review_round",
					"read_only": 1,
					"no_copy": 1,
					"module": MODULE,
				},
				{
					"fieldname": "custom_execution_approval_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_review_round",
					"module": MODULE,
				},
				{
					"fieldname": "custom_material_request",
					"label": "طلب المواد",
					"fieldtype": "Link",
					"options": "Material Request",
					"insert_after": "custom_execution_approval_column",
					"read_only": 1,
					"no_copy": 1,
					"module": MODULE,
				},
				*submittal_task_fields("custom_material_request"),
				{
					"fieldname": "custom_execution_documents_section",
					"label": "سجل المستندات",
					"fieldtype": "Section Break",
					"insert_after": "custom_submittal_acknowledgements",
					"collapsible": 1,
					"module": MODULE,
				},
				{
					"fieldname": "custom_execution_documents",
					"label": "سجل المستندات",
					"fieldtype": "Table",
					"options": "Task Execution Document",
					"insert_after": "custom_execution_documents_section",
					"read_only": 1,
					"no_copy": 1,
					"module": MODULE,
				},
			],
			"Material Request": [
				{
					"fieldname": "custom_task",
					"label": "المهمة",
					"fieldtype": "Link",
					"options": "Task",
					"insert_after": "schedule_date",
					"read_only": 1,
					"no_copy": 1,
					"module": MODULE,
				},
			],
			"ToDo": [
				# The acknowledgement row a code 2 ToDo stands for.
				{
					"fieldname": "custom_submittal_ack",
					"label": "Submittal Acknowledgement",
					"fieldtype": "Data",
					"insert_after": "reference_name",
					"read_only": 1,
					"hidden": 1,
					"module": MODULE,
				},
			],
			"Projects Settings": [
				{
					"fieldname": "custom_submittal_section",
					"label": "اعتمادات المواد (Material Submittal)",
					"fieldtype": "Section Break",
					"insert_after": "fetch_timesheet_in_sales_invoice",
					"module": MODULE,
				},
				{
					"fieldname": "custom_submittal_execution_role",
					"label": "دور إدارة التنفيذ",
					"fieldtype": "Link",
					"options": "Role",
					"insert_after": "custom_submittal_section",
					"description": "يصلهم ToDo بملاحظات الكود 2 (Approved with Comments).",
					"module": MODULE,
				},
				{
					"fieldname": "custom_submittal_operations_role",
					"label": "دور إدارة العمليات",
					"fieldtype": "Link",
					"options": "Role",
					"insert_after": "custom_submittal_execution_role",
					"module": MODULE,
				},
				{
					"fieldname": "custom_submittal_response_days",
					"label": "مدة رد الاستشاري (أيام)",
					"fieldtype": "Int",
					"default": "14",
					"insert_after": "custom_submittal_operations_role",
					"module": MODULE,
				},
			],
			"Quotation": [
				# Kept on amendment, so every revision stays linked to the inspection.
				{
					"fieldname": "custom_task",
					"label": "مهمة المعاينة",
					"fieldtype": "Link",
					"options": "Task",
					"insert_after": "custom_villa_apartment_no",
					"read_only": 1,
					"module": MODULE,
				},
			],
		},
		update=True,
	)


def setup_roles():
	for role, translation in ROLE_TRANSLATIONS.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)

		if not frappe.db.exists("Translation", {"language": "ar", "source_text": role}):
			frappe.get_doc(
				{
					"doctype": "Translation",
					"language": "ar",
					"source_text": role,
					"translated_text": translation,
				}
			).insert(ignore_permissions=True)


def setup_permissions():
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
	from frappe.permissions import setup_custom_perms

	changed = set()
	for doctype, role, permlevel, rights in PERMISSIONS:
		setup_custom_perms(doctype)
		if frappe.db.exists(
			"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": 0}
		):
			continue

		frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": doctype,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": permlevel,
				**rights,
			}
		).insert(ignore_permissions=True)
		changed.add(doctype)

	for doctype in changed:
		validate_permissions_for_doctype(doctype)


def setup_workflow():
	for state, style, _allow_edit, _status in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style}).insert(
				ignore_permissions=True
			)

	for action in {t[1] for t in TRANSITIONS}:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		workflow = frappe.get_doc("Workflow", WORKFLOW_NAME)
	else:
		workflow = frappe.new_doc("Workflow")
		workflow.update(
			{
				"workflow_name": WORKFLOW_NAME,
				"document_type": "Task",
				"workflow_state_field": "workflow_state",
				"is_active": 1,
				"send_email_alert": 0,
			}
		)

	# Only what is missing is added; rows already there, and changes to them, stay.
	states = {row.state for row in workflow.states}
	transitions = {(row.state, row.action, row.next_state, row.condition) for row in workflow.transitions}
	added = False
	for state, _style, allow_edit, status in STATES:
		if state in states:
			continue
		workflow.append(
			"states",
			{
				"state": state,
				"doc_status": "0",
				"allow_edit": allow_edit,
				"update_field": "status" if status else None,
				"update_value": status,
				# Ordinary tasks never leave the first state, so they keep showing their own status.
				"avoid_status_override": 1 if state == STATE_OPEN else 0,
			},
		)
		added = True
	for state, action, next_state, allowed, condition in TRANSITIONS:
		if (state, action, next_state, condition) in transitions:
			continue
		workflow.append(
			"transitions",
			{
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": allowed,
				"allow_self_approval": 1,
				"condition": condition,
			},
		)
		added = True

	if workflow.is_new():
		workflow.insert(ignore_permissions=True)
	elif added:
		workflow.save(ignore_permissions=True)


def setup_submittal_settings():
	defaults = {
		"custom_submittal_execution_role": SITE_ENGINEER,
		"custom_submittal_operations_role": OPERATIONS,
		"custom_submittal_response_days": 14,
	}
	for field, value in defaults.items():
		if not frappe.db.get_single_value("Projects Settings", field):
			frappe.db.set_single_value("Projects Settings", field, value)


def submittal_task_fields(insert_after):
	"""Submittal number and dates, the consultant's answer, the decision on a full
	rejection, and the revision and acknowledgement records."""
	fields = [
		("custom_submittal_section", "بيانات الـ Submittal", "Section Break", {"depends_on": IS_SUBMITTAL}),
		("custom_submittal_no", "رقم الـ Submittal", "Data", {"read_only": 1, "no_copy": 1}),
		("custom_submittal_revision", "المراجعة الحالية (Rev)", "Int", {"read_only": 1, "no_copy": 1, "depends_on": "eval:doc.custom_submittal_no"}),
		("custom_transmittal_no", "رقم خطاب الإرسال", "Data", {"no_copy": 1}),
		("custom_submittal_column", None, "Column Break", {}),
		("custom_submitted_on", "تاريخ الإرسال", "Date", {"read_only": 1, "no_copy": 1}),
		("custom_response_due_date", "تاريخ الرد المتوقع", "Date", {"read_only": 1, "no_copy": 1}),
		("custom_response_section", "رد الاستشاري", "Section Break",
			{"depends_on": f'eval:doc.custom_is_material_submittal && doc.workflow_state == "{STATE_SUBMITTED}"'}),
		("custom_response_file", "الملف المختوم", "Attach", {"no_copy": 1}),
		("custom_response_date", "تاريخ الرد", "Date", {"no_copy": 1}),
		("custom_response_column", None, "Column Break", {}),
		("custom_consultant_ref", "رقم خطاب الاستشاري", "Data", {"no_copy": 1}),
		("custom_response_comments", "ملاحظات الاستشاري", "Small Text", {"no_copy": 1}),
		("custom_rework_section", "قرار الإدارة", "Section Break",
			{"depends_on": f'eval:doc.custom_is_material_submittal && doc.workflow_state == "{STATE_REWORK}"'}),
		("custom_rework_decision", "القرار (اجتماع، تغيير آلية التنفيذ أو المواصفات)", "Small Text", {"no_copy": 1}),
		("custom_submittal_revisions_section", "سجل المراجعات", "Section Break", {"depends_on": IS_SUBMITTAL}),
		("custom_submittal_revisions", "سجل المراجعات", "Table",
			{"options": "Task Submittal Revision", "read_only": 1, "no_copy": 1}),
		("custom_submittal_ack_section", "الاطلاع على ملاحظات الكود 2", "Section Break",
			{"depends_on": "eval:(doc.custom_submittal_acknowledgements || []).length"}),
		("custom_submittal_acknowledgements", "الاطلاع على الملاحظات", "Table",
			{"options": "Task Submittal Acknowledgement", "read_only": 1, "no_copy": 1}),
	]
	out = []
	for fieldname, label, fieldtype, extra in fields:
		out.append({"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "insert_after": insert_after, "module": MODULE, **extra})
		insert_after = fieldname
	return out


def setup_task_types():
	for name, flag in (
		(TASK_TYPE_NAME, "custom_has_work_items"),
		(INSPECTION_TYPE_NAME, "custom_is_pre_quotation_inspection"),
		(SUBMITTAL_TYPE_NAME, "custom_is_material_submittal"),
	):
		if not frappe.db.exists("Task Type", name):
			frappe.get_doc({"doctype": "Task Type", flag: 1}).insert(ignore_permissions=True, set_name=name)
