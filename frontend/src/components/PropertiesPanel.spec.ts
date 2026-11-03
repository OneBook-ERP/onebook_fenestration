import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Checkbox, Select } from 'frappe-ui'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PropertiesPanel from '@/components/PropertiesPanel.vue'
import { useDesignerStore } from '@/stores/designer'

const glassState = vi.hoisted(() => ({ loading: false }))
vi.mock('frappe-ui', async (orig) => {
	const { reactive } = await import('vue')
	return {
		...(await orig<object>()),
		useList: () =>
			reactive({
				get data() {
					return glassState.loading
						? undefined
						: [
								{ name: '6CTG', glass_name: '6 mm clear toughened' },
								{ name: '5CLR', glass_name: '5 mm clear' },
							]
				},
				reload: () => {},
				list: { get loading() { return glassState.loading } },
			}),
	}
})

const tree = (leafs: object[]) => ({
	width: 1200,
	height: 1200,
	root: { type: 'split', dir: 'v', at: [600], children: leafs },
})
const result = (glass: object[]) =>
	({ members: [{ panel: 'F1-S1', path: 'F1.0' }, { panel: 'F1-F2', path: 'F1.1' }], glass }) as never

function mountPanel(leafs: object[], selected: string, glass: object[]) {
	const store = useDesignerStore()
	store.reset(tree(leafs) as never, 'SV1', '', '')
	store.select(selected)
	store.result = result(glass)
	return mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
}
const sash = { type: 'sash', glass: '6CTG', opening: 'out', hinge: 'left' }
const fixed = { type: 'fixed', glass: '6CTG' }

describe('PropertiesPanel', () => {
	enableAutoUnmount(afterEach)
	beforeEach(() => {
		setActivePinia(createPinia())
		glassState.loading = false
	})

	it('is full width on phone and w-72 from md', () => {
		const w = mountPanel([], 'F1', [])
		expect(w.get('aside').classes()).toEqual(expect.arrayContaining(['w-full', 'md:w-72']))
	})

	it('panel label: header uses the engine panel id', () => {
		const w = mountPanel([sash, fixed], 'F1.0', [])
		expect(w.text()).toContain('Selected panel F1-S1')
		expect(w.text()).not.toContain('F1.0')
	})

	it('derived sizes: sash shows glass cut size from the matching row', () => {
		const w = mountPanel([sash, fixed], 'F1.0', [{ panel: 'F1-S1', path: 'F1.0', width: 512.34, height: 900 }])
		expect(w.text()).toContain('Glass cut 512.3 × 900.0 mm')
	})

	it('derived sizes: shows a dash when there is no row', () => {
		const w = mountPanel([sash, fixed], 'F1.0', [])
		expect(w.text()).toContain('Glass cut —')
		expect(w.text()).not.toContain('Glass cut 0')
	})

	it('fixed-only selection shows label and glass size without sash fields', () => {
		const w = mountPanel([sash, fixed], 'F1.1', [{ panel: 'F1-F2', path: 'F1.1', width: 400, height: 700 }])
		expect(w.text()).toContain('Selected panel F1-F2')
		expect(w.text()).toContain('Glass cut 400.0 × 700.0 mm')
		expect(w.text()).not.toContain('Opening')
		expect(w.text()).not.toContain('Hinge')
		expect(w.text()).not.toContain('GHH')
	})

	it('glass is a select with named options and keeps unknown values', async () => {
		const w = mountPanel([sash, { type: 'fixed', glass: 'OLD1' }], 'F1.0', [])
		const glass = () => w.findAllComponents(Select).find((c) => c.props('label') === 'Glass')!
		const labels = () => (glass().props('options') as { label: string }[]).map((o) => o.label)
		expect(labels()).toEqual(['6 mm clear toughened (6CTG)', '5 mm clear (5CLR)'])
		expect(glass().props('modelValue')).toBe('6CTG')
		useDesignerStore().select('F1.1')
		await w.vm.$nextTick()
		expect(labels()).toContain('OLD1 (unknown)')
		expect(glass().props('modelValue')).toBe('OLD1')
	})

	it('does not call a code unknown while the glass list is loading', () => {
		glassState.loading = true
		const w = mountPanel([sash, fixed], 'F1.0', [])
		const glass = w.findAllComponents(Select).find((c) => c.props('label') === 'Glass')!
		const labels = (glass.props('options') as { label: string }[]).map((o) => o.label)
		expect(labels).toEqual(['6CTG'])
		expect(labels.join()).not.toContain('unknown')
	})

	it('sash shows hardware option controls and Handle updates the design node', async () => {
		const w = mountPanel([sash, fixed], 'F1.0', [])
		const selects = () => w.findAllComponents(Select)
		const labels = selects().map((c) => c.props('label'))
		expect(labels).toEqual(expect.arrayContaining(['Hinge', 'Hinge type', 'Handle']))
		const checks = w.findAllComponents(Checkbox).map((c) => c.props('label'))
		expect(checks).toEqual(['Opening limiter', 'Fly mesh'])
		const handle = selects().find((c) => c.props('label') === 'Handle')!
		expect(handle.props('modelValue')).toBe('none')
		handle.vm.$emit('update:modelValue', 'single')
		await w.vm.$nextTick()
		expect((useDesignerStore().design.root as never as { children: { handle?: string }[] }).children[0].handle).toBe('single')
		const mesh = w.findAllComponents(Checkbox).find((c) => c.props('label') === 'Fly mesh')!
		mesh.vm.$emit('update:modelValue', true)
		await w.vm.$nextTick()
		expect((useDesignerStore().design.root as never as { children: { mesh?: boolean }[] }).children[0].mesh).toBe(true)
	})

	it('fixed panels have no hardware option controls', () => {
		const w = mountPanel([sash, fixed], 'F1.1', [])
		expect(w.text()).not.toContain('Handle')
		expect(w.findAllComponents(Checkbox)).toHaveLength(0)
	})
})
