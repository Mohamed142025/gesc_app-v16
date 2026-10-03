"""Private comments: a comment on a document for one or more people, seen only by them and
its writer.

The document types come from Private Comment Settings. The comments live in their own
doctype, which no role can read; everything goes through the functions here, which check
the participants. They show in the document's timeline through Frappe's
additional_timeline_content hook, computed per user, so the other readers of the
document never see them. Replies stay in the same conversation among its participants.

Files sent with a comment are private files attached to the comment, not to the document,
so they are not among the document's attachments; each is shared with the other
participants, who alone can open it with its writer.
"""

import frappe
from frappe import _
from frappe.utils import cstr, escape_html, get_fullname, now_datetime, pretty_date

CACHE_KEY = "gesc_private_comment_doctypes"
MAX_LENGTH = 5000
MAX_FILES = 10


# Settings -----------------------------------------------------------------------------


def get_enabled_doctypes():
	doctypes = frappe.cache.get_value(CACHE_KEY)
	if doctypes is None:
		settings = frappe.get_cached_doc("Private Comment Settings")
		doctypes = [row.document_type for row in settings.document_types] if settings.enabled else []
		frappe.cache.set_value(CACHE_KEY, doctypes)
	return doctypes


def clear_cache():
	frappe.cache.delete_value(CACHE_KEY)
	frappe.clear_document_cache("Private Comment Settings", "Private Comment Settings")


def boot_session(bootinfo):
	bootinfo.private_comment_doctypes = get_enabled_doctypes() if frappe.session.user != "Guest" else []


def setup_private_comments():
	"""First run: on, for Task. Once the settings have been saved, they are left alone."""
	# Singles has no name column, so frappe.db.exists() cannot look it up.
	if frappe.db.sql("select 1 from `tabSingles` where doctype = %s limit 1", "Private Comment Settings"):
		return
	settings = frappe.get_single("Private Comment Settings")
	settings.enabled = 1
	settings.append("document_types", {"document_type": "Task"})
	settings.save(ignore_permissions=True)


# Actions ------------------------------------------------------------------------------


@frappe.whitelist()
def add(reference_doctype, reference_name, content, recipients=None, reply_to=None, files=None):
	content = cstr(content).strip()
	if not content:
		frappe.throw(_("اكتب نص التعليق."))
	if len(content) > MAX_LENGTH:
		frappe.throw(_("التعليق أطول من {0} حرف.").format(MAX_LENGTH))
	files = _valid_files(frappe.parse_json(files) if isinstance(files, str) else files)

	user = frappe.session.user
	if reply_to:
		thread = _get_thread(reply_to)
		reference_doctype, reference_name = thread.reference_doctype, thread.reference_name
		_check_enabled(reference_doctype)
		participants = _participants(thread)
		if user not in participants:
			frappe.throw(_("الرد متاح لأطراف هذا التعليق الخاص فقط."), frappe.PermissionError)
		to = [p for p in participants if p != user]
		thread_name = thread.name
	else:
		_check_enabled(reference_doctype)
		if not frappe.has_permission(reference_doctype, "read", doc=reference_name):
			frappe.throw(_("ليس لديك صلاحية على هذا المستند."), frappe.PermissionError)
		to = _valid_recipients(frappe.parse_json(recipients) if isinstance(recipients, str) else recipients, user)
		thread_name = None

	comment = frappe.get_doc(
		{
			"doctype": "Private Comment",
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"thread": thread_name,
			"content": content,
			"recipients": [{"user": u} for u in to],
		}
	).insert(ignore_permissions=True)

	_attach_files(comment, files, to)
	_share_with(reference_doctype, reference_name, to)
	_notify(comment, to, is_reply=bool(reply_to))
	return comment.name


@frappe.whitelist()
def delete(name):
	comment = frappe.get_doc("Private Comment", name)
	if comment.owner != frappe.session.user:
		frappe.throw(_("يحذف التعليق كاتبه فقط."), frappe.PermissionError)
	names = [comment.name]
	if not comment.thread:
		names += frappe.get_all("Private Comment", {"thread": comment.name}, pluck="name")
	# Deleting a comment deletes its files, but not the shares that opened them to the others.
	files = frappe.get_all(
		"File", {"attached_to_doctype": "Private Comment", "attached_to_name": ["in", names]}, pluck="name"
	)
	if files:
		frappe.db.delete("DocShare", {"share_doctype": "File", "share_name": ["in", files]})
	for name in reversed(names):
		frappe.delete_doc("Private Comment", name, ignore_permissions=True, delete_permanently=True)


