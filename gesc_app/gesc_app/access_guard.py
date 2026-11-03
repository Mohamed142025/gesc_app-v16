"""Server-side guards for employee data (security audit of 2026-11-03).

The Employee role reads Salary Slips, Salary Structure Assignments, Attendance, Employee
Checkins and the app's notifications of every employee, as Frappe HR leaves their scoping
to User Permissions, which this site does not use. Here:

- Salary Slip and Salary Structure Assignment: an employee sees their own only.
- Attendance and Employee Checkin: their own, and those of the employees who report to
  them or whose requests they approve (approver fields on the employee, or the approvers
  of the employee's department).
- PWA Notification: the ones sent to them.
- Employee: its bank, salary, ID, health and private contact details are read and edited
  by HR only (permission level 1).

Whoever holds another role that reads the doctype (HR, System Manager, ...) is not limited.

Also guarded on the server, whatever the app sends:
- An employee checks in only themselves, and not as a biometric import; they no longer
  edit or delete check-ins.
- An employee advance's repayment schedule is HR's: not set on a draft, and its
  installments' status not changed by hand except by HR.
- No one approves or rejects their own Permission or Overtime Request (HR excepted).
- The app's push subscriptions go only to the browsers' push services, its client error
  log is rate limited, and the team card needs an employee.
"""

from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.permissions import add_permission, update_permission_property
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.rate_limiter import rate_limit

# Roles every employee holds: they do not widen what a user sees here.
EMPLOYEE_ROLES = {"Employee", "Employee Self Service", "All", "Guest", "Desk User"}
HR_ROLES = ("HR User", "HR Manager", "System Manager")

OWN_ONLY = ("Salary Slip", "Salary Structure Assignment")
TEAM = ("Attendance", "Employee Checkin")
NOTIFICATION = "PWA Notification"

# Approver fields on Employee, for TEAM (those the site has).
APPROVER_FIELDS = (
	"leave_approver",
	"expense_approver",
	"shift_request_approver",
	"custom_permission_approver",
	"custom_overtime_approver",
)

SENSITIVE_EMPLOYEE_FIELDS = (
	"ctc",
	"salary_currency",
	"salary_mode",
	"bank_name",
	"bank_ac_no",
	"iban",
	"passport_number",
	"valid_upto",
	"date_of_issue",
	"place_of_issue",
	"health_details",
	"health_insurance_provider",
	"health_insurance_no",
	"blood_group",
	"marital_status",
	"family_background",
	"personal_email",
	"current_address",
	"current_accommodation_type",
	"permanent_address",
	"permanent_accommodation_type",
	"person_to_be_contacted",
	"emergency_phone_number",
	"relation",
	"custom_checkin_device",
)

PUSH_HOSTS = (
	"fcm.googleapis.com",
	"android.googleapis.com",
	"push.services.mozilla.com",
	"notify.windows.com",
	"push.apple.com",
)

SCHEDULE = "custom_repayment_schedule"
SCHEDULE_FIELDS = ("payroll_date", "amount", "status", "additional_salary", "salary_slip", "note")
DECISIONS = ("Approved", "Rejected")


# Setup -----------------------------------------------------------------------------------


def setup():
	"""Employee's sensitive fields at level 1 for HR; Employee Checkin created, not edited,
	by employees."""
	meta = frappe.get_meta("Employee")
	for fieldname in SENSITIVE_EMPLOYEE_FIELDS:
		field = meta.get_field(fieldname)
		if field and field.permlevel != 1:
			make_property_setter("Employee", fieldname, "permlevel", 1, "Int", validate_fields_for_doctype=False)
	for role in HR_ROLES:
		_ensure_permission("Employee", role, 1, write=True)

	for row in frappe.get_all(
		"Custom DocPerm",
		filters={"parent": "Employee Checkin", "role": "Employee", "permlevel": 0},
		fields=["name", "write", "delete"],
	):
		if row.write or row.delete:
			frappe.db.set_value("Custom DocPerm", row.name, {"write": 0, "delete": 0})
	frappe.clear_cache(doctype="Employee")
	frappe.clear_cache(doctype="Employee Checkin")


