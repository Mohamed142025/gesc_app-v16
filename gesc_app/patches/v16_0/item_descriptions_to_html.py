"""The item description became a text editor (Item Description, Task Execution Item);
plain text written before keeps its lines as paragraphs."""

import frappe
from frappe.utils import escape_html, is_html


def execute():
	for doctype in ("Item Description", "Task Execution Item"):
		for name, text in frappe.get_all(
			doctype, filters={"description": ("is", "set")}, fields=["name", "description"], as_list=True
		):
			if is_html(text):
				continue
			html = "".join(f"<p>{escape_html(line) or '<br>'}</p>" for line in text.strip().splitlines())
			frappe.db.set_value(doctype, name, "description", html, update_modified=False)
