// Who an announcement goes to (hr_announcement_audience): before it is submitted, the
// employees it would be sent to.
frappe.ui.form.on("HR Announcement", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) return;
		frm.add_custom_button(__("Preview Recipients"), () => preview(frm));
	},
});

function preview(frm) {
	frappe
		.xcall("gesc_app.gesc_app.hr_announcement_audience.preview_recipients", { doc: frm.doc })
		.then((employees) => {
			if (!employees.length) {
				frappe.msgprint(__("No active employee with a user matches the announcement's audience."));
				return;
			}
			const esc = frappe.utils.escape_html;
			const rows = employees
				.map(
					(e) =>
						`<tr><td>${esc(e.employee_name || e.name)}</td><td>${esc(e.department || "")}</td><td>${esc(e.designation || "")}</td></tr>`
				)
				.join("");
			frappe.msgprint({
				title: __("{0} employees will receive it", [employees.length]),
				message: `<table class="table table-bordered table-sm">
					<thead><tr><th>${__("Employee")}</th><th>${__("Department")}</th><th>${__("Designation")}</th></tr></thead>
					<tbody>${rows}</tbody></table>`,
				wide: true,
			});
		});
}
