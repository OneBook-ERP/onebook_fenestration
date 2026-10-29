import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { computeDesign, saveDesign } from '@/api'
import { routes } from '@/router'
import { useDesignerStore } from '@/stores/designer'
import Designer from './Designer.vue'

vi.mock('@/api', () => ({ computeDesign: vi.fn(), saveDesign: vi.fn(), getDesign: vi.fn() }))
vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	toast: { success: vi.fn(), error: vi.fn() },
}))

const result = {
	members: [
		{ panel: 'F1', role: 'frame', position: 'top', profile: 'P1', length: 900, angles: '45/45', path: 'F1' },
		{ panel: 'F1', role: 'frame', position: 'bottom', profile: 'P1', length: 900, angles: '45/45', path: 'F1' },
	],
	glass: [{ panel: 'F1', number: 1, glass: '6CTG', width: 800, height: 900, path: 'F1' }],
	bom: [{ item: 'I', name: 'Hinge', qty: 2, uom: 'Nos', panel: 'S1', position: '', length: 0, group: 'Hardware' }],
	shutter_kg: { S1: 4.5 },
	window_kg: 10.1234,
	area_m2: 1.116,
	area_sqft: 12.013,
	issues: [{ severity: 'Error', code: 'X', message: 'Too wide', panel: 'F1', hint: '', path: 'F1.0' }],
}

async function setup() {
	const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
	router.push('/projects/P1/designs/new?series_version=SV1')
	await router.isReady()
	const wrapper = mount(Designer, { global: { plugins: [router] } })
	await flushPromises()
	return { wrapper, router }
}

describe('Designer page', () => {
	beforeEach(() => {
		setActivePinia(createPinia())
		vi.useFakeTimers()
		vi.mocked(computeDesign).mockResolvedValue({ ok: true, result } as never)
		vi.mocked(saveDesign).mockReset()
	})
	afterEach(() => vi.useRealTimers())

	it('split vertical shows M1 on canvas', async () => {
		const { wrapper } = await setup()
		await wrapper.find('[data-path="F1"]').trigger('click')
		await wrapper.find('button[aria-label="Split vertical"]').trigger('click')
		expect(wrapper.find('svg').text()).toContain('M1')
	})

	it('results bar shows computed area', async () => {
		const { wrapper } = await setup()
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		expect(wrapper.text()).toContain('12.013')
		expect(wrapper.text()).toContain('10.123')
	})

	it('save sends svg and width 915', async () => {
		vi.mocked(saveDesign).mockResolvedValue({ ok: true, name: 'WD-1', results: {} } as never)
		const { wrapper, router } = await setup()
		await wrapper.find('input[aria-label="Design ref"]').setValue('W01')
		const w = wrapper.find('input[aria-label="Width"]')
		await w.setValue('915')
		await w.trigger('change')
		await wrapper.find('button[aria-label="Save"]').trigger('click')
		await flushPromises()
		const args = vi.mocked(saveDesign).mock.calls[0][0]
		expect(args.svg.startsWith('<svg')).toBe(true)
		expect(args.design.width).toBe(915)
		expect(args.design_ref).toBe('W01')
		expect(router.currentRoute.value.path).toBe('/projects/P1/designs/WD-1')
	})

	it('save without ref shows validation and does not call api', async () => {
		const { wrapper } = await setup()
		await wrapper.find('button[aria-label="Save"]').trigger('click')
		expect(wrapper.text()).toContain('Design ref is required')
		expect(saveDesign).not.toHaveBeenCalled()
	})

	it('clicking an issue row selects its path', async () => {
		const { wrapper } = await setup()
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		const tab = wrapper.findAll('button[role="tab"]').find((b) => b.text().startsWith('Issues'))!
		await tab.trigger('click')
		await wrapper.find('[data-issue-path="F1.0"]').trigger('click')
		expect(useDesignerStore().selectedPath).toBe('F1.0')
	})
})