@frappe.whitelist()
def mark_read(reference_doctype, reference_name):
	"""The current user has seen their private comments on this document."""
	recipient = frappe.qb.DocType("Private Comment Recipient")
	comment = frappe.qb.DocType("Private Comment")
	rows = (
		frappe.qb.from_(recipient)
		.join(comment)
		.on(comment.name == recipient.parent)
		.select(recipient.name)
		.where(
			(comment.reference_doctype == reference_doctype)
			& (comment.reference_name == reference_name)
			& (recipient.user == frappe.session.user)
			& recipient.read_on.isnull()
		)
		.run(pluck=True)
	)
	now = now_datetime()
	for row in rows:
		frappe.db.set_value("Private Comment Recipient", row, "read_on", now, update_modified=False)
	return len(rows)


@frappe.whitelist()
def search_users(txt=""):
	"""Active desk users, for choosing recipients."""
	txt = f"%{cstr(txt).strip()}%"
	return frappe.get_all(
		"User",
		filters=[
			["enabled", "=", 1],
			["user_type", "=", "System User"],
			["name", "not in", ["Administrator", "Guest", frappe.session.user]],
		],
		or_filters=[["name", "like", txt], ["full_name", "like", txt]],
		fields=["name as value", "full_name as description"],
		limit=20,
		order_by="full_name asc",
		ignore_permissions=True,
	)


# Timeline -----------------------------------------------------------------------------


def timeline(doctype, docname):
	"""One card per conversation the current user takes part in; nothing for anyone else."""
	if doctype not in get_enabled_doctypes():
		return []

	user = frappe.session.user
	comments = frappe.db.sql(
		"""
		select pc.name, pc.owner, pc.creation, pc.content, pc.thread
		from `tabPrivate Comment` pc
		where pc.reference_doctype = %(doctype)s and pc.reference_name = %(name)s
			and (pc.owner = %(user)s or exists (
				select 1 from `tabPrivate Comment Recipient` r where r.parent = pc.name and r.user = %(user)s))
		order by pc.creation asc
		""",
		{"doctype": doctype, "name": docname, "user": user},
		as_dict=True,
	)
	if not comments:
		return []

	recipients = {}
	for row in frappe.get_all(
		"Private Comment Recipient",
		filters={"parent": ["in", [c.name for c in comments]], "parenttype": "Private Comment"},
		fields=["parent", "user", "read_on"],
		order_by="idx asc",
	):
		recipients.setdefault(row.parent, []).append(row)

	files = {}
	for row in frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Private Comment", "attached_to_name": ["in", [c.name for c in comments]]},
		fields=["attached_to_name", "file_name", "file_url"],
		order_by="creation asc",
	):
		files.setdefault(row.attached_to_name, []).append(row)

	threads = {}
	for comment in comments:
		comment.recipients = recipients.get(comment.name, [])
		comment.files = files.get(comment.name, [])
		threads.setdefault(comment.thread or comment.name, []).append(comment)

	items = []
	for root_name, messages in threads.items():
		root = messages[0]
		unread = any(r.user == user and not r.read_on for m in messages for r in m.recipients)
		items.append(
			{
				"icon": "es-line-lock",
				"is_card": True,
				"creation": messages[-1].creation,
				"content": _render_thread(root_name, root, messages, user, unread),
				"private_comment_unread": 1 if unread else 0,
			}
		)
	return items


def _render_thread(root_name, root, messages, user, unread):
	people = [root.owner] + [r.user for r in root.recipients]
	names = "، ".join(escape_html(get_fullname(p)) for p in people)
	parts = [
		'<div class="private-comment" dir="auto">',
		'<div class="private-comment-head" style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:8px">',
		f'<span class="indicator-pill orange">🔒 {escape_html(_("خاص"))}</span>',
		f'<span class="text-muted small">{escape_html(_("يظهر فقط لـ"))}: {names}</span>',
	]
	if unread:
		parts.append(f'<span class="indicator-pill blue">{escape_html(_("جديد"))}</span>')
	parts.append("</div>")

	for message in messages:
		text = escape_html(message.content).replace("\n", "<br>")
		parts.append(
			'<div class="private-comment-message" style="padding:8px 0;border-top:1px solid var(--border-color)">'
			f'<div class="small"><b>{escape_html(get_fullname(message.owner))}</b> · '
			f'<span class="frappe-timestamp" data-timestamp="{message.creation}">{escape_html(pretty_date(message.creation))}</span>'
		)
		if message.owner == user:
			parts.append(
				f' · <a href="#" class="text-muted" data-private-delete="{message.name}">{escape_html(_("حذف"))}</a>'
			)
		parts.append(f'</div><div style="margin-top:4px;white-space:normal">{text}</div>')
		if message.files:
			links = "".join(
				f'<a href="{escape_html(f.file_url)}" target="_blank" rel="noopener" class="btn btn-xs btn-default" '
				f'style="margin:4px 4px 0 0">📎 {escape_html(f.file_name)}</a>'
				for f in message.files
			)
			parts.append(f'<div style="margin-top:4px">{links}</div>')
		if message.owner == user and message.recipients:
			read = [
				f'{escape_html(get_fullname(r.user))} ✓' if r.read_on else f'<span class="text-muted">{escape_html(get_fullname(r.user))}</span>'
				for r in message.recipients
			]
			parts.append(f'<div class="small text-muted" style="margin-top:4px">{escape_html(_("قرأه"))}: {"، ".join(read)}</div>')
		parts.append("</div>")

	parts.append(
		f'<div style="margin-top:6px"><button class="btn btn-xs btn-default" data-private-reply="{root_name}">'
		f'{escape_html(_("رد خاص"))}</button></div></div>'
	)
	return "".join(parts)


