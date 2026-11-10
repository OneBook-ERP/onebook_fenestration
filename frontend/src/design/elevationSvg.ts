import { layoutGeom } from './geometry'
import type { Design } from './types'

export const VIEW_W = 640
export const VIEW_H = 760
export const PAD = 60
export const FRAME_FACE = 42
export const BAR_FACE = 40
export const SASH_FACE = 50
export const DEFAULT_FINISH = '#8A8F98'
export const STROKE_COLOR = '#5B6470'
export const GLASS_FILL = '#DCEBF7'
export const DIM_COLOR = '#404040'

function fmt(n: number): string {
	return String(Math.round(n * 100) / 100)
}

function lighten(hexColor: string, amount = 0.1): string {
	if (!/^#[0-9a-fA-F]{6}$/.test(hexColor)) {
		hexColor = DEFAULT_FINISH
	}
	const num = parseInt(hexColor.slice(1), 16)
	const mix = (shift: number) => {
		const c = (num >> shift) & 255
		return Math.round(c + (255 - c) * amount)
	}
	return '#' + [16, 8, 0].map((s) => mix(s).toString(16).padStart(2, '0')).join('').toUpperCase()
}

export function generateElevationSvg(design: Design, finishColor?: string): string {
	const width = Number(design.width) || 0
	const height = Number(design.height) || 0
	if (width <= 0 || height <= 0 || !design.root) return ''

	const finish = finishColor && /^#[0-9a-fA-F]{6}$/.test(finishColor) ? finishColor : DEFAULT_FINISH
	const sashFill = lighten(finish, 0.1)

	const scale = Math.min((VIEW_W - 2 * PAD) / width, (VIEW_H - 2 * PAD) / height)
	const originX = (VIEW_W - width * scale) / 2
	const originY = (VIEW_H - height * scale) / 2

	const px = (mm: number) => originX + mm * scale
	const py = (mm: number) => originY + (height - mm) * scale

	const { cells, bars } = layoutGeom(design)

	const parts: string[] = [
		`<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Window ${fmt(width)} by ${fmt(height)} mm" viewBox="0 0 ${VIEW_W} ${VIEW_H}" width="${VIEW_W}" height="${VIEW_H}" font-family="Inter, sans-serif">`,
		`<rect x="0" y="0" width="${VIEW_W}" height="${VIEW_H}" fill="#FFFFFF"/>`,
	]

	// Outer frame
	const fw = width * scale
	const fh = height * scale
	const fx = px(0)
	const fy = py(height)
	parts.push(`<rect x="${fmt(fx)}" y="${fmt(fy)}" width="${fmt(fw)}" height="${fmt(fh)}" fill="${finish}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)

	// Frame corner miter lines
	const ff = FRAME_FACE * scale
	parts.push(`<line x1="${fmt(fx)}" y1="${fmt(fy)}" x2="${fmt(fx + ff)}" y2="${fmt(fy + ff)}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
	parts.push(`<line x1="${fmt(fx + fw)}" y1="${fmt(fy)}" x2="${fmt(fx + fw - ff)}" y2="${fmt(fy + ff)}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
	parts.push(`<line x1="${fmt(fx)}" y1="${fmt(fy + fh)}" x2="${fmt(fx + ff)}" y2="${fmt(fy + fh - ff)}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
	parts.push(`<line x1="${fmt(fx + fw)}" y1="${fmt(fy + fh)}" x2="${fmt(fx + fw - ff)}" y2="${fmt(fy + fh - ff)}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)

	// Bars (Mullions & Transoms)
	for (const bar of bars) {
		if (bar.dir === 'v') {
			const bw = BAR_FACE * scale
			const bx = px(bar.x) - bw / 2
			const by = py(bar.y + bar.length)
			const bh = bar.length * scale
			parts.push(`<rect x="${fmt(bx)}" y="${fmt(by)}" width="${fmt(bw)}" height="${fmt(bh)}" fill="${finish}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
		} else {
			const bh = BAR_FACE * scale
			const bx = px(bar.x)
			const by = py(bar.y) - bh / 2
			const bw = bar.length * scale
			parts.push(`<rect x="${fmt(bx)}" y="${fmt(by)}" width="${fmt(bw)}" height="${fmt(bh)}" fill="${finish}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
		}
	}

	// Cells
	for (const cell of cells) {
		const l = cell.x === 0 ? FRAME_FACE : BAR_FACE / 2
		const r = cell.x + cell.w >= width - 0.01 ? FRAME_FACE : BAR_FACE / 2
		const b = cell.y === 0 ? FRAME_FACE : BAR_FACE / 2
		const t = cell.y + cell.h >= height - 0.01 ? FRAME_FACE : BAR_FACE / 2

		const cx = px(cell.x + l)
		const cy = py(cell.y + cell.h - t)
		const cw = (cell.w - l - r) * scale
		const ch = (cell.h - t - b) * scale

		if (cell.node.type === 'sash') {
			// Sash frame
			parts.push(`<rect x="${fmt(cx)}" y="${fmt(cy)}" width="${fmt(cw)}" height="${fmt(ch)}" fill="${sashFill}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
			const sf = SASH_FACE * scale
			parts.push(`<line x1="${fmt(cx)}" y1="${fmt(cy)}" x2="${fmt(cx + sf)}" y2="${fmt(cy + sf)}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
			parts.push(`<line x1="${fmt(cx + cw)}" y1="${fmt(cy)}" x2="${fmt(cx + cw - sf)}" y2="${fmt(cy + sf)}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
			parts.push(`<line x1="${fmt(cx)}" y1="${fmt(cy + ch)}" x2="${fmt(cx + sf)}" y2="${fmt(cy + ch - sf)}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
			parts.push(`<line x1="${fmt(cx + cw)}" y1="${fmt(cy + ch)}" x2="${fmt(cx + cw - sf)}" y2="${fmt(cy + ch - sf)}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)

			const gx = cx + sf
			const gy = cy + sf
			const gw = Math.max(0, cw - 2 * sf)
			const gh = Math.max(0, ch - 2 * sf)
			parts.push(`<rect x="${fmt(gx)}" y="${fmt(gy)}" width="${fmt(gw)}" height="${fmt(gh)}" fill="${GLASS_FILL}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)

			const hinge = cell.node.hinge
			if (hinge === 'left') {
				parts.push(`<polyline points="${fmt(gx)},${fmt(gy)} ${fmt(gx + gw)},${fmt(gy + gh / 2)} ${fmt(gx)},${fmt(gy + gh)}" fill="none" stroke="${DIM_COLOR}" stroke-dasharray="6 4"/>`)
			} else if (hinge === 'right') {
				parts.push(`<polyline points="${fmt(gx + gw)},${fmt(gy)} ${fmt(gx)},${fmt(gy + gh / 2)} ${fmt(gx + gw)},${fmt(gy + gh)}" fill="none" stroke="${DIM_COLOR}" stroke-dasharray="6 4"/>`)
			} else if (hinge === 'top') {
				parts.push(`<polyline points="${fmt(gx)},${fmt(gy)} ${fmt(gx + gw / 2)},${fmt(gy + gh)} ${fmt(gx + gw)},${fmt(gy)}" fill="none" stroke="${DIM_COLOR}" stroke-dasharray="6 4"/>`)
			}
		} else {
			parts.push(`<rect x="${fmt(cx)}" y="${fmt(cy)}" width="${fmt(cw)}" height="${fmt(ch)}" fill="${GLASS_FILL}" stroke="${STROKE_COLOR}" stroke-width="1"/>`)
		}
	}

	// Dimensions
	const dimY = py(0) + 24
	parts.push(`<line x1="${fmt(fx)}" x2="${fmt(fx + fw)}" y1="${fmt(dimY)}" y2="${fmt(dimY)}" stroke="${DIM_COLOR}"/>`)
	parts.push(`<line x1="${fmt(fx)}" x2="${fmt(fx)}" y1="${fmt(dimY - 5)}" y2="${fmt(dimY + 5)}" stroke="${DIM_COLOR}"/>`)
	parts.push(`<line x1="${fmt(fx + fw)}" x2="${fmt(fx + fw)}" y1="${fmt(dimY - 5)}" y2="${fmt(dimY + 5)}" stroke="${DIM_COLOR}"/>`)
	parts.push(`<text x="${fmt(fx + fw / 2)}" y="${fmt(dimY - 4)}" text-anchor="middle" font-size="12" font-weight="600" fill="${DIM_COLOR}">${fmt(width)}</text>`)

	const dimX = fx - 24
	parts.push(`<line x1="${fmt(dimX)}" x2="${fmt(dimX)}" y1="${fmt(fy)}" y2="${fmt(fy + fh)}" stroke="${DIM_COLOR}"/>`)
	parts.push(`<line x1="${fmt(dimX - 5)}" x2="${fmt(dimX + 5)}" y1="${fmt(fy)}" y2="${fmt(fy)}" stroke="${DIM_COLOR}"/>`)
	parts.push(`<line x1="${fmt(dimX - 5)}" x2="${fmt(dimX + 5)}" y1="${fmt(fy + fh)}" y2="${fmt(fy + fh)}" stroke="${DIM_COLOR}"/>`)
	parts.push(`<text transform="translate(${fmt(dimX - 4)} ${fmt(fy + fh / 2)}) rotate(-90)" text-anchor="middle" font-size="12" font-weight="600" fill="${DIM_COLOR}">${fmt(height)}</text>`)

	parts.push('</svg>')
	return parts.join('')
}

