import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import w01 from '@/design/__fixtures__/w01.json'
import type { Design, SectionPieceTransform } from '@/design/types'
import SectionView from './SectionView.vue'

const fake = vi.hoisted(() => ({
	calls: [] as Record<string, unknown>[],
	orientationCalls: [] as { profileName: string; opts: unknown }[],
	response: null as unknown,
	orientationResult: null as Record<string, unknown> | null,
}))

vi.mock('@/api', () => ({
	crossSection: async (design: unknown, seriesVersion: string, axis: string, at: number | null) => {
		fake.calls.push({ design, series_version: seriesVersion, axis, at })
		return structuredClone(fake.response)
	},
	setProfileOrientation: async (profileName: string, opts: unknown) => {
		fake.orientationCalls.push({ profileName, opts })
		return (
			fake.orientationResult ?? {
				ok: true,
				profile_name: profileName,
				section_rotation: '90',
				section_flip_x: 0,
				section_flip_y: 0,
				width_mm: 60,
				depth_mm: 40,
			}
		)
	},
}))

const OUTLINE = (w: number, d: number) => ({ svg: `M 0 0 L ${w} 0 L ${w} ${d} L 0 ${d} Z`, width: w, depth: d })

const W_MULLION_BEADS_CUT = {
	ok: true,
	result: {
		axis: 'h',
		at: 610,
		length: 1220,
		pieces: [
			{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 0, end: 50, mirrored: false, thickness: 0 },
			{ kind: 'profile', code: 'E104161', role: 'bead', panel: 'F1.0', start: 25, end: 45, mirrored: false, thickness: 0 },
			{ kind: 'glass', code: '6CTG', role: 'glass', panel: 'F1.0', start: 40, end: 570, mirrored: false, thickness: 6 },
			{ kind: 'profile', code: 'E104161', role: 'bead', panel: 'F1.0', start: 565, end: 585, mirrored: true, thickness: 0 },
			{ kind: 'profile', code: 'E104159', role: 'mullion', panel: 'M1', start: 575, end: 645, mirrored: false, thickness: 0 },
			{ kind: 'profile', code: 'E104161', role: 'bead', panel: 'F1.1', start: 635, end: 655, mirrored: false, thickness: 0 },
			{ kind: 'glass', code: '6CTG', role: 'glass', panel: 'F1.1', start: 650, end: 1180, mirrored: false, thickness: 6 },
			{ kind: 'profile', code: 'E104161', role: 'bead', panel: 'F1.1', start: 1175, end: 1195, mirrored: true, thickness: 0 },
			{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 1170, end: 1220, mirrored: true, thickness: 0 },
		],
		dims: [],
		issues: [],
	},
	outlines: {
		E104156: OUTLINE(50, 70),
		E104161: OUTLINE(20, 20),
		E104159: OUTLINE(70, 70),
	},
}

const W01_CUT = {
	ok: true,
	result: {
		axis: 'h',
		at: 610,
		length: 915,
		pieces: [
			{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 0, end: 50, mirrored: false, thickness: 0 },
			{ kind: 'profile', code: 'E104160', role: 'sash', panel: 'F1-S1', start: 18, end: 78, mirrored: false, thickness: 0 },
			{ kind: 'glass', code: '6CTG', role: 'glass', panel: 'F1-S1', start: 68.5, end: 401.5, mirrored: false, thickness: 6 },
			{ kind: 'profile', code: 'E104160', role: 'sash', panel: 'F1-S1', start: 392, end: 452, mirrored: true, thickness: 0 },
			{ kind: 'profile', code: 'E104159', role: 'mullion', panel: 'M1', start: 422.5, end: 492.5, mirrored: false, thickness: 0 },
			{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 865, end: 915, mirrored: true, thickness: 0 },
		],
		dims: [
			{ start: 0, end: 915, label: '915', chain: 'overall' },
			{ start: 0, end: 50, label: '50', chain: 'profiles' },
			{ start: 0, end: 457.5, label: '457.5', chain: 'cells' },
			{ start: 68.5, end: 401.5, label: '333', chain: 'glass' },
		],
		issues: [],
	},
	outlines: { E104156: OUTLINE(50, 70), E104160: OUTLINE(60, 65), E104159: OUTLINE(70, 70) },
}

function mountView(props: Record<string, unknown> = {}) {
	return mount(SectionView, {
		props: { design: structuredClone(w01) as Design, seriesVersion: 'SV1', axis: 'h', at: null, ...props },
	})
}

