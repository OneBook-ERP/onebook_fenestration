<script setup lang="ts">
import { Alert, Badge, Button, Tooltip, toast, useList } from 'frappe-ui'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { copyDesign, getDesign, getFenestrationDefaults, saveDesign, type CutAxis, type SavedDesign } from '@/api'
import PropertiesPanel, { type Meta } from '@/components/PropertiesPanel.vue'
import ResultsBar from '@/components/ResultsBar.vue'
import Window3DView from '@/components/Window3DView.vue'
import WindowCanvas from '@/components/WindowCanvas.vue'
import SectionView from '@/components/SectionView.vue'
import { generateElevationSvg } from '@/design/elevationSvg'
import { layoutGeom } from '@/design/geometry'
import { TEMPLATES } from '@/design/templates'
import { typology } from '@/design/typology'
import { getNode, moveSplit, removeSplit, setLeaf, splitCell } from '@/design/tree'
import type { LeafNode, SectionPieceTransform, SplitDir } from '@/design/types'
import { useDesignerStore } from '@/stores/designer'

interface FinishRow {
	name: string
	finish_name: string
	color: string
}

interface SeriesVersionRow {
	name: string
	series: string
	version_note?: string
	docstatus?: number
}

const store = useDesignerStore()
const route = useRoute()
const router = useRouter()
const project = computed(() => String(route.params.project))
const savedName = computed(() => (route.params.name ? String(route.params.name) : null))

const meta = ref<Meta>({ ref: '', qty: 1, location: '' })
const refError = ref('')
const VIEWS = [
	{ label: 'Inside', value: 'inside' },
	{ label: 'Outside', value: 'outside' },
	{ label: '3D', value: '3d' },
] as const
const view = ref<'inside' | 'outside' | '3d'>('inside')
const saving = ref(false)
const loadError = ref('')
const loading = ref(false)
let loadedName: string | null = null
const lockedBy = ref<{ doctype: string; name: string } | null>(null)
const copying = ref(false)
const blocked = computed(() => loading.value || !!loadError.value || saving.value || !!lockedBy.value)
const lockMessage = computed(() =>
	lockedBy.value
		? `${meta.value.ref} is on ${lockedBy.value.doctype} ${lockedBy.value.name}. Copy the design to change it.`
		: '',
)
const toolHint = 'Select a panel on the drawing to use these tools'
const designType = computed(() => typology(store.design.root))
const canvas = ref<InstanceType<typeof WindowCanvas> | null>(null)

const sectionOn = ref(false)
const cutAxis = computed<CutAxis>({
	get: () => store.design.activeCutAxis ?? 'h',
	set: (val: CutAxis) => store.setActiveCutAxis(val),
})
/** The cut the user picked (cell centre, mm), sent to the engine; null lets the engine cut the first cell. */
const cutAt = ref<Record<CutAxis, number | null>>({ h: null, v: null })
/** Where the engine actually cut. Only places the markers; never sent back, so it cannot trigger a fetch. */
const cutSnapped = ref<Record<CutAxis, number | null>>({ h: null, v: null })
/** Marker positions: engine cut, else the picked cut, else the engine's default (centre of the first cell). */
const cutPos = computed(() => {
	const first = layoutGeom(store.design).cells[0]
	const pos = (a: CutAxis, fallback: number) => cutSnapped.value[a] ?? cutAt.value[a] ?? fallback
	return { axis: cutAxis.value, h: pos('h', first.y + first.h / 2), v: pos('v', first.x + first.w / 2) }
})
function pickCut(axis: CutAxis, at: number) {
	cutAt.value = { ...cutAt.value, [axis]: at }
	cutSnapped.value = { ...cutSnapped.value, [axis]: null }
}
function onSnapped(at: number) {
	cutSnapped.value = { ...cutSnapped.value, [cutAxis.value]: at }
}

const finishList = useList<FinishRow>({
	doctype: 'Profile Finish',
	fields: ['name', 'finish_name', 'color'],
	orderBy: 'name asc',
	limit: 100,
})
const finishes = computed(() => finishList.data ?? [])
const finishName = computed(() => finishes.value.find((f) => f.name === store.finish)?.finish_name || store.finish)
const finishColor = computed(() => finishes.value.find((f) => f.name === store.finish)?.color || undefined)
const outsideFinishColor = computed(
	() => finishes.value.find((f) => f.name === (store.design.finishOutside || store.finish))?.color || finishColor.value,
)

const versionList = useList<SeriesVersionRow>({
	doctype: 'Series Version',
	fields: ['name', 'series', 'version_note', 'docstatus'],
	filters: { docstatus: 1 },
	orderBy: 'modified desc',
	limit: 100,
})
const seriesVersions = computed(() => versionList.data ?? [])
const profileSeriesOptions = computed(() => {
	const set = new Set<string>()
	for (const sv of seriesVersions.value) {
		if (sv.series) set.add(sv.series)
	}
	set.add('CS400')
	set.add('CS4800')
	return Array.from(set).map((s) => ({ label: s, value: s }))
})

