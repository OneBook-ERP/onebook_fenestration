import { describe, expect, it } from 'vitest'
import { buildPlacedShape, canonicalTransformForPiece, extractWallFaces, magneticAutoJoin, profileContactGuides } from './sectionPuzzle'
import type { SectionPiece } from '@/api'
const transform = { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false }
const outline = { svg: 'M0 0 L10 0 L10 10 L0 10 Z', width: 10, depth: 10 }
const piece: SectionPiece = { kind: 'profile', role: 'sash', code: 'S', panel: 'F1', start: 0, end: 10, mirrored: false, thickness: 0 }
const shape = (index: number, x: number, mirrored = false) => buildPlacedShape(index, { ...piece, mirrored }, x, x + 10, outline, transform)

describe('section mating guides', () => {
	it('moves either mirrored or unmirrored profiles towards the same world-space wall', () => {
		for (const mirrored of [false, true]) {
			const moving = shape(0, 0, mirrored)
			const target = shape(1, 11)
			const snapped = magneticAutoJoin(moving, transform, moving.piece, [target], 1.5)!
			expect(snapped.offsetAlong).toBe(1)
			const final = buildPlacedShape(0, moving.piece, 0, 10, outline, snapped)
			expect(final.bbox.maxX).toBe(target.bbox.minX)
			expect(profileContactGuides(final, [target])).toContainEqual(expect.objectContaining({ axis: 'x', pos: 11 }))
		}
	})
	it('respects the screen-derived tolerance at high zoom', () => {
		const moving = shape(0, 0); const target = shape(1, 11)
		const snapped = magneticAutoJoin(moving, transform, piece, [target], 0.3)
		expect(snapped?.offsetAlong ?? 0).toBe(0)
	})
	it('does not invent vertical or horizontal mating faces for a diamond', () => {
		const diamond = buildPlacedShape(0, piece, 0, 10, { ...outline, svg: 'M5 0 L10 5 L5 10 L0 5 Z' }, transform)
		expect(extractWallFaces(diamond)).toEqual({ vFaces: [], hFaces: [] })
	})
	it('converts shared offsets to mirrored world offsets and back without changing depth or rotation', () => {
		const mirrored = { ...piece, mirrored: true }
		const common = { ...transform, offsetAlong: 3, offsetDepth: 12, rotation: 90 }
		const right = canonicalTransformForPiece(mirrored, common)
		expect(right).toEqual({ ...common, offsetAlong: -3 })
		expect(canonicalTransformForPiece(mirrored, right)).toEqual(common)
	})
})
