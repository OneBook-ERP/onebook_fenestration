import { describe, expect, it } from 'vitest'
import { louverSectionRings, LOUVER_ANGLE, LOUVER_THICKNESS } from './louverGeometry'
import { compactPieceSpans } from './sectionPuzzle'
import type { SectionPiece } from '@/api'

describe('louver blade width', () => {
	it('projects the actual width through the tilt independently of blade count', () => {
		for (const blades of [5, 9]) {
			const [ring] = louverSectionRings('h', 24, 600, 1152, blades, 80)
			const depth = Math.max(...ring.map(p => p.y)) - Math.min(...ring.map(p => p.y))
			expect(depth).toBeCloseTo(80 * Math.sin(LOUVER_ANGLE) + LOUVER_THICKNESS * Math.cos(LOUVER_ANGLE))
			expect(depth).toBeLessThan(80)
		}
	})
	it('keeps blade width and angle in Profile Focus while compressing spacing', () => {
		const piece: SectionPiece = { kind: 'louver', role: 'louver', code: 'Louver', panel: 'F1', start: 24, end: 1176, opening_height: 1152, blades: 9, blade_width: 80, mirrored: false, thickness: 0 }
		const { starts, ends } = compactPieceSpans([piece], true, 'v')
		const rings = louverSectionRings('v', starts[0], ends[0], 1152, 9, 80)
		const dx = rings[0][1].x - rings[0][0].x, dy = rings[0][1].y - rings[0][0].y
		expect(Math.hypot(dx, dy)).toBeCloseTo(80)
		expect(Math.atan2(-dy, dx)).toBeCloseTo(LOUVER_ANGLE)
		expect(Math.max(...rings[0].map(p => p.x))).toBeLessThan(Math.min(...rings[1].map(p => p.x)))
		expect(ends[0] - starts[0]).toBeLessThan(1152)
	})
})
