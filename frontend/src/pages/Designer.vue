<script setup lang="ts">
import { Alert, Badge, Button, Tooltip, toast, useList } from 'frappe-ui'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { copyDesign, getDesign, getFenestrationDefaults, saveDesign, type SavedDesign } from '@/api'
import PropertiesPanel, { type Meta } from '@/components/PropertiesPanel.vue'
import ResultsBar from '@/components/ResultsBar.vue'
import WindowCanvas from '@/components/WindowCanvas.vue'
import { typology } from '@/design/typology'
import { getNode, moveSplit, newDesign, setLeaf, splitCell } from '@/design/tree'
import type { LeafNode, SplitDir } from '@/design/types'
import { useDesignerStore } from '@/stores/designer'

interface FinishRow {
	name: string
	finish_name: string
	color: string
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
] as const
const view = ref<'inside' | 'outside'>('inside')
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

const finishList = useList<FinishRow>({
	doctype: 'Profile Finish',
	fields: ['name', 'finish_name', 'color'],
	orderBy: 'name asc',
	limit: 100,
})
const finishes = computed(() => finishList.data ?? [])
const finishColor = computed(() => finishes.value.find((f) => f.name === store.finish)?.color || undefined)

const issuePaths = computed(() => (store.result?.issues ?? []).map((i) => i.path))
const selectedLeaf = computed(() => {
	try {
		const n = getNode(store.design, store.selectedPath)
		return n.type === 'split' ? null : n
	} catch {
		return null
	}
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
		store.reset(
			newDesign(1200, 1200),
			String(route.query.series_version ?? ''),
			defaults.default_finish ?? '',
			defaults.default_price_structure ?? '',
		)
		return
	}
	if (name === loadedName) return
	loading.value = true
	try {
		const doc: SavedDesign = await getDesign(name)
		if (name !== savedName.value) return
		meta.value = { ref: doc.design_ref, qty: doc.qty, location: doc.location ?? '' }
		store.reset(parseJson(doc.design_json), doc.series_version, doc.finish ?? '', doc.price_structure ?? '')
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
			? { type: 'sash', glass, opening: 'out', hinge: 'left' }
			: kind === 'louver'
				? { type: 'louver', glass, blades: 9 }
				: { type: 'fixed', glass }
	store.apply((d) => setLeaf(d, store.selectedPath, leaf))
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
	<div class="flex h-screen flex-col bg-gray-50 text-gray-900">
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
				<Button label="Save" aria-label="Save" variant="solid" class="min-h-9" :disabled="blocked" @click="save" />
			</div>
		</header>
		<Alert v-if="loadError" role="alert" theme="red" :title="loadError" />
		<Alert v-if="lockedBy" role="status" theme="yellow" :title="lockMessage">
			<template #actions>
				<Button label="Copy design" aria-label="Copy design" :loading="copying" @click="copy" />
			</template>
		</Alert>

		<div class="flex min-h-0 flex-1">
			<nav class="flex w-36 shrink-0 flex-col gap-2 border-r border-gray-200 bg-white p-3" aria-label="Tools">
				<p v-if="!selectedLeaf" class="text-xs text-gray-500">{{ toolHint }}</p>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button label="Split vertical" aria-label="Split vertical" class="min-h-9 w-full" :disabled="!selectedLeaf" @click="split('v')" />
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button label="Split horizontal" aria-label="Split horizontal" class="min-h-9 w-full" :disabled="!selectedLeaf" @click="split('h')" />
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button label="Sash" aria-label="Sash" class="min-h-9 w-full" :disabled="!selectedLeaf" @click="convert('sash')" />
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button label="Fixed glass" aria-label="Fixed glass" class="min-h-9 w-full" :disabled="!selectedLeaf" @click="convert('fixed')" />
				</Tooltip>
				<Tooltip :text="selectedLeaf ? '' : toolHint">
					<Button label="Louver" aria-label="Louver" class="min-h-9 w-full" :disabled="!selectedLeaf" @click="convert('louver')" />
				</Tooltip>
			</nav>
			<main class="flex min-h-0 min-w-0 flex-1 items-center justify-center overflow-hidden p-2">
				<p v-if="loading" class="text-sm text-gray-500">Loading design...</p>
				<WindowCanvas
					v-else-if="!loadError"
					ref="canvas"
					:design="store.design"
					:selected-path="store.selectedPath"
					:issue-paths="issuePaths"
					:view="view"
					:finish-color="finishColor"
					@select="store.select"
					@move-split="onMoveSplit"
					@drag-start="store.beginDrag()"
					@drag-end="store.endDrag()"
				/>
			</main>
			<PropertiesPanel v-model:meta="meta" :finishes="finishes" :ref-error="refError" :ref-readonly="!!savedName" />
		</div>
		<ResultsBar />
	</div>
</template>
