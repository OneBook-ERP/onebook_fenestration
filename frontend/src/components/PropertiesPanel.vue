<script setup lang="ts">
import { FormControl, Select, toast, useList } from 'frappe-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { profileCatalog, type CatalogProfile } from '@/api'
import ProfilePickerModal, { type ProfileItem } from '@/components/ProfilePickerModal.vue'
import GlassPickerModal, { type GlassItem } from '@/components/GlassPickerModal.vue'
import { grillConfig, type Grill } from '@/design/grill'
import { exhaustCut, steelThickness } from '@/design/exhaustCut'
import { DEFAULT_LOUVER_WIDTH } from '@/design/louverGeometry'
import { layoutGeom } from '@/design/geometry'
import { getNode, moveSplit, removeSplit, setLeaf, setSize } from '@/design/tree'
import { panelLabel } from '@/design/typology'
import { transformedPathViewBox } from '@/design/svgBounds'
import type { ColorMode, DesignNode, FrameConfig, LeafNode, SashConfig, SplitNode } from '@/design/types'
import { profileThumbTransform } from '@/studio/sectionSvg'
import { useDesignerStore } from '@/stores/designer'

const FRAME_FACE_DEFAULT = 42
const BAR_FACE_DEFAULT = 40
const SASH_FACE_DEFAULT = 50

export interface Meta {
	ref: string
	qty: number
	name?: string
	floor?: string
	location: string
	note?: string
}
const meta = defineModel<Meta>('meta', { required: true })
const props = defineProps<{
	refError?: string
	refReadonly?: boolean
	finishes?: { name: string; finish_name: string; color?: string; finish_type?: string }[]
	seriesVersions?: { name: string; series: string; version_note?: string }[]
}>()
const store = useDesignerStore()

const glassList = useList<{ name: string; glass_name: string; thickness_mm?: number }>({
	doctype: 'Fenestration Glass',
	fields: ['name', 'glass_name', 'thickness_mm'],
	orderBy: 'name asc',
	limit: 100,
})

const profileList = useList<{
	name: string
	profile_code?: string
	profile_name?: string
	series?: string
	role?: string
	width_mm?: number
	depth_mm?: number
	section_svg?: string
	section_rotation?: string | number
	section_flip_x?: number | boolean
	section_flip_y?: number | boolean
}>({
	doctype: 'Fenestration Profile',
	fields: ['name', 'profile_code', 'profile_name', 'series', 'role', 'width_mm', 'depth_mm', 'section_svg', 'section_rotation', 'section_flip_x', 'section_flip_y'],
	orderBy: 'profile_code asc',
	limit: 500,
})

const catalogRows = ref<CatalogProfile[]>([])
async function loadProfileCatalog() {
	const rows: CatalogProfile[] = []
	let start = 0
	for (;;) {
		let res
		try { res = await profileCatalog(store.seriesVersion, start) } catch { break }
		if (!res.ok || !res.items) break
		rows.push(...res.items)
		if (res.next_start == null) break
		start = res.next_start
	}
	catalogRows.value = rows
	const widths: Record<string, number> = {}
	const roleDefaults: Record<string, string> = {}
	for (const r of rows) {
		if (!r.profile_code) continue
		const face = Number(r.width_mm) || 0
		if (face > 0) widths[r.profile_code] = face
		if (r.current_series !== false && r.role) {
			const role = String(r.role).toLowerCase()
			if (!roleDefaults[role]) roleDefaults[role] = r.profile_code
		}
	}
	store.setCatalogProfileMeta(widths, roleDefaults)
}
onMounted(() => void loadProfileCatalog())
watch(() => store.seriesVersion, () => void loadProfileCatalog())

const pickerOpen = ref(false)
const pickerRole = ref<'frame' | 'sash' | 'mullion' | 'transom' | 'bead' | 'all'>('all')
const pickerTargetKey = ref<string>('frame')
const profileAssignmentError = ref('')
const openProfileDropdown = ref<string | null>(null)

const activeSeriesBrand = computed(() => {
	const sv = (props.seriesVersions ?? []).find((s) => s.name === store.seriesVersion)
	return sv?.series || store.design.series || (store.seriesVersion ? store.seriesVersion.split('-')[0] : '') || 'CS400'
})

function toggleProfileDropdown(key: string) {
	openProfileDropdown.value = openProfileDropdown.value === key ? null : key
}

function profilesForDropdown(role: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead'): ResolvedProfilePreview[] {
	const list: ResolvedProfilePreview[] = []
	const seen = new Set<string>()
	const activeSeries = activeSeriesBrand.value.toLowerCase()
	for (const p of pickerProfiles.value) {
		if (!p.code || seen.has(p.code)) continue
		if (p.currentSeries === false) continue
		if (p.series && activeSeries && p.series.toLowerCase() !== activeSeries) continue
		if (!matchesRole(p.role, role)) continue
		seen.add(p.code)
		list.push(resolveProfilePreview(role, p.code))
	}
	return list
}

function selectDropdownProfile(role: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead', targetKey: string, code: string | undefined) {
	openProfileDropdown.value = null
	if (targetKey.startsWith('F1.')) {
		const side = targetKey.slice(3) as 'T' | 'L' | 'B' | 'R'
		onSetFrameSideProfile(side, code)
		return
	}
	if (role === 'frame') onSetFrameProfile(code)
	else if (role === 'sash') onSetRowSashProfile(code)
	else if (role === 'mullion' || role === 'transom') onSetGlobalBarProfile(role, code)
	else if (role === 'bead') onSetBeadProfile(code)
}

function assignProfile(action: () => void) {
	try {
		profileAssignmentError.value = ''
		action()
	} catch (error) {
		profileAssignmentError.value = error instanceof Error ? error.message : 'Could not assign this profile'
	}
}

const pickerProfiles = computed<ProfileItem[]>(() => {
	const activeSeries = activeSeriesBrand.value.toLowerCase()
	const fallbackRows: CatalogProfile[] = (profileList.data ?? []).map((r) => ({
		...r,
		code: r.profile_code || r.name,
		has_outline: Boolean(r.section_svg),
		current_series: !r.series || !activeSeries || r.series.toLowerCase() === activeSeries,
	}))
	const dbRows = [...catalogRows.value, ...fallbackRows].filter((r) => Boolean(r.profile_code || r.profile_name || r.code))
	const list: ProfileItem[] = []
	const seen = new Set<string>()

	for (const r of dbRows) {
		const code = r.profile_code || r.name
		if (!code || seen.has(code)) continue
		seen.add(code)
		const w = Number(r.width_mm || 0)
		const d = Number(r.depth_mm || 0)
		const maxW = store.seriesInfo?.profile_widths?.[code] ?? (w || d)
		list.push({
			code,
			name: r.profile_name || code,
			series: r.series,
			role: r.role,
			width_mm: w,
			depth_mm: d,
			maxWidth: maxW > 0 ? maxW : undefined,
			svg: r.section_svg,
			section_rotation: r.section_rotation,
			section_flip_x: r.section_flip_x,
			section_flip_y: r.section_flip_y,
			outline_transformed: r.outline_transformed,
			hasOutline: r.has_outline,
			currentSeries: r.current_series,
		})
	}

	for (const code of store.seriesInfo?.profiles ?? []) {
		if (seen.has(code)) continue
		seen.add(code)
		const maxW = store.seriesInfo?.profile_widths?.[code]
		list.push({
			code,
			name: code,
			series: store.seriesVersion,
			maxWidth: maxW,
		})
	}

	return list
})

function matchesRole(profileRole?: string, targetRole?: string): boolean {
	if (!profileRole || !targetRole) return false
	const p = profileRole.toLowerCase()
	const t = targetRole.toLowerCase()
	if (t === 'frame') return p === 'frame'
	if (t === 'sash') return p === 'sash'
	if (t === 'mullion' || t === 'transom') return p === 'mullion' || p === 'transom'
	if (t === 'bead') return p === 'bead'
	return p === t
}

function openProfilePicker(role: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead', targetKey: string) {
	pickerRole.value = role
	pickerTargetKey.value = targetKey
	pickerOpen.value = true
}

interface PendingPickerPrompt {
	role: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead'
	targetKey: string
}

const pendingPickerQueue = ref<PendingPickerPrompt[]>([])

function hasProfilesForRole(role: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead'): boolean {
	return pickerProfiles.value.some(
		(p) =>
			(p.currentSeries !== false || (store.seriesInfo?.profiles?.includes(p.code) ?? false)) &&
			(matchesRole(p.role, role) || !p.role),
	)
}

function promptProfilePickers(requests: PendingPickerPrompt[]) {
	const seen = new Set<string>()
	const eligible = requests.filter((req) => {
		const key = `${req.role}:${req.targetKey}`
		if (seen.has(key)) return false
		seen.add(key)
		return hasProfilesForRole(req.role)
	})
	if (!eligible.length) return
	if (!pickerOpen.value) {
		const [first, ...rest] = eligible
		pendingPickerQueue.value = [...pendingPickerQueue.value, ...rest]
		openProfilePicker(first.role, first.targetKey)
		return
	}
	pendingPickerQueue.value = [...pendingPickerQueue.value, ...eligible]
}

watch(pickerOpen, (open) => {
	if (!open && pendingPickerQueue.value.length > 0) {
		const [next, ...rest] = pendingPickerQueue.value
		pendingPickerQueue.value = rest
		openProfilePicker(next.role, next.targetKey)
	}
})

function onPickerSelect(code: string) {
	const targetRole = pickerRole.value
	const targetKey = pickerTargetKey.value
	const item = pickerProfiles.value.find((p) => p.code === code)
	const role = item?.role || targetRole
	const compatible =
		targetRole === 'mullion' || targetRole === 'transom'
			? role === 'mullion' || role === 'transom'
			: role === targetRole
	if (item && (!compatible || item.currentSeries === false) && typeof window !== 'undefined') {
		const reason = !compatible ? `is classified as ${role || 'unclassified'}` : 'belongs to another series'
		if (!window.confirm(`${code} ${reason}. Assign it anyway?`)) return
	}

	if (targetRole === 'frame') {
		assignProfile(() => store.setProfile('frame', targetKey || 'frame', code, role))
	} else if (targetRole === 'sash') {
		assignProfile(() => store.setProfile('sash', targetKey, code, role))
	} else if (targetRole === 'mullion' || targetRole === 'transom') {
		assignProfile(() => store.setProfile('bar', targetKey, code, role))
	} else if (targetRole === 'bead') {
		assignProfile(() => store.setProfile('bead', targetKey, code, role))
	}
}

function onSetFrameProfile(code: string | undefined) {
	const item = pickerProfiles.value.find((p) => p.code === code)
	assignProfile(() => store.setProfile('frame', 'frame', code, item?.role || 'frame'))
}

function onSetSashProfile(code: string | undefined) {
	const item = pickerProfiles.value.find((p) => p.code === code)
	const key =
		effectiveCellPath.value && effectiveCellPath.value !== 'FRAME' && effectiveCellPath.value !== 'F1'
			? effectiveCellPath.value
			: 'sash'
	assignProfile(() => store.setProfile('sash', key, code, item?.role || 'sash'))
}

function onSetBarProfile(code: string | undefined) {
	if (!selectedBar.value) return
	const item = pickerProfiles.value.find((p) => p.code === code)
	const barRole = selectedBar.value.dir === 'v' ? 'mullion' : 'transom'
	assignProfile(() => store.setProfile('bar', selectedBar.value!.id, code, item?.role || barRole))
}

function onSetGlobalSashProfile(code: string | undefined) {
	if (leaf.value?.type === 'sash') {
		onSetSashProfile(code)
		return
	}
	const item = pickerProfiles.value.find((p) => p.code === code)
	assignProfile(() => store.setProfile('sash', 'sash', code, item?.role || 'sash'))
}

function onSetGlobalBarProfile(role: 'mullion' | 'transom', code: string | undefined) {
	const item = pickerProfiles.value.find((p) => p.code === code)
	const matchesSelected =
		selectedBar.value &&
		((role === 'mullion' && selectedBar.value.dir === 'v') || (role === 'transom' && selectedBar.value.dir === 'h'))
	const targetId = matchesSelected ? selectedBar.value!.id : role
	assignProfile(() => store.setProfile('bar', targetId, code, item?.role || role))
}

function onSetBeadProfile(code: string | undefined) {
	const item = pickerProfiles.value.find((p) => p.code === code)
	assignProfile(() => store.setProfile('bead', activeBeadTargetKey.value, code, item?.role || 'bead'))
}

function getProfileDisplayLabel(role: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead', currentVal?: string) {
	if (!currentVal || currentVal === NONE) {
		const defCode =
			store.seriesInfo?.role_defaults?.[role] ??
			(store.result?.members ?? []).find((m) => m.role === role)?.profile
		return defCode ? `Series default (${defCode})` : 'Series default'
	}
	const item = pickerProfiles.value.find((p) => p.code === currentVal)
	if (item && item.name && item.name !== item.code) {
		return `${item.name} (${item.code})`
	}
	const dbRow = catalogRows.value.find((r) => (r.profile_code || r.name) === currentVal)
	if (dbRow && dbRow.profile_name && dbRow.profile_name !== currentVal) {
		return `${dbRow.profile_name} (${currentVal})`
	}
	return currentVal
}

async function refreshProfileCatalog() {
	await Promise.all([loadProfileCatalog(), Promise.resolve(profileList.reload?.())])
}

defineExpose({ openProfilePicker, promptProfilePickers, refreshProfileCatalog })

const MIXED_GLASS = '__MIXED__'

function cellHasGlass(node: LeafNode): boolean {
	if (node.type === 'louver') return node.bladeMaterial === 'glass'
	return !node.fan
}

const glassOptions = computed(() => {
	const codes = store.seriesInfo?.glasses
	const rows = (glassList.data ?? []).filter((g) => !codes || codes.includes(g.name))
	const opts = rows.map((g) => ({ label: `${g.glass_name || g.name} (${g.name})`, value: g.name }))
	const cur = activeGlassCell.value?.node.glass
	if (cur && !opts.some((o) => o.value === cur)) {
		const loaded = glassList.data !== undefined && glassList.data !== null && !glassList.list?.loading
		const note = codes && !codes.includes(cur) ? 'not in this series version' : 'unknown'
		opts.push({ label: loaded ? `${cur} (${note})` : cur, value: cur })
	}
	return opts
})

function buildProfileOptions(role: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead', currentVal?: string) {
	const defCode =
		store.seriesInfo?.role_defaults?.[role] ??
		(store.result?.members ?? []).find((m) => m.role === role)?.profile
	const defaultLabel = defCode ? `Series default (${defCode})` : 'Series default'
	const opts: { label: string; value: string }[] = [{ label: defaultLabel, value: NONE }]
	const seen = new Set<string>()
	const dbRows = catalogRows.value.filter((r) => Boolean(r.profile_code || r.profile_name))
	for (const r of dbRows) {
		const code = r.profile_code || r.name
		if (!code || seen.has(code)) continue
		if (!matchesRole(r.role, role)) continue
		seen.add(code)
		const label = r.profile_name && r.profile_name !== code ? `${r.profile_name} (${code})` : code
		opts.push({ label, value: code })
	}
	for (const code of store.seriesInfo?.profiles ?? []) {
		if (!code || seen.has(code)) continue
		const dbMatch = dbRows.find((r) => (r.profile_code || r.name) === code)
		if (!dbMatch || !matchesRole(dbMatch.role, role)) continue
		seen.add(code)
		opts.push({ label: code, value: code })
	}
	for (const m of store.result?.members ?? []) {
		if (!m.profile || seen.has(m.profile)) continue
		if (m.role && !matchesRole(m.role, role)) continue
		seen.add(m.profile)
		opts.push({ label: m.profile, value: m.profile })
	}
	if (currentVal && currentVal !== NONE && !seen.has(currentVal)) {
		const dbMatch = dbRows.find((r) => (r.profile_code || r.name) === currentVal)
		if (dbMatch && dbMatch.role && !matchesRole(dbMatch.role, role)) {
			opts.push({
				label: `${dbMatch.profile_name || currentVal} (${currentVal} - Invalid: ${dbMatch.role} profile)`,
				value: currentVal,
			})
		} else {
			opts.push({ label: currentVal, value: currentVal })
		}
	}
	return opts
}

const isFrameSelected = computed(() => store.selectedPath === 'FRAME' || (store.selectedPath === 'F1' && store.design.root.type === 'split'))
const isGrillSelected = computed(() => store.selectedPath.startsWith('GRILL:'))
const isGlassSelected = computed(() => store.selectedPath.startsWith('GLASS:'))
const effectiveCellPath = computed(() => store.selectedPath.replace(/^(GLASS|BEAD|GRILL):/, ''))

const frameProfileValue = computed(() => store.design.frameProfileId ?? store.design.profiles?.frame ?? NONE)
const frameProfileOptions = computed(() => buildProfileOptions('frame', frameProfileValue.value))
const frameMember = computed(() => (store.result?.members ?? []).find((m) => m.role === 'frame') ?? null)

const sashProfileValue = computed(() => {
	if (leaf.value?.type === 'sash' && leaf.value.profile) return leaf.value.profile
	const pathOverride = effectiveCellPath.value && store.design.profiles?.[effectiveCellPath.value]
	if (pathOverride) return pathOverride
	return store.design.sashProfileId ?? store.design.profiles?.sash ?? NONE
})
const sashProfileOptions = computed(() => buildProfileOptions('sash', sashProfileValue.value))

const selectedBarRole = computed<'mullion' | 'transom'>(() => (selectedBar.value?.dir === 'v' ? 'mullion' : 'transom'))
const barProfileValue = computed(() => {
	const b = selectedBar.value
	if (!b) return store.design.mullionProfileId ?? store.design.profiles?.mullion ?? NONE
	return store.design.profiles?.[b.id] ?? store.design.mullionProfileId ?? store.design.profiles?.mullion ?? NONE
})
const barProfileOptions = computed(() => buildProfileOptions(selectedBarRole.value, barProfileValue.value))

const beadedCells = computed(() => geom.value.cells.filter((c) => c.node.type === 'fixed' && !c.node.fan && c.node.bead !== false))
const scopedBeadCell = computed(() => {
	if (isBeadSelected.value && effectiveCellPath.value) {
		return beadedCells.value.find((c) => c.path === effectiveCellPath.value) ?? null
	}
	if (selectedGlassCell.value) {
		return beadedCells.value.find((c) => c.path === selectedGlassCell.value!.path) ?? null
	}
	return null
})
const activeBeadTargetKey = computed(() =>
	scopedBeadCell.value && beadedCells.value.length > 1 ? scopedBeadCell.value.path : 'bead',
)
const beadProfileValue = computed(() => {
	if (activeBeadTargetKey.value !== 'bead' && scopedBeadCell.value) {
		return (
			scopedBeadCell.value.node.beadProfileId ??
			store.design.profiles?.[`${scopedBeadCell.value.path}:bead`] ??
			store.design.beadProfileId ??
			store.design.profiles?.bead ??
			NONE
		)
	}
	return (
		store.design.beadProfileId ??
		store.design.profiles?.bead ??
		(beadedCells.value.length === 1 ? beadedCells.value[0].node.beadProfileId : undefined) ??
		NONE
	)
})
const beadProfileOptions = computed(() => buildProfileOptions('bead', beadProfileValue.value))

const beadJointOptions = [
	{ label: 'Mitre 45°', value: 'm' },
	{ label: 'Butt 90° (client sheet)', value: 'b' },
]
const beadJointValue = computed(() => store.design.beadJoint || 'm')
function onSetBeadJoint(val: string) {
	store.apply((d) => ({ ...d, beadJoint: val as 'm' | 'b' }))
}

const beadOffsetAlong = computed(() => {
	const beadCode = beadProfileValue.value !== NONE ? beadProfileValue.value : undefined
	const mapEntry = (beadCode && store.design.sectionMap?.[`bead:${beadCode}`]) || store.design.sectionMap?.['bead']
	if (mapEntry && typeof mapEntry.offsetAlong === 'number') return mapEntry.offsetAlong
	return store.design.beadOffset?.along ?? 0
})

const beadOffsetDepth = computed(() => {
	const beadCode = beadProfileValue.value !== NONE ? beadProfileValue.value : undefined
	const mapEntry = (beadCode && store.design.sectionMap?.[`bead:${beadCode}`]) || store.design.sectionMap?.['bead']
	if (mapEntry && typeof mapEntry.offsetDepth === 'number') return mapEntry.offsetDepth
	if (store.design.beadOffset?.depth !== undefined) return store.design.beadOffset.depth
	return 23
})

function onSetBeadOffset(along: number, depth: number) {
	store.apply((d) => {
		const beadCode = beadProfileValue.value !== NONE ? beadProfileValue.value : d.profiles?.bead || d.beadProfileId
		const nextMap = { ...(d.sectionMap ?? {}) }
		const key = beadCode ? `bead:${beadCode}` : 'bead'
		const existing = nextMap[key] ?? { offsetAlong: 0, offsetDepth: 23, rotation: 0, flipX: false, flipY: false }
		nextMap[key] = { ...existing, offsetAlong: along, offsetDepth: depth }
		return { ...d, beadOffset: { along, depth }, sectionMap: nextMap }
	})
}

const globalHingeOptions = [
	{ label: 'Auto (outer sides)', value: 'auto' },
	{ label: 'Left', value: 'left' },
	{ label: 'Right', value: 'right' },
	{ label: 'Top hung', value: 'top' },
]
const globalHingeValue = computed(() => store.design.hinge || 'auto')
function onSetGlobalHinge(val: string) {
	store.apply((d) => ({ ...d, hinge: val as 'auto' | 'left' | 'right' | 'top' }))
}

const geom = computed(() => layoutGeom(store.design))
const selectedCellGeom = computed(() => geom.value.cells.find((c) => c.path === effectiveCellPath.value) ?? null)
const selectedBar = computed(() => geom.value.bars.find((b) => b.id === store.selectedPath) ?? null)
const barMember = computed(() => {
	if (!selectedBar.value) return null
	return (
		(store.result?.members ?? []).find(
			(m) => m.panel === selectedBar.value?.id || m.path === selectedBar.value?.id,
		) ?? null
	)
})

const effectiveFrameFace = computed(() => {
	const widths = store.seriesInfo?.profile_widths
	if (widths) {
		const code = store.design.frameProfileId || store.design.profiles?.frame || frameMember.value?.profile
		if (code && widths[code]) return widths[code]
	}
	return FRAME_FACE_DEFAULT
})

