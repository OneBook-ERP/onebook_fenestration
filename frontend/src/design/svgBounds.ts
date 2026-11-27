const PATH_TOKEN_RE = /[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?/g

/**
 * Compute a centered SVG viewBox that frames a `<path d="...">` tightly by its actual bounds.
 */
export function svgPathViewBox(
	d?: string | null,
	fallbackW?: number | null,
	fallbackD?: number | null,
): string {
	const bounds = d ? measurePathBounds(d) : null
	if (bounds) {
		const bw = Math.max(bounds.maxX - bounds.minX, 1)
		const bh = Math.max(bounds.maxY - bounds.minY, 1)
		const pad = Math.max(bw, bh) * 0.14
		return `${round2(bounds.minX - pad)} ${round2(bounds.minY - pad)} ${round2(bw + pad * 2)} ${round2(bh + pad * 2)}`
	}
	const w = Number(fallbackW) || 0
	const h = Number(fallbackD) || 0
	if (w > 0 && h > 0) {
		const pad = Math.max(w, h) * 0.14
		return `${round2(-pad)} ${round2(-pad)} ${round2(w + pad * 2)} ${round2(h + pad * 2)}`
	}
	return '-5 -5 80 80'
}

export interface ProfileBoundsInput {
	svg?: string | null
	section_svg?: string | null
	width_mm?: number | null
	depth_mm?: number | null
	section_rotation?: string | number | null
	section_flip_x?: number | boolean | null
	section_flip_y?: number | boolean | null
	outline_transformed?: boolean | null
}

/**
 * Compute a centered SVG viewBox matching the profile's default rotation and flips
 * when rendering `<g :transform="profileThumbTransform(p)">` around `<path :d="svg">`.
 */
export function transformedPathViewBox(p: ProfileBoundsInput): string {
	const d = p.svg ?? p.section_svg
	if (p.outline_transformed) {
		return svgPathViewBox(d, p.width_mm, p.depth_mm)
	}
	const rot = (((Number(p.section_rotation || 0) % 360) + 360) % 360)
	const fx = Boolean(Number(p.section_flip_x || 0))
	const fy = Boolean(Number(p.section_flip_y || 0))
	if (!rot && !fx && !fy) {
		return svgPathViewBox(d, p.width_mm, p.depth_mm)
	}
	const bounds = d ? measurePathBounds(d) : null
	const isTurned = rot === 90 || rot === 270
	const w0 = Math.max(Number(isTurned ? p.depth_mm : p.width_mm) || 10, 1)
	const h0 = Math.max(Number(isTurned ? p.width_mm : p.depth_mm) || 10, 1)
	if (!bounds) {
		const outW = isTurned ? h0 : w0
		const outH = isTurned ? w0 : h0
		const pad = Math.max(outW, outH) * 0.14
		return `${round2(-pad)} ${round2(-pad)} ${round2(outW + pad * 2)} ${round2(outH + pad * 2)}`
	}
	const transformPt = (x: number, y: number): [number, number] => {
		const px = fx ? w0 - x : x
		const py = fy ? h0 - y : y
		if (rot === 90) return [h0 - py, px]
		if (rot === 180) return [w0 - px, h0 - py]
		if (rot === 270) return [py, w0 - px]
		return [px, py]
	}
	const pts = [
		transformPt(bounds.minX, bounds.minY),
		transformPt(bounds.maxX, bounds.minY),
		transformPt(bounds.minX, bounds.maxY),
		transformPt(bounds.maxX, bounds.maxY),
	]
	const xs = pts.map(([x]) => x)
	const ys = pts.map(([, y]) => y)
	const minX = Math.min(...xs)
	const maxX = Math.max(...xs)
	const minY = Math.min(...ys)
	const maxY = Math.max(...ys)
	const bw = Math.max(maxX - minX, 1)
	const bh = Math.max(maxY - minY, 1)
	const pad = Math.max(bw, bh) * 0.14
	return `${round2(minX - pad)} ${round2(minY - pad)} ${round2(bw + pad * 2)} ${round2(bh + pad * 2)}`
}

function round2(n: number): number {
	return Math.round(n * 100) / 100
}

function measurePathBounds(d: string): { minX: number; minY: number; maxX: number; maxY: number } | null {
	const tokens = d.match(PATH_TOKEN_RE)
	if (!tokens?.length) return null

	let minX = Infinity
	let minY = Infinity
	let maxX = -Infinity
	let maxY = -Infinity
	const push = (x: number, y: number) => {
		if (!Number.isFinite(x) || !Number.isFinite(y)) return
		if (x < minX) minX = x
		if (x > maxX) maxX = x
		if (y < minY) minY = y
		if (y > maxY) maxY = y
	}

	let i = 0
	let cmd = ''
	let cx = 0
	let cy = 0
	let sx = 0
	let sy = 0

	const nextNum = (): number | null => {
		if (i >= tokens.length || /^[A-Za-z]$/.test(tokens[i])) return null
		const v = Number(tokens[i++])
		return Number.isFinite(v) ? v : null
	}

	while (i < tokens.length) {
		if (/^[A-Za-z]$/.test(tokens[i])) {
			cmd = tokens[i++]
			if (cmd === 'Z' || cmd === 'z') {
				cx = sx
				cy = sy
				continue
			}
		} else if (!cmd) {
			break
		}

		const rel = cmd === cmd.toLowerCase()
		const upper = cmd.toUpperCase()

		if (upper === 'H') {
			const v = nextNum()
			if (v === null) break
			cx = rel ? cx + v : v
			push(cx, cy)
			continue
		}
		if (upper === 'V') {
			const v = nextNum()
			if (v === null) break
			cy = rel ? cy + v : v
			push(cx, cy)
			continue
		}
		if (upper === 'M' || upper === 'L' || upper === 'T') {
			const x = nextNum()
			const y = nextNum()
			if (x === null || y === null) break
			cx = rel ? cx + x : x
			cy = rel ? cy + y : y
			push(cx, cy)
			if (upper === 'M') {
				sx = cx
				sy = cy
				cmd = rel ? 'l' : 'L'
			}
			continue
		}
		if (upper === 'C') {
			const x1 = nextNum()
			const y1 = nextNum()
			const x2 = nextNum()
			const y2 = nextNum()
			const x = nextNum()
			const y = nextNum()
			if (x1 === null || y1 === null || x2 === null || y2 === null || x === null || y === null) break
			const ox = rel ? cx : 0
			const oy = rel ? cy : 0
			push(ox + x1, oy + y1)
			push(ox + x2, oy + y2)
			cx = ox + x
			cy = oy + y
			push(cx, cy)
			continue
		}
		if (upper === 'S' || upper === 'Q') {
			const x1 = nextNum()
			const y1 = nextNum()
			const x = nextNum()
			const y = nextNum()
			if (x1 === null || y1 === null || x === null || y === null) break
			const ox = rel ? cx : 0
			const oy = rel ? cy : 0
			push(ox + x1, oy + y1)
			cx = ox + x
			cy = oy + y
			push(cx, cy)
			continue
		}
		if (upper === 'A') {
			const rx = nextNum()
			const ry = nextNum()
			const rot = nextNum()
			const large = nextNum()
			const sweep = nextNum()
			const x = nextNum()
			const y = nextNum()
			if (rx === null || ry === null || rot === null || large === null || sweep === null || x === null || y === null) break
			cx = rel ? cx + x : x
			cy = rel ? cy + y : y
			push(cx, cy)
			continue
		}
		break
	}

	return Number.isFinite(minX) ? { minX, minY, maxX, maxY } : null
}

