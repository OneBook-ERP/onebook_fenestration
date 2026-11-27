import type { SectionOutline, SectionPiece } from '@/api'
import { roundTenth, type PaneGasketsMeta, type ResolvedGlassBounds } from '@/design/glassDomain'
import { buildPlacedShape, type PlacedShape, type Point } from '@/design/sectionPuzzle'
import type { SectionPieceTransform } from '@/design/types'
import type { SectionGlassDomain } from '@/studio/api'

export interface RayHit {
	point: Point
	dist: number
	shapeIndex: number
	role: string
	code: string
}

export interface PocketProbeResult {
	origin: Point
	topHit: Point
	bottomHit: Point
	leftHit: RayHit
	rightHit: RayHit
	pocketMinY: number
	pocketMaxY: number
	pocketWidthMm: number
	leftWallX: number
	rightWallX: number
	probeOffsetFromLow: number
	hitBeadWall: boolean
}

export interface DynamicDomainState {
	domain: SectionGlassDomain
	pocketMinY: number
	pocketMaxY: number
	pocketBwMm: number
	effectiveMinY: number
	effectiveMaxY: number
	effectiveBwMm: number
	narrowedByBead: boolean
	leftWallX: number
	rightWallX: number
	lowAnchorX: number
	highAnchorX: number
}

export interface GasketPlacement {
	id: string
	side: 'low' | 'high'
	face: 'outer' | 'inner'
	code: string
	nominalMm: number
	anchorX: number
	x: number
	y: number
	w: number
	h: number
}

interface Seg {
	a: Point
	b: Point
	shapeIndex: number
	role: string
	code: string
}

const BEAD_ROLES = new Set(['bead', 'glass_adaptor'])
const DEFAULT_GLASS_CLEARANCE_MM = 3.0

/**
 * Geometry raycaster for 1-click glazing pocket detection, domain-corner bead seating,
 * live vertical domain recalculation when beads enter, and gasket anchor placement.
 */
export class PocketRaycaster {
	readonly hostShapes: PlacedShape[]
	readonly beadShapes: PlacedShape[]
	readonly allProfileShapes: PlacedShape[]
	private readonly hostSegs: Seg[]
	private readonly allSegs: Seg[]

	constructor(shapes: PlacedShape[]) {
		const profiles = shapes.filter((s) => s.piece.kind === 'profile' && s.piece.role !== 'gasket')
		this.allProfileShapes = profiles
		this.beadShapes = profiles.filter((s) => BEAD_ROLES.has(s.piece.role))
		this.hostShapes = profiles.filter((s) => !BEAD_ROLES.has(s.piece.role))
		this.hostSegs = extractSegments(this.hostShapes)
		this.allSegs = extractSegments(this.allProfileShapes)
	}

