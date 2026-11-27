import type { CutAxis, SectionPiece } from '@/api'
import { canonicalTransformForPiece } from '@/design/sectionPuzzle'
import type { Design, DesignNode, SectionPieceTransform } from '@/design/types'
import {
	createEmptyGlassDomain,
	createEmptySectionTemplateAxis,
	type FenestrationProfileRow,
	type SectionTemplateAxisData,
	type SectionTemplateKey,
	type SectionTemplateTransform,
} from '@/studio/api'

export interface SectionTemplateMeta {
	key: SectionTemplateKey
	label: string
	group: 'fixed' | 'openable' | 'sliding'
	application: 'window' | 'door'
	hasMullion: boolean
	components: string[]
	defaultW: number
	defaultH: number
	description: string
}

export const SECTION_TEMPLATE_LIST: SectionTemplateMeta[] = [
	{
		key: 'fixed_window',
		label: 'Fixed Window',
		group: 'fixed',
		application: 'window',
		hasMullion: false,
		components: ['Frame', 'Bead'],
		defaultW: 1200,
		defaultH: 1200,
		description: 'Single fixed window pane glazed directly into outer frame.',
	},
	{
		key: 'fixed_door',
		label: 'Fixed Door',
		group: 'fixed',
		application: 'door',
		hasMullion: false,
		components: ['Frame', 'Bead'],
		defaultW: 1000,
		defaultH: 2100,
		description: 'Fixed door sidelight / panel with door frame & threshold.',
	},
	{
		key: 'fixed_window_mullion',
		label: 'Fixed Window + Mullion',
		group: 'fixed',
		application: 'window',
		hasMullion: true,
		components: ['Frame', 'Mullion', 'Bead'],
		defaultW: 1600,
		defaultH: 1200,
		description: 'Twin fixed window bays separated by a central mullion / transom.',
	},
	{
		key: 'fixed_door_mullion',
		label: 'Fixed Door + Mullion',
		group: 'fixed',
		application: 'door',
		hasMullion: true,
		components: ['Frame', 'Mullion', 'Bead'],
		defaultW: 1800,
		defaultH: 2100,
		description: 'Twin fixed door bays separated by a central mullion / transom.',
	},
	{
		key: 'openable_window',
		label: 'Openable Window',
		group: 'openable',
		application: 'window',
		hasMullion: false,
		components: ['Frame', 'Sash'],
		defaultW: 1000,
		defaultH: 1200,
		description: 'Single openable casement window sash inside outer frame.',
	},
	{
		key: 'openable_door',
		label: 'Openable Door',
		group: 'openable',
		application: 'door',
		hasMullion: false,
		components: ['Frame', 'Sash', 'Bead'],
		defaultW: 1000,
		defaultH: 2100,
		description: 'Single openable door shutter inside outer frame.',
	},
	{
		key: 'openable_window_mullion',
		label: 'Openable Window + Mullion',
		group: 'openable',
		application: 'window',
		hasMullion: true,
		components: ['Frame', 'Sash', 'Mullion'],
		defaultW: 1600,
		defaultH: 1200,
		description: 'Twin openable window sashes meeting at a central mullion / transom.',
	},
	{
		key: 'openable_door_mullion',
		label: 'Openable Door + Mullion',
		group: 'openable',
		application: 'door',
		hasMullion: true,
		components: ['Frame', 'Sash', 'Mullion', 'Bead'],
		defaultW: 1800,
		defaultH: 2100,
		description: 'Twin openable door shutters separated by a central mullion / transom.',
	},
	{
		key: 'sliding_window',
		label: 'Sliding Window',
		group: 'sliding',
		application: 'window',
		hasMullion: true,
		components: ['Frame', 'Sash', 'Interlock'],
		defaultW: 1800,
		defaultH: 1400,
		description: 'Multi-track sliding window sashes with central interlock.',
	},
	{
		key: 'sliding_door',
		label: 'Sliding Door',
		group: 'sliding',
		application: 'door',
		hasMullion: true,
		components: ['Frame', 'Sash', 'Interlock', 'Bead'],
		defaultW: 2200,
		defaultH: 2100,
		description: 'Multi-track sliding door sashes with central interlock.',
	},
]

export function getTemplateMeta(key: SectionTemplateKey): SectionTemplateMeta {
	return SECTION_TEMPLATE_LIST.find((t) => t.key === key) ?? SECTION_TEMPLATE_LIST[0]
}

