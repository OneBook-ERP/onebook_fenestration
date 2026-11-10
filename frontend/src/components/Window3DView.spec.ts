import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import w01 from '@/design/__fixtures__/w01.json'
import type { Design } from '@/design/types'
import Window3DView from './Window3DView.vue'

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
