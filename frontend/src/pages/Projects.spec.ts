import { flushPromises, mount } from '@vue/test-utils'
import { Combobox } from 'frappe-ui'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createProject, getProjectOverview } from '@/api'
import { routes } from '@/router'
import Projects from './Projects.vue'

vi.mock('@/api', () => ({ createProject: vi.fn(), getProjectOverview: vi.fn() }))
vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	useList: (await import('@/test-utils')).fakeUseList({
		'Fenestration Project': [
			{ name: 'FP-1', project_title: 'Villa Rose', customer: 'Acme', modified: '2026-01-01' },
			{ name: 'FP-2', project_title: 'Tower Block', customer: 'Beta', modified: '2026-01-02' },
		],
		'Series Version': [
			{ name: 'CS400-V01', series: 'CS400', creation: '2026-01-01 10:00:00' },
			{ name: 'CS400-V05', series: 'CS400', creation: '2026-03-01 10:00:00' },
			{ name: 'CS4800-V06', series: 'CS4800', creation: '2026-02-01 10:00:00' },
		],
		Customer: [{ name: 'Acme Corp' }, { name: 'Beta Ltd' }],
	}),
}))

describe('Projects', () => {
	it('lists projects and filters by search', async () => {
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/projects')
		await router.isReady()
		const w = mount(Projects, { global: { plugins: [router] } })
		expect(w.text()).toContain('Villa Rose')
		expect(w.text()).toContain('Tower Block')
		await w.get('input[type="search"], input[placeholder="Search projects"]').setValue('tower')
		await flushPromises()
		expect(w.text()).not.toContain('Villa Rose')
		expect(w.text()).toContain('Tower Block')
	})
	it('orders versions newest first and labels the latest of each series', async () => {
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/projects')
		await router.isReady()
		const w = mount(Projects, { global: { plugins: [router] }, attachTo: document.body })
		await w.findAll('button').find((b) => b.text() === 'New project')!.trigger('click')
		await flushPromises()
		const select = w.findAllComponents({ name: 'FormControl' }).find((c) => c.props('label') === 'Default series version')!
		expect(select.vm.$attrs.options).toEqual([
			{ label: 'CS400-V05 (latest)', value: 'CS400-V05' },
			{ label: 'CS4800-V06 (latest)', value: 'CS4800-V06' },
			{ label: 'CS400-V01', value: 'CS400-V01' },
		])
		w.unmount()
	})
	it('picks the customer from the Customer list', async () => {
		vi.mocked(createProject).mockResolvedValue('FP-3')
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/projects')
		await router.isReady()
		const w = mount(Projects, { global: { plugins: [router] }, attachTo: document.body })
		await w.findAll('button').find((b) => b.text() === 'New project')!.trigger('click')
		await flushPromises()
		const customer = w.findAllComponents(Combobox).find((c) => c.props('label') === 'Customer (optional)')
		expect(customer, 'customer combobox').toBeTruthy()
		expect(customer!.props('options')).toEqual([
			{ label: 'Acme Corp', value: 'Acme Corp' },
			{ label: 'Beta Ltd', value: 'Beta Ltd' },
		])
		customer!.vm.$emit('update:modelValue', 'Beta Ltd')
		const title = document.querySelector<HTMLInputElement>('input[id]:not([type="search"])')!
		title.value = 'Annex'
		title.dispatchEvent(new Event('input'))
		const dialog = w.findAllComponents({ name: 'FormControl' }).find((c) => c.props('label') === 'Default series version')!
		dialog.vm.$emit('update:modelValue', 'CS400-V01')
		await flushPromises()
		const create = Array.from(document.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Create project')!
		create.click()
		await flushPromises()
		expect(createProject).toHaveBeenCalledWith({
			project_title: 'Annex',
			customer: 'Beta Ltd',
			default_series_version: 'CS400-V01',
			fen_partner_type: 'Dealer',
		})
		w.unmount()
	})

	it('renders KPI stat cards, project progression, and filters by stage', async () => {
		vi.mocked(getProjectOverview).mockResolvedValueOnce({
			stats: {
				total_projects: 2,
				total_designs: 5,
				total_windows: 24,
				quoted_or_ordered: 1,
				in_production: 0,
			},
			projects: [
				{
					name: 'FP-1',
					project_title: 'Villa Rose',
					customer: 'Acme',
					default_series_version: 'CS400-V05',
					modified: '2026-01-01',
					design_count: 2,
					window_qty: 8,
					total_area_sqft: 96.5,
					stage: 'Designing',
				},
				{
					name: 'FP-2',
					project_title: 'Tower Block',
					customer: 'Beta',
					default_series_version: 'CS4800-V06',
					modified: '2026-01-02',
					design_count: 3,
					window_qty: 16,
					total_area_sqft: 210,
					stage: 'Quotation',
				},
			],
		})
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/projects')
		await router.isReady()
		const w = mount(Projects, { global: { plugins: [router] } })
		await flushPromises()

		const cards = w.findAll('[data-slot="project-stat-card"]')
		expect(cards).toHaveLength(4)
		expect(w.text()).toContain('24')
		expect(w.text()).toContain('2 designs')
		expect(w.text()).toContain('16 windows')

		const quotationBtn = w.findAll('button').find((b) => b.text().startsWith('Quotation'))!
		await quotationBtn.trigger('click')
		expect(w.text()).toContain('Tower Block')
		expect(w.text()).not.toContain('Villa Rose')
		w.unmount()
	})

	it('supports filtering and displaying Own Client projects', async () => {
		vi.mocked(getProjectOverview).mockResolvedValueOnce({
			stats: {
				total_projects: 2,
				total_designs: 3,
				total_windows: 10,
				quoted_or_ordered: 0,
				in_production: 0,
			},
			projects: [
				{
					name: 'FP-10',
					project_title: 'Greenwood Villa',
					customer: 'Ramesh Kumar',
					default_series_version: 'CS400-V05',
					modified: '2026-01-03',
					design_count: 2,
					window_qty: 6,
					total_area_sqft: 72,
					stage: 'Designing',
					fen_partner_type: 'Own Client',
				},
				{
					name: 'FP-11',
					project_title: 'Dealer Tower',
					customer: 'Acme',
					default_series_version: 'CS4800-V06',
					modified: '2026-01-02',
					design_count: 1,
					window_qty: 4,
					total_area_sqft: 48,
					stage: 'Designing',
					fen_partner_type: 'Dealer',
				},
			],
		})
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/projects')
		await router.isReady()
		const w = mount(Projects, { global: { plugins: [router] } })
		await flushPromises()

		expect(w.text()).toContain('Own Client')
		const filterSelect = w.findAllComponents({ name: 'FormControl' }).find((c) => c.props('type') === 'select')!
		filterSelect.vm.$emit('update:modelValue', 'Own Client')
		await flushPromises()

		expect(w.text()).toContain('Greenwood Villa')
		expect(w.text()).not.toContain('Dealer Tower')
		w.unmount()
	})
})
