import { louverSectionRings, louverLayout, LOUVER_ANGLE, LOUVER_THICKNESS } from './louverGeometry'
import type { SectionOutline, SectionPiece } from '@/api'
import type { SectionPieceTransform } from '@/design/types'

export interface Point {
	x: number
	y: number
}

export interface BBox {
	minX: number
	minY: number
	maxX: number
	maxY: number
	width: number
	height: number
}

export interface PlacedShape {
	index: number
	piece: SectionPiece
	rings: Point[][]
	bbox: BBox
	labelPos: Point
}

export const COMPACT_GLASS_MM = 96
export const GLASS_REF_THICKNESS_MM = 6
export const DEFAULT_PROFILE_DEPTH_MM = 45
export const SNAP_THRESHOLD_MM = 2.8
export const WALL_CLEARANCE_MM = 0.0
/** Deep solid penetration threshold (mm) so snap-hooks and T-slots can lock together like CAD. */
const DEEP_PENETRATION_MM = 1.35

/** Canonical key shared across Left/Right corners and B-B (top) / A-A (side) views. */
export function canonicalPieceKey(piece: SectionPiece): string {
	return `${piece.role}:${piece.code}`
}

/** Mirror pair mappings across the central mullion or frame centerline. */
export const MIRROR_OF: Record<string, string> = {
	OBL: 'MBR',
	OBR: 'MBL',
	MBL: 'OBR',
	MBR: 'OBL',
	OFL: 'MFR',
	MFR: 'OFL',
	OSL: 'MSR',
	MSR: 'OSL',
	OSR: 'MSL',
	MSL: 'OSR',
}

/** Return the twin instance tag mirrored across the central mullion/frame axis. */
export function getTwinTag(tag: string): string | null {
	return MIRROR_OF[tag] ?? null
}

/**
 * Classifies section pieces into instance tags (OBL, OBR, M1, MBL, MBR, OFL, MFR, etc.)
 * based on side relative to the divider (mullion/transom) and connection position.
 */
export function classifySectionPieceInstances(
	axis: 'h' | 'v',
	pieces: SectionPiece[],
	cutLength: number,
): string[] {
	if (!pieces.length) return []

	// Locate central divider bar if present
	const divider = pieces.find(
		(p) =>
			(axis === 'h' && p.role === 'mullion') ||
			(axis === 'v' && p.role === 'transom'),
	)
	const dividerMid = divider ? (divider.start + divider.end) / 2 : cutLength / 2

	const beadO: number[] = []
	const beadM: number[] = []
	const sashO: number[] = []
	const sashM: number[] = []
	const frameO: number[] = []
	const frameM: number[] = []

	for (let i = 0; i < pieces.length; i++) {
		const p = pieces[i]
		if (p === divider || p.role === 'mullion' || p.role === 'transom') continue
		if (p.kind === 'glass') continue

		const mid = (p.start + p.end) / 2
		const isO = mid < dividerMid

		if (p.role === 'bead' || p.role === 'gasket' || p.role === 'glass_adaptor') {
			if (isO) beadO.push(i)
			else beadM.push(i)
		} else if (p.role === 'sash') {
			if (isO) sashO.push(i)
			else sashM.push(i)
		} else if (p.role === 'frame') {
			if (isO) frameO.push(i)
			else frameM.push(i)
		}
	}

	const sortByPos = (indices: number[]) => indices.sort((a, b) => pieces[a].start - pieces[b].start)
	sortByPos(beadO)
	sortByPos(beadM)
	sortByPos(sashO)
	sortByPos(sashM)
	sortByPos(frameO)
	sortByPos(frameM)

	const tags: string[] = new Array(pieces.length).fill('')

	// Assign beads:
	// Side O: outer (jamb side, connection 1) = OBL, inner (mullion side, connection 2) = OBR
	if (beadO.length === 1) {
		tags[beadO[0]] = 'OBL'
	} else if (beadO.length >= 2) {
		tags[beadO[0]] = 'OBL'
		tags[beadO[beadO.length - 1]] = 'OBR'
		for (let k = 1; k < beadO.length - 1; k++) {
			tags[beadO[k]] = `OB_${k + 1}`
		}
	}

	// Side M: inner (mullion side, connection 2) = MBL, outer (jamb side, connection 1) = MBR
	if (beadM.length === 1) {
		tags[beadM[0]] = 'MBR'
	} else if (beadM.length >= 2) {
		tags[beadM[0]] = 'MBL'
		tags[beadM[beadM.length - 1]] = 'MBR'
		for (let k = 1; k < beadM.length - 1; k++) {
			tags[beadM[k]] = `MB_${k + 1}`
		}
	}

	// Assign frame:
	if (frameO.length > 0) tags[frameO[0]] = 'OFL'
	if (frameM.length > 0) tags[frameM[frameM.length - 1]] = 'MFR'

	// Assign sash:
	if (sashO.length === 1) {
		tags[sashO[0]] = 'OSL'
	} else if (sashO.length >= 2) {
		tags[sashO[0]] = 'OSL'
		tags[sashO[sashO.length - 1]] = 'OSR'
	}
	if (sashM.length === 1) {
		tags[sashM[0]] = 'MSR'
	} else if (sashM.length >= 2) {
		tags[sashM[0]] = 'MSL'
		tags[sashM[sashM.length - 1]] = 'MSR'
	}

	// Assign remaining items (divider, glass, fallbacks)
	for (let i = 0; i < pieces.length; i++) {
		if (tags[i]) continue
		const p = pieces[i]
		if (p === divider || p.role === 'mullion' || p.role === 'transom') {
			tags[i] = p.panel || 'M1'
		} else if (p.kind === 'glass') {
			tags[i] = `GLASS:${p.panel}`
		} else {
			const mid = (p.start + p.end) / 2
			const side = mid < dividerMid ? 'O' : 'M'
			tags[i] = `${side}_${p.role}_${i}`
		}
	}

	return tags
}

