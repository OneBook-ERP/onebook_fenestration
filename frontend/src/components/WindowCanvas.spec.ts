import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import w01 from '@/design/__fixtures__/w01.json'
import type { Design } from '@/design/types'
import WindowCanvas from './WindowCanvas.vue'

function mountCanvas(props: Record<string, unknown> = {}) {
	return mount(WindowCanvas, {
		props: { design: w01 as Design, selectedPath: null, issuePaths: [], view: 'inside', ...props },
	})
}

const SCALE_W01 = Math.min(520 / 915, 640 / 1220)

describe('WindowCanvas', () => {
	it('renders W01 cells, bar label and dimensions', () => {
		const w = mountCanvas()
		const paths = w.findAll('rect[data-path]').map((r) => r.attributes('data-path'))
		expect(paths).toEqual(['F1.0', 'F1.1'])
		const texts = w.findAll('text').map((t) => t.text())
		expect(texts).toContain('M1')
		expect(texts).toContain('457.5')
		expect(texts).toContain('915')
		expect(texts).toContain('GHH = 732')
	})

	it('emits select on cell click', async () => {
		const w = mountCanvas()
		await w.find('[data-path="F1.1"]').trigger('click')
		expect(w.emitted('select')![0]).toEqual(['F1.1'])
	})

	it('emits move-split when dragging a bar', async () => {
		const w = mountCanvas()
		const bar = w.find('[data-bar="M1"]')
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 1 })
		await bar.trigger('pointermove', { clientX: 120, pointerId: 1 })
		const ev = w.emitted('move-split')![0][0] as { splitPath: string; index: number; pos: number }
		expect(ev.splitPath).toBe('F1')
		expect(ev.index).toBe(0)
		expect(ev.pos).toBeGreaterThan(457.5)
		expect(ev.pos).toBeCloseTo(457.5 + 20 / SCALE_W01, 6)
	})

	it('converts drag deltas through the rendered size', async () => {
		const w = mountCanvas()
		vi.spyOn(w.find('svg').element, 'getBoundingClientRect').mockReturnValue({
			width: 320, height: 380, x: 0, y: 0, top: 0, left: 0, right: 320, bottom: 380, toJSON() {},
		} as DOMRect)
		const bar = w.find('[data-bar="M1"]')
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 1 })
		await bar.trigger('pointermove', { clientX: 120, pointerId: 1 })
		const ev = w.emitted('move-split')![0][0] as { pos: number }
		expect(ev.pos).toBeCloseTo(457.5 + 40 / SCALE_W01, 6)
	})

	it('scales to its container and keeps drag math in a letterboxed box', async () => {
		const w = mountCanvas()
		const el = w.find('svg')
		expect(el.attributes('width')).toBe('100%')
		expect(el.attributes('height')).toBe('100%')
		expect(el.attributes('preserveAspectRatio')).toBe('xMidYMid meet')
		vi.spyOn(el.element, 'getBoundingClientRect').mockReturnValue({
			width: 1280, height: 380, x: 0, y: 0, top: 0, left: 0, right: 1280, bottom: 380, toJSON() {},
		} as DOMRect)
		const bar = w.find('[data-bar="M1"]')
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 1 })
		await bar.trigger('pointermove', { clientX: 120, pointerId: 1 })
		const ev = w.emitted('move-split')![0][0] as { pos: number }
		// meet scale is min(1280/640, 380/760) = 0.5, so 20 px is 40 viewBox units
		expect(ev.pos).toBeCloseTo(457.5 + 40 / SCALE_W01, 6)
	})

	it('exported markup has a fixed pixel size', () => {
		const m = (mountCanvas().vm as unknown as { getSvgMarkup(): string }).getSvgMarkup()
		expect(m).toContain('width="640"')
		expect(m).toContain('height="760"')
	})

	it('ends a drag on window pointerup and on lostpointercapture', async () => {
		const w = mountCanvas()
		const bar = w.find('[data-bar="M1"]')
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 1 })
		await bar.trigger('pointermove', { clientX: 120, pointerId: 1 })
		window.dispatchEvent(new Event('pointerup'))
		expect(w.emitted('drag-end')).toHaveLength(1)
		await bar.trigger('pointermove', { clientX: 140, pointerId: 1 })
		expect(w.emitted('move-split')).toHaveLength(1)
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 2 })
		await bar.trigger('lostpointercapture', { pointerId: 2 })
		expect(w.emitted('drag-end')).toHaveLength(2)
		window.dispatchEvent(new Event('pointerup'))
		expect(w.emitted('drag-end')).toHaveLength(2)
	})

	it('labels fixed panes by glass number only, sashes S<n> and louvers L<n>', () => {
		const d: Design = {
			width: 1800, height: 1200,
			root: { type: 'split', dir: 'v', at: [600, 1200], children: [
				{ type: 'fixed', glass: 'G' }, { type: 'sash', glass: 'G' }, { type: 'louver', glass: 'G', blades: 3 },
			] },
		}
		const texts = mountCanvas({ design: d }).findAll('text').map((t) => t.text())
		expect(texts.filter((t) => /^F\d+$/.test(t))).toEqual([])
		expect(texts).toContain('S1')
		expect(texts).toContain('L1')
		expect(texts).toContain('1')
	})

	it('drags horizontal bars with inverted y', async () => {
		const d: Design = {
			width: 1500, height: 1500,
			root: { type: 'split', dir: 'h', at: [750], children: [{ type: 'fixed', glass: 'G' }, { type: 'fixed', glass: 'G' }] },
		}
		const w = mountCanvas({ design: d })
		const bar = w.find('[data-bar="T1"]')
		await bar.trigger('pointerdown', { clientY: 100, pointerId: 1 })
		await bar.trigger('pointermove', { clientY: 120, pointerId: 1 })
		const ev = w.emitted('move-split')![0][0] as { pos: number }
		expect(ev.pos).toBeCloseTo(750 - 20 / Math.min(520 / 1500, 640 / 1500), 6)
	})

	it('emits drag-start and drag-end around a bar drag', async () => {
		const w = mountCanvas()
		const bar = w.find('[data-bar="M1"]')
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 1 })
		expect(w.emitted('drag-start')).toHaveLength(1)
		await bar.trigger('pointermove', { clientX: 120, pointerId: 1 })
		expect(w.emitted('drag-end')).toBeUndefined()
		await bar.trigger('pointerup', { clientX: 120, pointerId: 1 })
		expect(w.emitted('drag-end')).toHaveLength(1)
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 2 })
		await bar.trigger('pointercancel', { pointerId: 2 })
		expect(w.emitted('drag-end')).toHaveLength(2)
	})

	it('ignores moves after pointerup', async () => {
		const w = mountCanvas()
		const bar = w.find('[data-bar="M1"]')
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 1 })
		await bar.trigger('pointerup', { clientX: 100, pointerId: 1 })
		await bar.trigger('pointermove', { clientX: 140, pointerId: 1 })
		expect(w.emitted('move-split')).toBeUndefined()
	})

	it('labels sash opening direction, independent of view', async () => {
		const w = mountCanvas()
		const outs = () => w.findAll('text').filter((t) => t.text() === 'OUT')
		expect(outs()).toHaveLength(2)
		await w.setProps({ view: 'outside' })
		expect(outs()).toHaveLength(2)
		expect(w.text()).toContain('View from outside')
		const d = structuredClone(w01) as Design
		;(d.root as any).children[0].opening = 'in'
		const w2 = mountCanvas({ design: d })
		const t = w2.findAll('text').map((x) => x.text())
		expect(t.filter((x) => x === 'IN')).toHaveLength(1)
		expect(t.filter((x) => x === 'OUT')).toHaveLength(1)
	})

	it('flips the swing apex when viewed from outside', async () => {
		const w = mountCanvas()
		const pts = () => w.find('polyline').attributes('points')
		const inside = pts()
		await w.setProps({ view: 'outside' })
		expect(pts()).not.toBe(inside)
	})

	it('draws a top-hung swing with the apex at the top edge centre', async () => {
		const d = structuredClone(w01) as Design
		;(d.root as any).children[0].hinge = 'top'
		const w = mountCanvas({ design: d })
		const apex = () => {
			const pts = w.find('polyline').attributes('points')!.split(' ').map((p) => p.split(',').map(Number))
			return { pts, apex: pts[1] }
		}
		for (const view of ['inside', 'outside']) {
			await w.setProps({ view })
			const { pts, apex: [ax, ay] } = apex()
			expect(ay).toBeLessThan(pts[0][1])
			expect(pts[0][1]).toBe(pts[2][1])
			expect(ax).toBeCloseTo((pts[0][0] + pts[2][0]) / 2, 6)
		}
	})

	it('exports a clean drawing', () => {
		const w = mountCanvas({ selectedPath: 'F1.0', issuePaths: ['F1.1'] })
		const m = (w.vm as unknown as { getSvgMarkup(): string }).getSvgMarkup()
		for (const bad of ['#2563EB', '#D97706', 'data-path', 'data-bar', 'cursor']) expect(m).not.toContain(bad)
	})

	it('ignores non-primary button presses', async () => {
		const w = mountCanvas()
		const bar = w.find('[data-bar="M1"]')
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 1, button: 2 })
		await bar.trigger('pointermove', { clientX: 120, pointerId: 1 })
		expect(w.emitted('move-split')).toBeUndefined()
	})

	it('outlines the selected cell', () => {
		const w = mountCanvas({ selectedPath: 'F1.0' })
		expect(w.find('[data-path="F1.0"]').attributes('stroke')).toBe('#2563EB')
		expect(w.find('[data-path="F1.1"]').attributes('stroke')).not.toBe('#2563EB')
	})

	it('outlines issue cells in amber', () => {
		const w = mountCanvas({ issuePaths: ['F1.1'] })
		expect(w.find('[data-path="F1.1"]').attributes('stroke')).toBe('#D97706')
	})

	it('exposes clean svg markup', () => {
		const w = mountCanvas()
		const markup = (w.vm as unknown as { getSvgMarkup(): string }).getSvgMarkup()
		expect(markup.startsWith('<svg')).toBe(true)
		expect(markup).not.toContain('<script')
		expect(markup).not.toMatch(/\son[a-z]+=/)
	})
})
