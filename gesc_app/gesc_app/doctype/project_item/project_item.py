# Copyright (c) 2026, mohamed sayed and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gesc_app.gesc_app.progress_utils import get_contract_values, update_project_item_progress


class ProjectItem(Document):
	def validate(self):
		self.validate_unique_item_per_project()

		quantity, supply_weight, install_weight = get_contract_values(self.project, self.item)
		self.quantity = quantity
		self.supply_weight_percent = supply_weight
		self.installation_weight_percent = install_weight

	def validate_unique_item_per_project(self):
		# Work Completion Notes resolve البند from (project, item) automatically,
		# so this pair must stay unique - two بنود for the same item would make
		# that lookup ambiguous.
		duplicate = frappe.db.exists(
			"Project Item", {"project": self.project, "item": self.item, "name": ["!=", self.name]}
		)
		if duplicate:
			frappe.throw(
				_("A البند for item {0} already exists in this project ({1}).").format(
					self.item, duplicate
				)
			)

	def on_update(self):
		update_project_item_progress(self.name)