/** Instance-specific key when mirror/sync is disabled or per-instance state is saved. */
export function instancePieceKey(axis: string, tagOrIndex: string | number, piece?: SectionPiece): string {
	if (typeof tagOrIndex === 'string') {
		return `${axis}:${tagOrIndex}`
	}
	return `${axis}:${tagOrIndex}:${piece?.role ?? 'piece'}:${piece?.code ?? 'code'}`
}

/**
 * All profiles (Outer Frame, Mullion, Transom, Sash, Bead/Gasket, and Glass)
 * are moveable in the puzzle editor.
 */
export function isPieceMoveable(piece: SectionPiece): boolean {
	return piece.kind !== 'louver'
}

/**
 * Default puzzle transform per role when a piece has not been manually moved yet.
 */
export function defaultTransformForPiece(
	piece: SectionPiece,
	outline: SectionOutline | null,
): SectionPieceTransform {
	void outline
	if (piece.role === 'bead') {
		return { offsetAlong: 0, offsetDepth: 23, rotation: 0, flipX: false, flipY: false }
	}
	if (piece.role === 'sash') {
		return { offsetAlong: 0, offsetDepth: -11.5, rotation: 0, flipX: false, flipY: false }
	}
	return { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false }
}

/** Search 0.5 mm positions against the real profile loops, preferring the
 * closest non-overlapping sash/gasket or glass/rebate contact. */
export function seatedDefaultTransform(
	movingIndex: number,
	piece: SectionPiece,
	baseStart: number,
	baseEnd: number,
	outline: SectionOutline | null,
	obstacles: PlacedShape[],
): SectionPieceTransform {
	const initial = defaultTransformForPiece(piece, outline)
	if ((piece.role !== 'sash' && piece.kind !== 'glass') || !obstacles.length) return initial
	const rawDepth = piece.kind === 'glass'
		? Math.max(piece.thickness || GLASS_REF_THICKNESS_MM, 1)
		: Math.max(outline?.depth || DEFAULT_PROFILE_DEPTH_MM, 1)
	const obstacleMin = Math.min(...obstacles.map((o) => o.bbox.minY))
	const obstacleMax = Math.max(...obstacles.map((o) => o.bbox.maxY))
	const minDepth = Math.floor((obstacleMin - rawDepth - 8) * 2) / 2
	const maxDepth = Math.ceil((obstacleMax + rawDepth + 8) * 2) / 2
	// Glass width and its endpoints come from the manufacturing layout. Only
	// its depth may be fitted; shifting it sideways breaks the opposite rebate.
	const alongRange = piece.kind === 'glass' ? 0 : Math.min(12, Math.max(2, (baseEnd - baseStart) / 8))
	let best: { transform: SectionPieceTransform; score: number } | null = null
	const evaluate = (along: number, depth: number) => {
		const roundedAlong = Math.round(along * 2) / 2 || 0
		const roundedDepth = Math.round(depth * 2) / 2
		const transform = { ...initial, offsetAlong: roundedAlong, offsetDepth: roundedDepth }
		const shape = buildPlacedShape(movingIndex, piece, baseStart, baseEnd, outline, transform)
		if (obstacles.some((obstacle) => solidsOverlap(shape, obstacle))) return
		const penalty = Math.abs(roundedAlong) * 0.02 + Math.abs(roundedDepth) * 0.001
		// The bounding-box gap is a lower bound for the exact polygon distance.
		// Skip expensive ring-to-ring distance work when it cannot beat the best fit.
		if (best && Math.min(...obstacles.map((obstacle) => bboxDistance(shape.bbox, obstacle.bbox))) + penalty >= best.score) return
		const clearance = Math.min(...obstacles.map((obstacle) => shapeDistance(shape, obstacle)))
		const score = clearance + penalty
		if (!best || score < best.score) best = { transform, score }
	}
	// A full 0.5 mm grid can mean several thousand polygon collision checks for
	// each sash. Find the seating basin coarsely, then retain the original 0.5 mm
	// precision in a small neighborhood around the best candidate.
	const coarseStep = 2.5
	for (let depth = minDepth; depth <= maxDepth; depth += coarseStep) {
		for (let along = -alongRange; along <= alongRange; along += coarseStep) evaluate(along, depth)
	}
	if (best) {
		const centerAlong = best.transform.offsetAlong
		const centerDepth = best.transform.offsetDepth
		for (let depth = Math.max(minDepth, centerDepth - coarseStep); depth <= Math.min(maxDepth, centerDepth + coarseStep); depth += 0.5) {
			for (let along = Math.max(-alongRange, centerAlong - coarseStep); along <= Math.min(alongRange, centerAlong + coarseStep); along += 0.5) evaluate(along, depth)
		}
	}
	const fitted = best?.transform ?? initial
	const shape = buildPlacedShape(movingIndex, piece, baseStart, baseEnd, outline, fitted)
	const joined = magneticAutoJoin(shape, fitted, piece, obstacles, 0.55)
	if (joined) {
		if (piece.kind === 'glass') joined.offsetAlong = 0
		const joinedShape = buildPlacedShape(movingIndex, piece, baseStart, baseEnd, outline, joined)
		if (!obstacles.some(obstacle => solidsOverlap(joinedShape, obstacle)) &&
			Math.min(...obstacles.map(obstacle => shapeDistance(joinedShape, obstacle))) <=
			Math.min(...obstacles.map(obstacle => shapeDistance(shape, obstacle)))) return joined
	}
	return fitted
}

