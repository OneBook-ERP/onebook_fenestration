import { describe, expect, it } from 'vitest'
import { computeSmartGuides, measureGuides, type Rect } from './sectionSmartGuides'

describe('sectionSmartGuides', () => {
	const fixedRects: Rect[] = [
		{ id: 'frame-left', x: 0, y: 0, w: 50, h: 80 },
		{ id: 'mullion-center', x: 200, y: 0, w: 40, h: 80 },
		{ id: 'frame-right', x: 400, y: 0, w: 50, h: 80 },
	]
	const opts = { scaleMmPerPixel: 1, tolerancePx: 5 }

	it('snaps edge-to-edge when close to target X line', () => {
		const moving: Rect = { id: 'bead', x: 198.5, y: 20, w: 25, h: 30 }
		const res = computeSmartGuides(moving, fixedRects, opts)

		expect(res.deltaX).toBe(1.5)
		expect(res.lines.length).toBeGreaterThan(0)
		expect(res.lines.some((l) => l.axis === 'x' && Math.abs(l.pos - 200) < 0.1)).toBe(true)
	})

	it('snaps center-to-center when centers align', () => {
		// mullion centre is x = 220, moving centre is 221 -> delta -1
		const moving: Rect = { id: 'sash', x: 206, y: 0, w: 30, h: 80 }
		const res = computeSmartGuides(moving, fixedRects, opts)

		expect(res.deltaX).toBe(-1)
		expect(res.lines.some((l) => l.axis === 'x' && Math.abs(l.pos - 220) < 0.1 && l.type === 'center')).toBe(true)
	})

	it('snaps top and bottom on Y axis', () => {
		const moving: Rect = { id: 'bead', x: 100, y: 1.5, w: 20, h: 25 }
		const res = computeSmartGuides(moving, fixedRects, opts)

		expect(res.deltaY).toBe(-1.5)
		expect(res.lines.some((l) => l.axis === 'y' && Math.abs(l.pos - 0) < 0.1)).toBe(true)
	})

	it('detects equal spacing between two neighbors and creates red gap pills', () => {
		// frame-left ends at 50, mullion starts at 200: a 30 wide item centres at x = 110
		const moving: Rect = { id: 'sash', x: 111.5, y: 10, w: 30, h: 60 }
		const res = computeSmartGuides(moving, fixedRects, opts)

		expect(res.deltaX).toBe(-1.5)
		expect(res.gaps.length).toBe(2)
		expect(res.gaps[0].gap).toBe(60)
		expect(res.gaps[1].gap).toBe(60)
		expect(res.gaps.every((g) => g.equal)).toBe(true)
	})

	it('scales tolerance by zoom scaleMmPerPixel', () => {
		const moving: Rect = { id: 'bead', x: 198.5, y: 20, w: 25, h: 30 }
		const resZoomed = computeSmartGuides(moving, fixedRects, { scaleMmPerPixel: 0.1, tolerancePx: 6 })
		expect(resZoomed.deltaX).toBe(0)

		const movingClose: Rect = { id: 'bead', x: 199.6, y: 20, w: 25, h: 30 }
		const resClose = computeSmartGuides(movingClose, fixedRects, { scaleMmPerPixel: 0.1, tolerancePx: 6 })
		expect(resClose.deltaX).toBe(0.4)
	})

	it('bypasses snapping completely when disabled (Alt/Ctrl held)', () => {
		const moving: Rect = { id: 'bead', x: 199.8, y: 20, w: 25, h: 30 }
		const res = computeSmartGuides(moving, fixedRects, { scaleMmPerPixel: 1, tolerancePx: 6, disabled: true })
		expect(res.deltaX).toBe(0)
		expect(res.deltaY).toBe(0)
		expect(res.lines).toEqual([])
		expect(res.gaps).toEqual([])
	})

	it('snaps when the distance is exactly the tolerance', () => {
		// Only the left edge (195 -> 200) is within 5 mm of any line of the target.
		const target: Rect[] = [{ id: 't', x: 200, y: 0, w: 40, h: 80 }]
		const moving: Rect = { id: 'm', x: 195, y: 500, w: 70, h: 10 }
		const res = computeSmartGuides(moving, target, opts)
		expect(res.deltaX).toBe(5)
	})

	it('snaps to a datum centre line and draws it as a centre guide', () => {
		const datum: Rect[] = [{ id: 'datum-center-x', x: 225, y: 0, w: 0, h: 80, guide: 'center' }]
		const moving: Rect = { id: 'mullion', x: 211, y: 0, w: 30, h: 20 }
		const res = computeSmartGuides(moving, datum, opts)

		expect(res.deltaX).toBe(-1)
		expect(res.deltaY).toBe(0)
		expect(res.lines).toHaveLength(1)
		expect(res.lines[0].axis).toBe('x')
		expect(res.lines[0].pos).toBe(225)
		expect(res.lines[0].type).toBe('center')
		// A datum is a line, not a neighbour: it never produces a distance marker.
		expect(res.gaps).toEqual([])
	})

	it('always reports the distance to the nearest neighbours, even when nothing snaps', () => {
		const moving: Rect = { id: 'bead', x: 100, y: 10, w: 20, h: 20 }
		const res = computeSmartGuides(moving, fixedRects, opts)

		expect(res.deltaX).toBe(0)
		expect(res.gaps.map((g) => g.gap).sort((a, b) => a - b)).toEqual([50, 80])
		expect(res.gaps.every((g) => g.axis === 'x' && !g.equal)).toBe(true)
	})

	it('measures vertical distance to an item below', () => {
		const below: Rect[] = [{ id: 'base', x: 0, y: 100, w: 100, h: 20 }]
		const moving: Rect = { id: 'glass', x: 20, y: 50, w: 30, h: 20 }
		const res = computeSmartGuides(moving, below, opts)

		expect(res.gaps).toHaveLength(1)
		expect(res.gaps[0].axis).toBe('y')
		expect(res.gaps[0].gap).toBe(30)
		expect(res.gaps[0].perpPos).toBe(35) // middle of the shared x range 20..50
	})

	it('marks a gap that equals another gap elsewhere and draws the twin too', () => {
		const layout: Rect[] = [
			{ id: 'a', x: 0, y: 0, w: 10, h: 20 },
			{ id: 'b', x: 30, y: 0, w: 10, h: 20 }, // a -> b gap = 20
			{ id: 'c', x: 100, y: 0, w: 10, h: 20 },
		]
		const moving: Rect = { id: 'm', x: 130, y: 0, w: 10, h: 20 } // c -> m gap = 20
		const res = computeSmartGuides(moving, layout, opts)

		expect(res.deltaX).toBe(0)
		expect(res.gaps).toHaveLength(2)
		expect(res.gaps.every((g) => g.equal && g.gap === 20)).toBe(true)
	})

	it('snaps a gap to a known gap elsewhere in the layout', () => {
		const layout: Rect[] = [
			{ id: 'a', x: 0, y: 0, w: 10, h: 20 },
			{ id: 'b', x: 30, y: 0, w: 10, h: 20 },
			{ id: 'c', x: 100, y: 0, w: 10, h: 20 },
		]
		const moving: Rect = { id: 'm', x: 132, y: 0, w: 10, h: 20 } // gap 22, known gap 20
		const res = computeSmartGuides(moving, layout, opts)
		expect(res.deltaX).toBe(-2)
	})

	it('does not apply equal spacing when the item overlaps another in x', () => {
		const moving: Rect = { id: 'sash', x: 206, y: 0, w: 30, h: 80 }
		const res = computeSmartGuides(moving, fixedRects, opts)
		// Snapped by alignment (-1), not by the 4 mm spacing shift to centre between the frames.
		expect(res.deltaX).toBe(-1)
	})

	it('returns nothing when nothing is near', () => {
		const moving: Rect = { id: 'far', x: 100, y: 300, w: 20, h: 20 }
		const res = computeSmartGuides(moving, fixedRects, opts)
		expect(res.deltaX).toBe(0)
		expect(res.deltaY).toBe(0)
		expect(res.lines).toEqual([])
		expect(res.gaps).toEqual([])
	})

	it('measureGuides reports without snapping', () => {
		// Left edge sits exactly on the mullion's left edge; nothing is moved.
		const moving: Rect = { id: 'bead', x: 200, y: 20, w: 25, h: 30 }
		const res = measureGuides(moving, fixedRects)
		expect(res.deltaX).toBe(0)
		expect(res.deltaY).toBe(0)
		expect(res.lines.some((l) => l.axis === 'x' && l.pos === 200)).toBe(true)
	})
})
