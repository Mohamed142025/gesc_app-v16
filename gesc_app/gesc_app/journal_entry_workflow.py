"""A custody Journal Entry is approved only through its workflow.

Frappe checks a workflow only when the state changes, so anyone with Submit could submit an
entry straight from any state and skip the accounts review. The workflow itself decides who
moves an entry into the approved state; this stops a submit that did not go there.

An entry is a custody entry when its owner has the custody role, as in the workflow's
conditions. Administrator holds every role and owns the system's own entries, so it is not one.
"""

import frappe
from frappe import _
from frappe.model.workflow import get_workflow_name

WORKFLOW = "قيود اليومية - العهد"
CUSTODY_ROLE = "عهد"
APPROVED_STATE = "تم موافقة التشغيل"


def before_submit(doc, method=None):
	if doc.owner == "Administrator" or doc.is_system_generated:
		return
	if get_workflow_name(doc.doctype) != WORKFLOW or doc.get("workflow_state") == APPROVED_STATE:
		return
	if frappe.db.exists("Has Role", {"parent": doc.owner, "parenttype": "User", "role": CUSTODY_ROLE}):
		frappe.throw(
			_("لا يمكن اعتماد قيد العهدة {0} مباشرة: لازم يمر بمراجعة الحسابات ثم موافقة التشغيل.").format(
				frappe.bold(doc.name)
			),
			title=_("مسار الاعتماد"),
		)