function bboxDistance(a: BBox, b: BBox): number {
	const dx = Math.max(0, a.minX - b.maxX, b.minX - a.maxX)
	const dy = Math.max(0, a.minY - b.maxY, b.minY - a.maxY)
	return Math.hypot(dx, dy)
}

/** Shared transforms are expressed on the low side; instance offsets are world coordinates. */
export function canonicalTransformForPiece(piece: SectionPiece, transform: SectionPieceTransform): SectionPieceTransform {
	return { ...transform, offsetAlong: (piece.mirrored ? -transform.offsetAlong : transform.offsetAlong) || 0 }
}

/**
 * Compress long glass spans to `COMPACT_GLASS_MM` while keeping every profile joint at 1:1 mm scale
 * and keeping any Mullion/Transom anchored at its exact proportional/center split position.
 */
export function compactPieceSpans(
	pieces: SectionPiece[],
	compact = true,
	axis: 'h' | 'v' = 'h',
): { starts: number[]; ends: number[]; totalSpan: number } {
	if (!pieces.length) return { starts: [], ends: [], totalSpan: 100 }
	if (!compact) {
		const starts = pieces.map((p) => p.start)
		const ends = pieces.map((p) => p.end)
		const maxEnd = Math.max(...ends, 100)
		return { starts, ends, totalSpan: maxEnd }
	}
	const displayLength = (piece: SectionPiece) => {
		const length = piece.end - piece.start
		if (piece.kind === 'louver' && axis === 'v') {
			const layout = louverLayout(piece.opening_height || length, piece.blades || 7, piece.blade_width)
			const projected = layout.chord * Math.cos(LOUVER_ANGLE) + (piece.thickness || LOUVER_THICKNESS) * Math.sin(LOUVER_ANGLE)
			return Math.min(length, Math.max(COMPACT_GLASS_MM, layout.count * (projected + 4)))
		}
		return Math.min(length, COMPACT_GLASS_MM)
	}
	const reductions: { cutAfter: number; delta: number }[] = []
	for (const p of pieces) {
		if (p.kind !== 'glass' && p.kind !== 'louver') continue
		const len = p.end - p.start
		if (len > displayLength(p)) {
			reductions.push({
				cutAfter: (p.start + p.end) / 2,
				delta: len - displayLength(p),
			})
		}
	}
	const shiftAt = (pos: number) => {
		let shift = 0
		for (const r of reductions) {
			if (pos > r.cutAfter) shift += r.delta
		}
		return pos - shift
	}
	const starts: number[] = []
	const ends: number[] = []
	for (const p of pieces) {
		if (p.kind === 'glass' || p.kind === 'louver') {
			const s = shiftAt(p.start)
			const e = shiftAt(p.end)
			starts.push(s)
			ends.push(Math.max(s + displayLength(p), e))
		} else {
			const w = p.end - p.start
			const center = (p.start + p.end) / 2
			const shiftedCenter = shiftAt(center)
			starts.push(shiftedCenter - w / 2)
			ends.push(shiftedCenter + w / 2)
		}
	}
	const minS = Math.min(...starts, 0)
	const normStarts = starts.map((s) => s - minS)
	const normEnds = ends.map((e) => e - minS)
	const totalSpan = Math.max(...normEnds, 100)
	return { starts: normStarts, ends: normEnds, totalSpan }
}

/**
 * Parse the profile SVG into closed polygon rings in mm.  Studio imports store
 * ordinary SVG path data (including DXF-originated arcs), not a second mesh
 * representation.  Curves are flattened here so the puzzle and Three preview
 * use the same source geometry.  An arc gets ten samples per quarter turn.
 */
const parsedSvgRingCache = new Map<string, Point[][]>()

