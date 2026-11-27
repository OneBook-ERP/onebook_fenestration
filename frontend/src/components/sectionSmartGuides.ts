/**
 * Figma-style smart guides for the cross-section puzzle editor.
 *
 * Pure functions: no DOM, no Vue. The canvas feeds in the dragged rectangle plus
 * every other rectangle (and optional "datum" lines such as the window centre or
 * the walls) and gets back:
 *
 *   - `deltaX` / `deltaY`: how far to nudge the drag so it snaps
 *   - `lines`: alignment guides (edge = solid, centre = dashed) at the snapped position
 *   - `gaps`: distance markers to the nearest neighbour on each side, with
 *     `equal: true` when the gap matches the opposite gap or a gap elsewhere
 *
 * Snapping and reporting are separate on purpose:
 *   - `computeSmartGuides` = snap, then report.
 *   - `measureGuides`      = report only. Use it after something else has already
 *     moved the piece (e.g. magnetic auto-join) or while snapping is switched off,
 *     so the user still sees what the piece lines up with.
 *
 * Both X and Y are handled by the same code: the Y pass runs the X logic on
 * transposed rectangles.
 */

export type GuideKind = 'edge' | 'center'
export type GuideAxis = 'x' | 'y'

export interface Rect {
	id: string
	x: number // minX
	y: number // minY
	w: number // width
	h: number // height
	/**
	 * Marks a guide-only datum (window centre line, glass plane, wall). A datum
	 * contributes alignment lines only along the axis where its size is 0
	 * (w = 0 -> vertical line at x, h = 0 -> horizontal line at y) and is never
	 * used as a neighbour for distance or spacing.
	 */
	guide?: GuideKind
}

export interface GuideLine {
	/** 'x' = vertical line at x = pos, spanning y start..end. 'y' = horizontal line at y = pos. */
	axis: GuideAxis
	pos: number
	start: number
	end: number
	type: GuideKind
}

export interface GapMarker {
	/** 'x' = horizontal marker measuring along x at y = perpPos. 'y' = vertical marker at x = perpPos. */
	axis: GuideAxis
	start: number
	end: number
	perpPos: number
	gap: number
	/** Same size as the opposite gap or as another gap in the layout. */
	equal: boolean
}

export interface SmartGuideResult {
	deltaX: number
	deltaY: number
	lines: GuideLine[]
	gaps: GapMarker[]
}

export interface SmartGuideOptions {
	scaleMmPerPixel: number
	tolerancePx?: number
	disabled?: boolean
}

/**
 * Two positions count as "aligned" when they differ by less than this. Piece
 * offsets are stored rounded to 0.1 mm, so a snap can land up to 0.05 mm away
 * from the exact target; this must stay above that.
 */
const ALIGN_EPS_MM = 0.08
/** Gaps smaller than this are treated as flush (no marker, no snapping). */
const MIN_GAP_MM = 0.5
/** Snap zone is always tolerancePx on screen; this only stops it collapsing to 0. */
const MIN_TOL_MM = 0.01
const LINE_PAD_MM = 6
const MAX_LINES_PER_AXIS = 4
const MAX_EQUAL_MARKERS = 6

const r1 = (n: number) => Math.round(n * 10) / 10 + 0 // `+ 0` turns -0 into 0
const r2 = (n: number) => Math.round(n * 100) / 100 + 0

const transpose = (r: Rect): Rect => ({ ...r, x: r.y, y: r.x, w: r.h, h: r.w })
const overlap = (a0: number, aLen: number, b0: number, bLen: number) => Math.min(a0 + aLen, b0 + bLen) - Math.max(a0, b0)

interface Line {
	pos: number
	kind: GuideKind
}

/** Candidate alignment lines of a rect along x: left, centre, right (or the single datum line). */
function linesOf(r: Rect): Line[] {
	if (r.guide) return r.w === 0 ? [{ pos: r.x, kind: r.guide }] : []
	return [
		{ pos: r.x, kind: 'edge' },
		{ pos: r.x + r.w / 2, kind: 'center' },
		{ pos: r.x + r.w, kind: 'edge' },
	]
}

function smallest(candidates: number[], tol: number): number | null {
	let best: number | null = null
	for (const c of candidates) {
		if (Math.abs(c) <= tol && (best === null || Math.abs(c) < Math.abs(best))) best = c
	}
	return best
}

