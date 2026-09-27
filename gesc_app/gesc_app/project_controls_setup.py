"""Fields for the project creation rules. Runs after every migrate; the rules start off
until they are switched on in Projects Settings."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from gesc_app.gesc_app.project_controls import ADVANCE_AMOUNT, ADVANCE_PERCENTAGE

MODULE = "Gesc App"
IS_PERCENTAGE = f"eval:doc.custom_advance_type == '{ADVANCE_PERCENTAGE}'"
IS_AMOUNT = f"eval:doc.custom_advance_type == '{ADVANCE_AMOUNT}'"


def advance_fields(insert_after, allow_on_submit=0):
	"""The agreed down payment, named the same on Quotation and Sales Order so it carries over."""
	return [
		{
			"fieldname": "custom_advance_type",
			"label": "طريقة الدفعة المقدمة",
			"fieldtype": "Select",
			"options": f"\n{ADVANCE_PERCENTAGE}\n{ADVANCE_AMOUNT}",
			"insert_after": insert_after,
			"allow_on_submit": allow_on_submit,
			"module": MODULE,
		},
		{
			"fieldname": "custom_advance_percentage",
			"label": "نسبة الدفعة المقدمة %",
			"fieldtype": "Percent",
			"insert_after": "custom_advance_type",
			"depends_on": IS_PERCENTAGE,
			"allow_on_submit": allow_on_submit,
			"module": MODULE,
		},
		{
			"fieldname": "custom_advance_amount",
			"label": "قيمة الدفعة المقدمة",
			"fieldtype": "Currency",
			"options": "currency",
			"insert_after": "custom_advance_percentage",
			"depends_on": IS_AMOUNT,
			"allow_on_submit": allow_on_submit,
			"module": MODULE,
		},
	]


def required_field(insert_after):
	return {
		"fieldname": "custom_advance_required",
		"label": "الدفعة المقدمة المطلوبة",
		"fieldtype": "Currency",
		"options": "currency",
		"insert_after": insert_after,
		"read_only": 1,
		"allow_on_submit": 1,
		"module": MODULE,
	}


def setup_project_controls():
	create_custom_fields(
		{
			"Projects Settings": [
				{
					"fieldname": "custom_project_rules_section",
					"label": "ضوابط إنشاء المشاريع",
					"fieldtype": "Section Break",
					"insert_after": "fetch_timesheet_in_sales_invoice",
					"module": MODULE,
				},
				{
					"fieldname": "custom_enforce_project_rules",
					"label": "تفعيل ضوابط إنشاء المشاريع",
					"fieldtype": "Check",
					"insert_after": "custom_project_rules_section",
					"description": "مشروع جديد يحتاج أمر بيع معتمد (غير ملحق) مدفوع عليه الدفعة المقدمة المطلوبة، وأمر البيع لا يُعتمد قبل تحديد الدفعة المقدمة.",
					"module": MODULE,
				},
				{
					"fieldname": "custom_project_creator_role",
					"label": "الدور المسموح له بإنشاء المشاريع",
					"fieldtype": "Link",
					"options": "Role",
					"insert_after": "custom_enforce_project_rules",
					"description": "لو فارغ، كل من له صلاحية إنشاء مشروع يقدر ينشئ بالشروط.",
					"module": MODULE,
				},
				{
					"fieldname": "custom_project_exception_role",
					"label": "دور الاستثناء من الضوابط",
					"fieldtype": "Link",
					"options": "Role",
					"insert_after": "custom_project_creator_role",
					"description": "ينشئ مشروعاً بدون عقد أو بدون الدفعة المقدمة بسبب مكتوب، ويعدّل الدفعة المقدمة على أمر بيع معتمد.",
					"module": MODULE,
				},
			],
			"Project": [
				{
					"fieldname": "custom_project_exception_reason",
					"label": "سبب الاستثناء",
					"fieldtype": "Small Text",
					"insert_after": "sales_order",
					"hidden": 1,
					"no_copy": 1,
					"module": MODULE,
				},
			],
			"Quotation": [
				{
					"fieldname": "custom_advance_section",
					"label": "الدفعة المقدمة",
					"fieldtype": "Section Break",
					"insert_after": "in_words",
					"module": MODULE,
				},
				*advance_fields("custom_advance_section"),
				{
					"fieldname": "custom_advance_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_advance_amount",
					"module": MODULE,
				},
				required_field("custom_advance_column"),
			],
			# Beside the standard "Advance Paid", so the agreed and the paid sit together.
			"Sales Order": [
				required_field("advance_paid"),
				{
					"fieldname": "custom_advance_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_advance_required",
					"module": MODULE,
				},
				*advance_fields("custom_advance_column", allow_on_submit=1),
			],
		},
		update=True,
	)
