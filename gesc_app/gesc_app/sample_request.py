"""Sample requests: a Material Request for samples given to a customer.

A sample request is a Material Issue as far as ERPNext is concerned - its status, issued
quantities and the Stock Entry made from it all work as for a Material Issue - so the
request's own purpose (material_request_type) stays "Material Issue". The purpose the user
picks is a field of its own ("الغرض", custom_request_purpose) with every standard purpose and
"طلب عينة"; it sets material_request_type, and for a sample it asks for the customer
(custom_sample_customer: ERPNext clears its own customer field outside "Customer Provided").

The Stock Entry made from a sample request is of the type "طلب عينة" (a Material Issue) and
carries the customer; a sample Stock Entry made by hand needs one too.

A sample is for a customer, a project, or both: at least one is needed. A project brings its
customer, and only that customer's projects may go with a chosen customer. The project goes on
the request's items and on the Stock Entry, so the sample is costed to it.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SAMPLE = "طلب عينة"
OLD_SAMPLE_TYPE = "Request a sample"
ISSUE = "Material Issue"
PURPOSE = "custom_request_purpose"
MODULE = "Gesc App"
# The standard purposes, in ERPNext's order, then the sample.
PURPOSES = ("Purchase", "Material Transfer", ISSUE, "Manufacture", "Subcontracting", "Customer Provided", SAMPLE)
SAMPLE_CUSTOMER = "custom_sample_customer"
SAMPLE_PROJECT = "custom_sample_project"
IS_SAMPLE_MR = f"eval:doc.{PURPOSE} == '{SAMPLE}'"


def setup():
	_setup_stock_entry_type()
	create_custom_fields(
		{
			"Material Request": [
				{
					"fieldname": PURPOSE,
					"label": "الغرض",
					"fieldtype": "Select",
					# Empty first, so a request made in code with only ERPNext's purpose is not
					# given the first purpose (sync_purpose fills it in).
					"options": "\n" + "\n".join(PURPOSES),
					"insert_after": "material_request_type",
					"in_list_view": 1,
					"in_standard_filter": 1,
					"description": "«طلب عينة» يُصرف من المخزن مثل Material Issue، لعميل محدد.",
					"module": MODULE,
				},
				{
					"fieldname": SAMPLE_CUSTOMER,
					"label": "العميل",
					"fieldtype": "Link",
					"options": "Customer",
					"insert_after": PURPOSE,
					"depends_on": IS_SAMPLE_MR,
					"mandatory_depends_on": f"eval:doc.{PURPOSE} == '{SAMPLE}' && !doc.{SAMPLE_PROJECT}",
					"description": "العميل أو المشروع، واحد منهم على الأقل.",
					"module": MODULE,
				},
				{
					"fieldname": SAMPLE_PROJECT,
					"label": "المشروع",
					"fieldtype": "Link",
					"options": "Project",
					"insert_after": SAMPLE_CUSTOMER,
					"depends_on": IS_SAMPLE_MR,
					"mandatory_depends_on": f"eval:doc.{PURPOSE} == '{SAMPLE}' && !doc.{SAMPLE_CUSTOMER}",
					"description": "لو اخترت عميلاً، تظهر مشاريعه فقط.",
					"module": MODULE,
				},
			],
			"Stock Entry": [
				{
					"fieldname": "custom_customer",
					"label": "العميل",
					"fieldtype": "Link",
					"options": "Customer",
					"insert_after": "stock_entry_type",
					"depends_on": f"eval:doc.stock_entry_type == '{SAMPLE}'",
					"mandatory_depends_on": f"eval:doc.stock_entry_type == '{SAMPLE}' && !doc.project",
					"module": MODULE,
				}
			],
		},
		update=True,
	)

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	# "الغرض" takes the place of the standard purpose, which it fills in.
	for doctype, fieldname, prop, value, prop_type in (
		("Material Request", "material_request_type", "hidden", "1", "Check"),
		("Material Request", "material_request_type", "reqd", "0", "Check"),
		("Material Request", PURPOSE, "reqd", "1", "Check"),
	):
		current = frappe.db.get_value(
			"Property Setter", {"doc_type": doctype, "field_name": fieldname, "property": prop}, "value"
		)
		if current != value:
			make_property_setter(doctype, fieldname, prop, value, prop_type, validate_fields_for_doctype=False)

	# The standard customer field keeps ERPNext's own rule (Customer Provided only).
	for prop in ("depends_on", "mandatory_depends_on"):
		frappe.db.delete("Property Setter", {"doc_type": "Material Request", "field_name": "customer", "property": prop})

	# Requests made before "الغرض" show their own purpose in it.
	frappe.db.sql(
		f"update `tabMaterial Request` set {PURPOSE} = material_request_type where ifnull({PURPOSE}, '') = ''"
	)
	frappe.clear_cache(doctype="Material Request")
	frappe.clear_cache(doctype="Stock Entry")


def _setup_stock_entry_type():
	if not frappe.db.exists("Stock Entry Type", SAMPLE):
		if frappe.db.exists("Stock Entry Type", OLD_SAMPLE_TYPE):
			frappe.rename_doc("Stock Entry Type", OLD_SAMPLE_TYPE, SAMPLE, force=True)
		else:
			frappe.get_doc({"doctype": "Stock Entry Type", "name": SAMPLE, "purpose": ISSUE}).insert(
				ignore_permissions=True, set_name=SAMPLE
			)
	if frappe.db.get_value("Stock Entry Type", SAMPLE, "purpose") != ISSUE:
		frappe.db.set_value("Stock Entry Type", SAMPLE, "purpose", ISSUE)


def is_sample(material_request):
	return frappe.db.get_value("Material Request", material_request, PURPOSE) == SAMPLE


# Material Request -----------------------------------------------------------------------


def sync_purpose(doc, method=None):
	"""before_validate: "الغرض" sets ERPNext's purpose; a request made elsewhere with only
	ERPNext's purpose gets it in "الغرض" too."""
	purpose = doc.get(PURPOSE)
	if purpose == SAMPLE:
		doc.material_request_type = ISSUE
		_check_customer_and_project(doc)
	elif purpose in PURPOSES:
		doc.material_request_type = purpose
		doc.set(SAMPLE_CUSTOMER, None)
		doc.set(SAMPLE_PROJECT, None)
	else:
		doc.set(PURPOSE, doc.material_request_type)


