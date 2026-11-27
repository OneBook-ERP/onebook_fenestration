import type { SectionPiece } from '@/api'
import { GLASS_REF_THICKNESS_MM, type PlacedShape } from '@/design/sectionPuzzle'
import type { GlassDomainAlign, SectionGlassDomain } from '@/studio/api'

export interface ResolvedGlassBounds {
	/** Left / bottom edge in section coordinates (mm) */
	x: number
	/** Top / outer edge of the glass in section coordinates (mm) */
	y: number
	/** Rendered glass width along the cut (mm) */
	w: number
	/** Rendered glass depth / thickness (mm) */
	depth: number
	/** Center Y (equal to `offsetDepth` used by SectionView & Window3DView) */
	offsetDepth: number
	/** Horizontal shift relative to baseStart */
	offsetAlong: number
	/** True if glass thickness exceeds the domain depth */
	exceedsDomain: boolean
	/** Domain outer rectangle in section coordinates */
	domainRect: { x: number; y: number; w: number; h: number }
}

const MIN_DOMAIN_DEPTH_MM = 2
const MIN_GLASS_SPAN_MM = 4

function roundHalf(n: number): number {
	return Math.round(n * 2) / 2
}

export function roundTenth(n: number): number {
	return Math.round(n * 10) / 10
}

export interface PaneGasketsMeta {
	outer_code: string
	outer_name: string
	outer_mm: number
	inner_code: string
	inner_name: string
	inner_mm: number
	bead_side: 'inside' | 'outside'
	no_bead: boolean
}

/** Extract resolved glazing gasket metadata attached to a glass SectionPiece, if present. */
export function paneGasketsFromPiece(piece: SectionPiece): PaneGasketsMeta | null {
	const raw = piece.config_placement?.glazing_gaskets
	if (!raw || typeof raw !== 'object') return null
	const g = raw as Record<string, unknown>
	const outerCode = String(g.outer_code || '')
	const innerCode = String(g.inner_code || '')
	if (!outerCode && !innerCode) return null
	return {
		outer_code: outerCode,
		outer_name: String(g.outer_name || outerCode),
		outer_mm: Math.max(1, Number(g.outer_mm) || 3),
		inner_code: innerCode,
		inner_name: String(g.inner_name || innerCode),
		inner_mm: Math.max(1, Number(g.inner_mm) || 3),
		bead_side: g.bead_side === 'outside' ? 'outside' : 'inside',
		no_bead: Boolean(g.no_bead),
	}
}

/** Extract a usable glass domain from a SectionPiece's backend config_placement, if present. */
export function glassDomainFromPiece(piece: SectionPiece): SectionGlassDomain | null {
	const cfg = piece.config_placement
	if (!cfg || cfg.source !== 'series_section_template_glass_domain') return null
	if (typeof cfg.minY !== 'number' || typeof cfg.maxY !== 'number') return null
	const minY = Math.min(cfg.minY, cfg.maxY)
	const maxY = Math.max(cfg.minY, cfg.maxY)
	if (maxY - minY < 1) return null
	const align: GlassDomainAlign =
		cfg.align === 'top' || cfg.align === 'bottom' ? cfg.align : 'center'
	const rawRc = cfg.raycast as Record<string, unknown> | undefined
	const raycast =
		rawRc && rawRc.enabled && typeof rawRc.pocketMinY === 'number' && typeof rawRc.pocketMaxY === 'number'
			? {
					enabled: true,
					pocketMinY: Number(rawRc.pocketMinY),
					pocketMaxY: Number(rawRc.pocketMaxY),
					pocketInsetLow: Number(rawRc.pocketInsetLow) || 0,
					pocketInsetHigh: Number(rawRc.pocketInsetHigh) || 0,
					pocketInsetMullion:
						rawRc.pocketInsetMullion != null ? Number(rawRc.pocketInsetMullion) : null,
					probeOffsetFromLow: Math.max(0.5, Number(rawRc.probeOffsetFromLow) || 4),
				}
			: null
	return {
		configured: true,
		minY,
		maxY,
		insetLow: typeof cfg.insetLow === 'number' ? cfg.insetLow : 0,
		insetHigh: typeof cfg.insetHigh === 'number' ? cfg.insetHigh : 0,
		align,
		...(raycast ? { raycast } : {}),
	}
}

/**
 * Fit ANY glass thickness strictly inside a configured Glass Domain without ever clipping past
 * the domain's top/bottom or left/right boundaries (when thickness fits within domain depth).
 */