const activeProfileSeries = computed(() => {
	const ver = store.seriesVersion
	const match = seriesVersions.value.find((sv) => sv.name === ver)
	if (match?.series) return match.series
	if (ver && ver.toUpperCase().includes('CS4800')) return 'CS4800'
	return 'CS400'
})

function onSelectProfileSeries(seriesName: string) {
	const target = seriesVersions.value.find((sv) => sv.series === seriesName)
	const nextVer = target?.name || (seriesName === 'CS4800' ? 'CS4800-v1' : 'CS400-v1')
	store.setSeriesVersion(nextVer)
}

const seriesVersionOptions = computed(() => {
	const list = seriesVersions.value
	const opts = list.map((sv) => ({
		label: `${sv.series} · ${sv.name}`,
		value: sv.name,
	}))
	if (store.seriesVersion && !opts.some((o) => o.value === store.seriesVersion)) {
		opts.unshift({ label: store.seriesVersion, value: store.seriesVersion })
	}
	return opts
})

const issuePaths = computed(() => (store.result?.issues ?? []).map((i) => i.path))
const activeCellPath = computed(() => store.selectedPath.replace(/^GLASS:/, ''))
const selectedLeaf = computed(() => {
	try {
		if (!activeCellPath.value || activeCellPath.value === 'FRAME') return null
		const n = getNode(store.design, activeCellPath.value)
		return n.type === 'split' ? null : n
	} catch {
		return null
	}
})
const canRemoveSplit = computed(() => {
	const p = activeCellPath.value
	if (!p || p === 'FRAME') return false
	if (layoutGeom(store.design).bars.some((b) => b.id === p)) return true
	try {
		const n = getNode(store.design, p)
		return n.type === 'split' || p.includes('.')
	} catch {
		return false
	}
})

const mainEl = ref<HTMLElement | null>(null)
const splitRatio = ref(50)
const resizingSplit = ref(false)
let splitDrag: { startX: number; origRatio: number } | null = null

function onSplitResizerPointerDown(e: PointerEvent) {
	if (e.button !== 0 && e.button !== undefined) return
	e.preventDefault()
	splitDrag = { startX: e.clientX, origRatio: splitRatio.value }
	resizingSplit.value = true
	window.addEventListener('pointermove', onSplitResizerPointerMove)
	window.addEventListener('pointerup', endSplitResize)
	window.addEventListener('pointercancel', endSplitResize)
}

function onSplitResizerPointerMove(e: PointerEvent) {
	if (!splitDrag) return
	const r = mainEl.value?.getBoundingClientRect()
	const totalW = r && r.width > 0 ? r.width : 1000
	const deltaPct = ((e.clientX - splitDrag.startX) / totalW) * 100
	splitRatio.value = Math.round(Math.min(80, Math.max(20, splitDrag.origRatio + deltaPct)) * 10) / 10
}

function endSplitResize() {
	if (!splitDrag) return
	splitDrag = null
	resizingSplit.value = false
	window.removeEventListener('pointermove', onSplitResizerPointerMove)
	window.removeEventListener('pointerup', endSplitResize)
	window.removeEventListener('pointercancel', endSplitResize)
}

const sidebarTemplates = computed(() => {
	const current = activeProfileSeries.value
	const list = TEMPLATES.filter((t) => t.series === current)
	if (list.length) return list
	return TEMPLATES.filter((t) => !t.series && t.id !== 'blank')
})

function parseJson<T>(v: T | string): T {
	return typeof v === 'string' ? JSON.parse(v) : v
}

async function load(name: string | null) {
	loadError.value = ''
	if (!name) {
		loadedName = null
		lockedBy.value = null
		meta.value = { ref: '', qty: 1, location: '' }
		let defaults = { default_finish: '', default_price_structure: '' }
		try {
			defaults = { ...defaults, ...(await getFenestrationDefaults()) }
		} catch {
			// Prices fall back to the server-side defaults when none are sent.
		}
		if (savedName.value) return
		const initialSv = String(route.query.series_version || seriesVersions.value[0]?.name || '')
		store.reset(
			(TEMPLATES.find((t) => t.id === route.query.template) ?? TEMPLATES[TEMPLATES.length - 1]).build(1200, 1200),
			initialSv,
			defaults.default_finish ?? '',
			defaults.default_price_structure ?? '',
		)
		store.select(layoutGeom(store.design).cells[0]?.path ?? 'F1')
		return
	}
	if (name === loadedName) return
	loading.value = true
	try {
		const doc: SavedDesign = await getDesign(name)
		if (name !== savedName.value) return
		meta.value = { ref: doc.design_ref, qty: doc.qty, location: doc.location ?? '' }
		store.reset(parseJson(doc.design_json), doc.series_version, doc.finish ?? '', doc.price_structure ?? '')
		store.select(layoutGeom(store.design).cells[0]?.path ?? 'F1')
		lockedBy.value = doc.locked_by ?? null
		loadedName = name
	} catch (e) {
		if (name !== savedName.value) return
		loadError.value = e instanceof Error ? e.message : 'Could not load design'
	} finally {
		if (name === savedName.value) loading.value = false
	}
}
watch(savedName, load, { immediate: true })
// Sync so load's meta assignment lands before store.reset clears the flag.
watch(meta, () => store.markDirty(), { deep: true, flush: 'sync' })

