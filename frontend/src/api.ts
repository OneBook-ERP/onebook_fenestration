import { call } from 'frappe-ui'
import type { Design } from '@/design/types'

const API = 'onebook_fenestration.api.design'

export interface Issue {
	severity: 'error' | 'warn'
	code: string
	message: string
	panel: string
	hint: string
	path: string
}
export interface Member {
	panel: string
	role: string
	position: string
	profile: string
	length: number
	angles: string
	path: string
}
export interface BomRow {
	item: string
	name: string
	qty: number
	uom: string
	panel: string
	position: string
	length: number
	group: string
}
export interface GlassRow {
	panel: string
	number: number
	glass: string
	width: number
	height: number
	path: string
}
export interface ComputeResult {
	members: Member[]
	glass: GlassRow[]
	bom: BomRow[]
	shutter_kg: Record<string, number> | number
	window_kg: number
	area_m2: number
	area_sqft: number
	issues: Issue[]
	pricing?: Pricing
}
export interface PricingLine {
	key: string
	label: string
	amount: number
	/** false for informational subtotal heads: listed but not added to unit_price. */
	include_in_total?: boolean
}
export interface Pricing {
	lines: PricingLine[]
	unit_price: number
	rate_per_sqft: number
}
export type ComputeResponse =
	| { ok: true; result: ComputeResult }
	| { ok: false; error_type?: string; message: string }

export interface SaveArgs {
	project: string
	design_ref: string
	series_version: string
	design: Design
	svg: string
	qty: number
	design_name?: string
	location?: string
	name?: string | null
	finish?: string | null
	price_structure?: string | null
}
export type SaveResponse =
	| {
			ok: true
			name: string
			results: {
				area_sqft: number
				window_kg: number
				error_count: number
				warning_count: number
				unit_price: number
				line_total: number
			}
	  }
	| { ok: false; message: string }

export interface SavedDesign {
	name: string
	project: string
	design_ref: string
	design_name: string
	qty: number
	location: string
	series_version: string
	/** get_design parses these server-side; older callers may still get JSON strings. */
	design_json: Design | string
	result_json: ComputeResult | Record<string, never> | string
	design_svg: string
	finish?: string | null
	price_structure?: string | null
	locked_by?: { doctype: string; name: string } | null
}

export function computeDesign(
	design: Design,
	seriesVersion: string,
	finish?: string | null,
	priceStructure?: string | null,
): Promise<ComputeResponse> {
	return call(`${API}.compute_design`, {
		design: JSON.stringify(design),
		series_version: seriesVersion,
		finish: finish || null,
		price_structure: priceStructure || null,
	})
}

export interface FenestrationDefaults {
	default_finish: string | null
	default_price_structure: string | null
}

export function getFenestrationDefaults(): Promise<FenestrationDefaults> {
	return call(`${API}.get_fenestration_defaults`)
}

export function saveDesign(args: SaveArgs): Promise<SaveResponse> {
	return call(`${API}.save_design`, { ...args, design: JSON.stringify(args.design) })
}

export function getDesign(name: string): Promise<SavedDesign> {
	return call(`${API}.get_design`, { name })
}

export function copyDesign(name: string): Promise<string> {
	return call(`${API}.copy_design`, { name })
}

export interface Session {
	user: string
	roles: string[]
}

export async function getSession(): Promise<Session> {
	const user: string = await call('frappe.auth.get_logged_user')
	if (user === 'Guest') return { user, roles: [] }
	const roles: string[] = await call('frappe.core.doctype.user.user.get_current_user_roles')
	return { user, roles }
}

export function logout(): Promise<unknown> {
	return call('logout')
}

export interface NewProject {
	project_title: string
	customer?: string
	default_series_version: string
}

export async function createProject(values: NewProject): Promise<string> {
	const doc = await call('frappe.client.insert', { doc: { doctype: 'Fenestration Project', ...values } })
	return doc.name
}

const PROJECT_API = 'onebook_fenestration.api.project'

export type MakeQuotationResponse = { ok: true; quotation: string } | { ok: false; message: string }
export interface QuoteStaleness {
	changed: string[]
	added: string[]
	removed: string[]
	transport_changed: boolean
}
export interface QuoteStatus {
	quotation: string | null
	docstatus?: number
	status?: string
	grand_total?: number
	rounded_total?: number
	stale?: QuoteStaleness
	is_stale?: boolean
	net_total?: number
	total_taxes_and_charges?: number
}
export interface RepriceResult {
	repriced: number
	failed: { design: string; message: string }[]
}

export function makeQuotation(project: string): Promise<MakeQuotationResponse> {
	return call(`${PROJECT_API}.make_quotation`, { project })
}

export function quoteStatus(project: string): Promise<QuoteStatus> {
	return call(`${PROJECT_API}.quote_status`, { project })
}

export function repriceProject(project: string): Promise<RepriceResult> {
	return call(`${PROJECT_API}.reprice_project`, { project })
}

export function setProjectField(project: string, fieldname: string, value: string | number | null): Promise<unknown> {
	return call('frappe.client.set_value', { doctype: 'Fenestration Project', name: project, fieldname, value })
}
