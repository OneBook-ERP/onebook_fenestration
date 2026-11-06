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
import { layoutGeom } from '@/design/geometry'
import { TEMPLATES } from '@/design/templates'
import { typology } from '@/design/typology'
import { getNode, moveSplit, removeSplit, setLeaf, splitCell } from '@/design/tree'
import type { LeafNode, SplitDir } from '@/design/types'
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
const cutAxis = ref<CutAxis>('h')
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

const issuePaths = computed(() => (store.result?.issues ?? []).map((i) => i.path))
const selectedLeaf = computed(() => {
	try {
		const n = getNode(store.design, store.selectedPath)
		return n.type === 'split' ? null : n
	} catch {
		return null
	}
})
const canRemoveSplit = computed(() => {
	const p = store.selectedPath
	if (!p) return false
	if (layoutGeom(store.design).bars.some((b) => b.id === p)) return true
	try {
		const n = getNode(store.design, p)
		return n.type === 'split' || p.includes('.')
	} catch {
		return false
	}
})

const sidebarTemplates = computed(() => TEMPLATES.filter((t) => t.id !== 'blank'))

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
onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
onUnmounted(() => {
	window.removeEventListener('beforeunload', onBeforeUnload)
	store.cancelCompute()
})
onBeforeRouteLeave(() => !store.dirty || window.confirm('Discard unsaved changes?'))

