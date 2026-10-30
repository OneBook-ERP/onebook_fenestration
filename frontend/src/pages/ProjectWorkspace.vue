<template>
	<div class="p-6">
		<header data-testid="project-header" class="mb-4">
			<nav aria-label="Breadcrumb" class="mb-1 text-sm text-ink-gray-5">
				<router-link to="/projects" data-testid="breadcrumb-projects" class="hover:text-ink-gray-8">Projects</router-link>
				<span aria-hidden="true"> / </span>
				<span>{{ project }}</span>
			</nav>
			<div class="flex flex-wrap items-center gap-3">
				<h1 class="text-xl font-semibold">{{ info?.project_title || project }}</h1>
				<Badge :theme="badge.theme" :label="badge.label" data-testid="quote-badge" />
				<span v-if="quote?.quotation" class="text-sm text-ink-gray-5">{{ quote.quotation }}</span>
			</div>
			<dl class="mt-3 grid grid-cols-2 gap-3 sm:flex sm:flex-wrap">
				<div v-for="k in kpis" :key="k.id" :data-testid="`kpi-${k.id}`" class="rounded border p-3 sm:min-w-32 sm:flex-1">
					<dt class="text-xs text-ink-gray-5">{{ k.label }}</dt>
					<dd class="text-lg font-semibold">{{ k.value }}</dd>
				</div>
			</dl>
		</header>

		<div role="tablist" aria-label="Project sections" class="mb-4 flex gap-1 overflow-x-auto border-b">
			<button
				v-for="t in tabs"
				:id="`tab-${t.id}`"
				:key="t.id"
				type="button"
				role="tab"
				class="min-h-9 shrink-0 whitespace-nowrap border-b-2 px-3 text-sm"
				:class="tabClass(t)"
				:aria-selected="activeTab === t.id"
				:aria-disabled="t.disabled ? 'true' : undefined"
				:aria-describedby="t.disabled ? 'tab-soon-hint' : undefined"
				:title="t.disabled ? 'Coming soon' : undefined"
				@click="selectTab(t)"
			>{{ t.label }}</button>
		</div>
		<span id="tab-soon-hint" class="sr-only">Coming soon</span>

		<div role="tabpanel" :aria-labelledby="`tab-${activeTab}`">
			<QuotePanel v-if="activeTab === 'quote'" :project="project" :info="info" @changed="onQuoteChanged" @repriced="onRepriced" />

			<template v-if="activeTab === 'designs'">
				<div class="mb-4 flex flex-wrap items-center gap-4">
					<FormControl v-model="search" class="ml-auto w-56" type="text" placeholder="Search designs" aria-label="Search designs" />
					<Dropdown :options="templateOptions">
						<Button class="min-h-9" variant="solid" data-testid="new-design" :disabled="!info?.default_series_version">New design</Button>
					</Dropdown>
				</div>

				<p v-if="designsLoading" class="text-sm text-ink-gray-5">Loading designs…</p>
				<p v-else-if="!designs.length" class="text-sm text-ink-gray-5">No designs yet.</p>
				<p v-else-if="!shown.length" class="text-sm text-ink-gray-5">No designs match.</p>
				<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
					<article v-for="d in shown" :key="d.name" data-testid="design-card" class="rounded border p-3">
						<div class="mb-2 flex h-40 items-center justify-center rounded bg-surface-gray-1">
							<img v-if="d.design_svg" :src="thumb(d.design_svg)" :alt="`Elevation of ${d.design_ref}`" class="max-h-full max-w-full" />
							<span v-else class="text-xs text-ink-gray-5">No preview</span>
						</div>
						<div class="flex items-center gap-2">
							<span class="font-medium">{{ d.design_ref }} · {{ typologyOf(d) }}</span>
							<span class="text-sm text-ink-gray-5">× {{ d.qty }}</span>
							<Badge v-if="d.error_count" class="ml-auto" theme="red" :label="`${d.error_count} errors`" />
							<Badge v-else-if="d.warning_count" class="ml-auto" theme="amber" :label="`${d.warning_count} warnings`" />
							<Badge v-else class="ml-auto" theme="green" label="OK" />
						</div>
						<p class="text-sm text-ink-gray-5">{{ d.series_version }} · {{ glassOf(d) }}<template v-if="d.location"> · {{ d.location }}</template></p>
						<p class="flex items-center gap-1.5 text-sm text-ink-gray-5">
							<span data-testid="finish-swatch" class="inline-block size-3 rounded-full border" :style="{ backgroundColor: finishColor(d.finish) }" aria-hidden="true"></span>
							{{ finishName(d.finish) }}
						</p>
						<p class="text-sm text-ink-gray-5">{{ fixed(d.area_sqft, 3) }} sq.ft · {{ fixed(d.window_kg, 1) }} kg</p>
						<p class="text-sm text-ink-gray-5">{{ money(d.unit_price) }} each</p>
						<p class="text-sm font-medium">Line {{ money(d.line_total) }}</p>
						<p v-if="pricedOn(d)" class="text-sm text-ink-gray-5">Priced {{ pricedOn(d) }}</p>
						<Button
							class="mt-2 min-h-9"
							variant="subtle"
							label="Edit design"
							data-testid="edit-design"
							:route="`/projects/${project}/designs/${d.name}`"
						/>
						<Button
							class="ml-2 mt-2 min-h-9"
							variant="subtle"
							label="Duplicate"
							data-testid="duplicate-design"
							:disabled="duplicating"
							@click="duplicate(d.name)"
						/>
					</article>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, Dropdown, FormControl, toast, useList } from 'frappe-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { copyDesign, quoteStatus, type QuoteStatus } from '@/api'