describe('SectionView', () => {
	enableAutoUnmount(afterEach)
	beforeEach(() => {
		fake.calls.length = 0
		fake.response = structuredClone(W01_CUT)
		vi.useFakeTimers()
	})
	afterEach(() => vi.useRealTimers())

	it('renders two glass segments and an exhaust label when the section intersects a cut', async () => {
		(fake.response as any).result.pieces[2].material = 'steel';
		(fake.response as any).result.pieces[2].cutout = { start: 145, end: 325, diameter: 180 }
		const w = mountView()
		await flushPromises()
		expect(w.get('[data-testid="exhaust-section-cut"]').findAll('polygon')).toHaveLength(2)
		expect(w.get('[data-testid="exhaust-section-cut"]').text()).toContain('Ø180 exhaust cut')
		expect(w.find('rect[data-piece="2"]').exists()).toBe(false)
		expect(w.get('[data-testid="exhaust-section-cut"] polygon').attributes('fill')).toBe('#A8ADB5')
		expect(w.get('[data-testid="exhaust-section-cut"]').text()).toContain('Steel')
	})

	it.each(['h', 'v'])('keeps profile focus framing stable with a large exhaust cut on the %s axis', async (axis) => {
		const baseline = mountView({ axis })
		await flushPromises()
		const viewBox = baseline.get('svg[role="img"]').attributes('viewBox')
		const profiles = baseline.findAll('path[data-piece]').map(p => p.attributes('transform'))
		baseline.unmount();
		(fake.response as any).result.pieces[2].cutout = { start: 85, end: 385, diameter: 300 }
		const w = mountView({ axis })
		await flushPromises()
		expect(w.get('[data-testid="toggle-compact-glass"]').attributes('aria-pressed')).toBe('true')
		expect(w.get('svg[role="img"]').attributes('viewBox')).toBe(viewBox)
		expect(w.findAll('path[data-piece]').map(p => p.attributes('transform'))).toEqual(profiles)
		expect(w.get('[data-testid="exhaust-section-cut"]').findAll('polygon')).toHaveLength(2)
		expect(w.text()).toContain('Ø300 exhaust cut')
		await w.get('[data-testid="toggle-compact-glass"]').trigger('click')
		expect(w.get('svg[role="img"]').attributes('viewBox')).not.toBe(viewBox)
	})

	it('shows the grill where the section crosses its selected panel', async () => {
 const design = structuredClone(w01) as any
 design.root.children[0].grill = {vertical:3,horizontal:2}
 const w=mountView({design})
 await flushPromises()
 expect(w.get('[data-testid="grill-section"]').findAll('rect').length).toBeGreaterThan(0)
 expect(w.get('[data-testid="grill-section"]').text()).toContain('Grill')
 expect(w.get('[data-testid="toggle-compact-glass"]').attributes('aria-pressed')).toBe('true')
 })

	it.each(['h','v'])('shows one continuous grill band with axis-specific markers and commits a drag on the %s axis', async axis => {
 (fake.response as any).result.at=600
 const design={width:1200,height:1200,root:{type:'fixed',glass:'6CTG',grill:{}}}
 const w=mountView({design,axis})
 await flushPromises()
 const bars=w.findAll('[data-grill-path]')
 expect(bars).toHaveLength(1)
 await bars[0].trigger('click')
 expect(w.emitted('select')!.at(-1)).toEqual(['GRILL:F1'])
 await w.setProps({selectedPath:'GRILL:F1'})
 expect(w.get('[data-testid="grill-band"]').attributes('stroke')).toBe('#2563EB')
 expect(w.find('[data-testid="profile-inspector"]').exists()).toBe(false)
 expect(w.findAll('[data-testid="grill-band"]')).toHaveLength(1)
 expect(w.findAll('[data-testid="grill-bar-marker"]')).toHaveLength(axis==='h'?3:2)
 expect(w.get('[data-testid="grill-section"]').text()).toContain(axis==='h'?'3 vertical bars':'2 horizontal bars')
 await bars[0].trigger('pointerdown',{button:0,clientX:100,clientY:100,pointerId:1})
 window.dispatchEvent(new MouseEvent('pointermove',{clientX:120,clientY:100,pointerId:1}))
 await w.vm.$nextTick()
 expect(w.find('[data-testid="grill-smart-guides"]').exists()).toBe(true)
 expect(w.findAll('[data-testid="grill-smart-guides"] line').length).toBeGreaterThan(0)
 window.dispatchEvent(new MouseEvent('pointerup',{clientX:120,clientY:100,pointerId:1}))
 await w.vm.$nextTick()
 const updates=w.emitted('update:grill')!
 expect(updates).toHaveLength(1)
 expect(updates[0][0]).toBe('F1')
 const grill=updates[0][1] as any
 if(axis==='v') { expect(grill.offset).toBeGreaterThan(-30); expect(grill.shiftY).toBe(0) }
 else { expect(grill.shiftX).toBeGreaterThan(0); expect(grill.offset).toBe(-30) }
 })

	it.each(['h', 'v'])('preserves grill edge clearances and translation in profile focus on %s', async axis => {
		fake.response = {
			ok: true, outlines: {}, result: { axis, at: 600, length: 1200, dims: [], issues: [], pieces: [
				{ kind: 'glass', role: 'glass', code: '6CTG', panel: 'F1', path: 'F1', start: 30, end: 1170, thickness: 6, mirrored: false },
			] },
		}
		const design: Design = { width: 1200, height: 1200, root: { type: 'fixed', glass: '6CTG', grill: {} } }
		const w = mountView({ design, axis })
		await flushPromises()
		const state = w.vm.$.setupState as any
		expect(state.grillSections[0]).toMatchObject({ x: 42, w: 72, alongScale: 1 })
		// A physical 12 mm clearance must still be 12 mm beside either profile.
		expect(126 - (state.grillSections[0].x + state.grillSections[0].w)).toBe(12)
		await w.setProps({ design: { ...design, root: { ...design.root, grill: { shiftX: 8, shiftY: 8 } } } })
		await flushPromises()
		expect(state.grillSections[0]).toMatchObject({ x: 50, w: 72, alongScale: 1 })
		await w.get('[data-testid="toggle-compact-glass"]').trigger('click')
		expect(state.grillSections[0]).toMatchObject({ x: 50, w: 1116, alongScale: 1 })
	})

	it.each(['h', 'v'])('reflects glazing bead rotation instead of rotating both sides together on %s', async axis => {
		fake.response = structuredClone(W_MULLION_BEADS_CUT)
		const w = mountView({ axis })
		await flushPromises()
		await w.get('[data-piece-group="1"]').trigger('click')
		await w.get('button[aria-label="Rotate clockwise"]').trigger('click')
		const map = w.emitted('update:section-map')!.at(-1)![0] as Record<string, SectionPieceTransform>
		expect(map[`${axis}:OBL`].rotation).toBe(90)
		expect(map[`${axis}:MBR`].rotation).toBe(90)
		expect(w.get('[data-piece="1"]').attributes('transform')).toContain('rotate(90)')
		expect(w.get('[data-piece="7"]').attributes('transform')).toContain('rotate(270)')
		const other = axis === 'h' ? 'v' : 'h'
		expect(map[`${other}:MBR`]).toEqual(map[`${axis}:MBR`])
	})

	it('mirrors glass moves across mullion divider and reflects along offset', async () => {
		fake.response = structuredClone(W_MULLION_BEADS_CUT)
		const w = mountView({ axis: 'h' })
		await flushPromises()

		// Drag left glass (index 2: panel F1.0, tag OGL) by +10px along and +5px depth
		const leftGlassGroup = w.get('[data-piece-group="2"]')
		await leftGlassGroup.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		await leftGlassGroup.trigger('pointermove', { clientX: 110, clientY: 105, pointerId: 1 })
		await leftGlassGroup.trigger('pointerup', { pointerId: 1 })
		await flushPromises()

		const map = w.emitted('update:section-map')!.at(-1)![0] as Record<string, SectionPieceTransform>
		expect(map['h:OGL']).toBeDefined()
		expect(map['h:MGR']).toBeDefined()
		// Left glass moved +along, right glass twin reflected by moving -along
		expect(map['h:OGL'].offsetAlong).toBeGreaterThan(0)
		expect(map['h:MGR'].offsetAlong).toBeCloseTo(-map['h:OGL'].offsetAlong, 5)
		// Both share the same depth adjustment
		expect(map['h:MGR'].offsetDepth).toBe(map['h:OGL'].offsetDepth)
		// Specific glass paths are also saved for 3D consumption
		expect(map['GLASS:F1.0']).toEqual(map['h:OGL'])
		expect(map['GLASS:F1.1']).toEqual(map['h:MGR'])
	})

	it('renders each profile and stationary center glass without cluttered dimension chains', async () => {
		const w = mountView()
		await flushPromises()
		expect(fake.calls[0]).toMatchObject({ series_version: 'SV1', axis: 'h', at: null })
		const pieces = w.findAll('[data-piece]')
		expect(pieces).toHaveLength(6)
		expect(w.findAll('path[data-piece]')).toHaveLength(5)
		const glass = w.get('[data-piece="2"]')
		expect(glass.element.tagName).toBe('rect')
		expect(glass.attributes('data-kind')).toBe('glass')
		const mullion = w.get('[data-piece="4"]')
		expect(mullion.attributes('data-piece')).toBe('4')
		expect(glass.attributes('data-stationary')).toBeUndefined()
		// Glass is stationary at the y = 0 center plane (-thickness/2 to +thickness/2)
		expect(Number(glass.attributes('y')) + Number(glass.attributes('height')) / 2).toBeCloseTo(0, 6)
		// The mirrored sash flips; the unmirrored one does not.
		expect(w.get('[data-piece="1"]').attributes('transform')).not.toContain('scale(-')
		expect(w.get('[data-piece="3"]').attributes('transform')).toContain('scale(-')
		// Cluttered bottom dimension chains are omitted
		expect(w.findAll('[data-chain]')).toHaveLength(0)
	})

	it('selects a profile, enters ghost mode while dragging, and resolves wall collisions on drop', async () => {
		const w = mountView()
		await flushPromises()
		const sashGroup = w.get('[data-piece-group="1"]')
		await sashGroup.trigger('click')
		expect(w.find('[data-testid="profile-inspector"]').exists()).toBe(true)
		expect(w.get('[data-testid="profile-inspector"]').text()).toContain('E104160')

		// Start dragging sash toward the stationary glass to trigger ghost mode
		await sashGroup.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		expect(w.get('[data-piece-group="1"]').attributes('data-ghost')).toBe('true')
		expect(w.text()).toContain('Ghost Mode')

		await sashGroup.trigger('pointermove', { clientX: 112, clientY: 108, pointerId: 1 })
		await sashGroup.trigger('pointerup', { pointerId: 1 })

		// Ghost mode ends on release and no profiles are left clipping
		expect(w.get('[data-piece-group="1"]').attributes('data-ghost')).toBeUndefined()
		expect(w.findAll('[data-colliding="true"]')).toHaveLength(0)
		expect(w.emitted('update:section-map')).toBeTruthy()
	})

	it('mirrors profile moves & rotations on opposite corners and syncs between B-B (top) and A-A (side) views', async () => {
		const w = mountView()
		await flushPromises()

		// Select left frame (index 0, mirrored: false) and right frame (index 5, mirrored: true)
		const getTranslateX = (idx: number) => {
			const t = w.get(`[data-piece="${idx}"]`).attributes('transform')!
			return Number(/translate\((-?[\d.]+)/.exec(t)![1])
		}
		const leftXBefore = getTranslateX(0)
		const rightXBefore = getTranslateX(5)

		// Drag left frame inward (+20 px -> +dx mm)
		const leftFrameGroup = w.get('[data-piece-group="0"]')
		await leftFrameGroup.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		await leftFrameGroup.trigger('pointermove', { clientX: 120, clientY: 100, pointerId: 1 })
		await leftFrameGroup.trigger('pointerup', { pointerId: 1 })

		const leftXAfter = getTranslateX(0)
		const rightXAfter = getTranslateX(5)

		// Left frame moved right (+delta), right frame automatically mirrored and moved left (-delta)
		const deltaLeft = leftXAfter - leftXBefore
		const deltaRight = rightXAfter - rightXBefore
		expect(deltaLeft).toBeGreaterThan(0)
		expect(deltaRight).toBeCloseTo(-deltaLeft, 5)

		// Rotate selected profile by +90° and verify sectionMap stores the canonical key `frame:E104156`
		await w.get('button[aria-label="Rotate clockwise"]').trigger('click')
		const lastMap = w.emitted('update:section-map')!.at(-1)![0] as Record<string, SectionPieceTransform>
		expect(lastMap['frame:E104156']).toBeDefined()
		expect(lastMap['frame:E104156'].rotation).toBe(90)

		// Switching to A-A vertical (side view) preserves the same `frame:E104156` transform
		const vBtn = w.findAll('button').find((b) => b.text() === 'A–A vertical')!
		await vBtn.trigger('click')
		await flushPromises()
		expect(w.get('[data-piece="0"]').attributes('transform')).toContain('rotate(90)')
	})

	it('rotates a profile on the mirrored side clockwise when clicking rotate clockwise', async () => {
		const w = mountView()
		await flushPromises()

		// Select right frame (index 5, which has piece.mirrored: true)
		await w.get('[data-piece-group="5"]').trigger('click')
		await flushPromises()

		// Click rotate clockwise (+90°)
		await w.get('button[aria-label="Rotate clockwise"]').trigger('click')
		await flushPromises()

		// Visual SVG transform on mirrored right frame (index 5) must rotate clockwise (+90)
		const rightTransform = w.get('[data-piece="5"]').attributes('transform') ?? ''
		expect(rightTransform).toContain('rotate(90)')

		// Visual badge readout in the toolbar must show 90°
		const inspector = w.get('[data-testid="profile-inspector"]')
		expect(inspector.text()).toContain('90°')

		// Mirrored twin (left frame, index 0) reflects the rotation (270° in SVG)
		const leftTransform = w.get('[data-piece="0"]').attributes('transform') ?? ''
		expect(leftTransform).toContain('rotate(270)')
	})

	it('supports workspace zoom, drag-to-pan, and positions the floating control pill directly above the selected profile', async () => {
		const w = mountView()
		await flushPromises()

		// Select left profile (index 0) and check floating toolbar position
		await w.get('[data-piece-group="0"]').trigger('click')
		const inspector0 = w.get('[data-testid="profile-inspector"]')
		const style0 = inspector0.attributes('style') ?? ''
		expect(style0).toContain('translate(-50%, -100%)')
		const leftPct0 = Number(/left:\s*([\d.]+)%/.exec(style0)![1])

		// Select right profile (index 5) and verify the floating toolbar moves above the right profile
		await w.get('[data-piece-group="5"]').trigger('click')
		const style5 = w.get('[data-testid="profile-inspector"]').attributes('style') ?? ''
		const leftPct5 = Number(/left:\s*([\d.]+)%/.exec(style5)![1])
		expect(leftPct5).toBeGreaterThan(leftPct0)

		// Zoom in using the bottom-right workspace zoom button
		const svg = w.get('svg')
		const vbBefore = svg.attributes('viewBox')!
		await w.get('button[aria-label="Zoom in section"]').trigger('click')
		expect(w.get('button[aria-label="Reset section zoom"]').text()).toBe('115%')
		expect(svg.attributes('viewBox')).not.toBe(vbBefore)

		// Drag the workspace background to pan the cross-section canvas
		const vbBeforePan = svg.attributes('viewBox')!
		await svg.trigger('pointerdown', { clientX: 200, clientY: 200, button: 0, pointerId: 2 })
		await svg.trigger('pointermove', { clientX: 260, clientY: 230, pointerId: 2 })
		await svg.trigger('pointerup', { pointerId: 2 })
		expect(svg.attributes('viewBox')).not.toBe(vbBeforePan)

		// Reset zoom & pan back to 100%
		await w.get('button[aria-label="Reset section zoom"]').trigger('click')
		expect(w.get('button[aria-label="Reset section zoom"]').text()).toBe('100%')
		expect(svg.attributes('viewBox')).toBe(vbBefore)
	})

	it('missing_outline_falls_back_to_box', async () => {
		delete (fake.response as { outlines: Record<string, unknown> }).outlines.E104159
		const w = mountView()
		await flushPromises()
		const box = w.get('[data-piece="4"]')
		expect(box.element.tagName).toBe('rect')
		expect(box.attributes('data-kind')).toBe('profile')
		expect(w.get('[data-testid="missing-outlines"]').text()).toContain('E104159')
		expect(w.get('[data-testid="missing-outlines"]').text()).not.toContain('E104156')
	})

	it('axis_toggle_refetches', async () => {
		const w = mountView()
		await flushPromises()
		expect(fake.calls).toHaveLength(1)
		const vBtn = w.findAll('button').find((b) => b.text() === 'A–A vertical')!
		expect(w.findAll('button').find((b) => b.text() === 'B–B horizontal')!.attributes('aria-pressed')).toBe('true')
		await vBtn.trigger('click')
		await flushPromises()
		expect(w.emitted('update:axis')![0]).toEqual(['v'])
		expect(fake.calls).toHaveLength(2)
		expect(fake.calls[1].axis).toBe('v')
		expect(vBtn.attributes('aria-pressed')).toBe('true')
	})

	it('refetches when the cut moves and, debounced, when the design changes', async () => {
		const w = mountView()
		await flushPromises()
		await w.setProps({ at: 300 })
		await flushPromises()
		expect(fake.calls).toHaveLength(2)
		expect(fake.calls[1].at).toBe(300)
		await w.setProps({ design: { ...(w01 as Design), width: 1000 } })
		await w.setProps({ design: { ...(w01 as Design), width: 1001 } })
		await flushPromises()
		expect(fake.calls).toHaveLength(2)
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		expect(fake.calls).toHaveLength(3)
		expect((fake.calls[2].design as Design).width).toBe(1001)
	})

	it('displays A–A bottom to top and converts upward dragging to increasing cut position', async () => {
		const w = mountView({ axis: 'v' })
		await flushPromises()
		expect(fake.calls[0].axis).toBe('v')
		expect(w.get('[data-testid="section-orientation"]').attributes('transform')).toBe('rotate(-90)')
		const frame = w.get('[data-piece-group="0"]')
		const before = w.get('[data-piece="0"]').attributes('transform')!
		await frame.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		await frame.trigger('pointermove', { clientX: 100, clientY: 80, pointerId: 1 })
		await frame.trigger('pointerup', { pointerId: 1 })
		const after = w.get('[data-piece="0"]').attributes('transform')!
		const along = (value: string) => Number(/translate\((-?[\d.]+)/.exec(value)![1])
		expect(along(after)).toBeGreaterThan(along(before))
		await w.setProps({ axis: 'h' })
		await flushPromises()
		expect(fake.calls.at(-1)!.axis).toBe('h')
		expect(w.get('[data-testid="section-orientation"]').attributes('transform')).toBeUndefined()
	})

	it('shows selectable louver blades in A–A and a labeled area in B–B without glass', async () => {
		fake.response = { ...structuredClone(W01_CUT), result: {
			axis: 'v', at: 200, length: 610, dims: [], issues: [], pieces: [
				{ kind: 'louver', role: 'louver', code: 'Louver', panel: 'F1.0', path: 'F1.0', start: 24, end: 586, opening_height: 562, blades: 9, mirrored: false, thickness: 0 },
			],
		} }
		const w = mountView({ axis: 'v' })
		await flushPromises()
		expect(w.get('[data-kind="louver"]').findAll('polygon')).toHaveLength(9)
		expect(w.text()).toContain('Louver · 9 blades')
		expect(w.find('[data-kind="glass"]').exists()).toBe(false)
		await w.get('[data-kind="louver"]').trigger('click')
		expect(w.emitted('select')!.at(-1)).toEqual(['F1.0'])
		await w.setProps({ axis: 'h' })
		await flushPromises()
		expect(w.get('[data-kind="louver"]').findAll('polygon')).toHaveLength(1)
		expect(w.get('[data-testid="louver-blade-strips"]').findAll('line')).toHaveLength(9)
		expect(w.get('[data-testid="louver-label"]').attributes('font-size')).toBe('3')
	})

	it('emits the snapped cut position', async () => {
		const w = mountView()
		await flushPromises()
		expect(w.emitted('cut')![0]).toEqual([610])
	})

	it('shows the error message of a failed cut', async () => {
		fake.response = { ok: false, error_type: 'design', message: 'bad axis' }
		const w = mountView()
		await flushPromises()
		expect(w.get('[role="alert"]').text()).toContain('bad axis')
		expect(w.findAll('[data-piece]')).toHaveLength(0)
	})

	it('scales to its container width', async () => {
		const w = mountView()
		await flushPromises()
		const svg = w.get('svg')
		expect(svg.attributes('width')).toBe('100%')
		expect(svg.attributes('viewBox')).toMatch(/^-?\d+(\.\d+)? -?\d+(\.\d+)? \d+(\.\d+)? \d+(\.\d+)?$/)
	})

	it('does not refetch when the cut moves to where the engine already cut', async () => {
		const w = mountView()
		await flushPromises()
		expect(fake.calls).toHaveLength(1)
		await w.setProps({ at: 610 })
		await flushPromises()
		expect(fake.calls).toHaveLength(1)
		await w.setProps({ at: 300 })
		await flushPromises()
		expect(fake.calls).toHaveLength(2)
	})

	it('allows selecting, rotating, and dragging the center mullion', async () => {
		const w = mountView()
		await flushPromises()

		// Mullion is piece index 4
		const mullionGroup = w.get('[data-piece-group="4"]')
		expect(mullionGroup.attributes('style')).toContain('cursor: move')

		// Click on the mullion to select it
		await mullionGroup.trigger('pointerdown', { clientX: 200, clientY: 100, button: 0, pointerId: 1 })
		expect(w.find('[data-testid="profile-inspector"]').exists()).toBe(true)
		expect(w.get('[data-testid="profile-inspector"]').text()).toContain('E104159')

		// Mullion is draggable (ghost mode is entered on pointerdown)
		expect(mullionGroup.attributes('data-ghost')).toBeDefined()

		// Rotating clockwise by 90° updates rotation
		await w.get('button[aria-label="Rotate clockwise"]').trigger('click')
		const lastMap = w.emitted('update:section-map')!.at(-1)![0] as Record<string, SectionPieceTransform>
		const transform = lastMap['mullion:E104159'] || lastMap['M1:mullion:E104159']
		expect(transform).toBeDefined()
		expect(transform.rotation).toBe(90)
	})

	it('toggles 1:1 Profile Focus, frames assembly cleanly and clamps boundaries at compacted span', async () => {
		const w = mountView()
		await flushPromises()

		const toggleBtn = w.get('[data-testid="toggle-compact-glass"]')
		expect(toggleBtn.attributes('aria-pressed')).toBe('true')

		// Toggle to full window mode (1:1 focus OFF)
		await toggleBtn.trigger('click')
		expect(toggleBtn.attributes('aria-pressed')).toBe('false')
		expect(w.get('button[aria-label="Reset section zoom"]').text()).toBe('100%')

		// Toggle back to 1:1 focus ON
		await toggleBtn.trigger('click')
		expect(toggleBtn.attributes('aria-pressed')).toBe('true')
		expect(w.get('button[aria-label="Reset section zoom"]').text()).toBe('100%')
	})

	it('allows zooming past 4x up to 25x in 1:1 off mode for deep profile groove inspection', async () => {
		const w = mountView()
		await flushPromises()

		// Switch to 1:1 OFF mode
		await w.get('[data-testid="toggle-compact-glass"]').trigger('click')

		// Zoom in repeatedly with zoomIn or wheel
		const zoomBtn = w.get('button[aria-label="Zoom in section"]')
		for (let i = 0; i < 15; i++) {
			await zoomBtn.trigger('click')
		}
		const resetText = w.get('button[aria-label="Reset section zoom"]').text()
		const zoomPct = parseInt(resetText, 10)
		expect(zoomPct).toBeGreaterThan(400) // Exceeds old 4.0 (400%) limit
	})

	it('aligns the bottom boundary wall exactly with the bottom edge of the outer profiles', async () => {
		const w = mountView()
		await flushPromises()

		// The outer frame (depth 70, baseY = 0) has its bottom edge at y = 70.
		// The bottom wall line must sit exactly at y = 70 with zero gap.
		const bottomLine = w.get('[data-testid="bottom-boundary-line"]')
		expect(Number(bottomLine.attributes('y1'))).toBe(70)
		expect(Number(bottomLine.attributes('y2'))).toBe(70)
	})

	it('toggles Mirror & Sync as a pure flag without wiping or recomputing stored state', async () => {
		const initialMap = {
			'sash:E104160': { offsetAlong: 10, offsetDepth: -11.5, rotation: 0, flipX: false, flipY: false },
		}
		const w = mountView({
			design: {
				...w01,
				sectionMap: initialMap,
			},
		})
		await flushPromises()

		const toggleBtn = w.get('[data-testid="toggle-mirror-sync"]')
		expect(toggleBtn.attributes('aria-pressed')).toBe('true')

		// Toggle Mirror & Sync to OFF
		await toggleBtn.trigger('click')
		expect(toggleBtn.attributes('aria-pressed')).toBe('false')

		// Emitted update:mirror-sync with false
		expect(w.emitted('update:mirror-sync')).toEqual([[false]])
		// Pure toggle: does NOT emit update:section-map or wipe transforms
		expect(w.emitted('update:section-map')).toBeUndefined()
	})

	it('links OBL <-> MBR (connection 1) and OBR <-> MBL (connection 2) across mullion centerline', async () => {
		fake.response = structuredClone(W_MULLION_BEADS_CUT)
		const w = mountView()
		await flushPromises()

		const getTranslateX = (idx: number) => {
			const t = w.get(`[data-piece="${idx}"]`).attributes('transform')!
			return Number(/translate\((-?[\d.]+)/.exec(t)![1])
		}

		// Initial positions
		const oblBefore = getTranslateX(1)
		const obrBefore = getTranslateX(3)
		const mblBefore = getTranslateX(5)
		const mbrBefore = getTranslateX(7)

		// 1. Drag OBL (index 1) by +10px
		const oblGroup = w.get('[data-piece-group="1"]')
		await oblGroup.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		await oblGroup.trigger('pointermove', { clientX: 110, clientY: 100, pointerId: 1 })
		await oblGroup.trigger('pointerup', { pointerId: 1 })
		await flushPromises()

		// Verify only MBR moved in opposite x direction, while OBR and MBL did not move!
		const oblDelta1 = getTranslateX(1) - oblBefore
		const mbrDelta1 = getTranslateX(7) - mbrBefore
		const obrDelta1 = getTranslateX(3) - obrBefore
		const mblDelta1 = getTranslateX(5) - mblBefore

		expect(oblDelta1).toBeGreaterThan(0)
		expect(mbrDelta1).toBeCloseTo(-oblDelta1, 5)
		expect(obrDelta1).toBe(0)
		expect(mblDelta1).toBe(0)

		// 2. Drag OBR (index 3) by +10px
		const obrGroup = w.get('[data-piece-group="3"]')
		await obrGroup.trigger('pointerdown', { clientX: 200, clientY: 100, button: 0, pointerId: 1 })
		await obrGroup.trigger('pointermove', { clientX: 210, clientY: 100, pointerId: 1 })
		await obrGroup.trigger('pointerup', { pointerId: 1 })
		await flushPromises()

		// Verify only MBL moved in opposite x direction, while OBL and MBR did not move further!
		const obrDelta2 = getTranslateX(3) - obrBefore
		const mblDelta2 = getTranslateX(5) - mblBefore
		expect(obrDelta2).toBeGreaterThan(0)
		expect(mblDelta2).toBeCloseTo(-obrDelta2, 5)
		expect(getTranslateX(1) - oblBefore).toBe(oblDelta1)
		expect(getTranslateX(7) - mbrBefore).toBe(mbrDelta1)
	})

	it('stops linked movement when Mirror & Sync is OFF and preserves differences when toggled ON', async () => {
		fake.response = structuredClone(W_MULLION_BEADS_CUT)
		const w = mountView({
			design: {
				...w01,
				mirrorSync: false,
				sectionMap: {
					'h:OBL': { offsetAlong: -5, offsetDepth: 23, rotation: 0, flipX: false, flipY: false },
					'h:MBR': { offsetAlong: 12, offsetDepth: 23, rotation: 0, flipX: false, flipY: false },
				},
			},
		})
		await flushPromises()

		const getTranslateX = (idx: number) => {
			const t = w.get(`[data-piece="${idx}"]`).attributes('transform')!
			return Number(/translate\((-?[\d.]+)/.exec(t)![1])
		}
		const mbrXBefore = getTranslateX(7)

		// With Sync OFF, drag OBL: MBR must NOT move!
		const oblGroup = w.get('[data-piece-group="1"]')
		await oblGroup.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		await oblGroup.trigger('pointermove', { clientX: 105, clientY: 100, pointerId: 1 })
		await oblGroup.trigger('pointerup', { pointerId: 1 })
		await flushPromises()

		expect(getTranslateX(7)).toBe(mbrXBefore)

		// Toggle Mirror & Sync ON: existing values stay unchanged
		const toggleBtn = w.get('[data-testid="toggle-mirror-sync"]')
		await toggleBtn.trigger('click')
		await flushPromises()
		expect(toggleBtn.attributes('aria-pressed')).toBe('true')
	})

	it('restores default symmetric assembly on Reset All', async () => {
		const w = mountView({
			design: {
				...w01,
				sectionMap: {
					'h:OBL': { offsetAlong: -5, offsetDepth: 23, rotation: 0, flipX: false, flipY: false },
				},
			},
		})
		await flushPromises()

		const resetAllBtn = w.get('[data-testid="reset-all-profiles"]')
		await resetAllBtn.trigger('click')
		await flushPromises()

		expect(w.emitted('update:section-map')?.at(-1)).toEqual([{}])
	})

	it('renders smart guides and spacing pills during drag and clears on pointerup', async () => {
		const w = mountView()
		await flushPromises()

		const sashGroup = w.get('[data-piece-group="1"]')
		await sashGroup.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })

		// Move sash near an alignment line
		await sashGroup.trigger('pointermove', { clientX: 105, clientY: 100, pointerId: 1 })
		await flushPromises()

		// When drag ends on pointerup, overlay is removed
		await sashGroup.trigger('pointerup', { pointerId: 1 })
		await flushPromises()
		expect(w.find('[data-testid="smart-guides-overlay"]').exists()).toBe(false)
	})
	it('publishes automatic sash placement to both section axes and the shared 3D transform', async () => {
		let worker: { onmessage?: (event: { data: unknown }) => void }
		vi.stubGlobal('Worker', class {
			onmessage?: (event: { data: unknown }) => void
			constructor() { worker = this }
			postMessage() {}
			terminate() {}
		})
		try {
			const w = mountView()
			await flushPromises()
			const left = { offsetAlong: 2, offsetDepth: 12, rotation: 0, flipX: false, flipY: false }
			worker!.onmessage!({ data: [null, left, null, { ...left, offsetAlong: -2 }, null, null] })
			await flushPromises()
			const map = w.emitted('update:section-map')!.at(-1)![0] as Record<string, SectionPieceTransform>
			expect(map['sash:E104160']).toEqual(left)
			for (const key of Object.keys(map).filter(key => key.startsWith('h:'))) {
				expect(map[`v:${key.slice(2)}`]).toEqual(map[key])
			}
		} finally { vi.unstubAllGlobals() }
	})

	it('selecting a profile without dragging never moves or snaps it', async () => {
		const w = mountView()
		await flushPromises()
		const frame = w.get('[data-piece-group="0"]')
		await frame.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		await frame.trigger('pointerup', { clientX: 100, clientY: 100, pointerId: 1 })
		expect(w.emitted('update:section-map')).toBeUndefined()
	})

	it('keeps the mirrored outline orientation while dragging its partner', async () => {
		const w = mountView()
		await flushPromises()
		const before = w.get('[data-piece="5"]').attributes('transform')
		const frame = w.get('[data-piece-group="0"]')
		await frame.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		await frame.trigger('pointermove', { clientX: 105, clientY: 100, altKey: true, pointerId: 1 })
		const during = w.get('[data-piece="5"]').attributes('transform')
		expect(during.match(/scale\([^)]*\)/)?.[0]).toBe(before.match(/scale\([^)]*\)/)?.[0])
	})

	it('Set default saves rotation and flips and resets all sectionMap orientation keys across axes', async () => {
		fake.orientationCalls = []
		fake.orientationResult = {
			ok: true,
			profile_name: 'E104159',
			section_rotation: '90',
			section_flip_x: 1,
			section_flip_y: 0,
			width_mm: 70,
			depth_mm: 70,
		}
		const w = mountView()
		await flushPromises()

		// Select Mullion (index 4, M1)
		await w.get('[data-piece-group="4"]').trigger('click')
		await w.get('button[aria-label="Flip horizontal"]').trigger('click')
		await w.get('button[aria-label="Rotate clockwise"]').trigger('click')
		await w.get('button[aria-label="Set as default orientation"]').trigger('click')
		await flushPromises()

		expect(fake.orientationCalls).toHaveLength(1)
		expect(fake.orientationCalls[0]).toEqual({
			profileName: 'E104159',
			opts: { delta: 90, delta_flip_x: true, delta_flip_y: false },
		})

		const lastMap = w.emitted('update:section-map')!.at(-1)![0] as Record<string, SectionPieceTransform>
		for (const k of ['h:M1', 'v:M1', 'M1', 'mullion:E104159']) {
			expect(lastMap[k]).toBeDefined()
			expect(lastMap[k].rotation).toBe(0)
			expect(lastMap[k].flipX).toBe(false)
			expect(lastMap[k].flipY).toBe(false)
		}
		expect(w.emitted('profile-orientation-updated')?.at(-1)).toEqual(['E104159'])
		expect(w.get('[data-testid="profile-inspector"]').text()).toContain('0°')
	})

	it('Set default on a mirrored piece (MFR) saves the unmirrored-equivalent delta and resets all frame keys', async () => {
		fake.orientationCalls = []
		fake.orientationResult = {
			ok: true,
			profile_name: 'E104156',
			section_rotation: '270',
			section_flip_x: 0,
			section_flip_y: 1,
			width_mm: 70,
			depth_mm: 50,
		}
		const w = mountView()
		await flushPromises()

		// Select mirrored right frame (index 5, MFR)
		await w.get('[data-piece-group="5"]').trigger('click')
		await w.get('button[aria-label="Rotate clockwise"]').trigger('click')
		await w.get('button[aria-label="Flip vertical"]').trigger('click')
		await w.get('button[aria-label="Set as default orientation"]').trigger('click')
		await flushPromises()

		expect(fake.orientationCalls).toHaveLength(1)
		// Clicking CW (+90°) on mirrored MFR sets pieceTransform.rotation = 270 (F_x * R(90) * F_x = R(270))
		expect(fake.orientationCalls[0]).toEqual({
			profileName: 'E104156',
			opts: { delta: 270, delta_flip_x: false, delta_flip_y: true },
		})

		const lastMap = w.emitted('update:section-map')!.at(-1)![0] as Record<string, SectionPieceTransform>
		for (const k of ['h:OFL', 'h:MFR', 'v:OFL', 'v:MFR', 'FRAME', 'frame:E104156']) {
			expect(lastMap[k]).toBeDefined()
			expect(lastMap[k].rotation).toBe(0)
			expect(lastMap[k].flipX).toBe(false)
			expect(lastMap[k].flipY).toBe(false)
		}
	})

	it('highlights Set default when profile is flipped without rotation', async () => {
		const w = mountView()
		await flushPromises()
		await w.get('[data-piece-group="4"]').trigger('click')
		const setDefaultBtn = w.get('button[aria-label="Set as default orientation"]')
		expect(setDefaultBtn.classes()).not.toContain('text-blue-800')
		await w.get('button[aria-label="Flip vertical"]').trigger('click')
		expect(setDefaultBtn.classes()).toContain('text-blue-800')
	})

})