	/**
	 * Cast 4 rays from `origin` against ALL rendered profiles (frame, sash, mullion, bead, interlock, etc.)
	 * so rays stop cleanly on beads and every profile wall without passing through.
	 */
	probeAt(origin: Point): PocketProbeResult | null {
		if (!this.allProfileShapes.length) return null
		if (this.allProfileShapes.some((s) => pointInRings(origin, s.rings))) return null

		const leftHit = castHorizontalRay(origin, -1, this.allSegs)
		const rightHit = castHorizontalRay(origin, 1, this.allSegs)
		if (!leftHit || !rightHit) return null
		if (rightHit.point.x - leftHit.point.x < 12) return null
		// Ignore closed internal hollow chambers inside a single extrusion.
		if (leftHit.shapeIndex === rightHit.shapeIndex) return null

		const lowShape = this.allProfileShapes.find((s) => s.index === leftHit.shapeIndex)
		const highShape = this.allProfileShapes.find((s) => s.index === rightHit.shapeIndex)
		if (!lowShape || !highShape) return null

		const minX = leftHit.point.x + 0.35
		const maxX = rightHit.point.x - 0.35

		// 1. Cast directly up/down around the cursor (tight ±2.2 mm anti-groove band) against ALL profiles.
		const directXs = buildBandXs(origin.x, minX, maxX, 2.2)
		let { upHits, downHits } = castVerticalBand(directXs, origin.y, this.allProfileShapes, this.allSegs)

		// 2. If cursor is in the open daylight gap where direct vertical rays miss walls, probe inside the nearest pocket mouth.
		const nearLow = origin.x - leftHit.point.x <= rightHit.point.x - origin.x
		const refShape = nearLow ? lowShape : highShape
		const pocketBackX = nearLow ? leftHit.point.x : rightHit.point.x
		const mouthX = nearLow ? refShape.bbox.maxX : refShape.bbox.minX
		let anchorVisualX = origin.x

		if (!upHits.length || !downHits.length) {
			const mouthXs = buildPocketSampleXs(origin.x, pocketBackX, mouthX, nearLow)
			const mouthRes = castVerticalBand(mouthXs, origin.y, this.allProfileShapes, this.allSegs)
			if (!upHits.length && mouthRes.upHits.length) {
				upHits = mouthRes.upHits
				anchorVisualX = mouthXs[Math.floor(mouthXs.length / 2)] ?? origin.x
			}
			if (!downHits.length && mouthRes.downHits.length) {
				downHits = mouthRes.downHits
				anchorVisualX = mouthXs[Math.floor(mouthXs.length / 2)] ?? origin.x
			}
		}

		if (!upHits.length && !downHits.length) return null

		// Tightest clamping lips: largest Y on top wall, smallest Y on bottom wall (ignores recessed T-slot notches).
		const bestUp = upHits.length
			? upHits.reduce((best, cur) => (cur.point.y > best.point.y ? cur : best))
			: null
		const bestDown = downHits.length
			? downHits.reduce((best, cur) => (cur.point.y < best.point.y ? cur : best))
			: null

		const topY = bestUp ? bestUp.point.y : refShape.bbox.minY
		const bottomY = bestDown ? bestDown.point.y : refShape.bbox.maxY
		if (bottomY - topY < 3) return null

		const hitBeadWall = Boolean(
			(bestUp && BEAD_ROLES.has(bestUp.role)) ||
				(bestDown && BEAD_ROLES.has(bestDown.role)) ||
				BEAD_ROLES.has(leftHit.role) ||
				BEAD_ROLES.has(rightHit.role),
		)

		const spanX = rightHit.point.x - leftHit.point.x
		const rawOffset = nearLow ? anchorVisualX - leftHit.point.x : rightHit.point.x - anchorVisualX
		const maxSafeOffset = Math.max(1.5, Math.min(Math.abs(mouthX - pocketBackX) + 4, spanX * 0.42))
		const probeOffsetFromLow = roundTenth(Math.max(1.0, Math.min(maxSafeOffset, rawOffset)))

		return {
			origin,
			topHit: { x: roundTenth(anchorVisualX), y: roundTenth(topY) },
			bottomHit: { x: roundTenth(anchorVisualX), y: roundTenth(bottomY) },
			leftHit,
			rightHit,
			pocketMinY: roundTenth(topY),
			pocketMaxY: roundTenth(bottomY),
			pocketWidthMm: roundTenth(bottomY - topY),
			leftWallX: roundTenth(leftHit.point.x),
			rightWallX: roundTenth(rightHit.point.x),
			probeOffsetFromLow,
			hitBeadWall,
		}
	}

	/** Convert a pocket raycast hit into a width-invariant `SectionGlassDomain`. */
	static toGlassDomain(
		probe: PocketProbeResult,
		baseStart: number,
		baseEnd: number,
		clearanceMm = DEFAULT_GLASS_CLEARANCE_MM,
	): SectionGlassDomain {
		const pocketInsetLow = roundTenth(probe.leftWallX - baseStart)
		const pocketInsetHigh = roundTenth(baseEnd - probe.rightWallX)
		const maxClear = Math.max(0, (probe.rightWallX - probe.leftWallX - 12) / 2)
		const clear = Math.min(clearanceMm, maxClear)
		const insetLow = roundTenth(pocketInsetLow + clear)
		const insetHigh = roundTenth(pocketInsetHigh + clear)
		return {
			configured: true,
			minY: probe.pocketMinY,
			maxY: probe.pocketMaxY,
			insetLow,
			insetHigh,
			insetMullion: insetHigh,
			align: 'center',
			raycast: {
				enabled: true,
				pocketMinY: probe.pocketMinY,
				pocketMaxY: probe.pocketMaxY,
				pocketInsetLow,
				pocketInsetHigh,
				pocketInsetMullion: pocketInsetHigh,
				probeOffsetFromLow: probe.probeOffsetFromLow,
			},
		}
	}

