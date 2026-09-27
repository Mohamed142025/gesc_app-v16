# Copyright (c) 2026, mohamed sayed and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PrivateCommentSettings(Document):
	def validate(self):
		seen = set()
		for row in self.document_types:
			if row.document_type in seen:
				frappe.throw(_("نوع المستند {0} مكرر.").format(row.document_type))
			seen.add(row.document_type)
			meta = frappe.get_meta(row.document_type)
			if meta.istable or meta.issingle:
				frappe.throw(_("{0} لا يصلح: اختر مستنداً له شاشة عادية.").format(row.document_type))

	def on_update(self):
		from gesc_app.gesc_app.private_comments import clear_cache

		clear_cache()