import QuotePanel from '@/components/QuotePanel.vue'
import type { Design, DesignNode } from '@/design/types'
import { typology } from '@/design/typology'
import { TEMPLATES } from '@/design/templates'
import { formatMoney } from '@/money'

interface DesignRow {
	name: string
	design_ref: string
	qty: number
	series_version: string
	area_sqft: number
	window_kg: number
	error_count: number
	warning_count: number
	design_svg: string
	design_name?: string
	finish?: string | null
	design_json?: Design | string | null
	location: string
	unit_price: number | null
	line_total: number | null
	pricing_json?: string | { priced_on?: string } | null
}
interface ProjectInfo {
	name: string
	project_title: string
	default_series_version: string
	customer?: string | null
	transport_charges?: number | null
	quotation?: string | null
}

const props = defineProps<{ project: string }>()
const router = useRouter()
const route = useRoute()

const projectList = useList<ProjectInfo>({
	doctype: 'Fenestration Project',
	fields: ['name', 'project_title', 'default_series_version', 'customer', 'transport_charges', 'quotation'],
	filters: { name: props.project },
	limit: 1,
})
const designList = useList<DesignRow>({
	doctype: 'Window Design',
	fields: [
		'name', 'design_ref', 'qty', 'series_version', 'area_sqft', 'window_kg',
		'error_count', 'warning_count', 'design_svg', 'design_name', 'finish', 'design_json', 'location', 'unit_price', 'line_total', 'pricing_json',
	],
	filters: { project: props.project },
	orderBy: 'design_ref asc',
	limit: 200,
})

const glassList = useList<{ name: string; glass_name?: string }>({
	doctype: 'Fenestration Glass',
	fields: ['name', 'glass_name'],
	limit: 100,
})

const finishList = useList<{ name: string; finish_name?: string; color?: string }>({
	doctype: 'Profile Finish',
	fields: ['name', 'finish_name', 'color'],
	limit: 200,
})

const quote = ref<QuoteStatus | null>(null)
const quoteError = ref(false)
async function loadQuote() {
	try {
		quote.value = await quoteStatus(props.project)
		quoteError.value = false
	} catch {
		quote.value = null
		quoteError.value = true
	}
}
onMounted(loadQuote)
function onQuoteChanged() {
	projectList.reload()
	loadQuote()
}
function onRepriced() {
	designList.reload()
	loadQuote()
}

const badge = computed<{ label: string; theme: 'gray' | 'blue' | 'amber' | 'red' }>(() => {
	const q = quote.value
	if (quoteError.value) return { label: 'Status unavailable', theme: 'gray' }
	if (!q?.quotation) return { label: 'Not quoted', theme: 'gray' }
	if (q.is_stale) return { label: 'Out of date', theme: 'red' }
	if (q.docstatus === 0) return { label: 'Draft quote', theme: 'amber' }
	return { label: q.status || '—', theme: 'blue' }
})
const designsLoading = computed(() => designList.data == null)
const kpis = computed(() => [
	{ id: 'windows', label: 'Windows', value: String(totals.value.windows) },
	{ id: 'area', label: 'Area (sq.ft)', value: totals.value.area.toFixed(3) },
	{ id: 'weight', label: 'Weight (kg)', value: totals.value.weight.toFixed(1) },
	{ id: 'value', label: 'Basic value', value: formatMoney(totals.value.value) },
	{ id: 'grand', label: 'Grand total incl. GST', value: quote.value?.quotation && quote.value.rounded_total != null ? formatMoney(quote.value.rounded_total) : '—' },
].map((k) => (designsLoading.value ? { ...k, value: '—' } : k)))

