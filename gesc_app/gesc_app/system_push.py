"""The system's notifications (Notification Log: alerts, assignments, mentions, shares…) pushed
to the devices of their user, as the HR app's own notifications are (ms_hrms.web_push).

Devices subscribe once from the HR app's settings; the push opens the document in the desk.
A document that also made an HR app notification for the same user (pushed by ms_hrms) is
not pushed twice.
"""

from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import add_to_date, get_url_to_form, now_datetime

# An HR app notification about the same document made this recently is the same event.
SAME_EVENT_MINUTES = 5


def on_notification_log(doc, method=None):
	"""Notification Log after insert: push it to its user's devices, after the commit."""
	if not doc.for_user or not frappe.db.exists("Push Subscription", {"user": doc.for_user}):
		return
	frappe.enqueue(push, queue="short", enqueue_after_commit=True, notification=doc.name)


def push(notification):
	from ms_hrms.web_push import _as_text, get_app_title, send_to_user

	doc = frappe.get_doc("Notification Log", notification)
	if pushed_by_hr_app(doc):
		return
	lang = frappe.db.get_value("User", doc.for_user, "language") or frappe.db.get_default("lang")
	title = _(doc.document_type, lang=lang) if doc.document_type else get_app_title()
	send_to_user(doc.for_user, title=title, body=_as_text(doc.subject), url=get_route(doc), tag=doc.name)


def pushed_by_hr_app(doc):
	if not (doc.document_type and doc.document_name):
		return False
	return frappe.db.exists(
		"PWA Notification",
		{
			"to_user": doc.for_user,
			"reference_document_type": doc.document_type,
			"reference_document_name": doc.document_name,
			"creation": (">=", add_to_date(now_datetime(), minutes=-SAME_EVENT_MINUTES)),
		},
	)


def get_route(doc):
	"""Where the push opens: the notification's own link, or its document in the desk; a
	path on the site, so it opens in the app."""
	if doc.link:
		url = urlparse(doc.link)
		return url.path + (f"?{url.query}" if url.query else "") if url.netloc else doc.link
	if doc.document_type and doc.document_name:
		return urlparse(get_url_to_form(doc.document_type, doc.document_name)).path
	return "/desk"
