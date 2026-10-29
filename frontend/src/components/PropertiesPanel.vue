<script setup lang="ts">
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
defineProps<{ refError?: string }>()
const store = useDesignerStore()

const input =
	'h-9 w-full rounded border border-gray-300 bg-white px-2 text-sm focus:border-blue-600 focus:outline-none'
const label = 'flex flex-col gap-1 text-xs font-medium text-gray-600'

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
function optStr(e: Event): string | undefined {
	return (e.target as HTMLSelectElement).value || undefined
}
function optNum(e: Event): number | undefined {
	const v = (e.target as HTMLInputElement).value
	return v === '' ? undefined : Number(v)
}
</script>

<template>
	<aside class="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-l border-gray-200 bg-white p-4">
		<details open class="flex flex-col gap-3">
			<summary class="cursor-pointer text-sm font-semibold">Basic info</summary>
			<div class="mt-3 flex flex-col gap-3">
				<label :class="label">Design ref
					<input v-model="meta.ref" aria-label="Design ref" :class="input" />
					<span v-if="refError" class="text-red-600">{{ refError }}</span>
				</label>
				<label :class="label">Quantity
					<input v-model.number="meta.qty" type="number" min="1" aria-label="Quantity" :class="input" />
				</label>
				<div class="grid grid-cols-2 gap-2">
					<label :class="label">Width (mm)
						<input :value="store.design.width" type="number" aria-label="Width" :class="input"
							@change="resize(num($event), store.design.height)" />
					</label>
					<label :class="label">Height (mm)
						<input :value="store.design.height" type="number" aria-label="Height" :class="input"
							@change="resize(store.design.width, num($event))" />
					</label>
				</div>
				<label :class="label">Location
					<input v-model="meta.location" aria-label="Location" :class="input" />
				</label>
			</div>
		</details>

		<details v-if="leaf" open class="flex flex-col gap-3">
			<summary class="cursor-pointer text-sm font-semibold">Selected panel ({{ store.selectedPath }})</summary>
			<div class="mt-3 flex flex-col gap-3">
				<template v-if="leaf.type === 'sash'">
					<label :class="label">Opening
						<select :class="input" aria-label="Opening" :value="leaf.opening ?? ''"
							@change="patchLeaf({ opening: optStr($event) })">
							<option value="">None</option>
							<option value="in">In</option>
							<option value="out">Out</option>
						</select>
					</label>
					<label :class="label">Hinge
						<select :class="input" aria-label="Hinge" :value="leaf.hinge ?? ''"
							@change="patchLeaf({ hinge: optStr($event) })">
							<option value="">None</option>
							<option value="left">Left</option>
							<option value="right">Right</option>
							<option value="top">Top</option>
						</select>
					</label>
					<label :class="label">GHH (mm)
						<input type="number" aria-label="GHH" :class="input" :value="leaf.ghh ?? ''"
							@change="patchLeaf({ ghh: optNum($event) })" />
					</label>
				</template>
				<label v-if="leaf.type === 'louver'" :class="label">Blades
					<input type="number" min="1" aria-label="Blades" :class="input" :value="leaf.blades"
						@change="patchLeaf({ blades: num($event) })" />
				</label>
				<label :class="label">Glass code
					<input aria-label="Glass code" :class="input" :value="leaf.glass"
						@change="patchLeaf({ glass: ($event.target as HTMLInputElement).value })" />
				</label>
			</div>
		</details>

		<details v-if="split" open class="flex flex-col gap-3">
			<summary class="cursor-pointer text-sm font-semibold">
				Split ({{ split.dir === 'v' ? 'vertical' : 'horizontal' }})
			</summary>
			<div class="mt-3 flex flex-col gap-3">
				<label v-for="(a, i) in split.at" :key="i" :class="label">Bar {{ i + 1 }} position (mm)
					<input type="number" :aria-label="`Bar ${i + 1} position`" :class="input" :value="a"
						@change="moveBar(i, $event)" />
				</label>
			</div>
		</details>
	</aside>
</template>
