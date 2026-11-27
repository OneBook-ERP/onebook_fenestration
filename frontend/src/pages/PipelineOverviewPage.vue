<template>
	<div class="mx-auto max-w-6xl p-6">
		<div class="mb-5 flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="text-xl font-semibold text-gray-900">{{ meta.title }}</h1>
				<p class="mt-0.5 text-[13px] text-gray-500">{{ meta.subtitle }}</p>
			</div>
			<Button variant="subtle" label="Refresh" :loading="loading" @click="load" />
		</div>

		<PipelineStatGrid class="mb-5" :cards="statCards" />

		<!-- Filter Pills & Search -->
		<div class="mb-3 flex flex-wrap items-center gap-2">
			<div class="flex flex-wrap items-center gap-1.5">
				<button
					v-for="pill in filterPills"
					:key="pill.key"
					type="button"
					class="rounded-lg border px-2.5 py-1 text-[12px] font-medium transition-colors"
					:class="
						activeFilter === pill.key
							? 'border-gray-900 bg-gray-900 text-white'
							: 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900'
					"
					@click="setFilter(pill.key)"
				>
					{{ pill.label }}
					<span class="ml-1" :class="activeFilter === pill.key ? 'text-gray-300' : 'text-gray-400'">
						{{ pill.count }}
					</span>
				</button>
			</div>

			<FormControl
				v-model="search"
				type="search"
				:placeholder="meta.searchPlaceholder"
				class="ml-auto w-full sm:w-72"
			/>
		</div>

		<!-- Section List / Cards -->
		<div class="overflow-hidden rounded-xl border border-gray-200 bg-white">
			<p v-if="loading" class="px-4 py-8 text-center text-sm text-gray-500">Loading {{ meta.title.toLowerCase() }}…</p>
			<p v-else-if="!filteredRows.length" class="px-4 py-8 text-center text-sm text-gray-500">{{ meta.emptyText }}</p>

			<!-- QUOTES -->
			<ul v-else-if="section === 'quotes'" class="divide-y divide-gray-100">
				<li v-for="q in filteredRows" :key="q.name" class="transition-colors hover:bg-gray-50/50">
					<div class="grid grid-cols-1 items-center gap-2 px-4 py-3 md:grid-cols-[minmax(200px,1.8fr)_110px_110px_120px_220px]">
						<div class="min-w-0">
							<div class="flex items-center gap-2">
								<span class="font-semibold text-gray-900">{{ q.name }}</span>
								<span class="text-xs text-gray-400">·</span>
								<RouterLink :to="`/projects/${q.fen_project}?tab=quote`" class="truncate text-[13px] font-medium text-blue-600 hover:underline">
									{{ q.project_title }}
								</RouterLink>
							</div>
							<div class="mt-0.5 text-[12px] text-gray-500">
								{{ q.customer || 'No customer' }} · {{ q.design_count }} designs · {{ q.window_qty }} windows
							</div>
						</div>
						<div>
							<span class="inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium" :class="statusBadgeClass(q.status, q.docstatus)">
								{{ q.status }}
							</span>
						</div>
						<div class="text-[12px] text-gray-500">{{ q.transaction_date || '—' }}</div>
						<div class="text-right text-[13px] font-semibold tabular-nums text-gray-900">{{ formatMoney(q.amount) }}</div>
						<div class="flex justify-end gap-1.5">
							<Button
								size="sm"
								variant="subtle"
								:label="expandedQuote === q.name ? 'Hide' : 'View'"
								:loading="quoteDetailLoading === q.name"
								@click="toggleQuotePreview(q.name)"
							/>
							<Button size="sm" variant="subtle" label="PDF" :href="printPdfUrl('Quotation', q.name, 'Fenestration Quotation')" target="_blank" />
							<Button size="sm" variant="subtle" label="Edit in ERPNext" :href="deskDocUrl('Quotation', q.name)" target="_blank" />
						</div>
					</div>
					<div v-if="expandedQuote === q.name && quoteDetailsMap[q.name]" class="border-t border-gray-100 bg-gray-50/50 p-4">
						<QuotationDetailsCard :details="quoteDetailsMap[q.name]" />
					</div>
				</li>
			</ul>

			<!-- ORDERS -->
			<ul v-else-if="section === 'orders'" class="divide-y divide-gray-100">
				<li
					v-for="o in filteredRows"
					:key="o.name"
					class="grid grid-cols-1 items-center gap-2 px-4 py-3 hover:bg-gray-50/70 md:grid-cols-[minmax(200px,1.8fr)_120px_130px_120px_90px]"
				>
					<div class="min-w-0">
						<div class="flex items-center gap-2">
							<span class="font-semibold text-gray-900">{{ o.name }}</span>
							<span class="text-xs text-gray-400">·</span>
							<RouterLink :to="`/projects/${o.fen_project}?tab=order`" class="truncate text-[13px] font-medium text-blue-600 hover:underline">
								{{ o.project_title }}
							</RouterLink>
						</div>
						<div class="mt-0.5 text-[12px] text-gray-500">
							{{ o.customer || 'No customer' }} · {{ o.total_qty }} qty · Due {{ o.delivery_date || '—' }}
						</div>
					</div>
					<div>
						<span class="inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium" :class="statusBadgeClass(o.status, o.docstatus)">
							{{ o.status }}
						</span>
					</div>
					<div>
						<div class="flex justify-between text-[11px] text-gray-500">
							<span>Delivered</span><span class="tabular-nums">{{ o.per_delivered }}%</span>
						</div>
						<div class="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
							<div class="h-full rounded-full bg-blue-500" :style="{ width: `${Math.min(100, o.per_delivered)}%` }" />
						</div>
					</div>
					<div class="text-right text-[13px] font-semibold tabular-nums text-gray-900">{{ formatMoney(o.amount) }}</div>
					<div class="flex justify-end">
						<Button size="sm" variant="subtle" label="Open" :href="deskDocUrl('Sales Order', o.name)" target="_blank" />
					</div>
				</li>
			</ul>

			<!-- PRODUCTION -->
			<ul v-else-if="section === 'production'" class="divide-y divide-gray-100">
				<li
					v-for="p in filteredRows"
					:key="`${p.doctype}-${p.name}`"
					class="grid grid-cols-1 items-center gap-2 px-4 py-3 hover:bg-gray-50/70 md:grid-cols-[minmax(200px,1.8fr)_120px_140px_100px_90px]"
				>
					<div class="min-w-0">
						<div class="flex items-center gap-2">
							<span class="rounded bg-gray-100 px-1.5 py-0.5 text-[10.5px] font-medium text-gray-600">{{ p.doctype }}</span>
							<span class="font-semibold text-gray-900">{{ p.name }}</span>
							<RouterLink :to="`/projects/${p.fen_project}?tab=production`" class="truncate text-[13px] font-medium text-blue-600 hover:underline">
								{{ p.project_title }}
							</RouterLink>
						</div>
						<div class="mt-0.5 text-[12px] text-gray-500">{{ p.subtitle || '—' }}</div>
					</div>
					<div>
						<span class="inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium" :class="statusBadgeClass(p.status, p.docstatus)">
							{{ p.status }}
						</span>
					</div>
					<div>
						<div class="flex justify-between text-[11px] text-gray-500">
							<span>Progress</span><span class="tabular-nums">{{ p.progress_pct }}%</span>
						</div>
						<div class="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
							<div class="h-full rounded-full bg-emerald-500" :style="{ width: `${Math.min(100, p.progress_pct)}%` }" />
						</div>
					</div>
					<div class="text-[12px] text-gray-500">{{ p.date || '—' }}</div>
					<div class="flex justify-end">
						<Button size="sm" variant="subtle" label="Open" :href="deskDocUrl(p.doctype, p.name)" target="_blank" />
					</div>
				</li>
			</ul>

			<!-- INSTALL -->
			<ul v-else-if="section === 'install'" class="divide-y divide-gray-100">
				<li
					v-for="row in filteredRows"
					:key="`${row._kind}-${row.name}`"
					class="grid grid-cols-1 items-center gap-2 px-4 py-3 hover:bg-gray-50/70 md:grid-cols-[minmax(200px,1.8fr)_130px_140px_100px_110px]"
				>
					<div class="min-w-0">
						<div class="flex items-center gap-2">
							<span class="font-semibold text-gray-900">{{ row.name }}</span>
							<span class="text-xs text-gray-400">·</span>
							<RouterLink :to="`/projects/${row.fen_project}?tab=install`" class="truncate text-[13px] font-medium text-blue-600 hover:underline">
								{{ row.project_title }}
							</RouterLink>
						</div>
						<div class="mt-0.5 truncate text-[12px] text-gray-500">
							{{ row.customer || 'No customer' }} · {{ row.site_address || 'No site address' }}
						</div>
					</div>
					<div>
						<span
							class="inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium"
							:class="row._kind === 'pending' ? 'bg-amber-50 text-amber-700' : statusBadgeClass(row.status, row.docstatus)"
						>
							{{ row._kind === 'pending' ? 'Pending Dispatch' : row.status }}
						</span>
					</div>
					<div class="text-[12px] text-gray-600">{{ row.total_qty }} windows</div>
					<div class="text-[12px] text-gray-500">{{ row.date || '—' }}</div>
					<div class="flex justify-end">
						<Button
							size="sm"
							variant="subtle"
							:label="row._kind === 'pending' ? 'Dispatch' : 'Open'"
							:href="deskDocUrl(row._kind === 'pending' ? 'Sales Order' : 'Delivery Note', row.name)"
							target="_blank"
						/>
					</div>
				</li>
			</ul>

			<!-- REPORTS -->
			<ul v-else-if="section === 'reports'" class="divide-y divide-gray-100">
				<li
					v-for="r in filteredRows"
					:key="r.name"
					class="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5 hover:bg-gray-50/70"
				>
					<div class="min-w-0">
						<div class="flex items-center gap-2">
							<RouterLink :to="`/projects/${r.name}?tab=reports`" class="text-[14px] font-semibold text-gray-900 hover:text-blue-600 hover:underline">
								{{ r.project_title }}
							</RouterLink>
							<span class="inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium" :class="statusBadgeClass(r.stage)">
								{{ r.stage }}
							</span>
						</div>
						<div class="mt-0.5 text-[12px] text-gray-500">
							{{ r.customer || 'No customer' }} · {{ r.design_count }} designs · {{ r.window_qty }} windows · {{ r.total_area_sqft }} sq.ft · {{ formatMoney(r.total_value) }}
						</div>
					</div>
					<div class="flex flex-wrap items-center gap-1.5">
						<Button size="sm" variant="subtle" label="Elevation" :href="printPdfUrl('Fenestration Project', r.name, 'Fenestration Elevation')" target="_blank" />
						<Button size="sm" variant="subtle" label="Estimate" :href="printPdfUrl('Fenestration Project', r.name, 'Fenestration Estimate Confirmation')" target="_blank" />
						<Button size="sm" variant="subtle" label="Assembly" :href="printPdfUrl('Fenestration Project', r.name, 'Fenestration Assembly Summary')" target="_blank" />
						<Button v-if="r.quotation" size="sm" variant="subtle" label="Quotation" :href="printPdfUrl('Quotation', r.quotation, 'Fenestration Quotation')" target="_blank" />
					</div>
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, FormControl } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { getQuotationDetails, getWorkspacePipeline, type PipelineSection, type QuotationDetail } from '@/api'
import PipelineStatGrid from '@/components/workspace/PipelineStatGrid.vue'
import QuotationDetailsCard from '@/components/workspace/QuotationDetailsCard.vue'
import { buildStatCards, SECTION_META } from '@/components/workspace/pipelineConfig'
import { deskDocUrl, statusBadgeClass } from '@/components/workspace/statusStyle'
import { formatMoney } from '@/money'
import { printPdfUrl } from '@/print'

