import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { FormControl, Select } from 'frappe-ui'
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

	it('edits the actual louver blade width independently of its blade count', async () => {
		const w = mountPanel([{ type: 'louver', glass: '6CTG', blades: 9 }, fixed], 'F1.0', [])
		const field = w.findAllComponents(FormControl).find(c => c.props('label') === 'Blade width (mm)')!
		expect((field.get('input').element as HTMLInputElement).value).toBe('60')
		await field.get('input').setValue('80')
		const root = useDesignerStore().design.root as any
		expect(root.children[0].bladeWidth).toBe(80)
		expect(root.children[0].blades).toBe(9)
	})

	it('selects glass or metal for the blades alone', async () => {
		const w = mountPanel([{ type: 'louver', glass: '6CTG', blades: 9 }, fixed], 'F1.0', [])
		const buttons = w.get('[aria-label="Blade material"]').findAll('button')
		expect(buttons[0].attributes('aria-pressed')).toBe('true')
		await buttons[1].trigger('click')
		const store = useDesignerStore()
		expect((store.design.root as any).children[0].bladeMaterial).toBe('glass')
		expect((store.design.root as any).children[1]).toEqual(fixed)
		await buttons[0].trigger('click')
		expect((store.design.root as any).children[0].bladeMaterial).toBe('metal')
		expect(w.text()).not.toContain('Beading')
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
		expect(labels).toEqual(expect.arrayContaining(['Opening limiter', 'Fly mesh']))
		const handle = selects().find((c) => c.props('label') === 'Handle')!
		expect(handle.props('modelValue')).toBe('none')
		handle.vm.$emit('update:modelValue', 'single')
		await w.vm.$nextTick()
		expect((useDesignerStore().design.root as never as { children: { handle?: string }[] }).children[0].handle).toBe('single')
		const mesh = selects().find((c) => c.props('label') === 'Fly mesh')!
		mesh.vm.$emit('update:modelValue', 'yes')
		await w.vm.$nextTick()
		const child = () => (useDesignerStore().design.root as never as { children: { mesh?: boolean }[] }).children[0]
		expect(child().mesh).toBe(true)
		mesh.vm.$emit('update:modelValue', 'no')
		await w.vm.$nextTick()
		expect(child().mesh).toBe(false)
	})

	it('limiter and mesh show the effective series default in the Series default label', async () => {
		const w = mountPanel([sash, fixed], 'F1.0', [])
		const first = (label: string) =>
			(w.findAllComponents(Select).find((c) => c.props('label') === label)!.props('options') as { label: string }[])[0].label
		expect(first('Fly mesh')).toBe('Series default')
		useDesignerStore().seriesInfo = { glasses: ['6CTG'], defaults: { limiter: false, mesh: true } }
		await w.vm.$nextTick()
		expect(first('Fly mesh')).toBe('Series default (Yes)')
		expect(first('Opening limiter')).toBe('Series default (No)')
	})

	it('glass options are limited to the series version and keep an unknown current value', async () => {
		const w = mountPanel([sash, { type: 'fixed', glass: 'OLD1' }], 'F1.0', [])
		useDesignerStore().seriesInfo = { glasses: ['5CLR'], defaults: { limiter: false, mesh: false } }
		await w.vm.$nextTick()
		const glass = () => w.findAllComponents(Select).find((c) => c.props('label') === 'Glass')!
		const labels = () => (glass().props('options') as { label: string }[]).map((o) => o.label)
		expect(labels()).toEqual(['5 mm clear (5CLR)', '6CTG (not in this series version)'])
		useDesignerStore().select('F1.1')
		await w.vm.$nextTick()
		expect(labels()).toContain('OLD1 (not in this series version)')
	})

	it('unset option shows "Series default" and clearing writes no keys', async () => {
		const w = mountPanel([{ ...sash, handle: 'single', mesh: true }, fixed], 'F1.0', [])
		const handle = w.findAllComponents(Select).find((c) => c.props('label') === 'Handle')!
		expect((handle.props('options') as { label: string }[])[0].label).toBe('Series default')
		handle.vm.$emit('update:modelValue', 'none')
		w.findAllComponents(Select).find((c) => c.props('label') === 'Fly mesh')!.vm.$emit('update:modelValue', 'none')
		await w.vm.$nextTick()
		const node = (useDesignerStore().design.root as never as { children: object[] }).children[0]
		expect(JSON.parse(JSON.stringify(node))).toEqual(sash)
		expect(Object.keys(node)).not.toEqual(expect.arrayContaining(['handle']))
		expect(Object.keys(node)).not.toEqual(expect.arrayContaining(['mesh']))
	})

	it('fixed panels have no hardware option controls', () => {
		const w = mountPanel([sash, fixed], 'F1.1', [])
		expect(w.text()).not.toContain('Handle')
		expect(w.text()).not.toContain('Fly mesh')
	})

	it('displays explicit sash width/height, glass width/height, mullion M1 dimensions, and hides cards when deselected', async () => {
		const w = mountPanel([sash, sash], 'F1.1', [{ panel: 'F1-S2', path: 'F1.1', width: 475.5, height: 1063 }])
		const store = useDesignerStore()
		store.result = {
			members: [
				{ panel: 'F1-S2', path: 'F1.1', role: 'sash', position: 'B', length: 577 },
				{ panel: 'F1-S2', path: 'F1.1', role: 'sash', position: 'L', length: 1164 },
				{ panel: 'M1', role: 'mullion', profile: 'P403', length: 1116, angles: [90, 90] },
			],
			glass: [{ panel: 'F1-S2', path: 'F1.1', width: 475.5, height: 1063 }],
		} as never
		await w.vm.$nextTick()

		expect(w.text()).toContain('Sash width')
		expect(w.text()).toContain('577 mm')
		expect(w.text()).toContain('Sash height')
		expect(w.text()).toContain('1164 mm')
		expect(w.text()).toContain('Glass width')
		expect(w.text()).toContain('475.5 mm')
		expect(w.text()).toContain('Glass height')
		expect(w.text()).toContain('1063.0 mm')

		// Select center mullion M1
		store.select('M1')
		await w.vm.$nextTick()
		expect(w.text()).toContain('Selected mullion M1')
		expect(w.text()).toContain('1116 mm')
		expect(w.text()).toContain('40 mm')
		expect(w.text()).toContain('600 mm')
		expect(w.text()).toContain('P403')

		// Deselect everything (click outside on workspace)
		store.select('')
		await w.vm.$nextTick()
		expect(w.text()).not.toContain('Selected panel')
		expect(w.text()).not.toContain('Selected mullion')
		expect(w.text()).not.toContain('Split (vertical)')
	})

	it('allows selecting outer frame, glass, sash, and mullion individually and choosing Fenestration Profiles', async () => {
		const w = mountPanel([sash, sash], 'FRAME', [{ panel: 'F1-S1', path: 'F1.0', width: 475.5, height: 1063 }])
		const store = useDesignerStore()
		store.seriesInfo = {
			glasses: ['6CTG', '5CLR'],
			profiles: ['E104156', 'E104160', 'E104159'],
			role_defaults: { frame: 'E104156', sash: 'E104160', mullion: 'E104159' },
			defaults: { limiter: false, mesh: false },
		}
		await w.vm.$nextTick()

		// 1. Outer frame selected ('FRAME')
		expect(w.find('[data-testid="selected-frame-card"]').exists()).toBe(true)
		expect(w.text()).toContain('Selected outer frame F1')
		const frameSelect = w.findAllComponents(Select).find((c) => c.props('label') === 'Frame profile')!
		expect(frameSelect).toBeDefined()
		frameSelect.vm.$emit('update:modelValue', 'E104160')
		await w.vm.$nextTick()
		expect(store.design.profiles?.frame).toBe('E104160')

		// 2. Glass selected ('GLASS:F1.0')
		store.select('GLASS:F1.0')
		await w.vm.$nextTick()
		expect(w.find('[data-testid="selected-glass-card"]').exists()).toBe(true)
		expect(w.text()).toContain('Selected glass F1-S1')

		// 3. Sash selected ('F1.0') -> change Sash profile
		store.select('F1.0')
		await w.vm.$nextTick()
		const sashSelect = w.findAllComponents(Select).find((c) => c.props('label') === 'Sash profile')!
		expect(sashSelect).toBeDefined()
		sashSelect.vm.$emit('update:modelValue', 'E104156')
		await w.vm.$nextTick()
		expect((store.design.root as never as { children: { profile?: string }[] }).children[0].profile).toBe('E104156')

		// 4. Mullion selected ('M1') -> change Mullion profile
		store.select('M1')
		await w.vm.$nextTick()
		const mullionSelect = w.findAllComponents(Select).find((c) => c.props('label') === 'Mullion profile')!
		expect(mullionSelect).toBeDefined()
		mullionSelect.vm.$emit('update:modelValue', 'E104159')
		await w.vm.$nextTick()
		expect(store.design.profiles?.M1).toBe('E104159')
	})

	it('design card is collapsed by default and expands on chevron click', async () => {
		const w = mountPanel([fixed], 'F1', [])
		const expandBtn = w.find('button[aria-label="Expand design details"]')
		expect(expandBtn.exists()).toBe(true)
		const inputsContainer = w.find('input#pp-ref').element.closest('div[style*="display"]')
		// Initially hidden via v-show
		expect(w.find('input#pp-ref').isVisible()).toBe(false)
		await expandBtn.trigger('click')
		expect(w.find('input#pp-ref').isVisible()).toBe(true)
	})

	it('no bead offset or depth fields appear anywhere', () => {
		const w = mountPanel([fixed], 'F1', [])
		expect(w.text()).not.toContain('Bead offset (along, depth)')
		expect(w.find('input[placeholder="0"]').exists()).toBe(false)
	})

	it('selecting a bead shows the "Bead" card with sync and corners, and clears panel card', async () => {
		const w = mountPanel([fixed], 'BEAD:F1', [])
		await w.vm.$nextTick()
		expect(w.find('[data-testid="selected-bead-card"]').exists()).toBe(true)
		expect(w.text()).toContain('Bead')
		expect(w.text()).toContain('Mitre 45°')
		expect(w.text()).toContain('Square')
		expect(w.text()).toContain('Mirror to opposite side')
		expect(w.text()).toContain('Set as default')
		expect(w.text()).toContain('Reset bead')
		// Bead identifier tags are internal only
		expect(w.text()).not.toContain('OBL')
		expect(w.text()).not.toContain('MBR')
	})

	it('selecting nothing shows the empty hint card', async () => {
		const w = mountPanel([fixed], '', [])
		await w.vm.$nextTick()
		expect(w.find('[data-testid="nothing-selected-card"]').exists()).toBe(true)
		expect(w.text()).toContain('Nothing selected')
		expect(w.text()).toContain('Click a panel on the canvas or a profile in the section view')
	})
})