const effectiveSashFace = computed(() => {
	const widths = store.seriesInfo?.profile_widths
	if (widths && leaf.value?.type === 'sash') {
		const code =
			leaf.value.profile ||
			store.design.profiles?.[effectiveCellPath.value] ||
			store.design.profiles?.sash
		if (code && widths[code]) return widths[code]
	}
	return SASH_FACE_DEFAULT
})

const effectiveBarFace = computed(() => {
	const widths = store.seriesInfo?.profile_widths
	const b = selectedBar.value
	if (widths && b) {
		const role = b.dir === 'v' ? 'mullion' : 'transom'
		const code =
			store.design.profiles?.[b.id] || store.design.profiles?.[role] || barMember.value?.profile
		if (code && widths[code]) return widths[code]
	}
	return BAR_FACE_DEFAULT
})

const barCutLength = computed(() => {
	const b = selectedBar.value
	if (!b) return '—'
	if (barMember.value?.length !== undefined) {
		return `${Number(barMember.value.length).toFixed(0)} mm`
	}
	const { width, height } = store.design
	const ff = effectiveFrameFace.value
	const bf = effectiveBarFace.value
	if (b.dir === 'v') {
		const bIn = b.y === 0 ? ff : bf / 2
		const tIn = b.y + b.length === height ? ff : bf / 2
		return `${Math.max(0, b.length - bIn - tIn).toFixed(0)} mm`
	}
	const lIn = b.x === 0 ? ff : bf / 2
	const rIn = b.x + b.length === width ? ff : bf / 2
	return `${Math.max(0, b.length - lIn - rIn).toFixed(0)} mm`
})

const selectedLabel = computed(() => panelLabel(effectiveCellPath.value, store.result))
const glassRow = computed(() => store.result?.glass.find((g) => g.path === effectiveCellPath.value) ?? null)
const glassCut = computed(() => {
	const row = glassRow.value
	const mm = (v: number | undefined) => (typeof v === 'number' ? v.toFixed(1) : null)
	const w = mm(row?.width)
	const h = mm(row?.height)
	return w && h ? `${w} × ${h} mm` : '—'
})

const infillLabel = computed(() => leaf.value?.fan && leaf.value.type !== 'louver' ? 'Steel' : 'Glass')
const grillFields: {key: keyof Grill; label: string}[] = [{key:'vertical',label:'Vertical bars'}, {key:'horizontal',label:'Horizontal bars'}, {key:'width',label:'Bar width (mm)'}, {key:'depth',label:'Bar depth (mm)'}, {key:'offset',label:'Depth position (mm)'}, {key:'inset',label:'Edge inset (mm)'}, {key:'shiftX',label:'Horizontal offset (mm)'}, {key:'shiftY',label:'Vertical offset (mm)'}]
function patchGrill(key: keyof Grill, value: number) {
 patchLeaf({ grill: grillConfig({ ...leaf.value?.grill, [key]: value }) })
}
const fanDimensions = computed(() => {
	const width = glassRow.value?.width ?? Number.parseFloat(glassDims.value.w)
	const height = glassRow.value?.height ?? Number.parseFloat(glassDims.value.h)
	const config = leaf.value?.fanCut ?? {}
	const diameter = config.diameter ?? 180
	return { width, height, diameter, centerX: config.centerX ?? width / 2, centerY: config.centerY ?? height / 2 }
})
const fanCutInvalid = computed(() => Boolean(leaf.value?.fan && !exhaustCut(leaf.value, fanDimensions.value.width, fanDimensions.value.height)))
function patchFanCut(field: 'diameter' | 'centerX' | 'centerY', value: number) {
	patchLeaf({ fanCut: { ...leaf.value?.fanCut, [field]: value } })
}

const glassDims = computed(() => {
	const row = glassRow.value
	if (typeof row?.width === 'number' && typeof row?.height === 'number') {
		return { w: `${row.width.toFixed(1)} mm`, h: `${row.height.toFixed(1)} mm` }
	}
	const c = selectedCellGeom.value
	if (!c) return { w: '—', h: '—' }
	const { width, height } = store.design
	const ff = effectiveFrameFace.value
	const bf = effectiveBarFace.value
	const sf = effectiveSashFace.value
	const l = c.x === 0 ? ff : bf / 2
	const r = c.x + c.w === width ? ff : bf / 2
	const b = c.y === 0 ? ff : bf / 2
	const t = c.y + c.h === height ? ff : bf / 2
	const sashIn = c.node.type === 'sash' ? sf * 2 : 0
	return {
		w: `${Math.max(0, c.w - l - r - sashIn).toFixed(1)} mm`,
		h: `${Math.max(0, c.h - t - b - sashIn).toFixed(1)} mm`,
	}
})

const sashDims = computed(() => {
	if (leaf.value?.type !== 'sash') return { w: '—', h: '—' }
	const members = (store.result?.members ?? []).filter(
		(m) => m.path === effectiveCellPath.value && m.role === 'sash',
	)
	const wMember = members.find((m) => m.position === 'B' || m.position === 'T')
	const hMember = members.find((m) => m.position === 'L' || m.position === 'R')
	if (wMember?.length !== undefined && hMember?.length !== undefined) {
		return {
			w: `${Number(wMember.length).toFixed(0)} mm`,
			h: `${Number(hMember.length).toFixed(0)} mm`,
		}
	}
	const c = selectedCellGeom.value
	if (!c) return { w: '—', h: '—' }
	const { width, height } = store.design
	const ff = effectiveFrameFace.value
	const bf = effectiveBarFace.value
	const l = c.x === 0 ? ff : bf / 2
	const r = c.x + c.w === width ? ff : bf / 2
	const b = c.y === 0 ? ff : bf / 2
	const t = c.y + c.h === height ? ff : bf / 2
	return {
		w: `${Math.max(0, c.w - l - r).toFixed(0)} mm`,
		h: `${Math.max(0, c.h - t - b).toFixed(0)} mm`,
	}
})

const sashSize = computed(() => {
	if (leaf.value?.type !== 'sash') return '—'
	const members = (store.result?.members ?? []).filter(
		(m) => m.path === effectiveCellPath.value && m.role === 'sash',
	)
	const wMember = members.find((m) => m.position === 'B' || m.position === 'T')
	const hMember = members.find((m) => m.position === 'L' || m.position === 'R')
	if (wMember && hMember) {
		return `${Number(wMember.length).toFixed(0)} × ${Number(hMember.length).toFixed(0)} mm`
	}
	return '—'
})

const frictionStayLabel = computed(() => {
	if (leaf.value?.type !== 'sash') return '—'
	const panel = selectedLabel.value
	const stay = (store.result?.bom ?? []).find(
		(b) =>
			b.panel === panel &&
			(b.item.startsWith('H416') ||
				b.item.startsWith('H417') ||
				b.name.toLowerCase().includes('stay') ||
				b.name.toLowerCase().includes('hinge')),
	)
	if (stay) {
		if (stay.item === 'H417' || stay.name.includes('14')) return '14" (auto)'
		return '12" (auto)'
	}
	return '12" (auto)'
})

const espagLabel = computed(() => {
	if (leaf.value?.type !== 'sash') return '—'
	if (leaf.value.lock === 'singlepoint') return 'Single-point handle'
	if (leaf.value.lock === 'none') return 'None'
	const panel = selectedLabel.value
	const rod = (store.result?.bom ?? []).find(
		(b) =>
			b.panel === panel &&
			(b.item.startsWith('H422') ||
				b.name.toLowerCase().includes('espag') ||
				b.name.toLowerCase().includes('rod')),
	)
	if (rod) {
		if (rod.item === 'H422A' || rod.name.includes('600')) return '600 mm (auto)'
		if (rod.item === 'H422B' || rod.name.includes('800')) return '800 mm (auto)'
		return '1200 mm (auto)'
	}
	return '1200 mm (auto)'
})

const NONE = 'none'
const finishOptions = (list: { name: string; finish_name: string }[] = []) =>
	list.map((f) => ({ label: f.finish_name || f.name, value: f.name }))

const seriesVersionOptions = computed(() => {
	const list = props.seriesVersions ?? []
	const opts = list.map((sv) => ({
		label: `${sv.series} · ${sv.name}`,
		value: sv.name,
	}))
	if (store.seriesVersion && !opts.some((o) => o.value === store.seriesVersion)) {
		opts.unshift({ label: store.seriesVersion, value: store.seriesVersion })
	}
	return opts
})

function finishColorFor(code: string | number | undefined): string {
	return (props.finishes ?? []).find((f) => f.name === String(code ?? ''))?.color || '#8A8F98'
}

function onSelectWholeFinish(code: string) {
	if (store.design.colorMode !== 'dual' && store.design.finishOutside) {
		store.apply((d) => {
			const { finishOutside: _, ...rest } = d
			return rest
		})
	}
	store.setFinish(code)
}

const colorMode = computed<ColorMode>(() => store.design.colorMode ?? 'single')
function setColorMode(mode: ColorMode) {
	store.apply((d) => ({
		...d,
		colorMode: mode,
		finishOutside: mode === 'dual' ? (d.finishOutside || store.finish || undefined) : undefined,
	}))
}
function setOutsideFinish(code: string) {
	store.apply((d) => ({
		...d,
		colorMode: 'dual',
		finishOutside: code || undefined,
	}))
}

const frameConfig = computed<FrameConfig>(() => store.design.frameConfig ?? '4-side')
function warnIfUnsupportedProduct(product: 'Window' | 'Door' | 'Sliding Window' | 'Sliding Door') {
	const supported = store.seriesInfo?.supported_products ?? []
	if (!supported.length || supported.includes(product)) return
	toast.warning(
		`Series ${activeSeriesBrand.value} does not contain profiles for ${product} assemblies (supported: ${supported.join(', ')}).`,
	)
}
function setFrameConfig(cfg: FrameConfig) {
	store.apply((d) => ({
		...d,
		frameConfig: cfg,
	}))
	if (cfg !== '4-side') {
		warnIfUnsupportedProduct(store.design.isSliding ? 'Sliding Door' : 'Door')
	}
}
const frameSidesList = computed(() => {
	const all: { side: 'T' | 'L' | 'B' | 'R'; label: string }[] = [
		{ side: 'T', label: 'Top' },
		{ side: 'L', label: 'Left' },
		{ side: 'B', label: 'Bottom' },
		{ side: 'R', label: 'Right' },
	]
	return frameConfig.value === '3-side' ? all.filter((s) => s.side !== 'B') : all
})
function frameSideCode(side: 'T' | 'L' | 'B' | 'R'): string {
	return store.design.profiles?.[`F1.${side}`] || frameProfileValue.value || 'Rule default'
}
function isFrameSideOverridden(side: 'T' | 'L' | 'B' | 'R'): boolean {
	return Boolean(store.design.frameOverridden?.[side] || store.design.profiles?.[`F1.${side}`])
}
function resetFrameSideOverride(side: 'T' | 'L' | 'B' | 'R') {
	store.setProfile('frame', `F1.${side}`, undefined)
}

const activeSashHingeCount = computed(() => {
	const cell = activeSashCell.value
	if (!cell || cell.node.type !== 'sash') return 0
	const isDoor = cell.node.sashConfig === 'door'
	const h = Number(activeSashDims.value.h) || cell.h
	const kg = Number((store.result?.shutter_kg as Record<string, number> | undefined)?.[cell.path] ?? 0)
	if (isDoor) {
		let n = h >= 2100 ? 5 : h >= 1400 ? 4 : 3
		if (kg >= 65) n += 2
		else if (kg >= 45) n += 1
		return Math.min(6, n)
	}
	let n = h >= 1600 ? 4 : h >= 1100 ? 3 : 2
	if (kg >= 50) n += 2
	else if (kg >= 30) n += 1
	return Math.min(5, n)
})

const selectorBoxStyle = {
	width: '100%',
	minHeight: '48px',
	padding: '6px 10px',
	border: '1px solid #d5dbe3',
	borderRadius: '7px',
	background: '#ffffff',
	boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
	display: 'flex',
	alignItems: 'center',
	justifyContent: 'space-between',
	gap: '8px',
	cursor: 'pointer',
	color: '#0f172a',
	textAlign: 'left' as const,
	fontSize: '12px',
	fontWeight: '600',
	transition: 'border-color 150ms ease, box-shadow 150ms ease',
}

const OPENINGS = [
	{ label: 'None', value: NONE },
	{ label: 'Inward', value: 'in' },
	{ label: 'Outward', value: 'out' },
]
const HINGES = [
	{ label: 'None', value: NONE },
	{ label: 'Left', value: 'left' },
	{ label: 'Right', value: 'right' },
	{ label: 'Top', value: 'top' },
	{ label: 'Bottom', value: 'bottom' },
]
const LOCKS = [
	{ label: 'Multi-point', value: 'multipoint' },
	{ label: 'Single-point', value: 'singlepoint' },
	{ label: 'None', value: 'none' },
]
const HINGE_TYPES = [
	{ label: 'Series default', value: NONE },
	{ label: 'Friction', value: 'friction' },
	{ label: 'Butt', value: 'butt' },
]
const YES = 'yes'
const NO = 'no'
function flagOptions(key: 'limiter' | 'mesh') {
	const def = store.seriesInfo?.defaults[key]
	const label = def === undefined ? 'Series default' : `Series default (${def ? 'Yes' : 'No'})`
	return [{ label, value: NONE }, { label: 'Yes', value: YES }, { label: 'No', value: NO }]
}
const limiterOptions = computed(() => flagOptions('limiter'))
const meshOptions = computed(() => flagOptions('mesh'))
const flagValue = (v: boolean | undefined) => (v === undefined ? NONE : v ? YES : NO)
const flagPatch = (v: string | number | null) => (v === YES ? true : v === NO ? false : undefined)
const HANDLES = [
	{ label: 'Series default', value: NONE },
	{ label: 'Multipoint', value: 'multipoint' },
	{ label: 'Single point', value: 'single' },
]

function nodeAt(path: string): DesignNode | null {
	try {
		return getNode(store.design, path)
	} catch {
		return null
	}
}
const leaf = computed(() => {
	if (!effectiveCellPath.value || isFrameSelected.value) return null
	const n = nodeAt(effectiveCellPath.value)
	return n && n.type !== 'split' ? n : null
})
const glassCells = computed(() => geom.value.cells.filter((c) => cellHasGlass(c.node)))
const hasGlass = computed(() => glassCells.value.length > 0)
const hasMullion = computed(() => geom.value.bars.some((b) => b.dir === 'v'))
const hasTransom = computed(() => geom.value.bars.some((b) => b.dir === 'h'))
const hasSash = computed(() => geom.value.cells.some((c) => c.node.type === 'sash'))
const hasBeadCatalogProfiles = computed(() =>
	pickerProfiles.value.some(
		(p) => matchesRole(p.role, 'bead') && (p.currentSeries !== false || (store.seriesInfo?.profiles?.includes(p.code) ?? false)),
	),
)
const hasActiveBead = computed(() => {
	if (isBeadSelected.value) return true
	if (!beadedCells.value.length) return false
	return Boolean(
		store.design.beadProfileId ||
			store.design.profiles?.bead ||
			store.seriesInfo?.role_defaults?.bead ||
			hasBeadCatalogProfiles.value ||
			geom.value.cells.some((c) => c.node.type !== 'louver' && !c.node.fan && Boolean(c.node.beadProfileId)) ||
			(store.result?.members ?? []).some((m) => m.role === 'bead'),
	)
})

const globalGlassCodes = computed(() =>
	Array.from(new Set(glassCells.value.map((c) => c.node.glass).filter(Boolean))),
)
const globalGlassValue = computed(() => {
	if (globalGlassCodes.value.length === 1) return globalGlassCodes.value[0]
	if (globalGlassCodes.value.length > 1) return MIXED_GLASS
	return ''
})

const glassPickerOpen = ref(false)
const pickerGlasses = computed<GlassItem[]>(() => {
	const allowed = store.seriesInfo?.glasses
	const list: GlassItem[] = []
	const seen = new Set<string>()
	for (const g of glassList.data ?? []) {
		if (!g.name || seen.has(g.name)) continue
		seen.add(g.name)
		list.push({
			code: g.name,
			name: g.glass_name || g.name,
			thickness_mm: g.thickness_mm ? Number(g.thickness_mm) : undefined,
			inSeries: !allowed || allowed.includes(g.name),
		})
	}
	for (const code of allowed ?? []) {
		if (!code || seen.has(code)) continue
		seen.add(code)
		list.push({ code, name: code, inSeries: true })
	}
	return list
})

const globalGlassDisplayLabel = computed(() => {
	if (globalGlassCodes.value.length > 1) return 'Mixed (per panel)'
	const code = globalGlassValue.value
	if (!code) return 'Select glass'
	const item = (glassList.data ?? []).find((g) => g.name === code)
	if (item?.glass_name && item.glass_name !== code) return `${item.glass_name} (${code})`
	return code
})

function openGlassPicker() {
	glassPickerOpen.value = true
}

function setDesignGlass(node: DesignNode, glass: string): DesignNode {
	if (node.type === 'split') {
		return { ...node, children: node.children.map((c) => setDesignGlass(c, glass)) }
	}
	if (!cellHasGlass(node)) return node
	return { ...node, glass }
}

function onSetGlobalGlass(glass: string) {
	if (!glass || glass === MIXED_GLASS) return
	store.apply((d) => ({ ...d, root: setDesignGlass(d.root, glass) }))
}

const globalSashProfileValue = computed(() => {
	if (leaf.value?.type === 'sash') return sashProfileValue.value
	const sashCells = geom.value.cells.filter((c) => c.node.type === 'sash')
	const explicit = Array.from(
		new Set(
			sashCells
				.map((c) => (c.node.type === 'sash' ? c.node.profile : undefined) ?? store.design.profiles?.[c.path])
				.filter((p): p is string => Boolean(p)),
		),
	)
	if (sashCells.length > 0 && explicit.length === 1 && sashCells.every((c) => ((c.node.type === 'sash' ? c.node.profile : undefined) ?? store.design.profiles?.[c.path]) === explicit[0])) {
		return explicit[0]
	}
	return store.design.sashProfileId ?? store.design.profiles?.sash ?? NONE
})
const globalSashProfileOptions = computed(() => buildProfileOptions('sash', globalSashProfileValue.value))

function resolveGlobalBarProfile(dir: 'v' | 'h', fallback: string | undefined): string {
	if (selectedBar.value?.dir === dir) return barProfileValue.value
	const bars = geom.value.bars.filter((b) => b.dir === dir)
	const overrides = Array.from(
		new Set(bars.map((b) => store.design.profiles?.[b.id]).filter((p): p is string => Boolean(p))),
	)
	if (bars.length > 0 && overrides.length === 1 && bars.every((b) => store.design.profiles?.[b.id] === overrides[0])) {
		return overrides[0]
	}
	return fallback ?? NONE
}

const globalMullionProfileValue = computed(() =>
	resolveGlobalBarProfile('v', store.design.mullionProfileId ?? store.design.profiles?.mullion),
)
const globalMullionProfileOptions = computed(() => buildProfileOptions('mullion', globalMullionProfileValue.value))

const globalTransomProfileValue = computed(() =>
	resolveGlobalBarProfile('h', store.design.profiles?.transom ?? store.design.mullionProfileId),
)
const globalTransomProfileOptions = computed(() => buildProfileOptions('transom', globalTransomProfileValue.value))

type ProfileRoleKey = 'frame' | 'sash' | 'mullion' | 'transom' | 'bead'

interface ResolvedProfilePreview {
	code: string
	title: string
	subtitle: string
	svg?: string
	transform?: string
	viewBox: string
}

function resolveProfilePreview(role: ProfileRoleKey, currentVal?: string): ResolvedProfilePreview {
	const fallbackRoleCode =
		store.seriesInfo?.role_defaults?.[role] ??
		(role === 'transom' ? store.seriesInfo?.role_defaults?.mullion : undefined) ??
		(store.result?.members ?? []).find((m) => m.role === role)?.profile ??
		(role === 'transom' ? (store.result?.members ?? []).find((m) => m.role === 'mullion')?.profile : undefined) ??
		''
	const code = currentVal && currentVal !== NONE ? currentVal : fallbackRoleCode
	if (!code) {
		return {
			code: '',
			title: role === 'bead' ? 'Select bead profile' : 'Select profile',
			subtitle: '',
			viewBox: '-5 -5 80 80',
		}
	}
	const item = pickerProfiles.value.find((p) => p.code === code)
	const dbRow = catalogRows.value.find((r) => (r.profile_code || r.name) === code)
	const name =
		(item?.name && item.name !== code ? item.name : undefined) ??
		(dbRow?.profile_name && dbRow.profile_name !== code ? dbRow.profile_name : undefined)
	const w = item?.width_mm ?? dbRow?.width_mm
	const d = item?.depth_mm ?? dbRow?.depth_mm
	const dims = w && d ? `${Math.round(w)} × ${Math.round(d)} mm` : ''
	const svg = item?.svg ?? dbRow?.section_svg
	const orientationSource = item ?? dbRow
	const thumbMeta = {
		svg,
		width_mm: w,
		depth_mm: d,
		section_rotation: orientationSource?.section_rotation,
		section_flip_x: orientationSource?.section_flip_x,
		section_flip_y: orientationSource?.section_flip_y,
		outline_transformed: orientationSource?.outline_transformed,
	}
	return {
		code,
		title: name || code,
		subtitle: [name ? code : '', dims].filter(Boolean).join(' · '),
		svg,
		transform: profileThumbTransform(thumbMeta),
		viewBox: transformedPathViewBox(thumbMeta),
	}
}

