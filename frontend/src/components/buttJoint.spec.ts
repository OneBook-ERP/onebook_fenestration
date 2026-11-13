import { describe, expect, it } from 'vitest'
import { seatAtDepth, splitAtSeatDepths, type ButtSeat } from './buttJoint'

// A 60 mm mullion whose room-side face is narrower than its rear flange.
const seat: ButtSeat = {
	contour: [
		{ x: 0, y: 0 }, { x: 20, y: 0 }, { x: 20, y: 20 },
		{ x: 40, y: 20 }, { x: 40, y: 40 }, { x: 20, y: 40 },
		{ x: 20, y: 60 }, { x: 0, y: 60 },
	],
	depthOffset: 0, origin: 630, direction: -1,
}

describe('bar butt joints', () => {
	it('fits the transom to both flange and recessed face instead of stopping at a fixed deduction', () => {
		expect(seatAtDepth(seat, 10, true)).toBe(630)
		expect(seatAtDepth(seat, 30, true)).toBe(610)
		expect(seatAtDepth(seat, 10, false)).toBe(570)
		expect(seatAtDepth(seat, 30, false)).toBe(590)
	})
	it('respects depth and plan offsets and leaves unsupported depths alone', () => {
		const shifted = { ...seat, depthOffset: 5, origin: 637 }
		expect(seatAtDepth(shifted, 35, true)).toBe(617)
		expect(seatAtDepth(shifted, 50, true)).toBeNull()
	})
	it('adds vertices around rebate steps so the joining walls follow the step', () => {
		const loops = [[{ x: 0, y: 0 }, { x: 40, y: 0 }, { x: 40, y: 60 }, { x: 0, y: 60 }]]
		const [split] = splitAtSeatDepths(loops, 0, [seat])
		expect(split.some((p) => p.x === 20 && p.y === 0)).toBe(true)
		expect(split.some((p) => p.x > 20 && p.x < 20.001 && p.y === 60)).toBe(true)
		expect(loops[0]).toHaveLength(4)
	})
})
