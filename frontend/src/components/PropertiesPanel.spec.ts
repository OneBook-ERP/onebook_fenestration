import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { FormControl, Select } from 'frappe-ui'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PropertiesPanel from '@/components/PropertiesPanel.vue'
import { useDesignerStore } from '@/stores/designer'

const glassState = vi.hoisted(() => ({ loading: false, includeBeadProfile: false, rotateFrame: false }))
vi.mock('frappe-ui', async (orig) => {
	const { reactive } = await import('vue')
	return {
		...(await orig<object>()),
		useList: (opts?: { doctype?: string }) =>
			reactive({
				get data() {
					if (opts?.doctype === 'Fenestration Profile') {
						return [
							{
								name: 'E104156',
								profile_code: 'E104156',
								profile_name: '40mm Casement Frame',
								role: 'frame',
								width_mm: glassState.rotateFrame ? 50 : 42,
								depth_mm: glassState.rotateFrame ? 42 : 50,
								section_svg: 'M 0 0 L 42 0 L 42 50 L 0 50 Z',
								...(glassState.rotateFrame
									? { section_rotation: '90', section_flip_x: 1, section_flip_y: 0 }
									: {}),
							},
							{
								name: 'E104160',
								profile_code: 'E104160',
								profile_name: '40mm Casement Sash',
								role: 'sash',
								width_mm: 60,
								depth_mm: 40,
								section_svg: 'M 0 0 L 60 0 L 60 40 L 0 40 Z',
							},
							{
								name: 'E104159',
								profile_code: 'E104159',
								profile_name: '40mm Casement Mullion',
								role: 'mullion',
								width_mm: 60,
								depth_mm: 55,
								section_svg: 'M 0 0 L 60 0 L 60 55 L 0 55 Z',
							},
							...(glassState.includeBeadProfile
								? [
										{
											name: 'CS4807-CS400',
											profile_code: 'CS4807-CS400',
											profile_name: '6 & 8mm Glass Beading',
											role: 'bead',
											width_mm: 23,
											depth_mm: 20,
											section_svg: 'M 0 0 L 23 0 L 23 20 L 0 20 Z',
										},
									]
								: []),
						]
					}
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
		glassState.includeBeadProfile = false
		glassState.rotateFrame = false
	})

	it('edits and removes an exhaust cut on the selected glass only', async () => {
		const w = mountPanel([{ ...fixed, fan: true }, fixed], 'F1.0', [{ panel: 'F1-S1', path: 'F1.0', width: 540, height: 1140 }])
		const field = (label: string) => w.findAllComponents(FormControl).find(c => c.props('label') === label)!.get('input')
		expect(w.get('[data-testid="steel-infill"]').text()).toBe('Steel sheet')
		expect(w.findAllComponents(Select).some(c => c.props('label') === 'Glass')).toBe(false)
		await field('Steel thickness (mm)').setValue('2')
		expect((useDesignerStore().design.root as any).children[0].steelThickness).toBe(2)
		expect((field('Cut diameter (mm)').element as HTMLInputElement).value).toBe('180')
		expect((field('Centre from panel left (mm)').element as HTMLInputElement).value).toBe('270')
		expect((field('Centre from panel top (mm)').element as HTMLInputElement).value).toBe('570')
		await field('Cut diameter (mm)').setValue('200')
		expect((field('Centre from panel left (mm)').element as HTMLInputElement).value).toBe('270')
		expect((field('Centre from panel top (mm)').element as HTMLInputElement).value).toBe('570')
		await field('Centre from panel left (mm)').setValue('250')
		await field('Centre from panel top (mm)').setValue('300')
		const store = useDesignerStore()
		expect((store.design.root as any).children[0].fanCut).toEqual({ diameter: 200, centerX: 250, centerY: 300 })
		expect((store.design.root as any).children[1]).toEqual(fixed)
		expect(w.find('[role="alert"]').exists()).toBe(false)
		await field('Cut diameter (mm)').setValue('1000')
		expect(w.get('[role="alert"]').text()).toContain('inside the panel')
		await w.get('[data-testid="exhaust-cut-controls"]').findAll('button').find(b => b.text() === 'Remove cut')!.trigger('click')
		expect((store.design.root as any).children[0].fan).toBe(false)
		expect(w.find('[data-testid="exhaust-cut-controls"]').exists()).toBe(false)
		expect(w.findAllComponents(Select).some(c => c.props('label') === 'Glass')).toBe(true)
		expect((store.design.root as any).children[0].glass).toBe('6CTG')
	})

	it('opens grill properties directly and edits only its selected panel', async () => {
 const w=mountPanel([{...fixed,grill:{}},fixed],'GRILL:F1.0',[])
 expect(w.text()).toContain('Grill · F1-S1')
 expect(w.findAllComponents(Select).some(c=>c.props('label')==='Glass')).toBe(false)
 const field=w.findAllComponents(FormControl).find(c=>c.props('label')==='Vertical bars')!
 await field.get('input').setValue('5')
 expect((useDesignerStore().design.root as any).children[0].grill.vertical).toBe(5)
 expect((useDesignerStore().design.root as any).children[1].grill).toBeUndefined()
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
		const w = mountPanel([{ type: 'louver', glass: '6CTG', blades: 9 }], 'F1.0', [])
		const buttons = w.get('[aria-label="Blade material"]').findAll('button')
		expect(buttons[0].attributes('aria-pressed')).toBe('true')
		await buttons[1].trigger('click')
		const store = useDesignerStore()
		expect((store.design.root as any).children[0].bladeMaterial).toBe('glass')
		await buttons[0].trigger('click')
		expect((store.design.root as any).children[0].bladeMaterial).toBe('metal')
		expect(w.text()).not.toContain('Beading')
	})

	it('is full width on phone and w-72 from md', () => {
		const w = mountPanel([], 'F1', [])
		expect(w.get('aside').classes()).toEqual(expect.arrayContaining(['w-full', 'md:w-72']))
	})

	it('panel label: badge uses the engine panel id', () => {
		const w = mountPanel([sash, fixed], 'F1.0', [])
		expect(w.get('[data-testid="series-sub-sash"]').text()).toContain('F1-S1')
		expect(w.get('[data-testid="series-sub-sash"]').text()).not.toContain('F1.0')
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

	it('fixed-only design shows label and glass size without sash fields', () => {
		const w = mountPanel([fixed, fixed], 'F1.1', [{ panel: 'F1-F2', path: 'F1.1', width: 400, height: 700 }])
		const glassText = w.get('[data-testid="series-sub-glass"]').text()
		expect(glassText).toContain('G1')
		expect(glassText).toContain('G2')
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

	it('fixed-only design has no hardware option controls', () => {
		const w = mountPanel([fixed, fixed], 'F1.1', [])
		expect(w.text()).not.toContain('Handle')
		expect(w.text()).not.toContain('Fly mesh')
	})

	it('displays explicit sash width/height, glass width/height, mullion M1 dimensions, and keeps properties visible inline when deselected', async () => {
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
		expect(w.get('[data-testid="series-sub-mullion"]').text()).toContain('M1 position (mm)')
		expect(w.text()).toContain('1116 mm')
		expect(w.text()).toContain('40 mm')
		expect(w.text()).toContain('600 mm')
		expect(w.text()).toContain('P403')

		// Deselect everything: inline properties stay accessible directly under SERIES & PROFILES, no separate selection card
		store.select('')
		await w.vm.$nextTick()
		expect(w.find('[data-testid="selected-panel-card"]').exists()).toBe(false)
		expect(w.find('[data-testid="nothing-selected-card"]').exists()).toBe(false)
		expect(w.find('[data-testid="series-sub-sash"]').exists()).toBe(true)
		expect(w.find('[data-testid="series-sub-mullion"]').exists()).toBe(true)
	})

	it('allows selecting outer frame, glass, sash, and mullion individually and choosing Fenestration Profiles without duplicate selectors', async () => {
		const w = mountPanel([sash, sash], 'FRAME', [{ panel: 'F1-S1', path: 'F1.0', width: 475.5, height: 1063 }])
		const store = useDesignerStore()
		store.seriesInfo = {
			glasses: ['6CTG', '5CLR'],
			profiles: ['E104156', 'E104160', 'E104159'],
			role_defaults: { frame: 'E104156', sash: 'E104160', mullion: 'E104159' },
			defaults: { limiter: false, mesh: false },
		}
		await w.vm.$nextTick()

		// 1. Outer frame selected ('FRAME') -> updates via single Frame profile control
		expect(w.find('[data-testid="series-sub-frame"]').exists()).toBe(true)
		expect(w.findAll('[data-testid="series-sub-frame"] button')).toHaveLength(0)
		const frameSelect = w.findAllComponents(Select).find((c) => c.props('label') === 'Frame profile')!
		expect(frameSelect).toBeDefined()
		frameSelect.vm.$emit('update:modelValue', 'E104156')
		await w.vm.$nextTick()
		expect(store.design.profiles?.frame).toBe('E104156')

		// 2. Glass selected ('GLASS:F1.0') -> highlighted inline under Glass row with no duplicate Glass dropdown
		store.select('GLASS:F1.0')
		await w.vm.$nextTick()
		expect(w.find('[data-testid="series-sub-glass"]').exists()).toBe(true)
		expect(w.findAllComponents(Select).filter((c) => c.props('label') === 'Glass')).toHaveLength(1)

		// 3. Sash selected ('F1.0') -> change Sash profile via single Sash row
		store.select('F1.0')
		await w.vm.$nextTick()
		const sashSelect = w.findAllComponents(Select).find((c) => c.props('label') === 'Sash profile')!
		expect(sashSelect).toBeDefined()
		sashSelect.vm.$emit('update:modelValue', 'E104160')
		await w.vm.$nextTick()
		expect((store.design.root as never as { children: { profile?: string }[] }).children[0].profile).toBe('E104160')

		// 4. Mullion selected ('M1') -> change Mullion profile via single Mullion row
		store.select('M1')
		await w.vm.$nextTick()
		const mullionSelect = w.findAllComponents(Select).find((c) => c.props('label') === 'Mullion profile')!
		expect(mullionSelect).toBeDefined()
		mullionSelect.vm.$emit('update:modelValue', 'E104159')
		await w.vm.$nextTick()
		expect(store.design.profiles?.M1).toBe('E104159')
	})

	it('design card is always open with no fold button', () => {
		const w = mountPanel([fixed], 'F1', [])
		expect(w.find('button[aria-label="Expand design details"]').exists()).toBe(false)
		expect(w.find('input#pp-ref').isVisible()).toBe(true)
	})

	it('no bead offset or depth fields appear anywhere', () => {
		const w = mountPanel([fixed], 'F1', [])
		expect(w.text()).not.toContain('Bead offset (along, depth)')
		expect(w.find('input[placeholder="0"]').exists()).toBe(false)
	})

	it('shows Bead controls (corners, sync, defaults) directly under the Bead selector without a duplicate profile selector', async () => {
		const w = mountPanel([fixed], 'BEAD:F1', [])
		await w.vm.$nextTick()
		const beadSub = w.get('[data-testid="series-sub-bead"]')
		expect(beadSub.text()).toContain('Mitre 45°')
		expect(beadSub.text()).toContain('Square')
		expect(beadSub.text()).toContain('Mirror to opposite side')
		expect(beadSub.text()).toContain('Set as default')
		expect(beadSub.text()).toContain('Reset bead')
		expect(beadSub.text()).not.toContain('Catalog')
		// Bead identifier tags are internal only
		expect(w.text()).not.toContain('OBL')
		expect(w.text()).not.toContain('MBR')
	})

	it('shows Frame and Glass setup properties inline right under their selectors even when nothing is selected', async () => {
		const store = useDesignerStore()
		store.reset({ width: 1200, height: 1200, root: fixed } as never, 'CS400-v1', '', '')
		store.select('')
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		expect(w.find('[data-testid="nothing-selected-card"]').exists()).toBe(false)
		expect(w.find('[data-testid="selected-panel-card"]').exists()).toBe(false)
		expect(w.find('[data-testid="series-sub-frame"]').exists()).toBe(true)
		const glassSub = w.get('[data-testid="series-sub-glass"]')
		expect(glassSub.text()).toContain('Beading')
		expect(glassSub.text()).toContain('Glass width')
		expect(glassSub.text()).toContain('Glass cut')
	})

	it('SERIES & PROFILES shows only Frame and Glass on a plain fixed window without mullion, sash, or bead, and Glass uses popup selector', async () => {
		const store = useDesignerStore()
		store.reset({ width: 1200, height: 1200, root: fixed } as never, 'CS400-v1', '', '')
		store.select('')
		store.result = { members: [{ panel: 'F1', role: 'frame', profile: 'E104156' }], glass: [] } as never
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, floor: '', location: '' } } })
		await w.vm.$nextTick()

		const card = w.get('[data-testid="series-profiles-card"]')
		expect(card.find('[data-testid="series-row-frame"]').exists()).toBe(true)
		expect(card.find('[data-testid="series-row-glass"]').exists()).toBe(true)
		expect(card.find('[data-testid="series-row-mullion"]').exists()).toBe(false)
		expect(card.find('[data-testid="series-row-transom"]').exists()).toBe(false)
		expect(card.find('[data-testid="series-row-sash"]').exists()).toBe(false)
		expect(card.find('[data-testid="series-row-bead"]').exists()).toBe(false)
		expect(card.find('[data-testid="design-finish-field"]').exists()).toBe(false)

		const glassBtn = card.get('[data-testid="global-glass-button"]')
		expect(glassBtn.text()).toContain('6 mm clear toughened (6CTG)')
		await glassBtn.trigger('click')
		const modal = w.get('[data-testid="glass-picker-modal"]')
		expect(modal.find('[data-testid="glass-card-item"]').exists()).toBe(false)
		expect(modal.findAll('button').some((b) => b.text().trim() === 'Cards')).toBe(false)
		const items = modal.findAll('[data-testid="glass-list-item"]')
		const clear5 = items.find((item) => item.text().includes('5CLR'))!
		expect(clear5).toBeDefined()
		await clear5.trigger('click')
		expect(w.find('[data-testid="glass-picker-modal"]').exists()).toBe(false)
		expect((store.design.root as { glass: string }).glass).toBe('5CLR')
	})

	it('DESIGN card renders Finish under Width/Height and Floor above Location', async () => {
		const store = useDesignerStore()
		store.reset({ width: 1200, height: 1200, root: fixed } as never, 'CS400-v1', 'GREY', '')
		const meta = { ref: 'W1', qty: 1, floor: '', location: '' }
		const w = mount(PropertiesPanel, {
			props: {
				meta,
				finishes: [
					{ name: 'GREY', finish_name: 'Grey', color: '#8A8F98' },
					{ name: 'BLACK', finish_name: 'Matte Black', color: '#111111' },
				],
			},
		})
		const finishBlock = w.get('[data-testid="design-finish-field"]')
		const floorInput = w.get('input#pp-floor')
		const locationInput = w.get('input#pp-location')
		const widthInput = w.get('input#pp-width')

		// DOM order: Width/Height -> Floor -> Location, and Surface Finish sits in its own folded accordion + flyout
		expect(widthInput.element.compareDocumentPosition(floorInput.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
		expect(floorInput.element.compareDocumentPosition(locationInput.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
		expect(w.find('[data-testid="acc-finish"]').exists()).toBe(true)

		// Custom color drawer renders prototype swatch grid backed by Frappe Profile Finish
		expect(finishBlock.text()).not.toContain('In ·')
		expect(finishBlock.text()).not.toContain('Out ·')
		const swatches = finishBlock.findAll('[data-testid="finish-swatch-tile"]')
		expect(swatches).toHaveLength(2)
		const prevFinish = store.finish
		await swatches[1].trigger('click')
		// Swatch click stages draft only; does not commit until Apply is clicked
		expect(store.finish).toBe(prevFinish)
		await w.get('[data-testid="eva-finish-flyout"]').findAll('button').find((b) => b.text().trim() === 'Apply')!.trigger('click')
		expect(store.finish).toBe('BLACK')
		const seriesBtn = w.get('[data-testid="series-version-field"] button')
		expect(seriesBtn.classes()).toContain('w-full')
		expect(seriesBtn.attributes('role')).toBe('combobox')
		const frameTrigger = w.get('[data-testid="profile-picker-btn-frame"]').element as HTMLElement
		expect(frameTrigger.style.width).toBe('100%')
		expect(frameTrigger.style.minHeight).toBe('48px')
		expect(frameTrigger.style.borderRadius).toBe('7px')
		expect(frameTrigger.style.background).toBe('rgb(255, 255, 255)')
		expect(w.find('[data-testid="global-glass-button"]').exists()).toBe(true)

		await floorInput.setValue('Floor 2')
		expect(meta.floor).toBe('Floor 2')
	})

	it('SERIES & PROFILES shows Mullion, Transom, Sash, and Bead only when present in the design', async () => {
		const store = useDesignerStore()
		store.reset(
			{
				width: 1200,
				height: 1200,
				beadProfileId: 'E104161',
				root: {
					type: 'split',
					dir: 'v',
					at: [600],
					children: [sash, { type: 'split', dir: 'h', at: [600], children: [fixed, { ...fixed, fan: true }] }],
				},
			} as never,
			'CS400-v1',
			'',
			'',
		)
		store.select('')
		store.result = {
			members: [
				{ panel: 'F1', role: 'frame', profile: 'E104156' },
				{ panel: 'F1-F2', role: 'bead', profile: 'E104161' },
			],
			glass: [],
		} as never
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		const card = w.get('[data-testid="series-profiles-card"]')
		expect(card.find('[data-testid="series-row-frame"]').exists()).toBe(true)
		expect(card.find('[data-testid="series-row-sash"]').exists()).toBe(true)
		expect(card.find('[data-testid="series-row-mullion"]').exists()).toBe(true)
		expect(card.find('[data-testid="series-row-transom"]').exists()).toBe(true)
		expect(card.find('[data-testid="series-row-bead"]').exists()).toBe(true)
		expect(card.find('[data-testid="series-row-glass"]').exists()).toBe(true)

		// When all panels are non-glass (steel fan cutouts), Glass row hides
		store.reset({ width: 1200, height: 1200, root: { ...fixed, fan: true } } as never, 'CS400-v1', '', '')
		await w.vm.$nextTick()
		expect(card.find('[data-testid="series-row-glass"]').exists()).toBe(false)
		expect(card.find('[data-testid="series-row-bead"]').exists()).toBe(false)
	})

	it('renders SERIES & PROFILES rows in the exact order components were added to the design', async () => {
		const fixed = { type: 'fixed', glassId: '6CTG', bead: false }
		const sash = { type: 'sash', glassId: '6CTG', opening: 'left', handle: true }
		const store = useDesignerStore()
		store.reset({ width: 1200, height: 1200, root: fixed } as never, 'CS400-v1', '', '')
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		const rowIds = () =>
			w
				.get('[data-testid="series-profiles-card"]')
				.findAll('[data-testid^="series-row-"]')
				.map((el) => el.attributes('data-testid'))

		expect(rowIds()).toEqual(['series-row-frame', 'series-row-glass'])

		// Step 3: Split vertically -> adds Mullion AFTER Frame and Glass
		store.apply((d) => ({
			...d,
			root: { type: 'split', dir: 'v', at: [600], children: [fixed, fixed] },
		}) as never)
		await w.vm.$nextTick()
		expect(rowIds()).toEqual(['series-row-frame', 'series-row-glass', 'series-row-mullion'])

		// Step 4: Turn left panel into a Sash -> appends Sash after Mullion
		store.apply((d) => ({
			...d,
			root: { type: 'split', dir: 'v', at: [600], children: [sash, fixed] },
		}) as never)
		await w.vm.$nextTick()
		expect(rowIds()).toEqual([
			'series-row-frame',
			'series-row-glass',
			'series-row-mullion',
			'series-row-sash',
		])

		// Removing the mullion drops only Mullion while preserving existing order
		store.apply((d) => ({ ...d, root: sash }) as never)
		await w.vm.$nextTick()
		expect(rowIds()).toEqual(['series-row-frame', 'series-row-glass', 'series-row-sash'])
	})

	it('renders the resolved profile picture and code instead of "Series default" in SERIES & PROFILES buttons', async () => {
		const store = useDesignerStore()
		store.reset(
			{
				width: 1200,
				height: 1200,
				root: { type: 'split', dir: 'v', at: [600], children: [fixed, fixed] },
			} as never,
			'CS400-v1',
			'',
			'',
		)
		store.seriesInfo = {
			glasses: ['6CTG'],
			profiles: ['E104156', 'E104159', 'CS4802'],
			role_defaults: { frame: 'E104156', mullion: 'E104159' },
			defaults: { limiter: false, mesh: false },
		}
		store.select('')
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		const frameBtn = w.get('[data-testid="profile-picker-btn-frame"]')
		expect(frameBtn.text()).not.toContain('Series default')
		expect(frameBtn.text()).toContain('40mm Casement Frame')
		expect(frameBtn.text()).toContain('E104156')
		expect(w.get('[data-testid="profile-thumb-frame"] svg path').attributes('d')).toBe('M 0 0 L 42 0 L 42 50 L 0 50 Z')

		const mullionBtn = w.get('[data-testid="profile-picker-btn-mullion"]')
		expect(mullionBtn.text()).not.toContain('Series default')
		expect(mullionBtn.text()).toContain('40mm Casement Mullion')
		expect(mullionBtn.text()).toContain('E104159')
		expect(w.get('[data-testid="profile-thumb-mullion"] svg path').attributes('d')).toBe('M 0 0 L 60 0 L 60 55 L 0 55 Z')
		expect(w.get('[data-testid="profile-thumb-frame"] svg').attributes('viewBox')).toBe('-7 -7 56 64')

		// Opening the profile selector opens the compact role-filtered thumbnail dropdown (with Browse full catalog option)
		await frameBtn.trigger('click')
		await w.vm.$nextTick()
		const dropdown = w.get('[data-testid="profile-dropdown-frame"]')
		expect(dropdown.findAll('[data-testid="profile-dropdown-item"]')).toHaveLength(1) // only CS400 frame profile E104156
		expect(dropdown.text()).toContain('E104156')
		expect(dropdown.text()).not.toContain('CS4802')
		await dropdown.get('[data-testid="profile-dropdown-browse-all"]').trigger('click')
		await w.vm.$nextTick()
		const modalCardSvg = w.get('[data-testid="profile-card-item"] svg')
		expect(modalCardSvg.attributes('viewBox')).not.toBe('-5 -5 80 80')
		expect(modalCardSvg.classes()).toEqual(expect.arrayContaining(['h-full', 'w-full']))
	})

	it('stacks Series and profile dropdowns below their labels without truncating text', async () => {
		const store = useDesignerStore()
		store.reset({ width: 1200, height: 1200, root: fixed } as never, 'CS400-v1', '', '')
		store.seriesInfo = {
			glasses: ['6CTG'],
			profiles: ['E104156'],
			role_defaults: { frame: 'E104156' },
			defaults: { limiter: false, mesh: false },
		}
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		for (const testid of ['series-version-field', 'series-row-frame', 'series-row-glass']) {
			const row = w.get(`[data-testid="${testid}"]`)
			expect((row.element as HTMLElement).style.flexDirection).toBe('column')
		}
		expect(w.get('[data-testid="series-version-field"] button').classes()).toContain('w-full')
		expect(w.find('[data-testid="profile-picker-btn-frame"] .truncate').exists()).toBe(false)
		expect(w.find('[data-testid="global-glass-button"] .truncate').exists()).toBe(false)
	})

	it('shows Bead profile dropdown when Beading is On and series has bead profiles even without role_defaults.bead', async () => {
		glassState.includeBeadProfile = true
		const store = useDesignerStore()
		store.reset(
			{
				width: 1200,
				height: 1200,
				root: { type: 'split', dir: 'v', at: [600], children: [fixed, fixed] },
			} as never,
			'CS400-v1',
			'',
			'',
		)
		store.seriesInfo = {
			glasses: ['6CTG'],
			profiles: ['E104156', 'E104159', 'CS4807-CS400'],
			role_defaults: { frame: 'E104156', mullion: 'E104159' },
			defaults: { limiter: false, mesh: false },
		}
		store.select('F1.1')
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		// Bead selector is visible for G2 with Beading On
		const beadBtn = w.get('[data-testid="profile-picker-btn-bead"]')
		expect(beadBtn.text()).toContain('Select bead profile')
		expect(w.get('[data-testid="series-sub-bead"]').text()).toContain('G2')

		// Assign bead profile specifically to G2 (F1.1) via the compact role-filtered thumbnail dropdown
		await beadBtn.trigger('click')
		await w.vm.$nextTick()
		const dropdown = w.get('[data-testid="profile-dropdown-bead"]')
		const beadItem = dropdown.findAll('[data-testid="profile-dropdown-item"]').find((c) => c.text().includes('CS4807-CS400'))!
		expect(beadItem).toBeDefined()
		await beadItem.trigger('click')
		await w.vm.$nextTick()

		expect((store.design.root as { children: { beadProfileId?: string }[] }).children[1].beadProfileId).toBe('CS4807-CS400')
		expect(w.get('[data-testid="profile-picker-btn-bead"]').text()).toContain('6 & 8mm Glass Beading')
		expect(w.get('[data-testid="profile-picker-btn-bead"]').text()).toContain('CS4807-CS400')
		expect(w.get('[data-testid="profile-thumb-bead"] svg').exists()).toBe(true)

		// Beading is automatic (no manual Beading On/Off toggle in Change Glazing item)
		const glassSub = w.get('[data-testid="series-sub-glass"]')
		expect(glassSub.find('[data-testid="auto-bead-gasket-preview"]').exists()).toBe(true)
		expect(glassSub.findAll('button').some((b) => b.text().trim() === 'Off')).toBe(false)
	})

	it('renders profile sub-panels cleanly on white without separate colored accent containers', async () => {
		const store = useDesignerStore()
		store.reset(
			{
				width: 1200,
				height: 1200,
				root: { type: 'split', dir: 'v', at: [600], children: [fixed, fixed] },
			} as never,
			'CS400-v1',
			'',
			'',
		)
		store.select('F1.0')
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		for (const testId of ['series-sub-frame', 'series-sub-glass']) {
			const style = w.get(`[data-testid="${testId}"]`).attributes('style') ?? ''
			expect(style).not.toContain('#f4f8ff')
			expect(style).not.toContain('#f8f9fb')
			expect(style).not.toContain('#1d6fdc')
			expect(style).not.toContain('border-left')
		}

		// Scope selector buttons ([All] [G1] [G2]) and Sync button match uniform 6px corner radius (not 999px pills)
		const g1Btn = w.get('[data-testid="series-sub-glass"]').findAll('button').find((b) => b.text().trim() === 'G1')!
		expect(g1Btn.attributes('style')).toContain('border-radius: 6px')
		expect(g1Btn.attributes('style')).not.toContain('999px')
	})

	it('prompts queued role profile pickers sequentially and updates global bar dropdown when cell is selected', async () => {
		const store = useDesignerStore()
		store.reset(
			{
				width: 1200,
				height: 1200,
				root: { type: 'split', dir: 'v', at: [600], children: [sash, fixed] },
			} as never,
			'CS400-v1',
			'',
			'',
		)
		store.seriesInfo = {
			glasses: ['6CTG'],
			profiles: ['E104156', 'E104159', 'E104160'],
			role_defaults: { frame: 'E104156' },
			defaults: { limiter: false, mesh: false },
		}
		store.select('F1.0')
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		;(w.vm as unknown as { promptProfilePickers: (reqs: { role: string; targetKey: string }[]) => void }).promptProfilePickers([
			{ role: 'mullion', targetKey: 'M1' },
			{ role: 'sash', targetKey: 'F1.0' },
		])
		await w.vm.$nextTick()

		// First queued picker: Select mullion profile
		let modal = w.get('[data-testid="profile-picker-modal"]')
		expect(modal.text()).toContain('Select mullion profile')
		await modal.findAll('[data-testid="profile-card-item"]').find((c) => c.text().includes('E104159'))!.trigger('click')
		await w.vm.$nextTick()
		await w.vm.$nextTick()

		expect((store.design as { profiles?: Record<string, string> }).profiles?.M1).toBe('E104159')
		expect(w.get('[data-testid="profile-picker-btn-mullion"]').text()).toContain('40mm Casement Mullion')

		// Second queued picker opens automatically: Select sash profile
		modal = w.get('[data-testid="profile-picker-modal"]')
		expect(modal.text()).toContain('Select sash profile')
		await modal.findAll('[data-testid="profile-card-item"]').find((c) => c.text().includes('E104160'))!.trigger('click')
		await w.vm.$nextTick()

		expect((store.design as { profiles?: Record<string, string> }).profiles?.['F1.0']).toBe('E104160')
		expect(w.find('[data-testid="profile-picker-modal"]').exists()).toBe(false)
	})

	it('automatically updates bead & gasket preview by glass thickness and swaps to Panel items when Select item changes', async () => {
		glassState.includeBeadProfile = true
		const store = useDesignerStore()
		store.reset(
			{
				width: 1200,
				height: 1200,
				root: { type: 'split', dir: 'v', at: [600], children: [{ type: 'fixed', glass: '6CTG', bead: true }, fixed] },
			} as never,
			'CS4800-v1',
			'',
			'',
		)
		store.seriesInfo = {
			glasses: ['6CTG', '12CTG'],
			profiles: ['E104156', 'E104159', 'CS4807-CS400'],
			role_defaults: { frame: 'E104156', mullion: 'E104159' },
			defaults: { limiter: false, mesh: false },
		}
		store.select('F1.0')
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		const preview = w.get('[data-testid="auto-bead-gasket-preview"]')
		expect(preview.text()).toContain('(G23) GASKET 3MM')

		// Switch Select item -> Panel / Wood / Steel -> hides Glass select and shows Panel item select
		const itemTypeSel = w.get('select[aria-label="Select item"]')
		await itemTypeSel.setValue('Panel')
		await w.vm.$nextTick()
		expect(w.find('select[aria-label="Panel item name"]').exists()).toBe(true)
		expect(w.find('select[aria-label="Glazing item name"]').exists()).toBe(false)
	})

	it('opens Sash drawer (not Frame F1) when clicking a single-cell sash at path F1', async () => {
		const store = useDesignerStore()
		store.reset(
			{
				width: 1200,
				height: 1200,
				root: { type: 'sash', glass: '6CTG', opening: 'out', hinge: 'left', bead: true },
			} as never,
			'CS400-v1',
			'',
			'',
		)
		store.select('')
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		// Clicking single-cell sash emits 'F1' -> must open Sash drawer, not Frame F1
		store.select('F1')
		await w.vm.$nextTick()
		const drawer = w.get('[data-testid="series-profiles-card"]')
		expect(drawer.text()).toContain('Sash')
		expect((w.get('[data-testid="series-sub-sash"]').element.parentElement as HTMLElement).style.display).not.toBe('none')
		expect((w.get('[data-testid="series-sub-frame"]').element.parentElement as HTMLElement).style.display).toBe('none')

		// Clicking outer frame emits 'FRAME' -> opens Frame F1 drawer
		store.select('FRAME')
		await w.vm.$nextTick()
		expect(w.get('[data-testid="series-profiles-card"]').text()).toContain('Frame F1')
		expect((w.get('[data-testid="series-sub-frame"]').element.parentElement as HTMLElement).style.display).not.toBe('none')
		expect((w.get('[data-testid="series-sub-sash"]').element.parentElement as HTMLElement).style.display).toBe('none')
	})

	it('applies default rotation and flips to sidebar and picker thumbnails (cards and list)', async () => {
		glassState.rotateFrame = true
		const store = useDesignerStore()
		store.reset({ width: 1200, height: 1200, root: fixed } as never, 'CS400-v1', '', '')
		store.seriesInfo = {
			glasses: ['6CTG'],
			profiles: ['E104156'],
			role_defaults: { frame: 'E104156' },
			defaults: { limiter: false, mesh: false },
		}
		store.select('F1')
		const w = mount(PropertiesPanel, { props: { meta: { ref: 'W1', qty: 1, location: '' } } })
		await w.vm.$nextTick()

		const expectedTransform = 'translate(50, 0) rotate(90) translate(21, 25) scale(-1, 1) translate(-21, -25)'
		const sidebarThumbG = w.get('[data-testid="profile-thumb-frame"] svg g')
		expect(sidebarThumbG.attributes('transform')).toBe(expectedTransform)
		expect(w.get('[data-testid="profile-thumb-frame"] svg').attributes('viewBox')).toBe('-7 -7 64 56')

		await w.get('[data-testid="profile-picker-btn-frame"]').trigger('click')
		await w.vm.$nextTick()
		await w.get('[data-testid="profile-dropdown-frame"] [data-testid="profile-dropdown-browse-all"]').trigger('click')
		await w.vm.$nextTick()

		const modal = w.get('[data-testid="profile-picker-modal"]')
		const cardSvg = modal.get('[data-testid="profile-card-item"] svg')
		expect(cardSvg.attributes('viewBox')).toBe('-7 -7 64 56')
		expect(cardSvg.get('g').attributes('transform')).toBe(expectedTransform)

		await modal.get('[data-testid="view-mode-list"]').trigger('click')
		await w.vm.$nextTick()
		const listSvg = modal.get('[data-testid="profile-list-item"] svg')
		expect(listSvg.attributes('viewBox')).toBe('-7 -7 64 56')
		expect(listSvg.get('g').attributes('transform')).toBe(expectedTransform)
	})
})