const pickerCurrentProfile = computed(() => {
	const targetRole = pickerRole.value === 'all' ? 'frame' : pickerRole.value
	if (pickerTargetKey.value === 'frame') return resolveProfilePreview('frame', frameProfileValue.value).code
	if (pickerRole.value === 'bead') {
		const node = pickerTargetKey.value !== 'bead' ? nodeAt(pickerTargetKey.value) : null
		const override =
			(node && node.type !== 'split' ? node.beadProfileId : undefined) ??
			(pickerTargetKey.value !== 'bead' ? store.design.profiles?.[`${pickerTargetKey.value}:bead`] : undefined)
		return resolveProfilePreview('bead', override ?? beadProfileValue.value).code
	}
	if (pickerRole.value === 'sash') {
		const node = pickerTargetKey.value !== 'sash' ? nodeAt(pickerTargetKey.value) : null
		const override =
			(node && node.type === 'sash' ? node.profile : undefined) ??
			(pickerTargetKey.value !== 'sash' ? store.design.profiles?.[pickerTargetKey.value] : undefined)
		return resolveProfilePreview('sash', override ?? globalSashProfileValue.value).code
	}
	if (pickerRole.value === 'mullion' || pickerRole.value === 'transom') {
		const isGlobalKey = pickerTargetKey.value === 'mullion' || pickerTargetKey.value === 'transom'
		const override = !isGlobalKey ? store.design.profiles?.[pickerTargetKey.value] : undefined
		const fallback = pickerRole.value === 'mullion' ? globalMullionProfileValue.value : globalTransomProfileValue.value
		return resolveProfilePreview(pickerRole.value, override ?? fallback).code
	}
	return resolveProfilePreview(targetRole, barProfileValue.value).code
})
const splitPath = computed(() => {
	const p = effectiveCellPath.value
	if (!p || isFrameSelected.value) return ''
	if (selectedBar.value) return selectedBar.value.splitPath
	return nodeAt(p)?.type === 'split' ? p : p.split('.').slice(0, -1).join('.')
})
const split = computed<SplitNode | null>(() => {
	const n = splitPath.value ? nodeAt(splitPath.value) : null
	return n && n.type === 'split' ? n : null
})

const activeIssues = computed(() => store.result?.issues ?? [])

function num(e: Event): number {
	return Number((e.target as HTMLInputElement).value)
}
function resize(w: number, h: number) {
	if (!(w > 0 && h > 0)) return
	store.apply((d) => setSize(d, w, h))
}
function patchLeaf(patch: Partial<LeafNode>) {
	if (!leaf.value) return
	const next = Object.fromEntries(
		Object.entries({ ...leaf.value, ...patch }).filter(([, v]) => v !== undefined),
	) as unknown as LeafNode
	store.apply((d) => setLeaf(d, effectiveCellPath.value, next))
 if (isGrillSelected.value && !next.grill) store.select(effectiveCellPath.value)
}
function moveBar(i: number, e: Event) {
	const pos = num(e)
	store.apply((d) => moveSplit(d, splitPath.value, i, pos))
}
function onRemoveSplit() {
	if (!splitPath.value) return
	const target = splitPath.value
	store.apply((d) => removeSplit(d, target))
	store.select(target)
}
const optStr = <T extends string = string>(v: string | number | null) =>
	v && v !== NONE ? (String(v) as T) : undefined
function optNum(e: Event): number | undefined {
	const v = (e.target as HTMLInputElement).value
	return v === '' ? undefined : Number(v)
}



const selectedBarPct = computed(() => {
	const b = selectedBar.value
	const s = split.value
	if (!b || !s) return 50
	const pos = s.at[b.index] ?? 0
	const total = s.dir === 'v' ? store.design.width : store.design.height
	return total > 0 ? Math.round((pos / total) * 100) : 50
})
function onBarSliderInput(e: Event) {
	const b = selectedBar.value
	const s = split.value
	if (!b || !s) return
	const pct = Number((e.target as HTMLInputElement).value)
	const total = s.dir === 'v' ? store.design.width : store.design.height
	const newPos = Math.round((pct / 100) * total)
	store.apply((d) => moveSplit(d, splitPath.value, b.index, newPos))
}

const isBeadSelected = computed(() => store.selection.kind === 'bead' || store.selectedPath.startsWith('BEAD:'))

const activeSegmentStyle = {
	height: '28px',
	border: '0',
	borderRadius: '6px',
	background: '#ffffff',
	fontSize: '12px',
	fontWeight: '600',
	cursor: 'pointer',
	color: '#14171c',
	boxShadow: '0 1px 2px rgba(20,23,28,0.12)',
}

const inactiveSegmentStyle = {
	height: '28px',
	border: '0',
	borderRadius: '6px',
	background: 'transparent',
	fontSize: '12px',
	fontWeight: '500',
	cursor: 'pointer',
	color: '#5b6472',
}

const syncBaseStyle = {
	fontSize: '12px',
	borderRadius: '6px',
	padding: '3px 10px',
	border: 'none',
	cursor: 'pointer',
}

const syncOnStyle = {
	...syncBaseStyle,
	fontWeight: '600',
	color: '#ffffff',
	background: '#1d6fdc',
}

const syncOffStyle = {
	...syncBaseStyle,
	fontWeight: '500',
	color: '#5b6472',
	background: '#eef0f3',
}

function onResetBead() {
	store.apply((d) => {
		const next = { ...(d.sectionMap ?? {}) }
		for (const k of Object.keys(next)) {
			if (k.toLowerCase().includes('bead')) {
				delete next[k]
			}
		}
		return { ...d, sectionMap: next }
	})
}

function onSetBeadAsDefault() {
	const code = beadProfileValue.value
	if (code && code !== NONE) {
		store.setProfile('bead', 'bead', code)
	}
}

const hasObjectSelected = computed(
	() => isBeadSelected.value || isFrameSelected.value || isGlassSelected.value || !!leaf.value || !!selectedBar.value,
)

interface GeomCell {
	path: string
	x: number
	y: number
	w: number
	h: number
	node: LeafNode
}

type GeomBar = (typeof geom.value.bars)[number]

function activeCellFor(predicate: (cell: GeomCell) => boolean): GeomCell | null {
	if (selectedCellGeom.value && predicate(selectedCellGeom.value)) return selectedCellGeom.value
	return geom.value.cells.find(predicate) ?? null
}

function activeBarFor(dir: 'v' | 'h'): GeomBar | null {
	if (selectedBar.value?.dir === dir) return selectedBar.value
	return geom.value.bars.find((b) => b.dir === dir) ?? null
}

function cellLabel(path: string): string {
	return panelLabel(path, store.result)
}

const selectedGlassCell = computed<GeomCell | null>(() =>
	selectedCellGeom.value && cellHasGlass(selectedCellGeom.value.node) ? selectedCellGeom.value : null,
)
const activeGlassCell = computed<GeomCell | null>(() => activeCellFor((c) => cellHasGlass(c.node)))
const sashCells = computed<GeomCell[]>(() => geom.value.cells.filter((c) => c.node.type === 'sash'))
const activeSashCell = computed<GeomCell | null>(() => activeCellFor((c) => c.node.type === 'sash'))
const louverCells = computed<GeomCell[]>(() => geom.value.cells.filter((c) => c.node.type === 'louver'))
const activeLouverCell = computed<GeomCell | null>(() => activeCellFor((c) => c.node.type === 'louver'))
const fanCells = computed<GeomCell[]>(() =>
	geom.value.cells.filter((c) => c.node.type !== 'louver' && Boolean(c.node.fan)),
)
const activeFanCell = computed<GeomCell | null>(() =>
	activeCellFor((c) => c.node.type !== 'louver' && Boolean(c.node.fan)),
)
const grillCells = computed<GeomCell[]>(() => geom.value.cells.filter((c) => Boolean(c.node.grill)))
const activeGrillCell = computed<GeomCell | null>(() => activeCellFor((c) => Boolean(c.node.grill)))

function formatGlassName(code?: string): string {
	if (!code) return 'Select glass'
	const item = (glassList.data ?? []).find((g) => g.name === code)
	if (item?.glass_name && item.glass_name !== code) return `${item.glass_name} (${code})`
	return code
}

const glassDisplayText = computed(() => {
	if (selectedGlassCell.value) return formatGlassName(selectedGlassCell.value.node.glass)
	return globalGlassDisplayLabel.value
})

const glassPickerCurrent = computed(() =>
	selectedGlassCell.value ? selectedGlassCell.value.node.glass : globalGlassValue.value,
)

function patchCell(path: string, patch: Partial<LeafNode>) {
	const current = nodeAt(path)
	if (!path || !current || current.type === 'split') return
	const next = Object.fromEntries(
		Object.entries({ ...current, ...patch }).filter(([, v]) => v !== undefined),
	) as unknown as LeafNode
	store.apply((d) => setLeaf(d, path, next))
	if (isGrillSelected.value && path === effectiveCellPath.value && !next.grill) {
		store.select(path)
	}
}

function patchGlassBead(bead: boolean) {
	const wasNotOn = glassScopeBeadState.value !== 'on'
	if (selectedGlassCell.value || glassCells.value.length <= 1) {
		if (activeGlassCell.value) patchCell(activeGlassCell.value.path, { bead })
	} else {
		for (const cell of glassCells.value) {
			if (cell.node.type !== 'louver') patchCell(cell.path, { bead })
		}
	}
	if (bead && wasNotOn) {
		promptProfilePickers([{ role: 'bead', targetKey: activeBeadTargetKey.value }])
	}
}

const glassScopeBeadState = computed<'on' | 'off' | 'mixed'>(() => {
	if (selectedGlassCell.value || glassCells.value.length <= 1) {
		const c = activeGlassCell.value
		return c && c.node.bead === false ? 'off' : 'on'
	}
	const nonLouvers = glassCells.value.filter((c) => c.node.type !== 'louver')
	if (!nonLouvers.length) return 'on'
	const allOn = nonLouvers.every((c) => c.node.bead !== false)
	const allOff = nonLouvers.every((c) => c.node.bead === false)
	return allOn ? 'on' : allOff ? 'off' : 'mixed'
})

function onGlassPickerSelect(code: string) {
	if (!code || code === MIXED_GLASS) return
	if (selectedGlassCell.value) {
		patchCell(selectedGlassCell.value.path, { glass: code })
		return
	}
	onSetGlobalGlass(code)
}

function onSelectGlassCode(raw: string | undefined) {
	if (!raw) return
	onGlassPickerSelect(raw)
}

function patchCellGrill(cell: GeomCell, key: keyof Grill, value: number) {
	patchCell(cell.path, { grill: grillConfig({ ...cell.node.grill, [key]: value }) })
}

function dimsForGlassCell(cell: GeomCell | null) {
	if (!cell) return { w: '—', h: '—', cut: '—', label: 'Glass' }
	const infill = cell.node.fan && cell.node.type !== 'louver' ? 'Steel' : 'Glass'
	const row = store.result?.glass.find((g) => g.path === cell.path) ?? null
	if (typeof row?.width === 'number' && typeof row?.height === 'number') {
		const wStr = `${row.width.toFixed(1)} mm`
		const hStr = `${row.height.toFixed(1)} mm`
		return { w: wStr, h: hStr, cut: `${row.width.toFixed(1)} × ${row.height.toFixed(1)} mm`, label: infill }
	}
	const { width, height } = store.design
	const ff = effectiveFrameFace.value
	const bf = BAR_FACE_DEFAULT
	const sf = sashFaceForCell(cell)
	const l = cell.x === 0 ? ff : bf / 2
	const r = cell.x + cell.w === width ? ff : bf / 2
	const b = cell.y === 0 ? ff : bf / 2
	const t = cell.y + cell.h === height ? ff : bf / 2
	const sashIn = cell.node.type === 'sash' ? sf * 2 : 0
	return {
		w: `${Math.max(0, cell.w - l - r - sashIn).toFixed(1)} mm`,
		h: `${Math.max(0, cell.h - t - b - sashIn).toFixed(1)} mm`,
		cut: '—',
		label: infill,
	}
}

function sashFaceForCell(cell: GeomCell | null): number {
	const widths = store.seriesInfo?.profile_widths
	if (widths && cell?.node.type === 'sash') {
		const code = cell.node.profile || store.design.profiles?.[cell.path] || store.design.profiles?.sash
		if (code && widths[code]) return widths[code]
	}
	return SASH_FACE_DEFAULT
}

function dimsForSashCell(cell: GeomCell | null) {
	if (!cell || cell.node.type !== 'sash') return { w: '—', h: '—', size: '—' }
	const members = (store.result?.members ?? []).filter((m) => m.path === cell.path && m.role === 'sash')
	const wMember = members.find((m) => m.position === 'B' || m.position === 'T')
	const hMember = members.find((m) => m.position === 'L' || m.position === 'R')
	if (wMember?.length !== undefined && hMember?.length !== undefined) {
		const w = Number(wMember.length).toFixed(0)
		const h = Number(hMember.length).toFixed(0)
		return { w: `${w} mm`, h: `${h} mm`, size: `${w} × ${h} mm` }
	}
	const { width, height } = store.design
	const ff = effectiveFrameFace.value
	const bf = BAR_FACE_DEFAULT
	const l = cell.x === 0 ? ff : bf / 2
	const r = cell.x + cell.w === width ? ff : bf / 2
	const b = cell.y === 0 ? ff : bf / 2
	const t = cell.y + cell.h === height ? ff : bf / 2
	return {
		w: `${Math.max(0, cell.w - l - r).toFixed(0)} mm`,
		h: `${Math.max(0, cell.h - t - b).toFixed(0)} mm`,
		size: '—',
	}
}

function fanDimsForCell(cell: GeomCell | null) {
	if (!cell) return { width: 0, height: 0, diameter: 180, centerX: 0, centerY: 0, invalid: false }
	const dims = dimsForGlassCell(cell)
	const row = store.result?.glass.find((g) => g.path === cell.path) ?? null
	const width = row?.width ?? Number.parseFloat(dims.w)
	const height = row?.height ?? Number.parseFloat(dims.h)
	const config = cell.node.fanCut ?? {}
	const diameter = config.diameter ?? 180
	const invalid = Boolean(cell.node.fan && !exhaustCut(cell.node, width, height))
	return {
		width,
		height,
		diameter,
		centerX: config.centerX ?? width / 2,
		centerY: config.centerY ?? height / 2,
		invalid,
	}
}

function patchCellFanCut(cell: GeomCell, field: 'diameter' | 'centerX' | 'centerY', value: number) {
	patchCell(cell.path, { fanCut: { ...cell.node.fanCut, [field]: value } })
}

function barSpecsFor(dir: 'v' | 'h') {
	const bars = geom.value.bars.filter((b) => b.dir === dir)
	const bar = activeBarFor(dir)
	if (!bar) return null
	const spNode = nodeAt(bar.splitPath)
	const sp = spNode && spNode.type === 'split' ? spNode : null
	const member = (store.result?.members ?? []).find((m) => m.panel === bar.id || m.path === bar.id) ?? null
	const widths = store.seriesInfo?.profile_widths
	const role = dir === 'v' ? 'mullion' : 'transom'
	const code = store.design.profiles?.[bar.id] || store.design.profiles?.[role] || member?.profile
	const face = (widths && code && widths[code]) || BAR_FACE_DEFAULT
	let cutLength = '—'
	if (member?.length !== undefined) {
		cutLength = `${Number(member.length).toFixed(0)} mm`
	} else {
		const { width, height } = store.design
		const ff = effectiveFrameFace.value
		const inA = (dir === 'v' ? bar.y === 0 : bar.x === 0) ? ff : face / 2
		const inB = (dir === 'v' ? bar.y + bar.length === height : bar.x + bar.length === width) ? ff : face / 2
		cutLength = `${Math.max(0, bar.length - inA - inB).toFixed(0)} mm`
	}
	const pos = sp?.at[bar.index] ?? 0
	const total = sp?.dir === 'v' ? store.design.width : store.design.height
	const pct = total > 0 ? Math.round((pos / total) * 100) : 50
	return { bars, bar, split: sp, member, face, cutLength, pct }
}

const activeBarMap = computed(() => ({
	mullion: barSpecsFor('v'),
	transom: barSpecsFor('h'),
}))

function moveSplitBar(splitTarget: string, index: number, e: Event) {
	const pos = num(e)
	store.apply((d) => moveSplit(d, splitTarget, index, pos))
}

function onSlideSplitBar(splitTarget: string, index: number, dir: 'v' | 'h', e: Event) {
	const pct = Number((e.target as HTMLInputElement).value)
	const total = dir === 'v' ? store.design.width : store.design.height
	store.apply((d) => moveSplit(d, splitTarget, index, Math.round((pct / 100) * total)))
}

function onRemoveSplitPath(splitTarget: string) {
	if (!splitTarget) return
	store.apply((d) => removeSplit(d, splitTarget))
	store.select(splitTarget)
}

const subPanelStyle = {
	padding: '2px 0 10px',
	borderBottom: '1px solid #eef0f3',
	display: 'flex',
	flexDirection: 'column' as const,
	gap: '12px',
}

function pillStyle(active: boolean) {
	return {
		fontSize: '11px',
		fontWeight: active ? '600' : '500',
		padding: '3px 8px',
		borderRadius: '6px',
		border: active ? '1px solid #1d6fdc' : '1px solid #d7dbe0',
		background: active ? '#e8f0fc' : '#ffffff',
		color: active ? '#1b5fb8' : '#5b6472',
		cursor: 'pointer',
	}
}

const activeGlassDims = computed(() => dimsForGlassCell(activeGlassCell.value))
const activeSashDims = computed(() => dimsForSashCell(activeSashCell.value))
const activeFanDims = computed(() => fanDimsForCell(activeFanCell.value))

const activeSashProfileValue = computed(() => {
	const cell = activeSashCell.value
	if (cell?.node.type === 'sash') {
		return cell.node.profile ?? store.design.profiles?.[cell.path] ?? store.design.sashProfileId ?? store.design.profiles?.sash ?? NONE
	}
	return globalSashProfileValue.value
})

function onSetRowSashProfile(code: string | undefined) {
	if (leaf.value?.type === 'sash') {
		onSetSashProfile(code)
		return
	}
	if (sashCells.value.length === 1 && sashCells.value[0].path && sashCells.value[0].path !== 'F1') {
		const item = pickerProfiles.value.find((p) => p.code === code)
		assignProfile(() => store.setProfile('sash', sashCells.value[0].path, code, item?.role || 'sash'))
		return
	}
	onSetGlobalSashProfile(code)
}

type ProfileRowKey =
	| 'frame'
	| 'glass'
	| 'bead'
	| 'sash'
	| 'mullion'
	| 'transom'
	| 'louver'
	| 'fan'
	| 'grill'

interface SeriesProfileRow {
	key: ProfileRowKey
	label: string
	testid: string
	hasSelector: boolean
	displayLabel: string
	profile?: ResolvedProfilePreview
	selectLabel?: string
	selectAriaLabel?: string
	options?: { label: string; value: string }[]
	modelValue?: string
	onOpen?: () => void
	onSelect?: (value: string | undefined) => void
}

const BASE_ROW_ORDER: ProfileRowKey[] = [
	'frame',
	'glass',
	'bead',
	'sash',
	'mullion',
	'transom',
	'louver',
	'fan',
	'grill',
]

const presentRowKeys = computed<ProfileRowKey[]>(() => {
	const flags: Record<ProfileRowKey, boolean> = {
		frame: true,
		glass: hasGlass.value,
		bead: hasActiveBead.value,
		sash: hasSash.value,
		mullion: hasMullion.value,
		transom: hasTransom.value,
		louver: louverCells.value.length > 0,
		fan: fanCells.value.length > 0,
		grill: grillCells.value.length > 0,
	}
	return BASE_ROW_ORDER.filter((key) => flags[key])
})

const orderedRowKeys = ref<ProfileRowKey[]>([])

watch(
	presentRowKeys,
	(present) => {
		const isFreshReset = store.past.length === 0 && store.future.length === 0
		if (isFreshReset || orderedRowKeys.value.length === 0) {
			orderedRowKeys.value = [...present]
			return
		}
		const presentSet = new Set(present)
		const kept = orderedRowKeys.value.filter((k) => presentSet.has(k))
		const keptSet = new Set(kept)
		const added = present.filter((k) => !keptSet.has(k))
		orderedRowKeys.value = [...kept, ...added]
	},
	{ immediate: true, flush: 'sync' },
)

const seriesProfileRows = computed<SeriesProfileRow[]>(() => {
	const catalog: Record<ProfileRowKey, SeriesProfileRow> = {
		frame: {
			key: 'frame',
			label: 'Frame',
			testid: 'series-row-frame',
			hasSelector: true,
			displayLabel: getProfileDisplayLabel('frame', frameProfileValue.value),
			profile: resolveProfilePreview('frame', frameProfileValue.value),
			selectLabel: 'Frame profile',
			options: frameProfileOptions.value,
			modelValue: frameProfileValue.value,
			onOpen: () => openProfilePicker('frame', 'frame'),
			onSelect: onSetFrameProfile,
		},
		sash: {
			key: 'sash',
			label: 'Sash',
			testid: 'series-row-sash',
			hasSelector: true,
			displayLabel: getProfileDisplayLabel('sash', activeSashProfileValue.value),
			profile: resolveProfilePreview('sash', activeSashProfileValue.value),
			selectLabel: 'Sash profile',
			selectAriaLabel: 'Global sash profile',
			options: globalSashProfileOptions.value,
			modelValue: activeSashProfileValue.value,
			onOpen: () => openProfilePicker('sash', leaf.value?.type === 'sash' ? effectiveCellPath.value : 'sash'),
			onSelect: onSetRowSashProfile,
		},
		mullion: {
			key: 'mullion',
			label: 'Mullion',
			testid: 'series-row-mullion',
			hasSelector: true,
			displayLabel: getProfileDisplayLabel('mullion', globalMullionProfileValue.value),
			profile: resolveProfilePreview('mullion', globalMullionProfileValue.value),
			selectLabel: 'Mullion profile',
			selectAriaLabel: 'Global mullion profile',
			options: globalMullionProfileOptions.value,
			modelValue: globalMullionProfileValue.value,
			onOpen: () => openProfilePicker('mullion', selectedBar.value?.dir === 'v' ? selectedBar.value.id : 'mullion'),
			onSelect: (val) => onSetGlobalBarProfile('mullion', val),
		},
		transom: {
			key: 'transom',
			label: 'Transom',
			testid: 'series-row-transom',
			hasSelector: true,
			displayLabel: getProfileDisplayLabel('transom', globalTransomProfileValue.value),
			profile: resolveProfilePreview('transom', globalTransomProfileValue.value),
			selectLabel: 'Transom profile',
			selectAriaLabel: 'Global transom profile',
			options: globalTransomProfileOptions.value,
			modelValue: globalTransomProfileValue.value,
			onOpen: () => openProfilePicker('transom', selectedBar.value?.dir === 'h' ? selectedBar.value.id : 'transom'),
			onSelect: (val) => onSetGlobalBarProfile('transom', val),
		},
		bead: {
			key: 'bead',
			label: 'Bead',
			testid: 'series-row-bead',
			hasSelector: true,
			displayLabel: getProfileDisplayLabel('bead', beadProfileValue.value),
			profile: resolveProfilePreview('bead', beadProfileValue.value),
			selectLabel: 'Bead profile',
			selectAriaLabel: 'Global bead profile',
			options: beadProfileOptions.value,
			modelValue: beadProfileValue.value,
			onOpen: () => openProfilePicker('bead', activeBeadTargetKey.value),
			onSelect: onSetBeadProfile,
		},
		glass: {
			key: 'glass',
			label: 'Glass',
			testid: 'series-row-glass',
			hasSelector: true,
			displayLabel: glassDisplayText.value,
			selectLabel: !isGrillSelected.value && !(leaf.value?.fan && leaf.value.type !== 'louver') ? 'Glass' : undefined,
			options: glassOptions.value,
			modelValue: activeGlassCell.value?.node.glass ?? '',
			onOpen: () => openGlassPicker(),
			onSelect: onSelectGlassCode,
		},
		louver: {
			key: 'louver',
			label: 'Louver',
			testid: 'series-row-louver',
			hasSelector: false,
			displayLabel: '',
		},
		fan: {
			key: 'fan',
			label: 'Exhaust cut',
			testid: 'series-row-fan',
			hasSelector: false,
			displayLabel: '',
		},
		grill: {
			key: 'grill',
			label: 'Grill',
			testid: 'series-row-grill',
			hasSelector: false,
			displayLabel: '',
		},
	}
	return orderedRowKeys.value.map((k) => catalog[k])
})