def _ensure_permission(doctype, role, permlevel, write):
	if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": permlevel}):
		add_permission(doctype, role, permlevel)
	update_permission_property(doctype, role, permlevel, "read", 1, validate=False)
	if write:
		update_permission_property(doctype, role, permlevel, "write", 1, validate=False)


# Who is limited --------------------------------------------------------------------------


def _sees_all(user):
	if user == "Administrator":
		return True
	try:
		from ms_hrms.request_approvers import sees_all
	except ImportError:
		return "System Manager" in frappe.get_roles(user)
	return sees_all(user)


def _privileged(doctype, user):
	"""A user with a role beyond the employee's that reads the doctype."""
	if user == "Administrator":
		return True
	cache = getattr(frappe.local, "gesc_access_privileged", None)
	if cache is None:
		cache = frappe.local.gesc_access_privileged = {}
	key = (doctype, user)
	if key not in cache:
		readers = {p.role for p in frappe.get_meta(doctype).permissions if p.read and not p.permlevel}
		cache[key] = bool((readers - EMPLOYEE_ROLES) & set(frappe.get_roles(user))) or _sees_all(user)
	return cache[key]


def _own_employees(user):
	return f"select name from `tabEmployee` where user_id = {frappe.db.escape(user)}"


def _team_employees(user):
	value = frappe.db.escape(user)
	meta = frappe.get_meta("Employee")
	approver = " or ".join(f"`{f}` = {value}" for f in APPROVER_FIELDS if meta.has_field(f))
	queries = [
		_own_employees(user),
		f"""select employee.name from `tabEmployee` employee
		join `tabEmployee` manager on manager.name = employee.reports_to
		where manager.user_id = {value}""",
		f"""select employee.name from `tabEmployee` employee
		join `tabDepartment Approver` approver on approver.parent = employee.department
			and approver.parenttype = 'Department'
		where approver.approver = {value}""",
	]
	if approver:
		queries.append(f"select name from `tabEmployee` where {approver}")
	return " union ".join(queries)


# Permission hooks ------------------------------------------------------------------------


def _employee_condition(doctype, user, scope):
	user = user or frappe.session.user
	if _privileged(doctype, user):
		return ""
	return f"`tab{doctype}`.employee in ({scope(user)})"


def salary_slip_condition(user=None):
	return _employee_condition("Salary Slip", user, _own_employees)


def salary_structure_assignment_condition(user=None):
	return _employee_condition("Salary Structure Assignment", user, _own_employees)


def attendance_condition(user=None):
	return _employee_condition("Attendance", user, _team_employees)


def employee_checkin_condition(user=None):
	return _employee_condition("Employee Checkin", user, _team_employees)


def notification_condition(user=None):
	user = user or frappe.session.user
	if _privileged(NOTIFICATION, user):
		return ""
	return f"`tab{NOTIFICATION}`.to_user = {frappe.db.escape(user)}"


def has_employee_permission(doc, ptype=None, user=None, debug=False):
	"""Controller check for single documents of OWN_ONLY and TEAM. It only takes away."""
	user = user or frappe.session.user
	if _privileged(doc.doctype, user) or doc.is_new() or not doc.get("employee"):
		return True
	scope = _own_employees if doc.doctype in OWN_ONLY else _team_employees
	return bool(frappe.db.sql(f"select 1 from ({scope(user)}) e where e.name = %s", doc.employee))


def has_notification_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	return _privileged(NOTIFICATION, user) or doc.is_new() or doc.get("to_user") == user


# Employee Checkin ------------------------------------------------------------------------


