import { flushPromises, mount } from '@vue/test-utils'
import { toast } from 'frappe-ui'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'
import { copyDesign } from '@/api'
import ProjectWorkspace from './ProjectWorkspace.vue'

vi.mock('@/api', async (orig) => ({
	...(await orig<object>()),
	quoteStatus: vi.fn().mockResolvedValue({ quotation: null }),
	copyDesign: vi.fn(),
}))
const svg = vi.hoisted(() => '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>')
vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	toast: { success: vi.fn(), error: vi.fn() },
	useList: (await import('@/test-utils')).fakeUseList({
		'Fenestration Project': [
			{ name: 'FP-2026-00001', project_title: 'Villa Rose', default_series_version: 'CS400-V01', customer: 'CUST-1', transport_charges: 0, quotation: null },
		],
		Customer: [{ name: 'CUST-1', customer_name: 'Acme Corp' }],
		'Window Design': [
			{ name: 'WD-1', design_ref: 'W01', qty: 260, series_version: 'CS400-V01', area_sqft: 12.013, window_kg: 10.5, error_count: 1, warning_count: 0, design_svg: svg, location: 'Hall', line_total: 4258987.2, pricing_json: JSON.stringify({ priced_on: '2026-10-30T10:15:00' }) },
			{ name: 'WD-2', design_ref: 'W02', qty: 60, series_version: 'CS400-V01', area_sqft: 8, window_kg: 5, error_count: 0, warning_count: 0, design_svg: '', location: '', line_total: 90000, pricing_json: '' },
		],
	}),
}))

async function setup() {
	const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
	router.push('/projects/FP-2026-00001')
	await router.isReady()
	const w = mount(ProjectWorkspace, { props: { project: 'FP-2026-00001' }, global: { plugins: [router] } })
	await flushPromises()
	return { w, router }
}

describe('ProjectWorkspace', () => {
	it('renders cards and totals', async () => {
		const { w } = await setup()
		expect(w.findAll('[data-testid="design-card"]')).toHaveLength(2)
		expect(w.text()).toContain('Villa Rose')
		expect(w.text()).toContain('320 windows')
		expect(w.text()).toContain('W01 × 260')
		expect(w.text()).toContain('3603.380 sq.ft') // 12.013*260 + 8*60
		expect(w.text()).toContain('3030.000 kg') // 10.5*260 + 5*60 = 3030
	})

	it('shows card line totals and the project value', async () => {
		const { w } = await setup()
		const cards = w.findAll('[data-testid="design-card"]')
		expect(cards[0].text()).toContain('₹42,58,987.20')
		expect(cards[1].text()).toContain('₹90,000.00')
		expect(w.text()).toContain('Value ₹43,48,987.20')
	})

	it('draws the thumbnail as a data-URI image', async () => {
		const { w } = await setup()
		const img = w.get('[data-testid="design-card"] img')
		expect(img.attributes('src')).toMatch(/^data:image\/svg\+xml/)
		expect(img.attributes('alt')).toBe('Elevation of W01')
	})

	it('New design lists the templates and routes with the chosen one', async () => {
		const { w, router } = await setup()
		await w.get('[data-testid="new-design"]').trigger('click')
		await flushPromises()
		const items = Array.from(document.body.querySelectorAll('[role="menuitem"]')).map((e) => e.textContent?.trim())
		expect(items).toEqual(['2-sash casement', 'Ventilator', 'Sash · fixed · sash', 'Top light', 'Blank'])
		;(Array.from(document.body.querySelectorAll('[role="menuitem"]'))[0] as HTMLElement).click()
		await vi.waitFor(() =>
			expect(router.currentRoute.value.fullPath).toBe(
				'/projects/FP-2026-00001/designs/new?series_version=CS400-V01&template=casement-2',
			),
		)
	})
	it('Duplicate copies the design and routes to the copy', async () => {
		vi.mocked(copyDesign).mockResolvedValue('WD-9')
		const { w, router } = await setup()
		await w.get('[data-testid="duplicate-design"]').trigger('click')
		expect(copyDesign).toHaveBeenCalledWith('WD-1')
		await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/projects/FP-2026-00001/designs/WD-9'))
	})
	it('Duplicate shows a toast on error and re-enables', async () => {
		vi.mocked(copyDesign).mockRejectedValue(new Error('boom'))
		const { w } = await setup()
		const btn = w.get('[data-testid="duplicate-design"]')
		await btn.trigger('click')
		await flushPromises()
		expect(toast.error).toHaveBeenCalledWith('boom')
		expect(btn.attributes('disabled')).toBeUndefined()
	})
	it('search filters cards case-insensitively', async () => {
		const { w } = await setup()
		await w.get('input[aria-label="Search designs"]').setValue('w02')
		expect(w.findAll('[data-testid="design-card"]')).toHaveLength(1)
		await w.get('input[aria-label="Search designs"]').setValue('hall')
		expect(w.findAll('[data-testid="design-card"]')).toHaveLength(1)
		expect(w.text()).toContain('W01 × 260')
	})
	it('Edit design is a frappe-ui button link to the designer', async () => {
		const { w } = await setup()
		const edit = w.get('[data-testid="design-card"] [data-testid="edit-design"]')
		expect(edit.text()).toBe('Edit design')
		expect(edit.attributes('href')).toBe('/fenestration/projects/FP-2026-00001/designs/WD-1')
		expect(edit.classes().join(' ')).not.toContain('text-ink-blue-3')
		expect(edit.classes().join(' ')).toMatch(/bg-surface|border/)
	})
	it('shows the quote panel and the price stamp on stamped cards only', async () => {
		const { w } = await setup()
		expect(w.text()).toContain('Create quotation')
		const cards = w.findAll('[data-testid="design-card"]')
		expect(cards[0].text()).toContain('Priced 30 Oct 2026')
		expect(cards[1].text()).not.toContain('Priced')
	})
})