export function parseSvgRings(svg: string | undefined, fallbackW: number, fallbackD: number): Point[][] {
	if (!svg) return [rectRing(0, 0, fallbackW, fallbackD)]
	const cacheKey = `${fallbackW}|${fallbackD}|${svg}`
	const cached = parsedSvgRingCache.get(cacheKey)
	if (cached) return cached
	const tokens = svg.match(/[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:e[-+]?\d+)?/g) ?? []
	const rings: Point[][] = []
	let i = 0
	let command = ''
	let current = { x: 0, y: 0 }
	let start = { x: 0, y: 0 }
	let lastControl: Point | null = null
	let ring: Point[] = []
	const isCommand = () => i < tokens.length && /^[a-zA-Z]$/.test(tokens[i])
	const number = () => Number(tokens[i++])
	const point = (relative: boolean): Point => ({ x: number() + (relative ? current.x : 0), y: number() + (relative ? current.y : 0) })
	const add = (p: Point) => {
		if (!ring.length || Math.hypot(p.x - ring[ring.length - 1].x, p.y - ring[ring.length - 1].y) > 0.01) ring.push(p)
	}
	const finish = () => {
		if (ring.length >= 3) rings.push(ring)
		ring = []
	}
	const cubic = (a: Point, b: Point, c: Point, d: Point) => {
		for (let n = 1; n <= 10; n++) {
			const t = n / 10; const mt = 1 - t
			add({ x: mt ** 3 * a.x + 3 * mt ** 2 * t * b.x + 3 * mt * t ** 2 * c.x + t ** 3 * d.x, y: mt ** 3 * a.y + 3 * mt ** 2 * t * b.y + 3 * mt * t ** 2 * c.y + t ** 3 * d.y })
		}
	}
	const quadratic = (a: Point, b: Point, c: Point) => {
		for (let n = 1; n <= 10; n++) { const t = n / 10; const mt = 1 - t; add({ x: mt * mt * a.x + 2 * mt * t * b.x + t * t * c.x, y: mt * mt * a.y + 2 * mt * t * b.y + t * t * c.y }) }
	}
	const arc = (a: Point, rx0: number, ry0: number, rotation: number, large: number, sweep: number, b: Point) => {
		let rx = Math.abs(rx0); let ry = Math.abs(ry0)
		if (!rx || !ry || (a.x === b.x && a.y === b.y)) { add(b); return }
		const phi = rotation * Math.PI / 180; const cos = Math.cos(phi); const sin = Math.sin(phi)
		const dx = (a.x - b.x) / 2; const dy = (a.y - b.y) / 2
		const x1 = cos * dx + sin * dy; const y1 = -sin * dx + cos * dy
		const scale = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
		if (scale > 1) { const s = Math.sqrt(scale); rx *= s; ry *= s }
		const den = rx * rx * y1 * y1 + ry * ry * x1 * x1
		const coef = den ? (large === sweep ? -1 : 1) * Math.sqrt(Math.max(0, (rx * rx * ry * ry - den) / den)) : 0
		const cx1 = coef * rx * y1 / ry; const cy1 = coef * -ry * x1 / rx
		const cx = cos * cx1 - sin * cy1 + (a.x + b.x) / 2; const cy = sin * cx1 + cos * cy1 + (a.y + b.y) / 2
		const angle = (u: Point, v: Point) => Math.atan2(u.x * v.y - u.y * v.x, u.x * v.x + u.y * v.y)
		const u = { x: (x1 - cx1) / rx, y: (y1 - cy1) / ry }; const v = { x: (-x1 - cx1) / rx, y: (-y1 - cy1) / ry }
		const begin = angle({ x: 1, y: 0 }, u); let delta = angle(u, v)
		if (!sweep && delta > 0) delta -= 2 * Math.PI
		if (sweep && delta < 0) delta += 2 * Math.PI
		const steps = Math.max(1, Math.ceil(Math.abs(delta) / (Math.PI / 2) * 10))
		for (let n = 1; n <= steps; n++) { const t = begin + delta * n / steps; add({ x: cx + rx * Math.cos(t) * cos - ry * Math.sin(t) * sin, y: cy + rx * Math.cos(t) * sin + ry * Math.sin(t) * cos }) }
	}
	while (i < tokens.length) {
		if (isCommand()) command = tokens[i++]
		if (!command) break
		const relative = command === command.toLowerCase(); const op = command.toUpperCase()
		if (op === 'Z') { add(start); finish(); current = { ...start }; lastControl = null; command = ''; continue }
		if (op === 'M') { if (ring.length) finish(); current = point(relative); start = { ...current }; add(current); command = relative ? 'l' : 'L'; lastControl = null; continue }
		if (op === 'L') { current = point(relative); add(current); lastControl = null; continue }
		if (op === 'H') { current = { x: number() + (relative ? current.x : 0), y: current.y }; add(current); lastControl = null; continue }
		if (op === 'V') { current = { x: current.x, y: number() + (relative ? current.y : 0) }; add(current); lastControl = null; continue }
		if (op === 'C') { const c1 = point(relative); const c2 = point(relative); const end = point(relative); cubic(current, c1, c2, end); current = end; lastControl = c2; continue }
		if (op === 'S') { const c1 = lastControl ? { x: 2 * current.x - lastControl.x, y: 2 * current.y - lastControl.y } : current; const c2 = point(relative); const end = point(relative); cubic(current, c1, c2, end); current = end; lastControl = c2; continue }
		if (op === 'Q') { const c = point(relative); const end = point(relative); quadratic(current, c, end); current = end; lastControl = c; continue }
		if (op === 'T') { const c: Point = lastControl ? { x: 2 * current.x - lastControl.x, y: 2 * current.y - lastControl.y } : current; const end = point(relative); quadratic(current, c, end); current = end; lastControl = c; continue }
		if (op === 'A') { const rx = number(); const ry = number(); const r = number(); const large = number(); const sweep = number(); const end = point(relative); arc(current, rx, ry, r, large, sweep, end); current = end; lastControl = null; continue }
		break
	}
	if (ring.length) finish()
	const parsed = rings.length ? rings : [rectRing(0, 0, fallbackW, fallbackD)]
	parsedSvgRingCache.set(cacheKey, parsed)
	return parsed
}

