<script setup lang="ts">
import { Alert, Badge, TabButtons } from 'frappe-ui'
import { computed, ref } from 'vue'
import type { BomRow, Member } from '@/api'
import { useDesignerStore } from '@/stores/designer'

const store = useDesignerStore()
const tab = ref('Cut list')

const result = computed(() => store.result)
const issues = computed(() => result.value?.issues ?? [])
const errors = computed(() => issues.value.filter((i) => i.severity === 'Error').length)
const warnings = computed(() => issues.value.filter((i) => i.severity === 'Warning').length)

const shutters = computed(() => {
	const s = result.value?.shutter_kg
	if (s == null) return []
	return typeof s === 'number' ? [['', s] as [string, number]] : Object.entries(s)
})

const cutList = computed(() => {
	const rows = new Map<string, { m: Member; qty: number }>()
	for (const m of result.value?.members ?? []) {
		const key = `${m.profile}|${m.length}|${m.angles}`
		const row = rows.get(key)
		if (row) row.qty += 1
		else rows.set(key, { m, qty: 1 })
	}
	return [...rows.values()]
})
const hardware = computed<BomRow[]>(() => (result.value?.bom ?? []).filter((b) => b.group !== 'Gasket'))

const tabOptions = computed(() =>
	['Cut list', 'Hardware', 'Glass', 'Issues'].map((t) => ({
		value: t,
		label: t === 'Issues' ? `Issues (${issues.value.length})` : t,
	})),
)

const th = 'px-3 py-1.5 text-left text-xs font-semibold text-gray-500'
const td = 'px-3 py-1.5 text-sm'
</script>

<template>
	<section class="border-t border-gray-200 bg-white">
		<Alert v-if="store.error" role="alert" theme="red" :title="store.error" />
		<div :class="{ 'opacity-50': store.error && result }">
			<div v-if="result" class="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-gray-100 px-4 py-2 text-sm">
				<span>Area {{ result.area_m2.toFixed(3) }} m&sup2; &middot; {{ result.area_sqft.toFixed(3) }} sq.ft</span>
				<span>Window {{ result.window_kg.toFixed(3) }} kg</span>
				<span v-for="[panel, kg] in shutters" :key="panel">
					Shutter {{ panel }} {{ Number(kg).toFixed(3) }} kg
				</span>
				<Badge theme="red" :label="`${errors} errors`" />
				<Badge theme="amber" :label="`${warnings} warnings`" />
			</div>
			<p v-else-if="!store.error" class="px-4 py-2 text-sm text-gray-500">Computing...</p>

			<div class="px-2 py-1">
				<TabButtons v-model="tab" :options="tabOptions" />
			</div>

		<div class="max-h-48 overflow-auto">
			<table v-if="tab === 'Cut list'" class="w-full">
				<thead><tr><th :class="th">Profile</th><th :class="th">Length</th><th :class="th">Angles</th><th :class="th">Qty</th></tr></thead>
				<tbody>
					<tr v-for="r in cutList" :key="`${r.m.profile}|${r.m.length}|${r.m.angles}`">
						<td :class="td">{{ r.m.profile }}</td><td :class="td">{{ r.m.length }}</td><td :class="td">{{ r.m.angles }}</td><td :class="td">{{ r.qty }}</td>
					</tr>
				</tbody>
			</table>
			<table v-else-if="tab === 'Hardware'" class="w-full">
				<thead><tr><th :class="th">Item</th><th :class="th">Name</th><th :class="th">Qty</th><th :class="th">UOM</th><th :class="th">Panel</th></tr></thead>
				<tbody>
					<tr v-for="(b, i) in hardware" :key="i">
						<td :class="td">{{ b.item }}</td><td :class="td">{{ b.name }}</td><td :class="td">{{ b.qty }}</td><td :class="td">{{ b.uom }}</td><td :class="td">{{ b.panel }}</td>
					</tr>
				</tbody>
			</table>
			<table v-else-if="tab === 'Glass'" class="w-full">
				<thead><tr><th :class="th">Panel</th><th :class="th">No.</th><th :class="th">Glass</th><th :class="th">Width</th><th :class="th">Height</th></tr></thead>
				<tbody>
					<tr v-for="g in result?.glass ?? []" :key="g.path">
						<td :class="td">{{ g.panel }}</td><td :class="td">{{ g.number }}</td><td :class="td">{{ g.glass }}</td><td :class="td">{{ g.width }}</td><td :class="td">{{ g.height }}</td>
					</tr>
				</tbody>
			</table>
			<ul v-else>
				<li v-for="(i, n) in issues" :key="n">
					<button
						:data-issue-path="i.path"
						class="flex min-h-9 w-full items-start gap-3 px-3 py-1.5 text-left text-sm hover:bg-gray-50"
						@click="store.select(i.path)"
					>
						<span class="font-mono text-xs text-gray-500">{{ i.path }}</span>
						<span :class="i.severity === 'Error' ? 'text-red-700' : 'text-amber-700'">{{ i.severity }}</span>
						<span>{{ i.message }}<template v-if="i.hint"> &mdash; {{ i.hint }}</template></span>
					</button>
				</li>
				<li v-if="!issues.length" class="px-3 py-2 text-sm text-gray-500">No issues.</li>
			</ul>
		</div>
		</div>
	</section>
</template>