export function templatesForSupportedProducts(rawProducts?: unknown): SectionTemplateMeta[] {
	const list = Array.isArray(rawProducts)
		? rawProducts.map((p) => String(p ?? '').trim())
		: typeof rawProducts === 'string' && rawProducts.trim()
			? (() => {
				try {
					const parsed = JSON.parse(rawProducts)
					return Array.isArray(parsed) ? parsed.map((p) => String(p ?? '').trim()) : rawProducts.split(',').map((p) => p.trim())
				} catch {
					return rawProducts.split(',').map((p) => p.trim())
				}
			})()
			: []
	const chosen = new Set(list.filter(Boolean))
	if (!chosen.size) return SECTION_TEMPLATE_LIST

	return SECTION_TEMPLATE_LIST.filter((tpl) => {
		if (tpl.group === 'sliding') {
			return tpl.application === 'door' ? chosen.has('Sliding Door') : chosen.has('Sliding Window')
		}
		return tpl.application === 'door' ? chosen.has('Door') : chosen.has('Window')
	})
}

export function buildTemplateDesign(
	key: SectionTemplateKey,
	axis: CutAxis,
	glassCode: string,
	profiles: Record<string, string>,
	sectionMap: Record<string, SectionPieceTransform>,
	seriesCode: string,
	mirrorSync = true,
): Design {
	const meta = getTemplateMeta(key)
	const glass = glassCode || '6CTG'
	const w = meta.defaultW
	const h = meta.defaultH
	const isDoor = meta.application === 'door'
	const isSliding = meta.group === 'sliding'
	const splitDir: 'v' | 'h' = !isSliding && axis === 'v' ? 'h' : 'v'
	const splitAt = splitDir === 'v' ? Math.round(w / 2) : Math.round(h / 2)

	const makeFixed = (): DesignNode => ({
		type: 'fixed',
		glass,
		bead: true,
	})

	const makeSash = (hinge: 'left' | 'right'): DesignNode =>
		isSliding
			? {
				type: 'sash',
				glass,
				bead: isDoor,
				isSliding: true,
				slideDir: hinge === 'left' ? 'right' : 'left',
				trackIdx: hinge === 'left' ? 0 : 1,
				trackCount: 2,
				sashConfig: isDoor ? 'door' : 'window',
				ghh: isDoor ? 1050 : 732,
			}
			: {
				type: 'sash',
				glass,
				opening: 'out',
				hinge,
				sashConfig: isDoor ? 'door' : 'window',
				hingeStay: isDoor ? 'Hinges' : 'Friction stay',
				ghh: isDoor ? 1050 : 732,
				lock: 'multipoint',
				bead: isDoor,
			}

	let root: DesignNode
	if (meta.group === 'fixed') {
		root = meta.hasMullion
			? { type: 'split', dir: splitDir, at: [splitAt], children: [makeFixed(), makeFixed()] }
			: makeFixed()
	} else {
		root = meta.hasMullion
			? { type: 'split', dir: splitDir, at: [splitAt], children: [makeSash('left'), makeSash('right')] }
			: makeSash('left')
	}

	const cleanProfiles: Record<string, string> = {}
	for (const [k, v] of Object.entries(profiles || {})) {
		if (v && v.trim()) cleanProfiles[k] = v.trim()
	}

	return {
		width: w,
		height: h,
		series: seriesCode,
		frameConfig: isDoor ? '3-side-threshold' : '4-side',
		...(isSliding ? { isSliding: true, trackCount: 2 } : {}),
		...(Object.keys(cleanProfiles).length ? { profiles: cleanProfiles } : {}),
		sectionMap: { ...sectionMap },
		mirrorSync,
		compactGlass: true,
		root,
	}
}

export function stripGlassFromSectionMap(
	map: Record<string, SectionPieceTransform>,
): Record<string, SectionTemplateTransform> {
	const clean: Record<string, SectionTemplateTransform> = {}
	for (const [k, v] of Object.entries(map || {})) {
		if (
			k.startsWith('GLASS:') ||
			k.startsWith('glass:') ||
			/^[hv]:(OGL|OGR|MGL|MGR|OG_\d+|MG_\d+|GLASS:)/.test(k) ||
			/^[hv]:\d+:glass:/.test(k)
		) {
			continue
		}
		clean[k] = {
			offsetAlong: Math.round((Number(v.offsetAlong) || 0) * 100) / 100,
			offsetDepth: Math.round((Number(v.offsetDepth) || 0) * 100) / 100,
			rotation: (((Math.round(Number(v.rotation) || 0) % 360) + 360) % 360),
			flipX: Boolean(v.flipX),
			flipY: Boolean(v.flipY),
			...(v.originU !== undefined ? { originU: Math.round(Number(v.originU) * 100) / 100 } : {}),
			...(v.originDepth !== undefined ? { originDepth: Math.round(Number(v.originDepth) * 100) / 100 } : {}),
		}
	}
	return clean
}

