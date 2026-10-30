import { flushPromises, mount } from '@vue/test-utils'
import { Combobox, toast } from 'frappe-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { makeQuotation, quoteStatus, repriceProject, setProjectField } from '@/api'
import QuotePanel from './QuotePanel.vue'

vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	useList: (await import('@/test-utils')).fakeUseList({
		Customer: [{ name: 'CUST-1', customer_name: 'Acme Corp' }, { name: 'CUST-2', customer_name: 'Beta Ltd' }],
	}),
	toast: { success: vi.fn(), error: vi.fn() },
}))
vi.mock('@/api', async (orig) => ({
	...(await orig<object>()),
	makeQuotation: vi.fn(),
	quoteStatus: vi.fn(),
	repriceProject: vi.fn(),
	setProjectField: vi.fn(),
}))

const base = { name: 'FP-1', customer: 'CUST-1', transport_charges: 0, quotation: null as string | null }

async function setup(info = base) {
	const w = mount(QuotePanel, { props: { project: 'FP-1', info } })
	await flushPromises()
	return w
}
const btn = (w: ReturnType<typeof mount>, label: string) => w.findAll('button, a').find((b) => b.text() === label)!

beforeEach(() => {
	vi.clearAllMocks()
	vi.mocked(quoteStatus).mockResolvedValue({ quotation: null })
	vi.mocked(setProjectField).mockResolvedValue({})
})

