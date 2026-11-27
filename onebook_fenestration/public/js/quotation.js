frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (frm.is_new()) return;

		const total = frm.doc.rounded_total || frm.doc.grand_total || 0;
		const formatted = format_currency(total, frm.doc.currency);
		frm.dashboard.add_indicator(__("Quotation Value: {0}", [formatted]), "blue");

		if (frm.doc.fen_partner_type) {
			const colorMap = {
				Dealer: "green",
				"Fabrication Partner": "blue",
				"Own Client": "purple",
			};
			frm.dashboard.add_indicator(
				__("Partner Type: {0}", [frm.doc.fen_partner_type]),
				colorMap[frm.doc.fen_partner_type] || "gray"
			);
		}

		if (frm.doc.crm_deal) {
			frm.add_custom_button(__("View CRM Deal"), () => {
				window.open(`/crm/deals/${encodeURIComponent(frm.doc.crm_deal)}`, "_blank");
			});
		}
	},
});