/** Build transformed world-space polygon rings (in mm). */
export function buildPlacedShape(
	index: number,
	piece: SectionPiece,
	baseStart: number,
	baseEnd: number,
	outline: SectionOutline | null,
	transform: SectionPieceTransform,
	axis: 'h' | 'v' = 'h',
): PlacedShape {
	if (piece.kind === 'louver') {
		const rings = louverSectionRings(axis, baseStart, baseEnd, piece.opening_height || piece.end - piece.start, piece.blades || 7, piece.blade_width, piece.thickness || LOUVER_THICKNESS)
		const bbox = computeBBox(rings)
		return { index, piece, rings, bbox, labelPos: { x: (baseStart + baseEnd) / 2, y: bbox.minY - 6 } }
	}
	const rawW = outline?.width && outline.width > 0 ? outline.width : Math.max(4, baseEnd - baseStart)
	const rawD =
		piece.kind === 'glass'
			? piece.thickness > 0
				? piece.thickness
				: GLASS_REF_THICKNESS_MM
			: outline?.depth && outline.depth > 0
				? outline.depth
				: DEFAULT_PROFILE_DEPTH_MM

	const dx = transform.offsetAlong
	const dy = transform.offsetDepth

	if (piece.kind === 'glass') {
		const w = Math.max(4, baseEnd - baseStart)
		const gx = baseStart + dx
		const gy = -rawD / 2 + dy
		const ring = rectRing(gx, gy, w, rawD)
		const bbox = computeBBox([ring])
		return {
			index,
			piece,
			rings: [ring],
			bbox,
			labelPos: { x: gx + w / 2, y: gy + rawD / 2 },
		}
	}

	const baseX = baseStart + dx
	const baseY = dy

	const localRings = parseSvgRings(outline?.svg, rawW, rawD)
	const rot = (((piece.mirrored ? -transform.rotation : transform.rotation) % 360) + 360) % 360
	const flipX = Boolean(piece.mirrored) !== Boolean(transform.flipX)
	const flipY = Boolean(transform.flipY)
	const cx = rawW / 2
	const cy = rawD / 2
	const originU = Number.isFinite(transform.originU) ? transform.originU! : cx
	const originDepth = Number.isFinite(transform.originDepth) ? transform.originDepth! : cy

	const worldRings = localRings.map((ring) =>
		ring.map((p) => {
			let x = p.x - originU
			let y = p.y - originDepth
			if (flipX) x = -x
			if (flipY) y = -y
			if (rot === 90) [x, y] = [-y, x]
			else if (rot === 180) [x, y] = [-x, -y]
			else if (rot === 270) [x, y] = [y, -x]
			return { x: baseX + originU + x, y: baseY + originDepth + y }
		}),
	)
	const bbox = computeBBox(worldRings)
	const labelPos = computeProfileLabelPos(worldRings, bbox)
	return { index, piece, rings: worldRings, bbox, labelPos }
}

/**
 * Find the best interior chamber / in-between cavity point inside a profile's footprint
 * so the profile code label sits cleanly inside the profile (like CAD) instead of overlapping above it.
 */
export function computeProfileLabelPos(rings: Point[][], bbox: BBox): Point {
	if (bbox.width <= 0 || bbox.height <= 0) {
		return { x: bbox.minX, y: bbox.minY }
	}
	let bestPt = { x: bbox.minX + bbox.width / 2, y: bbox.minY + bbox.height / 2 }
	let bestScore = -Infinity

	const cols = 7
	const rows = 7
	for (let r = 1; r <= rows; r++) {
		const fy = 0.16 + (0.68 * r) / (rows + 1)
		const y = bbox.minY + bbox.height * fy
		for (let c = 1; c <= cols; c++) {
			const fx = 0.16 + (0.68 * c) / (cols + 1)
			const x = bbox.minX + bbox.width * fx
			const pt = { x, y }
			const edgeClearance = minDistanceToRings(pt, rings)
			// Prefer open hollow chambers or in-between channels (not directly on a stroke line)
			const centerBias = 1 - 0.25 * (Math.abs(fx - 0.5) + Math.abs(fy - 0.5))
			const score = edgeClearance * centerBias
			if (score > bestScore) {
				bestScore = score
				bestPt = pt
			}
		}
	}
	return {
		x: Math.round(bestPt.x * 10) / 10,
		y: Math.round(bestPt.y * 10) / 10,
	}
}

/**
 * Check if two piece types sit on each other in CAD hierarchy without clipping.
 * Sash sits on outer frame and mullion; glass sits on sash; gaskets sit in grooves.
 */
