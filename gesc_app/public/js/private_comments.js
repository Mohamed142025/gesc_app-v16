// Private comments on the document types chosen in Private Comment Settings: a button to
// write one, reply and delete on the timeline card, and read receipts. The server shows
// each conversation only to its participants.
(() => {
	const API = "gesc_app.gesc_app.private_comments.";
	const enabled = (doctype) => (frappe.boot.private_comment_doctypes || []).includes(doctype);

	$(document).on("form-refresh", (event, frm) => {
		if (!frm || frm.is_new() || !enabled(frm.doctype)) return;
		frm.add_custom_button(__("تعليق خاص 🔒"), () => write(frm));
		mark_read(frm);
	});

	// The timeline cards are plain HTML from the server; their buttons act through here.
	$(document).on("click", "[data-private-reply]", function (event) {
		event.preventDefault();
		if (cur_frm) reply(cur_frm, this.dataset.privateReply);
	});

	$(document).on("click", "[data-private-delete]", function (event) {
		event.preventDefault();
		if (!cur_frm) return;
		const name = this.dataset.privateDelete;
		frappe.confirm(__("حذف هذا التعليق الخاص؟ حذف التعليق الأول يحذف ردوده أيضاً."), () =>
			frappe.xcall(API + "delete", { name }).then(() => cur_frm.reload_doc())
		);
	});

	function write(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("تعليق خاص 🔒"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "note",
					options: `<p class="text-muted small">${__(
						"لا يرى هذا التعليق إلا أنت ومن تختارهم، ويصلهم إشعار بذلك."
					)}</p>`,
				},
				{
					fieldname: "recipients",
					fieldtype: "MultiSelectPills",
					label: __("إلى"),
					reqd: 1,
					get_data: (txt) => frappe.xcall(API + "search_users", { txt }),
				},
				{ fieldname: "content", fieldtype: "Small Text", label: __("التعليق"), reqd: 1 },
			],
			primary_action_label: __("إرسال"),
			primary_action({ recipients, content }) {
				send(dialog, frm, { recipients, content });
			},
		});
		dialog.show();
	}

	function reply(frm, thread) {
		const dialog = new frappe.ui.Dialog({
			title: __("رد خاص 🔒"),
			fields: [{ fieldname: "content", fieldtype: "Small Text", label: __("الرد"), reqd: 1 }],
			primary_action_label: __("إرسال"),
			primary_action({ content }) {
				send(dialog, frm, { content, reply_to: thread });
			},
		});
		dialog.show();
	}

	function send(dialog, frm, args) {
		dialog.disable_primary_action();
		frappe
			.xcall(API + "add", { reference_doctype: frm.doctype, reference_name: frm.docname, ...args })
			.then(() => {
				dialog.hide();
				frappe.show_alert({ message: __("أُرسل التعليق الخاص."), indicator: "green" });
				frm.reload_doc();
			})
			.catch(() => dialog.enable_primary_action());
	}

	function mark_read(frm) {
		const items = frm.get_docinfo()?.additional_timeline_content || [];
		if (frm.__private_read_marked === frm.docname || !items.some((item) => item.private_comment_unread)) return;
		frm.__private_read_marked = frm.docname;
		frappe.xcall(API + "mark_read", { reference_doctype: frm.doctype, reference_name: frm.docname });
	}
})();