def _check_customer_and_project(doc):
	customer, project = doc.get(SAMPLE_CUSTOMER), doc.get(SAMPLE_PROJECT)
	if not customer and not project:
		frappe.throw(_("حدد العميل أو المشروع لطلب العينة."), title=_("العميل أو المشروع مطلوب"))
	if project:
		project_customer = frappe.db.get_value("Project", project, "customer")
		if project_customer and not customer:
			doc.set(SAMPLE_CUSTOMER, project_customer)
		elif project_customer and customer != project_customer:
			frappe.throw(
				_("المشروع {0} تابع للعميل {1}، وليس {2}.").format(
					frappe.bold(project), frappe.bold(project_customer), frappe.bold(customer)
				)
			)
		# The sample is costed to the project.
		for row in doc.items:
			if not row.project:
				row.project = project


# Stock Entry ----------------------------------------------------------------------------


@frappe.whitelist()
def make_stock_entry(source_name, target_doc=None):
	"""ERPNext's Stock Entry from a Material Request; a sample request's is a sample issue for
	its customer."""
	from erpnext.stock.doctype.material_request.material_request import make_stock_entry as erpnext_make

	entry = erpnext_make(source_name, target_doc)
	if is_sample(source_name):
		entry.stock_entry_type = SAMPLE
		entry.custom_customer, project = frappe.db.get_value(
			"Material Request", source_name, [SAMPLE_CUSTOMER, SAMPLE_PROJECT]
		)
		if project:
			entry.project = project
	return entry


def apply_sample(doc, method=None):
	"""before_validate: a Stock Entry against a sample request is a sample issue for its
	customer; a sample issue needs a customer."""
	requests = {row.material_request for row in doc.items if row.get("material_request")}
	sample_requests = [name for name in requests if is_sample(name)]
	if sample_requests and doc.purpose == ISSUE:
		doc.stock_entry_type = SAMPLE
		customer, project = frappe.db.get_value("Material Request", sample_requests[0], [SAMPLE_CUSTOMER, SAMPLE_PROJECT])
		if not doc.get("custom_customer"):
			doc.custom_customer = customer
		if not doc.project and project:
			doc.project = project
	if doc.stock_entry_type == SAMPLE:
		if not doc.get("custom_customer") and doc.project:
			doc.custom_customer = frappe.db.get_value("Project", doc.project, "customer")
		if not doc.get("custom_customer") and not doc.project:
			frappe.throw(_("حدد العميل أو المشروع لقيد طلب العينة."), title=_("العميل أو المشروع مطلوب"))
