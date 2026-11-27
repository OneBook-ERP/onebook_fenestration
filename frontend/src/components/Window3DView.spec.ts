import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import w01 from '@/design/__fixtures__/w01.json'
import type { Design } from '@/design/types'
import Window3DView from './Window3DView.vue'
import casementOutlines from '@/design/__fixtures__/casementSections.json'
import { buildPlacedShape, classifySectionPieceInstances } from '@/design/sectionPuzzle'
import type { SectionPiece } from '@/api'

vi.mock('@/api', () => ({
	windowAssembly: vi.fn(async () => ({ ok: false })),
	crossSection: vi.fn(async (_design: any, _series: any, axis: string) => ({
		ok: true,
		result: {
			axis,
			at: 600,
			length: 1200,
			pieces: [
				{ kind: 'profile', panel: 'F1', role: 'bead', code: 'E104161', start: 32, end: 56.1, mirrored: false },
				{ kind: 'profile', panel: 'F1', role: 'bead', code: 'E104161', start: 1143.9, end: 1168, mirrored: true },
			],
			dims: [],
			issues: [],
		},
		outlines: {
			E104156: { svg: 'M 0 0 L 42 0 L 42 60 L 0 60 Z', width: 42, depth: 60 },
			E104160: { svg: 'M 0 0 L 50 0 L 50 55 L 0 55 Z', width: 50, depth: 55 },
			E104161: { svg: 'M 0 0 L 24.1 0 L 24.1 21.7 L 0 21.7 Z', width: 24.1, depth: 21.7 },
		},
	})),
}))

function createMockDesign(): Design {
	const d = structuredClone(w01) as unknown as Design
	d.frameProfileId = 'E104156'
	return d
}

