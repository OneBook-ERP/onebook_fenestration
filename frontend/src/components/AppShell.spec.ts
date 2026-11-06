import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'
import AppShell from './AppShell.vue'

vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	useList: (await import('@/test-utils')).fakeUseList({
		'Fenestration Project': [{ name: 'FP-1', project_title: 'Villa Rose', customer: 'C', modified: '2026-01-01' }],
	}),
}))

async function setup(roles: string[]) {
	const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
	router.push('/projects')
	await router.isReady()
	return mount(AppShell, {
		props: { user: 'a@b.c', roles },
		slots: { default: '<p>content</p>' },
		global: { plugins: [router] },
		attachTo: document.body,
	})
}

describe('AppShell', () => {
	// First test: frappe-ui warns about a removed prop only once per module.
	it('mounts without frappe-ui prop warnings', async () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
		const w = await setup(['Sales User'])
		expect(warn.mock.calls.flat().join(' ')).not.toContain('[Dropdown]')
		w.unmount()
		warn.mockRestore()
	})

	it('renders the rail modules and the sidebar sub-navigation', async () => {
		const w = await setup(['Sales User'])
		const text = w.text()
		for (const label of ['Projects', 'Production', 'Install', 'Orders']) {
			expect(w.find(`[aria-label^="${label}"]`).exists(), label).toBe(true)
		}
		for (const label of ['Production', 'Install', 'Orders']) {
			const el = w.get(`[aria-label^="${label}"]`)
			expect(el.attributes('disabled') !== undefined || el.attributes('aria-disabled') === 'true', label).toBe(true)
		}
		expect(text).toContain('All projects')
		expect(text).toContain('Villa Rose')
		expect(w.text()).toContain('content')
		w.unmount()
	})

	it('shows Series Studio only to engineers and switches sidebar on /series-studio', async () => {
		const a = await setup(['Sales User'])
		expect(a.find('[aria-label^="Series Studio"]').exists()).toBe(false)
		a.unmount()

		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/series-studio')
		await router.isReady()
		const b = mount(AppShell, {
			props: { user: 'a@b.c', roles: ['Fenestration Engineer'] },
			slots: { default: '<p>studio content</p>' },
			global: { plugins: [router] },
			attachTo: document.body,
		})
		expect(b.find('[aria-label^="Series Studio"]').exists()).toBe(true)
		expect(b.text()).toContain('Profile Series')
		expect(b.text()).toContain('Series Version')
		expect(b.text()).toContain('Fenestration Profile')
		expect(b.text()).toContain('Fenestration Glass')
		b.unmount()
	})
})
