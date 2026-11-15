// Material Request for a project (gesc_app.gesc_app.material_request_project): a request
// from a task takes the task's project; a project shows its contract (Sales Order and main
// quotation) and, for a purchase or a transfer, makes its warehouse the target warehouse.
frappe.ui.form.on("Material Request", {
	onload(frm) {
		if (!frm.is_new()) return;
		if (!frm.doc.custom_sample_project) {
			// Made from a project's page with the project on an item only.
			const projects = [...new Set((frm.doc.items || []).map((row) => row.project).filter(Boolean))];
			if (projects.length === 1) {
				frm.set_value("custom_sample_project", projects[0]);
				return;
			}
		}
		if (frm.doc.custom_task && !frm.doc.custom_sample_project) {
			gesc_mr_apply_project(frm, null, frm.doc.custom_task);
		} else if (frm.doc.custom_sample_project) {
			gesc_mr_apply_project(frm, frm.doc.custom_sample_project);
		}
	},

	custom_task(frm) {
		if (frm.doc.custom_task && !frm.doc.custom_sample_project && frm.doc.docstatus === 0) {
			gesc_mr_apply_project(frm, null, frm.doc.custom_task);
		}
	},

	custom_sample_project(frm) {
		if (frm.doc.docstatus !== 0) return;
		if (!frm.doc.custom_sample_project) {
			frm.set_value("custom_project_sales_order", "");
			frm.set_value("custom_project_quotation", "");
			return;
		}
		gesc_mr_apply_project(frm, frm.doc.custom_sample_project);
	},

	custom_request_purpose(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.custom_sample_project) {
			gesc_mr_apply_project(frm, frm.doc.custom_sample_project);
		}
	},
});

async function gesc_mr_apply_project(frm, project, task) {
	const { message: info } = await frappe.call({
		method: "gesc_app.gesc_app.material_request_project.get_project_details",
		args: { project, task },
	});
	if (!info || !info.project) return;
	if (frm.doc.custom_sample_project !== info.project) {
		// Its own change handler comes back here with the project.
		frm.set_value("custom_sample_project", info.project);
		return;
	}
	frm.set_value("custom_project_sales_order", info.sales_order || "");
	frm.set_value("custom_project_quotation", info.quotation || "");
	const purpose = frm.doc.custom_request_purpose || frm.doc.material_request_type;
	const to_project = ["Purchase", "Material Transfer"].includes(purpose);
	// The project's warehouse, unless another target was chosen by hand.
	const auto = !frm.doc.set_warehouse || frm.doc.set_warehouse === frm.__gesc_auto_warehouse;
	if (to_project && info.warehouse && auto && frm.doc.set_warehouse !== info.warehouse) {
		frm.__gesc_auto_warehouse = info.warehouse;
		frm.set_value("set_warehouse", info.warehouse);
	}
}
