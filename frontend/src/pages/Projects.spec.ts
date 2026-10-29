import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'
import Projects from './Projects.vue'

vi.mock('@/api', () => ({ createProject: vi.fn() }))
vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	useList: (await import('@/test-utils')).fakeUseList({
		'Fenestration Project': [
			{ name: 'FP-1', project_title: 'Villa Rose', customer: 'Acme', modified: '2026-01-01' },
			{ name: 'FP-2', project_title: 'Tower Block', customer: 'Beta', modified: '2026-01-02' },
		],
		'Series Version': [{ name: 'CS400-V01' }],
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
})
