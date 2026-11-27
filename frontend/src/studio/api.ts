import { call } from 'frappe-ui'

export type SupportedProduct = 'Window' | 'Door' | 'Sliding Window' | 'Sliding Door'

export const SUPPORTED_PRODUCT_OPTIONS: Array<{ value: SupportedProduct; label: string; hint: string }> = [
	{ value: 'Window', label: 'Window', hint: 'Fixed & Openable Windows' },
	{ value: 'Door', label: 'Door', hint: 'Fixed & Openable Doors' },
	{ value: 'Sliding Window', label: 'Sliding Window', hint: 'Multi-track Sliding Windows' },
	{ value: 'Sliding Door', label: 'Sliding Door', hint: 'Multi-track Sliding Doors' },
]

export function parseSupportedProducts(raw: unknown): SupportedProduct[] {
	if (!raw) return []
	let list: unknown[] = []
	if (Array.isArray(raw)) {
		list = raw
	} else if (typeof raw === 'string') {
		const trimmed = raw.trim()
		if (!trimmed) return []
		if (trimmed.startsWith('[')) {
			try {
				const parsed = JSON.parse(trimmed)
				if (Array.isArray(parsed)) list = parsed
			} catch {
				list = trimmed.split(',')
			}
		} else {
			list = trimmed.split(',')
		}
	}
	const valid = new Set(SUPPORTED_PRODUCT_OPTIONS.map((o) => o.value))
	const chosen = new Set<SupportedProduct>()
	for (const item of list) {
		const s = String(item ?? '').trim() as SupportedProduct
		if (valid.has(s)) chosen.add(s)
	}
	return SUPPORTED_PRODUCT_OPTIONS.map((o) => o.value).filter((v) => chosen.has(v))
}

export interface ProfileSeriesRow {
	name: string
	series_code: string
	series_title: string
	system_type: 'Casement' | 'Sliding' | 'Door'
	supported_products?: SupportedProduct[] | string | null
	published_version?: string | null
	modified?: string
}

export interface SeriesDeductionRow {
	deduction_key: string
	value: number
}

export interface SeriesConstantRow {
	constant_key: string
	value: number
}

export interface SeriesMemberRuleRow {
	rule_id: string
	role: 'frame' | 'sash' | 'mullion' | 'transom'
	profile: string
	angle_start: number
	angle_end: number
	length_expr: string
}

export interface SeriesHardwareRuleRow {
	rule_id: string
	item: string
	item_name: string
	per: 'frame_member' | 'sash_member' | 'mullion' | 'transom_member' | 'sash' | 'glass' | 'window'
	when_expr?: string
	qty_expr: string
	length_expr?: string
	uom?: string
	bom_group?: string
}

export interface SeriesValidationRuleRow {
	rule_id: string
	when_expr: string
	severity: 'error' | 'warn'
	message: string
	hint?: string
}

export interface SeriesVersionRow {
	name: string
	series: string
	version_note?: string | null
	amended_from?: string | null
	docstatus: number
	modified?: string
}

export interface SeriesVersionDoc extends SeriesVersionRow {
	doctype?: string
	deductions: SeriesDeductionRow[]
	constants: SeriesConstantRow[]
	member_rules: SeriesMemberRuleRow[]
	hardware_rules: SeriesHardwareRuleRow[]
	validation_rules: SeriesValidationRuleRow[]
}

export type ProfileApplicationType = 'Both' | 'Window' | 'Door'

