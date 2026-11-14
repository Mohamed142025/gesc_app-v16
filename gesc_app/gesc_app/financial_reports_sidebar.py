"""gesc_app's reports in the financial sidebars: ERPNext's "Financial Reports" and the
financial auditor's "المراجع المالي".

ERPNext's sidebar is synced from its files on migrate, so the links are added again after
every migrate (after_migrate), each once, after the item named for it. A sidebar the site
does not have is skipped.
"""

import frappe

# Sidebar: (report, label, the item it follows)
SIDEBARS = {
	"Financial Reports": (
		("كشف حساب", "كشف حساب", "Supplier Ledger Summary"),
		("الموقف المالي للعقود", "الموقف المالي للعقود", "Accounts Receivable Summary"),
	),
	"المراجع المالي": (
		("كشف حساب", "كشف حساب", "General Ledger"),
		("الموقف المالي للعقود", "الموقف المالي للعقود", "Accounts Receivable"),
	),
}


def setup():
	for sidebar, reports in SIDEBARS.items():
		if frappe.db.exists("Workspace Sidebar", sidebar):
			add_reports(sidebar, reports)


def add_reports(name, reports):
	sidebar = frappe.get_doc("Workspace Sidebar", name)
	changed = False
	for report, label, after in reports:
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
