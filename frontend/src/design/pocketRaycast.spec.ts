import { describe, expect, it } from 'vitest'
import type { SectionOutline, SectionPiece } from '@/api'
import { fitGlassInDomain } from './glassDomain'
import { PocketRaycaster } from './pocketRaycast'
import { buildPlacedShape, compactPieceSpans } from './sectionPuzzle'

/**
 * C-channel sash profile (64 mm wide × 48 mm deep) with:
 * - Closed hollow chamber on the left [0..36, 0..48]
 * - Open glazing C-pocket on the right [36..64, 10..38] -> true pocket BW = 28 mm
 * - Recessed 2 mm T-slot gasket notch at x=[56..60], y=[8..10] & y=[38..40] (total 32 mm if unfiltered)
 */
const SASH_SVG = [
	// Outer perimeter with open C-pocket + recessed T-slot notches
	'M 0 0 L 64 0 L 64 10 L 60 10 L 60 8 L 56 8 L 56 10 L 36 10',
	'L 36 38 L 56 38 L 56 40 L 60 40 L 60 38 L 64 38 L 64 48 L 0 48 Z',
	// Hollow internal box chamber [3..33, 3..45]
	'M 3 3 L 33 3 L 33 45 L 3 45 Z',
].join(' ')

const SASH_OUTLINE: SectionOutline = { svg: SASH_SVG, width: 64, depth: 48 }

/**
 * U-channel glazing bead (HSL3410) drawn sideways by default (28 mm wide × 20 mm deep, opening downward)
 * so `seatBeadAtDomainCorner` MUST rotate it 90°/270° to seat into the sash pocket with 18 mm inner opening!
 * Local sideways geometry: outer width 28 (becomes height 28 when rotated!), inner gap [5..23] = 18 mm!
 */
const U_BEAD_SIDEWAYS_SVG =
	'M 0 0 L 28 0 L 28 20 L 23 20 L 23 3 L 5 3 L 5 20 L 0 20 Z'
const U_BEAD_OUTLINE: SectionOutline = { svg: U_BEAD_SIDEWAYS_SVG, width: 28, depth: 20 }

function makePiece(overrides: Partial<SectionPiece> & Pick<SectionPiece, 'kind' | 'code' | 'role'>): SectionPiece {
	return {
		panel: 'S1',
		start: 0,
		end: 64,
		mirrored: false,
		thickness: 0,
		...overrides,
	}
}

