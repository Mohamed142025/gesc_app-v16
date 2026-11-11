"""gesc_app's reports in ERPNext's "Financial Reports" sidebar.

The sidebar is ERPNext's and is synced from its files on migrate, so the links are added
again after every migrate (after_migrate), each once, after the item named for it.
"""

import frappe

SIDEBAR = "Financial Reports"
# (report, label, the report it follows)
REPORTS = (
	("كشف حساب", "كشف حساب", "Supplier Ledger Summary"),
	("الموقف المالي للعقود", "الموقف المالي للعقود", "Accounts Receivable Summary"),
)


def setup():
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR):
		return
	sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR)
	changed = False
	for report, label, after in REPORTS:
		if not frappe.db.exists("Report", report):
			continue
		if any(item.link_type == "Report" and item.link_to == report for item in sidebar.items):
			continue
		items = list(sidebar.items)
		position = next(
			(i + 1 for i, item in enumerate(items) if item.link_to == after),
			len(items),
		)
		row = sidebar.append(
			"items", {"label": label, "type": "Link", "link_type": "Report", "link_to": report, "child": 1}
		)
		items.insert(position, row)
		for idx, item in enumerate(items, 1):
			item.idx = idx
		sidebar.items = items
		changed = True
	if changed:
		sidebar.flags.ignore_permissions = True
		sidebar.save()
