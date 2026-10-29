export function printPdfUrl(doctype: string, name: string, format: string): string {
	const q = new URLSearchParams({ doctype, name, format, no_letterhead: '0' })
	return `/api/method/frappe.utils.print_format.download_pdf?${q}`
}