describe('PocketRaycaster (7-step pocket, bead & gasket workflow)', () => {
	const zeroT = { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false }
	const lowSashPiece = makePiece({ kind: 'profile', code: 'CS4804', role: 'sash', start: 0, end: 64, mirrored: false })
	const highSashPiece = makePiece({ kind: 'profile', code: 'CS4804', role: 'sash', start: 156, end: 220, mirrored: true })

	const lowSash = buildPlacedShape(0, lowSashPiece, 0, 64, SASH_OUTLINE, zeroT)
	const highSash = buildPlacedShape(1, highSashPiece, 156, 220, SASH_OUTLINE, zeroT)

	it('detects exact 28 mm pocket domain via 4-way raycast, ignores T-slot grooves, and rejects closed chambers', () => {
		const raycaster = new PocketRaycaster([lowSash, highSash])

		// Clicking inside the closed hollow tube chamber [3..33] must be rejected
		expect(raycaster.probeAt({ x: 18, y: 24 })).toBeNull()

		// Clicking right under the T-slot notch (x = 58, y = 24) still reports true 28 mm clamping lip (not 32 mm!)
		const probe = raycaster.probeAt({ x: 58, y: 24 })
		expect(probe).not.toBeNull()
		expect(probe!.pocketMinY).toBe(10)
		expect(probe!.pocketMaxY).toBe(38)
		expect(probe!.pocketWidthMm).toBe(28)
		expect(probe!.leftWallX).toBe(36)
		expect(probe!.rightWallX).toBe(184) // 220 - 36
	})

	it('auto-orients sideways U-beads into Left & Right pocket corners, narrows domain 28 -> 18 mm, and places gaskets', () => {
		const hostRaycaster = new PocketRaycaster([lowSash, highSash])
		const probe = hostRaycaster.probeAt({ x: 50, y: 24 })!
		const glassBaseStart = 50
		const glassBaseEnd = 170
		const domain = PocketRaycaster.toGlassDomain(probe, glassBaseStart, glassBaseEnd, 3)

		// Step 4: Seat sideways HSL3410 beads into Left (low) and Right (high) pocket corners
		const lowBeadPiece = makePiece({ kind: 'profile', code: 'HSL3410', role: 'glass_adaptor', start: 47, end: 75, mirrored: false })
		const highBeadPiece = makePiece({ kind: 'profile', code: 'HSL3410', role: 'glass_adaptor', start: 145, end: 173, mirrored: true })

		const lowBeadT = hostRaycaster.seatBeadAtDomainCorner(
			lowBeadPiece,
			2,
			47,
			75,
			glassBaseStart,
			glassBaseEnd,
			U_BEAD_OUTLINE,
			domain,
		)
		const highBeadT = hostRaycaster.seatBeadAtDomainCorner(
			highBeadPiece,
			3,
			145,
			173,
			glassBaseStart,
			glassBaseEnd,
			U_BEAD_OUTLINE,
			domain,
		)
		expect(lowBeadT).not.toBeNull()
		expect(highBeadT).not.toBeNull()

		const lowBeadShape = buildPlacedShape(2, lowBeadPiece, 47, 75, U_BEAD_OUTLINE, lowBeadT!)
		const highBeadShape = buildPlacedShape(3, highBeadPiece, 145, 173, U_BEAD_OUTLINE, highBeadT!)

		// Rotated to fit 28 mm pocket height cleanly and flush against back walls (36 and 184)
		expect(Math.round(lowBeadShape.bbox.height)).toBe(28)
		expect(Math.round(lowBeadShape.bbox.minX)).toBe(36)
		expect(Math.round(highBeadShape.bbox.height)).toBe(28)
		expect(Math.round(highBeadShape.bbox.maxX)).toBe(184)

		// Step 5: Dynamic re-raycast shrinks active domain from 28 mm -> 18 mm!
		const fullRaycaster = new PocketRaycaster([lowSash, highSash, lowBeadShape, highBeadShape])
		const dynWithBead = fullRaycaster.recalculateDynamicDomain(domain, glassBaseStart, glassBaseEnd)
		expect(dynWithBead.pocketBwMm).toBe(28)
		expect(dynWithBead.effectiveBwMm).toBe(18)
		expect(dynWithBead.narrowedByBead).toBe(true)
		expect(dynWithBead.effectiveMinY).toBe(15)
		expect(dynWithBead.effectiveMaxY).toBe(33)

		// Steps 6 & 7: 12 mm glass centers inside [15..33] -> [18..30], leaving 3 mm Outer & 3 mm Inner gaskets!
		const glassFit = fitGlassInDomain(glassBaseStart, glassBaseEnd, 12, dynWithBead.domain)
		expect(glassFit.y).toBe(18)
		expect(glassFit.depth).toBe(12)

		const gaskets = PocketRaycaster.computeGasketPlacements(dynWithBead, glassFit, {
			outer_code: 'G23',
			outer_name: '3mm Gasket',
			outer_mm: 3,
			inner_code: 'G23',
			inner_name: '3mm Gasket',
			inner_mm: 3,
			bead_side: 'inside',
			no_bead: false,
		})
		expect(gaskets).toHaveLength(4)
		const lowOuter = gaskets.find((g) => g.id === 'low-outer')!
		const lowInner = gaskets.find((g) => g.id === 'low-inner')!
		const highOuter = gaskets.find((g) => g.id === 'high-outer')!
		expect(lowOuter.y).toBe(15)
		expect(lowOuter.h).toBe(3)
		expect(lowInner.y).toBe(30)
		expect(lowInner.h).toBe(3)
		// Every gasket MUST be centered directly on its vertical ray anchor X!
		expect(lowOuter.x + lowOuter.w / 2).toBeCloseTo(dynWithBead.lowAnchorX, 1)
		expect(lowInner.x + lowInner.w / 2).toBeCloseTo(dynWithBead.lowAnchorX, 1)
		expect(highOuter.x + highOuter.w / 2).toBeCloseTo(dynWithBead.highAnchorX, 1)

		// Asymmetric gaskets (4 mm outer, 3 mm inner in 12 mm bead with 5 mm glass) seat flush on both faces!
		const asymDomain = { ...dynWithBead.domain, minY: 18, maxY: 30 }
		const asymDyn = { ...dynWithBead, effectiveMinY: 18, effectiveMaxY: 30, effectiveBwMm: 12, domain: asymDomain }
		const asymFit = fitGlassInDomain(glassBaseStart, glassBaseEnd, 5, asymDomain, { outerMm: 4, innerMm: 3 })
		expect(asymFit.y).toBe(22) // 18 + 4 mm outer
		const asymGaskets = PocketRaycaster.computeGasketPlacements(asymDyn, asymFit, {
			outer_code: 'G24',
			outer_name: '4mm Gasket',
			outer_mm: 4,
			inner_code: 'G23',
			inner_name: '3mm Gasket',
			inner_mm: 3,
			bead_side: 'inside',
			no_bead: false,
		})
		const aOut = asymGaskets.find((g) => g.id === 'low-outer')!
		const aIn = asymGaskets.find((g) => g.id === 'low-inner')!
		expect(aOut.y).toBe(18)
		expect(aOut.h).toBe(4)
		expect(aIn.y).toBe(27)
		expect(aIn.h).toBe(3)

		// Switching to 24 mm DGU (No Bead): domain automatically expands back to 28 mm!
		const dynNoBead = hostRaycaster.recalculateDynamicDomain(domain, glassBaseStart, glassBaseEnd)
		expect(dynNoBead.effectiveBwMm).toBe(28)
		expect(dynNoBead.narrowedByBead).toBe(false)
	})

	it('prevents wide 92 mm door shutters (CS4804) from overlapping in compact glass mode', () => {
		const pieces: SectionPiece[] = [
			makePiece({ kind: 'profile', code: 'CS4805', role: 'frame', start: 0, end: 52, mirrored: false }),
			makePiece({ kind: 'profile', code: 'CS4804', role: 'sash', start: 35, end: 127, mirrored: false }),
			makePiece({ kind: 'glass', code: '10CTG', role: 'glass', start: 85, end: 915, thickness: 10 }),
			makePiece({ kind: 'profile', code: 'CS4804', role: 'sash', start: 873, end: 965, mirrored: true }),
			makePiece({ kind: 'profile', code: 'CS4805', role: 'frame', start: 948, end: 1000, mirrored: true }),
		]
		const { starts, ends } = compactPieceSpans(pieces, true, 'h')
		// Left CS4804 ends at ends[1]; right CS4804 starts at starts[3] -> must leave >= 60 mm clear daylight gap!
		expect(starts[3] - ends[1]).toBeGreaterThanOrEqual(60)
	})

	it('stops vertical rays cleanly on clip-in frame beads (e.g. CS4807) and other profile roles', () => {
		// L-rebate fixed frame (open top, bottom rebate lip at y=[38..48], back wall at x=12)
		const frameSvg = 'M 0 0 L 12 0 L 12 38 L 42 38 L 42 48 L 0 48 Z'
		const frameOut: SectionOutline = { svg: frameSvg, width: 42, depth: 48 }
		// Clip-in bead sitting at y=[14..22] extending x=[12..38]
		const beadSvg = 'M 0 0 L 26 0 L 26 8 L 0 8 Z'
		const beadOut: SectionOutline = { svg: beadSvg, width: 26, depth: 8 }

		const lowFrame = buildPlacedShape(0, makePiece({ kind: 'profile', code: 'CS4801', role: 'frame', start: 0, end: 42 }), 0, 42, frameOut, zeroT)
		const lowBead = buildPlacedShape(1, makePiece({ kind: 'profile', code: 'CS4807', role: 'bead', start: 12, end: 38 }), 12, 38, beadOut, { ...zeroT, offsetDepth: 14 })
		const highBead = buildPlacedShape(2, makePiece({ kind: 'profile', code: 'CS4807', role: 'bead', start: 132, end: 158, mirrored: true }), 132, 158, beadOut, { ...zeroT, offsetDepth: 14 })
		const highFrame = buildPlacedShape(3, makePiece({ kind: 'profile', code: 'CS4801', role: 'frame', start: 128, end: 170, mirrored: true }), 128, 170, frameOut, zeroT)

		const raycaster = new PocketRaycaster([lowFrame, lowBead, highBead, highFrame])
		// Cursor between green bead (y=22) and bottom frame lip (y=38) MUST stop on bead y=22, NOT pass through to y=0!
		const probe = raycaster.probeAt({ x: 25, y: 30 })
		expect(probe).not.toBeNull()
		expect(probe!.pocketMinY).toBe(22)
		expect(probe!.pocketMaxY).toBe(38)
		expect(probe!.pocketWidthMm).toBe(16)
		expect(probe!.hitBeadWall).toBe(true)
	})

	it('seats tall snap-ear sash U-beads (like HSL3409, 31 mm height in 28 mm pocket) flush at pocket corners', () => {
		// HSL3409-like U-bead: 18 mm wide × 31 mm tall (outer snap ears at top/bottom), 12 mm inner channel [9.5..21.5]
		const hsl3409Svg =
			'M 0 3 L 15 3 L 15 0 L 18 0 L 18 9.5 L 3 9.5 L 3 21.5 L 18 21.5 L 18 31 L 15 31 L 15 28 L 0 28 Z'
		const hslOut: SectionOutline = { svg: hsl3409Svg, width: 18, depth: 31 }
		const hostRaycaster = new PocketRaycaster([lowSash, highSash])
		const probe = hostRaycaster.probeAt({ x: 50, y: 24 })!
		const domain = PocketRaycaster.toGlassDomain(probe, 50, 170, 3)

		const lowBeadPiece = makePiece({ kind: 'profile', code: 'HSL3409', role: 'glass_adaptor', start: 0, end: 18, mirrored: false })
		const seated = hostRaycaster.seatBeadAtDomainCorner(lowBeadPiece, 2, 0, 18, 50, 170, hslOut, domain)
		expect(seated).not.toBeNull()
		const placed = buildPlacedShape(2, lowBeadPiece, 0, 18, hslOut, seated!)
		// Must land flush against left pocket back wall (x = 36) and vertically centered on pocket center (y = 24)!
		expect(Math.round(placed.bbox.minX)).toBe(36)
		expect(Math.round((placed.bbox.minY + placed.bbox.maxY) / 2)).toBe(24)

		// Dynamic re-raycast shrinks active domain from 28 mm down to HSL3409's 12 mm inner channel!
		const dyn = new PocketRaycaster([lowSash, highSash, placed]).recalculateDynamicDomain(domain, 50, 170)
		expect(dyn.effectiveBwMm).toBe(12)
		expect(dyn.narrowedByBead).toBe(true)
	})

	it('keeps both left and mirrored right U-beads upright (never rotated 90°) when snap ears engage host pocket lips', () => {
		// Pre-rotated CAD-vertical U-bead (16.8 mm wide × 28.9 mm tall) with snap ears slightly overlapping [10..38] pocket lips
		const uprightHslSvg =
			'M 0 0.5 L 14 0.5 L 14 0 L 16.8 0 L 16.8 8.9 L 3 8.9 L 3 20.9 L 16.8 20.9 L 16.8 28.9 L 14 28.9 L 14 28.4 L 0 28.4 Z'
		const uprightOut: SectionOutline = { svg: uprightHslSvg, width: 16.8, depth: 28.9 }
		// Right sash pocket has narrow retention lips slightly inside [10..38] so snap ears engage
		const hostRaycaster = new PocketRaycaster([lowSash, highSash])
		const probe = hostRaycaster.probeAt({ x: 50, y: 24 })!
		const domain = PocketRaycaster.toGlassDomain(probe, 50, 170, 3)

		const leftBead = makePiece({ kind: 'profile', code: 'HSL3409', role: 'glass_adaptor', start: 0, end: 16.8, mirrored: false })
		const rightBead = makePiece({ kind: 'profile', code: 'HSL3409', role: 'glass_adaptor', start: 153.2, end: 170, mirrored: true })

		const leftT = hostRaycaster.seatBeadAtDomainCorner(leftBead, 2, 0, 16.8, 50, 170, uprightOut, domain)!
		const rightT = hostRaycaster.seatBeadAtDomainCorner(rightBead, 3, 153.2, 170, 50, 170, uprightOut, domain)!

		const leftPlaced = buildPlacedShape(2, leftBead, 0, 16.8, uprightOut, leftT)
		const rightPlaced = buildPlacedShape(3, rightBead, 153.2, 170, uprightOut, rightT)

		// Both must stay upright (~16.8 × ~28.9), NOT rotated 90° sideways (~28.9 × 16.8)
		expect(leftPlaced.bbox.height).toBeGreaterThan(25)
		expect(leftPlaced.bbox.width).toBeCloseTo(16.8, 1)
		expect(rightPlaced.bbox.height).toBeGreaterThan(25)
		expect(rightPlaced.bbox.width).toBeCloseTo(16.8, 1)
		expect(Math.round(rightPlaced.bbox.maxX)).toBe(184)
	})

	it('expands fixed-frame dynamic domain when switching from 6mm bead (CS4807) to thinner 24mm DGU bead (CS4809)', () => {
		// Fixed frame: vertical back wall at x=24, bottom glazing lip at y=[36..40]
		const frameSvg = 'M 0 0 L 24 0 L 24 36 L 42 36 L 42 40 L 0 40 Z'
		const frameOut: SectionOutline = { svg: frameSvg, width: 42, depth: 40 }
		const lowFrame = buildPlacedShape(0, makePiece({ kind: 'profile', code: 'E104156', role: 'frame', start: 0, end: 42 }), 0, 42, frameOut, zeroT)
		const highFrame = buildPlacedShape(3, makePiece({ kind: 'profile', code: 'E104156', role: 'frame', start: 138, end: 180, mirrored: true }), 138, 180, frameOut, zeroT)

		// Domain originally raycast with a 6 mm bead (glazing face at y = 24 -> 12 mm channel [24..36])
		const origDomain = {
			configured: true,
			minY: 24,
			maxY: 36,
			insetLow: -3,
			insetHigh: -3,
			align: 'center' as const,
			raycast: {
				enabled: true,
				pocketMinY: 24,
				pocketMaxY: 36,
				pocketInsetLow: -6,
				pocketInsetHigh: -6,
				probeOffsetFromLow: 15,
			},
		}

		// Swap in a 24 mm DGU L-bead (snap leg on left y=[0..20], glazing face on right y=[0..5]) at the same clip-in seat
		const dguBeadSvg = 'M 0 0 L 24 0 L 24 5 L 4 5 L 4 20 L 0 20 Z'
		const dguOut: SectionOutline = { svg: dguBeadSvg, width: 24, depth: 20 }
		const lowBead = buildPlacedShape(1, makePiece({ kind: 'profile', code: 'CS4809', role: 'bead', start: 20, end: 44 }), 20, 44, dguOut, zeroT)
		const highBead = buildPlacedShape(2, makePiece({ kind: 'profile', code: 'CS4809', role: 'bead', start: 136, end: 160, mirrored: true }), 136, 160, dguOut, zeroT)

		const dyn = new PocketRaycaster([lowFrame, lowBead, highBead, highFrame]).recalculateDynamicDomain(origDomain, 30, 150)
		// Dynamic domain must EXPAND from 12 mm [24..36] to 31 mm [5..36] so 24 mm DGU + gaskets fit cleanly!
		expect(dyn.effectiveMinY).toBe(5)
		expect(dyn.effectiveMaxY).toBe(36)
		expect(dyn.effectiveBwMm).toBe(31)
	})

	it('keeps mirrored bead polygons, raycast hits, and gaskets aligned even when originU=0 is stored', () => {
		const frameSvg = 'M 0 0 L 24 0 L 24 36 L 42 36 L 42 40 L 0 40 Z'
		const frameOut: SectionOutline = { svg: frameSvg, width: 42, depth: 40 }
		const beadSvg = 'M 0 0 L 22 0 L 22 24 L 18 24 L 18 14 L 0 14 Z'
		const beadOut: SectionOutline = { svg: beadSvg, width: 22, depth: 24 }

		const lowFrame = buildPlacedShape(0, makePiece({ kind: 'profile', code: 'E104156', role: 'frame', start: 0, end: 42 }), 0, 42, frameOut, zeroT)
		const highFrame = buildPlacedShape(3, makePiece({ kind: 'profile', code: 'E104159', role: 'mullion', start: 126, end: 168, mirrored: true }), 126, 168, frameOut, zeroT)
		const lowBead = buildPlacedShape(
			1,
			makePiece({ kind: 'profile', code: 'E104161', role: 'bead', start: 20, end: 42 }),
			20,
			42,
			beadOut,
			{ ...zeroT, originU: 0, originDepth: 0 },
		)
		const highBead = buildPlacedShape(
			2,
			makePiece({ kind: 'profile', code: 'E104161', role: 'bead', start: 126, end: 148, mirrored: true }),
			126,
			148,
			beadOut,
			{ ...zeroT, originU: 0, originDepth: 0 },
		)

		// Mirrored bead must stay at [126..148], NOT jump -22 mm left to [104..126]
		expect(highBead.bbox.minX).toBeCloseTo(126, 1)
		expect(highBead.bbox.maxX).toBeCloseTo(148, 1)

		const ray = new PocketRaycaster([lowFrame, lowBead, highBead, highFrame])
		// Ray aimed under the mirrored bead glazing lip (x=127.5) MUST stop on y=24, never pass through to y=0
		const probe = ray.probeAt({ x: 127.5, y: 29 })
		expect(probe).not.toBeNull()
		expect(probe!.pocketMinY).toBe(24)
		expect(probe!.pocketMaxY).toBe(36)
		expect(probe!.hitBeadWall).toBe(true)

		// Dynamic highAnchorX must sit directly under the mirrored bead's glazing lip (~127.2), never floating in mid-air
		const dom = PocketRaycaster.toGlassDomain(probe!, 30, 138, 3)
		const dyn = ray.recalculateDynamicDomain(dom, 30, 138)
		expect(dyn.highAnchorX).toBeGreaterThanOrEqual(126.5)
		expect(dyn.highAnchorX).toBeLessThanOrEqual(129.5)
	})
})