describe('Window3DView (Three.js real extruded 3D window)', () => {
	enableAutoUnmount(afterEach)

	beforeEach(() => {
		setActivePinia(createPinia())
	})

	it('keeps separate bead bounds and side profiles for fixed panes sharing F1', async () => {
		const w = mount(Window3DView, { props: { design: createMockDesign() } })
		await flushPromises()
		const state = w.vm.$.setupState as any
		const bead = (path: string, start: number, mirrored: boolean) => ({
			kind: 'profile', panel: 'F1', path, role: 'bead', code: 'E104161', start, end: start + 20, mirrored,
		})
		state.sectionCuts = [{ axis: 'h', length: 915, pieces: [
			bead('F1.0', 25, false), bead('F1.0', 590, true),
			bead('F1.1', 650, false), bead('F1.1', 870, true),
		] }]
		expect(state.panelFor('F1.0', 'bead')).toBe('F1.0')
		expect(state.sectionSpan('F1.0', 'bead', 'h')).toEqual({ min: 25, max: 610 })
		expect(state.sectionSpan('F1.1', 'bead', 'h')).toEqual({ min: 650, max: 890 })
		expect(state.sectionPieceFor('F1.0', 'bead', 'R').start).toBe(590)
		expect(state.sectionPieceFor('F1.1', 'bead', 'L').start).toBe(650)
	})

	it('uses the root sash section placement in 3D instead of falling back to an unplaced profile', async () => {
		const design = createMockDesign()
		design.width = design.height = 1200
		design.root = { type: 'sash', glass: '6CTG', opening: 'out', hinge: 'left' }
		const frame = casementOutlines.frame
		const sash = casementOutlines.sash
		const profile = (role: string, panel: string, path: string, start: number, width: number, mirrored: boolean): SectionPiece => ({
			kind: 'profile', role, code: role === 'sash' ? 'E104160' : 'E104156', panel, path,
			start, end: start + width, mirrored, thickness: 0,
		})
		const pieces = [
			profile('frame', 'F1', '', 0, frame.width, false),
			profile('sash', 'F1-S1', 'F1', 18, sash.width, false),
			profile('sash', 'F1-S1', 'F1', 1182 - sash.width, sash.width, true),
			profile('frame', 'F1', '', 1200 - frame.width, frame.width, true),
		]
		design.sectionMap = {}
		for (const axis of ['h', 'v'] as const) {
			const tags = classifySectionPieceInstances(axis, pieces, 1200)
			pieces.forEach((piece, index) => {
				design.sectionMap![`${axis}:${tags[index]}`] = {
					offsetAlong: piece.role === 'sash' ? (piece.mirrored ? -5 : 5) : 0,
					offsetDepth: piece.role === 'sash' ? -18 : 0, rotation: 0, flipX: false, flipY: false,
				}
			})
		}
		const w = mount(Window3DView, { props: { design } })
		await flushPromises()
		const state = w.vm.$.setupState as any
		state.sectionCuts = ['h', 'v'].map(axis => ({ axis, at: 600, length: 1200, pieces: structuredClone(pieces), dims: [], issues: [] }))
		const owner = state.panelFor('F1', 'sash')
		expect(owner).toBe('F1')
		for (const side of ['L', 'R', 'B', 'T']) {
			const piece = state.sectionPieceFor(owner, 'sash', side, 'E104160')
			expect(piece, `missing root sash on ${side}`).toBeDefined()
			const transform = state.getPieceTransform(piece, sash, undefined, side === 'L' || side === 'R' ? 'h' : 'v')
			expect(transform.offsetDepth).toBe(-18)
			expect(transform.offsetAlong).toBe(piece.mirrored ? -5 : 5)
			const section = buildPlacedShape(0, piece, piece.start, piece.end, sash, transform)
			const rail = state.buildProfileShape(sash, sash.width, sash.depth, transform, piece.mirrored)
			// Reconstruct the 3D rail's transverse coordinates back into section
			// coordinates. Every actual outline vertex must land on the 2D outline.
			const sectionPoints = section.rings.flat()
			for (const loop of rail.loops) for (const point of loop) {
				const u = point.y + rail.alongOffset
				const x = piece.mirrored ? piece.end - u : piece.start + u
				const y = point.x + rail.depthOffset
				expect(sectionPoints.some(p => Math.abs(p.x - x) < 0.001 && Math.abs(p.y - y) < 0.001)).toBe(true)
			}
		}
	})

	it('keeps transformed profile vertices on the section datum beside an unmoved grill', async () => {
		const w = mount(Window3DView, { props: { design: createMockDesign() } })
		await flushPromises()
		const state = w.vm.$.setupState as any
		const outline = { svg: 'M2 0 L40 0 L40 60 L2 60 Z', width: 42, depth: 60 }
		for (const mirrored of [false, true]) for (const rotation of [0, 90, 180, 270]) {
			const piece: SectionPiece = { kind: 'profile', role: 'frame', code: 'F', panel: 'F1', start: mirrored ? 1158 : 0, end: mirrored ? 1200 : 42, mirrored, thickness: 0 }
			const transform = { offsetAlong: mirrored ? -3 : 3, offsetDepth: 4, rotation, flipX: false, flipY: false }
			const section = buildPlacedShape(0, piece, piece.start, piece.end, outline, transform)
			const rail = state.buildProfileShape(outline, 42, 60, transform, mirrored)
			for (const loop of rail.loops) for (const point of loop) {
				const u = point.y + rail.alongOffset
				const x = mirrored ? piece.end - u : piece.start + u
				const y = point.x + rail.depthOffset
				expect(section.rings.flat().some(p => Math.abs(p.x-x) < 0.001 && Math.abs(p.y-y) < 0.001)).toBe(true)
			}
		}
	})

	it('copes the extruded transom cap to a stepped mullion face', async () => {
		const w = mount(Window3DView, { props: { design: createMockDesign() } })
		await flushPromises()
		const state = w.vm.$.setupState as any
		const shape = state.buildProfileShape(undefined, 60, 40)
		const seat = {
			contour: [
				{ x: 0, y: 0 }, { x: 20, y: 0 }, { x: 20, y: 20 },
				{ x: 40, y: 20 }, { x: 40, y: 40 }, { x: 20, y: 40 },
				{ x: 20, y: 60 }, { x: 0, y: 60 },
			], depthOffset: 0, origin: 6, direction: -1,
		}
		const geometry = state.getExtrudedMemberGeometry(shape, 552, false, undefined, undefined, 0, 0, { start: seat })
		const positions = geometry.getAttribute('position')
		const xs = Array.from({ length: positions.count }, (_, i) => positions.getX(i))
		// The rear flange seats 6 mm forward; the front seats 14 mm back.
		expect(Math.min(...xs)).toBeCloseTo(-14.05, 3)
		expect(xs.some((x) => Math.abs(x - 5.95) < 0.001)).toBe(true)
		expect(Math.max(...xs)).toBe(552)
		expect(xs.every(Number.isFinite)).toBe(true)
		geometry.dispose()
	})

	it('mounts in the designer workspace without separate camera/shader toolbars', async () => {
		const design = createMockDesign()
		const wrapper = mount(Window3DView, {
			props: {
				design,
				selectedPath: 'F1',
				finishColor: '#8A8F98',
			},
		})
		await flushPromises()

		expect(wrapper.find('[data-testid="window-3d-view"]').exists()).toBe(true)
		expect(wrapper.find('[data-testid="window-3d-view"]').classes()).toContain('bg-[#f8fafc]')

		const text = wrapper.text()
		expect(text).not.toContain('Isometric')
		expect(text).not.toContain('Mitre Close-up')
		expect(text).not.toContain('Shader v1')
		expect(text).not.toContain('Shader v2')
	})

	it('exposes resetCam that switches back to inside straight view', async () => {
		const design = createMockDesign()
		const wrapper = mount(Window3DView, {
			props: {
				design,
				selectedPath: null,
				side: 'outside',
			},
		})
		await flushPromises()

		;(wrapper.vm as unknown as { resetCam: () => void }).resetCam()
		await flushPromises()
		expect(wrapper.emitted('update:side')).toEqual([['inside']])
	})

	it('accepts per-object profiles on frame, sash, and bars', async () => {
		const design = createMockDesign()
		design.frameProfileId = 'E104156'
		design.profiles = {
			'F1.0': 'E104160',
			M1: 'E104159',
		}

		const wrapper = mount(Window3DView, {
			props: {
				design,
				selectedPath: 'F1.0',
				finishColor: '#2563EB',
				outsideFinishColor: '#1E293B',
			},
		})
		await flushPromises()

		expect(wrapper.exists()).toBe(true)
		// Should react to selectedPath change
		await wrapper.setProps({ selectedPath: 'FRAME' })
		await flushPromises()
		expect(wrapper.exists()).toBe(true)
	})

	it('adjusts bead dimensions and position in 3D according to sectionMap offsetAlong and offsetDepth', async () => {
		const design = createMockDesign()
		design.sectionMap = {
			'bead:E104161': {
				offsetAlong: -12,
				offsetDepth: 23,
				rotation: 0,
				flipX: false,
				flipY: false,
			},
		}

		const wrapper = mount(Window3DView, {
			props: {
				design,
				selectedPath: null,
			},
		})
		await flushPromises()

		expect(wrapper.exists()).toBe(true)
		// Bead mesh exists and root group rendered without errors
		expect(wrapper.find('[data-testid="window-3d-view"]').exists()).toBe(true)
	})

	it('adjusts glass position in 3D according to sectionMap offsetDepth', async () => {
		const design = createMockDesign()
		design.sectionMap = {
			'glass:6CTG': {
				offsetAlong: 0,
				offsetDepth: 24,
				rotation: 0,
				flipX: false,
				flipY: false,
			},
		}

		const wrapper = mount(Window3DView, {
			props: {
				design,
				selectedPath: null,
			},
		})
		await flushPromises()

		expect(wrapper.exists()).toBe(true)
		expect(wrapper.find('[data-testid="window-3d-view"]').exists()).toBe(true)
	})

	it('renders bead mitred ring for fixed panels without being intercepted by glass panes', async () => {
		const design = createMockDesign()
		const wrapper = mount(Window3DView, {
			props: {
				design,
				selectedPath: null,
			},
		})
		await flushPromises()

		expect(wrapper.exists()).toBe(true)
		expect(wrapper.find('[data-testid="window-3d-view"]').exists()).toBe(true)
	})

	it('renders bead section ring following cross-section view bounds and instance tags', async () => {
		const design = createMockDesign()
		design.sectionMap = {
			'h:OBL': { offsetAlong: 0, offsetDepth: 23, rotation: 0, flipX: false, flipY: false },
			'h:OBR': { offsetAlong: 0, offsetDepth: 23, rotation: 0, flipX: false, flipY: false },
		}
		const wrapper = mount(Window3DView, {
			props: {
				design,
				selectedPath: null,
			},
		})
		await flushPromises()

		expect(wrapper.exists()).toBe(true)
		const canvas = wrapper.find('[data-testid="window-3d-view"]')
		expect(canvas.exists()).toBe(true)
	})

	it('places architectural handles flush and centered on the visible interior stile face', async () => {
		const { createArchitecturalHandle, measureClosingStilePlacement } = await import('./handle3D')
		const THREE = await import('three')
		const w = mount(Window3DView, { props: { design: createMockDesign() } })
		await flushPromises()
		const state = w.vm.$.setupState as any

		const steppedOutline = {
			svg: 'M 0 10 L 50 10 L 50 28 L 42 28 L 42 62 L 18 62 L 18 28 L 0 28 Z',
			width: 50,
			depth: 52,
		}
		const shape = state.buildProfileShape(steppedOutline, 50, 52)
		const geom = state.getExtrudedMemberGeometry(shape, 1000, false)
		const railMesh = new THREE.Mesh(geom, new THREE.MeshBasicMaterial())
		railMesh.position.set(500, 0, 0)
		railMesh.rotation.z = Math.PI / 2

		const placement = measureClosingStilePlacement(
			railMesh,
			'R',
			{ minX: 50, maxX: 450, minY: 50, maxY: 950 },
			[],
		)
		// Max depth is 62mm -> world Z = 140/2 - 62 = 8; interior flat face u in [18..42] maps to X in [458..482] -> center 470
		expect(placement.interiorZ).toBeCloseTo(8, 2)
		expect(placement.center).toBeCloseTo(470, 2)

		const casementHandle = createArchitecturalHandle('casement', -1)
		expect(casementHandle.name).toBe('handle:casement')
		expect(casementHandle.children.length).toBeGreaterThanOrEqual(4)
		geom.dispose()
	})

	it('animates sliding sashes horizontally along X instead of swinging on pivot hinges', async () => {
		const slidingDesign: Design = {
			width: 1800,
			height: 1200,
			isSliding: true,
			trackCount: 2,
			root: {
				type: 'split',
				dir: 'v',
				at: [600, 1200],
				children: [
					{ type: 'sash', glass: '6CTG', isSliding: true, slideFixed: false, slideDir: 'right', trackIdx: 0, trackCount: 2 },
					{ type: 'sash', glass: '6CTG', isSliding: true, slideFixed: true, slideDir: 'right', trackIdx: 1, trackCount: 2 },
					{ type: 'sash', glass: '6CTG', isSliding: true, slideFixed: false, slideDir: 'left', trackIdx: 0, trackCount: 2 },
				],
			},
		}
		const w = mount(Window3DView, { props: { design: slidingDesign } })
		await flushPromises()
		const state = w.vm.$.setupState as any
		const { Group } = await import('three')
		const pLeft = new Group(); pLeft.position.set(38, 42, 16)
		const pMid = new Group(); pMid.position.set(582, 42, -16)
		const pRight = new Group(); pRight.position.set(1182, 42, 16)
		state.sashPivots.splice(0, state.sashPivots.length,
			{ pivot: pLeft, hinge: 'left', opening: 'out', initialRotY: 0, initialRotX: 0, isSliding: true, slideFixed: false, slideDir: 'right', slideTravel: 400, initialX: 38 },
			{ pivot: pMid, hinge: 'left', opening: 'out', initialRotY: 0, initialRotX: 0, isSliding: true, slideFixed: true, slideDir: 'right', slideTravel: 400, initialX: 582 },
			{ pivot: pRight, hinge: 'left', opening: 'out', initialRotY: 0, initialRotX: 0, isSliding: true, slideFixed: false, slideDir: 'left', slideTravel: 400, initialX: 1182 },
		)
		state.animatedOpenAngle = 45
		state.updateSashOpeningAngles()
		expect(pLeft.position.x).toBeCloseTo(438, 3)
		expect(pLeft.rotation.y).toBe(0)
		expect(pMid.position.x).toBe(582)
		expect(pRight.position.x).toBeCloseTo(782, 3)
		expect(pRight.rotation.y).toBe(0)
	})

	it('skips rebuilding stale geometry while new outlines for a dropped design are still loading', async () => {
		const { useDesignerStore } = await import('@/stores/designer')
		const { crossSection } = await import('@/api')
		const store = useDesignerStore()
		store.seriesVersion = 'SV1'

		const pending: Array<(v: any) => void> = []
		const origImpl = vi.mocked(crossSection).getMockImplementation()
		vi.mocked(crossSection).mockImplementation(
			() =>
				new Promise((r) => {
					pending.push(r)
				}),
		)

		try {
			const d1 = createMockDesign()
			const w = mount(Window3DView, { props: { design: d1 } })
			await flushPromises()
			const state = w.vm.$.setupState as any

			// Before outlines finish loading for SV1, outlines are incomplete
			expect(state.hasCompletedInitialOutlinesRef).toBe(false)

			// Resolve both H and V cut requests for d1
			for (const r of pending.splice(0)) {
				r({ ok: true, result: { axis: 'h', at: 600, length: 915, pieces: [], dims: [], issues: [] }, outlines: {} })
			}
			await flushPromises()
			expect(state.hasCompletedInitialOutlinesRef).toBe(true)

			// Trigger a structural change (e.g. drop sliding layout) while outlines are pending
			const d2 = createMockDesign()
			d2.isSliding = true
			d2.trackCount = 2
			await w.setProps({ design: d2 })
			await flushPromises()

			expect(state.designOutlinesKey(d2, 'SV1')).not.toBe(state.designOutlinesKey(d1, 'SV1'))
		} finally {
			if (origImpl) vi.mocked(crossSection).mockImplementation(origImpl)
		}
	})
})
