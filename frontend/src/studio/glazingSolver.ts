import type {
	FenestrationHardwareRow,
	GlazingAutoChannel,
	GlazingAutoConfig,
	GlobalGlazingProfileType,
	SectionRuleHost,
} from './api'

export const DEFAULT_MAX_GASKET_COMPRESSION_MM = 1.0
export const DEFAULT_LOOSE_TOLERANCE_MM = 0.05

export interface GasketCatalogItem {
	code: string
	item: string
	name: string
	thickness_mm: number
}

export interface GlazingWidthResolutionOk {
	ok: true
	source: 'auto_width'
	id: string
	label: string
	series: string
	profile_type: GlobalGlazingProfileType
	host: SectionRuleHost
	bead_profile: string
	no_bead: boolean
	bead_side: 'inside' | 'outside'
	bead_width_mm: number
	remaining_mm: number
	compression_mm: number
	total_gasket_mm: number
	inner_gasket_hardware: string
	inner_gasket_item: string
	inner_gasket_name: string
	inner_gasket_mm: number
	outer_gasket_hardware: string
	outer_gasket_item: string
	outer_gasket_name: string
	outer_gasket_mm: number
}

export interface GlazingWidthResolutionError {
	ok: false
	source: 'auto_width'
	reason: 'no_gaskets' | 'exceeds_max_bw' | 'no_gasket_combo'
	message: string
	glass_t: number
	candidate_widths: number[]
}

export type GlazingWidthResolution = GlazingWidthResolutionOk | GlazingWidthResolutionError

export function defaultGlazingAutoConfig(): GlazingAutoConfig {
	return {
		enabled: true,
		max_compression_mm: DEFAULT_MAX_GASKET_COMPRESSION_MM,
		loose_tolerance_mm: DEFAULT_LOOSE_TOLERANCE_MM,
		thicker_gasket_side: 'outer',
		gasket_pool: [],
		channels: [],
	}
}

export function normalizeGlazingAutoConfig(raw?: Partial<GlazingAutoConfig> | null): GlazingAutoConfig {
	const base = defaultGlazingAutoConfig()
	if (!raw || typeof raw !== 'object') return base
	const thicker = raw.thicker_gasket_side === 'inner' ? 'inner' : 'outer'
	const gasket_pool = Array.isArray(raw.gasket_pool)
		? [...new Set(raw.gasket_pool.map((c) => String(c || '').trim()).filter(Boolean))]
		: []
	const channels: GlazingAutoChannel[] = Array.isArray(raw.channels)
		? raw.channels
			.filter((ch): ch is GlazingAutoChannel => Boolean(ch && typeof ch === 'object'))
			.map((ch, idx) => {
				const bead = String(ch.bead_profile || '').trim()
				const noBead = Boolean(ch.no_bead) || !bead
				const pt =
					ch.profile_type === 'window' || ch.profile_type === 'door' || ch.profile_type === 'both'
						? ch.profile_type
						: 'both'
				const host: SectionRuleHost =
					ch.host === 'frame' || ch.host === 'sash' || ch.host === 'both' ? ch.host : 'frame'
				return {
					id: String(ch.id || `glazing_ch_${idx + 1}`).trim(),
					series: String(ch.series || '').trim(),
					label: String(ch.label || '').trim(),
					profile_type: pt,
					host,
					bead_profile: noBead ? '' : bead,
					no_bead: noBead,
					bead_width_mm: Math.max(0, Math.round(Number(ch.bead_width_mm || 0) * 100) / 100),
					bead_side: ch.bead_side === 'outside' ? 'outside' : 'inside',
				}
			})
		: []

	return {
		enabled: raw.enabled === undefined ? true : Boolean(raw.enabled),
		max_compression_mm: Math.max(
			0,
			Math.round(Number(raw.max_compression_mm ?? DEFAULT_MAX_GASKET_COMPRESSION_MM) * 100) / 100,
		),
		loose_tolerance_mm: Math.max(
			0,
			Math.round(Number(raw.loose_tolerance_mm ?? DEFAULT_LOOSE_TOLERANCE_MM) * 1000) / 1000,
		),
		thicker_gasket_side: thicker,
		gasket_pool,
		channels,
	}
}

