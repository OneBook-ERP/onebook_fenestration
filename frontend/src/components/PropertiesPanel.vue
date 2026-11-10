<script setup lang="ts">
import { FormControl, Select, useList } from 'frappe-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { profileCatalog, type CatalogProfile } from '@/api'
import ProfilePickerModal, { type ProfileItem } from '@/components/ProfilePickerModal.vue'
import { layoutGeom } from '@/design/geometry'
import { getNode, moveSplit, removeSplit, setLeaf, setSize } from '@/design/tree'
import { panelLabel } from '@/design/typology'
import type { DesignNode, LeafNode, SplitNode } from '@/design/types'
import { useDesignerStore } from '@/stores/designer'

const FRAME_FACE_DEFAULT = 42
const BAR_FACE_DEFAULT = 40
const SASH_FACE_DEFAULT = 50

export interface Meta {
	ref: string
	qty: number
	location: string
}
const meta = defineModel<Meta>('meta', { required: true })
const props = defineProps<{
	refError?: string
	refReadonly?: boolean
	finishes?: { name: string; finish_name: string; color?: string }[]
	seriesVersions?: { name: string; series: string; version_note?: string }[]
}>()
const store = useDesignerStore()

const glassList = useList<{ name: string; glass_name: string }>({
	doctype: 'Fenestration Glass',
	fields: ['name', 'glass_name'],
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
}>({
	doctype: 'Fenestration Profile',
	fields: ['name', 'profile_code', 'profile_name', 'series', 'role', 'width_mm', 'depth_mm', 'section_svg', 'section_rotation'],
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
}
onMounted(() => void loadProfileCatalog())
watch(() => store.seriesVersion, () => void loadProfileCatalog())

const pickerOpen = ref(false)
const pickerRole = ref<'frame' | 'sash' | 'mullion' | 'transom' | 'bead' | 'all'>('all')
const pickerTargetKey = ref<string>('frame')
const profileAssignmentError = ref('')

function assignProfile(action: () => void) {
	try {
		profileAssignmentError.value = ''
		action()
	} catch (error) {
		profileAssignmentError.value = error instanceof Error ? error.message : 'Could not assign this profile'
	}
}

const pickerProfiles = computed<ProfileItem[]>(() => {
	const fallbackRows: CatalogProfile[] = (profileList.data ?? []).map((r) => ({
		...r,
		code: r.profile_code || r.name,
		has_outline: Boolean(r.section_svg),
		current_series: true,
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
		assignProfile(() => store.setProfile('frame', 'frame', code, role))
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

function onSetBeadProfile(code: string | undefined) {
	const item = pickerProfiles.value.find((p) => p.code === code)
	assignProfile(() => store.setProfile('bead', 'bead', code, item?.role || 'bead'))
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

defineExpose({ openProfilePicker })

const glassOptions = computed(() => {
	const codes = store.seriesInfo?.glasses
	const rows = (glassList.data ?? []).filter((g) => !codes || codes.includes(g.name))
	const opts = rows.map((g) => ({ label: `${g.glass_name || g.name} (${g.name})`, value: g.name }))
	const cur = leaf.value?.glass
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
const isGlassSelected = computed(() => store.selectedPath.startsWith('GLASS:'))
const effectiveCellPath = computed(() => store.selectedPath.replace(/^(GLASS|BEAD):/, ''))

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

const beadProfileValue = computed(() => store.design.beadProfileId ?? store.design.profiles?.bead ?? NONE)
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

const currentFinishObj = computed(() => (props.finishes ?? []).find((f) => f.name === store.finish))
const outsideFinishCode = computed(() => store.design.finishOutside || store.finish)
const outsideFinishObj = computed(
	() =>
		(props.finishes ?? []).find((f) => f.name === outsideFinishCode.value) || currentFinishObj.value,
)

function setOutsideFinish(code: string) {
	store.apply((d) => ({ ...d, finishOutside: code }))
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
const hasSash = computed(() => geom.value.cells.some((c) => c.node.type === 'sash'))
const hasBead = computed(() => geom.value.cells.some((c) => c.node.type === 'fixed' && c.node.bead !== false))
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
const designExpanded = ref(false)

const activeSegmentStyle = {
	height: '28px',
	border: '0',
	borderRadius: '5px',
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
	borderRadius: '5px',
	background: 'transparent',
	fontSize: '12px',
	fontWeight: '500',
	cursor: 'pointer',
	color: '#5b6472',
}

const syncOnStyle = {
	fontSize: '12px',
	fontWeight: '600',
	color: '#ffffff',
	background: '#1d6fdc',
	borderRadius: '999px',
	padding: '3px 10px',
	border: 'none',
	cursor: 'pointer',
}

const syncOffStyle = {
	fontSize: '12px',
	fontWeight: '500',
	color: '#5b6472',
	background: '#eef0f3',
	borderRadius: '999px',
	padding: '3px 10px',
	border: 'none',
	cursor: 'pointer',
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

const selectedObjectLabel = computed(() => {
	if (isBeadSelected.value) return 'Bead'
	if (isFrameSelected.value) return 'Frame F1'
	if (isGlassSelected.value) return `Glass ${selectedLabel.value}`
	if (leaf.value) return `${selectedLabel.value} · ${leaf.value.type}`
	if (selectedBar.value)
		return `${selectedBar.value.id} · ${selectedBar.value.dir === 'v' ? 'mullion' : 'transom'}`
	return ''
})
</script>

<template>
	<aside
		class="flex w-full shrink-0 flex-col gap-3 border-t border-gray-200 bg-gray-50/70 p-3 md:w-72 md:overflow-y-auto md:border-t-0 md:border-l lg:w-80"
		style="background: #f4f5f7; font-family: 'Inter', system-ui, sans-serif; color: #14171c; box-sizing: border-box"
	>
		<!-- ─── 1. DESIGN CARD (Collapsed by default) ──────────── -->
		<div style="background: #ffffff; border: 1px solid #e1e4e8; border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; gap: 10px">
			<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px">
				<div style="display: flex; flex-direction: column; gap: 3px; min-width: 0">
					<span style="font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #5b6472">DESIGN</span>
					<span style="font-size: 13px; font-weight: 500">
						{{ meta.ref || 'Untitled' }} · {{ store.design.width }} × {{ store.design.height }} mm · Qty {{ meta.qty }}
					</span>
				</div>
				<button
					type="button"
					aria-label="Expand design details"
					style="width: 32px; height: 32px; border: 1px solid #d7dbe0; border-radius: 6px; background: #ffffff; display: flex; align-items: center; justify-content: center; cursor: pointer"
					@click="designExpanded = !designExpanded"
				>
					<span
						style="width: 14px; height: 14px; display: inline-block; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%235b6472' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E&quot;)"
						:style="{ transform: designExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s ease' }"
						aria-hidden="true"
					/>
				</button>
			</div>

			<!-- Prominent Design Ref, Quantity, Dimensions (Collapsible) -->
			<div v-show="designExpanded" style="display: flex; flex-direction: column; gap: 10px; border-top: 1px solid #f0f2f5; padding-top: 10px">
				<div class="grid grid-cols-3 gap-2">
					<div class="col-span-2">
						<label for="pp-ref" class="mb-1 flex items-center justify-between text-[10px] font-medium tracking-wide text-gray-600 uppercase">
							<span>Design ref <span class="text-red-500">*</span></span>
							<span v-if="refReadonly" class="text-[9px] text-gray-400">Locked</span>
						</label>
						<input
							id="pp-ref"
							v-model="meta.ref"
							type="text"
							placeholder="e.g. W-01"
							:readonly="refReadonly"
							class="w-full rounded-md border px-2.5 py-1.5 font-mono text-xs font-bold transition focus:outline-none focus:ring-1"
							:class="
								refError
									? 'border-red-400 bg-red-50/50 text-red-900 focus:border-red-500 focus:ring-red-500'
									: 'border-gray-300 bg-white text-gray-900 hover:border-gray-400 focus:border-blue-500 focus:ring-blue-500'
							"
						/>
						<p v-if="refError" class="mt-1 text-[10px] font-medium text-red-600">{{ refError }}</p>
					</div>
					<div>
						<label for="pp-qty" class="mb-1 block text-[10px] font-medium tracking-wide text-gray-600 uppercase">
							Quantity
						</label>
						<input
							id="pp-qty"
							v-model.number="meta.qty"
							type="number"
							min="1"
							class="w-full rounded-md border border-gray-300 bg-white px-2.5 py-1.5 font-mono text-xs font-semibold text-gray-900 transition hover:border-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
						/>
					</div>
				</div>

				<!-- Width and Height Inputs -->
				<div class="grid grid-cols-2 gap-2">
					<div>
						<label for="pp-width" class="mb-1 block text-[10px] font-medium tracking-wide text-gray-600 uppercase">
							Width (mm)
						</label>
						<input
							id="pp-width"
							type="number"
							class="w-full rounded-md border border-gray-300 bg-white px-2.5 py-1.5 font-mono text-xs font-semibold text-gray-900 transition hover:border-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
							:value="store.design.width"
							@change="resize(num($event), store.design.height)"
						/>
					</div>
					<div>
						<label for="pp-height" class="mb-1 block text-[10px] font-medium tracking-wide text-gray-600 uppercase">
							Height (mm)
						</label>
						<input
							id="pp-height"
							type="number"
							class="w-full rounded-md border border-gray-300 bg-white px-2.5 py-1.5 font-mono text-xs font-semibold text-gray-900 transition hover:border-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
							:value="store.design.height"
							@change="resize(store.design.width, num($event))"
						/>
					</div>
				</div>

				<!-- Location (optional) -->
				<div>
					<label for="pp-location" class="mb-1 block text-[10px] font-medium tracking-wide text-gray-500 uppercase">
						Location
					</label>
					<input
						id="pp-location"
						v-model="meta.location"
						type="text"
						placeholder="e.g. Master Bedroom, Floor 1"
						class="w-full rounded-md border border-gray-200 bg-gray-50/50 px-2.5 py-1 text-xs text-gray-800 transition hover:border-gray-300 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
					/>
				</div>
			</div>
		</div>

		<!-- ─── 2. SERIES & PROFILES CARD (Global) ───────────── -->
		<div style="background: #ffffff; border: 1px solid #e1e4e8; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 12px">
			<div style="display: flex; align-items: center; justify-content: space-between">
				<span style="font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #5b6472">SERIES &amp; PROFILES</span>
				<span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #1b5fb8; background: #e8f0fc; border-radius: 4px; padding: 2px 6px">
					{{ store.seriesVersion || 'No series' }}
				</span>
			</div>

			<div style="display: grid; grid-template-columns: 72px minmax(0, 1fr); align-items: center; column-gap: 10px; row-gap: 10px">
				<!-- Series -->
				<span style="font-size: 13px; color: #5b6472">Series</span>
				<div>
					<Select
						v-if="seriesVersionOptions.length"
						:options="seriesVersionOptions"
						:model-value="store.seriesVersion"
						@update:model-value="store.setSeriesVersion(String($event ?? ''))"
					/>
					<span v-else style="font-size: 13px; color: #14171c">{{ store.seriesVersion || 'None' }}</span>
				</div>

				<!-- Frame Profile -->
				<span style="font-size: 13px; color: #5b6472">Frame</span>
				<button
					type="button"
					style="height: 32px; padding: 0 10px; border: 1px solid #d7dbe0; border-radius: 6px; background: #ffffff; font-size: 13px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; color: #14171c"
					@click="openProfilePicker('frame', 'frame')"
				>
					<span class="truncate">
						{{ frameProfileValue && frameProfileValue !== NONE ? frameProfileValue : 'Series default' }}
						<span style="color: #5b6472">· default</span>
					</span>
					<span
						style="width: 12px; height: 12px; display: inline-block; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%235b6472' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E&quot;)"
						aria-hidden="true"
					/>
				</button>
				<Select
					style="display: none"
					label="Frame profile"
					:options="frameProfileOptions"
					:model-value="frameProfileValue"
					@update:model-value="onSetFrameProfile(optStr($event))"
				/>

				<!-- Mullion Profile -->
				<span style="font-size: 13px; color: #5b6472">Mullion</span>
				<button
					type="button"
					style="height: 32px; padding: 0 10px; border: 1px solid #d7dbe0; border-radius: 6px; background: #ffffff; font-size: 13px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; color: #14171c"
					@click="openProfilePicker('mullion', selectedBar?.id || 'mullion')"
				>
					<span class="truncate">
						{{ barProfileValue && barProfileValue !== NONE ? barProfileValue : 'Series default' }}
						<span style="color: #5b6472">· default</span>
					</span>
					<span
						style="width: 12px; height: 12px; display: inline-block; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%235b6472' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E&quot;)"
						aria-hidden="true"
					/>
				</button>
				<Select
					style="display: none"
					label="Mullion profile"
					:options="barProfileOptions"
					:model-value="barProfileValue"
					@update:model-value="onSetBarProfile(optStr($event))"
				/>

				<!-- Bead Profile -->
				<span style="font-size: 13px; color: #5b6472">Bead</span>
				<button
					type="button"
					style="height: 32px; padding: 0 10px; border: 1px solid #d7dbe0; border-radius: 6px; background: #ffffff; font-size: 13px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; color: #14171c"
					@click="openProfilePicker('bead', 'bead')"
				>
					<span class="truncate">
						{{ beadProfileValue && beadProfileValue !== NONE ? beadProfileValue : 'Series default' }}
						<span style="color: #5b6472">· 5 mm</span>
					</span>
					<span
						style="width: 12px; height: 12px; display: inline-block; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%235b6472' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E&quot;)"
						aria-hidden="true"
					/>
				</button>
				<Select
					style="display: none"
					label="Bead profile"
					:options="beadProfileOptions"
					:model-value="beadProfileValue"
					@update:model-value="onSetBeadProfile(optStr($event))"
				/>

				<!-- Finish -->
				<span style="font-size: 13px; color: #5b6472">Finish</span>
				<div style="display: flex; flex-direction: column; gap: 6px">
					<Select
						label="Finish"
						:options="finishOptions(finishes)"
						:model-value="store.finish"
						@update:model-value="store.setFinish(String($event ?? ''))"
					/>
					<div v-if="finishes?.length" style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px">
						<div
							class="flex items-center gap-1.5 rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-xs"
						>
							<span
								class="inline-block size-3 shrink-0 rounded-xs border border-gray-300"
								:style="{ backgroundColor: currentFinishObj?.color || '#8A8F98' }"
							/>
							<span class="truncate font-medium text-gray-800">
								In · {{ currentFinishObj?.finish_name || store.finish || 'Grey' }}
							</span>
						</div>
						<button
							type="button"
							class="flex items-center gap-1.5 rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-left text-xs transition hover:bg-gray-100"
							title="Click to cycle outside colour"
							@click="
								() => {
									const list = finishes || []
									if (!list.length) return
									const idx = list.findIndex((f) => f.name === outsideFinishCode)
									const next = list[(idx + 1) % list.length]
									if (next) setOutsideFinish(next.name)
								}
							"
						>
							<span
								class="inline-block size-3 shrink-0 rounded-xs border border-gray-300"
								:style="{ backgroundColor: outsideFinishObj?.color || '#8A8F98' }"
							/>
							<span class="truncate font-medium text-gray-800">
								Out · {{ outsideFinishObj?.finish_name || outsideFinishCode || 'Grey' }}
							</span>
						</button>
					</div>
				</div>
			</div>
		</div>

		<!-- ─── 3. SELECTION CARD (Contextual, 2px blue border) ─── -->
		<!-- CASE A: Bead Selected -->
		<div
			v-if="isBeadSelected"
			data-testid="selected-bead-card"
			style="background: #ffffff; border: 2px solid #1d6fdc; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 14px"
		>
			<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
				<div style="display: flex; align-items: center; gap: 8px">
					<span style="width: 10px; height: 10px; border-radius: 50%; background: #1d6fdc; display: inline-block"></span>
					<span style="font-size: 15px; font-weight: 600">Bead</span>
				</div>
			</div>

			<div style="display: grid; grid-template-columns: 72px minmax(0, 1fr); align-items: center; column-gap: 10px; row-gap: 12px">
				<span style="font-size: 13px; color: #5b6472">Profile</span>
				<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
					<button
						type="button"
						style="height: 32px; padding: 0 10px; border: 1px solid #d7dbe0; border-radius: 6px; background: #ffffff; font-size: 13px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; flex: 1; color: #14171c"
						@click="openProfilePicker('bead', 'bead')"
					>
						<span>{{ beadProfileValue }}</span>
						<span
						style="width: 12px; height: 12px; display: inline-block; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%235b6472' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E&quot;)"
						aria-hidden="true"
					/>
					</button>
					<button
						type="button"
						style="font-size: 12px; font-weight: 500; color: #1b5fb8; background: none; border: none; cursor: pointer; text-decoration: none"
						@click="openProfilePicker('bead', 'bead')"
					>
						Catalog
					</button>
				</div>

				<span style="font-size: 13px; color: #5b6472">Corners</span>
				<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); background: #eef0f3; border-radius: 7px; padding: 3px; gap: 3px">
					<button
						type="button"
						:style="beadJointValue === 'm' ? activeSegmentStyle : inactiveSegmentStyle"
						@click="onSetBeadJoint('m')"
					>
						Mitre 45°
					</button>
					<button
						type="button"
						:style="beadJointValue === 'b' ? activeSegmentStyle : inactiveSegmentStyle"
						@click="onSetBeadJoint('b')"
					>
						Square
					</button>
				</div>

				<span style="font-size: 13px; color: #5b6472">Sync</span>
				<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
					<span style="font-size: 13px">Mirror to opposite side</span>
					<button
						type="button"
						:style="store.design.mirrorSync !== false ? syncOnStyle : syncOffStyle"
						@click="store.setMirrorSync(store.design.mirrorSync === false ? true : false)"
					>
						{{ store.design.mirrorSync !== false ? 'On' : 'Off' }}
					</button>
				</div>
			</div>

			<div style="height: 1px; background: #e1e4e8"></div>

			<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px">
				<button
					type="button"
					style="height: 36px; border: 1px solid #d7dbe0; border-radius: 7px; background: #ffffff; font-size: 13px; font-weight: 500; cursor: pointer; color: #14171c"
					@click="onSetBeadAsDefault"
				>
					Set as default
				</button>
				<button
					type="button"
					style="height: 36px; border: 1px solid #d7dbe0; border-radius: 7px; background: #ffffff; font-size: 13px; font-weight: 500; cursor: pointer; color: #14171c"
					@click="onResetBead"
				>
					Reset bead
				</button>
			</div>
			<span style="font-size: 12px; color: #5b6472; line-height: 1.45">
				Drag the bead on the section or use the floating toolbar to move, rotate or flip it.
			</span>
		</div>

		<!-- CASE B: Panel Selected (Glass or Panel Leaf) -->
		<div
			v-else-if="leaf"
			data-testid="selected-panel-card"
			:data-has-glass="isGlassSelected ? '' : undefined"
			style="background: #ffffff; border: 2px solid #1d6fdc; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 14px"
		>
			<!-- If direct glass click, also render hidden selected-glass-card hook for tests -->
			<div v-if="isGlassSelected" data-testid="selected-glass-card" style="display: none">
				Selected glass {{ selectedLabel }}
			</div>

			<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
				<div style="display: flex; align-items: center; gap: 8px">
					<span style="width: 10px; height: 10px; border-radius: 2px; background: #1d6fdc; display: inline-block"></span>
					<span style="font-size: 15px; font-weight: 600">
						{{ isGlassSelected ? `Selected glass ${selectedLabel}` : `Selected panel ${selectedLabel}` }}
					</span>
				</div>
				<span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #1b5fb8; background: #e8f0fc; border-radius: 4px; padding: 3px 7px">
					{{ isGlassSelected ? 'glass' : leaf.type }}
				</span>
			</div>

			<div style="display: flex; flex-direction: column; gap: 10px">
				<!-- Sash Options (when type is sash and not direct glass click) -->
				<template v-if="leaf.type === 'sash' && !isGlassSelected">
					<div class="space-y-1">
						<div class="flex items-center justify-between">
							<label class="text-xs font-medium text-gray-700">Sash profile</label>
							<button
								type="button"
								class="text-[11px] font-medium text-blue-600 hover:text-blue-800 hover:underline"
								@click="openProfilePicker('sash', effectiveCellPath)"
							>
								Catalog
							</button>
						</div>
						<button
							type="button"
							class="flex w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-left text-xs font-medium text-gray-800 shadow-2xs transition hover:border-blue-500 hover:ring-1 hover:ring-blue-500"
							@click="openProfilePicker('sash', effectiveCellPath)"
						>
							<span class="truncate">
								{{ getProfileDisplayLabel('sash', sashProfileValue) }}
							</span>
							<span class="ml-2 text-xs text-gray-400">▾</span>
						</button>
						<Select
							style="display: none"
							label="Sash profile"
							:options="sashProfileOptions"
							:model-value="sashProfileValue"
							@update:model-value="onSetSashProfile(optStr($event))"
						/>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<Select
							label="Opening"
							:options="OPENINGS"
							:model-value="leaf.opening ?? NONE"
							@update:model-value="patchLeaf({ opening: optStr($event) })"
						/>
						<Select
							label="Hinge"
							:options="HINGES"
							:model-value="leaf.hinge ?? NONE"
							@update:model-value="patchLeaf({ hinge: optStr($event) })"
						/>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<Select
							label="Hinge type"
							:options="HINGE_TYPES"
							:model-value="leaf.hinge_type ?? NONE"
							@update:model-value="patchLeaf({ hinge_type: optStr<'friction' | 'butt'>($event) })"
						/>
						<Select
							label="Handle"
							:options="HANDLES"
							:model-value="leaf.handle ?? NONE"
							@update:model-value="patchLeaf({ handle: optStr<'multipoint' | 'single'>($event) })"
						/>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<Select
							label="Opening limiter"
							:options="limiterOptions"
							:model-value="flagValue(leaf.limiter)"
							@update:model-value="patchLeaf({ limiter: flagPatch($event) })"
						/>
						<Select
							label="Fly mesh"
							:options="meshOptions"
							:model-value="flagValue(leaf.mesh)"
							@update:model-value="patchLeaf({ mesh: flagPatch($event) })"
						/>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<FormControl
							type="number"
							label="GHH (mm)"
							:model-value="leaf.ghh ?? ''"
							@change="patchLeaf({ ghh: optNum($event) })"
						/>
						<Select
							label="Lock"
							:options="LOCKS"
							:model-value="leaf.lock ?? 'multipoint'"
							@update:model-value="patchLeaf({ lock: String($event ?? 'multipoint') })"
						/>
					</div>
				</template>

				<FormControl
					v-if="leaf.type === 'louver' && !isGlassSelected"
					type="number"
					label="Blades"
					min="1"
					:model-value="leaf.blades"
					@change="patchLeaf({ blades: num($event) })"
				/>

				<!-- Glass Select Row -->
				<div style="display: grid; grid-template-columns: 72px minmax(0, 1fr); align-items: center; column-gap: 10px; row-gap: 12px">
					<span style="font-size: 13px; color: #5b6472">Glass</span>
					<Select
						label="Glass"
						:options="glassOptions"
						:model-value="leaf.glass"
						@update:model-value="patchLeaf({ glass: String($event ?? '') })"
					/>

					<!-- Beading Segmented On/Off -->
					<template v-if="!isGlassSelected">
						<span style="font-size: 13px; color: #5b6472">Beading</span>
						<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); background: #eef0f3; border-radius: 7px; padding: 3px; gap: 3px">
							<button
								type="button"
								:style="leaf.bead !== false ? activeSegmentStyle : inactiveSegmentStyle"
								@click="patchLeaf({ bead: true })"
							>
								On
							</button>
							<button
								type="button"
								:style="leaf.bead === false ? activeSegmentStyle : inactiveSegmentStyle"
								@click="patchLeaf({ bead: false })"
							>
								Off
							</button>
						</div>
					</template>
				</div>
			</div>

			<div style="height: 1px; background: #e1e4e8"></div>

			<!-- Three Read-only Sizes (Plain Mono Text) -->
			<div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px">
				<div style="display: flex; flex-direction: column; gap: 3px">
					<span style="font-size: 11px; color: #5b6472">Glass width</span>
					<span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 500">{{ glassDims.w }}</span>
				</div>
				<div style="display: flex; flex-direction: column; gap: 3px">
					<span style="font-size: 11px; color: #5b6472">Glass height</span>
					<span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 500">{{ glassDims.h }}</span>
				</div>
				<div style="display: flex; flex-direction: column; gap: 3px">
					<span style="font-size: 11px; color: #5b6472">Glass cut </span>
					<span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 500">{{ glassCut }}</span>
				</div>
			</div>

			<div v-if="leaf.type === 'sash' && !isGlassSelected" style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; border-top: 1px solid #e1e4e8; padding-top: 8px">
				<div style="display: flex; flex-direction: column; gap: 3px">
					<span style="font-size: 11px; color: #5b6472">Sash width</span>
					<span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 500">{{ sashDims.w }}</span>
				</div>
				<div style="display: flex; flex-direction: column; gap: 3px">
					<span style="font-size: 11px; color: #5b6472">Sash height</span>
					<span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 500">{{ sashDims.h }}</span>
				</div>
				<div style="display: flex; flex-direction: column; gap: 3px">
					<span style="font-size: 11px; color: #5b6472">Sash size</span>
					<span style="font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 500">{{ sashSize }}</span>
				</div>
			</div>

			<div v-if="leaf.fan" class="flex items-center justify-between text-blue-700 text-xs">
				<span>Exhaust fan cut</span>
				<span class="font-semibold">180 mm cutout</span>
			</div>

			<div v-if="isGlassSelected && leaf.type === 'sash'" class="flex justify-end border-t border-gray-100 pt-2">
				<button
					type="button"
					class="text-xs font-medium text-blue-600 hover:underline"
					@click="store.select(effectiveCellPath)"
				>
					Inspect parent sash ({{ selectedLabel }})
				</button>
			</div>
		</div>

		<!-- CASE C: Outer Frame Selected -->
		<div
			v-else-if="isFrameSelected"
			data-testid="selected-frame-card"
			style="background: #ffffff; border: 2px solid #1d6fdc; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 14px"
		>
			<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
				<div style="display: flex; align-items: center; gap: 8px">
					<span style="width: 10px; height: 10px; border-radius: 2px; background: #1d6fdc; display: inline-block"></span>
					<span style="font-size: 15px; font-weight: 600">Selected outer frame F1</span>
				</div>
				<span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #1b5fb8; background: #e8f0fc; border-radius: 4px; padding: 3px 7px">
					frame
				</span>
			</div>
			<div class="flex flex-col gap-2.5">
				<div class="space-y-1">
					<div class="flex items-center justify-between">
						<label class="text-xs font-medium text-gray-700">Frame profile</label>
						<button
							type="button"
							class="text-[11px] font-medium text-blue-600 hover:text-blue-800 hover:underline"
							@click="openProfilePicker('frame', 'frame')"
						>
							Catalog
						</button>
					</div>
					<button
						type="button"
						class="flex w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-left text-xs font-medium text-gray-800 shadow-2xs transition hover:border-blue-500 hover:ring-1 hover:ring-blue-500"
						@click="openProfilePicker('frame', 'frame')"
					>
						<span class="truncate">
							{{ getProfileDisplayLabel('frame', frameProfileValue) }}
						</span>
						<span class="ml-2 text-xs text-gray-400">▾</span>
					</button>
					<Select
						style="display: none"
						label="Frame profile"
						:options="frameProfileOptions"
						:model-value="frameProfileValue"
						@update:model-value="onSetFrameProfile(optStr($event))"
					/>
				</div>
				<!-- Fabrication Specifications -->
				<div class="space-y-2 border-t border-gray-100 pt-2.5 text-xs">
					<div class="flex items-center justify-between text-gray-600">
						<span>Face width</span>
						<span class="font-mono font-medium text-gray-900">{{ effectiveFrameFace }} mm</span>
					</div>
					<div class="flex items-center justify-between text-gray-600">
						<span>Corner cut angles</span>
						<span class="font-mono font-medium text-gray-900">
							{{
								Array.isArray(frameMember?.angles)
									? `${frameMember.angles.join('° / ')}°`
									: '45° / 135°'
							}}
						</span>
					</div>
					<div class="rounded-lg border border-gray-100 bg-gray-50/80 p-2.5">
						<span class="block text-[10px] font-bold tracking-wider text-gray-500 uppercase">
							Cutting Schedule
						</span>
						<div class="mt-1.5 flex items-center justify-between text-gray-700">
							<span>Head &amp; Sill (Top / Bottom)</span>
							<span class="font-mono font-bold text-gray-900">2 × {{ store.design.width }} mm</span>
						</div>
						<div class="mt-1 flex items-center justify-between text-gray-700">
							<span>Jambs (Left / Right)</span>
							<span class="font-mono font-bold text-gray-900">2 × {{ store.design.height }} mm</span>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- CASE D: Selected Bar (Mullion / Transom) -->
		<div
			v-else-if="selectedBar"
			data-testid="selected-bar-card"
			style="background: #ffffff; border: 2px solid #1d6fdc; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 14px"
		>
			<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
				<div style="display: flex; align-items: center; gap: 8px">
					<span style="width: 10px; height: 10px; border-radius: 2px; background: #1d6fdc; display: inline-block"></span>
					<span style="font-size: 15px; font-weight: 600">
						Selected {{ selectedBar.dir === 'v' ? 'mullion' : 'transom' }} {{ selectedBar.id }}
					</span>
				</div>
				<span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #1b5fb8; background: #e8f0fc; border-radius: 4px; padding: 3px 7px">
					{{ selectedBar.dir === 'v' ? 'mullion' : 'transom' }}
				</span>
			</div>
			<div class="flex flex-col gap-2.5">
				<div class="space-y-1">
					<div class="flex items-center justify-between">
						<label class="text-xs font-medium text-gray-700">
							{{ selectedBar.dir === 'v' ? 'Mullion' : 'Transom' }} profile
						</label>
						<button
							type="button"
							class="text-[11px] font-medium text-blue-600 hover:text-blue-800 hover:underline"
							@click="openProfilePicker(selectedBar.dir === 'v' ? 'mullion' : 'transom', selectedBar.id)"
						>
							Catalog
						</button>
					</div>
					<button
						type="button"
						class="flex w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-left text-xs font-medium text-gray-800 shadow-2xs transition hover:border-blue-500 hover:ring-1 hover:ring-blue-500"
						@click="openProfilePicker(selectedBar.dir === 'v' ? 'mullion' : 'transom', selectedBar.id)"
					>
						<span class="truncate">
							{{ getProfileDisplayLabel(selectedBar.dir === 'v' ? 'mullion' : 'transom', barProfileValue) }}
						</span>
						<span class="ml-2 text-xs text-gray-400">▾</span>
					</button>
					<Select
						style="display: none"
						:label="`${selectedBar.dir === 'v' ? 'Mullion' : 'Transom'} profile`"
						:options="barProfileOptions"
						:model-value="barProfileValue"
						@update:model-value="onSetBarProfile(optStr($event))"
					/>
				</div>

				<!-- Bar Position -->
				<div v-if="split" class="space-y-1.5">
					<FormControl
						type="number"
						:label="`${selectedBar.id} position (mm)`"
						:model-value="split.at[selectedBar.index]"
						@change="moveBar(selectedBar.index, $event)"
					/>
					<div>
						<div class="flex items-center justify-between font-mono text-[11px] text-gray-500">
							<span>Bar position</span>
							<span>{{ selectedBarPct }}%</span>
						</div>
						<input
							type="range"
							min="10"
							max="90"
							:value="selectedBarPct"
							class="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-gray-200 accent-blue-600"
							@input="onBarSliderInput"
						/>
					</div>
				</div>

				<div class="space-y-1.5 border-t border-gray-100 pt-2 text-xs">
					<div class="flex items-center justify-between text-gray-600">
						<span>Cut length</span>
						<span class="font-mono font-medium text-gray-900">{{ barCutLength }}</span>
					</div>
					<div class="flex items-center justify-between text-gray-600">
						<span>Span</span>
						<span class="font-mono font-medium text-gray-900">{{ selectedBar.length }} mm</span>
					</div>
					<div class="flex items-center justify-between text-gray-600">
						<span>Face width</span>
						<span class="font-mono font-medium text-gray-900">{{ effectiveBarFace }} mm</span>
					</div>
					<div class="flex items-center justify-between text-gray-600">
						<span>Position</span>
						<span class="font-mono font-medium text-gray-900">
							{{ selectedBar.dir === 'v' ? selectedBar.x : selectedBar.y }} mm
						</span>
					</div>
					<div v-if="barMember?.profile" class="flex items-center justify-between text-gray-600">
						<span>Profile</span>
						<span class="font-mono font-medium text-gray-900">{{ barMember.profile }}</span>
					</div>
					<div v-if="barMember?.angles" class="flex items-center justify-between text-gray-600">
						<span>Cut angles</span>
						<span class="font-mono font-medium text-gray-900">
							{{
								Array.isArray(barMember.angles)
									? `${barMember.angles.join('° / ')}°`
									: barMember.angles
							}}
						</span>
					</div>
				</div>
				<div class="flex justify-end border-t border-gray-100 pt-2">
					<button
						type="button"
						class="text-xs font-medium text-red-600 hover:underline"
						@click.prevent="onRemoveSplit"
					>
						Remove split
					</button>
				</div>
			</div>
		</div>

		<!-- CASE E: Split Controls (Bar position only, no single bar selected) -->
		<div
			v-else-if="split"
			style="background: #ffffff; border: 1px solid #e1e4e8; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 10px"
		>
			<div class="flex items-center justify-between text-sm font-semibold text-gray-900">
				<span>Split ({{ split.dir === 'v' ? 'vertical' : 'horizontal' }})</span>
				<button
					type="button"
					class="text-xs font-medium text-red-600 hover:underline"
					@click.prevent="onRemoveSplit"
				>
					Remove split
				</button>
			</div>
			<div class="flex flex-col gap-2.5">
				<FormControl
					v-for="(a, i) in split.at"
					:key="i"
					type="number"
					:label="`Bar ${i + 1} position (mm)`"
					:model-value="a"
					@change="moveBar(i, $event)"
				/>
			</div>
		</div>

		<!-- CASE F: Nothing Selected -->
		<div
			v-else
			data-testid="nothing-selected-card"
			style="background: #ffffff; border: 1px dashed #d7dbe0; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 6px"
		>
			<span style="font-size: 13px; font-weight: 600; color: #5b6472">Nothing selected</span>
			<span style="font-size: 12px; color: #5b6472; line-height: 1.45">
				Click a panel on the canvas or a profile in the section view to inspect and edit its properties.
			</span>
		</div>

		<!-- ─── 4. ENGINEERING ISSUES ────────────────────────── -->
		<div
			v-for="(issue, idx) in activeIssues"
			:key="idx"
			class="rounded-xl border p-3 text-xs"
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
			class="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
			role="alert"
		>
			{{ profileAssignmentError }}. The previous profile is still selected.
		</p>

		<ProfilePickerModal
			v-model="pickerOpen"
			:title="`Select ${pickerRole} profile`"
			:target-role="pickerRole"
			:current-profile="
				pickerTargetKey === 'frame'
					? frameProfileValue
					: pickerTargetKey === 'bead'
						? beadProfileValue
						: pickerTargetKey === effectiveCellPath
							? sashProfileValue
							: barProfileValue
			"
			:series="store.seriesVersion"
			:profiles="pickerProfiles"
			@select="onPickerSelect"
		/>
	</aside>
</template>
