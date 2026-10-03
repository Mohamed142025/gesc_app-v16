# Copyright (c) 2026, mohamed sayed and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gesc_app.gesc_app.progress_utils import get_contract_values, update_project_item_progress


class ProjectItem(Document):
	def validate(self):
		self.validate_item_description()
		self.validate_unique_item_per_project()

		quantity, supply_weight, install_weight = get_contract_values(self.project, self.item, self.item_description)
		self.quantity = quantity
		self.supply_weight_percent = supply_weight
		self.installation_weight_percent = install_weight

	def validate_item_description(self):
		if not self.item_description:
			self.item_description_text = None
			return
		item_code = frappe.db.get_value("Item Description", self.item_description, "item_code")
		if item_code != self.item:
			frappe.throw(
				_("توصيف البند {0} ليس للصنف {1}.").format(frappe.bold(self.item_description), frappe.bold(self.item))
			)

	def validate_unique_item_per_project(self):
		# Work Completion Notes resolve البند from (project, item, item description)
		# automatically, so this combination must stay unique - two بنود for the
		# same item and description would make that lookup ambiguous.
		duplicate = frappe.db.exists(
			"Project Item",
			{
				"project": self.project,
				"item": self.item,
				"item_description": self.item_description or ("is", "not set"),
				"name": ["!=", self.name],
			},
		)
		if duplicate:
			frappe.throw(
				_("يوجد بالفعل بند للصنف {0} بنفس التوصيف في هذا المشروع ({1}).").format(
					frappe.bold(self.item), duplicate
				)
			)

	def on_update(self):
		update_project_item_progress(self.name)