function adjacencyFromTag(tag: string, role: string, hasDivider: boolean): 'frame' | 'mullion' | '' {
	if (!hasDivider) return role === 'bead' || role === 'sash' || role === 'glass_adaptor' ? 'frame' : ''
	if (tag === 'OBL' || tag === 'MBR' || tag === 'OSL' || tag === 'MSR') return 'frame'
	if (tag === 'OBR' || tag === 'MBL' || tag === 'OSR' || tag === 'MSL') return 'mullion'
	return ''
}

export function extractAxisTemplateData(
	snapshot: {
		axis: CutAxis
		pieces: SectionPiece[]
		tags: string[]
		transforms: SectionPieceTransform[]
		sectionMap: Record<string, SectionPieceTransform>
	},
	existingAxis: SectionTemplateAxisData | undefined,
): SectionTemplateAxisData {
	const roleTransforms: Record<string, SectionTemplateTransform> = {
		...(existingAxis?.roleTransforms ?? {}),
	}
	const beadByCode: Record<string, SectionTemplateTransform> = {
		...(existingAxis?.beadByCode ?? {}),
	}
	const hasDivider = snapshot.pieces.some((p) => p.role === 'mullion' || p.role === 'transom')

	// Prefer unmirrored (low-side) pieces first so canonical transforms are exact
	const indices = snapshot.pieces
		.map((_, i) => i)
		.sort((a, b) => Number(snapshot.pieces[a].mirrored) - Number(snapshot.pieces[b].mirrored))

	const seenKeys = new Set<string>()
	for (const i of indices) {
		const piece = snapshot.pieces[i]
		if (piece.kind !== 'profile') continue
		const rawT = snapshot.transforms[i]
		if (!rawT) continue
		const canon = canonicalTransformForPiece(piece, rawT)
		const norm: SectionTemplateTransform = {
			offsetAlong: Math.round((Number(canon.offsetAlong) || 0) * 100) / 100,
			offsetDepth: Math.round((Number(canon.offsetDepth) || 0) * 100) / 100,
			rotation: (((Math.round(Number(canon.rotation) || 0) % 360) + 360) % 360),
			flipX: Boolean(canon.flipX),
			flipY: Boolean(canon.flipY),
			...(canon.originU !== undefined ? { originU: Math.round(Number(canon.originU) * 100) / 100 } : {}),
			...(canon.originDepth !== undefined ? { originDepth: Math.round(Number(canon.originDepth) * 100) / 100 } : {}),
		}
		const tag = snapshot.tags[i] || ''
		const adj = adjacencyFromTag(tag, piece.role, hasDivider)

		if (!seenKeys.has(piece.role)) {
			roleTransforms[piece.role] = norm
			seenKeys.add(piece.role)
		}
		if (adj && (piece.role === 'bead' || piece.role === 'sash' || piece.role === 'glass_adaptor')) {
			const adjKey = `${piece.role}_${adj}`
			if (!seenKeys.has(adjKey)) {
				roleTransforms[adjKey] = norm
				seenKeys.add(adjKey)
			}
		}
		if ((piece.role === 'bead' || piece.role === 'glass_adaptor') && piece.code) {
			if (!seenKeys.has(`code:${piece.code}`)) {
				beadByCode[piece.code] = norm
				seenKeys.add(`code:${piece.code}`)
			}
			if (adj) {
				const codeAdj = `${piece.code}:${adj}`
				if (!seenKeys.has(`code:${codeAdj}`)) {
					beadByCode[codeAdj] = norm
					seenKeys.add(`code:${codeAdj}`)
				}
			}
		}
	}

	return {
		sectionMap: stripGlassFromSectionMap(snapshot.sectionMap),
		roleTransforms,
		beadByCode,
		glassDomain: existingAxis?.glassDomain ? { ...existingAxis.glassDomain } : createEmptyGlassDomain(),
	}
}