export interface FenestrationProfileRow {
	name: string
	profile_code: string
	profile_name: string
	series: string
	role: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead' | 'gasket' | 'accessory'
	profile_type?: ProfileApplicationType
	item?: string | null
	kg_per_m: number
	computed_kg_per_m?: number | null
	use_computed_weight?: number | boolean
	width_mm?: number | null
	depth_mm?: number | null
	area_mm2?: number | null
	perimeter_mm?: number | null
	total_perimeter_mm?: number | null
	visible_perimeter_mm?: number | null
	ix_mm4?: number | null
	iy_mm4?: number | null
	bar_lengths: string
	dxf_file?: string | null
	section_svg?: string | null
	section_warnings?: string | null
	section_rotation?: string | number | null
	section_flip_x?: number | boolean | null
	section_flip_y?: number | boolean | null
	section_anchors_json?: string | null
	section_anchors?: ProfileSectionAnchors
}

export interface ProfileAnchorPoint {
	x: number
	y: number
	w: number
	h: number
	configured: boolean
}

export interface ProfileSectionAnchors {
	bead_groove_seat: ProfileAnchorPoint
	bead_glass_face: ProfileAnchorPoint
	bead_side: SectionSide
	gasket_groove_root: ProfileAnchorPoint
	gasket_seal_tip: ProfileAnchorPoint
	frame_gasket_groove: ProfileAnchorPoint
	frame_bead_groove: ProfileAnchorPoint
	frame_glass_pocket: ProfileAnchorPoint
	sash_rebate_gasket_groove: ProfileAnchorPoint
	sash_glazing_gasket_groove: ProfileAnchorPoint
	sash_bead_groove: ProfileAnchorPoint
	sash_glass_pocket: ProfileAnchorPoint
}

export interface GlassGlazingRule {
	series: string
	host: SectionRuleHost
	bead_profile: string
	bead_side: SectionSide
	inner_gasket_item: string
	inner_gasket_name: string
	outer_gasket_item: string
	outer_gasket_name: string
}

export interface FenestrationGlassRow {
	name: string
	glass_code: string
	glass_name: string
	thickness_mm: number
	item?: string | null
	glazing_rules_json?: string | null
	glazing_rules?: GlassGlazingRule[]
	modified?: string
}

export function createEmptyProfileAnchors(): ProfileSectionAnchors {
	const pt = (): ProfileAnchorPoint => ({ x: 0, y: 0, w: 0, h: 0, configured: false })
	return {
		bead_groove_seat: pt(),
		bead_glass_face: pt(),
		bead_side: 'inside',
		gasket_groove_root: pt(),
		gasket_seal_tip: pt(),
		frame_gasket_groove: pt(),
		frame_bead_groove: pt(),
		frame_glass_pocket: pt(),
		sash_rebate_gasket_groove: pt(),
		sash_glazing_gasket_groove: pt(),
		sash_bead_groove: pt(),
		sash_glass_pocket: pt(),
	}
}

export function parseProfileAnchors(raw?: string | Partial<ProfileSectionAnchors> | null): ProfileSectionAnchors {
	const base = createEmptyProfileAnchors()
	if (!raw) return base
	let obj: Record<string, any> = {}
	if (typeof raw === 'string') {
		try {
			const parsed = JSON.parse(raw)
			if (parsed && typeof parsed === 'object') obj = parsed
		} catch {
			return base
		}
	} else if (typeof raw === 'object') {
		obj = raw as Record<string, any>
	}
	const normPt = (p: any): ProfileAnchorPoint => {
		const x = Number(p?.x ?? 0) || 0
		const y = Number(p?.y ?? 0) || 0
		const w = Math.max(0, Number(p?.w ?? 0) || 0)
		const h = Math.max(0, Number(p?.h ?? 0) || 0)
		return { x, y, w, h, configured: Boolean(p?.configured) || x !== 0 || y !== 0 || w > 0 || h > 0 }
	}
	return {
		bead_groove_seat: normPt(obj.bead_groove_seat),
		bead_glass_face: normPt(obj.bead_glass_face),
		bead_side: obj.bead_side === 'outside' ? 'outside' : 'inside',
		gasket_groove_root: normPt(obj.gasket_groove_root),
		gasket_seal_tip: normPt(obj.gasket_seal_tip),
		frame_gasket_groove: normPt(obj.frame_gasket_groove),
		frame_bead_groove: normPt(obj.frame_bead_groove),
		frame_glass_pocket: normPt(obj.frame_glass_pocket),
		sash_rebate_gasket_groove: normPt(obj.sash_rebate_gasket_groove),
		sash_glazing_gasket_groove: normPt(obj.sash_glazing_gasket_groove),
		sash_bead_groove: normPt(obj.sash_bead_groove),
		sash_glass_pocket: normPt(obj.sash_glass_pocket),
	}
}