export function extractGasketCatalog(
	hardware: Array<Partial<FenestrationHardwareRow> & { code?: string }> = [],
	gasketPool: string[] = [],
): GasketCatalogItem[] {
	const allowed = new Set(gasketPool.map((c) => c.trim().toLowerCase()).filter(Boolean))
	const out: GasketCatalogItem[] = []
	for (const hw of hardware) {
		if (hw.category && hw.category !== 'Gasket' && hw.category !== 'Seal / Weatherstrip') continue
		const thk = Math.round(Number(hw.thickness_mm || 0) * 1000) / 1000
		if (!(thk > 0)) continue
		const code = String(hw.hardware_code || hw.code || hw.name || '').trim()
		const item = String(hw.item || code).trim()
		const name = String(hw.hardware_name || hw.name || code).trim()
		if (allowed.size && !allowed.has(code.toLowerCase()) && !allowed.has(item.toLowerCase())) continue
		out.push({ code, item: item || code, name: name || code, thickness_mm: thk })
	}
	return out.sort((a, b) => a.thickness_mm - b.thickness_mm || a.code.localeCompare(b.code))
}

function matchingChannels(
	channels: GlazingAutoChannel[],
	series: string,
	host: SectionRuleHost,
	application: GlobalGlazingProfileType,
): GlazingAutoChannel[] {
	const seriesL = (series || '').trim().toLowerCase()
	const hostL = host || 'frame'
	const appL = application || 'window'
	const windowSash = hostL === 'sash' && appL === 'window'

	const matches = (ch: GlazingAutoChannel, wantSeries: string) => {
		if (!(Number(ch.bead_width_mm) > 0)) return false
		if ((ch.series || '').trim().toLowerCase() !== wantSeries) return false
		const cHost = ch.host || 'both'
		if (cHost !== 'both' && hostL !== 'both' && cHost !== hostL) return false
		const cType = ch.profile_type || 'both'
		if (cType !== 'both' && appL !== 'both' && cType !== appL) return false
		if (windowSash && !ch.no_bead) return false
		return true
	}

	let matched = seriesL ? channels.filter((ch) => matches(ch, seriesL)) : []
	if (!matched.length) matched = channels.filter((ch) => matches(ch, ''))

	return matched.sort((a, b) => {
		const bwDiff = Number(a.bead_width_mm) - Number(b.bead_width_mm)
		if (Math.abs(bwDiff) > 1e-6) return bwDiff
		const noBeadDiff = (a.no_bead ? 1 : 0) - (b.no_bead ? 1 : 0)
		if (noBeadDiff !== 0) return noBeadDiff
		const typeA = appL !== 'both' && a.profile_type === appL ? 0 : 1
		const typeB = appL !== 'both' && b.profile_type === appL ? 0 : 1
		if (typeA !== typeB) return typeA - typeB
		const hostA = hostL !== 'both' && a.host === hostL ? 0 : 1
		const hostB = hostL !== 'both' && b.host === hostL ? 0 : 1
		return hostA - hostB
	})
}

function bestGasketPair(
	bw: number,
	glassT: number,
	gaskets: GasketCatalogItem[],
	maxCompressionMm: number,
	looseToleranceMm: number,
	thickerSide: 'outer' | 'inner',
) {
	if (glassT <= 0 || bw <= 0 || glassT >= bw - 1e-6 || !gaskets.length) return null
	const remaining = bw - glassT
	let bestScore: [number, number, number, number] | null = null
	let bestPair: {
		inner: GasketCatalogItem
		outer: GasketCatalogItem
		remaining_mm: number
		compression_mm: number
		total_gasket_mm: number
	} | null = null

	const isBetter = (a: [number, number, number, number], b: [number, number, number, number]) => {
		for (let k = 0; k < 4; k++) {
			if (a[k] !== b[k]) return a[k] < b[k]
		}
		return false
	}

	for (let i = 0; i < gaskets.length; i++) {
		for (let j = i; j < gaskets.length; j++) {
			const gThin = gaskets[i]
			const gThick = gaskets[j]
			const totalG = gThick.thickness_mm + gThin.thickness_mm
			const compression = glassT + totalG - bw
			if (compression < -(looseToleranceMm + 1e-6)) continue
			if (compression > maxCompressionMm + 1e-6) continue
			const isExact = Math.abs(compression) <= looseToleranceMm + 1e-6 ? 0 : 1
			const overComp = Math.round(Math.max(0, compression) * 10000) / 10000
			const spread = Math.round((gThick.thickness_mm - gThin.thickness_mm) * 10000) / 10000
			const absComp = Math.round(Math.abs(compression) * 10000) / 10000
			const score: [number, number, number, number] = [isExact, overComp, spread, absComp]
			if (!bestScore || isBetter(score, bestScore)) {
				bestScore = score
				const [outer, inner] = thickerSide === 'inner' ? [gThin, gThick] : [gThick, gThin]
				bestPair = {
					inner,
					outer,
					remaining_mm: Math.round(remaining * 100) / 100,
					compression_mm: Math.round(compression * 100) / 100,
					total_gasket_mm: Math.round(totalG * 100) / 100,
				}
			}
		}
	}
	return bestPair
}

