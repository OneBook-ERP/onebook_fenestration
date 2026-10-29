<script setup lang="ts">
import { Alert, Badge, Button, toast } from 'frappe-ui'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { getDesign, saveDesign, type SavedDesign } from '@/api'
import PropertiesPanel, { type Meta } from '@/components/PropertiesPanel.vue'
import ResultsBar from '@/components/ResultsBar.vue'
import WindowCanvas from '@/components/WindowCanvas.vue'
import { getNode, moveSplit, newDesign, setLeaf, splitCell } from '@/design/tree'
import type { LeafNode, SplitDir } from '@/design/types'
import { useDesignerStore } from '@/stores/designer'

const store = useDesignerStore()
const route = useRoute()
const router = useRouter()
const project = computed(() => String(route.params.project))
const savedName = computed(() => (route.params.name ? String(route.params.name) : null))

const meta = ref<Meta>({ ref: '', qty: 1, location: '' })
const refError = ref('')
const view = ref<'inside' | 'outside'>('inside')
const saving = ref(false)
const loadError = ref('')
const loading = ref(false)
let loadedName: string | null = null
const blocked = computed(() => loading.value || !!loadError.value || saving.value)
const canvas = ref<InstanceType<typeof WindowCanvas> | null>(null)

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
		meta.value = { ref: '', qty: 1, location: '' }
		store.reset(newDesign(1200, 1200), String(route.query.series_version ?? ''))
		return
	}
	if (name === loadedName) return
	loading.value = true
	try {
		const doc: SavedDesign = await getDesign(name)
		if (name !== savedName.value) return
		meta.value = { ref: doc.design_ref, qty: doc.qty, location: doc.location ?? '' }
		store.reset(parseJson(doc.design_json), doc.series_version)
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

</script>

<template>
	<div class="flex h-screen flex-col bg-gray-50 text-gray-900">
		<header class="flex flex-wrap items-center gap-3 border-b border-gray-200 bg-white px-4 py-2">
			<Button label="Back" aria-label="Back to project" class="min-h-9" :route="`/projects/${project}`" />
			<span class="text-sm font-semibold">{{ meta.ref || 'New design' }}</span>
			<Badge v-if="store.seriesVersion" :label="store.seriesVersion" />
			<div class="ml-auto flex items-center gap-2">
				<Button label="Undo" aria-label="Undo" class="min-h-9" :disabled="!store.past.length" @click="store.undo()" />
				<Button label="Redo" aria-label="Redo" class="min-h-9" :disabled="!store.future.length" @click="store.redo()" />
				<Button
					label="Outside view"
					:aria-pressed="view === 'outside'"
					class="min-h-9"
					@click="view = view === 'inside' ? 'outside' : 'inside'"
				/>
				<Button label="Save" aria-label="Save" variant="solid" class="min-h-9" :disabled="blocked" @click="save" />
			</div>
		</header>
		<Alert v-if="loadError" role="alert" theme="red" :title="loadError" />

		<div class="flex min-h-0 flex-1">
			<nav class="flex w-36 shrink-0 flex-col gap-2 border-r border-gray-200 bg-white p-3" aria-label="Tools">
				<Button label="Split vertical" aria-label="Split vertical" class="min-h-9" :disabled="!selectedLeaf" @click="split('v')" />
				<Button label="Split horizontal" aria-label="Split horizontal" class="min-h-9" :disabled="!selectedLeaf" @click="split('h')" />
				<Button label="Sash" aria-label="Sash" class="min-h-9" :disabled="!selectedLeaf" @click="convert('sash')" />
				<Button label="Fixed glass" aria-label="Fixed glass" class="min-h-9" :disabled="!selectedLeaf" @click="convert('fixed')" />
				<Button label="Louver" aria-label="Louver" class="min-h-9" :disabled="!selectedLeaf" @click="convert('louver')" />
			</nav>
			<main class="flex min-w-0 flex-1 items-center justify-center overflow-auto">
				<p v-if="loading" class="text-sm text-gray-500">Loading design...</p>
				<WindowCanvas
					v-else-if="!loadError"
					ref="canvas"
					:design="store.design"
					:selected-path="store.selectedPath"
					:issue-paths="issuePaths"
					:view="view"
					@select="store.select"
					@move-split="onMoveSplit"
					@drag-start="store.beginDrag()"
					@drag-end="store.endDrag()"
				/>
			</main>
			<PropertiesPanel v-model:meta="meta" :ref-error="refError" :ref-readonly="!!savedName" />
		</div>
		<ResultsBar />
	</div>
</template>