function onBeforeUnload(e: BeforeUnloadEvent) {
	if (!store.dirty) return
	e.preventDefault()
	e.returnValue = ''
}
function onKeyDown(e: KeyboardEvent) {
	if (e.key !== 'Delete' && e.key !== 'Backspace') return
	const target = e.target as HTMLElement | null
	if (
		target &&
		(target.tagName === 'INPUT' ||
			target.tagName === 'TEXTAREA' ||
			target.tagName === 'SELECT' ||
			target.isContentEditable)
	) {
		return
	}
	if (!canDelete.value) return
	e.preventDefault()
	deleteSelected()
}
onMounted(() => {
	window.addEventListener('beforeunload', onBeforeUnload)
	window.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
	endSplitResize()
	window.removeEventListener('beforeunload', onBeforeUnload)
	window.removeEventListener('keydown', onKeyDown)
	store.cancelCompute()
})
onBeforeRouteLeave(() => !store.dirty || window.confirm('Discard unsaved changes?'))

function split(dir: SplitDir) {
	const path = activeCellPath.value
	store.apply((d) => splitCell(d, path, dir, 2))
	store.select(`${path}.0`)
}
function convert(kind: 'sash' | 'fixed' | 'louver') {
	const cur = selectedLeaf.value
	if (!cur) return
	const glass = cur.glass
	const leaf: LeafNode =
		kind === 'sash'
			? { type: 'sash', glass, opening: 'out', hinge: 'left', ghh: 732, lock: 'multipoint', fan: cur.fan }
			: kind === 'louver'
				? { type: 'louver', glass, blades: 9, fan: cur.fan }
				: { type: 'fixed', glass, fan: cur.fan }
	store.apply((d) => setLeaf(d, activeCellPath.value, leaf))
	store.select(activeCellPath.value)
}
function toggleExhaustFan() {
	const cur = selectedLeaf.value
	if (!cur) return
	store.apply((d) => setLeaf(d, activeCellPath.value, { ...cur, fan: !cur.fan }))
}
const isBeadOn = computed(() => {
	if (!selectedLeaf.value) return false
	return selectedLeaf.value.bead !== false
})
function toggleBead() {
	const cur = selectedLeaf.value
	if (!cur) return
	const nextBead = cur.bead === false ? true : false
	store.apply((d) => setLeaf(d, activeCellPath.value, { ...cur, bead: nextBead }))
}
function unsplitSelected() {
	const p = activeCellPath.value
	const bar = layoutGeom(store.design).bars.find((b) => b.id === p)
	let target = bar ? bar.splitPath : ''
	if (!target) {
		try {
			target = getNode(store.design, p).type === 'split' ? p : p.split('.').slice(0, -1).join('.')
		} catch {
			return
		}
	}
	if (!target) return
	store.apply((d) => removeSplit(d, target))
	const nextLeaf = layoutGeom(store.design).cells.find((c) => c.path === target || c.path.startsWith(`${target}.`))?.path ?? target
	store.select(nextLeaf)
}

const canDelete = computed(() => {
	const leaf = selectedLeaf.value
	if (!leaf) return canRemoveSplit.value
	return leaf.type === 'sash' || leaf.type === 'louver' || Boolean(leaf.fan)
})

const deleteLabel = computed(() => {
	const leaf = selectedLeaf.value
	if (!leaf && canRemoveSplit.value) return 'Merge split'
	if (leaf?.fan) return 'Delete exhaust cut'
	if (leaf?.type === 'sash') return 'Delete sash'
	if (leaf?.type === 'louver') return 'Delete louver'
	return 'Delete'
})

function deleteSelected() {
	const leaf = selectedLeaf.value
	if (!leaf) {
		if (canRemoveSplit.value) unsplitSelected()
		return
	}
	if (leaf.fan) {
		store.apply((d) => setLeaf(d, activeCellPath.value, { ...leaf, fan: false }))
		return
	}
	if (leaf.type === 'sash') {
		store.apply((d) => setLeaf(d, activeCellPath.value, { type: 'fixed', glass: leaf.glass, bead: leaf.bead !== false }))
		return
	}
	if (leaf.type === 'louver') {
		store.apply((d) => setLeaf(d, activeCellPath.value, { type: 'fixed', glass: leaf.glass, bead: leaf.bead !== false }))
		return
	}
}

const canResetPanel = computed(() => Boolean(selectedLeaf.value))

function resetPanel() {
	const leaf = selectedLeaf.value
	if (!leaf) return
	const defaultGlass = leaf.glass || store.seriesInfo?.defaults?.glass || '6CTG'
	store.apply((d) => setLeaf(d, activeCellPath.value, { type: 'fixed', glass: defaultGlass, bead: true }))
}