	/**
	 * Step 4: Automatically orient and seat a bead/adaptor profile at the Left or Right corner
	 * of a raycast pocket domain, centered on the pocket centerline for sash U-beads or aligned
	 * to the open rebate edge for 1-sided frame clip-in beads.
	 */
	seatBeadAtDomainCorner(
		piece: SectionPiece,
		index: number,
		baseStart: number,
		baseEnd: number,
		glassBaseStart: number,
		glassBaseEnd: number,
		outline: SectionOutline | null,
		domain: SectionGlassDomain,
		beadSide: 'inside' | 'outside' = 'inside',
	): SectionPieceTransform | null {
		const rc = domain.raycast
		if (!rc?.enabled || !outline || !(outline.width > 0 && outline.depth > 0)) return null

		const pocketMinY = Math.min(rc.pocketMinY, rc.pocketMaxY)
		const pocketMaxY = Math.max(rc.pocketMinY, rc.pocketMaxY)
		const pocketH = pocketMaxY - pocketMinY
		const pocketCenterY = (pocketMinY + pocketMaxY) / 2
		const wallX = piece.mirrored
			? glassBaseEnd - rc.pocketInsetHigh
			: glassBaseStart + rc.pocketInsetLow
		const glassDir = piece.mirrored ? -1 : 1

		const nearHost = findNearestHostForWall(this.hostShapes, wallX)
		const isSashHost = nearHost?.piece.role === 'sash'
		// Match host's shifted vertical pocket center if this stile has an individual offsetDepth.
		let localPocketMinY = pocketMinY
		let localPocketMaxY = pocketMaxY
		let localPocketCenterY = pocketCenterY
		if (isSashHost && nearHost) {
			const probeX = wallX + glassDir * Math.min(5.0, Math.max(2.0, outline.width * 0.3))
			const nearSegs = extractSegments([nearHost])
			const uHit = castVerticalRay({ x: probeX, y: pocketCenterY }, -1, nearSegs)
			const dHit = castVerticalRay({ x: probeX, y: pocketCenterY }, 1, nearSegs)
			if (uHit && dHit && dHit.point.y - uHit.point.y >= pocketH * 0.7) {
				localPocketMinY = roundTenth(uHit.point.y)
				localPocketMaxY = roundTenth(dHit.point.y)
				localPocketCenterY = roundTenth((localPocketMinY + localPocketMaxY) / 2)
			}
		}

		let best: { score: number; transform: SectionPieceTransform } | null = null
		const rotations: Array<0 | 90 | 180 | 270> = [0, 90, 180, 270]
		const flips = [false, true]

		for (const rotation of rotations) {
			for (const flipX of flips) {
				const zeroT: SectionPieceTransform = { offsetAlong: 0, offsetDepth: 0, rotation, flipX, flipY: false }
				const zeroShape = buildPlacedShape(index, piece, baseStart, baseEnd, outline, zeroT)
				const { bbox } = zeroShape
				if (bbox.width < 1 || bbox.height < 1) continue

				// Align back edge flush with pocket back wall (`wallX`).
				const targetXShift = piece.mirrored ? wallX - bbox.maxX : wallX - bbox.minX
				// Sash U-beads (e.g. HSL3409/HSL3410) span >= 72% of pocket height (allowing ~3-4 mm snap ears).
				const fitsAsInsert = isSashHost && bbox.height <= pocketH + 8.5 && bbox.height >= pocketH * 0.72

				const targetYShift = fitsAsInsert
					? localPocketCenterY - (bbox.minY + bbox.height / 2)
					: beadSide === 'outside'
						? localPocketMinY - bbox.minY
						: localPocketMaxY - bbox.maxY

				const placedT: SectionPieceTransform = {
					offsetAlong: roundTenth(targetXShift),
					offsetDepth: roundTenth(targetYShift),
					rotation,
					flipX,
					flipY: false,
				}
				const placed = buildPlacedShape(index, piece, baseStart, baseEnd, outline, placedT)
				const score = scoreBeadCandidate(
					placed,
					wallX,
					glassDir,
					localPocketMinY,
					localPocketMaxY,
					isSashHost,
					fitsAsInsert,
					nearHost,
				)
				if (!best || score < best.score) {
					best = { score, transform: placedT }
				}
			}
		}

		return best ? best.transform : null
	}

