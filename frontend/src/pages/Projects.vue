<template>
	<div class="mx-auto max-w-6xl p-6">
		<!-- Page Header -->
		<div class="mb-5 flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="text-xl font-semibold text-gray-900">Projects</h1>
				<p class="mt-0.5 text-[13px] text-gray-500">
					Track fenestration projects, window quantities, and pipeline progression.
				</p>
			</div>
			<Button variant="solid" @click="showNew = true">New project</Button>
		</div>

		<!-- KPI Summary Cards -->
		<div class="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
			<div
				v-for="card in statCards"
				:key="card.label"
				data-slot="project-stat-card"
				class="flex items-start justify-between rounded-xl border border-gray-200 bg-white p-4"
			>
				<div class="min-w-0">
					<div class="text-[12px] font-medium text-gray-500">{{ card.label }}</div>
					<div class="mt-1 text-2xl font-semibold tracking-tight text-gray-900">
						{{ card.value }}
					</div>
					<div class="mt-0.5 text-[11px] text-gray-500">{{ card.sublabel }}</div>
				</div>
				<div class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
					<span :class="[card.icon, 'size-4']" />
				</div>
			</div>
		</div>

		<!-- Stage Filter Pills & Search -->
		<div class="mb-3 flex flex-wrap items-center gap-2">
			<div class="flex flex-wrap items-center gap-1.5">
				<button
					v-for="pill in stagePills"
					:key="pill.key"
					type="button"
					class="rounded-lg border px-2.5 py-1 text-[12px] font-medium transition-colors"
					:class="
						stageFilter === pill.key
							? 'border-gray-900 bg-gray-900 text-white'
							: 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900'
					"
					@click="stageFilter = pill.key"
				>
					{{ pill.label }}
					<span
						class="ml-1"
						:class="stageFilter === pill.key ? 'text-gray-300' : 'text-gray-400'"
					>
						{{ pill.count }}
					</span>
				</button>
			</div>

			<div class="ml-auto flex w-full flex-wrap items-center gap-2 sm:w-auto">
				<FormControl
					v-model="partnerFilter"
					type="select"
					class="w-44"
					:options="[
						{ label: 'All Customers', value: 'all' },
						{ label: 'Shared with Hilux', value: 'shared' },
						{ label: 'Dealers', value: 'Dealer' },
						{ label: 'Fabrication Partners', value: 'Fabrication Partner' },
						{ label: 'Own Clients', value: 'Own Client' },
					]"
				/>
				<FormControl
					v-model="search"
					type="search"
					placeholder="Search projects"
					class="w-full sm:w-64"
				/>
			</div>
		</div>

		<!-- Projects List Table -->
		<div class="overflow-hidden rounded-xl border border-gray-200 bg-white">
			<div
				class="hidden grid-cols-[minmax(220px,2fr)_110px_90px_110px_150px_120px] items-center gap-3 border-b border-gray-200 bg-gray-50/70 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500 md:grid"
			>
				<div>Project</div>
				<div>Stage</div>
				<div>Designs</div>
				<div>Windows</div>
				<div>Progress</div>
				<div class="text-right">Series</div>
			</div>

			<ul class="divide-y divide-gray-100">
				<li v-for="p in filtered" :key="p.name">
					<RouterLink
						:to="`/projects/${p.name}`"
						class="grid grid-cols-1 items-center gap-2 px-4 py-3 transition-colors hover:bg-gray-50/80 md:grid-cols-[minmax(220px,2fr)_110px_90px_110px_150px_120px] md:gap-3"
					>
						<!-- Project Title, Customer & ID -->
						<div class="min-w-0">
							<div class="flex flex-wrap items-center gap-1.5">
								<span class="truncate text-[13.5px] font-medium text-gray-900">
									{{ p.project_title || p.name }}
								</span>
								<Badge
									size="sm"
									variant="subtle"
									:theme="partnerBadgeTheme(p.fen_partner_type)"
									:label="p.fen_partner_type || 'Dealer'"
								/>
								<Badge
									v-if="p.fen_shared_with_hilux"
									size="sm"
									variant="subtle"
									theme="green"
									:label="p.fen_manufacturing_status || 'Shared with Hilux'"
								/>
							</div>
							<div class="mt-0.5 flex items-center gap-2 text-[12px] text-gray-500">
								<span class="truncate">{{ p.customer || 'No customer' }}</span>
								<span class="text-gray-300">·</span>
								<span class="shrink-0 font-mono text-[11px] text-gray-400">{{ p.name }}</span>
							</div>
						</div>

						<!-- Stage Badge -->
						<div>
							<span
								class="inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium"
								:class="stageBadgeClass(p.stage)"
							>
								{{ p.stage }}
							</span>
						</div>

						<!-- Designs Count -->
						<div class="text-[12.5px] text-gray-700">
							{{ p.design_count }} {{ p.design_count === 1 ? 'design' : 'designs' }}
						</div>

						<!-- Window Quantity & Area -->
						<div>
							<div class="text-[12.5px] font-medium text-gray-800">
								{{ p.window_qty }} {{ p.window_qty === 1 ? 'window' : 'windows' }}
							</div>
							<div v-if="p.total_area_sqft > 0" class="text-[11px] text-gray-400">
								{{ p.total_area_sqft }} sq.ft
							</div>
						</div>

						<!-- 4-Step Progression Bar -->
						<div class="flex items-center gap-1" :title="`Stage: ${p.stage}`">
							<span
								v-for="(step, idx) in progressSteps"
								:key="step"
								class="h-1.5 flex-1 rounded-full transition-colors"
								:class="idx < stageStepIndex(p.stage) ? stageBarClass(p.stage) : 'bg-gray-200'"
							/>
						</div>

						<!-- Series Version -->
						<div class="flex items-center justify-end gap-1.5 text-[12px] text-gray-500">
							<span class="truncate">{{ p.default_series_version || '—' }}</span>
							<span class="lucide-chevron-right size-3.5 shrink-0 text-gray-400" />
						</div>
					</RouterLink>
				</li>
				<li v-if="!filtered.length" class="px-4 py-8 text-center text-sm text-gray-500">
					No projects found.
				</li>
			</ul>
		</div>

		<!-- New Project Dialog -->
		<Dialog v-model="showNew" title="New project">
			<div class="space-y-3">
				<FormControl v-model="form.project_title" label="Title" />
				<Combobox
					v-model="form.customer"
					label="Customer (optional)"
					placeholder="Select a customer"
					:options="customerOptions"
				/>
				<FormControl
					v-model="form.fen_partner_type"
					type="select"
					label="Customer Type"
					:options="[
						{ label: 'Dealer (Design & Share to Hilux to Manufacture)', value: 'Dealer' },
						{ label: 'Fabrication Partner (Raw Aluminium Frames & Materials Only)', value: 'Fabrication Partner' },
						{ label: 'Own Client (Direct Homeowner / Apartment — Supply & Install)', value: 'Own Client' },
					]"
				/>
				<FormControl
					v-model="form.default_series_version"
					type="select"
					label="Default series version"
					:options="versionOptions"
				/>
				<Alert v-if="error" theme="red" :title="error" />
			</div>
			<template #actions>
				<Button variant="solid" :loading="saving" :disabled="!canCreate" @click="create">Create project</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, Combobox, Dialog, FormControl, useList } from 'frappe-ui'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import {
	createProject,
	getProjectOverview,
	type PartnerType,
	type ProjectOverview,
	type ProjectOverviewRow,
	type ProjectStage,
} from '@/api'

