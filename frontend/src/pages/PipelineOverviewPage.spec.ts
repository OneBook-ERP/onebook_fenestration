import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { getWorkspacePipeline } from '@/api'
import { routes } from '@/router'
import PipelineOverviewPage from './PipelineOverviewPage.vue'

vi.mock('@/api', async (orig) => ({
	...(await orig<object>()),
	getWorkspacePipeline: vi.fn(),
}))

describe('PipelineOverviewPage', () => {
	it('renders overall Quotes stats, filter pills, and project links', async () => {
		vi.mocked(getWorkspacePipeline).mockResolvedValueOnce({
			stats: { total: 2, draft: 1, submitted: 1, ordered: 0, total_value: 25000 },
			items: [
				{
					name: 'SAL-QTN-1',
					fen_project: 'FP-1',
					project_title: 'Villa Rose',
					customer: 'Acme',
					transaction_date: '2026-11-18',
					docstatus: 0,
					status: 'Draft',
					amount: 10000,
					design_count: 2,
					window_qty: 4,
					modified: '2026-11-18',
				},
				{
					name: 'SAL-QTN-2',
					fen_project: 'FP-2',
					project_title: 'Tower Block',
					customer: 'Beta',
					transaction_date: '2026-11-18',
					docstatus: 1,
					status: 'Open',
					amount: 15000,
					design_count: 3,
					window_qty: 6,
					modified: '2026-11-18',
				},
			],
		})
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/quotes')
		await router.isReady()

		const w = mount(PipelineOverviewPage, {
			props: { section: 'quotes' },
			global: { plugins: [router] },
		})
		await flushPromises()

		expect(w.findAll('[data-slot="pipeline-stat-card"]')).toHaveLength(4)
		expect(w.text()).toContain('SAL-QTN-1')
		expect(w.text()).toContain('Villa Rose')
		expect(w.text()).toContain('Tower Block')

		const draftBtn = w.findAll('button').find((b) => b.text().startsWith('Draft'))!
		await draftBtn.trigger('click')
		await flushPromises()
		expect(w.text()).toContain('SAL-QTN-1')
		expect(w.text()).not.toContain('SAL-QTN-2')
		w.unmount()
	})
})