const editSelectionChipLabel = computed(() => {
	const leaf = selectedLeaf.value
	if (leaf) {
		const name = activeCellPath.value.toUpperCase()
		if (leaf.type === 'sash') return `Sash ${name} selected`
		if (leaf.type === 'louver') return `Louver ${name} selected`
		return `Panel ${name} selected`
	}
	if (canRemoveSplit.value) {
		return `Split ${activeCellPath.value.toUpperCase()} selected`
	}
	return 'Nothing selected'
})

const deleteActiveStyle = {
	height: '36px',
	padding: '0 12px',
	border: '1px solid #e8a9a2',
	borderRadius: '7px',
	background: '#ffffff',
	fontSize: '13px',
	fontWeight: '600',
	display: 'flex',
	alignItems: 'center',
	justifyContent: 'space-between',
	cursor: 'pointer',
	color: '#b42318',
	boxSizing: 'border-box' as const,
	width: '100%',
}

const deleteDisabledStyle = {
	height: '36px',
	padding: '0 12px',
	border: '1px solid #d7dbe0',
	borderRadius: '7px',
	background: '#ffffff',
	fontSize: '13px',
	fontWeight: '600',
	display: 'flex',
	alignItems: 'center',
	justifyContent: 'space-between',
	cursor: 'not-allowed',
	opacity: '0.45',
	color: '#5b6472',
	boxSizing: 'border-box' as const,
	width: '100%',
}

const editBtnStyle = {
	height: '36px',
	padding: '0 12px',
	border: '1px solid #d7dbe0',
	borderRadius: '7px',
	background: '#ffffff',
	fontSize: '13px',
	display: 'flex',
	alignItems: 'center',
	gap: '10px',
	cursor: 'pointer',
	color: '#14171c',
	boxSizing: 'border-box' as const,
	width: '100%',
}

const editBtnDisabledStyle = {
	height: '36px',
	padding: '0 12px',
	border: '1px solid #d7dbe0',
	borderRadius: '7px',
	background: '#ffffff',
	fontSize: '13px',
	display: 'flex',
	alignItems: 'center',
	gap: '10px',
	cursor: 'not-allowed',
	opacity: '0.45',
	color: '#5b6472',
	boxSizing: 'border-box' as const,
	width: '100%',
}

const buildBtnStyle = {
	height: '36px',
	padding: '0 12px !important',
	border: '1px solid #d7dbe0',
	borderRadius: '7px',
	background: '#ffffff',
	fontSize: '13px',
	fontWeight: '500',
	display: 'flex',
	alignItems: 'center',
	justifyContent: 'flex-start !important',
	gap: '10px !important',
	cursor: 'pointer',
	color: '#14171c',
	boxSizing: 'border-box' as const,
	width: '100%',
}

const buildBtnDisabledStyle = {
	height: '36px',
	padding: '0 12px !important',
	border: '1px solid #d7dbe0',
	borderRadius: '7px',
	background: '#ffffff',
	fontSize: '13px',
	fontWeight: '500',
	display: 'flex',
	alignItems: 'center',
	justifyContent: 'flex-start !important',
	gap: '10px !important',
	cursor: 'not-allowed',
	opacity: '0.45',
	color: '#5b6472',
	boxSizing: 'border-box' as const,
	width: '100%',
}

const buildBtnActiveStyle = {
	height: '36px',
	padding: '0 12px !important',
	border: '1px solid #b8d5fb',
	borderRadius: '7px',
	background: '#eef4ff',
	fontSize: '13px',
	fontWeight: '500',
	display: 'flex',
	alignItems: 'center',
	justifyContent: 'flex-start !important',
	gap: '10px !important',
	cursor: 'pointer',
	color: '#1b5fb8',
	boxSizing: 'border-box' as const,
	width: '100%',
}
function applyTemplate(tplId: string) {
	const tpl = TEMPLATES.find((t) => t.id === tplId)
	if (!tpl) return
	const width = tpl.defaultW ?? store.design.width
	const height = tpl.defaultH ?? store.design.height
	store.apply(() => tpl.build(width, height))
	store.select(layoutGeom(store.design).cells[0]?.path ?? 'F1')
}
function onMoveSplit(p: { splitPath: string; index: number; pos: number }) {
	store.dragTo((d) => moveSplit(d, p.splitPath, p.index, p.pos))
}
function onUpdateSectionMap(sectionMap: Record<string, SectionPieceTransform>) {
	store.apply((d) => ({ ...d, sectionMap }))
}