export function canPiecesOverlap(a: SectionPiece, b: SectionPiece): boolean {
	const rA = a.role
	const rB = b.role
	if (
		(rA === 'sash' && (rB === 'frame' || rB === 'mullion' || rB === 'transom')) ||
		(rB === 'sash' && (rA === 'frame' || rA === 'mullion' || rA === 'transom'))
	) {
		return true
	}
	if (a.kind === 'glass' || b.kind === 'glass' || a.kind === 'louver' || b.kind === 'louver') {
		return true
	}
	if (rA === 'gasket' || rB === 'gasket') {
		return true
	}
	if (
		(rA === 'bead' && (rB === 'sash' || rB === 'frame')) ||
		(rB === 'bead' && (rA === 'sash' || rA === 'frame'))
	) {
		return true
	}
	return false
}

/**
 * True only when two shapes' solid walls deeply penetrate each other (> DEEP_PENETRATION_MM).
 * Allows profiles to lock into concave grooves, T-slots, and rebates just like CAD.
 */
export function shapesCollide(a: PlacedShape, b: PlacedShape): boolean {
	if (canPiecesOverlap(a.piece, b.piece)) return false
	if (!bboxesOverlap(a.bbox, b.bbox, -0.2)) return false
	if (!a.rings.length || !b.rings.length) return false

	for (const ring of a.rings) {
		for (let i = 0; i < ring.length; i++) {
			const p1 = ring[i]
			const p2 = ring[(i + 1) % ring.length]
			const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 }
			if (pointInSolidEvenOdd(mid, b.rings) && minDistanceToRings(mid, b.rings) > DEEP_PENETRATION_MM) {
				return true
			}
		}
	}
	for (const ring of b.rings) {
		for (let i = 0; i < ring.length; i++) {
			const p1 = ring[i]
			const p2 = ring[(i + 1) % ring.length]
			const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 }
			if (pointInSolidEvenOdd(mid, a.rings) && minDistanceToRings(mid, a.rings) > DEEP_PENETRATION_MM) {
				return true
			}
		}
	}
	return false
}

/** Automatic placement has stricter semantics than interactive dragging: no
 * solid sash/frame/gasket or pane/rebate overlap is permitted at the start. */
function solidsOverlap(a: PlacedShape, b: PlacedShape): boolean {
	if (!bboxesOverlap(a.bbox, b.bbox, -0.02)) return false
	for (const [source, target] of [[a, b], [b, a]] as const) {
		for (const ring of source.rings) {
			for (let i = 0; i < ring.length; i++) {
				const p1 = ring[i]
				const p2 = ring[(i + 1) % ring.length]
				const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 }
				if (pointInSolidEvenOdd(mid, target.rings) && minDistanceToRings(mid, target.rings) > 0.05) return true
			}
		}
	}
	return false
}

function shapeDistance(a: PlacedShape, b: PlacedShape): number {
	let closest = Infinity
	for (const ring of a.rings) for (const point of ring) closest = Math.min(closest, minDistanceToRings(point, b.rings))
	for (const ring of b.rings) for (const point of ring) closest = Math.min(closest, minDistanceToRings(point, a.rings))
	return closest
}

/**
 * Resolve a dropped piece position with Magnetic Auto-Join so mating profile walls,
 * grooves, and glass faces lock flush with zero gap.
 */