/** Alignment snap along x: smallest shift (within tol) that lines one of our 3 lines up with any target line. */
function snapAlign(moving: Rect, targets: Rect[], tol: number): number | null {
	const mine = linesOf(moving)
	const candidates: number[] = []
	for (const t of targets) {
		for (const tl of linesOf(t)) {
			for (const ml of mine) candidates.push(tl.pos - ml.pos)
		}
	}
	return smallest(candidates, tol)
}

/** Nearest items to the left and right that share some vertical extent with `moving`. */
function nearestNeighbours(moving: Rect, items: Rect[]): { left?: Rect; right?: Rect } {
	let left: Rect | undefined
	let right: Rect | undefined
	for (const o of items) {
		if (overlap(moving.y, moving.h, o.y, o.h) <= ALIGN_EPS_MM) continue
		if (o.x + o.w <= moving.x + ALIGN_EPS_MM) {
			if (!left || o.x + o.w > left.x + left.w) left = o
		} else if (o.x >= moving.x + moving.w - ALIGN_EPS_MM) {
			if (!right || o.x < right.x) right = o
		}
	}
	return { left, right }
}

interface GapSpan {
	start: number
	end: number
	perp: number
	gap: number
}

/** Every visible gap between two items already in the layout (nothing sitting between them). */
function layoutGaps(items: Rect[]): GapSpan[] {
	const out: GapSpan[] = []
	for (const a of items) {
		for (const b of items) {
			if (a === b) continue
			const aEnd = a.x + a.w
			const gap = b.x - aEnd
			if (gap < MIN_GAP_MM) continue
			const span = overlap(a.y, a.h, b.y, b.h)
			if (span <= ALIGN_EPS_MM) continue
			const lo = Math.max(a.y, b.y)
			const blocked = items.some(
				(c) =>
					c !== a &&
					c !== b &&
					c.x >= aEnd - ALIGN_EPS_MM &&
					c.x + c.w <= b.x + ALIGN_EPS_MM &&
					overlap(c.y, c.h, lo, span) > ALIGN_EPS_MM,
			)
			if (blocked) continue
			out.push({ start: aEnd, end: b.x, perp: lo + span / 2, gap })
		}
	}
	return out
}

/**
 * Spacing snap along x. Candidates:
 *   1. centre between the two neighbours (left gap == right gap)
 *   2. make either gap equal to a gap that already exists elsewhere in the layout
 * Disabled when the moving item overlaps something in x (it is not "between" anything then).
 */
function snapSpacing(moving: Rect, items: Rect[], tol: number): number | null {
	const band = items.filter((o) => overlap(moving.y, moving.h, o.y, o.h) > ALIGN_EPS_MM)
	if (band.some((o) => overlap(moving.x, moving.w, o.x, o.w) > ALIGN_EPS_MM)) return null

	const { left, right } = nearestNeighbours(moving, band)
	const lg = left ? moving.x - (left.x + left.w) : 0
	const rg = right ? right.x - (moving.x + moving.w) : 0
	const hasL = lg >= MIN_GAP_MM
	const hasR = rg >= MIN_GAP_MM

	const candidates: number[] = []
	if (hasL && hasR) candidates.push((rg - lg) / 2)
	for (const k of layoutGaps(items)) {
		if (hasL) candidates.push(k.gap - lg)
		if (hasR) candidates.push(rg - k.gap)
	}
	return smallest(candidates, tol)
}

/** Shift along x: spacing and alignment compete, the smaller move wins (spacing on a tie). */
function snapPrimary(moving: Rect, targets: Rect[], items: Rect[], tol: number): number {
	const align = snapAlign(moving, targets, tol)
	const spacing = snapSpacing(moving, items, tol)
	if (align === null) return spacing ?? 0
	if (spacing === null) return align
	return Math.abs(spacing) <= Math.abs(align) ? spacing : align
}

/** Guide lines where one of our x-lines coincides with a target line. Centre guides sort first. */
function matchLines(moving: Rect, targets: Rect[], axis: GuideAxis): GuideLine[] {
	const mine = linesOf(moving)
	const found: GuideLine[] = []
	for (const t of targets) {
		const start = Math.min(moving.y, t.y) - LINE_PAD_MM
		const end = Math.max(moving.y + moving.h, t.y + t.h) + LINE_PAD_MM
		for (const tl of linesOf(t)) {
			for (const ml of mine) {
				if (Math.abs(tl.pos - ml.pos) > ALIGN_EPS_MM) continue
				const type: GuideKind = ml.kind === 'center' || tl.kind === 'center' ? 'center' : 'edge'
				const hit = found.find((f) => Math.abs(f.pos - tl.pos) <= ALIGN_EPS_MM)
				if (hit) {
					hit.start = Math.min(hit.start, start)
					hit.end = Math.max(hit.end, end)
					if (type === 'center') hit.type = 'center'
				} else {
					found.push({ axis, pos: tl.pos, start, end, type })
				}
			}
		}
	}
	found.sort((a, b) => Number(b.type === 'center') - Number(a.type === 'center'))
	return found
		.slice(0, MAX_LINES_PER_AXIS)
		.map((l) => ({ ...l, pos: r2(l.pos), start: r2(l.start), end: r2(l.end) }))
}

