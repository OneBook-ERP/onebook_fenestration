import type { FenestrationProfileRow } from './api'

export interface CardSvgMetrics {
	cw: number
	ch: number
	ox: number
	oy: number
	s: number
	dw: number
	dh: number
	dimX: number
	dimY: number
	tick: number
	vTextX: number
	vTextY: number
	pathStroke: number
	fontSize: number
	widthLabel: string
	depthLabel: string
}

export interface BlueprintSvgMetrics extends CardSvgMetrics {
	minorPx: number
	majorPx: number
	cx: number
	cy: number
	loops: number
	chambers: number
}

export function effectiveWeight(p: FenestrationProfileRow): number {
	if (p.use_computed_weight && p.computed_kg_per_m) {
		return Number(p.computed_kg_per_m)
	}
	return Number(p.kg_per_m || 0)
}

export function cleanDxfFilename(dxfPath?: string | null): string {
	const raw = (dxfPath || '').split('/').pop() || 'section.dxf'
	return raw.replace(/([0-9a-f]{6}){1,2}(\.dxf)$/i, '$2')
}

export function displayProfileCode(p: FenestrationProfileRow): string {
	const code = p.profile_code || p.name
	if (p.series && code.endsWith(`-${p.series}`)) {
		return code.slice(0, -(p.series.length + 1))
	}
	return code.replace('-CS400', '')
}

export function profileRotationTransform(p: {
	section_rotation?: string | number | null
	width_mm?: number | null
	depth_mm?: number | null
}): string {
	const rot = (((Number(p.section_rotation || 0) % 360) + 360) % 360)
	if (!rot) return ''
	const isTurned = rot === 90 || rot === 270
	const w0 = Math.max(Number(isTurned ? p.depth_mm : p.width_mm) || 10, 1)
	const h0 = Math.max(Number(isTurned ? p.width_mm : p.depth_mm) || 10, 1)
	if (rot === 90) return `translate(${h0}, 0) rotate(90)`
	if (rot === 180) return `translate(${w0}, ${h0}) rotate(180)`
	if (rot === 270) return `translate(0, ${w0}) rotate(270)`
	return ''
}

export function computeCardSvgMetrics(widthMm?: number | null, depthMm?: number | null): CardSvgMetrics {
	const w = Math.max(Number(widthMm) || 10, 1)
	const h = Math.max(Number(depthMm) || 10, 1)

	const cw = 280
	const ch = 166
	const padL = 48
	const padR = 24
	const padT = 14
	const padB = 34
	const availW = cw - padL - padR
	const availH = ch - padT - padB

	const s = Math.min(availW / w, availH / h)
	const dw = w * s
	const dh = h * s
	const ox = padL + (availW - dw) / 2
	const oy = padT + (availH - dh) / 2

	const dimGap = 10
	const tick = 4
	const fontSize = 11.5
	const dimY = oy + dh + dimGap
	const dimX = ox - dimGap
	const vTextX = dimX - 11
	const vTextY = oy + dh / 2
	const pathStroke = 1.35 / s

	return {
		cw,
		ch,
		ox,
		oy,
		s,
		dw,
		dh,
		dimX,
		dimY,
		tick,
		vTextX,
		vTextY,
		pathStroke,
		fontSize,
		widthLabel: Number(widthMm || 0).toFixed(1),
		depthLabel: Number(depthMm || 0).toFixed(1),
	}
}