const props = defineProps<{ section: PipelineSection }>()
const route = useRoute()
const router = useRouter()

const loading = ref(true)
const search = ref('')
const items = ref<any[]>([])
const pendingOrders = ref<any[]>([])
const stats = ref<Record<string, number>>({})
const expandedQuote = ref<string | null>(null)
const quoteDetailLoading = ref<string | null>(null)
const quoteDetailsMap = ref<Record<string, QuotationDetail>>({})

async function toggleQuotePreview(name: string) {
	if (expandedQuote.value === name) {
		expandedQuote.value = null
		return
	}
	if (!quoteDetailsMap.value[name] && typeof getQuotationDetails === 'function') {
		quoteDetailLoading.value = name
		try {
			quoteDetailsMap.value[name] = await getQuotationDetails(name)
		} finally {
			quoteDetailLoading.value = null
		}
	}
	expandedQuote.value = name
}

const activeFilter = computed(() => String(route.query.filter || 'all'))
const meta = computed(() => SECTION_META[props.section])
const statCards = computed(() => buildStatCards(props.section, stats.value))

async function load() {
	loading.value = true
	try {
		const res = await getWorkspacePipeline(props.section)
		items.value = res.items ?? []
		pendingOrders.value = res.pending_orders ?? []
		stats.value = res.stats ?? {}
	} catch {
		items.value = []
		pendingOrders.value = []
		stats.value = {}
	} finally {
		loading.value = false
	}
}

