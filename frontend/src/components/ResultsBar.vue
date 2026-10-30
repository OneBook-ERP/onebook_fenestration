<script setup lang="ts">
import { Alert, Badge, Button, TabButtons } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import type { BomRow, Member } from '@/api'
import { useProfileNames } from '@/composables/profiles'
import { formatMoney } from '@/money'
import { useDesignerStore } from '@/stores/designer'

const COLLAPSED_KEY = 'fen.resultsCollapsed'

const store = useDesignerStore()
const profileNames = useProfileNames()
const tab = ref('Cut list')

function readCollapsed() {
	try {
		const stored = localStorage.getItem(COLLAPSED_KEY)
		if (stored !== null) return stored === '1'
	} catch {
		// Storage unavailable: fall through to the viewport default.
	}
	return typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 767px)').matches
}
const collapsed = ref(readCollapsed())
watch(collapsed, (v) => {
	try {
		localStorage.setItem(COLLAPSED_KEY, v ? '1' : '0')
	} catch {
		// Storage unavailable: the state just won't persist.
	}
})

const result = computed(() => store.result)
const issues = computed(() => result.value?.issues ?? [])
const errors = computed(() => issues.value.filter((i) => i.severity === 'error').length)
const warnings = computed(() => issues.value.filter((i) => i.severity === 'warn').length)

const shutters = computed(() => {
	const s = result.value?.shutter_kg
	if (s == null) return []
	return typeof s === 'number' ? [['', s] as [string, number]] : Object.entries(s)
})

/** Angles arrive as an array or a string like "[45, 45]". */
function formatAngles(a: Member['angles'] | number[]): string {
	let list: unknown = a
	if (typeof a === 'string') {
		try {
			list = JSON.parse(a)
		} catch {
			return a || '\u2014'
		}
	}
	return Array.isArray(list) && list.length ? list.map((x) => `${x}\u00b0`).join(' / ') : '\u2014'
}
const dash = (v: unknown) => (v == null || v === '' ? '\u2014' : String(v))

const cutList = computed(() => {
	const rows = new Map<string, { m: Member; qty: number }>()
	for (const m of result.value?.members ?? []) {
		const key = `${m.profile}|${m.length}|${formatAngles(m.angles)}|${m.position}|${m.panel}`
		const row = rows.get(key)
		if (row) row.qty += 1
		else rows.set(key, { m, qty: 1 })
	}
	return [...rows.entries()].map(([key, r]) => ({ key, ...r }))
})
const hardware = computed<BomRow[]>(() => (result.value?.bom ?? []).filter((b) => b.group !== 'Gasket'))
const gaskets = computed(() => {
	const rows = new Map<string, { item: string; name: string; metres: number }>()
	for (const b of (result.value?.bom ?? []).filter((r) => r.group === 'Gasket')) {
		const row = rows.get(b.item) ?? { item: b.item, name: b.name, metres: 0 }
		row.metres += (b.length ?? 0) / 1000
		rows.set(b.item, row)
	}
	return [...rows.values()]
})

const counts = computed<Record<string, number>>(() => ({
	'Cut list': cutList.value.length,
	Hardware: hardware.value.length,
	Gaskets: gaskets.value.length,
	Glass: result.value?.glass?.length ?? 0,
	Issues: issues.value.length,
}))
const tabOptions = computed(() =>
	['Cut list', 'Hardware', 'Gaskets', 'Glass', 'Pricing', 'Issues'].map((t) => ({
		value: t,
		label: t === 'Pricing' ? t : `${t} \u00b7 ${counts.value[t]}`,
	})),
)

const pricing = computed(() => result.value?.pricing)

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
				<template v-if="pricing">
					<span class="font-semibold">Live price {{ formatMoney(pricing.unit_price) }}</span>
					<span>{{ formatMoney(pricing.rate_per_sqft) }}/sq.ft</span>
					<span class="text-xs text-gray-500">From current rates; saved designs keep their priced value until repriced.</span>
				</template>
				<Badge :theme="errors ? 'red' : 'green'" :label="`${errors} errors`" />
				<Badge v-if="warnings" theme="amber" :label="`${warnings} warnings`" />
				<Button
					class="ml-auto min-h-9"
					:label="collapsed ? 'Show results' : 'Hide results'"
					:aria-expanded="!collapsed"
					@click="collapsed = !collapsed"
				/>
			</div>
			<div v-else-if="!store.error" class="flex items-center px-4 py-2 text-sm text-gray-500">
				<span>Computing...</span>
				<Button
					class="ml-auto min-h-9"
					:label="collapsed ? 'Show results' : 'Hide results'"
					:aria-expanded="!collapsed"
					@click="collapsed = !collapsed"
				/>
			</div>

			<div v-if="!collapsed" class="px-2 py-1">
				<TabButtons v-model="tab" :options="tabOptions" />
			</div>

		<div v-if="!collapsed" class="max-h-48 overflow-auto">
			<table v-if="tab === 'Cut list'" class="w-full">
				<thead><tr><th :class="th">Profile</th><th :class="th">Code</th><th :class="th">Length (mm)</th><th :class="th">Angles</th><th :class="th">Qty</th><th :class="th">Position</th><th :class="th">Panel</th></tr></thead>
				<tbody>
					<tr v-for="r in cutList" :key="r.key">
						<td :class="td">{{ dash(profileNames[r.m.profile]) }}</td><td :class="td">{{ r.m.profile }}</td><td :class="td">{{ Number(r.m.length).toFixed(1) }}</td><td :class="td">{{ formatAngles(r.m.angles) }}</td><td :class="td">{{ r.qty }}</td><td :class="td">{{ dash(r.m.position) }}</td><td :class="td">{{ dash(r.m.panel) }}</td>
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
			<table v-else-if="tab === 'Gaskets'" class="w-full">
				<thead><tr><th :class="th">Item</th><th :class="th">Name</th><th :class="th">Length (m)</th></tr></thead>
				<tbody>
					<tr v-for="g in gaskets" :key="g.item">
						<td :class="td">{{ g.item }}</td><td :class="td">{{ g.name }}</td><td :class="td">{{ g.metres.toFixed(3) }}</td>
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
			<table v-else-if="tab === 'Pricing'" class="w-full">
				<thead><tr><th :class="th">Cost head</th><th :class="[th, 'text-right']">Amount</th></tr></thead>
				<tbody>
					<tr
						v-for="l in pricing?.lines ?? []"
						:key="l.key"
						:class="{ 'italic text-gray-500': l.include_in_total === false }"
						:title="l.include_in_total === false ? 'Not added to the total' : undefined"
					>
						<td :class="td">{{ l.label }}</td><td :class="[td, 'text-right']">{{ formatMoney(l.amount) }}</td>
					</tr>
					<tr v-if="pricing" class="border-t font-bold">
						<td :class="td">Total</td><td :class="[td, 'text-right']">{{ formatMoney(pricing.unit_price) }}</td>
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
						<span :class="i.severity === 'error' ? 'text-red-700' : 'text-amber-700'">{{ i.severity }}</span>
						<span>{{ i.message }}<template v-if="i.hint"> &mdash; {{ i.hint }}</template></span>
					</button>
				</li>
				<li v-if="!issues.length" class="px-3 py-2 text-sm text-gray-500">No issues.</li>
			</ul>
		</div>
		</div>
	</section>
</template>