import { call } from 'frappe-ui'

export interface ProfileSeriesRow {
	name: string
	series_code: string
	series_title: string
	system_type: 'Casement' | 'Sliding' | 'Door'
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

export interface FenestrationProfileRow {
	name: string
	profile_code: string
	profile_name: string
	series: string
	role: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead' | 'accessory'
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
}

export interface FenestrationGlassRow {
	name: string
	glass_code: string
	glass_name: string
	thickness_mm: number
	item?: string | null
	modified?: string
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
	values: Pick<ProfileSeriesRow, 'series_code' | 'series_title' | 'system_type'>,
	existingName?: string | null,
): Promise<string> {
	if (existingName) {
		await call('frappe.client.set_value', {
			doctype: 'Profile Series',
			name: existingName,
			fieldname: {
				series_title: values.series_title,
				system_type: values.system_type,
			},
		})
		return existingName
	}
	const doc = await call('frappe.client.insert', {
		doc: { doctype: 'Profile Series', ...values },
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
	if (existingName) {
		const existing = await call('frappe.client.get', {
			doctype: 'Fenestration Profile',
			name: existingName,
		})
		return call('frappe.client.save', {
			doc: {
				...existing,
				profile_name: values.profile_name,
				series: values.series,
				role: values.role,
				item: values.item || null,
				bar_lengths: values.bar_lengths,
				kg_per_m: values.kg_per_m,
				dxf_file: values.dxf_file || null,
				use_computed_weight: values.use_computed_weight ? 1 : 0,
				section_rotation:
					values.section_rotation !== undefined
						? String(values.section_rotation ?? '0')
						: String(existing.section_rotation || '0'),
				visible_perimeter_mm:
					values.visible_perimeter_mm !== undefined
						? values.visible_perimeter_mm
						: existing.visible_perimeter_mm,
			},
		})
	}
	return call('frappe.client.insert', {
		doc: {
			doctype: 'Fenestration Profile',
			...values,
			section_rotation: String(values.section_rotation ?? '0'),
			use_computed_weight: values.use_computed_weight ? 1 : 0,
		},
	})
}

export function setProfileOrientation(
	profileName: string,
	opts: number | string | { rotation?: number | string; delta?: number | string },
): Promise<{ ok: boolean; profile_name: string; section_rotation: string; width_mm: number; depth_mm: number }> {
	const params: Record<string, any> = { profile_name: profileName }
	if (typeof opts === 'object' && opts !== null) {
		if (opts.rotation !== undefined) params.rotation = String(opts.rotation)
		if (opts.delta !== undefined) params.delta = String(opts.delta)
	} else {
		params.rotation = String(opts)
	}
	return call('onebook_fenestration.api.studio.set_profile_orientation', params)
}

export function getFenestrationGlassDoc(name: string): Promise<FenestrationGlassRow> {
	return call('frappe.client.get', { doctype: 'Fenestration Glass', name })
}

export async function saveFenestrationGlass(
	values: { glass_code: string; glass_name: string; thickness_mm: number; item?: string | null },
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
			},
		})
		return existingName
	}
	const doc = await call('frappe.client.insert', {
		doc: {
			doctype: 'Fenestration Glass',
			glass_code: values.glass_code,
			glass_name: values.glass_name,
			thickness_mm: values.thickness_mm,
			item: values.item || null,
		},
	})
	return doc.name
}
