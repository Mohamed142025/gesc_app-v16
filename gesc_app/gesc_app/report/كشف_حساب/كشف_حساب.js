// Copyright (c) 2026, mohamed sayed and contributors
// For license information, please see license.txt

frappe.query_reports["كشف حساب"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "scope",
			label: __("نطاق الحسابات"),
			fieldtype: "Select",
			options: ["العهد", "كل الحسابات"],
			default: "العهد",
		},
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "MultiSelectList",
			options: "Account",
			get_data: (txt) =>
				frappe.db.get_link_options("Account", txt, {
					company: frappe.query_report.get_filter_value("company"),
				}),
		},
		{ fieldname: "party_type", label: __("Party Type"), fieldtype: "Link", options: "Party Type" },
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Dynamic Link",
			get_options: () => frappe.query_report.get_filter_value("party_type"),
		},
		{
			fieldname: "overdue_days",
			label: __("متأخرة بعد (يوم)"),
			fieldtype: "Int",
			default: 30,
		},
	],
	tree: true,
	name_field: "description",
	parent_field: "account",
	initial_depth: 1,

	// The chart slot carries the dashboard's data, drawn below in place of a chart.
	get_chart_data: () => null,

	after_refresh(report) {
		const dashboard = report.data?.length ? report.raw_data?.chart : null;
		statement_dashboard.render(report, dashboard);
	},

	formatter(value, row, column, data, default_formatter) {
		// An empty cell says nothing happened there; a zero would read as an amount.
		if (["amount_in", "amount_out", "days_open"].includes(column.fieldname) && !flt(value)) return "";
		if (column.fieldname === "balance" && (value === null || value === undefined)) return "";
		const formatted = default_formatter(value, row, column, data);
		if (!data) return formatted;
		if (column.fieldname === "days_open" && data.overdue) {
			return `<span class="gs-overdue" title="${__("رصيد مفتوح متأخر التسوية")}">⚠ ${formatted}</span>`;
		}
		if (["account", "total"].includes(data.row_kind)) return `<b>${formatted}</b>`;
		if (["counter", "opening"].includes(data.row_kind)) return `<span class="text-muted">${formatted}</span>`;
		return formatted;
	},
};

