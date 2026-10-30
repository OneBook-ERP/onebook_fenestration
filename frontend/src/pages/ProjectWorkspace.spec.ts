import { flushPromises, mount } from '@vue/test-utils'
import { toast } from 'frappe-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'
import { copyDesign, quoteStatus } from '@/api'
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
		'Profile Finish': [{ name: 'RAL9016', finish_name: 'White', color: '#f4f4f4' }],
		Customer: [{ name: 'CUST-1', customer_name: 'Acme Corp' }],
		'Window Design': [
			{ name: 'WD-1', design_ref: 'W01', qty: 260, series_version: 'CS400-V01', area_sqft: 12.013, window_kg: 10.5, error_count: 1, warning_count: 0, design_svg: svg, location: 'Hall', finish: 'RAL9016', design_json: JSON.stringify({ width: 1000, height: 1000, root: { type: 'split', dir: 'v', at: [500], children: [{ type: 'sash', glass: '5mm Clear' }, { type: 'sash', glass: '5mm Clear' }] } }), line_total: 4258987.2, pricing_json: JSON.stringify({ priced_on: '2026-10-30T10:15:00' }) },
			{ name: 'WD-2', design_ref: 'W02', qty: 60, series_version: 'CS400-V01', area_sqft: 8, window_kg: 5, error_count: 0, warning_count: 0, design_svg: '', location: '', finish: '', design_json: JSON.stringify({ width: 1000, height: 1000, root: { type: 'fixed', glass: 'Tinted' } }), line_total: 90000, pricing_json: '' },
		],
	}),
}))

beforeEach(() => {
	vi.mocked(quoteStatus).mockReset()
	vi.mocked(quoteStatus).mockResolvedValue({ quotation: null })
})