export function parseGlassGlazingRules(raw?: string | GlassGlazingRule[] | null): GlassGlazingRule[] {
	if (!raw) return []
	let arr: any[] = []
	if (typeof raw === 'string') {
		try {
			const parsed = JSON.parse(raw)
			if (Array.isArray(parsed)) arr = parsed
		} catch {
			return []
		}
	} else if (Array.isArray(raw)) {
		arr = raw
	}
	return arr
		.filter((r) => r && typeof r === 'object' && String(r.series || '').trim())
		.map((r) => ({
			series: String(r.series || '').trim(),
			host: (r.host === 'frame' || r.host === 'sash' ? r.host : 'both') as SectionRuleHost,
			bead_profile: String(r.bead_profile || '').trim(),
			bead_side: (r.bead_side === 'outside' ? 'outside' : 'inside') as SectionSide,
			inner_gasket_item: String(r.inner_gasket_item || '').trim(),
			inner_gasket_name: String(r.inner_gasket_name || '').trim(),
			outer_gasket_item: String(r.outer_gasket_item || '').trim(),
			outer_gasket_name: String(r.outer_gasket_name || '').trim(),
		}))
}

export interface DxfSectionPreview {
	area_mm2: number
	width_mm: number
	depth_mm: number
	perimeter_mm: number
	total_perimeter_mm: number
	ix_mm4: number
	iy_mm4: number
	computed_kg_per_m: number
	section_svg: string
	section_warnings: string
}

export type PreviewDxfResponse =
	| { ok: true; section: DxfSectionPreview }
	| { ok: false; message: string }

export function previewDxf(fileUrl: string): Promise<PreviewDxfResponse> {
	return call('onebook_fenestration.api.studio.preview_dxf', { file_url: fileUrl })
}

export function getProfileSeriesDoc(name: string): Promise<ProfileSeriesRow> {
	return call('frappe.client.get', { doctype: 'Profile Series', name })
}

export async function saveProfileSeries(
	values: Pick<ProfileSeriesRow, 'series_code' | 'series_title' | 'system_type'> & {
		supported_products?: SupportedProduct[]
	},
	existingName?: string | null,
): Promise<string> {
	const serializedProducts = JSON.stringify(parseSupportedProducts(values.supported_products))
	if (existingName) {
		await call('frappe.client.set_value', {
			doctype: 'Profile Series',
			name: existingName,
			fieldname: {
				series_title: values.series_title,
				system_type: values.system_type,
				supported_products: serializedProducts,
			},
		})
		return existingName
	}
	const doc: any = await call('frappe.client.insert', {
		doc: {
			doctype: 'Profile Series',
			series_code: values.series_code,
			series_title: values.series_title,
			system_type: values.system_type,
			supported_products: serializedProducts,
		},
	})
	return doc.name
}

export function getSeriesVersionDoc(name: string): Promise<SeriesVersionDoc> {
	return call('frappe.client.get', { doctype: 'Series Version', name })
}

export async function createSeriesVersion(
	payload: Partial<SeriesVersionDoc> & { series: string },
): Promise<SeriesVersionDoc> {
	return call('frappe.client.insert', {
		doc: {
			doctype: 'Series Version',
			series: payload.series,
			version_note: payload.version_note || '',
			amended_from: payload.amended_from || null,
			deductions: payload.deductions ?? [],
			constants: payload.constants ?? [],
			member_rules: payload.member_rules ?? [],
			hardware_rules: payload.hardware_rules ?? [],
			validation_rules: payload.validation_rules ?? [],
		},
	})
}