export function resolvePuzzleDrop(
	movingIndex: number,
	piece: SectionPiece,
	baseStart: number,
	baseEnd: number,
	outline: SectionOutline | null,
	desired: SectionPieceTransform,
	obstacles: PlacedShape[],
	snapTolerance = SNAP_THRESHOLD_MM,
): { transform: SectionPieceTransform; snapped: boolean; resolvedCollision: boolean } {
	if (!isPieceMoveable(piece)) {
		return {
			transform: { ...desired, offsetAlong: 0 },
			snapped: false,
			resolvedCollision: false,
		}
	}

	const testAt = (along: number, depth: number) => {
		const cand: SectionPieceTransform = {
			...desired,
			offsetAlong: Math.round(along * 10) / 10,
			offsetDepth: Math.round(depth * 10) / 10,
		}
		const shape = buildPlacedShape(movingIndex, piece, baseStart, baseEnd, outline, cand)
		const collides = obstacles.some((obs) => obs.index !== movingIndex && shapesCollide(shape, obs))
		return { cand, shape, collides }
	}

	const initial = testAt(desired.offsetAlong, desired.offsetDepth)

	// 1. Apply magnetic auto-join to nearby vertical & horizontal profile/groove walls
	const mag = magneticAutoJoin(initial.shape, initial.cand, piece, obstacles, snapTolerance)
	if (mag) {
		const verifyMag = testAt(mag.offsetAlong, mag.offsetDepth)
		if (!verifyMag.collides) {
			return { transform: verifyMag.cand, snapped: true, resolvedCollision: false }
		}
	}

	if (!initial.collides) {
		return { transform: initial.cand, snapped: false, resolvedCollision: false }
	}

	// 2. If deeply overlapping solid metal, nudge by the smallest local step (<= 4 mm) so it stays in the groove
	const radii = [0.4, 0.8, 1.2, 1.6, 2.0, 2.5, 3.0, 4.0]
	const dirs = [
		[0, 1],
		[0, -1],
		[1, 0],
		[-1, 0],
		[0.707, 0.707],
		[-0.707, 0.707],
		[0.707, -0.707],
		[-0.707, -0.707],
	]
	for (const r of radii) {
		for (const [ux, uy] of dirs) {
			const res = testAt(desired.offsetAlong + ux * r, desired.offsetDepth + uy * r)
			if (!res.collides) {
				const postMag = magneticAutoJoin(res.shape, res.cand, piece, obstacles, snapTolerance)
				if (postMag) {
					const vPost = testAt(postMag.offsetAlong, postMag.offsetDepth)
					if (!vPost.collides) {
						return { transform: vPost.cand, snapped: true, resolvedCollision: true }
					}
				}
				return { transform: res.cand, snapped: true, resolvedCollision: true }
			}
		}
	}

	// 3. Push out to the nearest flush border of colliding obstacles so pieces don't clip
	const sign = piece.mirrored ? -1 : 1
	const collidingObs = obstacles.filter((obs) => obs.index !== movingIndex && shapesCollide(initial.shape, obs))
	const pushCandidates: { along: number; depth: number; dist: number }[] = []

	for (const obs of collidingObs) {
		const dxLeft = (obs.bbox.minX - initial.shape.bbox.maxX - 0.2) * sign
		const dxRight = (obs.bbox.maxX - initial.shape.bbox.minX + 0.2) * sign
		const dyTop = obs.bbox.minY - initial.shape.bbox.maxY - 0.2
		const dyBottom = obs.bbox.maxY - initial.shape.bbox.minY + 0.2

		for (const dx of [dxLeft, dxRight]) {
			pushCandidates.push({
				along: desired.offsetAlong + dx,
				depth: desired.offsetDepth,
				dist: Math.abs(dx),
			})
		}
		for (const dy of [dyTop, dyBottom]) {
			pushCandidates.push({
				along: desired.offsetAlong,
				depth: desired.offsetDepth + dy,
				dist: Math.abs(dy),
			})
		}
	}

	pushCandidates.sort((a, b) => a.dist - b.dist)
	for (const cand of pushCandidates) {
		const res = testAt(cand.along, cand.depth)
		if (!res.collides) {
			const postMag = magneticAutoJoin(res.shape, res.cand, piece, obstacles, snapTolerance)
			if (postMag) {
				const vPost = testAt(postMag.offsetAlong, postMag.offsetDepth)
				if (!vPost.collides) {
					return { transform: vPost.cand, snapped: true, resolvedCollision: true }
				}
			}
			return { transform: res.cand, snapped: true, resolvedCollision: true }
		}
	}

	// 4. Fallback: revert to zero offset to prevent clipping
	const fallback = testAt(0, 0)
	return { transform: fallback.cand, snapped: true, resolvedCollision: true }
}

interface WallFaces {
	vFaces: { x: number; minY: number; maxY: number }[]
	hFaces: { y: number; minX: number; maxX: number }[]
}

export function extractWallFaces(shape: PlacedShape): WallFaces {
	// Only actual outline segments are mating surfaces. Bounding boxes can
	// pass through empty cavities and must not attract a profile.
	const vFaces: WallFaces['vFaces'] = []
	const hFaces: WallFaces['hFaces'] = []
	for (const ring of shape.rings) {
		for (let i = 0; i < ring.length; i++) {
			const a = ring[i]
			const b = ring[(i + 1) % ring.length]
			const dx = Math.abs(b.x - a.x)
			const dy = Math.abs(b.y - a.y)
			if (dx < 0.25 && dy >= 1.8) {
				vFaces.push({
					x: (a.x + b.x) / 2,
					minY: Math.min(a.y, b.y),
					maxY: Math.max(a.y, b.y),
				})
			} else if (dy < 0.25 && dx >= 1.8) {
				hFaces.push({
					y: (a.y + b.y) / 2,
					minX: Math.min(a.x, b.x),
					maxX: Math.max(a.x, b.x),
				})
			}
		}
	}
	return { vFaces, hFaces }
}

/**
 * Magnetic Auto-Join: snaps any vertical or horizontal wall/hook/rebate edge of `shape`
 * to the nearest mating wall/groove edge of `obstacles` within `SNAP_THRESHOLD_MM` so there is zero gap.
 */