export function computeBlueprintSvgMetrics(
	p: FenestrationProfileRow,
	showDims = true,
): BlueprintSvgMetrics {
	const w = Math.max(Number(p.width_mm) || 10, 1)
	const h = Math.max(Number(p.depth_mm) || 10, 1)
	const span = Math.max(w, h)

	const cw = 640
	const ch = 310
	const padL = showDims ? 72 : 44
	const padR = 52
	const padT = 26
	const padB = showDims ? 54 : 30
	const availW = cw - padL - padR
	const availH = ch - padT - padB

	const s = Math.min(availW / w, availH / h)
	const dw = w * s
	const dh = h * s
	const ox = padL + (availW - dw) / 2
	const oy = padT + (availH - dh) / 2

	const minorStepMm = span <= 35 ? 1 : span <= 80 ? 2 : 5
	const minorPx = minorStepMm * s
	const majorPx = minorPx * 5
	const pathStroke = 1.5 / s

	const dimGap = 14
	const tick = 5
	const fontSize = 12.5
	const dimY = oy + dh + dimGap
	const dimX = ox - dimGap
	const vTextX = dimX - 13
	const vTextY = oy + dh / 2

	const rot = (((Number(p.section_rotation || 0) % 360) + 360) % 360)
	const isTurned = rot === 90 || rot === 270
	const baseW = isTurned ? h : w
	const baseH = isTurned ? w : h
	let c = estimateSvgCentroid(p.section_svg || '', baseW, baseH)
	if (rot === 90) {
		c = { x: baseH - c.y, y: c.x }
	} else if (rot === 180) {
		c = { x: baseW - c.x, y: baseH - c.y }
	} else if (rot === 270) {
		c = { x: c.y, y: baseW - c.x }
	}
	const cx = ox + c.x * s
	const cy = oy + c.y * s
	const loops = countSvgLoops(p.section_svg || '')
	const chambers = Math.max(0, loops - 1)

	return {
		cw,
		ch,
		ox,
		oy,
		s,
		dw,
		dh,
		dimX,
		dimY,
		tick,
		vTextX,
		vTextY,
		pathStroke,
		fontSize,
		widthLabel: Number(p.width_mm || 0).toFixed(1),
		depthLabel: Number(p.depth_mm || 0).toFixed(1),
		minorPx,
		majorPx,
		cx,
		cy,
		loops,
		chambers,
	}
}

function countSvgLoops(svgPath: string): number {
	if (!svgPath) return 0
	const matches = svgPath.match(/M\s/g)
	return matches ? matches.length : 1
}

function estimateSvgCentroid(svgPath: string, fallbackW: number, fallbackH: number): { x: number; y: number } {
	if (!svgPath) return { x: fallbackW / 2, y: fallbackH / 2 }
	const subpaths = svgPath
		.split('Z')
		.map((s) => s.trim())
		.filter(Boolean)
	let totalArea = 0
	let cxSum = 0
	let cySum = 0
	let maxAbsArea = 0

	const parsedLoops = subpaths.map((sub) => {
		const cleaned = sub.replace(/^M\s*/, '')
		const pairs = cleaned.split(/\s*L\s*/)
		const pts: [number, number][] = []
		for (const pair of pairs) {
			const parts = pair.trim().split(/\s+/)
			if (parts.length >= 2) {
				const x = parseFloat(parts[0])
				const y = parseFloat(parts[1])
				if (!Number.isNaN(x) && !Number.isNaN(y)) pts.push([x, y])
			}
		}
		let area2 = 0
		let sx = 0
		let sy = 0
		for (let i = 0; i < pts.length; i++) {
			const [x1, y1] = pts[i]
			const [x2, y2] = pts[(i + 1) % pts.length]
			const cross = x1 * y2 - x2 * y1
			area2 += cross
			sx += (x1 + x2) * cross
			sy += (y1 + y2) * cross
		}
		const absA = Math.abs(area2) / 2
		if (absA > maxAbsArea) maxAbsArea = absA
		return {
			absA,
			cx: area2 !== 0 ? sx / (3 * area2) : fallbackW / 2,
			cy: area2 !== 0 ? sy / (3 * area2) : fallbackH / 2,
		}
	})

	for (const loop of parsedLoops) {
		if (loop.absA <= 1e-6) continue
		const sign = Math.abs(loop.absA - maxAbsArea) < 1e-4 ? 1 : -1
		totalArea += sign * loop.absA
		cxSum += sign * loop.absA * loop.cx
		cySum += sign * loop.absA * loop.cy
	}

	if (Math.abs(totalArea) > 1e-4) {
		const cx = cxSum / totalArea
		const cy = cySum / totalArea
		if (cx >= 0 && cx <= fallbackW && cy >= 0 && cy <= fallbackH) {
			return { x: cx, y: cy }
		}
	}
	return { x: fallbackW / 2, y: fallbackH / 2 }
}

