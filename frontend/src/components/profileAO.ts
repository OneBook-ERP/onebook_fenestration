/**
 * Cheap, exact ambient occlusion for extruded profile sections.
 *
 * A window profile is a 2D cross-section pulled along its length, so the dark
 * crevices (rebates, grooves, bead seats, chamber walls) can be found with a 2D
 * test on the section instead of a screen-space post effect. For a surface point
 * on the section outline we fan rays out over the half-plane in front of it and
 * measure how soon they hit the outline again. Close hits = tight crevice = dark.
 *
 * Pure functions: no three.js, no DOM. Section coordinates are whatever the caller
 * uses (the 3D view uses x = depth, y = distance from the outer edge), in mm.
 */

export interface Pt {
	x: number
	y: number
}

export interface AOOptions {
	/** Rays in the fan. More = smoother, slower. */
	rays?: number
	/** Occluders further than this (mm) are ignored. Roughly the size of the crevices you care about. */
	maxDist?: number
	/** 0..1. How dark the tightest crevice gets (0.8 -> down to 20 % brightness). */
	strength?: number
	/** Distance falloff exponent. 1 = linear. */
	falloff?: number
	/** Total fan angle in degrees, centred on the surface normal. */
	spreadDeg?: number
	/** Start rays this far (mm) off the surface so they do not hit their own wall. */
	lift?: number
}

/** Returns a brightness multiplier in [1 - strength, 1] (1 = fully open) for a point and its outward 2D normal. */
export type SectionAO = (px: number, py: number, nx: number, ny: number) => number

export function createSectionAO(loops: Pt[][], opts: AOOptions = {}): SectionAO {
	const rays = Math.max(4, Math.round(opts.rays ?? 16))
	const maxDist = opts.maxDist ?? 14
	const strength = Math.min(1, Math.max(0, opts.strength ?? 0.8))
	const falloff = opts.falloff ?? 1
	const spread = ((opts.spreadDeg ?? 170) * Math.PI) / 180
	const lift = opts.lift ?? 0.05

	// Flatten every loop edge to [ax, ay, ex, ey] (start + edge vector).
	const edges: number[] = []
	for (const loop of loops) {
		for (let i = 0; i < loop.length; i++) {
			const a = loop[i]
			const b = loop[(i + 1) % loop.length]
			if (a.x === b.x && a.y === b.y) continue
			edges.push(a.x, a.y, b.x - a.x, b.y - a.y)
		}
	}
	const E = new Float64Array(edges)

	// Fan directions relative to the normal, with cosine weights (grazing rays count less).
	const offsets = new Float64Array(rays)
	const weights = new Float64Array(rays)
	let weightSum = 0
	for (let k = 0; k < rays; k++) {
		const a = ((k + 0.5) / rays - 0.5) * spread
		offsets[k] = a
		weights[k] = Math.cos(a)
		weightSum += weights[k]
	}

	const memo = new Map<string, number>()

	return (px, py, nx, ny) => {
		const len = Math.hypot(nx, ny)
		if (len < 1e-6 || E.length === 0) return 1
		const ux = nx / len
		const uy = ny / len

		// 0.02 mm / 0.05 rounding: the same section vertex shows up on many triangles.
		const key = `${Math.round(px * 50)}|${Math.round(py * 50)}|${Math.round(ux * 20)}|${Math.round(uy * 20)}`
		const cached = memo.get(key)
		if (cached !== undefined) return cached

		const ox = px + ux * lift
		const oy = py + uy * lift
		const base = Math.atan2(uy, ux)

		let occ = 0
		for (let k = 0; k < rays; k++) {
			const ang = base + offsets[k]
			const dx = Math.cos(ang)
			const dy = Math.sin(ang)
			let nearest = maxDist
			for (let e = 0; e < E.length; e += 4) {
				const ex = E[e + 2]
				const ey = E[e + 3]
				const denom = dx * ey - dy * ex
				if (Math.abs(denom) < 1e-12) continue
				const wx = E[e] - ox
				const wy = E[e + 1] - oy
				const t = (wx * ey - wy * ex) / denom
				if (t <= 1e-6 || t >= nearest) continue
				const s = (wx * dy - wy * dx) / denom
				if (s < 0 || s > 1) continue
				nearest = t
			}
			if (nearest < maxDist) occ += weights[k] * Math.pow(1 - nearest / maxDist, falloff)
		}

		const result = 1 - strength * (occ / weightSum)
		memo.set(key, result)
		return result
	}
}

