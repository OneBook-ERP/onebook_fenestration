export function deskDocUrl(doctype: string, name: string): string {
	const slug = doctype.toLowerCase().replace(/\s+/g, '-')
	return `/app/${slug}/${encodeURIComponent(name)}`
}

export function statusBadgeClass(status: string, docstatus?: number): string {
	if (docstatus === 2 || status === 'Cancelled' || status === 'Lost') {
		return 'bg-red-50 text-red-700'
	}
	if (docstatus === 0 || status === 'Draft') {
		return 'bg-amber-50 text-amber-700'
	}
	switch (status) {
		case 'Completed':
		case 'Ordered':
		case 'Production':
			return 'bg-emerald-50 text-emerald-700'
		case 'In Process':
		case 'To Deliver and Bill':
		case 'To Deliver':
		case 'Open':
		case 'Designing':
			return 'bg-blue-50 text-blue-700'
		case 'To Bill':
		case 'Order':
		case 'Quotation':
			return 'bg-indigo-50 text-indigo-700'
		default:
			return 'bg-gray-100 text-gray-700'
	}
}

