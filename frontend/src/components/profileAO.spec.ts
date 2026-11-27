import { describe, expect, it } from 'vitest'
import { createSectionAO, type Pt } from './profileAO'

/** 100 x 50 block with an 8 mm wide, 30 mm deep slot cut into the top (y = 50). */
const SLOTTED_BLOCK: Pt[] = [
	{ x: 0, y: 0 },
	{ x: 100, y: 0 },
	{ x: 100, y: 50 },
	{ x: 54, y: 50 },
	{ x: 54, y: 20 },
	{ x: 46, y: 20 },
	{ x: 46, y: 50 },
	{ x: 0, y: 50 },
]

describe('createSectionAO', () => {
	const ao = createSectionAO([SLOTTED_BLOCK])

	it('leaves open outer faces fully bright', () => {
		expect(ao(10, 50, 0, 1)).toBeGreaterThan(0.97) // top face
		expect(ao(50, 0, 0, -1)).toBeGreaterThan(0.97) // underside
		expect(ao(100, 25, 1, 0)).toBeGreaterThan(0.97) // end face
	})

	it('darkens the bottom of a narrow slot', () => {
		const bottom = ao(50, 20, 0, 1)
		expect(bottom).toBeLessThan(0.75)
		expect(ao(10, 50, 0, 1) - bottom).toBeGreaterThan(0.25)
	})

	it('darkens slot walls less than the slot floor, more than open faces', () => {
		const wall = ao(46, 35, 1, 0) // left wall of the slot, facing into it
		const floor = ao(50, 20, 0, 1)
		expect(wall).toBeLessThan(0.97)
		expect(wall).toBeGreaterThan(floor)
	})

	it('is darker deeper in the slot', () => {
		expect(ao(46, 22, 1, 0)).toBeLessThan(ao(46, 48, 1, 0))
	})

	it('treats an inside corner as partly occluded', () => {
		const L: Pt[] = [
			{ x: 0, y: 0 },
			{ x: 60, y: 0 },
			{ x: 60, y: 20 },
			{ x: 20, y: 20 },
			{ x: 20, y: 60 },
			{ x: 0, y: 60 },
		]
		const corner = createSectionAO([L])(20.5, 20.5, 0.7071, 0.7071)
		expect(corner).toBeLessThan(0.9)
		expect(corner).toBeGreaterThan(0.3)
	})

	it('darkens the inside of a hollow chamber', () => {
		const outer: Pt[] = [
			{ x: 0, y: 0 },
			{ x: 40, y: 0 },
			{ x: 40, y: 40 },
			{ x: 0, y: 40 },
		]
		const hole: Pt[] = [
			{ x: 10, y: 10 },
			{ x: 10, y: 30 },
			{ x: 30, y: 30 },
			{ x: 30, y: 10 },
		]
		const chamber = createSectionAO([outer, hole])
		// Inside the hole the normals point into the air of the chamber.
		const corner = chamber(10.2, 10.2, 0.7071, 0.7071) // chamber corner: two walls close by
		const midWall = chamber(10, 20, 1, 0) // middle of a wall: opposite wall is beyond maxDist
		// A 90 degree inside corner blocks ~29 % of a cosine-weighted fan: 1 - 0.8 * 0.29 ~= 0.77.
		expect(corner).toBeLessThan(0.85)
		expect(corner).toBeGreaterThan(0.6)
		expect(midWall).toBeGreaterThan(corner)
		expect(chamber(0, 20, -1, 0)).toBeGreaterThan(0.97) // outer face stays bright
	})

	it('returns 1 for a degenerate normal or an empty section', () => {
		expect(ao(10, 50, 0, 0)).toBe(1)
		expect(createSectionAO([])(0, 0, 0, 1)).toBe(1)
	})

	it('respects strength and never goes below 1 - strength', () => {
		const strong = createSectionAO([SLOTTED_BLOCK], { strength: 1, maxDist: 30 })
		const weak = createSectionAO([SLOTTED_BLOCK], { strength: 0.2 })
		expect(weak(50, 20, 0, 1)).toBeGreaterThan(0.8)
		expect(strong(50, 20, 0, 1)).toBeGreaterThanOrEqual(0)
	})

	it('returns the same value for the same point (memoised)', () => {
		expect(ao(50, 20, 0, 1)).toBe(ao(50, 20, 0, 1))
	})
})