export function hasAxisTemplateData(axisData: SectionTemplateAxisData | undefined): boolean {
	if (!axisData) return false
	return Boolean(
		Object.keys(axisData.sectionMap || {}).length > 0 ||
			Object.keys(axisData.roleTransforms || {}).length > 0 ||
			Object.keys(axisData.beadByCode || {}).length > 0 ||
			axisData.glassDomain?.configured,
	)
}

function remapAxisTag(tag: string, fromAxis: CutAxis): string {
	if (fromAxis === 'h' && /^M\d+$/.test(tag)) return `T${tag.slice(1)}`
	if (fromAxis === 'v' && /^T\d+$/.test(tag)) return `M${tag.slice(1)}`
	return tag
}

/**
 * Project a saved B-B (horizontal) section map onto A-A (vertical) — or vice versa.
 * SectionView renders A-A in the exact same `(along, depth)` frame rotated -90°, so
 * every piece transform carries over identically with only the axis prefix (`h:` <-> `v:`)
 * and divider tag (`M1` <-> `T1`) remapped.
 */
export function mirrorSectionMapAxis(
	srcMap: Record<string, SectionTemplateTransform> | undefined,
	fromAxis: CutAxis,
	toAxis: CutAxis,
): Record<string, SectionTemplateTransform> {
	const out: Record<string, SectionTemplateTransform> = {}
	if (!srcMap) return out
	const fromPrefix = `${fromAxis}:`
	const toPrefix = `${toAxis}:`
	for (const [k, v] of Object.entries(srcMap)) {
		if (!v || typeof v !== 'object') continue
		if (k.startsWith(fromPrefix)) {
			const rest = k.slice(fromPrefix.length)
			out[`${toPrefix}${remapAxisTag(rest, fromAxis)}`] = { ...v }
		} else if (k.startsWith(toPrefix)) {
			continue
		} else {
			out[k] = { ...v }
		}
	}
	return out
}

export function mirrorAxisTemplateData(
	srcAxis: SectionTemplateAxisData | undefined,
	fromAxis: CutAxis,
	toAxis: CutAxis,
): SectionTemplateAxisData {
	if (!srcAxis) return createEmptySectionTemplateAxis()
	const nextRoles: Record<string, SectionTemplateTransform> = {}
	for (const [k, v] of Object.entries(srcAxis.roleTransforms || {})) {
		if (v) nextRoles[k] = { ...v }
	}
	if (fromAxis === 'h' && nextRoles.mullion) {
		nextRoles.transom = { ...nextRoles.mullion }
	} else if (fromAxis === 'v' && nextRoles.transom) {
		nextRoles.mullion = { ...nextRoles.transom }
	}
	const nextBeads: Record<string, SectionTemplateTransform> = {}
	for (const [k, v] of Object.entries(srcAxis.beadByCode || {})) {
		if (v) nextBeads[k] = { ...v }
	}
	return {
		sectionMap: mirrorSectionMapAxis(srcAxis.sectionMap, fromAxis, toAxis),
		roleTransforms: nextRoles,
		beadByCode: nextBeads,
		glassDomain: srcAxis.glassDomain ? { ...srcAxis.glassDomain } : createEmptyGlassDomain(),
	}
}

/**
 * Auto-pick Frame, Sash, and Mullion/Transom profiles for a Window or Door template
 * based on each profile's `profile_type` ('Window' | 'Door' | 'Both').
 */
export function autoProfilesForTemplate(
	meta: SectionTemplateMeta,
	seriesProfiles: FenestrationProfileRow[],
): Record<string, string> {
	const targetType = meta.application === 'door' ? 'Door' : 'Window'
	const pickForRoles = (roles: string[]): string => {
		const candidates = seriesProfiles.filter((p) => roles.includes(p.role))
		if (!candidates.length) return ''
		const exact = candidates.find((p) => p.profile_type === targetType)
		if (exact) return exact.profile_code || exact.name
		const shared = candidates.find((p) => !p.profile_type || p.profile_type === 'Both')
		if (shared) return shared.profile_code || shared.name
		return ''
	}

	const selected: Record<string, string> = {}
	const frameCode = pickForRoles(['frame'])
	if (frameCode) selected.frame = frameCode
	if (meta.group !== 'fixed') {
		const sashCode = pickForRoles(['sash'])
		if (sashCode) selected.sash = sashCode
	}
	if (meta.hasMullion) {
		const mullionCode = pickForRoles(['mullion', 'transom'])
		if (mullionCode) selected.mullion = mullionCode
		const transomCode = pickForRoles(['transom', 'mullion'])
		if (transomCode) selected.transom = transomCode
	}
	return selected
}

