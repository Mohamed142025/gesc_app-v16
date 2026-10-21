"""The project's name next to every project field.

Every document type and child table with a link to Project gets a read-only "اسم المشروع
المرتبط" right after it, fetched from the project's name. The fields are made after every
migrate, so a document type that gains a project field later gets one too; when a field is
made, the documents already there are filled.

When a project's name changes, every document and row linked to it is updated, submitted
ones included.

The ledgers (GL, payment and stock ledger entries, closing balances, reservations) are left
out: no one opens them as screens, and they are the largest tables. So is a project field
whose document already shows the project's name from it (Timesheet Detail).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Gesc App"
LABEL = "اسم المشروع المرتبط"
SOURCE = "project_name"
EXCLUDED = {
	"Account Closing Balance",
	"GL Entry",
	"Payment Ledger Entry",
	"Stock Ledger Entry",
	"Stock Reservation Entry",
}


def setup():
	fields = {}
	for doctype, link in get_project_links():
		fields.setdefault(doctype, []).append(
			{
				"fieldname": title_field(link),
				"label": LABEL,
				"fieldtype": "Data",
				"read_only": 1,
				"fetch_from": f"{link}.{SOURCE}",
				"insert_after": link,
				"depends_on": f"eval:doc.{link}",
				"translatable": 0,
				"module": MODULE,
			}
		)
	if fields:
		create_custom_fields(fields)
		for doctype, rows in fields.items():
			for row in rows:
				fill(doctype, row["insert_after"], row["fieldname"])
	place_next_to_project()


def get_project_links():
	"""The project fields that have no project name next to them yet: (doctype, field)."""
	rows = frappe.db.sql(
		"""select parent, fieldname from `tabDocField`
			where fieldtype = 'Link' and options = 'Project' and parenttype = 'DocType'
		union
		select dt, fieldname from `tabCustom Field`
			where fieldtype = 'Link' and options = 'Project'"""
	)
	links = []
	for doctype, link in rows:
		if doctype in EXCLUDED or not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		field = meta.get_field(link)
		if meta.issingle or meta.is_virtual or not field or field.hidden:
			continue
		if any(df.fetch_from == f"{link}.{SOURCE}" for df in meta.fields):
			continue
		links.append((doctype, link))
	return links


def place_next_to_project():
	"""Right after the project field, ahead of other custom fields placed after it. Frappe
	orders those by their idx; the direction is checked on the meta rather than assumed."""
	for doctype, link, field in get_title_fields():
		if is_next_to_project(doctype, link, field):
			continue
		others = frappe.get_all(
			"Custom Field",
			filters={"dt": doctype, "insert_after": link, "fieldname": ("!=", field)},
			pluck="idx",
		)
		if not others:
			continue
		for idx in (max(others) + 1, min(others) - 1):
			frappe.db.set_value("Custom Field", f"{doctype}-{field}", "idx", idx, update_modified=False)
			frappe.clear_cache(doctype=doctype)
			if is_next_to_project(doctype, link, field):
				break


def is_next_to_project(doctype, link, field):
	fields = [df.fieldname for df in frappe.get_meta(doctype, cached=False).fields]
	return link in fields and fields[fields.index(link) + 1 : fields.index(link) + 2] == [field]


def title_field(link):
	return "custom_project_title" if link == "project" else f"custom_{link.removeprefix('custom_')}_title"


def get_title_fields():
	"""The project name fields made here: (doctype, link, field)."""
	return [
		(row.dt, row.fetch_from.split(".")[0], row.fieldname)
		for row in frappe.get_all(
			"Custom Field",
			filters={"module": MODULE, "label": LABEL, "fetch_from": ("like", f"%.{SOURCE}")},
			fields=["dt", "fieldname", "fetch_from"],
		)
	]


def fill(doctype, link, field, project=None):
	"""Write the project's name into the documents linked to it that show another."""
	condition = "and project.name = %(project)s" if project else ""
	frappe.db.sql(
		f"""update `tab{doctype}` doc
			join `tabProject` project on project.name = doc.`{link}`
			set doc.`{field}` = project.`{SOURCE}`
			where ifnull(doc.`{field}`, '') != ifnull(project.`{SOURCE}`, '') {condition}""",
		{"project": project},
	)


def update_project_title(doc, method=None):
	"""Project on_update: the new name everywhere the project is linked."""
	if doc.is_new() or not doc.has_value_changed(SOURCE):
		return
	for doctype, link, field in get_title_fields():
		if frappe.db.has_column(doctype, field):
			fill(doctype, link, field, doc.name)