def guard_checkin(doc, method=None):
	"""before_insert: an employee checks in themselves only, and not as an import. Server
	code inserting with ignore_permissions (approvals, imports by HR) is not limited."""
	if doc.flags.ignore_permissions or frappe.flags.in_import or frappe.flags.in_migrate:
		return
	user = frappe.session.user
	if _privileged("Employee Checkin", user):
		return
	if frappe.db.get_value("Employee", doc.employee, "user_id") != user:
		frappe.throw(_("لا يمكنك تسجيل بصمة لموظف آخر."), frappe.PermissionError)
	if doc.get("custom_biometric_import"):
		frappe.throw(_("تسجيل البصمة من التطبيق لا يكون استيراداً من جهاز البصمة."), frappe.PermissionError)


# Employee Advance ------------------------------------------------------------------------


def strip_draft_schedule(doc, method=None):
	"""validate / before_submit: the repayment plan is set by HR after approval, so a
	request does not bring its own."""
	if doc.flags.ms_hrms_repayment or not doc.meta.has_field(SCHEDULE) or not doc.get(SCHEDULE):
		return
	if doc.docstatus == 1 and method != "before_submit":
		return
	if _sees_all(frappe.session.user):
		return
	doc.set(SCHEDULE, [])
	for fieldname in (
		"custom_repaid_amount",
		"custom_repayment_balance",
		"custom_missed_installments",
		"custom_repayment_installment",
		"custom_repayment_months",
	):
		if doc.meta.has_field(fieldname):
			doc.set(fieldname, 0)
	if doc.meta.has_field("custom_repayment_start"):
		doc.custom_repayment_start = None


def guard_schedule(doc, method=None):
	"""before_update_after_submit: only HR, or the repayment code itself, changes the
	installments (their status included)."""
	if doc.flags.ms_hrms_repayment or not doc.meta.has_field(SCHEDULE) or _sees_all(frappe.session.user):
		return
	before = doc.get_doc_before_save()
	if not before:
		return

	def rows(d):
		return {
			row.name: tuple(str(row.get(f) or "") for f in SCHEDULE_FIELDS) for row in d.get(SCHEDULE) or []
		}

	if rows(doc) != rows(before):
		frappe.throw(_("جدول سداد السلفة يعدّله قسم الموارد البشرية فقط."), frappe.PermissionError)


# Permission and Overtime Requests --------------------------------------------------------


def no_self_decision(doc, method=None):
	"""validate: the employee does not approve or reject their own request."""
	if doc.is_new() or doc.status not in DECISIONS or not doc.has_value_changed("status"):
		return
	user = frappe.session.user
	if _sees_all(user):
		return
	if frappe.db.get_value("Employee", doc.employee, "user_id") == user:
		frappe.throw(_("لا يمكنك اعتماد أو رفض طلبك بنفسك."), frappe.PermissionError)


# The employee app's methods (override_whitelisted_methods) --------------------------------


@frappe.whitelist(methods=["POST"])
def subscribe(subscription, device=None, quiet=False):
	"""ms_hrms.web_push.subscribe, for the browsers' push services only: the site posts
	to the endpoint it is given."""
	from ms_hrms.web_push import subscribe as _subscribe

	data = frappe.parse_json(subscription) if isinstance(subscription, str) else subscription
	endpoint = urlparse((data or {}).get("endpoint") or "")
	host = (endpoint.hostname or "").lower()
	if endpoint.scheme != "https" or not any(host == h or host.endswith("." + h) for h in PUSH_HOSTS):
		frappe.throw(_("عنوان الإشعارات غير مقبول."), frappe.ValidationError)
	return _subscribe(subscription, device=device, quiet=quiet)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60)
def log_client_error(error):
	from ms_hrms.web_push import log_client_error as _log_client_error

	return _log_client_error(error)


@frappe.whitelist()
def get_team_today():
	"""ms_hrms.pwa_api.get_team_today for employees only: a user with no employee has no
	team."""
	from ms_hrms.pwa_api import get_team_today as _get_team_today

	if not frappe.db.exists("Employee", {"user_id": frappe.session.user, "status": "Active"}):
		return {"size": 0}
	return _get_team_today()