function split(dir: SplitDir) {
	const path = store.selectedPath
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
	store.apply((d) => setLeaf(d, store.selectedPath, leaf))
}
function toggleExhaustFan() {
	const cur = selectedLeaf.value
	if (!cur) return
	store.apply((d) => setLeaf(d, store.selectedPath, { ...cur, fan: !cur.fan }))
}
function unsplitSelected() {
	const p = store.selectedPath
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
function applyTemplate(tplId: string) {
	const tpl = TEMPLATES.find((t) => t.id === tplId)
	if (!tpl) return
	const { width, height } = store.design
	store.apply(() => tpl.build(width, height))
	store.select(layoutGeom(store.design).cells[0]?.path ?? 'F1')
}
function onMoveSplit(p: { splitPath: string; index: number; pos: number }) {
	store.dragTo((d) => moveSplit(d, p.splitPath, p.index, p.pos))
}

async function save() {
	refError.value = ''
	if (blocked.value) return
	if (!meta.value.ref.trim()) {
		refError.value = 'Design ref is required'
		return
	}
	saving.value = true
	try {
		const res = await saveDesign({
			project: project.value,
			design_ref: meta.value.ref.trim(),
			series_version: store.seriesVersion,
			design: store.design,
			svg: canvas.value?.getSvgMarkup() ?? '',
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
				<div class="hidden text-[11px] font-bold uppercase tracking-wider text-gray-400 md:block">Build</div>
				<p v-if="!selectedLeaf" class="shrink-0 self-center text-xs text-gray-500 md:self-auto">{{ toolHint }}</p>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Split vertical"
						aria-label="Split vertical"
						icon-left="lucide-columns-2"
						class="min-h-9 shrink-0 justify-start whitespace-nowrap md:w-full"
						:disabled="!selectedLeaf"
						@click="split('v')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Split horizontal"
						aria-label="Split horizontal"
						icon-left="lucide-rows-2"
						class="min-h-9 shrink-0 justify-start whitespace-nowrap md:w-full"
						:disabled="!selectedLeaf"
						@click="split('h')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Sash"
						aria-label="Sash"
						icon-left="lucide-panel-left-open"
						class="min-h-9 shrink-0 justify-start whitespace-nowrap md:w-full"
						:disabled="!selectedLeaf"
						@click="convert('sash')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Fixed glass"
						aria-label="Fixed glass"
						icon-left="lucide-square"
						class="min-h-9 shrink-0 justify-start whitespace-nowrap md:w-full"
						:disabled="!selectedLeaf"
						@click="convert('fixed')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Louver"
						aria-label="Louver"
						icon-left="lucide-align-justify"
						class="min-h-9 shrink-0 justify-start whitespace-nowrap md:w-full"
						:disabled="!selectedLeaf"
						@click="convert('louver')"
					/>
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button
						label="Exhaust fan cut"
						aria-label="Exhaust fan cut"
						icon-left="lucide-fan"
						:variant="selectedLeaf?.fan ? 'subtle' : 'outline'"
						class="min-h-9 shrink-0 justify-start whitespace-nowrap md:w-full"
						:disabled="!selectedLeaf"
						@click="toggleExhaustFan"
					/>
				</Tooltip>
				<Button
					v-if="canRemoveSplit"
					label="Merge split"
					aria-label="Merge split"
					icon-left="lucide-combine"
					variant="ghost"
					class="min-h-9 shrink-0 justify-start whitespace-nowrap text-red-600 md:w-full"
					@click="unsplitSelected"
				/>

				<!-- Templates Quick Switcher -->
				<div class="mt-3 hidden border-t border-gray-100 pt-3 md:block">
					<div class="mb-2 text-[11px] font-bold uppercase tracking-wider text-gray-400">Templates</div>
					<div class="grid grid-cols-2 gap-2">
						<button
							v-for="t in sidebarTemplates"
							:key="t.id"
							type="button"
							class="flex flex-col items-center gap-1.5 rounded-lg border border-gray-200 bg-white p-2 text-center text-[11px] font-medium text-gray-700 transition-colors hover:border-gray-400 hover:bg-gray-50"
							@click="applyTemplate(t.id)"
						>
							<div class="relative h-7 w-7 rounded border border-gray-400 bg-gray-50">
								<div v-if="t.id === 'casement-2'" class="flex h-full w-full">
									<div class="h-full w-1/2 border-r border-gray-400" />
									<div class="h-full w-1/2" />
								</div>
								<div v-else-if="t.id === 'ventilator'" class="flex h-full w-full">
									<div class="flex h-full w-2/3 flex-col border-r border-gray-400">
										<div class="h-1/3 border-b border-gray-300" />
										<div class="h-1/3 border-b border-gray-300" />
										<div class="h-1/3" />
									</div>
									<div class="h-full w-1/3" />
								</div>
								<div v-else-if="t.id === 'sash-fixed-sash'" class="flex h-full w-full">
									<div class="h-full w-1/3 border-r border-gray-400" />
									<div class="h-full w-1/3 border-r border-gray-400" />
									<div class="h-full w-1/3" />
								</div>
								<div v-else-if="t.id === 'top-light'" class="flex h-full w-full flex-col">
									<div class="h-1/3 border-b border-gray-400" />
									<div class="h-2/3" />
								</div>
							</div>
							<span class="leading-tight">{{ t.label }}</span>
						</button>
					</div>
				</div>
			</nav>

			<main
				class="flex min-h-[50vh] min-w-0 flex-1 flex-col items-center bg-white md:min-h-0"
				:class="sectionOn ? 'justify-start overflow-y-auto overflow-x-hidden' : 'justify-center overflow-hidden'"
			>
				<p v-if="loading" class="text-sm text-gray-500">Loading design...</p>
				<template v-else-if="!loadError">
					<Window3DView
						v-if="view === '3d'"
						:design="store.design"
						:selected-path="store.selectedPath"
						:finish-color="finishColor"
						:outside-finish-color="outsideFinishColor"
						@select="store.select"
					/>
					<div
						v-else
						class="flex h-full w-full flex-1 items-stretch justify-center"
						:class="sectionOn ? 'min-h-[45vh]' : 'min-h-0'"
					>
						<WindowCanvas
							ref="canvas"
							:design="store.design"
							:selected-path="store.selectedPath"
							:issue-paths="issuePaths"
							:view="view === 'outside' ? 'outside' : 'inside'"
							:finish-color="view === 'outside' ? outsideFinishColor : finishColor"
							:section="sectionOn ? cutPos : null"
							:members="store.result?.members"
							:glass="store.result?.glass"
							@select="store.select"
							@move-split="onMoveSplit"
							@drag-start="store.beginDrag()"
							@drag-end="store.endDrag()"
							@update:cut="(c) => pickCut(c.axis, c.at)"
						/>
					</div>
					<SectionView
						v-if="sectionOn && store.seriesVersion"
						v-model:axis="cutAxis"
						class="shrink-0"
						:design="store.design"
						:series-version="store.seriesVersion"
						:at="cutAt[cutAxis]"
						@cut="onSnapped"
					/>
				</template>
			</main>
			<PropertiesPanel
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
