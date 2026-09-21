import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)
from frappe.desk.doctype.notification_settings.notification_settings import is_notifications_enabled


IGNORED_DOCTYPES = {"Notification Log", "ToDo"}


def notify_assignees_on_update(doc, method=None):
	if doc.doctype in IGNORED_DOCTYPES or not doc.name or not frappe.db.exists(doc.doctype, doc.name):
		return

	assignees = frappe.get_all(
		"ToDo",
		filters={
			"reference_type": doc.doctype,
			"reference_name": str(doc.name),
			"status": ("not in", ("Cancelled", "Closed")),
			"allocated_to": ("is", "set"),
		},
		pluck="allocated_to",
	)
	if not assignees:
		return

	users = frappe.get_all(
		"User",
		filters={"name": ("in", list(set(assignees))), "enabled": 1},
		fields=["name", "email"],
	)
	emails = [user.email for user in users if user.email and is_notifications_enabled(user.name)]
	if not emails:
		return

	document_title = get_title(doc.doctype, doc.name)
	subject = _("{0} was updated: {1} {2}").format(
		frappe.bold(frappe.session.user),
		frappe.bold(_(doc.doctype)),
		get_title_html(document_title),
	)

	enqueue_create_notification(
		emails,
		{
			"type": "Alert",
			"document_type": doc.doctype,
			"document_name": doc.name,
			"subject": subject,
			"from_user": frappe.session.user,
			"email_header": _("Document Updated"),
		},
	)


@frappe.whitelist()
def get_unread_notification_count():
	return frappe.db.count(
		"Notification Log",
		filters={"for_user": frappe.session.user, "read": 0},
	)