import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import ResultsBar from '@/components/ResultsBar.vue'
import { useDesignerStore } from '@/stores/designer'

vi.mock('@/composables/profiles', () => ({ useProfileNames: () => ref({ E104156: 'Outer Frame' }) }))

const member = (o: object) => ({ panel: 'F1', role: 'frame', position: 'L', profile: 'E104156', length: 1219, angles: '[45, 45]', path: 'F1', ...o })
const base = {
	members: [member({}), member({ panel: 'S1' }), member({ angles: [45, 45] })],
	glass: [],
	bom: [
		{ item: 'H1', name: 'Hinge', qty: 2, uom: 'Nos', panel: 'S1', position: '', length: 0, group: 'Hardware' },
		{ item: 'G1', name: 'Gasket A', qty: 1, uom: 'm', panel: 'F1', position: 'T', length: 1500, group: 'Gasket' },
		{ item: 'G1', name: 'Gasket A', qty: 1, uom: 'm', panel: 'F1', position: 'B', length: 1250, group: 'Gasket' },
	],
	shutter_kg: {},
	window_kg: 1,
	area_m2: 1,
	area_sqft: 10.7,
	pricing: { lines: [], unit_price: 1000, rate_per_sqft: 93 },
	issues: [] as object[],
}

function mountBar(result: object | null) {
	const store = useDesignerStore()
	store.result = result as never
	return mount(ResultsBar)
}
const tab = (w: ReturnType<typeof mount>, t: string) => w.findAll('button, [role="radio"]').find((b) => b.text().startsWith(t))!
const headers = (w: ReturnType<typeof mount>) => w.findAll('th').map((h) => h.text())

describe('ResultsBar', () => {
	enableAutoUnmount(afterEach)
	beforeEach(() => {
		setActivePinia(createPinia())
		localStorage.clear()
	})

	it('error pill green when zero, no warnings badge at zero, amber for 2', () => {
		let w = mountBar(base)
		expect(w.text()).toContain('0 errors')
		expect(w.text()).not.toContain('warnings')
		w.unmount()
		w = mountBar({ ...base, issues: [1, 2].map((n) => ({ severity: 'warn', code: 'Y', message: 'm', panel: 'F1', hint: '', path: `F1.${n}` })) })
		expect(w.text()).toContain('2 warnings')
		expect(w.html()).toMatch(/amber/)
		expect(mountBar(base).html()).toMatch(/green/)
	})

	it('cut list columns and grouping', () => {
		const w = mountBar(base)
		expect(headers(w)).toEqual(['Profile', 'Code', 'Length (mm)', 'Angles', 'Qty', 'Position', 'Panel'])
		const text = w.find('tbody').text()
		expect(text).toContain('1219.0')
		expect(text).toContain('45° / 45°')
		expect(text).toContain('Outer Frame')
		expect(w.findAll('tbody tr')).toHaveLength(2)
		expect(w.findAll('tbody tr')[0].text()).toContain('F1')
		expect(w.findAll('tbody tr')[0].findAll('td')[4].text()).toBe('2')
	})

	it('gaskets tab', async () => {
		const w = mountBar(base)
		expect(tab(w, 'Cut list').text()).toBe('Cut list · 2')
		expect(tab(w, 'Hardware').text()).toBe('Hardware · 1')
		expect(tab(w, 'Gaskets').text()).toBe('Gaskets · 1')
		expect(tab(w, 'Glass').text()).toBe('Glass · 0')
		expect(tab(w, 'Issues').text()).toBe('Issues · 0')
		await tab(w, 'Hardware').trigger('click')
		expect(w.find('tbody').text()).not.toContain('Gasket A')
		await tab(w, 'Gaskets').trigger('click')
		expect(headers(w)).toEqual(['Item', 'Name', 'Length (m)'])
		expect(w.find('tbody').text()).toContain('2.750')
	})

	it('renders with no result', () => {
		const w = mountBar(null)
		expect(tab(w, 'Cut list').text()).toBe('Cut list · 0')
		expect(tab(w, 'Gaskets').text()).toBe('Gaskets · 0')
	})

	it('live price label', () => {
		const w = mountBar(base)
		expect(w.text()).toContain('Live price ₹1,000.00')
		expect(w.text()).toContain('From current rates; saved designs keep their priced value until repriced.')
	})

	it('results drawer collapses and persists', async () => {
		const w = mountBar(base)
		const toggle = () => w.findAll('button').find((b) => b.text() === 'Hide results')!
		expect(toggle().attributes('aria-expanded')).toBe('true')
		await toggle().trigger('click')
		expect(w.find('table').exists()).toBe(false)
		expect(w.text()).toContain('Window 1.000 kg')
		expect(localStorage.getItem('fen.resultsCollapsed')).toBe('1')
		const w2 = mountBar(base)
		expect(w2.find('table').exists()).toBe(false)
		expect(w2.findAll('button').find((b) => b.text() === 'Show results')!.attributes('aria-expanded')).toBe('false')
	})
})
