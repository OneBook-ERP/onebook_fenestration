import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import w01 from '@/design/__fixtures__/w01.json'
import type { Design } from '@/design/types'
import WindowCanvas from './WindowCanvas.vue'

function mountCanvas(props: Record<string, unknown> = {}) {
	return mount(WindowCanvas, {
		props: { design: w01 as Design, selectedPath: null, issuePaths: [], view: 'inside', ...props },
	})
}

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
