"""Fields for quotation approval. Runs after every migrate; approval starts off until it is
switched on in Selling Settings."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from gesc_app.gesc_app.quotation_approval import (
	STATUS_APPROVED,
	STATUS_DRAFT,
	STATUS_PENDING,
	STATUS_REJECTED,
	TODO_REQUEST,
	TODO_REWORK,
)

MODULE = "Gesc App"
ENABLED = "eval:doc.custom_quotation_approval_enabled"


def setup_quotation_approval():
	record = {"read_only": 1, "no_copy": 1, "module": MODULE}
	create_custom_fields(
		{
			"Selling Settings": [
				{
					"fieldname": "custom_quotation_approval_section",
					"label": "اعتماد عروض الأسعار",
					"fieldtype": "Section Break",
					"insert_after": "set_zero_rate_for_expired_batch",
					"module": MODULE,
				},
				{
					"fieldname": "custom_quotation_approval_enabled",
					"label": "تفعيل دورة اعتماد عروض الأسعار",
					"fieldtype": "Check",
					"insert_after": "custom_quotation_approval_section",
					"description": "عرض السعر لا يُعمل له Submit قبل اعتماده، وأي تغيير في محتواه التجاري بعد الاعتماد يلغيه.",
					"module": MODULE,
				},
				{
					"fieldname": "custom_quotation_approver_role",
					"label": "الدور المعتمِد لعروض الأسعار",
					"fieldtype": "Link",
					"options": "Role",
					"insert_after": "custom_quotation_approval_enabled",
					"depends_on": ENABLED,
					"mandatory_depends_on": ENABLED,
					"module": MODULE,
				},
				{
					"fieldname": "custom_quotation_block_unapproved_print",
					"label": "منع طباعة وتنزيل وإرسال عرض السعر قبل اعتماده",
					"fieldtype": "Check",
					"insert_after": "custom_quotation_approver_role",
					"depends_on": ENABLED,
					"description": "الدور المعتمِد يقدر يعاين دائماً.",
					"module": MODULE,
				},
				{
					"fieldname": "custom_quotation_request_notify_role",
					"label": "الدور الذي يُبلَّغ عند طلب الاعتماد",
					"fieldtype": "Link",
					"options": "Role",
					"insert_after": "custom_quotation_block_unapproved_print",
					"depends_on": ENABLED,
					"description": "عند الضغط على «طلب اعتماد» يصل إشعار تلقائي لكل مستخدم له هذا الدور (الدور المعتمِد يصله ToDo بالفعل). اتركه فارغاً لإيقاف الإشعار.",
					"module": MODULE,
				},
			],
			"Quotation": [
				{
					"fieldname": "custom_approval_status",
					"label": "حالة الاعتماد",
					"fieldtype": "Select",
					"options": f"\n{STATUS_DRAFT}\n{STATUS_PENDING}\n{STATUS_APPROVED}\n{STATUS_REJECTED}",
					"insert_after": "order_type",
					"depends_on": "eval:doc.custom_approval_status",
					"in_list_view": 1,
					"in_standard_filter": 1,
					"allow_on_submit": 1,
					**record,
				},
				{
					"fieldname": "custom_approval_section",
					"label": "بيانات الاعتماد",
					"fieldtype": "Section Break",
					"insert_after": "custom_advance_required",
					"collapsible": 1,
					"depends_on": "eval:doc.custom_approval_requested_by || doc.custom_approved_by || doc.custom_rejected_by",
					"module": MODULE,
				},
				{"fieldname": "custom_approval_requested_by", "label": "طلب الاعتماد", "fieldtype": "Link", "options": "User",
					"insert_after": "custom_approval_section", **record},
				{"fieldname": "custom_approval_requested_on", "label": "تاريخ الطلب", "fieldtype": "Datetime",
					"insert_after": "custom_approval_requested_by", **record},
				{"fieldname": "custom_approval_column", "fieldtype": "Column Break", "insert_after": "custom_approval_requested_on", "module": MODULE},
				{"fieldname": "custom_approved_by", "label": "اعتمده", "fieldtype": "Link", "options": "User",
					"insert_after": "custom_approval_column", "allow_on_submit": 1, **record},
				{"fieldname": "custom_approved_on", "label": "تاريخ الاعتماد", "fieldtype": "Datetime",
					"insert_after": "custom_approved_by", "allow_on_submit": 1, **record},
				{"fieldname": "custom_rejected_by", "label": "رفضه", "fieldtype": "Link", "options": "User",
					"insert_after": "custom_approved_on", **record},
				{"fieldname": "custom_rejected_on", "label": "تاريخ الرفض", "fieldtype": "Datetime",
					"insert_after": "custom_rejected_by", **record},
				{"fieldname": "custom_rejection_reason", "label": "سبب الرفض", "fieldtype": "Small Text",
					"insert_after": "custom_rejected_on", **record},
				{"fieldname": "custom_approval_fingerprint", "label": "بصمة المحتوى المعتمد", "fieldtype": "Data",
					"insert_after": "custom_rejection_reason", "hidden": 1, "allow_on_submit": 1, **record},
			],
			"ToDo": [
				{
					"fieldname": "custom_approval_todo",
					"label": "Quotation Approval",
					"fieldtype": "Select",
					"options": f"\n{TODO_REQUEST}\n{TODO_REWORK}",
					"insert_after": "reference_name",
					"read_only": 1,
					"hidden": 1,
					"module": MODULE,
				},
			],
		},
		update=True,
	)