watch(() => props.section, load, { immediate: true })

function setFilter(key: string) {
	router.replace({ query: { ...route.query, filter: key === 'all' ? undefined : key } })
}

const installRows = computed(() => [
	...items.value.map((d) => ({ ...d, _kind: 'delivery', date: d.posting_date })),
	...pendingOrders.value.map((o) => ({
		...o,
		_kind: 'pending',
		site_address: '',
		date: o.delivery_date || o.transaction_date,
	})),
])

const baseRows = computed(() => (props.section === 'install' ? installRows.value : items.value))

const filterPills = computed(() => {
	const rows = baseRows.value
	if (props.section === 'quotes') {
		return [
			{ key: 'all', label: 'All', count: rows.length },
			{ key: 'draft', label: 'Draft', count: rows.filter((r) => r.docstatus === 0).length },
			{ key: 'open', label: 'Submitted', count: rows.filter((r) => r.docstatus === 1 && r.status !== 'Ordered').length },
			{ key: 'ordered', label: 'Ordered', count: rows.filter((r) => r.status === 'Ordered').length },
		]
	}
	if (props.section === 'orders') {
		return [
			{ key: 'all', label: 'All', count: rows.length },
			{ key: 'to_deliver', label: 'To Deliver', count: rows.filter((r) => r.docstatus === 1 && r.per_delivered < 100).length },
			{ key: 'completed', label: 'Completed', count: rows.filter((r) => r.status === 'Completed').length },
		]
	}
	if (props.section === 'production') {
		return [
			{ key: 'all', label: 'All', count: rows.length },
			{ key: 'wo', label: 'Work Orders', count: rows.filter((r) => r.doctype === 'Work Order').length },
			{ key: 'mr', label: 'Material Requests', count: rows.filter((r) => r.doctype === 'Material Request').length },
			{ key: 'po', label: 'Purchase Orders', count: rows.filter((r) => r.doctype === 'Purchase Order').length },
		]
	}
	if (props.section === 'install') {
		return [
			{ key: 'all', label: 'All', count: rows.length },
			{ key: 'pending', label: 'Pending Dispatch', count: rows.filter((r) => r._kind === 'pending').length },
			{ key: 'delivery', label: 'Deliveries', count: rows.filter((r) => r._kind === 'delivery').length },
		]
	}
	return [
		{ key: 'all', label: 'All Projects', count: rows.length },
		{ key: 'quoted', label: 'Quoted / Ordered', count: rows.filter((r) => ['Quotation', 'Order', 'Production'].includes(r.stage)).length },
	]
})

