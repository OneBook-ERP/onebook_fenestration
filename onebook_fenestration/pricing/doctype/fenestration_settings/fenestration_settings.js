frappe.ui.form.on("Fenestration Settings", {
	refresh(frm) {
		const api = "onebook_fenestration.pricing.rate_sheet";
		frm.add_custom_button(
			__("Download rate sheet"),
			() => {
				window.open(`/api/method/${api}.download_rate_sheet`);
			},
			__("Rates")
		);
		frm.add_custom_button(
			__("Import rate sheet"),
			() => {
				new frappe.ui.FileUploader({
					restrictions: { allowed_file_types: [".xlsx"] },
					make_attachments_public: false,
					on_success(file) {
						frappe.call({
							method: `${api}.import_rate_sheet`,
							args: { file_url: file.file_url },
							freeze: true,
							callback: ({ message }) => show_import_result(message),
						});
					},
				});
			},
			__("Rates")
		);
	},
});

function show_import_result(result) {
	const skipped = result.skipped
		.map(
			(s) =>
				`<tr><td>${s.row}</td><td>${frappe.utils.escape_html(
					s.item_code || ""
				)}</td><td>${frappe.utils.escape_html(s.reason)}</td></tr>`
		)
		.join("");
	const table = skipped
		? `<table class="table table-bordered"><thead><tr><th>${__("Row")}</th><th>${__(
				"Item"
		  )}</th><th>${__("Reason")}</th></tr></thead><tbody>${skipped}</tbody></table>`
		: "";
	frappe.msgprint({
		title: __("Rate sheet imported"),
		indicator: skipped ? "orange" : "green",
		message: `<p>${__("Created")}: ${result.created}, ${__("Updated")}: ${
			result.updated
		}, ${__("Unchanged")}: ${result.unchanged}, ${__("Skipped")}: ${
			result.skipped.length
		}</p>${table}`,
		wide: true,
	});
}
