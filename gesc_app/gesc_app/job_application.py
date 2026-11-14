"""The job application form on the website (HRMS's "job-application" Web Form) and the
applicant's details it collects.

The applicant gives their name, date of birth, qualification, address, phone, email, last
and expected salary, and their CV, which the form requires. The age is worked out from the
date of birth, as of the application, so the applicant is not asked for it twice.

The form is HRMS's and is synced from its files on migrate, so it is set up again after
every migrate (after_migrate). What the form requires is checked again on the server, for
whatever is sent through it; applicants added by HR in the desk are not held to it.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import date_diff, getdate, nowdate

MODULE = "Gesc App"
WEB_FORM = "job-application"
QUALIFICATIONS = (
	"مؤهل متوسط / Intermediate Diploma",
	"مؤهل فوق متوسط / Higher Diploma",
	"بكالوريوس أو ليسانس / Bachelor's",
	"ماجستير / Master's",
	"دكتوراه / PhD",
	"أخرى / Other",
)
MIN_AGE, MAX_AGE = 16, 75

INTRODUCTION = """<div dir="rtl" style="text-align:right">
<p>املأ بياناتك وارفع <b>سيرتك الذاتية (CV)</b> في آخر الصفحة. <b>الطلب لا يُقبل بدون السيرة الذاتية.</b></p>
</div>
<div dir="ltr" style="text-align:left">
<p>Fill in your details and upload your <b>CV</b> at the end of the form. <b>Applications without a CV are not accepted.</b></p>
</div>"""
SUCCESS = "شكراً لتقديمك، سنتواصل معك. / Thank you for applying, we will be in touch."

# (fieldname, label, required, description); a None fieldname starts a section.
FORM_FIELDS = (
	("job_title", "الوظيفة / Job Opening", 0, None),
	(None, "البيانات الشخصية / Personal Details", 0, None),
	("applicant_name", "الاسم بالكامل / Full Name", 1, None),
	("custom_date_of_birth", "تاريخ الميلاد / Date of Birth", 1, None),
	("custom_qualification", "المؤهل الدراسي / Qualification", 1, None),
	("custom_specialization", "التخصص / Specialization", 0, "مثال: هندسة مدني / e.g. Civil Engineering"),
	("custom_address", "العنوان / Address", 1, None),
	(None, "بيانات التواصل / Contact", 0, None),
	("phone_number", "رقم التليفون / Phone Number", 1, None),
	("email_id", "البريد الإلكتروني / Email", 1, None),
	(None, "الراتب / Salary", 0, None),
	("custom_last_salary", "آخر راتب / Last Salary", 0, "اتركه فارغاً إن لم تعمل من قبل / Leave empty if you have not worked before"),
	("custom_expected_salary", "الراتب المتوقع / Expected Salary", 1, None),
	(None, "السيرة الذاتية / CV", 0, None),
	(
		"resume_attachment",
		"السيرة الذاتية (CV) / Resume",
		1,
		"ارفع ملف السيرة الذاتية (PDF أو Word) — إجباري / Upload your CV (PDF or Word) — required",
	),
)


def setup():
	create_custom_fields(
		{
			"Job Applicant": [
				{
					"fieldname": "custom_personal_section",
					"label": "البيانات الشخصية",
					"fieldtype": "Section Break",
					"insert_after": "applicant_rating",
					"module": MODULE,
				},
				{
					"fieldname": "custom_date_of_birth",
					"label": "تاريخ الميلاد",
					"fieldtype": "Date",
					"insert_after": "custom_personal_section",
					"module": MODULE,
				},
				{
					"fieldname": "custom_age",
					"label": "السن عند التقديم",
					"fieldtype": "Int",
					"insert_after": "custom_date_of_birth",
					"read_only": 1,
					"in_list_view": 1,
					"description": "يُحسب من تاريخ الميلاد.",
					"module": MODULE,
				},
				{
					"fieldname": "custom_qualification",
					"label": "المؤهل الدراسي",
					"fieldtype": "Select",
					"options": "\n" + "\n".join(QUALIFICATIONS),
					"insert_after": "custom_age",
					"in_list_view": 1,
					"in_standard_filter": 1,
					"module": MODULE,
				},
				{
					"fieldname": "custom_specialization",
					"label": "التخصص",
					"fieldtype": "Data",
					"insert_after": "custom_qualification",
					"module": MODULE,
				},
				{
					"fieldname": "custom_personal_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_specialization",
					"module": MODULE,
				},
				{
					"fieldname": "custom_address",
					"label": "العنوان",
					"fieldtype": "Small Text",
					"insert_after": "custom_personal_column",
					"module": MODULE,
				},
				{
					"fieldname": "custom_last_salary",
					"label": "آخر راتب",
					"fieldtype": "Currency",
					"insert_after": "custom_address",
					"module": MODULE,
				},
				{
					"fieldname": "custom_expected_salary",
					"label": "الراتب المتوقع",
					"fieldtype": "Currency",
					"insert_after": "custom_last_salary",
					"in_list_view": 1,
					"module": MODULE,
				},
			]
		},
		update=True,
	)
	setup_web_form()


def setup_web_form():
	if not frappe.db.exists("Web Form", WEB_FORM):
		return
	form = frappe.get_doc("Web Form", WEB_FORM)
	meta = frappe.get_meta(form.doc_type)
	wanted = []
	for fieldname, label, reqd, description in FORM_FIELDS:
		if not fieldname:
			wanted.append({"fieldtype": "Section Break", "label": label})
			continue
		df = meta.get_field(fieldname)
		wanted.append(
			{
				"fieldname": fieldname,
				# The opening comes filled in from the jobs page, as text: HRMS's own choice,
				# so a visitor is not asked to pick from the openings.
				"fieldtype": "Data" if fieldname == "job_title" else df.fieldtype,
				"label": label,
				"reqd": reqd,
				"options": "Email" if fieldname == "email_id" else ("Phone" if fieldname == "phone_number" else df.options),
				"description": description,
				"read_only": 1 if fieldname == "job_title" else 0,
			}
		)

	def shape(rows):
		keys = ("fieldname", "fieldtype", "label", "reqd", "options", "description", "read_only")
		return [tuple((row.get(k) or None) if k not in ("reqd", "read_only") else int(row.get(k) or 0) for k in keys) for row in rows]

	if (
		shape(form.web_form_fields) == shape(wanted)
		and form.introduction_text == INTRODUCTION
		and form.success_message == SUCCESS
	):
		return
	form.set("web_form_fields", wanted)
	form.introduction_text = INTRODUCTION
	form.success_message = SUCCESS
	# A standard Web Form is otherwise edited in developer mode only.
	in_patch = frappe.flags.in_patch
	frappe.flags.in_patch = True
	try:
		form.save(ignore_permissions=True)
	finally:
		frappe.flags.in_patch = in_patch


# Job Applicant hook -------------------------------------------------------------------


def validate(doc, method=None):
	if doc.custom_date_of_birth:
		born = getdate(doc.custom_date_of_birth)
		applied = getdate(doc.creation or nowdate())
		age = _years(born, applied)
		if born > applied or not MIN_AGE <= age <= MAX_AGE:
			frappe.throw(_("تاريخ الميلاد غير صحيح. / Please check the date of birth."))
		doc.custom_age = age
	else:
		doc.custom_age = 0

	if doc.is_new() and frappe.form_dict.get("web_form") == WEB_FORM:
		_check_web_submission(doc)


def _years(born, on):
	return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def _check_web_submission(doc):
	"""What the form requires, for whatever is sent through it. The CV may still be on its
	way: the form saves an uploaded file only after the applicant is created."""
	data = frappe.form_dict.get("data")
	data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
	# The form's own required fields, as it stands on this site.
	required = frappe.get_all(
		"Web Form Field",
		filters={"parent": WEB_FORM, "parenttype": "Web Form", "reqd": 1, "fieldname": ("is", "set")},
		fields=["fieldname", "label"],
		order_by="idx",
	)
	missing = [row.label for row in required if not (doc.get(row.fieldname) or data.get(row.fieldname))]
	if missing:
		frappe.throw(
			_("أكمل البيانات المطلوبة: {0} / Please complete: {0}").format("، ".join(missing)),
			title=_("بيانات ناقصة / Missing details"),
		)