export async function updateSeriesVersion(doc: SeriesVersionDoc): Promise<SeriesVersionDoc> {
	return call('frappe.client.save', {
		doc: { ...doc, doctype: 'Series Version' },
	})
}

export async function publishSeriesVersion(doc: SeriesVersionDoc): Promise<SeriesVersionDoc> {
	const saved = await updateSeriesVersion(doc)
	return call('frappe.client.submit', { doc: saved })
}

export async function cancelSeriesVersion(name: string): Promise<SeriesVersionDoc> {
	return call('frappe.client.cancel', { doctype: 'Series Version', name })
}

export function getFenestrationProfileDoc(name: string): Promise<FenestrationProfileRow> {
	return call('frappe.client.get', { doctype: 'Fenestration Profile', name })
}

export async function saveFenestrationProfile(
	values: Partial<FenestrationProfileRow> & {
		profile_code: string
		profile_name: string
		series: string
		role: string
		bar_lengths: string
		kg_per_m: number
	},
	existingName?: string | null,
): Promise<FenestrationProfileRow> {
	const effectiveProfileType: ProfileApplicationType =
		values.role === 'bead' || values.role === 'gasket'
			? 'Both'
			: values.profile_type === 'Window' || values.profile_type === 'Door'
				? values.profile_type
				: 'Both'
	if (existingName) {
		const existing: any = await call('frappe.client.get', {
			doctype: 'Fenestration Profile',
			name: existingName,
		})
		return call('frappe.client.save', {
			doc: {
				...existing,
				profile_name: values.profile_name,
				series: values.series,
				role: values.role,
				profile_type: effectiveProfileType,
				item: values.item || null,
				bar_lengths: values.bar_lengths,
				kg_per_m: values.kg_per_m,
				dxf_file: values.dxf_file || null,
				use_computed_weight: values.use_computed_weight ? 1 : 0,
				section_rotation:
					values.section_rotation !== undefined
						? String(values.section_rotation ?? '0')
						: String(existing.section_rotation || '0'),
				section_flip_x:
					values.section_flip_x !== undefined
						? (values.section_flip_x ? 1 : 0)
						: (existing.section_flip_x ? 1 : 0),
				section_flip_y:
					values.section_flip_y !== undefined
						? (values.section_flip_y ? 1 : 0)
						: (existing.section_flip_y ? 1 : 0),
				visible_perimeter_mm:
					values.visible_perimeter_mm !== undefined
						? values.visible_perimeter_mm
						: existing.visible_perimeter_mm,
				section_anchors_json:
					values.section_anchors_json !== undefined
						? values.section_anchors_json
						: existing.section_anchors_json,
			},
		})
	}
	return call('frappe.client.insert', {
		doc: {
			doctype: 'Fenestration Profile',
			...values,
			profile_type: effectiveProfileType,
			section_rotation: String(values.section_rotation ?? '0'),
			section_flip_x: values.section_flip_x ? 1 : 0,
			section_flip_y: values.section_flip_y ? 1 : 0,
			use_computed_weight: values.use_computed_weight ? 1 : 0,
			section_anchors_json: values.section_anchors_json || null,
		},
	})
}

