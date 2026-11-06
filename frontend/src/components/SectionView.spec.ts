import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import w01 from '@/design/__fixtures__/w01.json'
import type { Design } from '@/design/types'
import SectionView from './SectionView.vue'

const fake = vi.hoisted(() => ({
	calls: [] as Record<string, unknown>[],
	response: null as unknown,
}))

vi.mock('@/api', () => ({
	crossSection: async (design: unknown, seriesVersion: string, axis: string, at: number | null) => {
		fake.calls.push({ design, series_version: seriesVersion, axis, at })
		return structuredClone(fake.response)
	},
}))

const OUTLINE = (w: number, d: number) => ({ svg: `M 0 0 L ${w} 0 L ${w} ${d} L 0 ${d} Z`, width: w, depth: d })

const W01_CUT = {
	ok: true,
	result: {
		axis: 'h',
		at: 610,
		length: 915,
		pieces: [
			{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 0, end: 50, mirrored: false },
			{ kind: 'profile', code: 'E104160', role: 'sash', panel: 'F1-S1', start: 18, end: 78, mirrored: false },
			{ kind: 'glass', code: '6CTG', role: 'glass', panel: 'F1-S1', start: 68.5, end: 401.5, mirrored: false },
			{ kind: 'profile', code: 'E104160', role: 'sash', panel: 'F1-S1', start: 392, end: 452, mirrored: true },
			{ kind: 'profile', code: 'E104159', role: 'mullion', panel: 'M1', start: 422.5, end: 492.5, mirrored: false },
			{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 865, end: 915, mirrored: true },
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
		props: { design: w01 as Design, seriesVersion: 'SV1', axis: 'h', at: null, ...props },
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

	it('renders_a_piece_per_section_piece', async () => {
		const w = mountView()
		await flushPromises()
		expect(fake.calls[0]).toMatchObject({ series_version: 'SV1', axis: 'h', at: null })
		expect((fake.calls[0].design as Design).width).toBe(915)
		const pieces = w.findAll('[data-piece]')
		expect(pieces).toHaveLength(6)
		expect(w.findAll('path[data-piece]')).toHaveLength(5)
		const glass = w.get('[data-piece="2"]')
		expect(glass.element.tagName).toBe('rect')
		expect(glass.attributes('data-kind')).toBe('glass')
		// The mirrored sash flips; the unmirrored one does not.
		expect(w.get('[data-piece="1"]').attributes('transform')).not.toContain('scale(-')
		expect(w.get('[data-piece="3"]').attributes('transform')).toContain('scale(-')
		const texts = w.findAll('text').map((t) => t.text())
		for (const t of ['E104156', 'E104160', 'E104159', '6CTG', '915', '457.5', '333', '50']) expect(texts).toContain(t)
		expect(w.text()).not.toContain('No section outline')
	})

	it('scales each outline to its piece width', async () => {
		fake.response = structuredClone(W01_CUT)
		;(fake.response as typeof W01_CUT).outlines.E104159 = OUTLINE(35, 70)
		const w = mountView()
		await flushPromises()
		const a = w.get('[data-piece="0"]').attributes('transform')!
		const b = w.get('[data-piece="4"]').attributes('transform')!
		const sx = (t: string) => Number(/scale\((-?[\d.]+)/.exec(t)![1])
		// 70 mm mullion from a 35 mm-wide outline is drawn at twice the scale of the 50/50 frame.
		expect(sx(b) / sx(a)).toBeCloseTo(2, 6)
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
		expect(svg.attributes('viewBox')).toMatch(/^0 0 \d+(\.\d+)? \d+(\.\d+)?$/)
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
})