export function resolveGlazingByWidth(
	autoConfig: Partial<GlazingAutoConfig> | null | undefined,
	hardware: Array<Partial<FenestrationHardwareRow> & { code?: string }>,
	glassT: number,
	series = '',
	host: SectionRuleHost = 'frame',
	application: GlobalGlazingProfileType = 'window',
): GlazingWidthResolution | null {
	if (!(glassT > 0) || !autoConfig) return null
	const cfg = normalizeGlazingAutoConfig(autoConfig)
	if (!cfg.enabled || !cfg.channels.length) return null

	const candidates = matchingChannels(cfg.channels, series, host, application)
	if (!candidates.length) return null

	const gaskets = extractGasketCatalog(hardware, cfg.gasket_pool)
	if (!gaskets.length) {
		return {
			ok: false,
			source: 'auto_width',
			reason: 'no_gaskets',
			message: 'No gaskets with thickness_mm > 0 are configured for automatic resolution.',
			glass_t: Math.round(glassT * 100) / 100,
			candidate_widths: candidates.map((c) => c.bead_width_mm),
		}
	}

	for (const ch of candidates) {
		const bw = Number(ch.bead_width_mm)
		if (glassT >= bw - 1e-6) continue
		const pair = bestGasketPair(
			bw,
			glassT,
			gaskets,
			cfg.max_compression_mm,
			cfg.loose_tolerance_mm,
			cfg.thicker_gasket_side,
		)
		if (!pair) continue
		const noBead = Boolean(ch.no_bead) || !String(ch.bead_profile || '').trim()
		return {
			ok: true,
			source: 'auto_width',
			id: ch.id,
			label: ch.label || (noBead ? `No Bead (${bw} mm)` : `${ch.bead_profile} (${bw} mm)`),
			series: ch.series,
			profile_type: ch.profile_type,
			host: ch.host,
			bead_profile: noBead ? '' : ch.bead_profile,
			no_bead: noBead,
			bead_side: ch.bead_side,
			bead_width_mm: bw,
			remaining_mm: pair.remaining_mm,
			compression_mm: pair.compression_mm,
			total_gasket_mm: pair.total_gasket_mm,
			inner_gasket_hardware: pair.inner.code,
			inner_gasket_item: pair.inner.item,
			inner_gasket_name: pair.inner.name,
			inner_gasket_mm: pair.inner.thickness_mm,
			outer_gasket_hardware: pair.outer.code,
			outer_gasket_item: pair.outer.item,
			outer_gasket_name: pair.outer.name,
			outer_gasket_mm: pair.outer.thickness_mm,
		}
	}

	const maxBw = Math.max(...candidates.map((c) => Number(c.bead_width_mm)))
	const widthsStr = candidates.map((c) => `${Number(c.bead_width_mm)} mm`).join(', ')
	if (glassT >= maxBw - 1e-6) {
		return {
			ok: false,
			source: 'auto_width',
			reason: 'exceeds_max_bw',
			message: `Glass thickness ${glassT} mm exceeds maximum configured width (${maxBw} mm).`,
			glass_t: Math.round(glassT * 100) / 100,
			candidate_widths: candidates.map((c) => c.bead_width_mm),
		}
	}
	return {
		ok: false,
		source: 'auto_width',
		reason: 'no_gasket_combo',
		message: `Glass thickness ${glassT} mm has no valid gasket pair (within ${cfg.max_compression_mm} mm compression) for [${widthsStr}].`,
		glass_t: Math.round(glassT * 100) / 100,
		candidate_widths: candidates.map((c) => c.bead_width_mm),
	}
}