async function save() {
	refError.value = ''
	if (blocked.value) {
		toast.error('Cannot save while design is loading or locked')
		return
	}
	if (!meta.value.ref.trim()) {
		refError.value = 'Design ref is required'
		toast.error('Design ref is required (please enter a ref like W-01)')
		return
	}
	saving.value = true
	try {
		const res = await saveDesign({
			project: project.value,
			design_ref: meta.value.ref.trim(),
			series_version: store.seriesVersion,
			design: store.design,
			svg: canvas.value?.getSvgMarkup() || generateElevationSvg(store.design, finishColor.value),
			qty: meta.value.qty,
			location: meta.value.location,
			name: savedName.value,
			finish: store.finish || null,
			price_structure: store.priceStructure || null,
		})
		if (res.ok) {
			toast.success('Design saved')
			store.markSaved()
			loadedName = res.name
			await router.replace({ name: 'Designer', params: { project: project.value, name: res.name } })
		} else {
			toast.error(res.message)
		}
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Save failed')
	} finally {
		saving.value = false
	}
}

async function copy() {
	if (!savedName.value || copying.value) return
	copying.value = true
	try {
		const copyName = await copyDesign(savedName.value)
		await router.push({ name: 'Designer', params: { project: project.value, name: copyName } })
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Copy failed')
	} finally {
		copying.value = false
	}
}

const propertiesPanel = ref<InstanceType<typeof PropertiesPanel> | null>(null)

function onSectionOpenProfilePicker(piece: { role?: string; panel?: string }) {
	const role =
		piece.role === 'mullion'
			? 'mullion'
			: piece.role === 'transom'
				? 'transom'
				: piece.role === 'sash'
					? 'sash'
					: 'frame'
	const key = piece.role === 'frame' ? 'frame' : piece.panel || 'frame'
	propertiesPanel.value?.openProfilePicker(role, key)
}
</script>