describe('QuotePanel', () => {
	it('saves the selected customer through set_value', async () => {
		const w = await setup()
		const cb = w.findAllComponents(Combobox).find((c) => c.props('label') === 'Customer')!
		expect(cb.props('options')).toEqual([
			{ label: 'Acme Corp', value: 'CUST-1' },
			{ label: 'Beta Ltd', value: 'CUST-2' },
		])
		cb.vm.$emit('update:modelValue', 'CUST-2')
		await flushPromises()
		expect(setProjectField).toHaveBeenCalledWith('FP-1', 'customer', 'CUST-2')
		expect(w.emitted('changed')).toBeTruthy()
	})

	it('saves transport charges on blur', async () => {
		vi.useFakeTimers()
		const w = await setup()
		const input = w.get('input[type="number"]')
		await input.setValue('1500')
		await input.trigger('blur')
		await vi.advanceTimersByTimeAsync(500)
		vi.useRealTimers()
		expect(setProjectField).toHaveBeenCalledWith('FP-1', 'transport_charges', 1500)
	})

	it('Create quotation calls make_quotation and shows status with grand total', async () => {
		vi.mocked(makeQuotation).mockResolvedValue({ ok: true, quotation: 'QTN-1' })
		const w = await setup()
		vi.mocked(quoteStatus).mockResolvedValue({ quotation: 'QTN-1', docstatus: 0, grand_total: 118000 })
		await btn(w, 'Create quotation').trigger('click')
		await flushPromises()
		expect(makeQuotation).toHaveBeenCalledWith('FP-1')
		expect(toast.success).toHaveBeenCalledWith('Quotation QTN-1 created')
		expect(w.text()).toContain('Draft')
		expect(w.text()).toContain('₹1,18,000.00')
		expect(btn(w, 'Update quotation')).toBeTruthy()
		expect(w.emitted('changed')).toBeTruthy()
	})

	it('shows the gate message when make_quotation refuses', async () => {
		vi.mocked(makeQuotation).mockResolvedValue({ ok: false, message: 'W01 has errors' })
		const w = await setup()
		await btn(w, 'Create quotation').trigger('click')
		await flushPromises()
		expect(toast.error).toHaveBeenCalledWith('W01 has errors')
		expect(toast.success).not.toHaveBeenCalled()
	})

	it('labels Update and announces updated when a draft exists', async () => {
		vi.mocked(quoteStatus).mockResolvedValue({ quotation: 'QTN-1', docstatus: 0, grand_total: 100 })
		vi.mocked(makeQuotation).mockResolvedValue({ ok: true, quotation: 'QTN-1' })
		const w = await setup({ ...base, quotation: 'QTN-1' })
		await btn(w, 'Update quotation').trigger('click')
		await flushPromises()
		expect(toast.success).toHaveBeenCalledWith('Quotation QTN-1 updated')
	})

	it('links the three PDFs; disabled without a quotation', async () => {
		vi.mocked(quoteStatus).mockResolvedValue({ quotation: 'QTN-1', docstatus: 1, grand_total: 100 })
		const w = await setup({ ...base, quotation: 'QTN-1' })
		expect(w.text()).toContain('Submitted')
		const q = 'no_letterhead=0'
		expect(btn(w, 'Quotation').attributes('href')).toBe(
			`/api/method/frappe.utils.print_format.download_pdf?doctype=Quotation&name=QTN-1&format=Fenestration+Quotation&${q}`,
		)
		expect(btn(w, 'Elevation Report').attributes('href')).toContain('doctype=Fenestration+Project&name=FP-1&format=Fenestration+Elevation')
		expect(btn(w, 'Estimate Confirmation').attributes('href')).toContain('format=Fenestration+Estimate+Confirmation')
		expect(btn(w, 'Assembly Summary').attributes('href')).toContain(
			'download_pdf?doctype=Fenestration+Project&name=FP-1&format=Fenestration+Assembly+Summary',
		)
		expect(btn(w, 'Assembly Detail').attributes('href')).toContain(
			'doctype=Fenestration+Project&name=FP-1&format=Fenestration+Assembly+Detail',
		)
		vi.mocked(quoteStatus).mockResolvedValue({ quotation: null })
		const none = await setup()
		expect(btn(none, 'Quotation').attributes('href')).toBeUndefined()
		expect(btn(none, 'Quotation').attributes('disabled')).toBeDefined()
		expect(btn(none, 'Elevation Report').attributes('href')).toBeTruthy()
	})

	it('Reprice calls the API, toasts and emits repriced', async () => {
		vi.mocked(repriceProject).mockResolvedValue({ repriced: 3, failed: [{ design: 'WD-9', message: 'x' }] })
		const w = await setup()
		await btn(w, 'Reprice').trigger('click')
		await flushPromises()
		expect(repriceProject).toHaveBeenCalledWith('FP-1')
		expect(toast.success).toHaveBeenCalledWith('Repriced 3 designs, 1 failed')
		expect(w.emitted('repriced')).toBeTruthy()
	})

	it('retries the transport save after a failed one', async () => {
		vi.useFakeTimers()
		vi.mocked(setProjectField).mockRejectedValueOnce(new Error('denied'))
		const w = await setup()
		const input = w.get('input[type="number"]')
		await input.setValue('900')
		await input.trigger('blur')
		await vi.advanceTimersByTimeAsync(500)
		expect(toast.error).toHaveBeenCalledWith('denied')
		await input.trigger('blur')
		await vi.advanceTimersByTimeAsync(500)
		vi.useRealTimers()
		expect(setProjectField).toHaveBeenCalledTimes(2)
	})

	it('toasts a status refresh failure without unhandled rejection', async () => {
		vi.mocked(quoteStatus).mockRejectedValue(new Error('status down'))
		const w = await setup({ ...base, quotation: 'QTN-1' })
		expect(toast.error).toHaveBeenCalledWith('status down')
		expect(w.exists()).toBe(true)
	})

	it('reports make_quotation success even when the status refresh fails', async () => {
		vi.mocked(makeQuotation).mockResolvedValue({ ok: true, quotation: 'QTN-1' })
		const w = await setup()
		vi.mocked(quoteStatus).mockRejectedValue(new Error('status down'))
		await btn(w, 'Create quotation').trigger('click')
		await flushPromises()
		expect(toast.success).toHaveBeenCalledWith('Quotation QTN-1 created')
		expect(toast.error).toHaveBeenCalledWith('status down')
		expect(toast.error).not.toHaveBeenCalledWith('Quotation failed')
	})

	it('refreshes status once after make_quotation', async () => {
		vi.mocked(makeQuotation).mockResolvedValue({ ok: true, quotation: 'QTN-1' })
		const w = await setup()
		vi.mocked(quoteStatus).mockClear()
		vi.mocked(quoteStatus).mockResolvedValue({ quotation: 'QTN-1', docstatus: 0, grand_total: 1 })
		await btn(w, 'Create quotation').trigger('click')
		await flushPromises()
		await w.setProps({ info: { ...base, quotation: 'QTN-1' } })
		await flushPromises()
		expect(quoteStatus).toHaveBeenCalledTimes(1)
	})

	it('clears the customer with an empty value', async () => {
		const w = await setup()
		w.findAllComponents(Combobox).find((c) => c.props('label') === 'Customer')!.vm.$emit('update:modelValue', null)
		await flushPromises()
		expect(setProjectField).toHaveBeenCalledWith('FP-1', 'customer', '')
	})

	it('shows the rounded total when present, else the grand total', async () => {
		vi.mocked(quoteStatus).mockResolvedValue({ quotation: 'QTN-1', docstatus: 0, grand_total: 1000.4, rounded_total: 1000 })
		const w = await setup({ ...base, quotation: 'QTN-1' })
		expect(w.get('[data-testid="quote-status"]').text()).toContain('₹1,000.00')
		expect(w.get('[data-testid="quote-status"]').text()).not.toContain('1,000.40')
	})

	it('warns which designs changed since the quotation', async () => {
		vi.mocked(quoteStatus).mockResolvedValue({
			quotation: 'QTN-1',
			docstatus: 0,
			grand_total: 100,
			is_stale: true,
			stale: { changed: ['W01'], added: ['W09'], removed: ['W02 — 2 sash'], transport_changed: true },
		})
		const w = await setup({ ...base, quotation: 'QTN-1' })
		const alert = w.get('[data-testid="quote-stale"]')
		expect(alert.text()).toContain('Designs changed since quotation')
		for (const text of ['W01', 'W09', 'W02 — 2 sash', 'Transport']) expect(alert.text()).toContain(text)
		expect(btn(w, 'Update quotation')).toBeTruthy()
	})

	it('hides the stale warning for a fresh quotation', async () => {
		vi.mocked(quoteStatus).mockResolvedValue({
			quotation: 'QTN-1',
			docstatus: 0,
			grand_total: 100,
			is_stale: false,
			stale: { changed: [], added: [], removed: [], transport_changed: false },
		})
		const w = await setup({ ...base, quotation: 'QTN-1' })
		expect(w.find('[data-testid="quote-stale"]').exists()).toBe(false)
	})
})
