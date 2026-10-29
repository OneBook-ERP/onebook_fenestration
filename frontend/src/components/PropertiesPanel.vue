<script setup lang="ts">
import { FormControl, Select } from 'frappe-ui'
import { computed } from 'vue'
import { getNode, moveSplit, setLeaf, setSize } from '@/design/tree'
import type { DesignNode, LeafNode, SplitNode } from '@/design/types'
import { useDesignerStore } from '@/stores/designer'

export interface Meta {
	ref: string
	qty: number
	location: string
}
const meta = defineModel<Meta>('meta', { required: true })
defineProps<{ refError?: string; refReadonly?: boolean }>()
const store = useDesignerStore()

const NONE = 'none'
const OPENINGS = [{ label: 'None', value: NONE }, { label: 'In', value: 'in' }, { label: 'Out', value: 'out' }]
const HINGES = [
	{ label: 'None', value: NONE },
	{ label: 'Left', value: 'left' },
	{ label: 'Right', value: 'right' },
	{ label: 'Top', value: 'top' },
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

function num(e: Event): number {
	return Number((e.target as HTMLInputElement).value)
}
function resize(w: number, h: number) {
	if (!(w > 0 && h > 0)) return
	store.apply((d) => setSize(d, w, h))
}
function patchLeaf(patch: Partial<LeafNode>) {
	if (!leaf.value) return
	const next = { ...leaf.value, ...patch } as LeafNode
	store.apply((d) => setLeaf(d, store.selectedPath, next))
}
function moveBar(i: number, e: Event) {
	const pos = num(e)
	store.apply((d) => moveSplit(d, splitPath.value, i, pos))
}
const optStr = (v: string | number | null) => (v && v !== NONE ? String(v) : undefined)
function optNum(e: Event): number | undefined {
	const v = (e.target as HTMLInputElement).value
	return v === '' ? undefined : Number(v)
}
</script>

<template>
	<aside class="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-l border-gray-200 bg-white p-4">
		<details open>
			<summary class="cursor-pointer text-sm font-semibold">Basic info</summary>
			<div class="mt-3 flex flex-col gap-3">
				<FormControl v-model="meta.ref" label="Design ref" :readonly="refReadonly" :error="refError" />
				<FormControl v-model="meta.qty" type="number" label="Quantity" min="1" />
				<div class="grid grid-cols-2 gap-2">
					<FormControl :model-value="store.design.width" type="number" label="Width (mm)"
						@change="resize(num($event), store.design.height)" />
					<FormControl :model-value="store.design.height" type="number" label="Height (mm)"
						@change="resize(store.design.width, num($event))" />
				</div>
				<FormControl v-model="meta.location" label="Location" />
			</div>
		</details>

		<details v-if="leaf" open>
			<summary class="cursor-pointer text-sm font-semibold">Selected panel ({{ store.selectedPath }})</summary>
			<div class="mt-3 flex flex-col gap-3">
				<template v-if="leaf.type === 'sash'">
					<Select label="Opening" :options="OPENINGS" :model-value="leaf.opening ?? NONE"
						@update:model-value="patchLeaf({ opening: optStr($event) })" />
					<Select label="Hinge" :options="HINGES" :model-value="leaf.hinge ?? NONE"
						@update:model-value="patchLeaf({ hinge: optStr($event) })" />
					<FormControl type="number" label="GHH (mm)" :model-value="leaf.ghh ?? ''"
						@change="patchLeaf({ ghh: optNum($event) })" />
				</template>
				<FormControl v-if="leaf.type === 'louver'" type="number" label="Blades" min="1"
					:model-value="leaf.blades" @change="patchLeaf({ blades: num($event) })" />
				<FormControl label="Glass code" :model-value="leaf.glass"
					@change="patchLeaf({ glass: ($event.target as HTMLInputElement).value })" />
			</div>
		</details>

		<details v-if="split" open>
			<summary class="cursor-pointer text-sm font-semibold">
				Split ({{ split.dir === 'v' ? 'vertical' : 'horizontal' }})
			</summary>
			<div class="mt-3 flex flex-col gap-3">
				<FormControl v-for="(a, i) in split.at" :key="i" type="number" :label="`Bar ${i + 1} position (mm)`"
					:model-value="a" @change="moveBar(i, $event)" />
			</div>
		</details>
	</aside>
</template>