export function setProfileOrientation(
	profileName: string,
	opts: number | string | {
		rotation?: number | string
		delta?: number | string
		flip_x?: boolean | number | string
		flip_y?: boolean | number | string
		delta_flip_x?: boolean | number | string
		delta_flip_y?: boolean | number | string
	},
): Promise<{
	ok: boolean
	profile_name: string
	section_rotation: string
	section_flip_x?: number
	section_flip_y?: number
	width_mm: number
	depth_mm: number
}> {
	const params: Record<string, any> = { profile_name: profileName }
	if (typeof opts === 'object' && opts !== null) {
		if (opts.rotation !== undefined) params.rotation = String(opts.rotation)
		if (opts.delta !== undefined) params.delta = String(opts.delta)
		if (opts.flip_x !== undefined) params.flip_x = opts.flip_x ? 1 : 0
		if (opts.flip_y !== undefined) params.flip_y = opts.flip_y ? 1 : 0
		if (opts.delta_flip_x !== undefined) params.delta_flip_x = opts.delta_flip_x ? 1 : 0
		if (opts.delta_flip_y !== undefined) params.delta_flip_y = opts.delta_flip_y ? 1 : 0
	} else {
		params.rotation = String(opts)
	}
	return call('onebook_fenestration.api.studio.set_profile_orientation', params)
}

export function getFenestrationGlassDoc(name: string): Promise<FenestrationGlassRow> {
	return call('frappe.client.get', { doctype: 'Fenestration Glass', name })
}

export async function saveFenestrationGlass(
	values: {
		glass_code: string
		glass_name: string
		thickness_mm: number
		item?: string | null
		glazing_rules_json?: string | null
	},
	existingName?: string | null,
): Promise<string> {
	if (existingName) {
		await call('frappe.client.set_value', {
			doctype: 'Fenestration Glass',
			name: existingName,
			fieldname: {
				glass_name: values.glass_name,
				thickness_mm: values.thickness_mm,
				item: values.item || null,
				glazing_rules_json: values.glazing_rules_json ?? null,
			},
		})
		return existingName
	}
	const doc: any = await call('frappe.client.insert', {
		doc: {
			doctype: 'Fenestration Glass',
			glass_code: values.glass_code,
			glass_name: values.glass_name,
			thickness_mm: values.thickness_mm,
			item: values.item || null,
			glazing_rules_json: values.glazing_rules_json ?? null,
		},
	})
	return doc.name
}

export type SectionOpeningType = 'fixed' | 'openable' | 'sliding'
export type SectionApplication = 'window' | 'door'
export type SectionSide = 'inside' | 'outside'
export type SectionRuleHost = 'frame' | 'sash' | 'both'
export type SectionPresetKey = `${SectionOpeningType}:${SectionApplication}`

export interface SectionGasketSlot {
	x: number
	y: number
	w: number
	h: number
	side: SectionSide
	gasket_item: string
	gasket_name: string
	thickness_mm: number
	configured?: boolean
}

export interface SectionBeadSlot {
	x: number
	y: number
	w: number
	h: number
	side: SectionSide
	rotation: number
	flip_x: boolean
	flip_y: boolean
	configured?: boolean
}

export interface SectionGlassSlot {
	x: number
	y: number
	w: number
	h: number
	rebate_depth_mm: number
	clearance_mm: number
	configured?: boolean
}

export interface BeadGasketRule {
	id: string
	min_glass_mm: number
	max_glass_mm: number
	host: SectionRuleHost
	bead_profile: string
	bead_side: SectionSide
	bead_groove: string
	bead_offset_along: number
	bead_offset_depth: number
	bead_rotation: number
	bead_flip_x: boolean
	bead_flip_y: boolean
	inner_gasket_item: string
	inner_gasket_name: string
	outer_gasket_item: string
	outer_gasket_name: string
	gasket_groove: string
}

export interface SectionConfigPreset {
	frame: {
		profile: string
		gasket_slot: SectionGasketSlot
		bead_slot: SectionBeadSlot
		glass_slot: SectionGlassSlot
	}
	sash: {
		profile: string
		rebate_gasket_slot: SectionGasketSlot
		glazing_gasket_slot: SectionGasketSlot
		bead_slot: SectionBeadSlot
		glass_slot: SectionGlassSlot
		seat_offset_along: number
		seat_offset_depth: number
		interlock_profile: string
		track_count: number
	}
	bead_gasket_rules: BeadGasketRule[]
}

