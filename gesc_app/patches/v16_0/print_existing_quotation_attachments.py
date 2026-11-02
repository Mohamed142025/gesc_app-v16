"""Quotation attachments are printed only when ticked; those added before keep being printed."""

import frappe


def execute():
	frappe.db.set_value("Quotation Attachment", {"show_in_print": 0}, "show_in_print", 1, update_modified=False)
