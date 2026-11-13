export const LOUVER_ANGLE = 32 * Math.PI / 180
export const LOUVER_THICKNESS = 4
export const LOUVER_DEPTH = 20
export const DEFAULT_LOUVER_WIDTH = 60

export function louverLayout(height: number, blades: number, width = DEFAULT_LOUVER_WIDTH) {
	const count = Math.max(1, Math.round(blades || 7))
	const pitch = height / count
	return { count, pitch, chord: Number.isFinite(width) && width > 0 ? width : DEFAULT_LOUVER_WIDTH, centres: Array.from({ length: count }, (_, i) => (i + 0.5) * pitch) }
}

/** Section coordinates: x along the cut, y into the window depth. */
export function louverSectionRings(axis: 'h' | 'v', start: number, end: number, height: number, blades: number, width = DEFAULT_LOUVER_WIDTH, thickness = LOUVER_THICKNESS) {
	const layout = louverLayout(height, blades, width)
	const sin = Math.sin(LOUVER_ANGLE), cos = Math.cos(LOUVER_ANGLE)
	const halfDepth = (layout.chord * sin + thickness * cos) / 2
	if (axis === 'h') {
		// Plan indication of the blade bank, including cuts through the air gaps.
		return [[{ x: start, y: LOUVER_DEPTH - halfDepth }, { x: end, y: LOUVER_DEPTH - halfDepth },
			{ x: end, y: LOUVER_DEPTH + halfDepth }, { x: start, y: LOUVER_DEPTH + halfDepth }]]
	}
	const scale = (end - start) / height
	return layout.centres.map((centre) => [
		[-layout.chord / 2, -thickness / 2], [layout.chord / 2, -thickness / 2],
		[layout.chord / 2, thickness / 2], [-layout.chord / 2, thickness / 2],
	].map(([along, normal]) => ({
		x: start + centre * scale + along * cos - normal * sin,
		y: LOUVER_DEPTH - along * sin - normal * cos,
	})))
}