	/**
	 * Step 5: Dynamically re-cast vertical rays through `[hostShapes + beadShapes]` so when a
	 * bead enters or changes (e.g. switching glass thickness), the active domain height &
	 * vertical gasket anchors update automatically.
	 */
	recalculateDynamicDomain(
		domain: SectionGlassDomain,
		glassBaseStart: number,
		glassBaseEnd: number,
	): DynamicDomainState {
		const rc = domain.raycast
		const pocketMinY = rc?.enabled ? Math.min(rc.pocketMinY, rc.pocketMaxY) : Math.min(domain.minY, domain.maxY)
		const pocketMaxY = rc?.enabled ? Math.max(rc.pocketMinY, rc.pocketMaxY) : Math.max(domain.minY, domain.maxY)
		const pocketBwMm = roundTenth(pocketMaxY - pocketMinY)

		const leftWallX = rc?.enabled
			? roundTenth(glassBaseStart + rc.pocketInsetLow)
			: roundTenth(glassBaseStart + (domain.insetLow || 0))
		const rightWallX = rc?.enabled
			? roundTenth(glassBaseEnd - rc.pocketInsetHigh)
			: roundTenth(glassBaseEnd - (domain.insetHigh || 0))

		const bayMidX = (leftWallX + rightWallX) / 2
		const lowBeads = this.beadShapes.filter((b) => b.bbox.minX >= leftWallX - 15 && (b.bbox.minX + b.bbox.maxX) / 2 < bayMidX)
		const highBeads = this.beadShapes.filter((b) => b.bbox.maxX <= rightWallX + 15 && (b.bbox.minX + b.bbox.maxX) / 2 >= bayMidX)

		const probeOff = rc?.probeOffsetFromLow ?? 4
		const baseLowAnchorX = roundTenth(leftWallX + probeOff)
		const baseHighAnchorX = roundTenth(rightWallX - probeOff)

		// Keep the user's locked vertical anchor X when it aligns with the bead's glass-facing lip;
		// on asymmetric frame/mullion bays snap to the bead's glass-facing lip so gaskets sit squarely under the bead.
		const resolveAnchorX = (baseX: number, beads: PlacedShape[], isLow: boolean): number => {
			if (!beads.length) return baseX
			const minB = Math.min(...beads.map((b) => b.bbox.minX))
			const maxB = Math.max(...beads.map((b) => b.bbox.maxX))
			const lipX = isLow ? roundTenth(maxB - 1.2) : roundTenth(minB + 1.2)
			if (baseX >= minB + 0.5 && baseX <= maxB - 0.5 && Math.abs(baseX - lipX) <= 2.2) return baseX
			return lipX
		}
		const lowAnchorX = resolveAnchorX(baseLowAnchorX, lowBeads, true)
		const highAnchorX = resolveAnchorX(baseHighAnchorX, highBeads, false)

		if (!rc?.enabled || (!lowBeads.length && !highBeads.length)) {
			return {
				domain,
				pocketMinY,
				pocketMaxY,
				pocketBwMm,
				effectiveMinY: roundTenth(Math.min(domain.minY, domain.maxY)),
				effectiveMaxY: roundTenth(Math.max(domain.minY, domain.maxY)),
				effectiveBwMm: roundTenth(Math.abs(domain.maxY - domain.minY)),
				narrowedByBead: false,
				leftWallX,
				rightWallX,
				lowAnchorX,
				highAnchorX,
			}
		}

		const centerY = (pocketMinY + pocketMaxY) / 2
		// Allow frame clip-in beads (e.g. switching 6 mm CS4807 -> 12 mm CS4808 -> 24 mm CS4809)
		// to dynamically expand the active glazing channel across the host frame's vertical rebate.
		const hasFrameBead = [...lowBeads, ...highBeads].some((b) => b.piece.role === 'bead')
		let hostMinY = pocketMinY
		let hostMaxY = pocketMaxY
		for (const h of this.hostShapes) {
			if (h.bbox.minY < hostMinY) hostMinY = h.bbox.minY
			if (h.bbox.maxY > hostMaxY) hostMaxY = h.bbox.maxY
		}
		const minAllowedY = hasFrameBead ? hostMinY - 1.0 : pocketMinY - 1.5
		const maxAllowedY = hasFrameBead ? hostMaxY + 1.0 : pocketMaxY + 1.5
		const upHits: number[] = []
		const downHits: number[] = []
		for (const ax of [lowAnchorX - 0.8, lowAnchorX, lowAnchorX + 0.8, highAnchorX - 0.8, highAnchorX, highAnchorX + 0.8]) {
			const pt = { x: ax, y: centerY }
			if (this.beadShapes.some((b) => pointInRings(pt, b.rings))) continue
			const u = castVerticalRay(pt, -1, this.allSegs)
			const d = castVerticalRay(pt, 1, this.allSegs)
			if (u && u.point.y >= minAllowedY && u.point.y < centerY - 0.8) upHits.push(u.point.y)
			if (d && d.point.y <= maxAllowedY && d.point.y > centerY + 0.8) downHits.push(d.point.y)
		}

		const effMinY = upHits.length ? roundTenth(Math.max(...upHits)) : pocketMinY
		const effMaxY = downHits.length ? roundTenth(Math.min(...downHits)) : pocketMaxY
		const validNarrow = effMaxY - effMinY >= 3
		const finalMinY = validNarrow ? effMinY : pocketMinY
		const finalMaxY = validNarrow ? effMaxY : pocketMaxY
		const effBw = roundTenth(finalMaxY - finalMinY)

		// Also advance horizontal glass inset past any U-bead back web so glass never clips the bead web.
		let extraLowWeb = 0
		for (const b of lowBeads) {
			const webHit = castHorizontalRay({ x: lowAnchorX, y: (finalMinY + finalMaxY) / 2 }, -1, extractSegments([b]))
			if (webHit && webHit.point.x > leftWallX && webHit.point.x < leftWallX + 8) {
				extraLowWeb = Math.max(extraLowWeb, webHit.point.x - leftWallX)
			}
		}
		let extraHighWeb = 0
		for (const b of highBeads) {
			const webHit = castHorizontalRay({ x: highAnchorX, y: (finalMinY + finalMaxY) / 2 }, 1, extractSegments([b]))
			if (webHit && webHit.point.x < rightWallX && webHit.point.x > rightWallX - 8) {
				extraHighWeb = Math.max(extraHighWeb, rightWallX - webHit.point.x)
			}
		}

		const updatedDomain: SectionGlassDomain = {
			...domain,
			minY: finalMinY,
			maxY: finalMaxY,
			insetLow: roundTenth(Math.max(domain.insetLow, rc.pocketInsetLow + extraLowWeb + 2.0)),
			insetHigh: roundTenth(Math.max(domain.insetHigh, rc.pocketInsetHigh + extraHighWeb + 2.0)),
		}

		return {
			domain: updatedDomain,
			pocketMinY,
			pocketMaxY,
			pocketBwMm,
			effectiveMinY: finalMinY,
			effectiveMaxY: finalMaxY,
			effectiveBwMm: effBw,
			narrowedByBead: effBw < pocketBwMm - 0.2,
			leftWallX,
			rightWallX,
			lowAnchorX,
			highAnchorX,
		}
	}

