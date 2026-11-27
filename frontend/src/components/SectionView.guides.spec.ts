import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import w01 from '@/design/__fixtures__/w01.json'
import type { Design } from '@/design/types'
import SectionView from './SectionView.vue'

/**
 * Isolates the overlay: the guide engine is replaced by a fixed result so this file
 * only tests what SectionView draws (and when it clears it), not the maths.
 * The maths is covered by sectionSmartGuides.spec.ts.
 */
const fake = vi.hoisted(() => ({
	guides: { deltaX: 0, deltaY: 0, lines: [], gaps: [] } as unknown,
	cut: null as unknown,
}))

vi.mock('@/api', () => ({
	crossSection: async () => structuredClone(fake.cut),
}))

vi.mock('./sectionSmartGuides', () => ({
	computeSmartGuides: () => fake.guides,
	measureGuides: () => fake.guides,
}))

const OUTLINE = (w: number, d: number) => ({ svg: `M 0 0 L ${w} 0 L ${w} ${d} L 0 ${d} Z`, width: w, depth: d })

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
		dims: [],
		issues: [],
	},
	outlines: { E104156: OUTLINE(50, 70), E104160: OUTLINE(60, 65), E104159: OUTLINE(70, 70) },
}

function mountView() {
	return mount(SectionView, {
		props: { design: structuredClone(w01) as Design, seriesVersion: 'SV1', axis: 'h', at: null },
	})
}

describe('SectionView smart-guide overlay', () => {
	enableAutoUnmount(afterEach)
	beforeEach(() => {
		fake.cut = structuredClone(W01_CUT)
		fake.guides = { deltaX: 0, deltaY: 0, lines: [], gaps: [] }
		vi.useFakeTimers()
	})
	afterEach(() => vi.useRealTimers())

	it('draws centre guides and distance pills while dragging, and clears them on drop', async () => {
		fake.guides = {
			deltaX: 0,
			deltaY: 0,
			lines: [
				{ axis: 'x', pos: 457.5, start: -10, end: 80, type: 'center' },
				{ axis: 'y', pos: 70, start: 0, end: 300, type: 'edge' },
			],
			gaps: [
				{ axis: 'x', start: 50, end: 99, perpPos: 35, gap: 49, equal: true },
				{ axis: 'y', start: 10, end: 40, perpPos: 120, gap: 30.5, equal: false },
			],
		}
		const w = mountView()
		await flushPromises()

		const sash = w.get('[data-piece-group="1"]')
		await sash.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		await sash.trigger('pointermove', { clientX: 105, clientY: 100, pointerId: 1 })

		expect(w.find('[data-testid="smart-guides-overlay"]').exists()).toBe(true)

		const centre = w.get('[data-guide-type="center"]')
		expect(centre.attributes('stroke-dasharray')).toBeDefined() // dashed = centre
		expect(w.get('[data-guide-type="edge"]').attributes('stroke-dasharray')).toBeUndefined()

		const pills = w.findAll('[data-testid="smart-guide-gap"]')
		expect(pills).toHaveLength(2)
		expect(pills[0].text()).toBe('49')
		expect(pills[0].attributes('data-equal')).toBe('true')
		expect(pills[1].text()).toBe('30.5')
		expect(pills[1].attributes('data-equal')).toBe('false')

		await sash.trigger('pointerup', { pointerId: 1 })
		expect(w.find('[data-testid="smart-guides-overlay"]').exists()).toBe(false)
	})

	it('draws no overlay when there is nothing to show', async () => {
		const w = mountView()
		await flushPromises()
		const sash = w.get('[data-piece-group="1"]')
		await sash.trigger('pointerdown', { clientX: 100, clientY: 100, button: 0, pointerId: 1 })
		await sash.trigger('pointermove', { clientX: 105, clientY: 100, pointerId: 1 })
		expect(w.find('[data-testid="smart-guides-overlay"]').exists()).toBe(false)
		await sash.trigger('pointerup', { pointerId: 1 })
	})
})

