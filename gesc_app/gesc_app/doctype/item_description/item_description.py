import re

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class ItemDescription(Document):
	def before_validate(self):
		if self.item_code:
			self.item_name = frappe.db.get_value("Item", self.item_code, "item_name")

	def validate(self):
		if not self.item_code:
			frappe.throw("كود الصنف مطلوب لإنشاء التوصيف")

		if not self.description:
			frappe.throw("التوصيف مطلوب")

	def autoname(self):
		sequence = make_autoname("ITEM-DESCRIPTION-.###")
		sequence = sequence.rsplit("-", 1)[-1]
		self.name = "-".join(
			[
				self._name_part(self.description_name),
				self._name_part(self.item_name),
				sequence,
			]
		)

	@staticmethod
	def _name_part(value):
		value = re.sub(r"[\\/\s]+", "-", (value or "").strip())
		return re.sub(r"[^\w\-\u0600-\u06ff]", "", value, flags=re.UNICODE) or "ITEM"