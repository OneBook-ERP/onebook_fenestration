import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'
import AppShell from './AppShell.vue'

vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	useList: (await import('@/test-utils')).fakeUseList({
		'Fenestration Project': [
			{ name: 'FP-1', project_title: 'Villa Rose', customer: 'C', modified: '2026-01-01' },
			{ name: 'FP-2', project_title: 'Lake View', customer: 'C', modified: '2026-01-02' },
		],
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
		for (const label of ['Projects', 'Quotes', 'Orders', 'Production', 'Install', 'Reports']) {
			const el = w.get(`[aria-label^="${label}"]`)
			expect(el.attributes('disabled')).toBeUndefined()
			expect(el.attributes('aria-disabled')).toBeUndefined()
		}
		expect(text).toContain('All projects')
		expect(text).toContain('Villa Rose')
		expect(w.text()).toContain('content')
		w.unmount()
	})

	it('switches sidebar sub-navigation for common pipeline modules', async () => {
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/quotes')
		await router.isReady()
		const w = mount(AppShell, {
			props: { user: 'a@b.c', roles: ['Sales User'] },
			slots: { default: '<p>quotes</p>' },
			global: { plugins: [router] },
			attachTo: document.body,
		})
		expect(w.text()).toContain('All quotes')
		expect(w.text()).toContain('Draft quotes')
		await router.push('/production')
		await w.vm.$nextTick()
		expect(w.text()).toContain('Work Orders')
		expect(w.text()).toContain('Material Requests')
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

	it('marks only the currently open recent project as active', async () => {
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/projects/FP-1')
		await router.isReady()
		const w = mount(AppShell, {
			props: { user: 'a@b.c', roles: ['Sales User'] },
			slots: { default: '<p>project</p>' },
			global: { plugins: [router] },
			attachTo: document.body,
		})
		const items = w.findAll('[data-slot="sidebar-item"]')
		const villa = items.find((i) => i.text().includes('Villa Rose'))!
		const lake = items.find((i) => i.text().includes('Lake View'))!
		expect(villa.attributes('data-state')).toBe('active')
		expect(lake.attributes('data-state')).toBe('inactive')
		w.unmount()
	})

	it('collapses and expands the secondary sidebar via header, rail expand, and active rail icon', async () => {
		const w = await setup(['Sales User'])
		const nav = w.get('[data-slot="sidebar"]')
		expect(nav.attributes('data-state')).toBe('expanded')

		await w.get('[aria-label="Collapse sidebar"]').trigger('click')
		expect(nav.attributes('data-state')).toBe('collapsed')

		await w.get('[aria-label="Expand sidebar"]').trigger('click')
		expect(nav.attributes('data-state')).toBe('expanded')

		await w.get('[aria-label="Projects"]').trigger('click')
		expect(nav.attributes('data-state')).toBe('collapsed')
		w.unmount()
	})

	it('toggles expandable sidebar nav groups', async () => {
		const w = await setup(['Sales User'])
		const groupTrigger = w.get('[data-slot="sidebar-nav-group"] > button')
		expect(groupTrigger.attributes('aria-expanded')).toBe('true')

		await groupTrigger.trigger('click')
		expect(groupTrigger.attributes('aria-expanded')).toBe('false')
		w.unmount()
	})

	it('opens quick search from the rail and filters projects', async () => {
		const w = await setup(['Sales User'])
		await w.get('[aria-label="Search"]').trigger('click')

		const dialog = document.body.querySelector('[data-slot="sidebar-quick-search"]')
		expect(dialog).not.toBeNull()

		const input = dialog!.querySelector('input') as HTMLInputElement
		input.value = 'Villa'
		input.dispatchEvent(new Event('input'))
		await w.vm.$nextTick()

		expect(dialog!.textContent).toContain('Villa Rose')
		expect(dialog!.textContent).not.toContain('Lake View')
		w.unmount()
	})
})