	/** Steps 6 & 7: Place Outer (top) and Inner (bottom) gaskets centered directly on the vertical ray anchors. */
	static computeGasketPlacements(
		dyn: DynamicDomainState,
		glassFit: ResolvedGlassBounds,
		meta: PaneGasketsMeta | null,
	): GasketPlacement[] {
		const topGap = glassFit.y - dyn.effectiveMinY
		const botGap = dyn.effectiveMaxY - (glassFit.y + glassFit.depth)
		if (topGap < 0.4 && botGap < 0.4) return []

		const outerCode = meta?.outer_code || 'Outer'
		const innerCode = meta?.inner_code || 'Inner'
		const outerMm = meta?.outer_mm ?? roundTenth(Math.max(1.5, topGap))
		const innerMm = meta?.inner_mm ?? roundTenth(Math.max(1.5, botGap))

		const sides: Array<{ side: 'low' | 'high'; anchorX: number }> = [
			{ side: 'low', anchorX: dyn.lowAnchorX },
			{ side: 'high', anchorX: dyn.highAnchorX },
		]

		const out: GasketPlacement[] = []
		for (const s of sides) {
			const w = 3.6
			const cx = roundTenth(s.anchorX)
			if (topGap >= 0.4) {
				// Fill flush from clamping lip to glass face when gap matches nominal gasket (+1.5 mm); otherwise draw true nominal thickness against glass.
				const fillFlush = topGap <= outerMm + 1.5
				const h = fillFlush ? topGap : Math.max(0.8, outerMm)
				out.push({
					id: `${s.side}-outer`,
					side: s.side,
					face: 'outer',
					code: outerCode,
					nominalMm: outerMm,
					anchorX: cx,
					x: roundTenth(cx - w / 2),
					y: roundTenth(fillFlush ? dyn.effectiveMinY : glassFit.y - h),
					w,
					h: roundTenth(h),
				})
			}
			if (botGap >= 0.4) {
				const fillFlush = botGap <= innerMm + 1.5
				const h = fillFlush ? botGap : Math.max(0.8, innerMm)
				out.push({
					id: `${s.side}-inner`,
					side: s.side,
					face: 'inner',
					code: innerCode,
					nominalMm: innerMm,
					anchorX: cx,
					x: roundTenth(cx - w / 2),
					y: roundTenth(glassFit.y + glassFit.depth),
					w,
					h: roundTenth(h),
				})
			}
		}
		return out
	}
}

