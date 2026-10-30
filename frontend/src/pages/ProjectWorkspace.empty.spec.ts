import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'
import ProjectWorkspace from './ProjectWorkspace.vue'

vi.mock('@/api', async (orig) => ({
	...(await orig<object>()),
	quoteStatus: vi.fn().mockResolvedValue({ quotation: null }),
}))
vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	toast: { success: vi.fn(), error: vi.fn() },
	useList: (await import('@/test-utils')).fakeUseList({
		'Fenestration Project': [{ name: 'FP-1', project_title: 'Empty', default_series_version: 'CS400-V01' }],
	}),
}))

describe('ProjectWorkspace empty project', () => {
	it('shows zero KPIs and Not quoted', async () => {
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/projects/FP-1')
		await router.isReady()
		const w = mount(ProjectWorkspace, { props: { project: 'FP-1' }, global: { plugins: [router] } })
		await flushPromises()
		const h = w.get('[data-testid="project-header"]')
		expect(h.get('[data-testid="kpi-windows"]').text()).toContain('0')
		expect(h.get('[data-testid="kpi-area"]').text()).toContain('0.000')
		expect(h.get('[data-testid="kpi-weight"]').text()).toContain('0.0')
		expect(h.get('[data-testid="kpi-grand"]').text()).toContain('—')
		expect(h.text()).toContain('Not quoted')
		expect(w.text()).toContain('Designs · 0')
	})
})