const statement_dashboard = {
	render(report, data) {
		let root = report.page.main.find(".gesc-statement");
		if (!data) {
			root.hide();
			return;
		}
		if (!root.length) root = $('<div class="gesc-statement"></div>').insertBefore(report.$chart);
		root.html(`<style>${this.styles}</style>${this.tiles(data)}${this.charts(data)}<div class="gs-tip" hidden></div>`);
		root.show();
		this.bind(report, root);
	},

	money: (value) => format_number(value, null, 0),

	short(value) {
		const size = Math.abs(value);
		if (size >= 1e6) return `${flt(value / 1e6, 1)}M`;
		if (size >= 1e3) return `${flt(value / 1e3, 1)}K`;
		return `${flt(value, 0)}`;
	},

	tiles(d) {
		const esc = frappe.utils.escape_html;
		const tile = (label, value, note = "", extra = "") => `
			<div class="gs-tile ${extra}">
				<div class="gs-label">${esc(label)}</div>
				<div class="gs-value">${value}</div>
				<div class="gs-note">${note}</div>
			</div>`;
		const open = [`<bdi>${d.open_count} ${__("حساب برصيد مفتوح")}</bdi>`];
		if (d.negative_count) open.push(`<bdi class="gs-overdue">⚠ ${d.negative_count} ${__("بالسالب")}</bdi>`);
		return `<div class="gs-tiles">
			${tile(__("الرصيد الحالي"), this.money(d.closing), open.join(" · "), "gs-hero")}
			${tile(__("القيمة الداخلة"), this.money(d.total_in), __("خلال الفترة"))}
			${tile(__("القيمة الخارجة"), this.money(d.total_out), __("خلال الفترة"))}
			${tile(
				__("نسبة التسوية"),
				d.settled_percent === null ? "—" : `${flt(d.settled_percent, 1)}%`,
				__("الخارج من رصيد أول المدة والداخل")
			)}
			${tile(
				__("متأخرة التسوية"),
				d.overdue_count ? `<span class="gs-overdue">⚠</span> ${d.overdue_count}` : "0",
				d.overdue_count
					? `<bdi>${this.money(d.overdue_amount)}</bdi> · <bdi>${__("بلا تسوية منذ أكثر من {0} يوم", [d.overdue_days])}</bdi>`
					: __("لا يوجد حساب متأخر")
			)}
		</div>`;
	},

	charts(d) {
		const panels = [this.balances(d), this.monthly(d), this.destinations(d)].filter(Boolean);
		return panels.length ? `<div class="gs-charts">${panels.join("")}</div>` : "";
	},

	panel: (title, subtitle, body) => `
		<section class="gs-panel">
			<h4 class="gs-title">${title}</h4>
			<div class="gs-subtitle">${subtitle}</div>
			${body}
		</section>`,

	ranked(rows, row_html) {
		const largest = Math.max(...rows.map((row) => row.amount), 1);
		return `<div class="gs-ranked">${rows
			.map((row) => row_html(row, Math.max((row.amount * 100) / largest, 1)))
			.join("")}</div>`;
	},

	bar_row(row, width, chip, tip, action) {
		const esc = frappe.utils.escape_html;
		const inner = `
			<span class="gs-row-head">
				<span class="gs-row-name">${esc(row.label)}</span>
				<span class="gs-row-value">${chip}<bdi>${this.money(row.amount)}</bdi></span>
			</span>
			<span class="gs-track"><span class="gs-fill" style="width:${width}%"></span></span>`;
		const attrs = `data-tip="${esc(tip)}" aria-label="${esc(tip)}"`;
		const target = action || (row.account ? `data-account="${esc(row.account)}"` : "");
		return target
			? `<button type="button" class="gs-row gs-clickable" ${target} ${attrs}>${inner}</button>`
			: `<div class="gs-row" tabindex="0" ${attrs}>${inner}</div>`;
	},

	balances(d) {
		const body = d.balances.length
			? this.ranked(d.balances, (row, width) => {
					const lines = [row.label, `${__("الرصيد")}: ${format_number(row.amount, null, 2)}`];
					if (row.days !== null && row.days !== undefined) lines.push(`${row.days} ${__("يوم بلا تسوية")}`);
					const chip = row.overdue ? `<bdi class="gs-chip">⚠ ${row.days} ${__("يوم")}</bdi>` : "";
					return this.bar_row(row, width, chip, lines.join("\n"));
			  })
			: `<div class="gs-empty">${__("لا يوجد رصيد مفتوح")}</div>`;
		return this.panel(__("الرصيد المفتوح لكل حساب"), __("اضغط على حساب لعرضه وحده"), body);
	},

	destinations(d) {
		if (!d.destinations.length) return "";
		const total = d.destinations.reduce((sum, row) => sum + row.amount, 0);
		return this.panel(
			__("الخارج ذهب إلى أين"),
			__("أكبر الحسابات المقابلة للقيمة الخارجة · اضغط على حساب لعرض حركاته"),
			this.ranked(d.destinations, (row, width) => {
				const share = total ? flt((row.amount * 100) / total, 1) : 0;
				const action = `data-destination="${frappe.utils.escape_html(row.label)}" data-others="${row.others ? 1 : 0}"`;
				return this.bar_row(row, width, "", `${row.label}\n${format_number(row.amount, null, 2)} · ${share}%`, action);
			})
		);
	},

	// The movements behind a bar of "where it went".
	show_movements(report, destination, others) {
		frappe
			.xcall("gesc_app.gesc_app.report.كشف_حساب.كشف_حساب.get_destination_movements", {
				filters: report.get_filter_values(),
				destination: others ? null : destination,
				others,
			})
			.then((rows) => this.movements_dialog(destination, others, rows));
	},

	movements_dialog(destination, others, rows) {
		const esc = frappe.utils.escape_html;
		const total = rows.reduce((sum, row) => sum + row.amount, 0);
		const row_html = (row) => `<tr>
			<td class="text-nowrap">${frappe.datetime.str_to_user(row.posting_date)}</td>
			<td><div class="small text-muted">${esc(row.voucher_label)}</div>${frappe.utils.get_form_link(row.voucher_type, row.voucher_no, true)}</td>
			<td>${esc(row.from_account)}</td>
			${others ? `<td>${esc(row.destination)}</td>` : ""}
			<td>${esc(row.party || "")}</td>
			<td>${esc(row.remark || "")}</td>
			<td class="text-right text-nowrap"><bdi>${format_number(row.amount, null, 2)}</bdi>${row.estimated ? " *" : ""}</td>
		</tr>`;
		const note = rows.some((row) => row.estimated)
			? `<p class="small text-muted">* ${__("المستند فيه أكثر من حساب على الجانبين، والقيمة هي نصيب الحركة منه.")}</p>`
			: "";
		const dialog = new frappe.ui.Dialog({ title: __("الحركات: {0}", [destination]), size: "extra-large" });
		dialog.$body.html(`<div style="max-height: 65vh; overflow: auto">
			<table class="table table-bordered table-sm">
				<thead><tr>
					<th>${__("التاريخ")}</th><th>${__("المستند")}</th><th>${__("من حساب")}</th>
					${others ? `<th>${__("إلى حساب")}</th>` : ""}
					<th>${__("الطرف")}</th><th>${__("البيان")}</th><th class="text-right">${__("القيمة")}</th>
				</tr></thead>
				<tbody>${rows.map(row_html).join("")}</tbody>
				<tfoot><tr class="bold">
					<td colspan="${others ? 6 : 5}">${__("الإجمالي")} (${rows.length})</td>
					<td class="text-right text-nowrap"><bdi>${format_number(total, null, 2)}</bdi></td>
				</tr></tfoot>
			</table>
		</div>${note}`);
		dialog.show();
	},

	monthly(d) {
		if (d.monthly.length < 2) return "";
		const esc = frappe.utils.escape_html;
		const largest = Math.max(...d.monthly.flatMap((m) => [m.in, m.out]), 1);
		const columns = d.monthly
			.map((m) => {
				const tip = `${m.label}\n${__("داخل")}: ${format_number(m.in, null, 2)}\n${__("خارج")}: ${format_number(m.out, null, 2)}`;
				const bar = (value, cls) =>
					`<span class="gs-col ${cls}" style="height:${value ? Math.max((value * 100) / largest, 1) : 0}%"></span>`;
				return `<div class="gs-band" tabindex="0" data-tip="${esc(tip)}" aria-label="${esc(tip)}">
					<div class="gs-pair">${bar(m.in, "gs-in")}${bar(m.out, "gs-out")}</div>
					<div class="gs-month">${esc(m.label)}</div>
				</div>`;
			})
			.join("");
		return this.panel(
			__("الداخل والخارج شهرياً"),
			`<span class="gs-legend"><i class="gs-key gs-in"></i>${__("داخل")}</span>
			 <span class="gs-legend"><i class="gs-key gs-out"></i>${__("خارج")}</span>`,
			`<div class="gs-plot">
				<div class="gs-grid"><span>${this.short(largest)}</span><span>${this.short(largest / 2)}</span><span>0</span></div>
				<div class="gs-bands">${columns}</div>
			</div>`
		);
	},

	bind(report, root) {
		const tip = root.find(".gs-tip");
		const show = (el, x, y) => {
			tip.text(el.dataset.tip).prop("hidden", false);
			const box = tip[0].getBoundingClientRect();
			tip.css({
				left: Math.max(8, Math.min(x - box.width / 2, window.innerWidth - box.width - 8)),
				top: y - box.height - 12 < 8 ? y + 16 : y - box.height - 12,
			});
		};
		root.on("mousemove", "[data-tip]", function (e) {
			show(this, e.clientX, e.clientY);
		});
		root.on("focusin", "[data-tip]", function () {
			const box = this.getBoundingClientRect();
			show(this, box.left + box.width / 2, box.top);
		});
		root.on("mouseleave focusout", "[data-tip]", () => tip.prop("hidden", true));
		root.on("click", ".gs-clickable[data-account]", function () {
			report.set_filter_value("account", [this.dataset.account]);
		});
		const dashboard = this;
		root.on("click", ".gs-clickable[data-destination]", function () {
			tip.prop("hidden", true);
			dashboard.show_movements(report, this.dataset.destination, cint(this.dataset.others));
		});
	},

	styles: `
		.gesc-statement { --gs-in: #2a78d6; --gs-out: #eb6834; --gs-bar: #2a78d6; --gs-grid: var(--border-color);
			--gs-warn: #b35c00; margin-bottom: var(--margin-md); }
		:root[data-theme="dark"] .gesc-statement { --gs-in: #3987e5; --gs-out: #d95926; --gs-bar: #3987e5; --gs-warn: #fab219; }
		.gs-overdue { color: var(--gs-warn, #b35c00); font-weight: 600; }
		.gs-tiles { display: grid; grid-template-columns: 1.5fr repeat(4, 1fr); gap: var(--margin-sm); margin-bottom: var(--margin-sm); }
		.gs-tile, .gs-panel { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--border-radius-lg, 12px); }
		.gs-tile { padding: var(--padding-md); min-width: 0; }
		.gs-label { color: var(--text-muted); font-size: var(--text-sm); }
		.gs-value { color: var(--text-color); font-size: 24px; font-weight: 600; line-height: 1.3; margin-block: 4px; font-variant-numeric: tabular-nums; }
		.gs-hero .gs-value { font-size: 40px; line-height: 1.15; }
		.gs-note { color: var(--text-muted); font-size: var(--text-xs); }
		.gs-charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--margin-sm); }
		.gs-panel { padding: var(--padding-md); min-width: 0; }
		.gs-title { margin: 0; font-size: var(--text-base); font-weight: 600; color: var(--text-color); }
		.gs-subtitle { color: var(--text-muted); font-size: var(--text-xs); margin-block: 2px 12px; min-height: 18px; }
		.gs-empty { color: var(--text-muted); padding-block: 32px; text-align: center; }
		.gs-ranked { display: flex; flex-direction: column; gap: 2px; }
		.gs-row { display: block; width: 100%; padding: 5px 6px; background: none; border: 0; border-radius: 6px; text-align: start; color: inherit; }
		.gs-clickable { cursor: pointer; }
		.gs-row:hover, .gs-row:focus-visible, .gs-band:hover, .gs-band:focus-visible { background: var(--subtle-fg); outline: none; }
		.gs-row-head { display: flex; justify-content: space-between; gap: 8px; font-size: var(--text-sm); }
		.gs-row-name { color: var(--text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
		.gs-row-value { color: var(--text-color); font-weight: 600; white-space: nowrap; font-variant-numeric: tabular-nums; }
		.gs-chip { color: var(--gs-warn); font-weight: 500; font-size: var(--text-xs); margin-inline-end: 10px; }
		.gs-track { display: block; margin-top: 4px; }
		.gs-fill { display: block; height: 10px; background: var(--gs-bar); border-start-end-radius: 4px; border-end-end-radius: 4px; }
		.gs-legend { display: inline-flex; align-items: center; gap: 5px; margin-inline-end: 18px; }
		.gs-key { display: inline-block; width: 10px; height: 10px; border-radius: 3px; }
		.gs-key.gs-in, .gs-col.gs-in { background: var(--gs-in); }
		.gs-key.gs-out, .gs-col.gs-out { background: var(--gs-out); }
		.gs-plot { position: relative; height: 200px; }
		.gs-grid { position: absolute; inset: 0 0 24px 0; display: flex; flex-direction: column; justify-content: space-between; color: var(--text-muted); font-size: 10px; pointer-events: none; }
		.gs-grid span { border-bottom: 1px solid var(--gs-grid); height: 0; line-height: 0; padding-bottom: 7px; }
		.gs-bands { position: absolute; inset: 0; display: flex; padding-inline-start: 34px; }
		.gs-band { flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; border-radius: 6px; }
		.gs-pair { flex: 1; display: flex; align-items: flex-end; justify-content: center; gap: 2px; }
		.gs-col { display: block; width: min(16px, 34%); border-radius: 4px 4px 0 0; }
		.gs-month { height: 24px; line-height: 24px; text-align: center; color: var(--text-muted); font-size: 10px; white-space: nowrap; overflow: hidden; }
		.gs-tip { position: fixed; z-index: 1050; pointer-events: none; white-space: pre-line; max-width: 280px; padding: 6px 10px;
			background: var(--neutral-black, #111); color: #fff; border-radius: 6px; font-size: var(--text-xs); line-height: 1.5; }
		.gs-tip[hidden] { display: none; }
		@media (max-width: 991px) {
			.gs-tiles { grid-template-columns: repeat(2, 1fr); }
			.gs-hero { grid-column: 1 / -1; }
		}
		@media (max-width: 480px) { .gs-charts { grid-template-columns: minmax(0, 1fr); } }
	`,
};
