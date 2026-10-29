<script setup lang="ts">
import { toast } from 'frappe-ui'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { getDesign, saveDesign } from '@/api'
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

onMounted(async () => {
	if (!savedName.value) {
		store.reset(newDesign(1200, 1200), String(route.query.series_version ?? ''))
		return
	}
	try {
		const doc = await getDesign(savedName.value)
		Object.assign(meta.value, { ref: doc.design_ref, qty: doc.qty, location: doc.location ?? '' })
		store.reset(JSON.parse(doc.design_json), doc.series_version)
	} catch (e) {
		loadError.value = e instanceof Error ? e.message : 'Could not load design'
	}
})

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
	store.apply((d) => moveSplit(d, p.splitPath, p.index, p.pos))
}

async function save() {
	refError.value = ''
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

const btn =
	'inline-flex h-9 min-w-9 items-center justify-center rounded border border-gray-300 bg-white px-3 text-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40'
</script>

<template>
	<div class="flex h-screen flex-col bg-gray-50 text-gray-900">
		<header class="flex flex-wrap items-center gap-3 border-b border-gray-200 bg-white px-4 py-2">
			<RouterLink :to="`/projects/${project}`" aria-label="Back to project" :class="btn">&larr; Back</RouterLink>
			<span class="text-sm font-semibold">{{ meta.ref || 'New design' }}</span>
			<span v-if="store.seriesVersion" class="rounded-full bg-gray-100 px-2 py-0.5 text-xs">{{ store.seriesVersion }}</span>
			<div class="ml-auto flex items-center gap-2">
				<button :class="btn" aria-label="Undo" :disabled="!store.past.length" @click="store.undo()">Undo</button>
				<button :class="btn" aria-label="Redo" :disabled="!store.future.length" @click="store.redo()">Redo</button>
				<button
					:class="btn"
					aria-label="Toggle inside or outside view"
					@click="view = view === 'inside' ? 'outside' : 'inside'"
				>{{ view === 'inside' ? 'Inside' : 'Outside' }}</button>
				<button
					class="inline-flex h-9 items-center rounded bg-gray-900 px-4 text-sm font-medium text-white disabled:opacity-50"
					aria-label="Save"
					:disabled="saving"
					@click="save"
				>Save</button>
			</div>
		</header>
		<p v-if="loadError" role="alert" class="bg-red-50 px-4 py-2 text-sm text-red-700">{{ loadError }}</p>

		<div class="flex min-h-0 flex-1">
			<nav class="flex w-36 shrink-0 flex-col gap-2 border-r border-gray-200 bg-white p-3" aria-label="Tools">
				<button :class="btn" aria-label="Split vertical" :disabled="!selectedLeaf" @click="split('v')">Split vertical</button>
				<button :class="btn" aria-label="Split horizontal" :disabled="!selectedLeaf" @click="split('h')">Split horizontal</button>
				<button :class="btn" aria-label="Sash" :disabled="!selectedLeaf" @click="convert('sash')">Sash</button>
				<button :class="btn" aria-label="Fixed glass" :disabled="!selectedLeaf" @click="convert('fixed')">Fixed glass</button>
				<button :class="btn" aria-label="Louver" :disabled="!selectedLeaf" @click="convert('louver')">Louver</button>
			</nav>
			<main class="flex min-w-0 flex-1 items-center justify-center overflow-auto">
				<WindowCanvas
					ref="canvas"
					:design="store.design"
					:selected-path="store.selectedPath"
					:issue-paths="issuePaths"
					:view="view"
					@select="store.select"
					@move-split="onMoveSplit"
				/>
			</main>
			<PropertiesPanel v-model:meta="meta" :ref-error="refError" />
		</div>
		<ResultsBar />
	</div>
</template>
