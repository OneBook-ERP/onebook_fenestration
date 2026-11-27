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
	material?: 'glass' | 'steel'
	thickness?: number
	cutout?: import('@/design/exhaustCut').ExhaustCut | null
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
export interface SeriesInfo {
	/** Glass codes of the series version. */
	glasses: string[]
	/** Profile codes of the series version. */
	profiles?: string[]
	/** Default profile code per member role (`frame`, `sash`, `mullion`, `transom`, `bead`). */
	role_defaults?: Record<string, string>
	/** Face size along the cut: width_mm, or depth_mm when width_mm is missing. */
	profile_widths?: Record<string, number>
	/** Effective series defaults for the sash options a design can override. */
	defaults: { limiter: boolean; mesh: boolean }
	/** Optional series-level auto section configuration (beads, gaskets, grooves). */
	section_config?: Record<string, any>
	/** Supported assemblies configured on Profile Series (e.g. Window, Door, Sliding Window, Sliding Door). */
	supported_products?: string[]
}
export type ComputeResponse =
	| { ok: true; result: ComputeResult; series?: SeriesInfo }
	| { ok: false; error_type?: string; message: string }

export interface SaveArgs {
	project: string
	design_ref: string
	series_version: string
	design: Design
	svg: string
	qty: number
	design_name?: string
	floor?: string
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
	floor?: string
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

export type CutAxis = 'h' | 'v'
export type DimChain = 'overall' | 'cells' | 'glass' | 'profiles'
export interface SectionPiece {
	material?: 'glass' | 'steel'
	cutout?: { start: number; end: number; diameter: number } | null
	blades?: number
	blade_width?: number
	opening_height?: number
	/** Physical pane/member owner; fixed panes share panel F1. */
	path?: string
	kind: 'profile' | 'glass' | 'louver'
	code: string
	role: string
	panel: string
	/** mm along the cut: x from the frame's left edge (h), y up from its bottom edge (v). */
	start: number
	end: number
	/** Outline flipped: it is the right/top member of its pair. */
	mirrored: boolean
	/** Glass: overall unit thickness in mm (drawn as the band's depth); 0 for profiles. */
	thickness: number
	/** Optional placement metadata from Profile Series auto section configuration. */
	config_placement?: {
		source?: string
		template?: string
		axis?: 'h' | 'v'
		preset?: string
		host?: string
		side?: 'inside' | 'outside'
		groove?: string
		slot_x?: number
		slot_y?: number
		offsetAlong?: number
		offsetDepth?: number
		rotation?: number
		flipX?: boolean
		flipY?: boolean
		originU?: number
		originDepth?: number
		minY?: number
		maxY?: number
		insetLow?: number
		insetHigh?: number
		align?: 'center' | 'top' | 'bottom'
		gasket_slot?: Record<string, any> | null
		rebate_gasket_slot?: Record<string, any> | null
		glazing_gasket_slot?: Record<string, any> | null
		bead_slot?: Record<string, any> | null
		glass_slot?: Record<string, any> | null
		rebate_depth_mm?: number
		clearance_mm?: number
		inner_gasket_item?: string
		outer_gasket_item?: string
		glazing_gaskets?: Record<string, any> | null
		raycast?: Record<string, any> | null
	} | null
}
export interface SectionDim {
	start: number
	end: number
	label: string
	chain: DimChain
}
/** Profile section outline: SVG path `d` in mm, bbox starting at 0,0 with y down. */
export interface SectionOutline {
	svg: string
	width: number
	depth: number
}
export interface CrossSection {
	axis: CutAxis
	/** Where the engine cut, snapped to a cell centre. */
	at: number
	length: number
	pieces: SectionPiece[]
	dims: SectionDim[]
	issues: Issue[]
}
export type CutResponse =
	| { ok: true; result: CrossSection; outlines: Record<string, SectionOutline> }
	| { ok: false; error_type?: string; message: string }

/** Profiles and glass one cut line crosses; `at` null lets the engine cut through the first cell. */
export function crossSection(design: Design, seriesVersion: string, axis: CutAxis, at: number | null): Promise<CutResponse> {
	return call(`${API}.cross_section`, {
		design: JSON.stringify(design),
		series_version: seriesVersion,
		axis,
		at,
	})
}

export interface AssemblyMember {
	id: string; panel: string; path: string; role: string; position: string; profile: string
	x: number; y: number; width: number; height: number; axis: 'x' | 'y'; length: number
	end_treatment: 'mitre' | 'butt'
}
export interface AssemblyPane { material?: 'glass' | 'steel'
	cutout?: import('@/design/exhaustCut').ExhaustCut | null; id: string; panel: string; path: string; glass: string; x: number; y: number; width: number; height: number; thickness: number }
export interface WindowAssembly { width: number; height: number; members: AssemblyMember[]; panes: AssemblyPane[]; issues: Issue[] }
export type AssemblyResponse = { ok: true; result: WindowAssembly; outlines: Record<string, SectionOutline> } | { ok: false; error_type?: string; message: string }
/** Complete manufacturing-derived instance list used by the 3D renderer. */
export function windowAssembly(design: Design, seriesVersion: string): Promise<AssemblyResponse> {
	return call(`${API}.window_assembly`, { design: JSON.stringify(design), series_version: seriesVersion })
}

export interface CatalogProfile { code: string; name: string; profile_code?: string; profile_name?: string; series?: string; role?: string; width_mm?: number; depth_mm?: number; section_svg?: string; section_rotation?: string | number | null; section_flip_x?: number | boolean | null; section_flip_y?: number | boolean | null; outline_transformed?: boolean; has_outline: boolean; current_series: boolean }
export interface ProfileCatalogResponse { ok: boolean; items?: CatalogProfile[]; total?: number; next_start?: number | null; series?: string; message?: string }
export function profileCatalog(seriesVersion: string, start = 0, pageLength = 200): Promise<ProfileCatalogResponse> {
	return call(`${API}.profile_catalog`, { series_version: seriesVersion, start, page_length: pageLength })
}

export interface ProfileOrientationOpts {
	rotation?: number | string
	delta?: number | string
	flip_x?: boolean | number | string
	flip_y?: boolean | number | string
	delta_flip_x?: boolean | number | string
	delta_flip_y?: boolean | number | string
}

export interface ProfileOrientationResult {
	ok: boolean
	profile_name: string
	section_rotation: string
	section_flip_x?: number
	section_flip_y?: number
	width_mm: number
	depth_mm: number
}

export function setProfileOrientation(
	profileName: string,
	opts: number | string | ProfileOrientationOpts,
): Promise<ProfileOrientationResult> {
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

export function deleteDesign(name: string): Promise<unknown> {
	return call('frappe.client.delete', { doctype: 'Window Design', name })
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

export type PartnerType = 'Dealer' | 'Fabrication Partner' | 'Own Client'

export interface NewProject {
	project_title: string
	customer?: string
	default_series_version: string
	fen_partner_type?: PartnerType
}

export async function createProject(values: NewProject): Promise<string> {
	const doc: any = await call('frappe.client.insert', { doc: { doctype: 'Fenestration Project', ...values } })
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

export interface ProfileCutRow {
	length_mm: number
	pieces: number
	angles: string
	role: string
	kg: number
}
export interface WindowProfileGroup {
	profile_code: string
	item_code: string
	item_name: string
	uom: string
	kg: number
	total_mm: number
	pieces: number
	default_supplier?: string | null
	cuts: ProfileCutRow[]
}
export interface GlassPaneRow {
	width_mm: number
	height_mm: number
	pieces: number
	area_m2: number
	material: string
}
export interface WindowGlassGroup {
	glass_code: string
	item_code: string
	item_name: string
	uom: string
	area_m2: number
	pieces: number
	default_supplier?: string | null
	panes: GlassPaneRow[]
}
export interface WindowHardwareItem {
	item_code: string
	item_name: string
	category: 'Gasket' | 'Hardware'
	group: string
	qty: number
	uom: string
	length_mm: number
	default_supplier?: string | null
}
export interface WindowBomEntry {
	name: string
	design_ref: string
	design_name: string
	qty: number
	series_version: string
	finish: string
	floor: string
	location: string
	width_mm?: number | null
	height_mm?: number | null
	design_svg?: string
	profiles: WindowProfileGroup[]
	glass: WindowGlassGroup[]
	hardware: WindowHardwareItem[]
	problems: string[]
}
export interface SummaryProfileRow {
	item_code: string
	profile_code: string
	item_name: string
	cut_length_mm: number
	pieces: number
	total_mm: number
	kg: number
	uom: string
	spec_note: string
	default_supplier?: string | null
}
export interface SummaryGlassRow {
	item_code: string
	glass_code: string
	item_name: string
	width_mm: number
	height_mm: number
	pieces: number
	area_m2: number
	uom: string
	spec_note: string
	default_supplier?: string | null
}
export interface SummaryHardwareRow {
	item_code: string
	item_name: string
	category: string
	group: string
	qty: number
	uom: string
	spec_note: string
	default_supplier?: string | null
}
export interface MaterialTree {
	project: {
		name: string
		project_title: string
		customer?: string | null
		company?: string | null
	}
	warehouses: { name: string; warehouse_name: string }[]
	default_warehouse?: string | null
	windows: WindowBomEntry[]
	summary: {
		profiles: SummaryProfileRow[]
		glass: SummaryGlassRow[]
		hardware: SummaryHardwareRow[]
	}
	problems: string[]
}

export function materialTree(project: string): Promise<MaterialTree> {
	return call(`${PROJECT_API}.material_tree`, { project })
}

export function makeProjectMaterialRequest(
	project: string,
	category = 'all',
	warehouse?: string | null,
): Promise<{ ok: boolean; material_request: string }> {
	return call(`${PROJECT_API}.make_project_material_request`, {
		project,
		category,
		warehouse: warehouse || null,
	})
}

export function makeProjectPurchaseOrder(
	project: string,
	supplier: string,
	category = 'all',
	warehouse?: string | null,
): Promise<{ ok: boolean; purchase_order: string }> {
	return call(`${PROJECT_API}.make_project_purchase_order`, {
		project,
		supplier,
		category,
		warehouse: warehouse || null,
	})
}

export type ProjectStage = 'Draft' | 'Designing' | 'Quotation' | 'Order' | 'Production'

export interface ProjectOverviewRow {
	name: string
	project_title: string
	customer: string
	default_series_version?: string | null
	quotation?: string | null
	modified: string
	design_count: number
	window_qty: number
	total_area_sqft: number
	stage: ProjectStage
	fen_partner_type?: PartnerType
	fen_shared_with_hilux?: number | boolean
	fen_shared_on?: string | null
	fen_shared_by?: string | null
	fen_manufacturing_status?: string | null
	fen_design_locked?: number | boolean
}

export interface ProjectOverviewStats {
	total_projects: number
	total_designs: number
	total_windows: number
	quoted_or_ordered: number
	in_production: number
}

export interface ProjectOverview {
	stats: ProjectOverviewStats
	projects: ProjectOverviewRow[]
}

export function getProjectOverview(): Promise<ProjectOverview> {
	return call(`${PROJECT_API}.project_overview`)
}

export type PipelineSection = 'quotes' | 'orders' | 'production' | 'install' | 'reports'

export interface PipelineQuoteRow {
	name: string
	fen_project: string
	project_title: string
	customer: string
	transaction_date?: string
	valid_till?: string
	docstatus: number
	status: string
	amount: number
	design_count: number
	window_qty: number
	modified: string
}

export interface PipelineOrderRow {
	name: string
	fen_project: string
	project_title: string
	customer: string
	transaction_date?: string
	delivery_date?: string
	docstatus: number
	status: string
	per_delivered: number
	per_billed: number
	amount: number
	total_qty: number
	modified: string
}

export interface PipelineProductionRow {
	doctype: 'Work Order' | 'Material Request' | 'Purchase Order'
	name: string
	fen_project: string
	project_title: string
	subtitle: string
	status: string
	docstatus: number
	qty: number | null
	produced_qty: number | null
	progress_pct: number
	date: string
}

export interface PipelineInstallRow {
	name: string
	fen_project: string
	project_title: string
	customer: string
	site_address: string
	posting_date: string
	status: string
	docstatus: number
	total_qty: number
	per_installed: number
}

export interface PipelineReportRow {
	name: string
	project_title: string
	customer: string
	quotation: string
	stage: ProjectStage
	design_count: number
	window_qty: number
	total_area_sqft: number
	total_weight_kg: number
	total_value: number
}

export interface WorkspacePipelineResponse<T = any> {
	stats: Record<string, number>
	items: T[]
	pending_orders?: PipelineOrderRow[]
}

export function getWorkspacePipeline<T = any>(
	section: PipelineSection,
	project?: string,
): Promise<WorkspacePipelineResponse<T>> {
	return call(`${PROJECT_API}.workspace_pipeline`, project ? { section, project } : { section })
}

export function makeSalesOrder(
	project: string,
): Promise<{ ok: true; sales_order: string } | { ok: false; message: string }> {
	return call(`${PROJECT_API}.make_sales_order`, { project })
}

export interface QuotationDetailItem {
	idx: number
	item_code: string
	item_name: string
	description: string
	fen_window_design: string
	qty: number
	uom: string
	rate: number
	amount: number
}

export interface QuotationDetailTax {
	idx: number
	charge_type: string
	account_head: string
	description: string
	rate: number
	tax_amount: number
	total: number
}

export interface QuotationDetail {
	name: string
	fen_project: string
	customer_name: string
	address_display: string
	contact_display: string
	contact_mobile: string
	contact_email: string
	transaction_date: string
	valid_till: string
	docstatus: number
	status: string
	currency: string
	net_total: number
	total_taxes_and_charges: number
	grand_total: number
	rounded_total: number
	in_words: string
	tc_name: string
	terms: string
	items: QuotationDetailItem[]
	taxes: QuotationDetailTax[]
}

export function getQuotationDetails(quotation: string): Promise<QuotationDetail> {
	return call(`${PROJECT_API}.quotation_details`, { quotation })
}

export interface FlowAction {
	id: string
	kind: 'submit' | 'create' | 'quote'
	label: string
	doctype?: string
	name?: string
	source_doctype?: string
	source_name?: string
	target_doctype?: string
	project?: string
	primary?: boolean
	requires_supplier?: boolean
	supports_po_no?: boolean
}

export interface FlowStage {
	id: string
	label: string
	tab: string
	state: 'pending' | 'draft' | 'submitted'
	count: number
}

export interface FlowDocSummary {
	name: string
	status: string
	docstatus: number
	actions?: FlowAction[]
	[key: string]: unknown
}

export interface ProjectFlowState {
	project: string
	partner_type?: PartnerType
	shared_with_hilux?: boolean
	shared_on?: string | null
	shared_by?: string | null
	share_notes?: string
	design_locked?: boolean
	manufacturing_status?: string
	is_hilux_staff?: boolean
	quotation: FlowDocSummary | null
	sales_orders: FlowDocSummary[]
	material_requests: FlowDocSummary[]
	purchase_orders: FlowDocSummary[]
	purchase_receipts: FlowDocSummary[]
	purchase_invoices: FlowDocSummary[]
	delivery_notes: FlowDocSummary[]
	sales_invoices: FlowDocSummary[]
	payment_entries: FlowDocSummary[]
	suppliers: Array<{ name: string; supplier_name?: string }>
	primary_action: FlowAction | null
	create_options: FlowAction[]
	stages: FlowStage[]
}

export interface ShareProjectResult {
	ok: boolean
	project: string
	shared_with_hilux: boolean
	shared_on: string
	shared_by: string
	design_locked: boolean
	manufacturing_status: string
	design_count: number
	window_qty: number
	shared_with_users: string[]
}

export function shareProjectWithHilux(
	project: string,
	notes = '',
	lockDesigns = true,
): Promise<ShareProjectResult> {
	return call(`${PROJECT_API}.share_project_with_hilux`, {
		project,
		notes,
		lock_designs: lockDesigns ? 1 : 0,
	})
}

export function unlockProjectDesigns(
	project: string,
	reason = '',
): Promise<{ ok: boolean; project: string; design_locked: boolean; manufacturing_status: string }> {
	return call(`${PROJECT_API}.unlock_project_designs`, { project, reason })
}

export function updateManufacturingStatus(
	project: string,
	status: string,
): Promise<{ ok: boolean; project: string; manufacturing_status: string; design_locked: boolean }> {
	return call(`${PROJECT_API}.update_manufacturing_status`, { project, status })
}

export type FlowMutationResult =
	| { ok: true; doctype: string; name: string; status: string; docstatus: number; project?: string }
	| { ok: false; message: string }

export function getProjectFlow(project: string): Promise<ProjectFlowState> {
	return call(`${PROJECT_API}.project_flow`, { project })
}

export function submitFlowDoc(doctype: string, name: string): Promise<FlowMutationResult> {
	return call(`${PROJECT_API}.submit_flow_doc`, { doctype, name })
}

export function createFlowDoc(
	sourceDoctype: string,
	sourceName: string,
	targetDoctype: string,
	opts: { supplier?: string; poNo?: string; submit?: boolean } = {},
): Promise<FlowMutationResult> {
	return call(`${PROJECT_API}.create_flow_doc`, {
		source_doctype: sourceDoctype,
		source_name: sourceName,
		target_doctype: targetDoctype,
		supplier: opts.supplier ?? null,
		po_no: opts.poNo ?? null,
		submit: opts.submit ? 1 : 0,
	})
}
