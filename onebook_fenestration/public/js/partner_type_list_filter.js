(function () {
	const PARTNER_TYPE_OPTIONS = ["Dealer", "Fabrication Partner", "Own Client"];
	const TARGET_DOCTYPES = ["Customer", "Quotation", "Sales Order"];

	function upgradePartnerTypeFilter(listview) {
		const existing = listview?.page?.fields_dict?.fen_partner_type;
		if (!existing || existing.df?.fieldtype === "Autocomplete") return;

		const currentValue = existing.get_value ? existing.get_value() : "";
		const $oldWrapper = $(existing.wrapper);
		if (!$oldWrapper.length) return;

		const $holder = $('<div class="col-md-2"></div>').insertAfter($oldWrapper);
		const df = {
			fieldtype: "Autocomplete",
			fieldname: "fen_partner_type",
			label: __("Partner Type"),
			placeholder: __("Partner Type"),
			options: PARTNER_TYPE_OPTIONS,
			condition: "=",
			is_filter: 1,
			input_class: "input-xs",
			onchange: () => listview.filter_area.debounced_refresh_list_view(),
		};

		const ctrl = frappe.ui.form.make_control({
			df,
			parent: $holder,
			only_input: true,
		});
		ctrl.refresh();
		if (currentValue) {
			ctrl.set_input(currentValue);
		}
		$holder
			.attr("title", __("Partner Type"))
			.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });

		$oldWrapper.remove();
		listview.page.fields_dict.fen_partner_type = ctrl;
	}

	function wrapDoctypeListSettings(doctype) {
		const settings = (frappe.listview_settings[doctype] =
			frappe.listview_settings[doctype] || {});
		if (settings._fen_partner_filter_wrapped) return;
		const origOnload = settings.onload;
		settings.onload = function (listview) {
			if (typeof origOnload === "function") {
				origOnload.call(this, listview);
			}
			upgradePartnerTypeFilter(listview);
		};
		settings._fen_partner_filter_wrapped = true;
	}

	TARGET_DOCTYPES.forEach(wrapDoctypeListSettings);
})();