const sameMarker = (a: GapMarker, b: GapMarker) =>
	Math.abs(a.start - b.start) < 0.01 && Math.abs(a.end - b.end) < 0.01 && Math.abs(a.perpPos - b.perpPos) < 0.01

/** Distance markers to the nearest neighbour on each side, plus twins of any equal gap elsewhere. */
function measureGaps(moving: Rect, items: Rect[], axis: GuideAxis): GapMarker[] {
	const { left, right } = nearestNeighbours(moving, items)
	const markers: GapMarker[] = []
	const add = (start: number, end: number, other: Rect) => {
		const gap = end - start
		if (gap < MIN_GAP_MM) return
		const span = overlap(moving.y, moving.h, other.y, other.h)
		const lo = Math.max(moving.y, other.y)
		markers.push({ axis, start: r2(start), end: r2(end), perpPos: r2(lo + span / 2), gap: r1(gap), equal: false })
	}
	if (left) add(left.x + left.w, moving.x, left)
	if (right) add(moving.x + moving.w, right.x, right)
	if (!markers.length) return markers

	const known = layoutGaps(items)
	const extra: GapMarker[] = []
	for (const m of markers) {
		const twins = known.filter((k) => Math.abs(k.gap - m.gap) <= ALIGN_EPS_MM)
		if (twins.length || markers.some((o) => o !== m && Math.abs(o.gap - m.gap) <= ALIGN_EPS_MM)) m.equal = true
		for (const k of twins) {
			if (extra.length >= MAX_EQUAL_MARKERS) break
			const twin: GapMarker = {
				axis,
				start: r2(k.start),
				end: r2(k.end),
				perpPos: r2(k.perp),
				gap: r1(k.gap),
				equal: true,
			}
			if (![...markers, ...extra].some((o) => sameMarker(o, twin))) extra.push(twin)
		}
	}
	return [...markers, ...extra]
}

function measureAxis(moving: Rect, targets: Rect[], items: Rect[], axis: GuideAxis) {
	return { lines: matchLines(moving, targets, axis), gaps: measureGaps(moving, items, axis) }
}

/**
 * Report only: alignment guides and distance markers for `rect` exactly where it is.
 * No snapping, no deltas. Use it after another system has moved the piece, or while
 * snapping is switched off (Alt / Ctrl) so the user can still read distances.
 */
export function measureGuides(rect: Rect, targets: Rect[]): SmartGuideResult {
	const items = targets.filter((t) => !t.guide)
	const x = measureAxis(rect, targets, items, 'x')
	const y = measureAxis(transpose(rect), targets.map(transpose), items.map(transpose), 'y')
	return { deltaX: 0, deltaY: 0, lines: [...x.lines, ...y.lines], gaps: [...x.gaps, ...y.gaps] }
}

/** Snap the dragged rect to the targets, then report guides and distances at the snapped position. */
export function computeSmartGuides(moving: Rect, targets: Rect[], options: SmartGuideOptions): SmartGuideResult {
	if (options.disabled || targets.length === 0) {
		return { deltaX: 0, deltaY: 0, lines: [], gaps: [] }
	}

	const tol = Math.max(MIN_TOL_MM, (options.tolerancePx ?? 6) * options.scaleMmPerPixel)
	const items = targets.filter((t) => !t.guide)

	// X first, then Y on the X-snapped rect (vertical neighbours depend on the x position).
	const dx = snapPrimary(moving, targets, items, tol)
	const shifted: Rect = { ...moving, x: moving.x + dx }
	const dy = snapPrimary(transpose(shifted), targets.map(transpose), items.map(transpose), tol)
	const snapped: Rect = { ...shifted, y: shifted.y + dy }

	const { lines, gaps } = measureGuides(snapped, targets)
	return { deltaX: r2(dx), deltaY: r2(dy), lines, gaps }
}
