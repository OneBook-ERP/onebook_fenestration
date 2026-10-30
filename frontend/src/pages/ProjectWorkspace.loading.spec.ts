import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
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
	useList: (options: { doctype: string }) =>
		reactive({
			data: options.doctype === 'Fenestration Project' ? [{ name: 'FP-1', project_title: 'Pending', default_series_version: 'CS400-V01' }] : options.doctype === 'Window Design' ? null : [],
			reload: () => {},
			list: { loading: options.doctype === 'Window Design' },
		}),
}))

describe('ProjectWorkspace first load', () => {
	it('shows a loading state and dashes instead of empty copy and zero KPIs', async () => {
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/projects/FP-1')
		await router.isReady()
		const w = mount(ProjectWorkspace, { props: { project: 'FP-1' }, global: { plugins: [router] } })
		await flushPromises()
		expect(w.text()).toContain('Loading designs…')
		expect(w.text()).not.toContain('No designs yet.')
		for (const id of ['windows', 'area', 'weight', 'value']) {
			expect(w.get(`[data-testid="kpi-${id}"] dd`).text()).toBe('—')
		}
	})
})