interface ProjectRow {
	name: string
	project_title: string
	customer: string
	default_series_version?: string | null
	modified: string
}

const STAGES: ProjectStage[] = ['Draft', 'Designing', 'Quotation', 'Order', 'Production']
const progressSteps = ['Designing', 'Quotation', 'Order', 'Production']

const router = useRouter()
const search = ref('')
const stageFilter = ref<'all' | ProjectStage>('all')
const partnerFilter = ref<'all' | 'shared' | PartnerType>('all')
const showNew = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive({
	project_title: '',
	customer: null as string | null,
	default_series_version: '',
	fen_partner_type: 'Dealer' as PartnerType,
})

const overview = ref<ProjectOverview | null>(null)

const projects = useList<ProjectRow>({
	doctype: 'Fenestration Project',
	fields: ['name', 'project_title', 'customer', 'default_series_version', 'modified'],
	orderBy: 'modified desc',
	limit: 100,
})
const customers = useList<{ name: string; fen_partner_type?: PartnerType }>({
	doctype: 'Customer',
	fields: ['name', 'fen_partner_type'],
	orderBy: 'name asc',
	limit: 500,
})
watch(
	() => form.customer,
	(custName) => {
		if (!custName) return
		const found = (customers.data ?? []).find((c) => c.name === custName)
		if (found?.fen_partner_type) {
			form.fen_partner_type = found.fen_partner_type
		}
	},
)
const versions = useList<{ name: string; series: string; creation: string }>({
	doctype: 'Series Version',
	fields: ['name', 'series', 'creation'],
	filters: { docstatus: 1 },
	limit: 100,
})

onMounted(async () => {
	try {
		if (typeof getProjectOverview === 'function') {
			overview.value = await getProjectOverview()
		}
	} catch {
		// Fall back to basic useList data if overview endpoint is unavailable
	}
})

