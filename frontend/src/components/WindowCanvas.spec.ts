import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import w01 from '@/design/__fixtures__/w01.json'
import type { Design } from '@/design/types'
import WindowCanvas, { MAX_PAN_OFFSET, MAX_ZOOM, MIN_ZOOM } from './WindowCanvas.vue'

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

	it('fills the frame with the finish colour and lightens the sash', () => {
		const w = mountCanvas({ finishColor: '#6B3E26' })
		expect(w.find('svg > rect:nth-of-type(2)').attributes('fill')).toBe('#6B3E26')
		expect(w.find('[data-path="F1.1"]').attributes('fill')).toBe('#7A513C')
	})

	it('falls back to the default finish colour for non-#RRGGBB colours', () => {
		for (const finishColor of ['red', '#abc', 'rgb(1, 2, 3)', '']) {
			const w = mountCanvas({ finishColor })
			expect(w.find('svg > rect:nth-of-type(2)').attributes('fill')).toBe('#8A8F98')
			expect(w.find('[data-path="F1.1"]').attributes('fill')).toBe('#969AA2')
		}
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
	it('cut_marker_click_moves_cut', async () => {
		const w = mountCanvas({ section: { axis: 'h', h: 610, v: 228.75 } })
		expect(w.findAll('[data-cut]').map((g) => g.attributes('data-cut'))).toEqual(['v', 'h'])
		const labels = w.findAll('[data-cut] text').map((t) => t.text())
		expect(labels.filter((t) => t === 'A')).toHaveLength(2)
		expect(labels.filter((t) => t === 'B')).toHaveLength(2)
		await w.find('[data-path="F1.1"]').trigger('click')
		expect(w.emitted('update:cut')![0]).toEqual([{ axis: 'h', at: 610 }])
		expect(w.emitted('select')![0]).toEqual(['F1.1'])
		await w.setProps({ section: { axis: 'v', h: 610, v: 228.75 } })
		await w.find('[data-path="F1.1"]').trigger('click')
		expect(w.emitted('update:cut')![1]).toEqual([{ axis: 'v', at: 686.25 }])
	})

	it('draws the active cut line at its position', () => {
		const w = mountCanvas({ section: { axis: 'v', h: 610, v: 228.75 } })
		const line = w.get('[data-cut="v"] line')
		const x = (640 - 915 * SCALE_W01) / 2 + 228.75 * SCALE_W01
		expect(Number(line.attributes('x1'))).toBeCloseTo(x, 6)
		expect(line.attributes('x1')).toBe(line.attributes('x2'))
		expect(w.get('[data-cut="v"]').attributes('opacity')).toBe('1')
		expect(Number(w.get('[data-cut="h"]').attributes('opacity'))).toBeLessThan(1)
	})

	it('has no cut markers or cut events without a section', async () => {
		const w = mountCanvas()
		expect(w.findAll('[data-cut]')).toHaveLength(0)
		await w.find('[data-path="F1.1"]').trigger('click')
		expect(w.emitted('update:cut')).toBeUndefined()
	})

	it('leaves cut markers out of the exported drawing', () => {
		const w = mountCanvas({ section: { axis: 'h', h: 610, v: 228.75 } })
		const m = (w.vm as unknown as { getSvgMarkup(): string }).getSvgMarkup()
		expect(m).not.toContain('stroke-dasharray="12 4 3 4"')
		expect(m).not.toContain('>A<')
	})

	it('zooms in and out with controls, mouse wheel, and keys while clamping to MIN_ZOOM and MAX_ZOOM', async () => {
		const w = mountCanvas()
		const svg = w.find('svg')
		expect(svg.attributes('viewBox')).toBe('0 0 640 760')

		await w.find('button[aria-label="Zoom in"]').trigger('click')
		expect(w.find('button[aria-label="Reset zoom"]').text()).toBe('115%')

		await svg.trigger('wheel', { deltaY: 100 })
		expect(w.find('button[aria-label="Reset zoom"]').text()).toBe('100%')

		for (let i = 0; i < 30; i++) {
			window.dispatchEvent(new KeyboardEvent('keydown', { key: '-' }))
		}
		await w.vm.$nextTick()
		expect((w.vm as any).zoom).toBe(MIN_ZOOM)
		expect(w.find('button[aria-label="Zoom out"]').attributes('disabled')).toBeDefined()

		for (let i = 0; i < 40; i++) {
			window.dispatchEvent(new KeyboardEvent('keydown', { key: '+' }))
		}
		await w.vm.$nextTick()
		expect((w.vm as any).zoom).toBe(MAX_ZOOM)
		expect(w.find('button[aria-label="Zoom in"]').attributes('disabled')).toBeDefined()

		window.dispatchEvent(new KeyboardEvent('keydown', { key: '0' }))
		await w.vm.$nextTick()
		expect((w.vm as any).zoom).toBe(1)
		expect(svg.attributes('viewBox')).toBe('0 0 640 760')
		w.unmount()
	})

	it('holds Shift to grab and move around the workspace and clamps pan to MAX_PAN_OFFSET', async () => {
		const w = mountCanvas()
		const svg = w.find('svg')
		window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Shift' }))
		await w.vm.$nextTick()
		expect(svg.attributes('style')).toContain('cursor: grab')

		await svg.trigger('pointerdown', { clientX: 200, clientY: 200, shiftKey: true, button: 0, pointerId: 1 })
		expect(svg.attributes('style')).toContain('cursor: grabbing')

		await svg.trigger('pointermove', { clientX: 280, clientY: 250, shiftKey: true, pointerId: 1 })
		expect((w.vm as any).pan).toEqual({ x: 80, y: 50 })

		await svg.trigger('pointermove', { clientX: 9999, clientY: -9999, shiftKey: true, pointerId: 1 })
		expect((w.vm as any).pan).toEqual({ x: MAX_PAN_OFFSET, y: -MAX_PAN_OFFSET })

		await svg.trigger('pointerup', { pointerId: 1 })
		window.dispatchEvent(new KeyboardEvent('keyup', { key: 'Shift' }))
		await w.vm.$nextTick()

		// Exported SVG markup resets viewBox and background rect to canonical 640x760
		const m = (w.vm as unknown as { getSvgMarkup(): string }).getSvgMarkup()
		expect(m).toContain('viewBox="0 0 640 760"')
		expect(m).toContain('width="640"')
		expect(m).toContain('height="760"')
		w.unmount()
	})

	it('renders 45° miter or 90° butt corner cut lines on frame and sashes', async () => {
		const w = mountCanvas()
		const frameCuts = () => w.findAll('line[data-corner-cut="frame"]')
		const sashCuts = () => w.findAll('line[data-corner-cut="sash"]')
		expect(frameCuts()).toHaveLength(4)
		expect(sashCuts()).toHaveLength(8) // 2 sashes * 4 corners
		for (const ln of [...frameCuts(), ...sashCuts()]) {
			expect(ln.attributes('data-cut-angle')).toBe('45')
			// 45° miter line has non-zero dx and dy
			expect(Number(ln.attributes('x1'))).not.toBe(Number(ln.attributes('x2')))
			expect(Number(ln.attributes('y1'))).not.toBe(Number(ln.attributes('y2')))
		}

		// When members specify 90° butt joints
		await w.setProps({
			members: [
				{ role: 'frame', path: 'F1', angles: [90, 90] },
				{ role: 'sash', path: 'F1.0', angles: '[90, 90]' },
				{ role: 'sash', path: 'F1.1', angles: '45/135' },
			],
		})
		for (const ln of frameCuts()) {
			expect(ln.attributes('data-cut-angle')).toBe('90')
			expect(Number(ln.attributes('y1'))).toBeCloseTo(Number(ln.attributes('y2')), 6)
		}
		expect(sashCuts().slice(0, 4).every((ln) => ln.attributes('data-cut-angle') === '90')).toBe(true)
		expect(sashCuts().slice(4, 8).every((ln) => ln.attributes('data-cut-angle') === '45')).toBe(true)
	})

	it('places handles at the center of each sash opposite to the hinge and draws a red hinge side line', async () => {
		const w = mountCanvas()
		const handles = w.findAll('rect[data-handle="true"]')
		expect(handles).toHaveLength(2)

		const cell0 = w.find('[data-path="F1.0"]')
		const cell1 = w.find('[data-path="F1.1"]')
		const box0 = {
			x: Number(cell0.attributes('x')),
			y: Number(cell0.attributes('y')),
			w: Number(cell0.attributes('width')),
			h: Number(cell0.attributes('height')),
		}
		const box1 = {
			x: Number(cell1.attributes('x')),
			y: Number(cell1.attributes('y')),
			w: Number(cell1.attributes('width')),
			h: Number(cell1.attributes('height')),
		}

		// Vertically centered on each sash
		const h0CenterY = Number(handles[0].attributes('y')) + Number(handles[0].attributes('height')) / 2
		const h1CenterY = Number(handles[1].attributes('y')) + Number(handles[1].attributes('height')) / 2
		expect(h0CenterY).toBeCloseTo(box0.y + box0.h / 2, 5)
		expect(h1CenterY).toBeCloseTo(box1.y + box1.h / 2, 5)

		// S1 has left hinge -> handle on right half of S1; S2 has right hinge -> handle on left half of S2
		const h0CenterX = Number(handles[0].attributes('x')) + Number(handles[0].attributes('width')) / 2
		const h1CenterX = Number(handles[1].attributes('x')) + Number(handles[1].attributes('width')) / 2
		expect(h0CenterX).toBeGreaterThan(box0.x + box0.w / 2)
		expect(h1CenterX).toBeLessThan(box1.x + box1.w / 2)

		// Hinge lines in red (#DC2626) on the hinged sides (left edge of S1, right edge of S2)
		const hingeLines = w.findAll('line[data-hinge-line="true"]')
		expect(hingeLines).toHaveLength(2)
		expect(hingeLines[0].attributes('stroke')).toBe('#DC2626')
		expect(Number(hingeLines[0].attributes('x1'))).toBeCloseTo(box0.x, 5)
		expect(Number(hingeLines[0].attributes('x2'))).toBeCloseTo(box0.x, 5)
		expect(hingeLines[1].attributes('stroke')).toBe('#DC2626')
		expect(Number(hingeLines[1].attributes('x1'))).toBeCloseTo(box1.x + box1.w, 5)
		expect(Number(hingeLines[1].attributes('x2'))).toBeCloseTo(box1.x + box1.w, 5)
	})

	it('selects panels reliably even after panning the workspace', async () => {
		const w = mountCanvas()
		const svg = w.find('svg')
		await svg.trigger('pointerdown', { clientX: 100, clientY: 100, shiftKey: true, button: 0, pointerId: 1 })
		await svg.trigger('pointermove', { clientX: 160, clientY: 140, shiftKey: true, pointerId: 1 })
		await svg.trigger('pointerup', { pointerId: 1 })

		await new Promise((r) => setTimeout(r, 10))
		await w.find('[data-path="F1.1"]').trigger('click', { shiftKey: false })
		expect(w.emitted('select')![0]).toEqual(['F1.1'])
	})

	it('shows sash width & height and glass width & height when a sash (e.g. S2 / F1.1) is selected', () => {
		const w = mountCanvas({
			selectedPath: 'F1.1',
			members: [
				{ role: 'sash', path: 'F1.1', position: 'B', length: 577 },
				{ role: 'sash', path: 'F1.1', position: 'L', length: 1164 },
			],
			glass: [{ path: 'F1.1', width: 475.5, height: 1063 }],
		})
		const dims = w.find('[data-selected-dims="F1.1"]')
		expect(dims.exists()).toBe(true)
		expect(dims.text()).toContain('Sash: 577 × 1164 mm')
		expect(dims.text()).toContain('Glass: 475.5 × 1063 mm')
		expect(dims.text()).toContain('Glass W: 475.5')
		expect(dims.text()).toContain('Glass H: 1063')
	})

	it('allows selecting the center mullion M1 and shows its specific dimensions', async () => {
		const w = mountCanvas({
			selectedPath: 'M1',
			members: [{ role: 'mullion', panel: 'M1', length: 1136 }],
		})
		const bar = w.find('[data-bar="M1"]')
		expect(bar.attributes('stroke')).toBe('#2563EB')

		const barDims = w.find('[data-bar-dims="M1"]')
		expect(barDims.exists()).toBe(true)
		expect(barDims.text()).toContain('M1: 1136 × 40 mm')
		expect(barDims.text()).toContain('Pos: 457.5 mm')
		expect(barDims.text()).toContain('Span: 1220 mm')

		// Clicking the mullion or its badge emits select('M1')
		await w.find('[data-bar-badge="M1"]').trigger('click')
		expect(w.emitted('select')![0]).toEqual(['M1'])

		// Clean SVG export strips selection overlays on bars too
		const m = (w.vm as unknown as { getSvgMarkup(): string }).getSvgMarkup()
		expect(m).not.toContain('#2563EB')
	})

	it('deselects everything when clicking outside the window on the workspace background', async () => {
		const w = mountCanvas({ selectedPath: 'F1.1' })
		await w.find('rect[data-workspace-bg="true"]').trigger('click')
		expect(w.emitted('select')![0]).toEqual([''])
	})

	it('allows selecting outer frame (FRAME), sash (F1.1), and glass (GLASS:F1.1) individually', async () => {
		const w = mountCanvas()
		// Click outer frame
		await w.find('rect[data-frame="FRAME"]').trigger('click')
		expect(w.emitted('select')![0]).toEqual(['FRAME'])

		// Click glass pane inside sash F1.1
		await w.find('rect[data-glass="F1.1"]').trigger('click')
		expect(w.emitted('select')![1]).toEqual(['GLASS:F1.1'])

		// Click sash badge S1 (F1.1)
		await w.find('[data-panel-badge="F1.1"]').trigger('click')
		expect(w.emitted('select')![2]).toEqual(['F1.1'])

		// Render selected outer frame dimensions when selectedPath === 'FRAME'
		await w.setProps({ selectedPath: 'FRAME' })
		expect(w.find('[data-frame-dims="FRAME"]').exists()).toBe(true)
		expect(w.get('[data-frame-dims="FRAME"]').text()).toContain('Outer Frame: 915 × 1220 mm')
	})
})