# Helpers ------------------------------------------------------------------------------


def _check_enabled(doctype):
	if doctype not in get_enabled_doctypes():
		frappe.throw(_("التعليقات الخاصة غير مفعّلة على {0}.").format(_(doctype)))


def _get_thread(name):
	comment = frappe.get_doc("Private Comment", name)
	return frappe.get_doc("Private Comment", comment.thread) if comment.thread else comment


def _participants(root):
	return [root.owner] + [r.user for r in root.recipients]


def _valid_recipients(users, author):
	users = [u for u in dict.fromkeys(users or []) if u and u != author]
	if not users:
		frappe.throw(_("اختر شخصاً واحداً على الأقل."))
	valid = set(
		frappe.get_all(
			"User",
			filters=[["name", "in", users], ["enabled", "=", 1], ["user_type", "=", "System User"]],
			pluck="name",
		)
	)
	invalid = [u for u in users if u not in valid]
	if invalid:
		frappe.throw(_("مستخدمون غير متاحين: {0}").format(", ".join(invalid)))
	return users


def _valid_files(names):
	"""Files the writer has just uploaded for this comment: their own, private, and not
	attached to anything yet."""
	names = [n for n in dict.fromkeys(names or []) if n]
	if len(names) > MAX_FILES:
		frappe.throw(_("أقصى عدد للمرفقات في التعليق الواحد {0}.").format(MAX_FILES))
	files = []
	for name in names:
		file = frappe.db.get_value(
			"File", name, ["name", "owner", "is_private", "is_folder", "attached_to_doctype"], as_dict=True
		)
		if (
			not file
			or file.is_folder
			or file.owner != frappe.session.user
			or not file.is_private
			or file.attached_to_doctype
		):
			frappe.throw(_("المرفق غير متاح. ارفع الملف من جديد داخل التعليق الخاص."))
		files.append(file.name)
	return files


def _attach_files(comment, files, users):
	"""The files belong to the comment, and the other participants may open them."""
	from frappe.share import add_docshare

	for name in files:
		frappe.db.set_value(
			"File",
			name,
			{"attached_to_doctype": comment.doctype, "attached_to_name": comment.name},
			update_modified=False,
		)
		for user in users:
			add_docshare("File", name, user, read=1, notify=0, flags={"ignore_share_permission": True})


def _share_with(doctype, name, users):
	"""A recipient who cannot open the document gets read access to it."""
	from frappe.share import add_docshare

	for user in users:
		if not frappe.has_permission(doctype, "read", doc=name, user=user):
			add_docshare(doctype, name, user, read=1, flags={"ignore_share_permission": True})


def _notify(comment, users, is_reply):
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	if not users:
		return
	author = get_fullname(frappe.session.user)
	count = frappe.db.count("File", {"attached_to_doctype": comment.doctype, "attached_to_name": comment.name})
	attachments_note = f"<br><br>📎 {escape_html(_('مرفقات: {0}').format(count))}" if count else ""
	for user in users:
		others = [get_fullname(u) for u in [comment.owner] + [r.user for r in comment.recipients] if u not in (user, frappe.session.user)]
		audience = _("لك") if not others else _("لك ولـ {0}").format("، ".join(others))
		subject = (
			_("🔒 رد خاص من {0} على {1} {2}، يظهر {3} فقط.")
			if is_reply
			else _("🔒 تعليق خاص من {0} على {1} {2}، يظهر {3} فقط.")
		).format(escape_html(author), _(comment.reference_doctype), comment.reference_name, audience)
		enqueue_create_notification(
			user,
			{
				"type": "Alert",
				"document_type": comment.reference_doctype,
				"document_name": comment.reference_name,
				"subject": subject,
				"email_content": escape_html(comment.content).replace("\n", "<br>") + attachments_note,
				"from_user": frappe.session.user,
			},
		)