export function magneticAutoJoin(
	shape: PlacedShape,
	cand: SectionPieceTransform,
	piece: SectionPiece,
	obstacles: PlacedShape[],
	tolerance = SNAP_THRESHOLD_MM,
): SectionPieceTransform | null {
	void piece
	const myWalls = extractWallFaces(shape)
	let bestDx = 0
	let bestDy = 0
	let minDistX = tolerance
	let minDistY = tolerance

	for (const obs of obstacles) {
		if (obs.index === shape.index) continue
		if (!bboxesOverlap(shape.bbox, obs.bbox, tolerance + 0.1)) continue
		const obsWalls = extractWallFaces(obs)

		for (const mv of myWalls.vFaces) {
			for (const ov of obsWalls.vFaces) {
				// Require vertical proximity/overlap to snap X faces together
				if (mv.maxY >= ov.minY + 0.05 && mv.minY <= ov.maxY - 0.05) {
					const diff = ov.x - mv.x
					if (Math.abs(diff) < minDistX) {
						minDistX = Math.abs(diff)
						bestDx = diff
					}
				}
			}
		}

		for (const mh of myWalls.hFaces) {
			for (const oh of obsWalls.hFaces) {
				// Require horizontal proximity/overlap to snap Y faces together
				if (mh.maxX >= oh.minX + 0.05 && mh.minX <= oh.maxX - 0.05) {
					const diff = oh.y - mh.y
					if (Math.abs(diff) < minDistY) {
						minDistY = Math.abs(diff)
						bestDy = diff
					}
				}
			}
		}
	}

	if (minDistX >= tolerance && minDistY >= tolerance) return null
	return {
		...cand,
		offsetAlong: Math.round((cand.offsetAlong + bestDx) * 10) / 10,
		offsetDepth: Math.round((cand.offsetDepth + bestDy) * 10) / 10,
	}
}

/** Guides through the actual wall segments that are flush after snapping. */
export function profileContactGuides(shape: PlacedShape, obstacles: PlacedShape[]) {
	const lines: { axis: 'x' | 'y'; pos: number; start: number; end: number; type: 'edge' }[] = []
	const mine = extractWallFaces(shape)
	for (const obstacle of obstacles) {
		if (!bboxesOverlap(shape.bbox, obstacle.bbox, 0.1)) continue
		const walls = extractWallFaces(obstacle)
		for (const a of mine.vFaces) for (const b of walls.vFaces) {
			if (Math.abs(a.x - b.x) <= 0.08 && Math.min(a.maxY, b.maxY) > Math.max(a.minY, b.minY) &&
				!lines.some(line => line.axis === 'x' && Math.abs(line.pos - b.x) < 0.08)) {
				lines.push({ axis: 'x', pos: b.x, start: Math.min(a.minY, b.minY) - 2, end: Math.max(a.maxY, b.maxY) + 2, type: 'edge' })
			}
		}
		for (const a of mine.hFaces) for (const b of walls.hFaces) {
			if (Math.abs(a.y - b.y) <= 0.08 && Math.min(a.maxX, b.maxX) > Math.max(a.minX, b.minX) &&
				!lines.some(line => line.axis === 'y' && Math.abs(line.pos - b.y) < 0.08)) {
				lines.push({ axis: 'y', pos: b.y, start: Math.min(a.minX, b.minX) - 2, end: Math.max(a.maxX, b.maxX) + 2, type: 'edge' })
			}
		}
	}
	return lines.slice(0, 8)
}

function rectRing(x: number, y: number, w: number, h: number): Point[] {
	return [
		{ x, y },
		{ x: x + w, y },
		{ x: x + w, y: y + h },
		{ x, y: y + h },
	]
}

export function computeBBox(rings: Point[][]): BBox {
	let minX = Infinity
	let minY = Infinity
	let maxX = -Infinity
	let maxY = -Infinity
	for (const r of rings) {
		for (const p of r) {
			if (p.x < minX) minX = p.x
			if (p.y < minY) minY = p.y
			if (p.x > maxX) maxX = p.x
			if (p.y > maxY) maxY = p.y
		}
	}
	if (!Number.isFinite(minX)) return { minX: 0, minY: 0, maxX: 0, maxY: 0, width: 0, height: 0 }
	return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY }
}

function bboxesOverlap(a: BBox, b: BBox, pad = 0): boolean {
	return a.maxX + pad > b.minX && a.minX - pad < b.maxX && a.maxY + pad > b.minY && a.minY - pad < b.maxY
}

function pointInRing(pt: Point, ring: Point[]): boolean {
	let inside = false
	for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
		const xi = ring[i].x
		const yi = ring[i].y
		const xj = ring[j].x
		const yj = ring[j].y
		const intersect = yi > pt.y !== yj > pt.y && pt.x < ((xj - xi) * (pt.y - yi)) / (yj - yi + 1e-12) + xi
		if (intersect) inside = !inside
	}
	return inside
}

/** True when `pt` is inside the solid region of an Even-Odd (`fill-rule="evenodd"`) multi-ring path. */
function pointInSolidEvenOdd(pt: Point, rings: Point[][]): boolean {
	let inside = false
	for (const ring of rings) {
		if (pointInRing(pt, ring)) inside = !inside
	}
	return inside
}

function distToSegment(p: Point, a: Point, b: Point): number {
	const dx = b.x - a.x
	const dy = b.y - a.y
	const lenSq = dx * dx + dy * dy
	if (lenSq < 1e-9) return Math.hypot(p.x - a.x, p.y - a.y)
	const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq))
	return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
}

function minDistanceToRings(pt: Point, rings: Point[][]): number {
	let minD = Infinity
	for (const ring of rings) {
		for (let i = 0; i < ring.length; i++) {
			const d = distToSegment(pt, ring[i], ring[(i + 1) % ring.length])
			if (d < minD) minD = d
		}
	}
	return minD
}