type AccordionKey = 'basic' | 'finish' | 'frame' | 'sash' | 'div' | 'glaz' | 'bead' | 'addons'
const openAccordion = ref<AccordionKey | null>('basic')
const flyoutOpen = ref(false)
const flyoutKey = ref<ProfileRowKey | 'finish' | null>(null)
const openFrameSide = ref<'T' | 'L' | 'B' | 'R' | null>('T')

const colorSearch = ref('')
const colorSortAsc = ref(true)
const colorDualTarget = ref<'in' | 'out'>('in')
const openFinishGroup = ref<string>('Powder Coat')

const groupedFinishes = computed(() => {
	const q = colorSearch.value.trim().toLowerCase()
	const rows = (props.finishes ?? []).filter((f) => {
		if (!q) return true
		return (
			(f.finish_name || '').toLowerCase().includes(q) ||
			(f.name || '').toLowerCase().includes(q) ||
			(f.finish_type || '').toLowerCase().includes(q)
		)
	})
	const sorted = [...rows].sort((a, b) => {
		const la = (a.finish_name || a.name).toLowerCase()
		const lb = (b.finish_name || b.name).toLowerCase()
		return colorSortAsc.value ? la.localeCompare(lb) : lb.localeCompare(la)
	})
	const groups = new Map<string, typeof sorted>()
	for (const f of sorted) {
		const cat = f.finish_type || 'Powder Coating'
		const arr = groups.get(cat) ?? []
		arr.push(f)
		groups.set(cat, arr)
	}
	return Array.from(groups.entries()).map(([name, items]) => ({ name, items }))
})

watch(
	groupedFinishes,
	(groups) => {
		if (groups.length && !groups.some((g) => g.name === openFinishGroup.value)) {
			openFinishGroup.value = groups[0].name
		}
	},
	{ immediate: true },
)

const finishDraft = ref<{ colorMode: ColorMode; finish: string; finishOutside?: string } | null>(null)

function initFinishDraft() {
	finishDraft.value = {
		colorMode: store.design.colorMode ?? 'single',
		finish: store.finish || '',
		finishOutside: store.design.finishOutside,
	}
}

const draftColorMode = computed<ColorMode>(() => finishDraft.value?.colorMode ?? colorMode.value)
const draftFinish = computed(() => finishDraft.value?.finish ?? store.finish)
const draftFinishOutside = computed(() => finishDraft.value?.finishOutside ?? store.design.finishOutside)

function setDraftColorMode(mode: ColorMode) {
	if (!finishDraft.value) initFinishDraft()
	finishDraft.value = {
		...finishDraft.value!,
		colorMode: mode,
		finishOutside: mode === 'dual' ? (finishDraft.value!.finishOutside || finishDraft.value!.finish || undefined) : undefined,
	}
}

function toggleFinishGroup(name: string) {
	openFinishGroup.value = openFinishGroup.value === name ? '' : name
}

function pickFinishSwatch(code: string) {
	if (!finishDraft.value) initFinishDraft()
	if (finishDraft.value!.colorMode === 'dual' && colorDualTarget.value === 'out') {
		finishDraft.value = { ...finishDraft.value!, finishOutside: code || undefined }
		return
	}
	finishDraft.value = {
		...finishDraft.value!,
		colorMode: finishDraft.value!.colorMode === 'none' ? 'single' : finishDraft.value!.colorMode,
		finish: code,
	}
}

function isSwatchActive(code: string): boolean {
	if (draftColorMode.value === 'none') return false
	if (draftColorMode.value === 'dual' && colorDualTarget.value === 'out') {
		return (draftFinishOutside.value || draftFinish.value) === code
	}
	return draftFinish.value === code
}

function toggleFrameSide(side: 'T' | 'L' | 'B' | 'R') {
	openFrameSide.value = openFrameSide.value === side ? null : side
}

function onSetFrameSideProfile(side: 'T' | 'L' | 'B' | 'R', code: string | undefined) {
	const item = pickerProfiles.value.find((p) => p.code === code)
	assignProfile(() => store.setProfile('frame', `F1.${side}`, code, item?.role || 'frame'))
}

const frameConfigLabel = computed(() => {
	if (frameConfig.value === '3-side') return '3 SideOuterFrame'
	if (frameConfig.value === '3-side-threshold') return '3 Side Outer With Low Threshold'
	return '4 SideOuterFrame'
})

// Exact resolved DXF profile previews for every left-rail item card
const framePreview = computed(() => resolveProfilePreview('frame', frameProfileValue.value))
const beadPreview = computed(() => resolveProfilePreview('bead', beadProfileValue.value))
function sashPreviewFor(cell: GeomCell): ResolvedProfilePreview {
	const code =
		(cell.node.type === 'sash' ? cell.node.profile : undefined) ??
		store.design.profiles?.[cell.path] ??
		store.design.sashProfileId ??
		store.design.profiles?.sash ??
		NONE
	return resolveProfilePreview('sash', code)
}
function barPreviewFor(b: GeomBar): ResolvedProfilePreview {
	const role = b.dir === 'v' ? 'mullion' : 'transom'
	const code =
		store.design.profiles?.[b.id] ??
		(role === 'mullion' ? store.design.mullionProfileId : undefined) ??
		store.design.profiles?.[role] ??
		NONE
	return resolveProfilePreview(role, code)
}

// Glazing Item prototype fields (Select item, Item thickness, Multi-cell Apply to, Auto Bead & Gasket preview)
const PANEL_ITEMS = [
	'ACP SHEET 4MM',
	'POWDER COATED ALUMINIUM LOUVER PANEL',
	'TEAK WOOD PANEL 12MM',
	'STEEL SECURITY SHEET',
]
const glazeItemType = ref<'Glass' | 'Panel'>('Glass')
const glazeThickness = ref<string>('all')
const glazeTargets = ref<string[]>([])
const openBeadSide = ref<'Top' | 'Left' | 'Bottom' | 'Right' | null>('Top')

watch(
	activeGlassCell,
	(cell) => {
		if (cell?.node.itemType === 'Panel' || cell?.node.addon === 'Panel') {
			glazeItemType.value = 'Panel'
		} else {
			glazeItemType.value = 'Glass'
		}
	},
	{ immediate: true },
)

watch(
	glassCells,
	(cells) => {
		const paths = cells.map((c) => c.path)
		if (!glazeTargets.value.length || !glazeTargets.value.some((p) => paths.includes(p))) {
			glazeTargets.value = paths
		}
	},
	{ immediate: true },
)

const availableGlassThicknesses = computed(() => {
	const set = new Set<number>()
	for (const g of glassList.data ?? []) {
		const t = Number(g.thickness_mm)
		if (Number.isFinite(t) && t > 0) set.add(t)
	}
	return Array.from(set).sort((a, b) => a - b)
})

const filteredGlassList = computed(() => {
	const codes = store.seriesInfo?.glasses
	const rows = (glassList.data ?? []).filter((g) => !codes || codes.includes(g.name))
	if (glazeThickness.value === 'all') return rows
	const targetT = Number(glazeThickness.value)
	return rows.filter((g) => Number(g.thickness_mm) === targetT)
})

function toggleGlazeAll() {
	const allPaths = glassCells.value.map((c) => c.path)
	if (glazeTargets.value.length === allPaths.length) {
		glazeTargets.value = allPaths.slice(0, 1)
	} else {
		glazeTargets.value = allPaths
	}
	store.select('')
}

function toggleGlazeCell(path: string) {
	if (glazeTargets.value.includes(path)) {
		if (glazeTargets.value.length > 1) {
			glazeTargets.value = glazeTargets.value.filter((p) => p !== path)
		}
	} else {
		glazeTargets.value = [...glazeTargets.value, path]
	}
	store.select(path)
}

function onChangeGlazeItemType(nextType: 'Glass' | 'Panel') {
	glazeItemType.value = nextType
	const targets = glazeTargets.value.length ? glazeTargets.value : glassCells.value.map((c) => c.path)
	store.apply((d) => {
		let next = d
		for (const p of targets) {
			const cur = nodeAt(p)
			if (cur && cur.type !== 'split') {
				if (nextType === 'Panel') {
					next = setLeaf(next, p, {
						...cur,
						itemType: 'Panel',
						panelItem: cur.panelItem || PANEL_ITEMS[0],
						addon: 'Panel',
						bead: true,
					})
				} else {
					const { addon: _a, panelItem: _p, ...rest } = cur
					next = setLeaf(next, p, {
						...(rest as LeafNode),
						itemType: 'Glass',
						bead: true,
					})
				}
			}
		}
		return next
	})
}

function applyPanelToTargets(panelName: string) {
	const targets = glazeTargets.value.length ? glazeTargets.value : glassCells.value.map((c) => c.path)
	store.apply((d) => {
		let next = d
		for (const p of targets) {
			const cur = nodeAt(p)
			if (cur && cur.type !== 'split') {
				next = setLeaf(next, p, {
					...cur,
					itemType: 'Panel',
					panelItem: panelName,
					addon: 'Panel',
					bead: true,
				})
			}
		}
		return next
	})
}

function applyGlassToTargets(code: string) {
	if (!code || code === MIXED_GLASS) return
	const targets = glazeTargets.value.length ? glazeTargets.value : glassCells.value.map((c) => c.path)
	store.apply((d) => {
		let next = d
		for (const p of targets) {
			const cur = nodeAt(p)
			if (cur && cur.type !== 'split' && cellHasGlass(cur)) {
				const { addon: _a, panelItem: _p, ...rest } = cur
				next = setLeaf(next, p, { ...(rest as LeafNode), glass: code, itemType: 'Glass', bead: true })
			}
		}
		return next
	})
}

const activeGlassThicknessMm = computed(() => {
	const cell = activeGlassCell.value
	if (!cell) return 6
	if (cell.node.itemType === 'Panel') {
		const pm = String(cell.node.panelItem || '').match(/(\d+(?:\.\d+)?)\s*mm/i)
		return pm ? Number(pm[1]) : 4
	}
	const code = cell.node.glass
	const row = (glassList.data ?? []).find((g) => g.name === code)
	if (row?.thickness_mm) return Number(row.thickness_mm)
	const m = String(code ?? '').match(/(\d+(?:\.\d+)?)/)
	return m ? Number(m[1]) : 6
})

const activeGlassThicknessLabel = computed(() => `${activeGlassThicknessMm.value} mm`)

const activeFrameDepthMm = computed(() => {
	const code = framePreview.value.code
	const item = pickerProfiles.value.find((p) => p.code === code)
	const dbRow = catalogRows.value.find((r) => (r.profile_code || r.name) === code)
	const d = Number(item?.depth_mm ?? dbRow?.depth_mm ?? 0)
	if (d > 0) return d
	const titleMatch = String(framePreview.value.title || '').match(/(\d+(?:\.\d+)?)\s*mm/i)
	if (titleMatch) return Number(titleMatch[1])
	const ser = activeSeriesBrand.value.toUpperCase()
	if (ser.includes('HSL3400')) return 90
	if (ser.includes('HSL2600')) return 60
	if (ser.includes('CS4800')) return 48
	return 40
})

const autoBeadGasketPreview = computed(() => {
	const t = activeGlassThicknessMm.value
	const fDepth = activeFrameDepthMm.value
	const isSliding = Boolean(store.design.isSliding) || activeSeriesBrand.value.toUpperCase().startsWith('HSL')
	const activePath = activeGlassCell.value?.path
	const computedBead =
		(store.result?.members ?? []).find(
			(m) => (m.role === 'bead' || m.role === 'glass_adaptor') && (!activePath || m.path === activePath),
		) ?? (store.result?.members ?? []).find((m) => m.role === 'bead' || m.role === 'glass_adaptor')

	let beadText: string
	if (beadPreview.value.code) {
		beadText = `${beadPreview.value.title}${beadPreview.value.subtitle ? ` (${beadPreview.value.subtitle})` : ''}`
	} else if (computedBead?.profile) {
		const p = resolveProfilePreview('bead', computedBead.profile)
		beadText = `${p.title}${p.subtitle ? ` (${p.subtitle})` : ''}`
	} else if (fDepth >= 48) {
		beadText =
			t <= 12
				? '(HSL3409) SLD SGU GLASS ADAPTOR 28.9MM X 16.8MM'
				: `DGU direct pocket (${fDepth}mm frame · ${t}mm glass)`
	} else {
		beadText =
			t <= 8
				? `Auto ${t}mm glazing bead (${fDepth}mm frame)`
				: `Thin glazing bead (${fDepth}mm frame · ${t}mm glass)`
	}

	const gaskets = (store.result?.bom ?? []).filter(
		(b) => (b.group || '').toLowerCase().includes('gasket') || (b.name || '').toLowerCase().includes('gasket'),
	)
	const beadGasket = gaskets.find(
		(g) => (g.name || '').toLowerCase().includes('bead') || (g.name || '').toLowerCase().includes('glaz') || g.item === 'G23' || g.item === 'G22',
	)
	const frameGasket =
		gaskets.find((g) => (g.name || '').toLowerCase().includes('frame') || (g.name || '').toLowerCase().includes('weather') || (g.name || '').toLowerCase().includes('wool')) ??
		gaskets.find((g) => g !== beadGasket)

	const fallbackBeadGasket =
		t <= 6 ? '(G23) GASKET 3MM' : t <= 12 ? '(G22) GASKET 2MM' : '(G25) DGU GLAZING GASKET 1.5MM'
	const fallbackFrameGasket = isSliding
		? '(G24) SLIDING WOOL PILE'
		: fDepth >= 48
			? '(G21-48) FRAME GASKET 48MM CASEMENT'
			: '(G21) FRAME GASKET 40MM CASEMENT'

	return {
		frameDepth: `${fDepth} mm`,
		glassThickness: `${t} mm`,
		bead: beadText,
		beadGasket: beadGasket ? `${beadGasket.item ? `(${beadGasket.item}) ` : ''}${beadGasket.name}` : fallbackBeadGasket,
		frameGasket: frameGasket ? `${frameGasket.item ? `(${frameGasket.item}) ` : ''}${frameGasket.name}` : fallbackFrameGasket,
	}
})

const FRAME_CONFIG_OPTIONS = [
	{ label: '4 SideOuterFrame', value: '4-side' },
	{ label: '3 SideOuterFrame', value: '3-side' },
	{ label: '3 Side Outer With Low Threshold', value: '3-side-threshold' },
]
const SASH_CONFIG_OPTIONS = [
	{ label: 'Casement Window Sash', value: 'window' },
	{ label: 'Casement Door Sash', value: 'door' },
]
const SLIDE_MODE_OPTIONS = [
	{ label: 'Sliding Sash', value: 'sliding' },
	{ label: 'Fixed Panel', value: 'fixed' },
]
const SLIDE_DIR_OPTIONS = [
	{ label: 'Right (→)', value: 'right' },
	{ label: 'Left (←)', value: 'left' },
]
const DOOR_HANDLE_SETS = [
	'(H420) DOOR HANDLE SET',
	'(H425) ESPAG L HANDLE',
]
const DOOR_HANDLE_SET_OPTIONS = DOOR_HANDLE_SETS.map((value) => ({ label: value, value }))
const DOOR_HINGE_ITEMS = [
	'(H415) DOOR HINGE 3 WING',
	'(H416) HEAVY DUTY DOOR HINGE',
]
const DOOR_HINGE_ITEM_OPTIONS = DOOR_HINGE_ITEMS.map((value) => ({ label: value, value }))
const HINGE_STAY_OPTIONS = [
	{ label: 'None', value: 'None' },
	{ label: 'Hinges', value: 'Hinges' },
	{ label: 'Friction stay', value: 'Friction stay' },
]
function normalizedHingeStay(node: LeafNode): string {
	if (node.type !== 'sash') return 'None'
	const v = String(node.hingeStay || '').toLowerCase()
	if (v === 'hinges') return 'Hinges'
	if (v === 'friction' || v === 'friction stay') return 'Friction stay'
	if (node.sashConfig === 'door') return 'Hinges'
	return 'None'
}

function onChangeSashConfig(cell: { path: string; node: LeafNode }, val: unknown) {
	if (cell.node.type !== 'sash') return
	const next = String(val ?? 'window') as SashConfig
	patchCell(cell.path, {
		sashConfig: next,
		bead: next === 'door',
		hingeStay: next === 'door' ? 'Hinges' : cell.node.hingeStay,
		activeLeaf: next === 'door' ? (cell.node.activeLeaf ?? true) : undefined,
		handleItem: next === 'door' ? DOOR_HANDLE_SETS[0] : DOOR_HANDLE_SETS[1],
		hingeItem: next === 'door' ? DOOR_HINGE_ITEMS[0] : cell.node.hingeItem,
	})
	warnIfUnsupportedProduct(next === 'door' ? (cell.node.isSliding ? 'Sliding Door' : 'Door') : (cell.node.isSliding ? 'Sliding Window' : 'Window'))
}

function onChangeHingeStay(cell: { path: string }, val: unknown) {
	const stay = String(val ?? 'None') as 'None' | 'Hinges' | 'Friction stay'
	patchCell(cell.path, {
		hingeStay: stay,
		hinge_type: stay === 'Hinges' ? 'butt' : stay === 'Friction stay' ? 'friction' : undefined,
	})
}

interface FlyDraft {
	design: ReturnType<typeof structuredClone<typeof store.design>>
	finish: string
	seriesVersion: string
}
let flyDraft: FlyDraft | null = null

function captureFlyDraft() {
	if (flyDraft) return
	try {
		flyDraft = {
			design: structuredClone(JSON.parse(JSON.stringify(store.design))),
			finish: store.finish,
			seriesVersion: store.seriesVersion,
		}
	} catch {
		flyDraft = null
	}
}

function toggleAccordion(k: AccordionKey) {
	if (openAccordion.value === k) {
		openAccordion.value = null
		flyoutOpen.value = false
		flyoutKey.value = null
		flyDraft = null
	} else {
		openAccordion.value = k
	}
}

function openItemFlyout(acc: AccordionKey, key: ProfileRowKey | 'finish', selectTarget?: string) {
	openAccordion.value = acc
	if (selectTarget !== undefined) store.select(selectTarget)
	if (flyoutOpen.value && flyoutKey.value === key && selectTarget === undefined) {
		flyoutOpen.value = false
		flyoutKey.value = null
		flyDraft = null
		finishDraft.value = null
		return
	}
	flyDraft = null
	captureFlyDraft()
	if (key === 'finish') initFinishDraft()
	else finishDraft.value = null
	flyoutKey.value = key
	flyoutOpen.value = true
}

function applyFlyout() {
	openProfileDropdown.value = null
	if (finishDraft.value) {
		const fd = finishDraft.value
		finishDraft.value = null
		store.apply((d) => ({
			...d,
			colorMode: fd.colorMode,
			finishOutside: fd.colorMode === 'dual' ? (fd.finishOutside || fd.finish || undefined) : undefined,
		}))
		if (fd.finish !== store.finish) {
			store.setFinish(fd.finish)
		}
	}
	flyDraft = null
	flyoutOpen.value = false
	flyoutKey.value = null
}

function cancelFlyout() {
	openProfileDropdown.value = null
	finishDraft.value = null
	if (flyDraft) {
		const snap = flyDraft
		flyDraft = null
		store.apply(() => snap.design)
		if (store.finish !== snap.finish) store.setFinish(snap.finish)
		if (store.seriesVersion !== snap.seriesVersion) store.setSeriesVersion(snap.seriesVersion)
	}
	flyoutOpen.value = false
	flyoutKey.value = null
}

function closeFlyout() {
	applyFlyout()
}

const activeBarsList = computed(() => layoutGeom(store.design).bars)
const activeFinishLabel = computed(() => {
	if (colorMode.value === 'none') return 'No color (Mill)'
	const f = (props.finishes ?? []).find((x) => x.name === store.finish)
	return f?.finish_name || store.finish || 'Select finish'
})
const outsideFinishLabel = computed(() => {
	if (colorMode.value === 'none') return 'No color (Mill)'
	const code = store.design.finishOutside || store.finish
	const f = (props.finishes ?? []).find((x) => x.name === code)
	return f?.finish_name || code || 'Select finish'
})

const glassGroups = computed(() => {
	const groups: { key: string; glass: string; label: string; cellLabels: string[]; firstPath: string }[] = []
	glassCells.value.forEach((c, idx) => {
		const g = c.node.glass || '6CTG'
		let grp = groups.find((x) => x.glass === g)
		if (!grp) {
			grp = { key: g, glass: g, label: formatGlassName(g), cellLabels: [], firstPath: c.path }
			groups.push(grp)
		}
		grp.cellLabels.push(`G${idx + 1}`)
	})
	return groups
})