export type SectionTemplateKey =
	| 'fixed_window'
	| 'fixed_door'
	| 'fixed_window_mullion'
	| 'fixed_door_mullion'
	| 'openable_window'
	| 'openable_door'
	| 'openable_window_mullion'
	| 'openable_door_mullion'
	| 'sliding_window'
	| 'sliding_door'

export const SECTION_TEMPLATE_KEYS: SectionTemplateKey[] = [
	'fixed_window',
	'fixed_door',
	'fixed_window_mullion',
	'fixed_door_mullion',
	'openable_window',
	'openable_door',
	'openable_window_mullion',
	'openable_door_mullion',
	'sliding_window',
	'sliding_door',
]

export interface SectionTemplateTransform {
	offsetAlong: number
	offsetDepth: number
	rotation: number
	flipX: boolean
	flipY: boolean
	originU?: number
	originDepth?: number
}

export type GlassDomainAlign = 'center' | 'top' | 'bottom'

export interface SectionRaycastPocket {
	enabled: boolean
	pocketMinY: number
	pocketMaxY: number
	pocketInsetLow: number
	pocketInsetHigh: number
	pocketInsetMullion?: number | null
	probeOffsetFromLow: number
}

export interface SectionGlassDomain {
	configured: boolean
	minY: number
	maxY: number
	insetLow: number
	insetHigh: number
	insetMullion?: number | null
	align: GlassDomainAlign
	raycast?: SectionRaycastPocket | null
}

export interface SectionTemplateAxisData {
	sectionMap: Record<string, SectionTemplateTransform>
	roleTransforms: Record<string, SectionTemplateTransform>
	beadByCode: Record<string, SectionTemplateTransform>
	glassDomain?: SectionGlassDomain
}

export interface SectionTemplateEntry {
	configured: boolean
	glass: string
	profiles: Record<string, string>
	axis_h: SectionTemplateAxisData
	axis_v: SectionTemplateAxisData
}

export interface SeriesSectionConfig {
	version: number
	presets: Record<SectionPresetKey, SectionConfigPreset>
	templates?: Record<SectionTemplateKey, SectionTemplateEntry>
}

export interface GasketItemOption {
	name: string
	item_name?: string
	stock_uom?: string
}

export interface SeriesSectionConfigResponse {
	ok: boolean
	series: ProfileSeriesRow
	preview_series_version?: string | null
	config: SeriesSectionConfig
	global_glazing_rules?: GlobalGlazingRule[]
	global_glazing_auto?: GlazingAutoConfig
	gasket_hardware?: FenestrationHardwareRow[]
	profiles: FenestrationProfileRow[]
	glasses: FenestrationGlassRow[]
	gaskets: GasketItemOption[]
}

export const HARDWARE_CATEGORIES = [
	'Gasket',
	'Beading',
	'Handle',
	'Hinge',
	'Lock',
	'Roller',
	'Corner Cleat',
	'Seal / Weatherstrip',
	'Fastener',
	'Accessory',
] as const

export type HardwareCategory = (typeof HARDWARE_CATEGORIES)[number]

export interface FenestrationHardwareRow {
	name: string
	hardware_code: string
	hardware_name: string
	category: HardwareCategory | string
	item?: string | null
	uom?: string | null
	thickness_mm?: number | null
	weight_kg?: number | null
	description?: string | null
	dxf_file?: string | null
	section_svg?: string | null
	width_mm?: number | null
	depth_mm?: number | null
	area_mm2?: number | null
	perimeter_mm?: number | null
	section_rotation?: string | number | null
	section_flip_x?: number | boolean | null
	section_flip_y?: number | boolean | null
	section_warnings?: string | null
	modified?: string
}

export type GlobalGlazingProfileType = 'both' | 'window' | 'door'

