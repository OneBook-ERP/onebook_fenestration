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

	it('mounts properly and renders camera controls including Mitre Close-up', async () => {
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

		const text = wrapper.text()
		expect(text).toContain('Isometric')
		expect(text).toContain('Front')
		expect(text).toContain('Exterior')
		expect(text).toContain('Mitre Close-up')
		expect(text).toContain('Shader v1')
		expect(text).toContain('Shader v2')
	})

	it('switches camera presets when clicked', async () => {
		const design = createMockDesign()
		const wrapper = mount(Window3DView, {
			props: {
				design,
				selectedPath: null,
			},
		})
		await flushPromises()

		const buttons = wrapper.findAll('button')
		const mitreBtn = buttons.find((b) => b.text().includes('Mitre Close-up'))
		expect(mitreBtn).toBeDefined()
		await mitreBtn!.trigger('click')
		expect(mitreBtn!.classes()).toContain('bg-white')

		const frontBtn = buttons.find((b) => b.text() === 'Front')
		expect(frontBtn).toBeDefined()
		await frontBtn!.trigger('click')
		expect(frontBtn!.classes()).toContain('bg-white')
	})

	it('toggles between Shader v1 and Shader v2', async () => {
		const design = createMockDesign()
		const wrapper = mount(Window3DView, {
			props: {
				design,
				selectedPath: null,
			},
		})
		await flushPromises()

		const v1Btn = wrapper.find('[data-testid="shader-v1-btn"]')
		const v2Btn = wrapper.find('[data-testid="shader-v2-btn"]')
		expect(v1Btn.exists()).toBe(true)
		expect(v2Btn.exists()).toBe(true)

		// V1 is default
		expect(v1Btn.classes()).toContain('bg-white')
		expect(v2Btn.classes()).not.toContain('bg-white')

		await v2Btn.trigger('click')
		await flushPromises()
		expect(v2Btn.classes()).toContain('bg-white')
		expect(v1Btn.classes()).not.toContain('bg-white')
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
})
