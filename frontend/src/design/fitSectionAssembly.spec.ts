import { describe, expect, it } from 'vitest'
import outlines from './__fixtures__/casementSections.json'
import { fitSectionAssembly } from './fitSectionAssembly'
import { defaultTransformForPiece } from './sectionPuzzle'
import type { SeatingEntry } from './sectionSeating'

function casement(): SeatingEntry[] {
	const profile = (role: 'frame' | 'sash', start: number, mirrored = false): SeatingEntry => {
		const outline = outlines[role]
		const piece = { kind: 'profile' as const, role, code: role, panel: role === 'sash' ? 'F1-S1' : 'F1', path: 'F1', start, end: start + outline.width, mirrored, thickness: 0 }
		return { piece, outline, start, end: piece.end, transform: defaultTransformForPiece(piece, outline), needsSeat: role === 'sash' }
	}
	const glass = { kind: 'glass' as const, role: 'glass', code: '6CTG', panel: 'F1-S1', path: 'F1', start: 80, end: 320, mirrored: false, thickness: 6 }
	return [profile('frame', 0), profile('sash', 18),
		{ piece: glass, outline: null, start: 80, end: 320, transform: defaultTransformForPiece(glass, null), needsSeat: true },
		profile('sash', 400 - 18 - outlines.sash.width, true), profile('frame', 400 - outlines.frame.width, true)]
}

describe('complete casement assembly fitting', () => {
	it('keeps both sash edges at one depth, mirrors offsets, and keeps glass centered', () => {
		const fitted = fitSectionAssembly(casement())
		expect(fitted[1]).not.toBeNull()
		expect(fitted[3]!.offsetDepth).toBe(fitted[1]!.offsetDepth)
		expect(fitted[3]!.offsetAlong).toBe(-fitted[1]!.offsetAlong)
		expect(fitted[2]!.offsetAlong).toBe(0)
	}, 10000)
	it('produces the same assembly when the cut pieces arrive in reverse order', () => {
		const entries = casement()
		const forward = fitSectionAssembly(entries)
		const reverse = fitSectionAssembly([...entries].reverse()).reverse()
		expect(reverse).toEqual(forward)
	}, 10000)
	it('respects an existing sash placement and uses it for the missing partner', () => {
		const entries = casement()
		entries[3].needsSeat = false
		entries[3].transform = { offsetAlong: -3, offsetDepth: 17, rotation: 0, flipX: false, flipY: false }
		entries[2].needsSeat = false
		const fitted = fitSectionAssembly(entries)
		expect(fitted[3]).toBeNull()
		expect(fitted[1]).toMatchObject({ offsetAlong: 3, offsetDepth: 17 })
		expect(fitted[2]).toBeNull()
	})
})