export interface GlobalGlazingRule {
	id: string
	label: string
	profile_type?: GlobalGlazingProfileType
	min_glass_mm: number
	max_glass_mm: number
	host: SectionRuleHost
	bead_profile: string
	no_bead?: boolean
	bead_side: SectionSide
	inner_gasket_hardware: string
	inner_gasket_item: string
	inner_gasket_name: string
	outer_gasket_hardware: string
	outer_gasket_item: string
	outer_gasket_name: string
}

export interface GlazingAutoChannel {
	id: string
	series: string
	label: string
	profile_type: GlobalGlazingProfileType
	host: SectionRuleHost
	bead_profile: string
	no_bead: boolean
	bead_width_mm: number
	bead_side: SectionSide
}

export interface GlazingAutoConfig {
	enabled: boolean
	max_compression_mm: number
	loose_tolerance_mm: number
	thicker_gasket_side: 'outer' | 'inner'
	gasket_pool: string[]
	channels: GlazingAutoChannel[]
}

export interface GlobalGlazingRulesResponse {
	ok: boolean
	rules: GlobalGlazingRule[]
	auto_config?: GlazingAutoConfig
	series_list?: ProfileSeriesRow[]
	beads: FenestrationProfileRow[]
	hardware: FenestrationHardwareRow[]
	gasket_items: GasketItemOption[]
	glasses: FenestrationGlassRow[]
}

export function getFenestrationHardwareDoc(name: string): Promise<FenestrationHardwareRow> {
	return call('frappe.client.get', { doctype: 'Fenestration Hardware', name })
}

export async function saveFenestrationHardware(
	values: Partial<FenestrationHardwareRow> & {
		hardware_code: string
		hardware_name: string
		category: string
	},
	existingName?: string | null,
): Promise<FenestrationHardwareRow> {
	if (existingName) {
		const existing: any = await call('frappe.client.get', {
			doctype: 'Fenestration Hardware',
			name: existingName,
		})
		return call('frappe.client.save', {
			doc: {
				...existing,
				hardware_name: values.hardware_name,
				category: values.category,
				item: values.item || null,
				uom: values.uom || 'Meter',
				thickness_mm: values.thickness_mm ?? null,
				weight_kg: values.weight_kg ?? null,
				description: values.description || null,
				dxf_file: values.dxf_file || null,
				section_rotation:
					values.section_rotation !== undefined
						? String(values.section_rotation ?? '0')
						: String(existing.section_rotation || '0'),
				section_flip_x:
					values.section_flip_x !== undefined
						? (values.section_flip_x ? 1 : 0)
						: (existing.section_flip_x ? 1 : 0),
				section_flip_y:
					values.section_flip_y !== undefined
						? (values.section_flip_y ? 1 : 0)
						: (existing.section_flip_y ? 1 : 0),
			},
		})
	}
	return call('frappe.client.insert', {
		doc: {
			doctype: 'Fenestration Hardware',
			...values,
			section_rotation: String(values.section_rotation ?? '0'),
			section_flip_x: values.section_flip_x ? 1 : 0,
			section_flip_y: values.section_flip_y ? 1 : 0,
		},
	})
}

export function setHardwareOrientation(
	hardwareName: string,
	opts: { rotation?: number | string; flip_x?: boolean | number; flip_y?: boolean | number },
): Promise<{
	ok: boolean
	hardware_name: string
	section_rotation: string
	section_flip_x?: number
	section_flip_y?: number
	width_mm: number
	depth_mm: number
}> {
	return call('onebook_fenestration.api.studio.set_hardware_orientation', {
		hardware_name: hardwareName,
		...(opts.rotation !== undefined ? { rotation: String(opts.rotation) } : {}),
		...(opts.flip_x !== undefined ? { flip_x: opts.flip_x ? 1 : 0 } : {}),
		...(opts.flip_y !== undefined ? { flip_y: opts.flip_y ? 1 : 0 } : {}),
	})
}

export function getGlobalGlazingRules(): Promise<GlobalGlazingRulesResponse> {
	return call('onebook_fenestration.api.studio.get_global_glazing_rules')
}

