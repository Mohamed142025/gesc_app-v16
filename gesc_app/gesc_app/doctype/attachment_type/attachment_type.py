# Copyright (c) 2026, mohamed sayed and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class AttachmentType(Document):
	def validate(self):
		self.attachment_type_name = (self.attachment_type_name or "").strip()