function scoreBeadCandidate(
	placed: PlacedShape,
	wallX: number,
	glassDir: 1 | -1,
	pocketMinY: number,
	pocketMaxY: number,
	isSashHost: boolean,
	fitsAsInsert: boolean,
	nearHost?: PlacedShape,
): number {
	const pocketH = pocketMaxY - pocketMinY
	const centerY = (pocketMinY + pocketMaxY) / 2
	const segs = extractSegments([placed])
	let penalty = 0

	if (fitsAsInsert) {
		// U-channel insert bead: open mouth must face glass (`glassDir`), closed web near `wallX`.
		const mouthX =
			glassDir === 1
				? placed.bbox.minX + placed.bbox.width * 0.72
				: placed.bbox.maxX - placed.bbox.width * 0.72
		const backTestX =
			glassDir === 1
				? placed.bbox.minX + Math.min(1.8, placed.bbox.width * 0.15)
				: placed.bbox.maxX - Math.min(1.8, placed.bbox.width * 0.15)
		const mouthBlocked = pointInRings({ x: mouthX, y: centerY }, placed.rings)
		if (mouthBlocked) penalty += 500
		const upLeg = castVerticalRay({ x: mouthX, y: centerY }, -1, segs)
		const downLeg = castVerticalRay({ x: mouthX, y: centerY }, 1, segs)
		if (!upLeg || !downLeg) penalty += 220
		const backHit = castHorizontalRay({ x: mouthX, y: centerY }, (-glassDir) as 1 | -1, segs)
		if (!backHit && !pointInRings({ x: backTestX, y: centerY }, placed.rings)) penalty += 180
		penalty += Math.abs(pocketH - placed.bbox.height) * 4.0
	} else {
		// Prevent rotating an upright U-channel sideways into a tall sash pocket when an upright orientation exists.
		if (isSashHost && pocketH >= 18) penalty += 260
		// 1-sided clip-in frame bead: glazing face toward glass should fit cleanly inside pocket height.
		if (placed.bbox.minY < pocketMinY - 6 || placed.bbox.maxY > pocketMaxY + 6) penalty += 80
		penalty += Math.abs(placed.bbox.width - placed.bbox.height) * 0.2
	}

	if (nearHost) {
		let overlapPts = 0
		for (const ring of placed.rings) {
			for (const pt of ring) {
				// Ignore shallow snap-ear engagement grooves at the top/bottom pocket retention lips.
				if (fitsAsInsert && (pt.y <= pocketMinY + 2.0 || pt.y >= pocketMaxY - 2.0)) continue
				if (pointInRings(pt, nearHost.rings)) overlapPts++
			}
		}
		penalty += overlapPts * 3
	}
	void wallX
	return penalty
}

function findNearestHostForWall(hosts: PlacedShape[], wallX: number): PlacedShape | undefined {
	let best: PlacedShape | undefined
	let bestScore = Infinity
	for (const h of hosts) {
		const contains = wallX >= h.bbox.minX - 1.5 && wallX <= h.bbox.maxX + 1.5
		const dist = contains ? 0 : Math.min(Math.abs(h.bbox.minX - wallX), Math.abs(h.bbox.maxX - wallX))
		const roleBonus = h.piece.role === 'sash' ? 0 : 10
		const score = dist * 10 + roleBonus
		if (score < bestScore) {
			bestScore = score
			best = h
		}
	}
	return best
}

function buildBandXs(centerX: number, minX: number, maxX: number, halfSpan: number): number[] {
	if (maxX <= minX) return [centerX]
	const clamped = Math.max(minX, Math.min(maxX, centerX))
	const steps = [-1, -0.5, 0, 0.5, 1]
	const set = new Set<number>()
	for (const f of steps) {
		set.add(roundTenth(Math.max(minX, Math.min(maxX, clamped + f * halfSpan))))
	}
	return [...set]
}

