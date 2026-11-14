"""Journal Entries are approved and cancelled only through their workflow.

Frappe checks a workflow only when the state changes, and not at all on cancel, so anyone
with Submit or Cancel could do either straight from the form or the list, skipping who the
workflow allows and leaving the state wrong. The workflow decides who moves an entry where;
these stop what did not go through it.

- Approve: a custody entry (its owner has the custody role, as in the workflow's conditions)
  is submitted only into the operations-approved state. Administrator holds every role and
  owns the system's own entries, so it is not one.
- Cancel: any entry is cancelled only into a cancelled state of the workflow, by its
  "إلغاء" action. The system's own entries (exchange gain/loss and the like) and
  Administrator are left to cancel as before, so automatic cancellations still run.
"""

import frappe
from frappe import _
from frappe.model.workflow import get_workflow_name
from frappe.utils import cint

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


def before_cancel(doc, method=None):
	if doc.is_system_generated or frappe.session.user == "Administrator":
		return
	if frappe.flags.in_patch or frappe.flags.in_migrate:
		return
	if get_workflow_name(doc.doctype) != WORKFLOW:
		return
	workflow = frappe.get_cached_doc("Workflow", WORKFLOW)
	if doc.get("workflow_state") in {state.state for state in workflow.states if cint(state.doc_status) == 2}:
		return
	frappe.throw(
		_("إلغاء القيد {0} يتم من زر الإجراءات «إلغاء» في مسار الاعتماد، لمن له صلاحية الإلغاء فيه.").format(
			frappe.bold(doc.name)
		),
		title=_("مسار الاعتماد"),
	)