const allProjects = computed<ProjectOverviewRow[]>(() => {
	if (overview.value?.projects) return overview.value.projects
	return (projects.data ?? []).map((p) => ({
		...p,
		design_count: 0,
		window_qty: 0,
		total_area_sqft: 0,
		stage: 'Draft' as ProjectStage,
	}))
})

const stats = computed(() => {
	if (overview.value?.stats) return overview.value.stats
	return {
		total_projects: allProjects.value.length,
		total_designs: 0,
		total_windows: 0,
		quoted_or_ordered: 0,
		in_production: 0,
	}
})

const statCards = computed(() => [
	{
		label: 'Total Projects',
		value: stats.value.total_projects,
		sublabel: `${allProjects.value.filter((p) => p.stage === 'Designing').length} in design`,
		icon: 'lucide-folder-kanban',
	},
	{
		label: 'Total Designs',
		value: stats.value.total_designs,
		sublabel: 'Active window elevations',
		icon: 'lucide-panels-top-left',
	},
	{
		label: 'Total Windows',
		value: stats.value.total_windows,
		sublabel: 'Total unit quantity',
		icon: 'lucide-layout-grid',
	},
	{
		label: 'Quoted & Orders',
		value: stats.value.quoted_or_ordered,
		sublabel: `${stats.value.in_production} in production`,
		icon: 'lucide-file-check',
	},
])

const stagePills = computed(() => [
	{ key: 'all' as const, label: 'All', count: allProjects.value.length },
	...STAGES.map((stage) => ({
		key: stage,
		label: stage,
		count: allProjects.value.filter((p) => p.stage === stage).length,
	})),
])

const filtered = computed(() => {
	const q = search.value.trim().toLowerCase()
	return allProjects.value.filter((p) => {
		if (stageFilter.value !== 'all' && p.stage !== stageFilter.value) return false
		if (partnerFilter.value === 'shared' && !p.fen_shared_with_hilux) return false
		if (
			(partnerFilter.value === 'Dealer' ||
				partnerFilter.value === 'Fabrication Partner' ||
				partnerFilter.value === 'Own Client') &&
			(p.fen_partner_type || 'Dealer') !== partnerFilter.value
		) {
			return false
		}
		if (!q) return true
		return [p.name, p.project_title, p.customer, p.stage, p.fen_partner_type, p.fen_manufacturing_status].some((v) =>
			(v ?? '').toLowerCase().includes(q),
		)
	})
})

const customerOptions = computed(() => (customers.data ?? []).map((c) => ({ label: c.name, value: c.name })))
const versionOptions = computed(() => {
	const newestFirst = [...(versions.data ?? [])].sort((a, b) => b.creation.localeCompare(a.creation))
	const latest = new Set<string>()
	return newestFirst.map((v) => {
		const isLatest = !latest.has(v.series)
		latest.add(v.series)
		return { label: isLatest ? `${v.name} (latest)` : v.name, value: v.name }
	})
})
const canCreate = computed(() => !!form.project_title.trim() && !!form.default_series_version)

function partnerBadgeTheme(partnerType?: PartnerType): 'gray' | 'blue' | 'violet' {
	if (partnerType === 'Fabrication Partner') return 'blue'
	if (partnerType === 'Own Client') return 'violet'
	return 'gray'
}

function stageStepIndex(stage: ProjectStage): number {
	const idx = progressSteps.indexOf(stage)
	return idx === -1 ? 0 : idx + 1
}

function stageBadgeClass(stage: ProjectStage): string {
	switch (stage) {
		case 'Designing':
			return 'bg-blue-50 text-blue-700'
		case 'Quotation':
			return 'bg-amber-50 text-amber-700'
		case 'Order':
			return 'bg-indigo-50 text-indigo-700'
		case 'Production':
			return 'bg-emerald-50 text-emerald-700'
		default:
			return 'bg-gray-100 text-gray-600'
	}
}

function stageBarClass(stage: ProjectStage): string {
	switch (stage) {
		case 'Designing':
			return 'bg-blue-500'
		case 'Quotation':
			return 'bg-amber-500'
		case 'Order':
			return 'bg-indigo-500'
		case 'Production':
			return 'bg-emerald-500'
		default:
			return 'bg-gray-300'
	}
}

async function create() {
	saving.value = true
	error.value = ''
	try {
		const name = await createProject({
			project_title: form.project_title.trim(),
			customer: form.customer?.trim() || undefined,
			default_series_version: form.default_series_version,
			fen_partner_type: form.fen_partner_type,
		})
		showNew.value = false
		router.push(`/projects/${name}`)
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not create the project.'
	} finally {
		saving.value = false
	}
}
</script>