export function fitGlassInDomain(
	baseStart: number,
	baseEnd: number,
	thicknessMm: number,
	domain: SectionGlassDomain,
	gasketRatio?: { outerMm: number; innerMm: number } | null,
): ResolvedGlassBounds {
	const minY = Math.min(domain.minY, domain.maxY)
	const maxY = Math.max(domain.minY, domain.maxY)
	const domainH = Math.max(1, maxY - minY)
	const rawD = thicknessMm > 0 ? thicknessMm : GLASS_REF_THICKNESS_MM

	// Horizontal span constrained inside domain insets (relative to real glass ends)
	const rawX1 = baseStart + (Number(domain.insetLow) || 0)
	const rawX2 = baseEnd - (Number(domain.insetHigh) || 0)
	let x = rawX1
	let w = rawX2 - rawX1
	if (w < MIN_GLASS_SPAN_MM) {
		const mid = (baseStart + baseEnd) / 2
		x = mid - MIN_GLASS_SPAN_MM / 2
		w = MIN_GLASS_SPAN_MM
	}

	const exceedsDomain = rawD > domainH + 0.05
	let y: number
	if (exceedsDomain) {
		// Glass is thicker than pocket depth: center inside domain and flag warning
		y = (minY + maxY - rawD) / 2
	} else if (domain.align === 'top') {
		y = minY
	} else if (domain.align === 'bottom') {
		y = maxY - rawD
	} else if (gasketRatio && gasketRatio.outerMm > 0 && gasketRatio.innerMm > 0) {
		const totalGap = domainH - rawD
		y = minY + totalGap * (gasketRatio.outerMm / (gasketRatio.outerMm + gasketRatio.innerMm))
	} else {
		y = (minY + maxY - rawD) / 2
	}

	// Clamp strictly inside [minY, maxY - rawD] whenever glass fits
	if (!exceedsDomain) {
		y = Math.max(minY, Math.min(maxY - rawD, y))
	}

	const offsetDepth = roundTenth(y + rawD / 2)
	const offsetAlong = roundTenth(x - baseStart)

	return {
		x: roundTenth(x),
		y: roundTenth(y),
		w: roundTenth(w),
		depth: rawD,
		offsetDepth,
		offsetAlong,
		exceedsDomain,
		domainRect: {
			x: roundTenth(x),
			y: roundTenth(minY),
			w: roundTenth(w),
			h: roundTenth(domainH),
		},
	}
}

/**
 * Compute a sensible initial Glass Domain centered in the surrounding profile depth envelope
 * when the user enables Glass Domain for the first time on a template.
 */
export function suggestInitialGlassDomain(
	profileShapes: PlacedShape[],
	glassThicknessMm = GLASS_REF_THICKNESS_MM,
): SectionGlassDomain {
	const candidates = profileShapes.filter(
		(s) => s.piece.kind === 'profile' && (s.piece.role === 'sash' || s.piece.role === 'frame' || s.piece.role === 'mullion'),
	)
	const host = candidates.filter((s) => s.piece.role === 'sash')
	const ref = host.length ? host : candidates
	if (!ref.length) {
		const half = Math.max(10, glassThicknessMm / 2 + 4)
		return {
			configured: true,
			minY: roundHalf(-half),
			maxY: roundHalf(half),
			insetLow: 0,
			insetHigh: 0,
			insetMullion: null,
			align: 'center',
		}
	}
	const envMinY = Math.min(...ref.map((s) => s.bbox.minY))
	const envMaxY = Math.max(...ref.map((s) => s.bbox.maxY))
	const envH = Math.max(12, envMaxY - envMinY)
	const pad = Math.min(envH * 0.2, Math.max(4, (envH - Math.max(glassThicknessMm + 6, 16)) / 2))
	const minY = roundHalf(envMinY + pad)
	const maxY = roundHalf(Math.max(minY + Math.max(glassThicknessMm + 4, 12), envMaxY - pad))
	return {
		configured: true,
		minY,
		maxY,
		insetLow: 0,
		insetHigh: 0,
		insetMullion: null,
		align: 'center',
	}
}

export type DomainDragHandle = 'move' | 'n' | 's' | 'w' | 'e' | 'nw' | 'ne' | 'sw' | 'se'

/** Apply a drag delta `(dxAlong, dyDepth)` in section mm to a Glass Domain handle. */
export function applyGlassDomainDrag(
	orig: SectionGlassDomain,
	handle: DomainDragHandle,
	dxAlong: number,
	dyDepth: number,
	baseSpanMm: number,
	mirrorHorizontal = true,
	snapStep = 0.5,
): SectionGlassDomain {
	const snap = (v: number) => Math.round(v / snapStep) * snapStep
	let minY = orig.minY
	let maxY = orig.maxY
	let insetLow = orig.insetLow
	let insetHigh = orig.insetHigh

	if (handle === 'move') {
		const dy = snap(dyDepth)
		minY = orig.minY + dy
		maxY = orig.maxY + dy
	} else {
		if (handle.includes('n')) {
			minY = Math.min(orig.maxY - MIN_DOMAIN_DEPTH_MM, snap(orig.minY + dyDepth))
		}
		if (handle.includes('s')) {
			maxY = Math.max(orig.minY + MIN_DOMAIN_DEPTH_MM, snap(orig.maxY + dyDepth))
		}
		if (handle.includes('w')) {
			const nextLow = snap(orig.insetLow + dxAlong)
			const nextHigh = mirrorHorizontal ? nextLow : orig.insetHigh
			if (baseSpanMm - nextLow - nextHigh >= MIN_GLASS_SPAN_MM) {
				insetLow = nextLow
				insetHigh = nextHigh
			}
		}
		if (handle.includes('e')) {
			const nextHigh = snap(orig.insetHigh - dxAlong)
			const nextLow = mirrorHorizontal ? nextHigh : orig.insetLow
			if (baseSpanMm - nextLow - nextHigh >= MIN_GLASS_SPAN_MM) {
				insetHigh = nextHigh
				insetLow = nextLow
			}
		}
	}

	return {
		...orig,
		configured: true,
		minY: roundTenth(minY),
		maxY: roundTenth(maxY),
		insetLow: roundTenth(insetLow),
		insetHigh: roundTenth(insetHigh),
	}
}