const TAB_IDS = ['designs', 'quote'] as const
const activeTab = computed(() => {
	const t = String(route.query.tab ?? '')
	return (TAB_IDS as readonly string[]).includes(t) ? t : 'designs'
})
const tabs = computed(() => [
	{ id: 'designs', label: `Designs · ${designs.value.length}`, disabled: false },
	{ id: 'quote', label: 'Quote', disabled: false },
	{ id: 'order', label: 'Order', disabled: true },
	{ id: 'production', label: 'Production', disabled: true },
	{ id: 'install', label: 'Install', disabled: true },
	{ id: 'reports', label: 'Reports', disabled: true },
])
type Tab = { id: string; label: string; disabled: boolean }
function selectTab(t: Tab) {
	if (t.disabled) return
	router.replace({ query: { ...route.query, tab: t.id === 'designs' ? undefined : t.id } })
}
function tabClass(t: Tab) {
	if (t.disabled) return 'cursor-not-allowed border-transparent text-ink-gray-4'
	return activeTab.value === t.id ? 'border-ink-gray-9 font-medium' : 'border-transparent text-ink-gray-6'
}
function fixed(n: number | null | undefined, dp: number): string {
	return n == null ? '—' : Number(n).toFixed(dp)
}

function parseTree(d: DesignRow): DesignNode | null {
	try {
		const doc = typeof d.design_json === 'string' ? JSON.parse(d.design_json || 'null') : d.design_json
		return doc?.root ?? null
	} catch {
		return null
	}
}
function leafGlass(node: DesignNode): string[] {
	return node.type === 'split' ? node.children.flatMap(leafGlass) : [node.glass]
}
function typologyOf(d: DesignRow): string {
	const root = parseTree(d)
	return root ? typology(root) : '—'
}
const glasses = computed(() => new Map((glassList.data ?? []).map((g) => [g.name, g.glass_name])))
function glassName(code: string): string {
	return glasses.value.get(code) || code
}
function money(n: number | null | undefined): string {
	return n == null ? '—' : formatMoney(n)
}
function glassOf(d: DesignRow): string {
	const root = parseTree(d)
	const names = root ? [...new Set(leafGlass(root).filter(Boolean).map(glassName))] : []
	return names.length ? names.join(', ') : '—'
}
const finishes = computed(() => new Map((finishList.data ?? []).map((f) => [f.name, f])))
function finishName(code?: string | null): string {
	return code ? finishes.value.get(code)?.finish_name || code : '—'
}
function finishColor(code?: string | null): string {
	return (code && finishes.value.get(code)?.color) || '#9ca3af'
}

const info = computed(() => projectList.data?.[0])
const designs = computed(() => designList.data ?? [])
const search = ref('')
const shown = computed(() => {
	const q = search.value.trim().toLowerCase()
	if (!q) return designs.value
	return designs.value.filter((d) =>
		[d.design_ref, d.design_name, d.location].some((v) => (v ?? '').toLowerCase().includes(q)),
	)
})
const totals = computed(() => {
	let windows = 0, area = 0, weight = 0, value = 0
	for (const d of designs.value) {
		windows += d.qty
		area += d.area_sqft * d.qty
		weight += d.window_kg * d.qty
		value += d.line_total ?? 0
	}
	return { windows, area, weight, value }
})

const dateFormat = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

function pricedOn(d: DesignRow): string {
	try {
		const pricing = typeof d.pricing_json === 'string' ? JSON.parse(d.pricing_json || '{}') : d.pricing_json
		return pricing?.priced_on ? dateFormat.format(new Date(pricing.priced_on)) : ''
	} catch {
		return ''
	}
}

function thumb(svg: string) {
	return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg)
}

const templateOptions = TEMPLATES.map((t) => ({ label: t.label, onClick: () => newDesign(t.id) }))

function newDesign(template: string) {
	router.push({
		path: `/projects/${props.project}/designs/new`,
		query: { series_version: info.value?.default_series_version, template },
	})
}

const duplicating = ref(false)
async function duplicate(name: string) {
	if (duplicating.value) return
	duplicating.value = true
	let copy: string
	try {
		copy = await copyDesign(name)
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Copy failed')
		return
	} finally {
		duplicating.value = false
	}
	await router.push(`/projects/${props.project}/designs/${copy}`).catch(() => {
		toast.error(`Copied as ${copy}, but could not open it`)
	})
}
</script>
