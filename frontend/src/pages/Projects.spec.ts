import { flushPromises, mount } from '@vue/test-utils'
import { Combobox } from 'frappe-ui'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createProject } from '@/api'
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
		expect(createProject).toHaveBeenCalledWith({ project_title: 'Annex', customer: 'Beta Ltd', default_series_version: 'CS400-V01' })
		w.unmount()
	})
})