watch(
	[() => store.selectedPath, () => store.design.root.type],
	([sel]) => {
		if (!sel) {
			applyFlyout()
			return
		}
		if (sel === 'FRAME' || (sel === 'F1' && store.design.root.type === 'split')) {
			openAccordion.value = 'frame'
			if (!flyoutOpen.value || flyoutKey.value !== 'frame') {
				flyDraft = null
				captureFlyDraft()
			}
			flyoutKey.value = 'frame'
			flyoutOpen.value = true
		} else if (/^[MT]\d+$/.test(sel)) {
			openAccordion.value = 'div'
			const bar = activeBarsList.value.find((b) => b.id === sel)
			const nextKey = bar?.dir === 'h' ? 'transom' : 'mullion'
			if (!flyoutOpen.value || flyoutKey.value !== nextKey) {
				flyDraft = null
				captureFlyDraft()
			}
			flyoutKey.value = nextKey
			flyoutOpen.value = true
		} else if (sel.startsWith('GLASS:')) {
			openAccordion.value = 'glaz'
			if (!flyoutOpen.value || flyoutKey.value !== 'glass') {
				flyDraft = null
				captureFlyDraft()
			}
			flyoutKey.value = 'glass'
			flyoutOpen.value = true
		} else if (sel.startsWith('BEAD:')) {
			openAccordion.value = 'bead'
			if (!flyoutOpen.value || flyoutKey.value !== 'bead') {
				flyDraft = null
				captureFlyDraft()
			}
			flyoutKey.value = 'bead'
			flyoutOpen.value = true
		} else if (sel.startsWith('GRILL:')) {
			openAccordion.value = 'addons'
			if (!flyoutOpen.value || flyoutKey.value !== 'grill') {
				flyDraft = null
				captureFlyDraft()
			}
			flyoutKey.value = 'grill'
			flyoutOpen.value = true
		} else {
			try {
				const n = getNode(store.design, sel)
				let nextAcc: AccordionKey = 'glaz'
				let nextKey: ProfileRowKey = 'glass'
				if (n.type === 'sash') {
					nextAcc = 'sash'
					nextKey = 'sash'
				} else if (n.type === 'louver') {
					nextAcc = 'addons'
					nextKey = 'louver'
				} else if (n.fan) {
					nextAcc = 'addons'
					nextKey = 'fan'
				}
				openAccordion.value = nextAcc
				if (!flyoutOpen.value || flyoutKey.value !== nextKey) {
					flyDraft = null
					captureFlyDraft()
				}
				flyoutKey.value = nextKey
				flyoutOpen.value = true
			} catch {
				// ignore unknown path
			}
		}
	},
)

const flyoutTitle = computed(() => {
	if (flyoutKey.value === 'finish') return 'Custom color'
	if (flyoutKey.value === 'frame') return 'Frame F1'
	if (flyoutKey.value === 'sash') return activeSashCell.value ? `Sash ${cellLabel(activeSashCell.value.path)}` : 'Sash'
	if (flyoutKey.value === 'mullion') return selectedBar.value ? `Mullion ${selectedBar.value.id}` : 'Mullion'
	if (flyoutKey.value === 'transom') return selectedBar.value ? `Transom ${selectedBar.value.id}` : 'Transom'
	if (flyoutKey.value === 'glass') return 'Change Glazing item'
	if (flyoutKey.value === 'bead') return 'Bead'
	if (flyoutKey.value === 'louver') return 'Louver'
	if (flyoutKey.value === 'fan') return 'Exhaust Fan Cut'
	if (flyoutKey.value === 'grill') return 'Grill'
	return 'Properties'
})
</script>