async function setup(query = '') {
	const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
	router.push('/projects/FP-2026-00001' + query)
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
				expect(w.text()).toContain('W01 · 2-sash casement')
	})

	it('shows card line totals and the project value', async () => {
		const { w } = await setup()
		const cards = w.findAll('[data-testid="design-card"]')
		expect(cards[0].text()).toContain('₹42,58,987.20')
		expect(cards[1].text()).toContain('₹90,000.00')
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
	it('Duplicate is disabled while the copy is pending', async () => {
		let resolve!: (v: string) => void
		vi.mocked(copyDesign).mockReturnValue(new Promise<string>((r) => (resolve = r)))
		const { w } = await setup()
		const btn = w.get('[data-testid="duplicate-design"]')
		await btn.trigger('click')
		expect(btn.attributes('disabled')).toBeDefined()
		resolve('WD-9')
		await flushPromises()
	})
	it('a failed navigation after copy is not reported as Copy failed', async () => {
		vi.mocked(toast.error).mockClear()
		vi.mocked(copyDesign).mockResolvedValue('WD-9')
		const { w, router } = await setup()
		vi.spyOn(router, 'push').mockRejectedValue(new Error('nav'))
		await w.get('[data-testid="duplicate-design"]').trigger('click')
		await flushPromises()
		expect(toast.error).not.toHaveBeenCalledWith('Copy failed')
		expect(toast.error).not.toHaveBeenCalledWith('nav')
		expect(toast.error).toHaveBeenCalledWith('Copied as WD-9, but could not open it')
	})
	it('New design button has a 36px touch target', async () => {
		const { w } = await setup()
		expect(w.get('[data-testid="new-design"]').classes()).toContain('min-h-9')
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
		expect(w.text()).toContain('W01 · ')
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
		await w.findAll('[role="tab"]')[1].trigger('click')
		await flushPromises()
		expect(w.text()).toContain('Create quotation')
		await w.findAll('[role="tab"]')[0].trigger('click')
		await flushPromises()
		const cards = w.findAll('[data-testid="design-card"]')
		expect(cards[0].text()).toContain('Priced 30 Oct 2026')
		expect(cards[1].text()).not.toContain('Priced')
	})

	describe('tabs', () => {
		it('labels, disabled tabs and tab content', async () => {
			const { w } = await setup()
			const tabs = w.findAll('[role="tab"]')
			expect(tabs.map((t) => t.text())).toEqual(['Designs · 2', 'Quote', 'Order', 'Production', 'Install', 'Reports'])
			expect(tabs.slice(2).every((t) => t.attributes('aria-disabled') === 'true' && t.attributes('disabled') === undefined)).toBe(true)
			expect(tabs[2].attributes('aria-describedby')).toBeTruthy()
			expect(w.get(`#${tabs[2].attributes('aria-describedby')}`).text()).toBe('Coming soon')
			expect(w.get('[role="tablist"]').element.children.length).toBe(6)
			expect(tabs[0].attributes('aria-selected')).toBe('true')
			expect(w.get('[role="tabpanel"]').attributes('aria-labelledby')).toBe(tabs[0].attributes('id'))
			await tabs[2].trigger('click')
			await flushPromises()
			expect(w.findAll('[data-testid="design-card"]')).toHaveLength(2)
			expect(w.find('[data-testid="quote-panel"]').exists()).toBe(false)
			expect(w.findAll('[data-testid="design-card"]')).toHaveLength(2)
			await tabs[1].trigger('click')
			await flushPromises()
			expect(w.find('[data-testid="quote-panel"]').exists()).toBe(true)
			expect(w.findAll('[data-testid="design-card"]')).toHaveLength(0)
		})
		it('?tab=quote opens Quote', async () => {
			const { w } = await setup('?tab=quote')
			expect(w.find('[data-testid="quote-panel"]').exists()).toBe(true)
			expect(w.findAll('[data-testid="design-card"]')).toHaveLength(0)
		})
		it.each(['?tab=bogus', '?tab=order'])('%s falls back to Designs', async (q) => {
			const { w } = await setup(q)
			expect(w.findAll('[data-testid="design-card"]')).toHaveLength(2)
			expect(w.find('[data-testid="quote-panel"]').exists()).toBe(false)
		})
		it('clicking a tab syncs the query', async () => {
			const { w, router } = await setup()
			await w.findAll('[role="tab"]')[1].trigger('click')
			await flushPromises()
			expect(router.currentRoute.value.query.tab).toBe('quote')
		})
	})

	describe('header', () => {
		const header = (w: Awaited<ReturnType<typeof setup>>['w']) => w.get('[data-testid="project-header"]')
		it('breadcrumb, title, KPIs and Not quoted badge', async () => {
			const { w } = await setup()
			const crumb = w.get('[data-testid="breadcrumb-projects"]')
			expect(crumb.text()).toBe('Projects')
			expect(crumb.attributes('href')).toBe('/fenestration/projects')
			const h = header(w)
			expect(h.text()).toContain('FP-2026-00001')
			expect(h.text()).toContain('Villa Rose')
			expect(h.text()).toContain('Not quoted')
			expect(h.get('[data-testid="kpi-windows"]').text()).toContain('320')
			expect(h.get('[data-testid="kpi-area"]').text()).toContain('3603.380')
			expect(h.get('[data-testid="kpi-weight"]').text()).toContain('3030.0')
			expect(h.get('[data-testid="kpi-value"]').text()).toContain('₹43,48,987.20')
			expect(h.get('[data-testid="kpi-grand"]').text()).toContain('—')
		})
		it('does not claim Not quoted when the status call fails', async () => {
			vi.mocked(quoteStatus).mockRejectedValue(new Error('down'))
			const { w } = await setup()
			const h = header(w)
			expect(h.text()).toContain('Status unavailable')
			expect(h.text()).not.toContain('Not quoted')
			expect(h.get('[data-testid="kpi-grand"]').text()).toContain('—')
		})
		it('draft quote', async () => {
			vi.mocked(quoteStatus).mockResolvedValue({ quotation: 'QTN-1', docstatus: 0, status: 'Draft', rounded_total: 5130000 })
			const { w } = await setup()
			const h = header(w)
			expect(h.text()).toContain('Draft quote')
			expect(h.text()).toContain('QTN-1')
			expect(h.get('[data-testid="kpi-grand"]').text()).toContain('₹51,30,000.00')
		})
		it('submitted quote shows its status; stale wins', async () => {
			vi.mocked(quoteStatus).mockResolvedValue({ quotation: 'QTN-1', docstatus: 1, status: 'Open', rounded_total: 1 })
			let { w } = await setup()
			expect(header(w).text()).toContain('Open')
			vi.mocked(quoteStatus).mockResolvedValue({ quotation: 'QTN-1', docstatus: 1, status: 'Open', rounded_total: 1, is_stale: true })
			;({ w } = await setup())
			expect(header(w).text()).toContain('Out of date')
		})
	})

	describe('card details', () => {
		it('shows typology, glass, finish, ok badge and footer', async () => {
			vi.mocked(quoteStatus).mockResolvedValue({ quotation: null })
			const { w } = await setup()
			const [c1, c2] = w.findAll('[data-testid="design-card"]')
			expect(c1.text()).toContain('W01 · 2-sash casement')
			expect(c1.text()).toContain('× 260')
			expect(c1.text()).toContain('CS400-V01 · 5mm Clear')
			expect(c1.text()).toContain('White')
			expect(c1.get('[data-testid="finish-swatch"]').attributes('style')).toContain('background-color')
			expect(c1.text()).not.toContain('OK')
			expect(c1.text()).toContain('12.013 sq.ft · 10.5 kg')
			expect(c1.text()).toContain('Saved price ₹42,58,987.20')
			expect(c1.text()).toContain('Priced 30 Oct 2026')
			expect(c2.text()).toContain('OK')
			expect(c2.text()).toContain('8.000 sq.ft · 5.0 kg')
			expect(c2.text()).toContain('W02 · Fixed')
			expect(c2.text()).toContain('—')
		})
	})
})