export function saveGlobalGlazingRules(
	rules: GlobalGlazingRule[],
	autoConfig?: GlazingAutoConfig,
): Promise<{ ok: boolean; rules: GlobalGlazingRule[]; auto_config?: GlazingAutoConfig }> {
	return call('onebook_fenestration.api.studio.save_global_glazing_rules', {
		rules: JSON.stringify(rules),
		...(autoConfig !== undefined ? { auto_config: JSON.stringify(autoConfig) } : {}),
	})
}

export function createEmptyGlassDomain(): SectionGlassDomain {
	return {
		configured: false,
		minY: 0,
		maxY: 0,
		insetLow: 0,
		insetHigh: 0,
		insetMullion: null,
		align: 'center',
	}
}

export function createEmptySectionTemplateAxis(): SectionTemplateAxisData {
	return {
		sectionMap: {},
		roleTransforms: {},
		beadByCode: {},
		glassDomain: createEmptyGlassDomain(),
	}
}

export function createEmptySectionTemplate(): SectionTemplateEntry {
	return {
		configured: false,
		glass: '',
		profiles: {},
		axis_h: createEmptySectionTemplateAxis(),
		axis_v: createEmptySectionTemplateAxis(),
	}
}

export function createEmptySectionPreset(): SectionConfigPreset {
	return {
		frame: {
			profile: '',
			gasket_slot: { x: 0, y: 0, w: 0, h: 0, side: 'outside', gasket_item: '', gasket_name: '', thickness_mm: 3, configured: false },
			bead_slot: { x: 0, y: 0, w: 0, h: 0, side: 'inside', rotation: 0, flip_x: false, flip_y: false, configured: false },
			glass_slot: { x: 0, y: 0, w: 0, h: 0, rebate_depth_mm: 12, clearance_mm: 4, configured: false },
		},
		sash: {
			profile: '',
			rebate_gasket_slot: { x: 0, y: 0, w: 0, h: 0, side: 'outside', gasket_item: '', gasket_name: '', thickness_mm: 3, configured: false },
			glazing_gasket_slot: { x: 0, y: 0, w: 0, h: 0, side: 'outside', gasket_item: '', gasket_name: '', thickness_mm: 3, configured: false },
			bead_slot: { x: 0, y: 0, w: 0, h: 0, side: 'inside', rotation: 0, flip_x: false, flip_y: false, configured: false },
			glass_slot: { x: 0, y: 0, w: 0, h: 0, rebate_depth_mm: 12, clearance_mm: 4, configured: false },
			seat_offset_along: 0,
			seat_offset_depth: 0,
			interlock_profile: '',
			track_count: 2,
		},
		bead_gasket_rules: [],
	}
}

export function createEmptySectionConfig(): SeriesSectionConfig {
	return {
		version: 1,
		presets: {
			'fixed:window': createEmptySectionPreset(),
			'fixed:door': createEmptySectionPreset(),
			'openable:window': createEmptySectionPreset(),
			'openable:door': createEmptySectionPreset(),
			'sliding:window': createEmptySectionPreset(),
			'sliding:door': createEmptySectionPreset(),
		},
		templates: Object.fromEntries(
			SECTION_TEMPLATE_KEYS.map((k) => [k, createEmptySectionTemplate()]),
		) as Record<SectionTemplateKey, SectionTemplateEntry>,
	}
}

export function getSeriesSectionConfig(series: string): Promise<SeriesSectionConfigResponse> {
	return call('onebook_fenestration.api.studio.get_series_section_config', { series })
}

export function saveSeriesSectionConfig(
	series: string,
	config: SeriesSectionConfig,
): Promise<{ ok: boolean; series: string; config: SeriesSectionConfig }> {
	return call('onebook_fenestration.api.studio.save_series_section_config', {
		series,
		config: JSON.stringify(config),
	})
}
