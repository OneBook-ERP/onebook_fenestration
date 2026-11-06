<script setup lang="ts">
import { FormControl, Select, useList } from 'frappe-ui'
import { computed } from 'vue'
import { getNode, moveSplit, removeSplit, setLeaf, setSize } from '@/design/tree'
import { panelLabel } from '@/design/typology'
import type { DesignNode, LeafNode, SplitNode } from '@/design/types'
import { useDesignerStore } from '@/stores/designer'

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
const selectedLabel = computed(() => panelLabel(store.selectedPath, store.result))
const glassCut = computed(() => {
	const row = store.result?.glass.find((g) => g.path === store.selectedPath)
	const mm = (v: number | undefined) => (typeof v === 'number' ? v.toFixed(1) : null)
	const w = mm(row?.width)
	const h = mm(row?.height)
	return w && h ? `${w} × ${h} mm` : '—'
})

const sashSize = computed(() => {
	if (leaf.value?.type !== 'sash') return '—'
	const members = (store.result?.members ?? []).filter(
		(m) => m.path === store.selectedPath && m.role === 'sash',
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
		(b) => b.panel === panel && (b.item.startsWith('H416') || b.item.startsWith('H417') || b.name.toLowerCase().includes('stay') || b.name.toLowerCase().includes('hinge')),
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
		(b) => b.panel === panel && (b.item.startsWith('H422') || b.name.toLowerCase().includes('espag') || b.name.toLowerCase().includes('rod')),
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

const currentFinishObj = computed(() =>
	(props.finishes ?? []).find((f) => f.name === store.finish),
)
const outsideFinishCode = computed(() => store.design.finishOutside || store.finish)
const outsideFinishObj = computed(() =>
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
	const n = nodeAt(store.selectedPath)
	return n && n.type !== 'split' ? n : null
})
const splitPath = computed(() => {
	const p = store.selectedPath
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
	const next = Object.fromEntries(Object.entries({ ...leaf.value, ...patch }).filter(([, v]) => v !== undefined)) as unknown as LeafNode
	store.apply((d) => setLeaf(d, store.selectedPath, next))
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
const optStr = <T extends string = string>(v: string | number | null) => (v && v !== NONE ? (String(v) as T) : undefined)
function optNum(e: Event): number | undefined {
	const v = (e.target as HTMLInputElement).value
	return v === '' ? undefined : Number(v)
}
</script>

<template>
	<aside class="flex w-full shrink-0 flex-col gap-3 border-t border-gray-200 bg-gray-50/60 p-3 md:w-72 md:overflow-y-auto md:border-t-0 md:border-l lg:w-80">
		<!-- Card 1: Basic Info -->
		<details open class="rounded-xl border border-gray-200 bg-white p-3.5 shadow-2xs">
			<summary class="cursor-pointer text-sm font-semibold text-gray-900">Basic info</summary>
			<div class="mt-3 flex flex-col gap-3">
				<div class="grid grid-cols-2 gap-2.5">
					<FormControl v-model="meta.ref" label="Design ref" :readonly="refReadonly" :error="refError" />
					<FormControl v-model="meta.qty" type="number" label="Quantity" min="1" />
				</div>
				<div class="grid grid-cols-2 gap-2.5">
					<FormControl
						:model-value="store.design.width"
						type="number"
						label="Width (mm)"
						@change="resize(num($event), store.design.height)"
					/>
					<FormControl
						:model-value="store.design.height"
						type="number"
						label="Height (mm)"
						@change="resize(store.design.width, num($event))"
					/>
				</div>
				<FormControl v-model="meta.location" label="Location" placeholder="e.g. Bedroom 2, Floor 1" />
			</div>
		</details>

		<!-- Card 2: System & Finish -->
		<details open class="rounded-xl border border-gray-200 bg-white p-3.5 shadow-2xs">
			<summary class="cursor-pointer text-sm font-semibold text-gray-900">System &amp; finish</summary>
			<div class="mt-3 flex flex-col gap-3">
				<Select
					v-if="seriesVersionOptions.length"
					label="Series"
					:options="seriesVersionOptions"
					:model-value="store.seriesVersion"
					@update:model-value="store.setSeriesVersion(String($event ?? ''))"
				/>
				<Select
					label="Finish"
					:options="finishOptions(finishes)"
					:model-value="store.finish"
					@update:model-value="store.setFinish(String($event ?? ''))"
				/>
				<div v-if="finishes?.length" class="space-y-1.5">
					<div class="text-xs text-gray-500">Finish (dual colour)</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-xs">
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
							class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-left text-xs hover:bg-gray-100"
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
		</details>

		<!-- Card 3: Selected Panel -->
		<details
			v-if="leaf"
			open
			class="rounded-xl border-2 border-blue-600 bg-white p-3.5 shadow-2xs"
		>
			<summary class="flex cursor-pointer items-center justify-between text-sm font-semibold text-gray-900">
				<span>Selected panel {{ selectedLabel }}</span>
				<span class="rounded bg-blue-50 px-1.5 py-0.5 font-mono text-xs font-semibold text-blue-700">
					{{ leaf.type }}
				</span>
			</summary>
			<div class="mt-3 flex flex-col gap-3">
				<template v-if="leaf.type === 'sash'">
					<div class="grid grid-cols-2 gap-2.5">
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
					<div class="grid grid-cols-2 gap-2.5">
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
					<div class="grid grid-cols-2 gap-2.5">
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
					<div class="grid grid-cols-2 gap-2.5">
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
					v-if="leaf.type === 'louver'"
					type="number"
					label="Blades"
					min="1"
					:model-value="leaf.blades"
					@change="patchLeaf({ blades: num($event) })"
				/>
				<Select
					label="Glass"
					:options="glassOptions"
					:model-value="leaf.glass"
					@update:model-value="patchLeaf({ glass: String($event ?? '') })"
				/>

				<!-- Derived Engineering Summary Table -->
				<div class="mt-1 space-y-1.5 border-t border-gray-100 pt-2.5 text-xs">
					<div v-if="leaf.type === 'sash'" class="flex items-center justify-between text-gray-600">
						<span>Sash size</span>
						<span class="font-medium text-gray-900">{{ sashSize }}</span>
					</div>
					<p class="flex items-center justify-between text-gray-600">
						<span>Glass cut {{ glassCut }}</span>
					</p>
					<template v-if="leaf.type === 'sash'">
						<div class="flex items-center justify-between text-gray-600">
							<span>Friction stay</span>
							<span class="font-medium text-gray-900">{{ frictionStayLabel }}</span>
						</div>
						<div class="flex items-center justify-between text-gray-600">
							<span>Espag</span>
							<span class="font-medium text-gray-900">{{ espagLabel }}</span>
						</div>
					</template>
					<div v-if="leaf.fan" class="flex items-center justify-between text-blue-700">
						<span>Exhaust fan cut</span>
						<span class="font-semibold">180 mm cutout</span>
					</div>
				</div>
			</div>
		</details>

		<!-- Card 4: Split Controls -->
		<details v-if="split" open class="rounded-xl border border-gray-200 bg-white p-3.5 shadow-2xs">
			<summary class="flex cursor-pointer items-center justify-between text-sm font-semibold text-gray-900">
				<span>Split ({{ split.dir === 'v' ? 'vertical' : 'horizontal' }})</span>
				<button
					type="button"
					class="text-xs font-medium text-red-600 hover:underline"
					@click.prevent="onRemoveSplit"
				>
					Remove split
				</button>
			</summary>
			<div class="mt-3 flex flex-col gap-3">
				<FormControl
					v-for="(a, i) in split.at"
					:key="i"
					type="number"
					:label="`Bar ${i + 1} position (mm)`"
					:model-value="a"
					@change="moveBar(i, $event)"
				/>
			</div>
		</details>

		<!-- Card 5: Contextual Engineering Issues / Warnings -->
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
	</aside>
</template>