function castVerticalBand(
	xs: number[],
	originY: number,
	profiles: PlacedShape[],
	segs: Seg[],
): { upHits: RayHit[]; downHits: RayHit[] } {
	const upHits: RayHit[] = []
	const downHits: RayHit[] = []
	for (const sx of xs) {
		const pt = { x: sx, y: originY }
		if (profiles.some((s) => pointInRings(pt, s.rings))) continue
		const u = castVerticalRay(pt, -1, segs)
		const d = castVerticalRay(pt, 1, segs)
		if (u) upHits.push(u)
		if (d) downHits.push(d)
	}
	return { upHits, downHits }
}

function buildPocketSampleXs(originX: number, backX: number, mouthX: number, nearLow: boolean): number[] {
	const lo = Math.min(backX, mouthX) + 0.9
	const hi = Math.max(backX, mouthX) - 0.9
	if (hi <= lo) return [originX]
	const base = originX >= lo && originX <= hi ? originX : nearLow ? hi - 1.2 : lo + 1.2
	const offsets = [-2.0, -1.0, 0, 1.0, 2.0]
	const set = new Set<number>()
	for (const off of offsets) {
		set.add(roundTenth(Math.max(lo, Math.min(hi, base + off))))
	}
	return [...set]
}

function extractSegments(shapes: PlacedShape[]): Seg[] {
	const segs: Seg[] = []
	for (const s of shapes) {
		for (const ring of s.rings) {
			for (let i = 0; i < ring.length; i++) {
				const a = ring[i]
				const b = ring[(i + 1) % ring.length]
				if (Math.hypot(b.x - a.x, b.y - a.y) > 0.02) {
					segs.push({ a, b, shapeIndex: s.index, role: s.piece.role, code: s.piece.code })
				}
			}
		}
	}
	return segs
}

function castHorizontalRay(origin: Point, dir: 1 | -1, segs: Seg[]): RayHit | null {
	let best: RayHit | null = null
	for (const s of segs) {
		const minY = Math.min(s.a.y, s.b.y)
		const maxY = Math.max(s.a.y, s.b.y)
		if (origin.y < minY - 1e-6 || origin.y > maxY + 1e-6) continue
		const dy = s.b.y - s.a.y
		if (Math.abs(dy) < 1e-6) continue
		const t = (origin.y - s.a.y) / dy
		if (t < -1e-6 || t > 1 + 1e-6) continue
		const hitX = s.a.x + t * (s.b.x - s.a.x)
		const dist = (hitX - origin.x) * dir
		if (dist <= 0.05) continue
		if (!best || dist < best.dist) {
			best = { point: { x: hitX, y: origin.y }, dist, shapeIndex: s.shapeIndex, role: s.role, code: s.code }
		}
	}
	return best
}

function castVerticalRay(origin: Point, dir: 1 | -1, segs: Seg[]): RayHit | null {
	let best: RayHit | null = null
	for (const s of segs) {
		const minX = Math.min(s.a.x, s.b.x)
		const maxX = Math.max(s.a.x, s.b.x)
		if (origin.x < minX - 1e-6 || origin.x > maxX + 1e-6) continue
		const dx = s.b.x - s.a.x
		if (Math.abs(dx) < 1e-6) continue
		const t = (origin.x - s.a.x) / dx
		if (t < -1e-6 || t > 1 + 1e-6) continue
		const hitY = s.a.y + t * (s.b.y - s.a.y)
		const dist = (hitY - origin.y) * dir
		if (dist <= 0.05) continue
		if (!best || dist < best.dist) {
			best = { point: { x: origin.x, y: hitY }, dist, shapeIndex: s.shapeIndex, role: s.role, code: s.code }
		}
	}
	return best
}

function pointInRings(pt: Point, rings: Point[][]): boolean {
	let inside = false
	for (const ring of rings) {
		for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
			const xi = ring[i].x
			const yi = ring[i].y
			const xj = ring[j].x
			const yj = ring[j].y
			const intersect = yi > pt.y !== yj > pt.y && pt.x < ((xj - xi) * (pt.y - yi)) / (yj - yi) + xi
			if (intersect) inside = !inside
		}
	}
	return inside
}
