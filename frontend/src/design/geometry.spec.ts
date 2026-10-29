import { describe, expect, it } from 'vitest'
import w01 from './__fixtures__/w01.json'
import { layoutGeom } from './geometry'
import { newDesign, splitCell } from './tree'
import type { Design } from './types'

describe('layoutGeom', () => {
	it('W01 has two cells and bar M1', () => {
		const { cells, bars } = layoutGeom(w01 as Design)
		expect(cells.map((c) => [c.path, c.x, c.y, c.w, c.h])).toEqual([
			['F1.0', 0, 0, 457.5, 1220],
			['F1.1', 457.5, 0, 457.5, 1220],
		])
		expect(bars).toEqual([{ id: 'M1', dir: 'v', splitPath: 'F1', index: 0, x: 457.5, y: 0, length: 1220 }])
	})

	it('numbers nested bars in tree order', () => {
		let d = splitCell(newDesign(1000, 1200), 'F1', 'v') // M1
		d = splitCell(d, 'F1.0', 'h') // T1 (visited before F1.1)
		d = splitCell(d, 'F1.1', 'h') // T2
		d = splitCell(d, 'F1.1.0', 'v') // M2
		const { bars } = layoutGeom(d)
		expect(bars.map((b) => b.id)).toEqual(['M1', 'T1', 'T2', 'M2'])
		const t1 = bars[1]
		expect(t1).toMatchObject({ dir: 'h', splitPath: 'F1.0', x: 0, y: 600, length: 500 })
		expect(bars[3]).toMatchObject({ x: 500 + 250, y: 0, length: 600 })
	})
})
