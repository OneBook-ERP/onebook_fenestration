import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'
import ProjectWorkspace from './ProjectWorkspace.vue'

const svg = vi.hoisted(() => '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>')
vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	useList: (await import('@/test-utils')).fakeUseList({
		'Fenestration Project': [
			{ name: 'FP-2026-00001', project_title: 'Villa Rose', default_series_version: 'CS400-V01' },
		],
		'Window Design': [
			{ name: 'WD-1', design_ref: 'W01', qty: 260, series_version: 'CS400-V01', area_sqft: 12.013, window_kg: 10.5, error_count: 1, warning_count: 0, design_svg: svg, location: 'Hall' },
			{ name: 'WD-2', design_ref: 'W02', qty: 60, series_version: 'CS400-V01', area_sqft: 8, window_kg: 5, error_count: 0, warning_count: 0, design_svg: '', location: '' },
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

	it('draws the thumbnail as a data-URI image', async () => {
		const { w } = await setup()
		const img = w.get('[data-testid="design-card"] img')
		expect(img.attributes('src')).toMatch(/^data:image\/svg\+xml/)
		expect(img.attributes('alt')).toBe('Elevation of W01')
	})

	it('New design routes to the designer with the default series version', async () => {
		const { w, router } = await setup()
		await w.get('[data-testid="new-design"]').trigger('click')
		await vi.waitFor(() =>
			expect(router.currentRoute.value.fullPath).toBe('/projects/FP-2026-00001/designs/new?series_version=CS400-V01'),
		)
	})
})
