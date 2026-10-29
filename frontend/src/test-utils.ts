import { reactive } from 'vue'

/** Stand-in for frappe-ui's useList: one reactive row set per doctype. */
export function fakeUseList(rowsByDoctype: Record<string, unknown[]>) {
	return (options: { doctype: string }) =>
		reactive({
			data: rowsByDoctype[options.doctype] ?? [],
			reload: () => {},
			list: { loading: false },
		})
}