<template>
	<div class="flex min-h-0 shrink-0 flex-col md:flex-row">
		<!-- ─── LEFT ACCORDION RAIL (.left, 310px) ─────────────────── -->
		<aside
			class="flex w-full shrink-0 flex-col border-b border-[#dcdfe4] bg-white text-[#2b2f36] md:w-72 md:border-r md:border-b-0 lg:w-[310px]"
			style="font-family: 'Segoe UI', Inter, Arial, sans-serif; box-sizing: border-box"
		>
			<div class="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto p-3">
				<!-- 1. Basic info (strictly 1 field per row, prototype + Frappe fields) -->
				<div>
					<button
						type="button"
						data-testid="acc-basic"
						class="flex h-[42px] w-full items-center justify-between rounded-[7px] px-3.5 text-left text-[13.5px] font-semibold transition"
						:class="openAccordion === 'basic' ? 'bg-[#edf4ff] text-[#1a6fd4]' : 'bg-[#f3f5f8] text-[#1e293b] hover:bg-[#eaedf2]'"
						@click="toggleAccordion('basic')"
					>
						<span>Basic info</span>
						<span class="font-mono text-base leading-none opacity-80">{{ openAccordion === 'basic' ? '−' : '+' }}</span>
					</button>
					<div v-show="openAccordion === 'basic'" class="eva-rail-form flex flex-col gap-3 bg-white px-1.5 pt-3 pb-1">
						<div>
							<label for="pp-ref" class="eva-field-label flex items-center justify-between">
								<span>Design ref. <span class="text-rose-500">*</span></span>
								<span v-if="refReadonly" class="text-[10.5px] font-normal text-[#94a3b8]">Locked</span>
							</label>
							<input
								id="pp-ref"
								v-model="meta.ref"
								type="text"
								placeholder="e.g. W-01"
								:readonly="refReadonly"
								class="eva-field-input"
								:class="refError ? 'eva-field-error' : ''"
							/>
							<p v-if="refError" class="mt-1 text-[11px] font-medium text-red-600">{{ refError }}</p>
						</div>
						<div>
							<label for="pp-qty" class="eva-field-label">Design quantity <span class="text-rose-500">*</span></label>
							<input
								id="pp-qty"
								v-model.number="meta.qty"
								type="number"
								min="1"
								class="eva-field-input font-mono tabular-nums"
							/>
						</div>
						<div>
							<label for="pp-name" class="eva-field-label">Design name</label>
							<input
								id="pp-name"
								v-model="meta.name"
								type="text"
								placeholder="e.g. Living Room Casement"
								class="eva-field-input"
							/>
						</div>
						<div>
							<label for="pp-width" class="eva-field-label">Width (mm)</label>
							<div class="relative">
								<input
									id="pp-width"
									type="number"
									class="eva-field-input pr-10 font-mono tabular-nums"
									:value="store.design.width"
									@change="resize(num($event), store.design.height)"
								/>
								<span class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 font-mono text-[11px] font-medium text-[#94a3b8]">mm</span>
							</div>
						</div>
						<div>
							<label for="pp-height" class="eva-field-label">Height (mm)</label>
							<div class="relative">
								<input
									id="pp-height"
									type="number"
									class="eva-field-input pr-10 font-mono tabular-nums"
									:value="store.design.height"
									@change="resize(store.design.width, num($event))"
								/>
								<span class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 font-mono text-[11px] font-medium text-[#94a3b8]">mm</span>
							</div>
						</div>
						<div>
							<label for="pp-floor" class="eva-field-label">Floor number</label>
							<input
								id="pp-floor"
								v-model="meta.floor"
								type="text"
								placeholder="e.g. Floor 1"
								class="eva-field-input"
							/>
						</div>
						<div>
							<label for="pp-location" class="eva-field-label">Location</label>
							<input
								id="pp-location"
								v-model="meta.location"
								type="text"
								placeholder="e.g. Master Bedroom"
								class="eva-field-input"
							/>
						</div>
						<div>
							<label for="pp-note" class="eva-field-label">Note</label>
							<textarea
								id="pp-note"
								v-model="meta.note"
								rows="2"
								placeholder="Add fabrication or site note..."
								class="eva-field-textarea"
							/>
						</div>
						<div data-testid="series-version-field" style="display: flex; flex-direction: column; gap: 4px; min-width: 0">
							<span class="eva-field-label !mb-0">System / Series</span>
							<Select
								v-if="seriesVersionOptions.length"
								variant="outline"
								side="bottom"
								align="start"
								:offset="5"
								class="w-full"
								:options="seriesVersionOptions"
								:model-value="store.seriesVersion"
								@update:model-value="store.setSeriesVersion(String($event ?? ''))"
							/>
							<span v-else class="text-xs text-gray-800">{{ store.seriesVersion || 'None' }}</span>
						</div>
					</div>
				</div>

				<!-- 2. Surface finish -->
				<div>
					<button
						type="button"
						data-testid="acc-finish"
						class="flex h-[42px] w-full items-center justify-between rounded-[7px] px-3.5 text-left text-[13.5px] font-semibold transition"
						:class="openAccordion === 'finish' ? 'bg-[#edf4ff] text-[#1a6fd4]' : 'bg-[#f3f5f8] text-[#1e293b] hover:bg-[#eaedf2]'"
						@click="toggleAccordion('finish')"
					>
						<span>Surface finish</span>
						<span class="font-mono text-base leading-none opacity-80">{{ openAccordion === 'finish' ? '−' : '+' }}</span>
					</button>
					<div v-show="openAccordion === 'finish'" class="bg-white px-1.5 pt-3 pb-1">
						<div class="mb-2 text-[13px] font-semibold text-[#2b2f36]">Custom color</div>
						<button
							type="button"
							data-testid="open-custom-color"
							class="flex min-h-[58px] w-full items-center gap-3 rounded-[4px] border p-2 text-left transition"
							:class="flyoutOpen && flyoutKey === 'finish' ? 'border-[#1a6fd4] bg-[#f8fbff]' : 'border-[#dcdfe4] bg-white hover:border-[#b6c6dd]'"
							@click="openItemFlyout('finish', 'finish')"
						>
							<span
								class="size-[42px] shrink-0 rounded-[2px] border border-black/15"
								:style="{ backgroundColor: colorMode === 'none' ? '#a8b0ba' : finishColorFor(store.finish) }"
							/>
							<div class="min-w-0 flex-1">
								<div class="truncate text-[13px] font-semibold text-[#2b2f36]">{{ activeFinishLabel }}</div>
								<div class="text-[11px] text-[#6b7280]">
									{{ colorMode === 'dual' ? `dual · out: ${outsideFinishLabel}` : colorMode }}
								</div>
							</div>
							<span
								class="flex size-[30px] shrink-0 items-center justify-center rounded-[3px] text-sm font-semibold"
								:class="flyoutOpen && flyoutKey === 'finish' ? 'bg-[#e6effb] text-[#1a6fd4]' : 'text-[#444]'"
							>&gt;</span>
						</button>
					</div>
				</div>

				<!-- 3. Framing (Shows Exact Selected Frame Profile DXF Thumbnail & Name) -->
				<div>
					<button
						type="button"
						data-testid="acc-frame"
						class="flex h-[42px] w-full items-center justify-between rounded-[7px] px-3.5 text-left text-[13.5px] font-semibold transition"
						:class="openAccordion === 'frame' ? 'bg-[#edf4ff] text-[#1a6fd4]' : 'bg-[#f3f5f8] text-[#1e293b] hover:bg-[#eaedf2]'"
						@click="toggleAccordion('frame')"
					>
						<span>Framing</span>
						<span class="font-mono text-base leading-none opacity-80">{{ openAccordion === 'frame' ? '−' : '+' }}</span>
					</button>
					<div v-show="openAccordion === 'frame'" class="bg-white px-1.5 pt-3 pb-1">
						<button
							type="button"
							data-testid="open-frame-f1"
							class="flex min-h-[60px] w-full items-center gap-3 rounded-[4px] border p-2 text-left transition"
							:class="flyoutOpen && flyoutKey === 'frame' ? 'border-[#1a6fd4] bg-[#f8fbff]' : 'border-[#dcdfe4] bg-white hover:border-[#b6c6dd]'"
							@click="openItemFlyout('frame', 'frame', 'FRAME')"
						>
							<div
								data-testid="left-thumb-frame"
								class="flex size-[42px] shrink-0 items-center justify-center overflow-hidden rounded-[3px] border border-[#cfd4da] bg-[#f8fafc] p-1 text-[#2d4a7a]"
							>
								<svg
									v-if="framePreview.svg"
									xmlns="http://www.w3.org/2000/svg"
									:viewBox="framePreview.viewBox"
									class="block h-full w-full"
									preserveAspectRatio="xMidYMid meet"
								>
									<g :transform="framePreview.transform || undefined">
										<path
											:d="framePreview.svg"
											fill="#CBD5E1"
											stroke="#334155"
											stroke-width="1.5"
											fill-rule="evenodd"
											vector-effect="non-scaling-stroke"
										/>
									</g>
								</svg>
								<span v-else class="lucide-frame size-5" aria-hidden="true" />
							</div>
							<div class="min-w-0 flex-1">
								<div class="truncate text-[12.5px] font-semibold text-[#2b2f36]">
									F1 · {{ framePreview.code ? framePreview.title : (store.seriesVersion || 'Frame') }}
								</div>
								<div class="truncate font-mono text-[10.5px] text-[#6b7280]">
									{{ framePreview.subtitle || frameConfigLabel }}
								</div>
							</div>
							<span
								class="flex size-[30px] shrink-0 items-center justify-center rounded-[3px] text-sm font-semibold"
								:class="flyoutOpen && flyoutKey === 'frame' ? 'bg-[#e6effb] text-[#1a6fd4]' : 'text-[#444]'"
							>&gt;</span>
						</button>
					</div>
				</div>

				<!-- 4. Sash (Shows Exact Selected Sash Profile DXF Thumbnail & Name) -->
				<div>
					<button
						type="button"
						data-testid="acc-sash"
						class="flex h-[42px] w-full items-center justify-between rounded-[7px] px-3.5 text-left text-[13.5px] font-semibold transition"
						:class="openAccordion === 'sash' ? 'bg-[#edf4ff] text-[#1a6fd4]' : 'bg-[#f3f5f8] text-[#1e293b] hover:bg-[#eaedf2]'"
						@click="toggleAccordion('sash')"
					>
						<span>Sash <span v-if="sashCells.length" class="ml-1 text-xs font-normal opacity-75">({{ sashCells.length }})</span></span>
						<span class="font-mono text-base leading-none opacity-80">{{ openAccordion === 'sash' ? '−' : '+' }}</span>
					</button>
					<div v-show="openAccordion === 'sash'" class="flex flex-col gap-2 bg-white px-1.5 pt-3 pb-1">
						<div v-if="!sashCells.length" class="rounded-[4px] border border-dashed border-[#dcdfe4] px-3 py-2.5 text-[12px] text-[#6b7280]">
							No openable sashes yet. Drag a design from the canvas palette.
						</div>
						<button
							v-for="cell in sashCells"
							:key="cell.path"
							type="button"
							class="flex min-h-[60px] w-full items-center gap-3 rounded-[4px] border p-2 text-left transition"
							:class="flyoutOpen && flyoutKey === 'sash' && activeSashCell?.path === cell.path ? 'border-[#1a6fd4] bg-[#f8fbff]' : 'border-[#dcdfe4] bg-white hover:border-[#b6c6dd]'"
							@click="openItemFlyout('sash', 'sash', cell.path)"
						>
							<div class="flex size-[42px] shrink-0 items-center justify-center overflow-hidden rounded-[3px] border border-[#cfd4da] bg-[#f8fafc] p-1 text-[#2d4a7a]">
								<svg
									v-if="sashPreviewFor(cell).svg"
									xmlns="http://www.w3.org/2000/svg"
									:viewBox="sashPreviewFor(cell).viewBox"
									class="block h-full w-full"
									preserveAspectRatio="xMidYMid meet"
								>
									<g :transform="sashPreviewFor(cell).transform || undefined">
										<path
											:d="sashPreviewFor(cell).svg"
											fill="#CBD5E1"
											stroke="#334155"
											stroke-width="1.5"
											fill-rule="evenodd"
											vector-effect="non-scaling-stroke"
										/>
									</g>
								</svg>
								<span v-else class="lucide-panel-left-open size-5" aria-hidden="true" />
							</div>
							<div class="min-w-0 flex-1">
								<div class="truncate text-[12.5px] font-semibold text-[#2b2f36]">
									{{ cellLabel(cell.path) }} · {{ sashPreviewFor(cell).code ? sashPreviewFor(cell).title : (cell.node.type === 'sash' && cell.node.sashConfig === 'door' ? 'Casement Door Sash' : 'Casement Window Sash') }}
								</div>
								<div class="truncate font-mono text-[10.5px] text-[#6b7280]">
									{{ sashPreviewFor(cell).subtitle ? `${sashPreviewFor(cell).subtitle} · ` : '' }}{{ cell.node.type === 'sash' ? (cell.node.isSliding ? (cell.node.slideFixed ? 'Fixed' : `Slide ${cell.node.slideDir === 'left' ? '←' : '→'} · Track ${(cell.node.trackIdx ?? 0) + 1}`) : (cell.node.sashConfig === 'door' ? (cell.node.activeLeaf === false ? 'Passive' : 'Active') : (cell.node.hinge || 'left'))) : '' }}
								</div>
							</div>
							<span
								class="flex size-[30px] shrink-0 items-center justify-center rounded-[3px] text-sm font-semibold"
								:class="flyoutOpen && flyoutKey === 'sash' && activeSashCell?.path === cell.path ? 'bg-[#e6effb] text-[#1a6fd4]' : 'text-[#444]'"
							>&gt;</span>
						</button>
					</div>
				</div>

				<!-- 5. Divider (Shows Exact Selected Mullion / Transom Profile DXF Thumbnail & Name) -->
				<div>
					<button
						type="button"
						data-testid="acc-div"
						class="flex h-[42px] w-full items-center justify-between rounded-[7px] px-3.5 text-left text-[13.5px] font-semibold transition"
						:class="openAccordion === 'div' ? 'bg-[#edf4ff] text-[#1a6fd4]' : 'bg-[#f3f5f8] text-[#1e293b] hover:bg-[#eaedf2]'"
						@click="toggleAccordion('div')"
					>
						<span>Divider <span v-if="activeBarsList.length" class="ml-1 text-xs font-normal opacity-75">({{ activeBarsList.length }})</span></span>
						<span class="font-mono text-base leading-none opacity-80">{{ openAccordion === 'div' ? '−' : '+' }}</span>
					</button>
					<div v-show="openAccordion === 'div'" class="flex flex-col gap-2 bg-white px-1.5 pt-3 pb-1">
						<div v-if="!activeBarsList.length" class="rounded-[4px] border border-dashed border-[#dcdfe4] px-3 py-2.5 text-[12px] text-[#6b7280]">
							No mullions or transoms yet. Drag a divider onto a cell.
						</div>
						<div v-for="b in activeBarsList" :key="b.id" class="space-y-1">
							<button
								type="button"
								class="flex min-h-[60px] w-full items-center gap-3 rounded-[4px] border p-2 text-left transition"
								:class="flyoutOpen && (flyoutKey === 'mullion' || flyoutKey === 'transom') && store.selectedPath === b.id ? 'border-[#1a6fd4] bg-[#f8fbff]' : 'border-[#dcdfe4] bg-white hover:border-[#b6c6dd]'"
								@click="openItemFlyout('div', b.dir === 'h' ? 'transom' : 'mullion', b.id)"
							>
								<div class="flex size-[42px] shrink-0 items-center justify-center overflow-hidden rounded-[3px] border border-[#cfd4da] bg-[#f8fafc] p-1 text-[#2d4a7a]">
									<svg
										v-if="barPreviewFor(b).svg"
										xmlns="http://www.w3.org/2000/svg"
										:viewBox="barPreviewFor(b).viewBox"
										class="block h-full w-full"
										preserveAspectRatio="xMidYMid meet"
									>
										<g :transform="barPreviewFor(b).transform || undefined">
											<path
												:d="barPreviewFor(b).svg"
												fill="#CBD5E1"
												stroke="#334155"
												stroke-width="1.5"
												fill-rule="evenodd"
												vector-effect="non-scaling-stroke"
											/>
										</g>
									</svg>
									<span v-else :class="b.dir === 'v' ? 'lucide-columns-2' : 'lucide-rows-2'" class="size-5" aria-hidden="true" />
								</div>
								<div class="min-w-0 flex-1">
									<div class="truncate text-[12.5px] font-semibold text-[#2b2f36]">
										{{ b.id }} · {{ barPreviewFor(b).code ? barPreviewFor(b).title : (b.dir === 'v' ? 'Mullion' : 'Transom') }}
									</div>
									<div class="truncate font-mono text-[10.5px] text-[#6b7280]">
										{{ barPreviewFor(b).subtitle ? `${barPreviewFor(b).subtitle} · ` : '' }}@ {{ Math.round(b.dir === 'v' ? b.x : b.y) }} mm
									</div>
								</div>
								<span
									class="flex size-[30px] shrink-0 items-center justify-center rounded-[3px] text-sm font-semibold"
									:class="flyoutOpen && (flyoutKey === 'mullion' || flyoutKey === 'transom') && store.selectedPath === b.id ? 'bg-[#e6effb] text-[#1a6fd4]' : 'text-[#444]'"
								>&gt;</span>
							</button>
							<button
								type="button"
								class="ml-auto block text-[11px] font-medium text-[#1a6fd4] hover:underline"
								@click="onRemoveSplitPath(b.splitPath)"
							>
								Remove {{ b.id }}
							</button>
						</div>
					</div>
				</div>

				<!-- 6. Glazing Item -->
				<div>
					<button
						type="button"
						data-testid="acc-glaz"
						class="flex h-[42px] w-full items-center justify-between rounded-[7px] px-3.5 text-left text-[13.5px] font-semibold transition"
						:class="openAccordion === 'glaz' ? 'bg-[#edf4ff] text-[#1a6fd4]' : 'bg-[#f3f5f8] text-[#1e293b] hover:bg-[#eaedf2]'"
						@click="toggleAccordion('glaz')"
					>
						<span>Glazing Item</span>
						<span class="font-mono text-base leading-none opacity-80">{{ openAccordion === 'glaz' ? '−' : '+' }}</span>
					</button>
					<div v-show="openAccordion === 'glaz'" class="flex flex-col gap-2 bg-white px-1.5 pt-3 pb-1">
						<div
							v-for="grp in glassGroups"
							:key="grp.key"
							class="flex min-h-[58px] items-center gap-3 rounded-[4px] border border-[#dcdfe4] bg-white p-2"
						>
							<div class="flex size-[42px] shrink-0 items-center justify-center rounded-[3px] border border-[#2d4a7a] bg-[#e6f5fb] text-[#2d4a7a]">
								<span class="lucide-square size-5" aria-hidden="true" />
							</div>
							<div class="min-w-0 flex-1">
								<div class="truncate text-[12.5px] font-semibold text-[#2b2f36]">{{ grp.label }}</div>
								<div class="mt-1 flex flex-wrap gap-1">
									<span v-for="lbl in grp.cellLabels" :key="lbl" class="rounded-[3px] border border-[#777] px-1.5 text-[11px] font-medium text-[#2b2f36]">{{ lbl }}</span>
								</div>
							</div>
						</div>
						<button
							type="button"
							class="ml-auto rounded-[3px] bg-[#e3e5e8] px-3.5 py-2 text-[13px] font-medium text-[#2b2f36] hover:bg-[#d8dbe0]"
							@click="openItemFlyout('glaz', 'glass', glassGroups[0]?.firstPath)"
						>
							Change Glazing/mesh
						</button>
					</div>
				</div>

				<!-- 7. Bead (Shows Exact Selected Bead Profile DXF Thumbnail & Name) -->
				<div>
					<button
						type="button"
						data-testid="acc-bead"
						class="flex h-[42px] w-full items-center justify-between rounded-[7px] px-3.5 text-left text-[13.5px] font-semibold transition"
						:class="openAccordion === 'bead' ? 'bg-[#edf4ff] text-[#1a6fd4]' : 'bg-[#f3f5f8] text-[#1e293b] hover:bg-[#eaedf2]'"
						@click="toggleAccordion('bead')"
					>
						<span>Bead</span>
						<span class="font-mono text-base leading-none opacity-80">{{ openAccordion === 'bead' ? '−' : '+' }}</span>
					</button>
					<div v-show="openAccordion === 'bead'" class="bg-white px-1.5 pt-3 pb-1">
						<button
							type="button"
							class="flex min-h-[60px] w-full items-center gap-3 rounded-[4px] border p-2 text-left transition"
							:class="flyoutOpen && flyoutKey === 'bead' ? 'border-[#1a6fd4] bg-[#f8fbff]' : 'border-[#dcdfe4] bg-white hover:border-[#b6c6dd]'"
							@click="openItemFlyout('bead', 'bead')"
						>
							<div class="flex size-[42px] shrink-0 items-center justify-center overflow-hidden rounded-[3px] border border-[#cfd4da] bg-[#f8fafc] p-1 text-[#2d4a7a]">
								<svg
									v-if="beadPreview.svg"
									xmlns="http://www.w3.org/2000/svg"
									:viewBox="beadPreview.viewBox"
									class="block h-full w-full"
									preserveAspectRatio="xMidYMid meet"
								>
									<g :transform="beadPreview.transform || undefined">
										<path
											:d="beadPreview.svg"
											fill="#CBD5E1"
											stroke="#334155"
											stroke-width="1.5"
											fill-rule="evenodd"
											vector-effect="non-scaling-stroke"
										/>
									</g>
								</svg>
								<span v-else class="lucide-box-select size-5" aria-hidden="true" />
							</div>
							<div class="min-w-0 flex-1">
								<div class="truncate text-[12.5px] font-semibold text-[#2b2f36]">
									{{ beadPreview.code ? beadPreview.title : 'Glazing Bead & Gasket' }}
								</div>
								<div class="truncate font-mono text-[10.5px] text-[#6b7280]">
									{{ beadPreview.subtitle || 'Series rule default' }}
								</div>
							</div>
							<span
								class="flex size-[30px] shrink-0 items-center justify-center rounded-[3px] text-sm font-semibold"
								:class="flyoutOpen && flyoutKey === 'bead' ? 'bg-[#e6effb] text-[#1a6fd4]' : 'text-[#444]'"
							>&gt;</span>
						</button>
					</div>
				</div>

				<!-- 8. Add-ons (Louver / Exhaust Fan / Grill) -->
				<div v-if="louverCells.length || fanCells.length || grillCells.length">
					<button
						type="button"
						data-testid="acc-addons"
						class="flex h-[42px] w-full items-center justify-between rounded-[7px] px-3.5 text-left text-[13.5px] font-semibold transition"
						:class="openAccordion === 'addons' ? 'bg-[#edf4ff] text-[#1a6fd4]' : 'bg-[#f3f5f8] text-[#1e293b] hover:bg-[#eaedf2]'"
						@click="toggleAccordion('addons')"
					>
						<span>Add-ons</span>
						<span class="font-mono text-base leading-none opacity-80">{{ openAccordion === 'addons' ? '−' : '+' }}</span>
					</button>
					<div v-show="openAccordion === 'addons'" class="flex flex-col gap-2 bg-white px-1.5 pt-3 pb-1">
						<button
							v-if="louverCells.length"
							type="button"
							class="flex w-full items-center justify-between rounded-[4px] border border-[#dcdfe4] p-2.5 text-left text-[13px] font-semibold hover:border-[#b6c6dd]"
							@click="openItemFlyout('addons', 'louver', louverCells[0].path)"
						>
							<span>Louver ({{ louverCells.length }})</span>
							<span>&gt;</span>
						</button>
						<button
							v-if="fanCells.length"
							type="button"
							class="flex w-full items-center justify-between rounded-[4px] border border-[#dcdfe4] p-2.5 text-left text-[13px] font-semibold hover:border-[#b6c6dd]"
							@click="openItemFlyout('addons', 'fan', fanCells[0].path)"
						>
							<span>Exhaust Fan Cut ({{ fanCells.length }})</span>
							<span>&gt;</span>
						</button>
						<button
							v-if="grillCells.length"
							type="button"
							class="flex w-full items-center justify-between rounded-[4px] border border-[#dcdfe4] p-2.5 text-left text-[13px] font-semibold hover:border-[#b6c6dd]"
							@click="openItemFlyout('addons', 'grill', `GRILL:${grillCells[0].path}`)"
						>
							<span>Grill ({{ grillCells.length }})</span>
							<span>&gt;</span>
						</button>
					</div>
				</div>

				<!-- Engineering Issues -->
				<div
					v-for="(issue, idx) in activeIssues"
					:key="idx"
					class="rounded-[4px] border p-2.5 text-xs"
					:class="
						issue.severity === 'error'
							? 'border-red-200 bg-red-50/80 text-red-900'
							: 'border-amber-200 bg-amber-50/80 text-amber-900'
					"
				>
					<div class="font-semibold">
						{{ issue.severity === 'error' ? 'Engineering Error' : 'Engineering Warning' }}
						<span v-if="issue.panel" class="font-mono text-[11px] opacity-75">· {{ issue.panel }}</span>
					</div>
					<p class="mt-1 leading-relaxed opacity-90">
						{{ issue.message }}
						<template v-if="issue.hint"> — {{ issue.hint }}</template>
					</p>
				</div>

				<p
					v-if="profileAssignmentError"
					class="rounded-[4px] border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
					role="alert"
				>
					{{ profileAssignmentError }}. The previous profile is still selected.
				</p>
			</div>
		</aside>

		<!-- ─── DOCKED SECONDARY FLYOUT: CUSTOM COLOR (.fly, 320px) ── -->
		<section
			v-show="flyoutOpen && flyoutKey === 'finish'"
			data-testid="eva-finish-flyout"
			class="flex min-h-0 w-full shrink-0 flex-col border-b border-[#dcdfe4] bg-white shadow-[2px_0_8px_rgba(0,0,0,0.06)] md:w-[320px] md:border-r md:border-b-0"
			style="font-family: 'Segoe UI', Inter, Arial, sans-serif"
		>
			<div class="flex h-[48px] shrink-0 items-center justify-between border-b border-[#edf0f4] px-3.5">
				<span class="text-[14.5px] font-semibold text-[#0f172a]">Custom color</span>
				<button type="button" aria-label="Close finish drawer" class="flex size-7 items-center justify-center rounded-[6px] text-[#64748b] transition-colors hover:bg-[#f1f5f9] hover:text-[#0f172a]" @click="cancelFlyout">
					<span class="lucide-x size-4" aria-hidden="true" />
				</button>
			</div>
			<div data-testid="design-finish-field" class="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3.5">
				<!-- Search + A-Z sort -->
				<div class="flex items-center gap-2">
					<div class="flex h-[36px] flex-1 items-center gap-1.5 rounded-[7px] border border-[#d5dbe3] bg-white px-2.5 text-[#64748b] shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-colors focus-within:border-[#1a6fd4] focus-within:ring-[3px] focus-within:ring-[#1a6fd4]/12">
						<span class="lucide-search size-3.5 shrink-0" aria-hidden="true" />
						<input
							v-model="colorSearch"
							type="text"
							placeholder="Search finish..."
							class="w-full border-0 bg-transparent text-[13px] text-[#0f172a] outline-none placeholder:text-[#94a3b8]"
						/>
					</div>
					<button
						type="button"
						class="flex h-[36px] shrink-0 items-center gap-1 rounded-[7px] border border-[#d5dbe3] bg-white px-2.5 text-[12px] font-medium text-[#334155] shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:border-[#9aa5b4] hover:bg-[#f8fafc]"
						@click="colorSortAsc = !colorSortAsc"
					>
						<span>{{ colorSortAsc ? 'A–Z' : 'Z–A' }}</span>
					</button>
				</div>

				<!-- Color mode radios (exact Eva prototype — staged in finishDraft until Apply) -->
				<div class="space-y-1.5">
					<div class="text-[12px] font-semibold text-[#2b2f36]">Color mode</div>
					<div class="flex items-center gap-3.5 text-[12.5px] text-[#2b2f36]">
						<label class="flex cursor-pointer items-center gap-1.5">
							<input type="radio" name="eva-color-mode" value="none" :checked="draftColorMode === 'none'" class="accent-[#1a6fd4]" @change="setDraftColorMode('none')" />
							<span>No color</span>
						</label>
						<label class="flex cursor-pointer items-center gap-1.5">
							<input type="radio" name="eva-color-mode" value="single" :checked="draftColorMode === 'single'" class="accent-[#1a6fd4]" @change="setDraftColorMode('single')" />
							<span>Single color</span>
						</label>
						<label class="flex cursor-pointer items-center gap-1.5">
							<input type="radio" name="eva-color-mode" value="dual" :checked="draftColorMode === 'dual'" class="accent-[#1a6fd4]" @change="setDraftColorMode('dual')" />
							<span>Dual color</span>
						</label>
					</div>
				</div>

				<!-- Dual color Inside / Outside target toggle -->
				<div v-if="draftColorMode === 'dual'" class="grid grid-cols-2 gap-1.5 rounded-[4px] bg-[#f0f1f3] p-1 text-[12px]">
					<button
						type="button"
						class="flex items-center justify-center gap-2 rounded-[3px] py-1.5 font-semibold transition"
						:class="colorDualTarget === 'in' ? 'bg-white text-[#1a6fd4] shadow-xs' : 'text-[#555]'"
						@click="colorDualTarget = 'in'"
					>
						<span class="size-3.5 rounded-[2px] border border-black/20" :style="{ backgroundColor: finishColorFor(draftFinish) }" />
						<span>Inside</span>
					</button>
					<button
						type="button"
						class="flex items-center justify-center gap-2 rounded-[3px] py-1.5 font-semibold transition"
						:class="colorDualTarget === 'out' ? 'bg-white text-[#1a6fd4] shadow-xs' : 'text-[#555]'"
						@click="colorDualTarget = 'out'"
					>
						<span class="size-3.5 rounded-[2px] border border-black/20" :style="{ backgroundColor: finishColorFor(draftFinishOutside || draftFinish) }" />
						<span>Outside</span>
					</button>
				</div>

				<div v-if="draftColorMode === 'none'" class="rounded-[4px] border border-[#dcdfe4] bg-[#f7f8fa] px-3 py-2.5 text-[12px] text-[#555]">
					Mill finish (uncoated aluminium). Pick any swatch below to switch to coated finish.
				</div>

				<!-- Collapsible Finish Categories + 3-Column Swatch Grid (backed by Frappe Profile Finish) -->
				<div v-for="grp in groupedFinishes" :key="grp.name" class="space-y-2">
					<button
						type="button"
						class="flex h-[38px] w-full items-center justify-between rounded-[4px] px-3 text-left text-[13px] font-semibold transition"
						:class="openFinishGroup === grp.name ? 'bg-[#e6effb] text-[#1a6fd4]' : 'bg-[#f0f1f3] text-[#2b2f36] hover:bg-[#e7e9ed]'"
						@click="toggleFinishGroup(grp.name)"
					>
						<span>{{ grp.name }}</span>
						<span class="text-xs">{{ openFinishGroup === grp.name ? '∧' : '∨' }}</span>
					</button>
					<div v-show="openFinishGroup === grp.name" class="grid grid-cols-3 gap-x-2.5 gap-y-3 px-0.5 pt-1">
						<button
							v-for="f in grp.items"
							:key="f.name"
							type="button"
							data-testid="finish-swatch-tile"
							class="flex flex-col items-center gap-1 rounded-[4px] p-1 text-center transition hover:bg-[#f5f8fc]"
							:class="isSwatchActive(f.name) ? 'ring-2 ring-[#1a6fd4] bg-[#f0f6ff]' : ''"
							@click="pickFinishSwatch(f.name)"
						>
							<span
								class="block aspect-square w-full rounded-[2px] border border-black/15"
								:style="{ backgroundColor: f.color || '#8A8F98' }"
							/>
							<span class="line-clamp-3 w-full text-[10px] leading-tight text-[#374151]">
								{{ f.finish_name || f.name }}
							</span>
						</button>
					</div>
				</div>

				<div v-if="!groupedFinishes.length" class="rounded-[4px] border border-dashed border-[#dcdfe4] px-3 py-4 text-center text-xs text-gray-500">
					No finishes found in Profile Finish master.
				</div>
			</div>
			<div class="flex h-[54px] shrink-0 items-center justify-end gap-2.5 border-t border-[#edf0f4] px-3.5">
				<button type="button" class="h-[34px] rounded-[7px] px-3.5 text-[13px] font-medium text-[#475569] transition-colors hover:bg-[#f1f5f9] hover:text-[#0f172a]" @click="cancelFlyout">
					Cancel
				</button>
				<button type="button" class="h-[34px] rounded-[7px] bg-[#1a6fd4] px-4 text-[13px] font-semibold text-white shadow-xs transition-colors hover:bg-[#155db3]" @click="applyFlyout">
					Apply
				</button>
			</div>
		</section>

		<!-- ─── DOCKED SECONDARY FLYOUT: FRAME / SASH / DIVIDER / GLAZING / BEAD (.fly, 320px) ── -->
		<section
			v-show="flyoutOpen && flyoutKey !== 'finish'"
			data-testid="series-profiles-card"
			class="flex min-h-0 w-full shrink-0 flex-col border-b border-[#dcdfe4] bg-white shadow-[2px_0_8px_rgba(0,0,0,0.06)] md:w-[320px] md:border-r md:border-b-0"
			style="font-family: 'Segoe UI', Inter, Arial, sans-serif"
		>
			<div class="flex h-[48px] shrink-0 items-center justify-between border-b border-[#edf0f4] px-3.5">
				<span class="text-[14.5px] font-semibold text-[#0f172a]">{{ flyoutTitle }}</span>
				<button
					type="button"
					aria-label="Close property drawer"
					class="flex size-7 items-center justify-center rounded-[6px] text-[#64748b] transition-colors hover:bg-[#f1f5f9] hover:text-[#0f172a]"
					@click="cancelFlyout"
				>
					<span class="lucide-x size-4" aria-hidden="true" />
				</button>
			</div>

			<div data-testid="eva-secondary-flyout" class="eva-fly-body flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3.5">
				<template v-for="row in seriesProfileRows" :key="row.key">
					<div v-show="flyoutKey === row.key" class="flex flex-col gap-3">
						<!-- Frame F1 Exact Prototype Top Controls (Brand, System, Frame configuration, Mode info) -->
						<template v-if="row.key === 'frame'">
							<div>
								<label class="eva-field-label">Brand</label>
								<input
									type="text"
									:value="activeSeriesBrand"
									disabled
									class="eva-field-input"
								/>
							</div>
							<div>
								<Select
									label="System"
									required
									aria-label="Frame system"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="seriesVersionOptions"
									:model-value="store.seriesVersion"
									@update:model-value="store.setSeriesVersion(String($event ?? ''))"
								/>
							</div>
							<div data-testid="series-sub-frame-config">
								<Select
									label="Frame configuration"
									required
									aria-label="Frame configuration"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="FRAME_CONFIG_OPTIONS"
									:model-value="frameConfig"
									@update:model-value="setFrameConfig(String($event ?? '4-side') as FrameConfig)"
								/>
							</div>
							<div v-if="frameConfig === '3-side'" class="rounded-[4px] border border-[#e3e7ee] bg-[#f7f8fa] px-3 py-2 text-[11.5px] text-[#4b5563]">
								<div class="font-semibold text-[#2b2f36]">3 Side Open Bottom</div>
								No bottom frame profile (floor-to-ceiling / door jamb mode).
							</div>
							<div v-else-if="frameConfig === '3-side-threshold'" class="rounded-[4px] border border-[#e3e7ee] bg-[#f7f8fa] px-3 py-2 text-[11.5px] text-[#4b5563]">
								<div class="font-semibold text-[#2b2f36]">Low Threshold Mode</div>
								Bottom uses low threshold sill bar; T/L/R use door frame.
							</div>
						</template>

						<!-- Glazing Item Prototype Top Controls (Select item + Item thickness, 1 per row — NO duplicate picker) -->
						<template v-if="row.key === 'glass' && activeGlassCell">
							<div class="space-y-1">
								<label class="block text-[12.5px] font-medium text-[#2b2f36]">Select item</label>
								<select
									:value="glazeItemType"
									aria-label="Select item"
									class="h-[38px] w-full rounded-[3px] border border-[#cfd4da] bg-white px-2.5 text-[13px] text-[#2b2f36] focus:border-[#1a6fd4] focus:outline-none"
									@change="onChangeGlazeItemType(($event.target as HTMLSelectElement).value as 'Glass' | 'Panel')"
								>
									<option value="Glass">Glass</option>
									<option value="Panel">Panel / Wood / Steel</option>
								</select>
							</div>
							<div v-if="glazeItemType === 'Glass'" class="space-y-1">
								<label class="block text-[12.5px] font-medium text-[#2b2f36]">Item thickness</label>
								<select
									v-model="glazeThickness"
									aria-label="Item thickness"
									class="h-[38px] w-full rounded-[3px] border border-[#cfd4da] bg-white px-2.5 text-[13px] text-[#2b2f36] focus:border-[#1a6fd4] focus:outline-none"
								>
									<option value="all">All thicknesses</option>
									<option v-for="t in availableGlassThicknesses" :key="t" :value="String(t)">{{ t }} mm</option>
								</select>
							</div>
						</template>

						<!-- Divider Caption -->
						<div v-if="row.key === 'mullion' || row.key === 'transom'" class="text-[11px] font-bold tracking-wider uppercase text-[#475569]">
							FRAME {{ row.key === 'mullion' ? 'MULLION' : 'TRANSOM' }}
						</div>

						<!-- Frappe DXF Profile Selector + Compact Thumbnail Dropdown -->
						<div v-if="row.hasSelector && row.key !== 'glass'" :data-testid="row.testid" style="display: flex; flex-direction: column; gap: 4px; min-width: 0; position: relative">
							<span style="font-size: 12px; font-weight: 500; color: #5b6472">{{ row.label }}</span>
							<button
								type="button"
								:data-testid="`profile-picker-btn-${row.key}`"
								:style="selectorBoxStyle"
								@click="toggleProfileDropdown(row.key)"
							>
								<template v-if="row.profile && (row.profile.code || row.profile.svg)">
									<div
										:data-testid="`profile-thumb-${row.key}`"
										style="width: 38px; height: 38px; flex-shrink: 0; border: 1px solid #e2e8f0; border-radius: 5px; background: #f8fafc; display: flex; align-items: center; justify-content: center; padding: 3px; overflow: hidden"
									>
										<svg
											v-if="row.profile.svg"
											xmlns="http://www.w3.org/2000/svg"
											:viewBox="row.profile.viewBox"
											style="width: 100%; height: 100%; display: block"
											preserveAspectRatio="xMidYMid meet"
										>
											<g :transform="row.profile.transform || undefined">
												<path
													:d="row.profile.svg"
													fill="#CBD5E1"
													stroke="#334155"
													stroke-width="1.5"
													fill-rule="evenodd"
													vector-effect="non-scaling-stroke"
												/>
											</g>
										</svg>
										<span v-else style="font-family: 'JetBrains Mono', monospace; font-size: 9px; font-weight: 600; color: #64748b">
											{{ row.profile.code || '—' }}
										</span>
									</div>
									<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px">
										<span style="font-size: 12px; font-weight: 600; color: #14171c; line-height: 1.25; overflow-wrap: anywhere">
											{{ row.profile.title }}
										</span>
										<span
											v-if="row.profile.subtitle"
											style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #5b6472; line-height: 1.25; overflow-wrap: anywhere"
										>
											{{ row.profile.subtitle }}
										</span>
									</div>
								</template>
								<span v-else style="flex: 1; min-width: 0; line-height: 1.3; overflow-wrap: anywhere">
									{{ row.profile ? row.profile.title : row.displayLabel }}
								</span>
								<span
									style="width: 12px; height: 12px; display: inline-block; flex-shrink: 0; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%235b6472' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E&quot;)"
									aria-hidden="true"
								/>
							</button>
							<!-- Compact Role-Filtered Thumbnail Dropdown -->
							<div
								v-if="openProfileDropdown === row.key"
								:data-testid="`profile-dropdown-${row.key}`"
								class="mt-1 flex max-h-[250px] flex-col gap-1 overflow-y-auto rounded-[4px] border border-[#cfd4da] bg-white p-1.5 shadow-[0_6px_18px_rgba(0,0,0,0.12)]"
							>
								<button
									v-for="opt in profilesForDropdown(row.key as ProfileRoleKey)"
									:key="opt.code"
									type="button"
									data-testid="profile-dropdown-item"
									class="flex w-full items-center gap-2.5 rounded-[3px] border p-1.5 text-left transition"
									:class="(row.profile?.code || '') === opt.code ? 'border-[#1a6fd4] bg-[#eef5ff]' : 'border-transparent hover:bg-[#f5f7fa]'"
									@click="selectDropdownProfile(row.key as ProfileRoleKey, row.key, opt.code)"
								>
									<div class="flex size-[34px] shrink-0 items-center justify-center overflow-hidden rounded-[3px] border border-[#e2e8f0] bg-[#f8fafc] p-0.5">
										<svg
											v-if="opt.svg"
											xmlns="http://www.w3.org/2000/svg"
											:viewBox="opt.viewBox"
											class="block h-full w-full"
											preserveAspectRatio="xMidYMid meet"
										>
											<g :transform="opt.transform || undefined">
												<path :d="opt.svg" fill="#CBD5E1" stroke="#334155" stroke-width="1.5" fill-rule="evenodd" vector-effect="non-scaling-stroke" />
											</g>
										</svg>
										<span v-else class="font-mono text-[8.5px] font-semibold text-[#64748b]">{{ opt.code }}</span>
									</div>
									<div class="min-w-0 flex-1">
										<div class="truncate text-[12px] font-semibold text-[#14171c]">{{ opt.title }}</div>
										<div class="truncate font-mono text-[10px] text-[#5b6472]">{{ opt.subtitle || opt.code }}</div>
									</div>
								</button>
								<div v-if="!profilesForDropdown(row.key as ProfileRoleKey).length" class="px-2 py-2 text-[11.5px] text-[#6b7280]">
									No {{ row.label.toLowerCase() }} profiles in this series.
								</div>
								<button
									type="button"
									data-testid="profile-dropdown-browse-all"
									class="mt-0.5 border-t border-[#eef0f3] px-2 pt-1.5 pb-0.5 text-left text-[11px] font-medium text-[#1a6fd4] hover:underline"
									@click="openProfileDropdown = null; row.onOpen?.()"
								>
									Browse full catalog...
								</button>
							</div>
							<Select
								v-if="row.onSelect && (row.selectLabel || row.selectAriaLabel)"
								style="display: none"
								:label="row.selectLabel"
								:aria-label="row.selectAriaLabel"
								:options="row.options"
								:model-value="row.modelValue"
								@update:model-value="row.onSelect(optStr($event))"
							/>
						</div>
						<div v-else-if="row.hasSelector && row.key === 'glass'" :data-testid="row.testid" style="display: flex; flex-direction: column; gap: 4px; min-width: 0">
							<Select
								v-if="row.onSelect && (row.selectLabel || row.selectAriaLabel)"
								style="display: none"
								:label="row.selectLabel"
								:aria-label="row.selectAriaLabel"
								:options="row.options"
								:model-value="row.modelValue"
								@update:model-value="row.onSelect(optStr($event))"
							/>
						</div>

						<!-- Sub-panel: Frame (Single-open Top / Left / Bottom / Right accordions + cut specs) -->
						<template v-if="row.key === 'frame'">
							<div class="flex flex-col gap-2">
								<div v-for="s in frameSidesList" :key="s.side" class="overflow-hidden rounded-[4px]">
									<button
										type="button"
										:data-testid="`frame-side-acc-${s.side}`"
										class="flex h-[40px] w-full items-center justify-between px-3 text-left text-[13px] font-semibold transition"
										:class="openFrameSide === s.side ? 'bg-[#e6effb] text-[#1a6fd4]' : 'bg-[#f0f1f3] text-[#2b2f36] hover:bg-[#e7e9ed]'"
										@click="toggleFrameSide(s.side)"
									>
										<span class="flex items-center gap-2">
											<span>{{ s.label }}</span>
											<span v-if="isFrameSideOverridden(s.side)" class="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
												Overridden
											</span>
										</span>
										<span class="text-xs">{{ openFrameSide === s.side ? '∧' : '∨' }}</span>
									</button>
									<div v-show="openFrameSide === s.side" class="space-y-2 border border-t-0 border-[#e5e7eb] bg-white p-2.5">
										<label class="block text-[12px] font-medium text-[#2b2f36]">Profile</label>
										<button
											type="button"
											:data-testid="`profile-picker-btn-F1.${s.side}`"
											:style="selectorBoxStyle"
											@click="toggleProfileDropdown(`F1.${s.side}`)"
										>
											<div class="flex size-[36px] shrink-0 items-center justify-center overflow-hidden rounded-[4px] border border-[#e2e8f0] bg-[#f8fafc] p-0.5">
												<svg
													v-if="resolveProfilePreview('frame', store.design.profiles?.[`F1.${s.side}`] || frameProfileValue).svg"
													xmlns="http://www.w3.org/2000/svg"
													:viewBox="resolveProfilePreview('frame', store.design.profiles?.[`F1.${s.side}`] || frameProfileValue).viewBox"
													class="block h-full w-full"
													preserveAspectRatio="xMidYMid meet"
												>
													<g :transform="resolveProfilePreview('frame', store.design.profiles?.[`F1.${s.side}`] || frameProfileValue).transform || undefined">
														<path
															:d="resolveProfilePreview('frame', store.design.profiles?.[`F1.${s.side}`] || frameProfileValue).svg"
															fill="#CBD5E1"
															stroke="#334155"
															stroke-width="1.5"
															fill-rule="evenodd"
															vector-effect="non-scaling-stroke"
														/>
													</g>
												</svg>
												<span v-else class="font-mono text-[9px] font-semibold text-[#64748b]">
													{{ resolveProfilePreview('frame', store.design.profiles?.[`F1.${s.side}`] || frameProfileValue).code || '—' }}
												</span>
											</div>
											<div class="min-w-0 flex-1">
												<div class="truncate text-[12px] font-semibold text-[#14171c]">
													{{
														store.design.profiles?.[`F1.${s.side}`]
															? resolveProfilePreview('frame', store.design.profiles[`F1.${s.side}`]).title
															: `Series default (${resolveProfilePreview('frame', frameProfileValue).code || 'Rule'})`
													}}
												</div>
												<div class="truncate font-mono text-[10px] text-[#5b6472]">
													{{ resolveProfilePreview('frame', store.design.profiles?.[`F1.${s.side}`] || frameProfileValue).subtitle }}
												</div>
											</div>
											<span
												style="width: 12px; height: 12px; display: inline-block; flex-shrink: 0; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%235b6472' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E&quot;)"
												aria-hidden="true"
											/>
										</button>
										<div
											v-if="openProfileDropdown === `F1.${s.side}`"
											:data-testid="`profile-dropdown-F1.${s.side}`"
											class="flex max-h-[220px] flex-col gap-1 overflow-y-auto rounded-[4px] border border-[#cfd4da] bg-white p-1.5 shadow-[0_6px_18px_rgba(0,0,0,0.12)]"
										>
											<button
												type="button"
												class="flex w-full items-center gap-2 rounded-[3px] px-2 py-1.5 text-left text-[12px] font-medium transition"
												:class="!store.design.profiles?.[`F1.${s.side}`] ? 'bg-[#eef5ff] text-[#1a6fd4]' : 'text-[#2b2f36] hover:bg-[#f5f7fa]'"
												@click="openProfileDropdown = null; resetFrameSideOverride(s.side)"
											>
												<span>Series default ({{ resolveProfilePreview('frame', frameProfileValue).code || 'Rule' }})</span>
											</button>
											<button
												v-for="opt in profilesForDropdown('frame')"
												:key="opt.code"
												type="button"
												data-testid="profile-dropdown-item"
												class="flex w-full items-center gap-2.5 rounded-[3px] border p-1.5 text-left transition"
												:class="store.design.profiles?.[`F1.${s.side}`] === opt.code ? 'border-[#1a6fd4] bg-[#eef5ff]' : 'border-transparent hover:bg-[#f5f7fa]'"
												@click="selectDropdownProfile('frame', `F1.${s.side}`, opt.code)"
											>
												<div class="flex size-[32px] shrink-0 items-center justify-center overflow-hidden rounded-[3px] border border-[#e2e8f0] bg-[#f8fafc] p-0.5">
													<svg
														v-if="opt.svg"
														xmlns="http://www.w3.org/2000/svg"
														:viewBox="opt.viewBox"
														class="block h-full w-full"
														preserveAspectRatio="xMidYMid meet"
													>
														<g :transform="opt.transform || undefined">
															<path :d="opt.svg" fill="#CBD5E1" stroke="#334155" stroke-width="1.5" fill-rule="evenodd" vector-effect="non-scaling-stroke" />
														</g>
													</svg>
													<span v-else class="font-mono text-[8.5px] font-semibold text-[#64748b]">{{ opt.code }}</span>
												</div>
												<div class="min-w-0 flex-1">
													<div class="truncate text-[12px] font-semibold text-[#14171c]">{{ opt.title }}</div>
													<div class="truncate font-mono text-[10px] text-[#5b6472]">{{ opt.subtitle || opt.code }}</div>
												</div>
											</button>
										</div>
										<div v-if="isFrameSideOverridden(s.side)" class="flex justify-end pt-0.5">
											<button
												type="button"
												class="text-[11.5px] font-medium text-red-600 hover:underline"
												@click="resetFrameSideOverride(s.side)"
											>
												Reset to rule
											</button>
										</div>
									</div>
								</div>
							</div>

							<div data-testid="series-sub-frame" :style="subPanelStyle">
								<div style="display: flex; flex-direction: column; gap: 4px; font-size: 11px">
									<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 10px">
										<div style="display: flex; align-items: center; justify-content: space-between; gap: 4px">
											<span style="color: #5b6472">Face width</span>
											<span style="font-family: 'JetBrains Mono', monospace; font-weight: 500; white-space: nowrap">{{ effectiveFrameFace }} mm</span>
										</div>
										<div style="display: flex; align-items: center; justify-content: space-between; gap: 4px">
											<span style="color: #5b6472">Cut</span>
											<span style="font-family: 'JetBrains Mono', monospace; font-weight: 500; white-space: nowrap">
												{{ Array.isArray(frameMember?.angles) ? frameMember.angles.map((a) => `${Number(a) === 135 ? 45 : a}°`).join(' / ') : '45° / 45°' }}
											</span>
										</div>
									</div>
									<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
										<span style="color: #5b6472; white-space: nowrap">{{ frameConfig === '4-side' ? 'Head & Sill' : 'Head' }}</span>
										<span style="font-family: 'JetBrains Mono', monospace; font-weight: 500; white-space: nowrap">
											{{ frameConfig === '4-side' ? '2' : '1' }} × {{ store.design.width }} mm
										</span>
									</div>
									<div v-if="frameConfig === '3-side-threshold'" style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
										<span style="color: #5b6472; white-space: nowrap">Threshold sill</span>
										<span style="font-family: 'JetBrains Mono', monospace; font-weight: 500; white-space: nowrap">1 × {{ store.design.width }} mm</span>
									</div>
									<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
										<span style="color: #5b6472; white-space: nowrap">Jambs</span>
										<span style="font-family: 'JetBrains Mono', monospace; font-weight: 500; white-space: nowrap">2 × {{ store.design.height }} mm</span>
									</div>
								</div>
							</div>
						</template>

						<!-- Sub-panel: Glass (Unified Single Selector + Square Apply-To + Auto Bead & Gasket by Frame & Glass Thickness) -->
						<div v-else-if="row.key === 'glass' && activeGlassCell" data-testid="series-sub-glass" :style="subPanelStyle">
							<div v-if="glazeItemType === 'Glass'" class="space-y-1">
								<div class="flex items-center justify-between">
									<label class="block text-[12.5px] font-medium text-[#2b2f36]">Item name <span class="text-red-500">*</span></label>
									<button
										type="button"
										data-testid="global-glass-button"
										class="text-[11.5px] font-medium text-[#1a6fd4] hover:underline"
										@click="openGlassPicker()"
									>
										Browse catalog ({{ glassDisplayText }})
									</button>
								</div>
								<select
									aria-label="Glazing item name"
									class="h-[38px] w-full rounded-[3px] border border-[#cfd4da] bg-white px-2.5 text-[13px] text-[#2b2f36] focus:border-[#1a6fd4] focus:outline-none"
									:value="activeGlassCell.node.glass"
									@change="applyGlassToTargets(($event.target as HTMLSelectElement).value)"
								>
									<option v-for="g in filteredGlassList" :key="g.name" :value="g.name">
										{{ g.glass_name || g.name }}{{ g.thickness_mm ? ` (${g.thickness_mm} mm)` : '' }}
									</option>
									<option v-if="!filteredGlassList.length" :value="activeGlassCell.node.glass">
										{{ formatGlassName(activeGlassCell.node.glass) }}
									</option>
								</select>
							</div>
							<div v-else class="space-y-1">
								<label class="block text-[12.5px] font-medium text-[#2b2f36]">Panel item <span class="text-red-500">*</span></label>
								<select
									aria-label="Panel item name"
									class="h-[38px] w-full rounded-[3px] border border-[#cfd4da] bg-white px-2.5 text-[13px] text-[#2b2f36] focus:border-[#1a6fd4] focus:outline-none"
									:value="activeGlassCell.node.panelItem || PANEL_ITEMS[0]"
									@change="applyPanelToTargets(($event.target as HTMLSelectElement).value)"
								>
									<option v-for="p in PANEL_ITEMS" :key="p" :value="p">{{ p }}</option>
								</select>
							</div>
							<div v-if="glassCells.length > 1" class="space-y-1.5">
								<div class="text-[12.5px] font-medium text-[#2b2f36]">Apply to</div>
								<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px">
									<button
										type="button"
										:style="{ ...pillStyle(!selectedGlassCell && glazeTargets.length === glassCells.length), minWidth: '46px', height: '42px', fontSize: '12.5px' }"
										@click="toggleGlazeAll"
									>
										All
									</button>
									<button
										v-for="(cell, idx) in glassCells"
										:key="cell.path"
										type="button"
										:style="{ ...pillStyle(glazeTargets.includes(cell.path) || selectedGlassCell?.path === cell.path), minWidth: '46px', height: '42px', fontSize: '12.5px' }"
										@click="toggleGlazeCell(cell.path)"
									>
										G{{ idx + 1 }}
									</button>
								</div>
							</div>
							<div data-testid="auto-bead-gasket-preview" class="rounded-[4px] border border-[#e3e7ee] bg-[#f7f8fa] p-2.5 text-[11.5px] leading-relaxed text-[#374151]">
								<div class="mb-1 text-[10.5px] font-semibold uppercase tracking-wide text-[#6b7280]">
									Auto Beading &amp; Gaskets ({{ autoBeadGasketPreview.frameDepth }} frame · {{ autoBeadGasketPreview.glassThickness }} glazing)
								</div>
								<div><span class="font-semibold text-[#1f2937]">Bead 1:</span> {{ autoBeadGasketPreview.bead }}</div>
								<div><span class="font-semibold text-[#1f2937]">Bead Gasket 1:</span> {{ autoBeadGasketPreview.beadGasket }}</div>
								<div><span class="font-semibold text-[#1f2937]">Frame Gasket:</span> {{ autoBeadGasketPreview.frameGasket }}</div>
							</div>
							<div class="space-y-1.5 border-t border-[#e6e8ec] pt-2 text-[12px]">
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">{{ activeGlassDims.label }} width</span>
									<span class="font-mono font-medium">{{ activeGlassDims.w }}</span>
								</div>
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">{{ activeGlassDims.label }} height</span>
									<span class="font-mono font-medium">{{ activeGlassDims.h }}</span>
								</div>
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">{{ activeGlassDims.label }} cut </span>
									<span class="font-mono font-medium">{{ activeGlassDims.cut }}</span>
								</div>
							</div>
						</div>

						<!-- Sub-panel: Sash (Strictly ONE Field Per Row + Exact Prototype Fields) -->
						<div v-else-if="row.key === 'sash' && activeSashCell && activeSashCell.node.type === 'sash'" data-testid="series-sub-sash" :style="subPanelStyle">
							<div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px">
								<div v-if="sashCells.length > 1" style="display: flex; flex-wrap: wrap; gap: 4px">
									<button v-for="cell in sashCells" :key="cell.path" type="button" :style="pillStyle(activeSashCell.path === cell.path)" @click="store.select(cell.path)">
										{{ cellLabel(cell.path) }}
									</button>
								</div>
								<span v-else style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #1b5fb8; background: #e8f0fc; border-radius: 4px; padding: 2px 6px">
									{{ cellLabel(activeSashCell.path) }}
								</span>
							</div>

							<!-- Sliding Panel Controls (when active sash is a sliding track leaf) -->
							<template v-if="activeSashCell.node.isSliding">
								<div class="flex items-center justify-between rounded-[7px] border border-[#e2e8f0] bg-[#f8fafc] px-3 py-2 text-[12px]">
									<span class="font-medium text-[#475569]">Sliding Track</span>
									<span class="font-mono font-semibold text-[#1a6fd4]">
										Track {{ (activeSashCell.node.trackIdx ?? 0) + 1 }} of {{ activeSashCell.node.trackCount ?? 2 }}
									</span>
								</div>
								<div>
									<Select
										label="Panel type"
										aria-label="Panel type"
										variant="outline"
										side="bottom"
										align="start"
										:offset="5"
										class="w-full"
										:options="SLIDE_MODE_OPTIONS"
										:model-value="activeSashCell.node.slideFixed ? 'fixed' : 'sliding'"
										@update:model-value="patchCell(activeSashCell.path, { slideFixed: $event === 'fixed', lock: $event === 'fixed' ? 'none' : (activeSashCell.node.lock && activeSashCell.node.lock !== 'none' ? activeSashCell.node.lock : 'singlepoint') })"
									/>
								</div>
								<div v-if="!activeSashCell.node.slideFixed">
									<Select
										label="Slide direction"
										aria-label="Slide direction"
										variant="outline"
										side="bottom"
										align="start"
										:offset="5"
										class="w-full"
										:options="SLIDE_DIR_OPTIONS"
										:model-value="activeSashCell.node.slideDir ?? 'right'"
										@update:model-value="patchCell(activeSashCell.path, { slideDir: ($event === 'left' ? 'left' : 'right') })"
									/>
								</div>
								<div v-if="!activeSashCell.node.slideFixed">
									<Select
										label="Glass Sash Locking"
										aria-label="Glass Sash Locking"
										variant="outline"
										side="bottom"
										align="start"
										:offset="5"
										class="w-full"
										:options="LOCKS"
										:model-value="activeSashCell.node.lock ?? 'singlepoint'"
										@update:model-value="patchCell(activeSashCell.path, { lock: String($event ?? 'singlepoint') })"
									/>
								</div>
								<div v-if="!activeSashCell.node.slideFixed">
									<Select
										label="Handle"
										aria-label="Handle"
										variant="outline"
										side="bottom"
										align="start"
										:offset="5"
										class="w-full"
										:options="HANDLES"
										:model-value="activeSashCell.node.handle ?? NONE"
										@update:model-value="patchCell(activeSashCell.path, { handle: optStr<'multipoint' | 'single'>($event) })"
									/>
								</div>
								<div>
									<Select
										label="Fly mesh"
										aria-label="Fly mesh"
										variant="outline"
										side="bottom"
										align="start"
										:offset="5"
										class="w-full"
										:options="meshOptions"
										:model-value="flagValue(activeSashCell.node.mesh)"
										@update:model-value="patchCell(activeSashCell.path, { mesh: flagPatch($event) })"
									/>
								</div>
							</template>
							<template v-else>
							<!-- 1. Sash configuration -->
							<div>
								<Select
									label="Sash configuration"
									aria-label="Sash configuration"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="SASH_CONFIG_OPTIONS"
									:model-value="activeSashCell.node.sashConfig ?? 'window'"
									@update:model-value="onChangeSashConfig(activeSashCell, $event)"
								/>
							</div>

							<!-- 2. Glass Sash Locking (Window) OR Leaf Role (Door) -->
							<template v-if="activeSashCell.node.sashConfig === 'door'">
								<div class="space-y-1.5">
									<span class="block text-[12px] font-medium text-[#475569]">Leaf Role (Double Door Active/Passive)</span>
									<div class="flex flex-col gap-1.5 text-[13px] text-[#0f172a]">
										<label class="flex cursor-pointer items-center gap-2">
											<input
												type="radio"
												name="eva-door-leaf"
												:checked="activeSashCell.node.activeLeaf !== false"
												class="accent-[#1a6fd4]"
												@change="patchCell(activeSashCell.path, { activeLeaf: true, handleItem: activeSashCell.node.handleItem || '(H420) DOOR HANDLE SET' })"
											/>
											<span>Active (Handle)</span>
										</label>
										<label class="flex cursor-pointer items-center gap-2">
											<input
												type="radio"
												name="eva-door-leaf"
												:checked="activeSashCell.node.activeLeaf === false"
												class="accent-[#1a6fd4]"
												@change="patchCell(activeSashCell.path, { activeLeaf: false, handleItem: undefined })"
											/>
											<span>Passive (Hinges only)</span>
										</label>
									</div>
								</div>
							</template>
							<div v-else>
								<Select
									label="Glass Sash Locking"
									aria-label="Glass Sash Locking"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="LOCKS"
									:model-value="activeSashCell.node.lock ?? 'multipoint'"
									@update:model-value="patchCell(activeSashCell.path, { lock: String($event ?? 'multipoint') })"
								/>
							</div>

							<!-- 3. Hinges And Friction Stay -->
							<div>
								<Select
									label="Hinges And Friction Stay"
									aria-label="Hinges And Friction Stay"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="HINGE_STAY_OPTIONS"
									:model-value="normalizedHingeStay(activeSashCell.node)"
									@update:model-value="onChangeHingeStay(activeSashCell, $event)"
								/>
							</div>

							<!-- 4. Hinge Side (1 per row) -->
							<div>
								<Select
									label="Hinge"
									aria-label="Hinge"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="HINGES"
									:model-value="activeSashCell.node.hinge ?? NONE"
									@update:model-value="patchCell(activeSashCell.path, { hinge: optStr($event) })"
								/>
							</div>

							<!-- 5. Opening (1 per row) -->
							<div>
								<Select
									label="Opening"
									aria-label="Opening"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="OPENINGS"
									:model-value="activeSashCell.node.opening ?? NONE"
									@update:model-value="patchCell(activeSashCell.path, { opening: optStr($event) })"
								/>
							</div>

							<!-- 6. Hinge type (1 per row) -->
							<div>
								<Select
									label="Hinge type"
									aria-label="Hinge type"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="HINGE_TYPES"
									:model-value="activeSashCell.node.hinge_type ?? NONE"
									@update:model-value="patchCell(activeSashCell.path, { hinge_type: optStr<'friction' | 'butt'>($event) })"
								/>
							</div>

							<!-- 7. Hardware Caption + Door / Window Handle & Hinge Items -->
							<template v-if="activeSashCell.node.sashConfig === 'door'">
								<div v-if="activeSashCell.node.activeLeaf !== false" class="space-y-1">
									<div class="pt-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-[#64748b]">
										Casement Active Door Sash Handle Locking Set
									</div>
									<Select
										aria-label="Door Handle Locking Set"
										variant="outline"
										side="bottom"
										align="start"
										:offset="5"
										class="w-full"
										:options="DOOR_HANDLE_SET_OPTIONS"
										:model-value="activeSashCell.node.handleItem || DOOR_HANDLE_SETS[0]"
										@update:model-value="patchCell(activeSashCell.path, { handleItem: String($event ?? DOOR_HANDLE_SETS[0]) })"
									/>
								</div>
								<div v-else class="rounded-[7px] border border-[#e2e8f0] bg-[#f8fafc] px-3 py-2 text-[12px] text-[#475569]">
									Passive door leaf — no handle or lock set; hinges only.
								</div>
								<div class="space-y-1">
									<div class="pt-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-[#64748b]">
										Side Hung Door Sash Hinge
									</div>
									<Select
										aria-label="Door Hinge Item"
										variant="outline"
										side="bottom"
										align="start"
										:offset="5"
										class="w-full"
										:options="DOOR_HINGE_ITEM_OPTIONS"
										:model-value="activeSashCell.node.hingeItem || DOOR_HINGE_ITEMS[0]"
										@update:model-value="patchCell(activeSashCell.path, { hingeItem: String($event ?? DOOR_HINGE_ITEMS[0]) })"
									/>
								</div>
							</template>
							<div v-else class="border-t border-[#eef2f6] pt-2 text-[10.5px] font-semibold uppercase tracking-wider text-[#64748b]">
								CASEMENT WINDOW {{ activeSashCell.node.lock === 'singlepoint' ? 'SINGLE' : 'MULTI' }} POINT LOCK
							</div>

							<!-- 8. Handle (1 per row) -->
							<div>
								<Select
									label="Handle"
									aria-label="Handle"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="HANDLES"
									:model-value="activeSashCell.node.handle ?? NONE"
									@update:model-value="patchCell(activeSashCell.path, { handle: optStr<'multipoint' | 'single'>($event) })"
								/>
							</div>

							<!-- 9. Opening limiter (1 per row) -->
							<div>
								<Select
									label="Opening limiter"
									aria-label="Opening limiter"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="limiterOptions"
									:model-value="flagValue(activeSashCell.node.limiter)"
									@update:model-value="patchCell(activeSashCell.path, { limiter: flagPatch($event) })"
								/>
							</div>

							<!-- 10. Fly mesh (1 per row) -->
							<div>
								<Select
									label="Fly mesh"
									aria-label="Fly mesh"
									variant="outline"
									side="bottom"
									align="start"
									:offset="5"
									class="w-full"
									:options="meshOptions"
									:model-value="flagValue(activeSashCell.node.mesh)"
									@update:model-value="patchCell(activeSashCell.path, { mesh: flagPatch($event) })"
								/>
							</div>

							<!-- 11. GHH (mm) (1 per row) -->
							<div>
								<label class="eva-field-label">GHH (mm)</label>
								<div class="relative">
									<input
										type="number"
										aria-label="GHH (mm)"
										class="eva-field-input pr-10 font-mono tabular-nums"
										:value="activeSashCell.node.ghh ?? ''"
										@change="patchCell(activeSashCell.path, { ghh: optNum($event) })"
									/>
									<span class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 font-mono text-[11px] font-medium text-[#94a3b8]">mm</span>
								</div>
							</div>

							<!-- 12. Allow sash equalization checkbox -->
							<label class="flex cursor-pointer items-center gap-2 pt-0.5 text-[13px] text-[#2b2f36]">
								<input
									type="checkbox"
									:checked="activeSashCell.node.allowEqualization !== false"
									class="size-4 accent-[#1a6fd4]"
									@change="patchCell(activeSashCell.path, { allowEqualization: ($event.target as HTMLInputElement).checked })"
								/>
								<span>Allow sash equalization</span>
							</label>
							</template>

							<!-- Computed Engineering Summary (1 stat per row) -->
							<div class="space-y-1.5 border-t border-[#e6e8ec] pt-2 text-[12px]">
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">Sash width</span>
									<span class="font-mono font-medium">{{ activeSashDims.w }}</span>
								</div>
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">Sash height</span>
									<span class="font-mono font-medium">{{ activeSashDims.h }}</span>
								</div>
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">Sash size</span>
									<span class="font-mono font-medium">{{ activeSashDims.size }}</span>
								</div>
								<div v-if="!activeSashCell.node.isSliding" class="flex items-center justify-between">
									<span class="text-[#5b6472]">Hinges</span>
									<span class="font-mono font-medium">{{ activeSashHingeCount }}</span>
								</div>
							</div>
						</div>

						<!-- Sub-panel: Mullion or Transom Bar (1 per row + prototype drag hint) -->
						<div v-else-if="(row.key === 'mullion' || row.key === 'transom') && activeBarMap[row.key]" :data-testid="`series-sub-${row.key}`" :style="subPanelStyle">
							<div v-if="activeBarMap[row.key]!.bars.length > 1" style="display: flex; flex-wrap: wrap; gap: 4px">
								<button v-for="b in activeBarMap[row.key]!.bars" :key="b.id" type="button" :style="pillStyle(activeBarMap[row.key]!.bar.id === b.id)" @click="store.select(b.id)">
									{{ b.id }}
								</button>
							</div>
							<div v-if="activeBarMap[row.key]!.split" class="space-y-2">
								<FormControl
									type="number"
									:label="`${activeBarMap[row.key]!.bar.id} position (mm)`"
									:model-value="activeBarMap[row.key]!.split!.at[activeBarMap[row.key]!.bar.index]"
									@change="moveSplitBar(activeBarMap[row.key]!.bar.splitPath, activeBarMap[row.key]!.bar.index, $event)"
								/>
								<div>
									<div class="flex items-center justify-between font-mono text-[11px] text-gray-500">
										<span>{{ row.key === 'mullion' ? 'Distance from Left' : 'Distance from Top' }}</span>
										<span>{{ activeBarMap[row.key]!.pct }}%</span>
									</div>
									<input
										type="range"
										min="10"
										max="90"
										:value="activeBarMap[row.key]!.pct"
										class="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-gray-200 accent-[#1a6fd4]"
										@input="onSlideSplitBar(activeBarMap[row.key]!.bar.splitPath, activeBarMap[row.key]!.bar.index, activeBarMap[row.key]!.bar.dir, $event)"
									/>
								</div>
							</div>
							<div class="rounded-[4px] border border-[#e3e7ee] bg-[#f7f8fa] px-3 py-2 text-[11.5px] text-[#4b5563]">
								You can also drag <b>{{ activeBarMap[row.key]!.bar.id }}</b> directly on the canvas to reposition it.
							</div>
							<div class="space-y-1.5 border-t border-[#e6e8ec] pt-2 text-[12px]">
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">Cut length</span>
									<span class="font-mono font-medium">{{ activeBarMap[row.key]!.cutLength }}</span>
								</div>
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">Span</span>
									<span class="font-mono font-medium">{{ activeBarMap[row.key]!.bar.length }} mm</span>
								</div>
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">Face width</span>
									<span class="font-mono font-medium">{{ activeBarMap[row.key]!.face }} mm</span>
								</div>
								<div class="flex items-center justify-between">
									<span class="text-[#5b6472]">Position</span>
									<span class="font-mono font-medium">
										{{ activeBarMap[row.key]!.bar.dir === 'v' ? activeBarMap[row.key]!.bar.x : activeBarMap[row.key]!.bar.y }} mm
									</span>
								</div>
								<div v-if="activeBarMap[row.key]!.member?.profile" class="flex items-center justify-between">
									<span class="text-[#5b6472]">Profile</span>
									<span class="font-mono font-medium">{{ activeBarMap[row.key]!.member!.profile }}</span>
								</div>
								<div v-if="activeBarMap[row.key]!.member?.angles" class="flex items-center justify-between">
									<span class="text-[#5b6472]">Cut angles</span>
									<span class="font-mono font-medium">
										{{ Array.isArray(activeBarMap[row.key]!.member!.angles) ? activeBarMap[row.key]!.member!.angles!.map((a) => `${Number(a) === 135 ? 45 : a}°`).join(' / ') : activeBarMap[row.key]!.member!.angles }}
									</span>
								</div>
							</div>
							<div class="flex justify-end border-t border-gray-200/70 pt-1.5">
								<button type="button" class="text-xs font-medium text-red-600 hover:underline" @click.prevent="onRemoveSplitPath(activeBarMap[row.key]!.bar.splitPath)">
									Remove split
								</button>
							</div>
						</div>

						<!-- Sub-panel: Bead (Prototype Automatic Rule + Top/Left/Bottom/Right breakdown + Frappe Controls) -->
						<div v-else-if="row.key === 'bead'" data-testid="series-sub-bead" :style="subPanelStyle">
							<div v-if="beadedCells.length > 1" style="display: flex; flex-wrap: wrap; align-items: center; gap: 4px">
								<button type="button" :style="pillStyle(!scopedBeadCell)" @click="store.select('')">All</button>
								<button v-for="cell in beadedCells" :key="cell.path" type="button" :style="pillStyle(scopedBeadCell?.path === cell.path)" @click="store.select(cell.path)">
									G{{ Math.max(1, glassCells.findIndex((g) => g.path === cell.path) + 1) }}
								</button>
							</div>
							<div class="rounded-[4px] border border-[#e3e7ee] bg-[#f7f8fa] p-2.5 text-[11.5px] text-[#374151]">
								<div class="text-[10.5px] font-semibold uppercase tracking-wide text-[#6b7280]">Automatic Rule Selection</div>
								Auto-selected from <b>{{ activeGlassThicknessLabel }}</b> glazing in <b>{{ store.seriesVersion || activeSeriesBrand }}</b>.
							</div>
							<div class="flex flex-col gap-1.5">
								<div v-for="side in (['Top', 'Left', 'Bottom', 'Right'] as const)" :key="side" class="overflow-hidden rounded-[4px]">
									<button
										type="button"
										class="flex h-[36px] w-full items-center justify-between px-3 text-left text-[12.5px] font-semibold transition"
										:class="openBeadSide === side ? 'bg-[#e6effb] text-[#1a6fd4]' : 'bg-[#f0f1f3] text-[#2b2f36] hover:bg-[#e7e9ed]'"
										@click="openBeadSide = openBeadSide === side ? null : side"
									>
										<span>{{ side }}</span>
										<span class="text-xs">{{ openBeadSide === side ? '∧' : '∨' }}</span>
									</button>
									<div v-show="openBeadSide === side" class="space-y-1 border border-t-0 border-[#e5e7eb] bg-white p-2.5 text-[11.5px]">
										<div><span class="text-[#6b7280]">Bead 1:</span> <span class="font-medium text-[#1f2937]">{{ autoBeadGasketPreview.bead }}</span></div>
										<div><span class="text-[#6b7280]">Bead Gasket 1:</span> <span class="font-medium text-[#1f2937]">{{ autoBeadGasketPreview.beadGasket }}</span></div>
										<div><span class="text-[#6b7280]">Frame Gasket:</span> <span class="font-medium text-[#1f2937]">{{ autoBeadGasketPreview.frameGasket }}</span></div>
									</div>
								</div>
							</div>
							<div class="space-y-1">
								<span class="block text-[12.5px] font-medium text-[#2b2f36]">Corners</span>
								<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); background: #eef0f3; border-radius: 7px; padding: 3px; gap: 3px">
									<button type="button" :style="beadJointValue === 'm' ? activeSegmentStyle : inactiveSegmentStyle" @click="onSetBeadJoint('m')">Mitre 45°</button>
									<button type="button" :style="beadJointValue === 'b' ? activeSegmentStyle : inactiveSegmentStyle" @click="onSetBeadJoint('b')">Square</button>
								</div>
							</div>
							<div class="flex items-center justify-between gap-2 pt-0.5">
								<span class="text-[12.5px] font-medium text-[#2b2f36]">Mirror to opposite side</span>
								<button type="button" :style="store.design.mirrorSync !== false ? syncOnStyle : syncOffStyle" @click="store.setMirrorSync(store.design.mirrorSync === false ? true : false)">
									{{ store.design.mirrorSync !== false ? 'On' : 'Off' }}
								</button>
							</div>
							<div class="flex flex-col gap-1.5 border-t border-[#e6e8ec] pt-2">
								<button type="button" style="height: 34px; border: 1px solid #d7dbe0; border-radius: 4px; background: #ffffff; font-size: 12.5px; font-weight: 500; cursor: pointer; color: #14171c" @click="onSetBeadAsDefault">Set as default</button>
								<button type="button" style="height: 34px; border: 1px solid #d7dbe0; border-radius: 4px; background: #ffffff; font-size: 12.5px; font-weight: 500; cursor: pointer; color: #14171c" @click="onResetBead">Reset bead</button>
							</div>
						</div>

						<!-- Sub-panel: Louver -->
						<div v-else-if="row.key === 'louver' && activeLouverCell && activeLouverCell.node.type === 'louver'" data-testid="series-sub-louver" :style="subPanelStyle">
							<div class="flex items-center justify-between">
								<span class="text-xs font-semibold text-gray-800">Louver · {{ cellLabel(activeLouverCell.path) }}</span>
								<div v-if="louverCells.length > 1" style="display: flex; flex-wrap: wrap; gap: 4px">
									<button v-for="cell in louverCells" :key="cell.path" type="button" :style="pillStyle(activeLouverCell.path === cell.path)" @click="store.select(cell.path)">
										{{ cellLabel(cell.path) }}
									</button>
								</div>
							</div>
							<FormControl type="number" label="Blades" min="1" :model-value="activeLouverCell.node.blades" @change="patchCell(activeLouverCell.path, { blades: num($event) })" />
							<FormControl type="number" label="Blade width (mm)" min="1" step="1" data-testid="louver-blade-width" :model-value="activeLouverCell.node.bladeWidth ?? DEFAULT_LOUVER_WIDTH" @change="num($event) > 0 && Number.isFinite(num($event)) && patchCell(activeLouverCell.path, { bladeWidth: num($event) })" />
							<div class="space-y-1.5">
								<span class="text-xs text-gray-600">Blade material</span>
								<div class="grid grid-cols-2 gap-1 rounded-lg bg-gray-100 p-1" role="group" aria-label="Blade material">
									<button v-for="material in (['metal', 'glass'] as const)" :key="material" type="button" :aria-pressed="(activeLouverCell.node.bladeMaterial ?? 'metal') === material" :style="(activeLouverCell.node.bladeMaterial ?? 'metal') === material ? activeSegmentStyle : inactiveSegmentStyle" @click="patchCell(activeLouverCell.path, { bladeMaterial: material })">
										{{ material === 'metal' ? 'Metal' : 'Glass' }}
									</button>
								</div>
							</div>
						</div>

						<!-- Sub-panel: Steel Exhaust Fan Cut -->
						<div v-else-if="row.key === 'fan' && activeFanCell" data-testid="exhaust-cut-controls" :style="subPanelStyle">
							<div class="flex items-center justify-between text-xs text-blue-700">
								<span>Exhaust fan cut · {{ cellLabel(activeFanCell.path) }}</span>
								<button type="button" @click="patchCell(activeFanCell.path, { fan: false })">Remove cut</button>
							</div>
							<div class="flex items-center justify-between text-xs">
								<span style="color: #5b6472">Material</span>
								<span data-testid="steel-infill" class="font-medium text-gray-900">Steel sheet</span>
							</div>
							<FormControl type="number" label="Steel thickness (mm)" :model-value="steelThickness(activeFanCell.node)" @change="patchCell(activeFanCell.path, { steelThickness: num($event) })" />
							<p v-if="activeFanCell.node.steelThickness !== undefined && (!Number.isFinite(activeFanCell.node.steelThickness) || activeFanCell.node.steelThickness <= 0)" class="text-xs text-red-600" role="alert">
								Enter a positive sheet thickness.
							</p>
							<FormControl type="number" label="Cut diameter (mm)" :model-value="activeFanDims.diameter" @change="patchCellFanCut(activeFanCell, 'diameter', num($event))" />
							<FormControl type="number" label="Centre from panel left (mm)" :model-value="activeFanDims.centerX" @change="patchCellFanCut(activeFanCell, 'centerX', num($event))" />
							<FormControl type="number" label="Centre from panel top (mm)" :model-value="activeFanDims.centerY" @change="patchCellFanCut(activeFanCell, 'centerY', num($event))" />
							<p v-if="activeFanDims.invalid" class="text-xs text-red-600" role="alert">Enter a positive diameter and keep the entire cut inside the panel.</p>
						</div>

						<!-- Sub-panel: Grill -->
						<div v-else-if="row.key === 'grill' && activeGrillCell && activeGrillCell.node.grill" data-testid="grill-controls" :style="subPanelStyle">
							<div class="flex items-center justify-between text-xs">
								<strong>Grill · {{ cellLabel(activeGrillCell.path) }}</strong>
								<button class="text-xs text-red-600" @click="patchCell(activeGrillCell.path, { grill: undefined })">Remove grill</button>
							</div>
							<FormControl v-for="field in grillFields" :key="field.key" type="number" :label="field.label" :model-value="grillConfig(activeGrillCell.node.grill)[field.key]" @change="patchCellGrill(activeGrillCell, field.key, num($event))" />
							<p class="text-xs text-gray-500">Depth is measured from the section datum. Negative values place the grill toward the inside.</p>
						</div>
					</div>
				</template>
			</div>

			<div class="flex h-[54px] shrink-0 items-center justify-end gap-2.5 border-t border-[#edf0f4] px-3.5">
				<button type="button" class="h-[34px] rounded-[7px] px-3.5 text-[13px] font-medium text-[#475569] transition-colors hover:bg-[#f1f5f9] hover:text-[#0f172a]" @click="cancelFlyout">
					Cancel
				</button>
				<button type="button" class="h-[34px] rounded-[7px] bg-[#1a6fd4] px-4 text-[13px] font-semibold text-white shadow-xs transition-colors hover:bg-[#155db3]" @click="applyFlyout">
					Apply
				</button>
			</div>
		</section>

		<ProfilePickerModal
			v-model="pickerOpen"
			:title="`Select ${pickerRole} profile`"
			:target-role="pickerRole"
			:current-profile="pickerCurrentProfile"
			:series="store.seriesVersion"
			:profiles="pickerProfiles"
			@select="onPickerSelect"
		/>
		<GlassPickerModal
			v-model="glassPickerOpen"
			title="Select glass"
			:current-glass="glassPickerCurrent"
			:series="store.seriesVersion"
			:glasses="pickerGlasses"
			@select="onGlassPickerSelect"
		/>
	</div>
</template>

<style scoped>
/* Unified modern CAD inspector field & dropdown styling across Basic Info rail and secondary drawers */
.eva-field-label,
.eva-fly-body :deep(label):not(:has(input[type='checkbox'])):not(:has(input[type='radio'])) {
	display: block !important;
	font-size: 12px !important;
	font-weight: 500 !important;
	letter-spacing: -0.005em !important;
	color: #475569 !important;
	margin-bottom: 5px !important;
}

.eva-rail-form :deep(.eva-field-input),
.eva-rail-form :deep(button[role='combobox']),
.eva-fly-body :deep(button[role='combobox']),
.eva-fly-body :deep(select),
.eva-fly-body :deep(input:not([type='checkbox']):not([type='radio']):not([type='range'])) {
	height: 36px !important;
	min-height: 36px !important;
	width: 100% !important;
	border-radius: 7px !important;
	border: 1px solid #d5dbe3 !important;
	background-color: #ffffff !important;
	color: #0f172a !important;
	font-size: 13px !important;
	font-weight: 500 !important;
	padding-left: 10px !important;
	padding-right: 10px !important;
	box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
	transition: border-color 150ms ease, box-shadow 150ms ease, background-color 150ms ease !important;
}

.eva-rail-form :deep(button[role='combobox']),
.eva-fly-body :deep(button[role='combobox']) {
	justify-content: space-between !important;
}

.eva-rail-form :deep(button[role='combobox'] [data-slot='chevron']),
.eva-fly-body :deep(button[role='combobox'] [data-slot='chevron']) {
	color: #64748b !important;
	transition: transform 150ms ease, color 150ms ease !important;
}

.eva-rail-form :deep(button[role='combobox'][data-state='open'] [data-slot='chevron']),
.eva-fly-body :deep(button[role='combobox'][data-state='open'] [data-slot='chevron']) {
	transform: rotate(180deg);
	color: #1a6fd4 !important;
}

.eva-rail-form :deep(.eva-field-textarea),
.eva-fly-body :deep(textarea) {
	min-height: 68px !important;
	height: auto !important;
	width: 100% !important;
	border-radius: 7px !important;
	border: 1px solid #d5dbe3 !important;
	background-color: #ffffff !important;
	color: #0f172a !important;
	font-size: 13px !important;
	font-weight: 400 !important;
	line-height: 1.45 !important;
	padding: 8px 10px !important;
	box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
	transition: border-color 150ms ease, box-shadow 150ms ease !important;
}

.eva-fly-body :deep(select) {
	appearance: none !important;
	-webkit-appearance: none !important;
	padding-right: 30px !important;
	cursor: pointer !important;
	background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E") !important;
	background-repeat: no-repeat !important;
	background-position: right 10px center !important;
	background-size: 14px 14px !important;
}

.eva-rail-form :deep(.eva-field-input:hover),
.eva-rail-form :deep(.eva-field-textarea:hover),
.eva-rail-form :deep(button[role='combobox']:hover),
.eva-fly-body :deep(button[role='combobox']:hover),
.eva-fly-body :deep(select:hover),
.eva-fly-body :deep(input:not([type='checkbox']):not([type='radio']):not([type='range']):hover),
.eva-fly-body :deep(textarea:hover) {
	border-color: #9aa5b4 !important;
}

.eva-rail-form :deep(.eva-field-input:focus),
.eva-rail-form :deep(.eva-field-textarea:focus),
.eva-rail-form :deep(button[role='combobox']:focus),
.eva-rail-form :deep(button[role='combobox'][data-state='open']),
.eva-fly-body :deep(button[role='combobox']:focus),
.eva-fly-body :deep(button[role='combobox'][data-state='open']),
.eva-fly-body :deep(select:focus),
.eva-fly-body :deep(input:not([type='checkbox']):not([type='radio']):not([type='range']):focus),
.eva-fly-body :deep(textarea:focus) {
	border-color: #1a6fd4 !important;
	outline: none !important;
	box-shadow: 0 0 0 3px rgba(26, 111, 212, 0.12) !important;
}

.eva-rail-form :deep(.eva-field-error) {
	border-color: #ef4444 !important;
	background-color: #fef2f2 !important;
	color: #7f1d1d !important;
}

.eva-rail-form :deep(.eva-field-error:focus) {
	border-color: #dc2626 !important;
	box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.14) !important;
}

.eva-rail-form :deep(input::placeholder),
.eva-rail-form :deep(textarea::placeholder),
.eva-fly-body :deep(input::placeholder),
.eva-fly-body :deep(textarea::placeholder) {
	color: #94a3b8 !important;
	font-weight: 400 !important;
}

.eva-rail-form :deep(input:disabled),
.eva-rail-form :deep(input:read-only),
.eva-fly-body :deep(input:disabled),
.eva-fly-body :deep(select:disabled),
.eva-fly-body :deep(button[role='combobox'][data-disabled]) {
	border-color: #e2e8f0 !important;
	background-color: #f8fafc !important;
	color: #64748b !important;
	box-shadow: none !important;
}
</style>
