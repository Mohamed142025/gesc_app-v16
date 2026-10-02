// Quotation approval from Selling Settings: the status on the form, and "طلب اعتماد",
// "اعتماد" and "رفض" in place of Submit until the quotation is approved. The server
// enforces the same rules.
(() => {
	const DRAFT = "مسودة";
	const PENDING = "بانتظار الاعتماد";
	const APPROVED = "معتمد";
	const REJECTED = "مرفوض";
	const API = "gesc_app.gesc_app.quotation_approval.";

	let settings_request = null;
	const load_settings = () => (settings_request ||= frappe.xcall(API + "get_approval_settings"));

	frappe.ui.form.on("Quotation", {
		// Before the form's first refresh, which is when Frappe first draws its message.
		setup(frm) {
			keep_approval_message(frm);
		},

		refresh(frm) {
			load_settings().then((settings) => {
				const first_load = !frm.__approval;
				frm.__approval = settings;
				// The refresh that loaded the settings held Frappe's message back.
				if (first_load && !uses_approval(frm)) frm.show_submit_message();
				render(frm, settings);
			});
		},

		before_submit(frm) {
			const settings = frm.__approval;
			if (settings?.enabled && frm.doc.custom_approval_status !== APPROVED) {
				frappe.msgprint({
					title: __("عرض السعر غير معتمد"),
					message: __("عرض السعر يحتاج اعتماد قبل الـ Submit والإرسال للعميل."),
					indicator: "orange",
				});
				frappe.validated = false;
			}
		},
	});

	// Frappe fills the same message area with "Submit this document to confirm" on every
	// refresh; while approval is on, the approval status takes its place. Until the settings
	// arrive neither is known to apply, so nothing is drawn yet.
	function keep_approval_message(frm) {
		if (frm.__approval_message_kept) return;
		const show_submit_message = frm.show_submit_message.bind(frm);
		frm.show_submit_message = () => {
			if (!frm.__approval) return;
			if (uses_approval(frm)) show_status(frm);
			else show_submit_message();
		};
		frm.__approval_message_kept = true;
	}

	function uses_approval(frm) {
		return frm.__approval?.enabled && !frm.is_new() && frm.doc.docstatus === 0;
	}

	function show_status(frm) {
		const settings = frm.__approval;
		const doc = frm.doc;
		const status = doc.custom_approval_status || DRAFT;
		const who = (user) => frappe.user.full_name(user);
		const when = (value) => (value ? frappe.datetime.comment_when(value) : "");

		if (status === APPROVED) {
			set_message(frm, __("معتمد بواسطة {0} {1}، ويمكن عمل Submit وإرساله للعميل.", [who(doc.custom_approved_by), when(doc.custom_approved_on)]), "green");
		} else if (status === PENDING) {
			set_message(frm, __("بانتظار الاعتماد: طلبه {0} {1}.", [who(doc.custom_approval_requested_by), when(doc.custom_approval_requested_on)]), "orange");
		} else if (status === REJECTED) {
			set_message(frm, __("مرفوض بواسطة {0}: {1}. عدّل العرض واطلب الاعتماد مرة أخرى.", [who(doc.custom_rejected_by), frappe.utils.escape_html(doc.custom_rejection_reason || "")]), "red");
		} else {
			set_message(frm, __("عرض السعر يحتاج اعتماد {0} قبل الـ Submit والإرسال للعميل.", [__(settings.approver_role || "")]), "blue");
		}
	}

	function render(frm, settings) {
		if (!uses_approval(frm)) {
			set_message(frm, "");
			return;
		}

		const status = frm.doc.custom_approval_status || DRAFT;
		show_status(frm);
		if (status === APPROVED) return;

		// Submit waits for the approval: the primary button becomes the next step instead.
		frm.page.clear_primary_action();
		if (status === PENDING) {
			if (settings.is_approver) {
				frm.page.set_primary_action(__("اعتماد"), () => approve(frm));
				frm.add_custom_button(__("رفض"), () => reject(frm)).addClass("btn-danger");
			}
			return;
		}

		if (frm.perm[0]?.write) {
			frm.page.set_primary_action(__("طلب اعتماد"), () => request(frm));
		}
		if (settings.is_approver) {
			frm.add_custom_button(__("اعتماد مباشر"), () => approve(frm));
		}
	}

	// Frappe adds a new message block on every call, so the previous one is removed first.
	function set_message(frm, text, color) {
		frm.__approval_block?.remove();
		frm.__approval_block = null;
		if (!text) return;
		frm.set_intro(text, color);
		frm.__approval_block = frm.layout.message.children().last();
	}

	function call(frm, method, args, done) {
		return frappe
			.xcall(API + method, { quotation: frm.doc.name, ...args })
			.then((doc) => {
				frappe.model.sync(doc);
				frm.refresh();
				frappe.show_alert({ message: done, indicator: "green" });
			})
			// The server's message is already on screen.
			.catch(() => {});
	}

	function request(frm) {
		call(frm, "request_approval", {}, __("تم إرسال طلب الاعتماد."));
	}

	function approve(frm) {
		const total = format_currency(frm.doc.rounded_total || frm.doc.grand_total, frm.doc.currency);
		frappe.confirm(__("اعتماد عرض السعر {0} بإجمالي {1}؟", [frm.doc.name, total]), () =>
			call(frm, "approve", {}, __("تم اعتماد عرض السعر."))
		);
	}

	function reject(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("رفض عرض السعر"),
			fields: [{ fieldname: "reason", fieldtype: "Small Text", label: __("سبب الرفض"), reqd: 1 }],
			primary_action_label: __("رفض"),
			primary_action({ reason }) {
				dialog.hide();
				call(frm, "reject", { reason }, __("تم رفض عرض السعر وإبلاغ المنشئ."));
			},
		});
		// Frappe finds the dialog's main button by .btn-primary (Ctrl+Enter, disabling), so it stays.
		dialog.get_primary_btn().addClass("btn-danger");
		dialog.show();
	}
})();
