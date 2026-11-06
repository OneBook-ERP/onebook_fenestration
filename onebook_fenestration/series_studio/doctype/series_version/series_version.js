frappe.ui.form.on("Series Version", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Check readiness"), () => {
			frappe.call({
				method: "onebook_fenestration.series_studio.readiness.readiness",
				args: { series_version: frm.doc.name },
				freeze: true,
				callback: ({ message }) => show_readiness(message),
			});
		});
	},
});

const CHECK_LABELS = {
	settings: __("Fenestration Settings"),
	item_links: __("Items linked to profiles and glasses"),
	prices: __("Rates on the cost price list"),
	gasket_rules: __("Glazing gasket rule for every glass"),
	perimeters: __("Profile perimeters"),
	outlines: __("Profile outlines"),
};
const STATUS_INDICATORS = { ok: "green", warn: "orange", block: "red" };

function show_readiness(report) {
	const rows = report.checks
		.map((c) => {
			const items = c.items.map((item) => frappe.utils.escape_html(item)).join(", ");
			return `<tr>
			<td><span class="indicator-pill ${STATUS_INDICATORS[c.status]}">${__(c.status)}</span></td>
			<td>${CHECK_LABELS[c.check] || c.check}</td>
			<td>${items || "–"}</td>
		</tr>`;
		})
		.join("");
	const dialog = new frappe.ui.Dialog({
		title: report.ok ? __("Ready to price") : __("Not ready to price"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "report" }],
	});
	dialog.fields_dict.report.$wrapper.html(
		`<table class="table table-bordered"><thead><tr><th>${__("Status")}</th><th>${__(
			"Check"
		)}</th><th>${__("Needs attention")}</th></tr></thead><tbody>${rows}</tbody></table>`
	);
	dialog.show();
}