<template>
	<div class="flex min-h-screen flex-col bg-gray-50 text-gray-900 md:h-screen">
		<header class="flex flex-wrap items-center gap-3 border-b border-gray-200 bg-white px-4 py-2">
			<nav aria-label="Breadcrumb" class="flex items-center gap-1 text-sm">
				<RouterLink :to="`/projects/${project}`" class="min-h-9 content-center text-gray-600 hover:text-gray-900">
					Projects / {{ project }}
				</RouterLink>
			</nav>
			<span class="text-sm font-semibold">{{ meta.ref || 'New design' }} · {{ designType }}</span>
			<Badge v-if="store.seriesVersion" :label="store.seriesVersion" />
			<div class="ml-auto flex items-center gap-2">
				<Button icon="lucide-undo-2" aria-label="Undo" class="min-h-9 min-w-9" :disabled="!store.past.length" @click="store.undo()" />
				<Button icon="lucide-redo-2" aria-label="Redo" class="min-h-9 min-w-9" :disabled="!store.future.length" @click="store.redo()" />
				<div class="flex rounded-md border border-gray-200 p-0.5" role="group" aria-label="View">
					<Button
						v-for="v in VIEWS"
						:key="v.value"
						:label="v.label"
						:variant="view === v.value ? 'subtle' : 'ghost'"
						:aria-pressed="view === v.value"
						class="min-h-9"
						@click="view = v.value"
					/>
				</div>
				<Button
					label="Section"
					aria-label="Section"
					:variant="sectionOn ? 'subtle' : 'outline'"
					:aria-pressed="sectionOn"
					class="min-h-9"
					@click="sectionOn = !sectionOn"
				/>
				<Button label="Save" aria-label="Save" variant="solid" class="min-h-9" :disabled="blocked" @click="save" />
			</div>
		</header>
		<Alert v-if="loadError" role="alert" theme="red" :title="loadError" />
		<Alert v-if="lockedBy" role="status" theme="yellow" :title="lockMessage">
			<template #actions>
				<Button label="Copy design" aria-label="Copy design" :loading="copying" @click="copy" />
			</template>
		</Alert>

		<div class="flex min-h-0 flex-1 flex-col md:flex-row">
			<nav
				class="flex shrink-0 flex-row gap-2 overflow-x-auto border-b border-gray-200 bg-white p-3 md:w-36 md:flex-col md:overflow-x-visible md:overflow-y-auto md:border-r md:border-b-0 lg:w-52"
				aria-label="Tools"
			>
				<div class="hidden text-[11px] font-semibold uppercase tracking-wider text-[#5b6472] md:block">BUILD</div>
				<p v-if="!selectedLeaf" class="shrink-0 self-center text-xs text-gray-500 md:self-auto">{{ toolHint }}</p>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Split vertical"
						aria-label="Split vertical"
						icon-left="lucide-columns-2"
						class="min-h-9 shrink-0 whitespace-nowrap md:w-full"
						:style="selectedLeaf ? buildBtnStyle : buildBtnDisabledStyle"
						:disabled="!selectedLeaf"
						@click="split('v')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Split horizontal"
						aria-label="Split horizontal"
						icon-left="lucide-rows-2"
						class="min-h-9 shrink-0 whitespace-nowrap md:w-full"
						:style="selectedLeaf ? buildBtnStyle : buildBtnDisabledStyle"
						:disabled="!selectedLeaf"
						@click="split('h')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Sash"
						aria-label="Sash"
						icon-left="lucide-panel-left-open"
						class="min-h-9 shrink-0 whitespace-nowrap md:w-full"
						:style="selectedLeaf ? buildBtnStyle : buildBtnDisabledStyle"
						:disabled="!selectedLeaf"
						@click="convert('sash')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Fixed glass"
						aria-label="Fixed glass"
						icon-left="lucide-square"
						class="min-h-9 shrink-0 whitespace-nowrap md:w-full"
						:style="selectedLeaf ? buildBtnStyle : buildBtnDisabledStyle"
						:disabled="!selectedLeaf"
						@click="convert('fixed')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Bead on / off"
						aria-label="Bead on / off"
						icon-left="lucide-box-select"
						class="min-h-9 shrink-0 whitespace-nowrap md:w-full"
						:style="isBeadOn ? buildBtnActiveStyle : (selectedLeaf ? buildBtnStyle : buildBtnDisabledStyle)"
						:disabled="!selectedLeaf"
						@click="toggleBead"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Louver"
						aria-label="Louver"
						icon-left="lucide-align-justify"
						class="min-h-9 shrink-0 whitespace-nowrap md:w-full"
						:style="selectedLeaf ? buildBtnStyle : buildBtnDisabledStyle"
						:disabled="!selectedLeaf"
						@click="convert('louver')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Exhaust fan cut"
						aria-label="Exhaust fan cut"
						icon-left="lucide-fan"
						class="min-h-9 shrink-0 whitespace-nowrap md:w-full"
						:style="selectedLeaf?.fan ? buildBtnActiveStyle : (selectedLeaf ? buildBtnStyle : buildBtnDisabledStyle)"
						:disabled="!selectedLeaf"
						@click="toggleExhaustFan"
					/>
				</Tooltip>

				<!-- EDIT Group (Card) -->
				<div
					data-testid="edit-group-card"
					class="mt-2 flex flex-col gap-2 rounded-xl border border-gray-200 bg-[#f6f7f9] p-3 text-xs"
				>
					<div class="flex items-center justify-between">
						<span style="font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #5b6472">EDIT</span>
						<span
							style="font-size: 12px; font-weight: 500; color: #1b5fb8; background: #e8f0fc; border-radius: 999px; padding: 3px 9px"
						>
							{{ editSelectionChipLabel }}
						</span>
					</div>

					<!-- Delete Button -->
					<button
						type="button"
						aria-label="Delete"
						:aria-disabled="!canDelete"
						:style="canDelete ? deleteActiveStyle : deleteDisabledStyle"
						@click="canDelete && deleteSelected()"
					>
						<span style="display: flex; align-items: center; gap: 10px">
							<span
								style="width: 16px; height: 16px; display: inline-block; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23b42318' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5'/%3E%3C/svg%3E&quot;)"
								aria-hidden="true"
							/>
							{{ deleteLabel }}
						</span>
						<span
							style="font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #8a4a44; background: #fbe9e7; border-radius: 4px; padding: 2px 5px"
						>
							Del
						</span>
					</button>

					<!-- Merge Split Button -->
					<button
						type="button"
						aria-label="Merge split"
						:aria-disabled="!canRemoveSplit"
						:style="canRemoveSplit ? editBtnStyle : editBtnDisabledStyle"
						@click="canRemoveSplit && unsplitSelected()"
					>
						<span
							style="width: 16px; height: 16px; display: inline-block; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2314171c' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 4v6a4 4 0 0 0 4 4h6M19 4v6a4 4 0 0 1-4 4M12 14v6'/%3E%3C/svg%3E&quot;)"
							aria-hidden="true"
						/>
						Merge split
					</button>

					<!-- Reset Panel Button -->
					<button
						type="button"
						aria-label="Reset panel"
						:aria-disabled="!canResetPanel"
						:style="canResetPanel ? editBtnStyle : editBtnDisabledStyle"
						@click="canResetPanel && resetPanel()"
					>
						<span
							style="width: 16px; height: 16px; display: inline-block; background-repeat: no-repeat; background-position: center; background-size: contain; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2314171c' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 12a8 8 0 1 0 3-6.2M4 4v4h4'/%3E%3C/svg%3E&quot;)"
							aria-hidden="true"
						/>
						Reset panel
					</button>

					<span style="font-size: 11px; color: #5b6472; line-height: 1.45">
						Acts on the selection. Greyed out when nothing removable is selected.
					</span>
				</div>

				<!-- Profile Series Selector -->
				<div class="mt-3 hidden border-t border-gray-100 pt-3 md:block">
					<div class="mb-1.5 flex items-center justify-between">
						<span class="text-[11px] font-bold uppercase tracking-wider text-gray-500">Profile Series</span>
					</div>
					<select
						data-testid="sidebar-series-select"
						class="w-full rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-800 shadow-2xs transition hover:border-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
						:value="activeProfileSeries"
						@change="onSelectProfileSeries(($event.target as HTMLSelectElement).value)"
					>
						<option v-for="s in profileSeriesOptions" :key="s.value" :value="s.value">
							{{ s.label }}
						</option>
					</select>
				</div>

				<!-- Templates Quick Switcher -->
				<div class="mt-3 hidden border-t border-gray-100 pt-3 md:block">
					<div class="mb-2 flex items-center justify-between">
						<span class="text-[11px] font-bold uppercase tracking-wider text-gray-500">Templates</span>
						<span class="text-[10px] font-mono text-gray-400">{{ activeProfileSeries }}</span>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<button
							v-for="t in sidebarTemplates"
							:key="t.id"
							type="button"
							class="flex flex-col items-center gap-1.5 rounded-lg border border-gray-200 bg-white p-2 text-center text-[11px] font-medium text-gray-700 transition-colors hover:border-gray-400 hover:bg-gray-50"
							@click="applyTemplate(t.id)"
						>
							<div class="relative h-7 w-7 rounded border border-gray-400 bg-gray-50 overflow-hidden">
								<!-- Fixed Pane -->
								<div v-if="t.id === 'cs400-fixed' || t.id === 'cs4800-fixed'" class="h-full w-full bg-blue-50/50" />
								<!-- Fixed with Mullion -->
								<div v-else-if="t.id === 'cs400-fixmull' || t.id === 'cs4800-fixmull'" class="flex h-full w-full">
									<div class="h-full w-1/2 border-r border-gray-400 bg-blue-50/30" />
									<div class="h-full w-1/2 bg-blue-50/30" />
								</div>
								<!-- Single Sash -->
								<div v-else-if="t.id === 'cs400-single' || t.id === 'cs4800-single'" class="relative h-full w-full bg-blue-50/30">
									<div class="absolute inset-0 flex items-center justify-center text-[8px] text-gray-400 font-mono">◤</div>
								</div>
								<!-- Double Sash -->
								<div v-else-if="t.id === 'cs400-double' || t.id === 'cs4800-double' || t.id === 'casement-2'" class="flex h-full w-full">
									<div class="relative h-full w-1/2 border-r border-gray-400 bg-blue-50/30">
										<div class="absolute inset-0 flex items-center justify-center text-[8px] text-gray-400">◤</div>
									</div>
									<div class="relative h-full w-1/2 bg-blue-50/30">
										<div class="absolute inset-0 flex items-center justify-center text-[8px] text-gray-400">◥</div>
									</div>
								</div>
								<!-- Triple Sash -->
								<div v-else-if="t.id === 'cs400-triple' || t.id === 'cs4800-triple'" class="flex h-full w-full">
									<div class="h-full w-1/3 border-r border-gray-400 bg-blue-50/30" />
									<div class="h-full w-1/3 border-r border-gray-400 bg-blue-50/30" />
									<div class="h-full w-1/3 bg-blue-50/30" />
								</div>
								<!-- Double Open Cum Fixed -->
								<div v-else-if="t.id === 'cs400-dcf' || t.id === 'cs4800-door-dcf'" class="flex h-full w-full flex-col">
									<div class="flex h-3/5 w-full border-b border-gray-400">
										<div class="h-full w-1/2 border-r border-gray-300 bg-blue-50/30" />
										<div class="h-full w-1/2 bg-blue-50/30" />
									</div>
									<div class="h-2/5 w-full bg-gray-100" />
								</div>
								<!-- Single Open with Mesh -->
								<div v-else-if="t.id === 'cs4800-single-mesh'" class="relative h-full w-full bg-emerald-50/40">
									<div class="absolute inset-0 flex items-center justify-center text-[7px] text-emerald-600 font-mono">▤</div>
								</div>
								<!-- Double Open with Mesh -->
								<div v-else-if="t.id === 'cs4800-double-mesh'" class="flex h-full w-full">
									<div class="h-full w-1/2 border-r border-gray-400 bg-emerald-50/40 flex items-center justify-center text-[7px] text-emerald-600">▤</div>
									<div class="h-full w-1/2 bg-emerald-50/40 flex items-center justify-center text-[7px] text-emerald-600">▤</div>
								</div>
								<!-- Single Door -->
								<div v-else-if="t.id === 'cs4800-door-single'" class="relative h-full w-full bg-amber-50/40">
									<div class="absolute inset-0 flex items-center justify-center text-[8px] text-amber-700">🚪</div>
								</div>
								<!-- Single Door with Threshold -->
								<div v-else-if="t.id === 'cs4800-door-single-thresh'" class="flex h-full w-full flex-col bg-amber-50/40">
									<div class="flex-1 flex items-center justify-center text-[8px] text-amber-700">🚪</div>
									<div class="h-1 w-full bg-gray-600" />
								</div>
								<!-- Double Door -->
								<div v-else-if="t.id === 'cs4800-door-double'" class="flex h-full w-full bg-amber-50/40">
									<div class="h-full w-1/2 border-r border-amber-300 flex items-center justify-center text-[7px] text-amber-700">◨</div>
									<div class="h-full w-1/2 flex items-center justify-center text-[7px] text-amber-700">◧</div>
								</div>
								<!-- Ventilator -->
								<div v-else-if="t.id === 'ventilator'" class="flex h-full w-full">
									<div class="flex h-full w-2/3 flex-col border-r border-gray-400">
										<div class="h-1/3 border-b border-gray-300" />
										<div class="h-1/3 border-b border-gray-300" />
										<div class="h-1/3" />
									</div>
									<div class="h-full w-1/3" />
								</div>
								<!-- Sash Fixed Sash -->
								<div v-else-if="t.id === 'sash-fixed-sash'" class="flex h-full w-full">
									<div class="h-full w-1/3 border-r border-gray-400" />
									<div class="h-full w-1/3 border-r border-gray-400 bg-blue-50/30" />
									<div class="h-full w-1/3" />
								</div>
								<!-- Top Light -->
								<div v-else-if="t.id === 'top-light'" class="flex h-full w-full flex-col">
									<div class="h-1/3 border-b border-gray-400" />
									<div class="h-2/3" />
								</div>
								<div v-else class="h-full w-full bg-gray-100" />
							</div>
							<span class="leading-tight line-clamp-2">{{ t.label }}</span>
						</button>
					</div>
				</div>
			</nav>

			<main
				ref="mainEl"
				class="flex min-h-[50vh] min-w-0 flex-1 items-stretch bg-white md:min-h-0"
				:class="sectionOn ? 'flex-col overflow-hidden md:flex-row' : 'flex-col items-center justify-center overflow-hidden'"
			>
				<p v-if="loading" class="m-auto text-sm text-gray-500">Loading design...</p>
				<template v-else-if="!loadError">
					<div
						data-testid="designer-left-pane"
						class="flex h-full min-h-0 min-w-0 items-stretch justify-center overflow-hidden"
						:class="sectionOn && store.seriesVersion ? 'w-full md:shrink-0' : 'flex-1'"
						:style="sectionOn && store.seriesVersion ? { width: `${splitRatio}%` } : undefined"
					>
						<Window3DView
							v-if="view === '3d'"
							:design="store.design"
							:selected-path="store.selectedPath"
							:finish-color="finishColor"
							:outside-finish-color="outsideFinishColor"
							:finish-name="finishName"
							@select="store.select"
						/>
						<WindowCanvas
							v-show="view !== '3d'"
							ref="canvas"
							:design="store.design"
							:selected-path="store.selectedPath"
							:issue-paths="issuePaths"
							:view="view === 'outside' ? 'outside' : 'inside'"
							:finish-color="view === 'outside' ? outsideFinishColor : finishColor"
							:section="sectionOn ? cutPos : null"
							:members="store.result?.members"
							:glass="store.result?.glass"
							:profile-widths="store.seriesInfo?.profile_widths"
							@select="store.select"
							@move-split="onMoveSplit"
							@drag-start="store.beginDrag()"
							@drag-end="store.endDrag()"
							@update:cut="(c) => pickCut(c.axis, c.at)"
						/>
					</div>

					<!-- Draggable Split Workspace Resizer Separator -->
					<div
						v-if="sectionOn && store.seriesVersion"
						data-testid="workspace-resizer"
						role="separator"
						aria-orientation="vertical"
						aria-label="Resize workspace split"
						:aria-valuenow="Math.round(splitRatio)"
						title="Drag left or right to resize Window Designer and Cross-Section workspaces (double-click to reset)"
						class="group relative z-10 flex h-2 w-full shrink-0 cursor-row-resize items-center justify-center bg-gray-200 transition-colors hover:bg-blue-500 md:h-full md:w-2 md:cursor-col-resize"
						:class="resizingSplit ? 'bg-blue-600' : ''"
						@pointerdown="onSplitResizerPointerDown"
						@pointermove="onSplitResizerPointerMove"
						@pointerup="endSplitResize"
						@dblclick="splitRatio = 50"
					>
						<div
							class="h-1 w-8 rounded-full bg-gray-400 transition-colors group-hover:bg-white md:h-8 md:w-1"
							:class="resizingSplit ? 'bg-white' : ''"
						/>
					</div>

					<div
						v-if="sectionOn && store.seriesVersion"
						data-testid="section-split-pane"
						class="flex h-full min-h-[42vh] min-w-0 flex-1 overflow-hidden md:min-h-0"
					>
						<SectionView
							v-model:axis="cutAxis"
							class="h-full w-full flex-1"
							:design="store.design"
							:series-version="store.seriesVersion"
							:at="cutAt[cutAxis]"
							:selected-path="store.selectedPath"
							@cut="onSnapped"
							@update:section-map="onUpdateSectionMap"
							@update:mirror-sync="store.setMirrorSync"
							@update:compact-glass="store.setCompactGlass"
							@update:section-viewport="(ax, vp) => store.setSectionViewport(ax, vp)"
							@open-profile-picker="onSectionOpenProfilePicker"
							@select="store.select"
						/>
					</div>
				</template>
			</main>
			<PropertiesPanel
				ref="propertiesPanel"
				v-model:meta="meta"
				:finishes="finishes"
				:series-versions="seriesVersions"
				:ref-error="refError"
				:ref-readonly="!!savedName"
			/>
		</div>
		<ResultsBar />
	</div>
</template>