const filteredRows = computed(() => {
	const f = activeFilter.value
	const q = search.value.trim().toLowerCase()
	return baseRows.value.filter((r) => {
		if (f !== 'all') {
			if (props.section === 'quotes') {
				if (f === 'draft' && r.docstatus !== 0) return false
				if (f === 'open' && !(r.docstatus === 1 && r.status !== 'Ordered')) return false
				if (f === 'ordered' && r.status !== 'Ordered') return false
			} else if (props.section === 'orders') {
				if (f === 'to_deliver' && !(r.docstatus === 1 && r.per_delivered < 100)) return false
				if (f === 'completed' && r.status !== 'Completed') return false
			} else if (props.section === 'production') {
				if (f === 'wo' && r.doctype !== 'Work Order') return false
				if (f === 'mr' && r.doctype !== 'Material Request') return false
				if (f === 'po' && r.doctype !== 'Purchase Order') return false
			} else if (props.section === 'install') {
				if (f === 'pending' && r._kind !== 'pending') return false
				if (f === 'delivery' && r._kind !== 'delivery') return false
			} else if (props.section === 'reports') {
				if (f === 'quoted' && !['Quotation', 'Order', 'Production'].includes(r.stage)) return false
			}
		}
		if (!q) return true
		return [r.name, r.project_title, r.customer, r.subtitle, r.status, r.stage].some((v) =>
			String(v ?? '').toLowerCase().includes(q),
		)
	})
})
</script>

