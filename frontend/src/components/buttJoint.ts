/** A mating profile expressed along the joining member's length and wall depth. */
export interface ButtSeat {
	contour: { x: number; y: number }[] // x = section depth, y = profile face coordinate
	depthOffset: number
	origin: number
	direction: number
}

/** Near surface of the mating outer contour. Holes are deliberately excluded. */
export function seatAtDepth(seat: ButtSeat, worldDepth: number, start: boolean): number | null {
	const depth = worldDepth - seat.depthOffset
	const hits: number[] = []
	for (let i = 0; i < seat.contour.length; i++) {
		const a = seat.contour[i], b = seat.contour[(i + 1) % seat.contour.length]
		if (depth < Math.min(a.x, b.x) - 1e-7 || depth > Math.max(a.x, b.x) + 1e-7) continue
		if (Math.abs(b.x - a.x) < 1e-7) {
			hits.push(a.y, b.y)
		} else {
			hits.push(a.y + (b.y - a.y) * (depth - a.x) / (b.x - a.x))
		}
	}
	if (!hits.length) return null
	const positions = hits.map((u) => seat.origin + seat.direction * u)
	return start ? Math.max(...positions) : Math.min(...positions)
}

/** Keep rebate steps in the joining extrusion's side walls when its cap is coped. */
export function splitAtSeatDepths<T extends { x: number; y: number }>(
	loops: T[][], depthOffset: number, seats: (ButtSeat | undefined)[],
): { x: number; y: number }[][] {
	const depths = [...new Set(seats.flatMap((s) => s ? s.contour.flatMap((p) => {
		const d = p.x + s.depthOffset - depthOffset
		return [d - 0.0001, d, d + 0.0001]
	}) : []))].sort((a, b) => a - b)
	return loops.map((loop) => loop.flatMap((a, i) => {
		const b = loop[(i + 1) % loop.length]
		const cuts = depths.filter((x) => x > Math.min(a.x, b.x) + 1e-8 && x < Math.max(a.x, b.x) - 1e-8)
		if (a.x > b.x) cuts.reverse()
		return [a, ...cuts.map((x) => ({ x, y: a.y + (b.y - a.y) * (x - a.x) / (b.x - a.x) }))]
	}))
}
