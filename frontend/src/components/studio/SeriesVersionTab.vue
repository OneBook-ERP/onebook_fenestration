<template>
	<div>
		<div class="mb-4 flex flex-wrap gap-1.5 border-b border-outline-gray-2 pb-2" role="group" aria-label="Filter versions by series">
			<button
				v-for="s in seriesTabs"
				:key="s.key"
				type="button"
				:data-testid="`version-series-${s.key}`"
				class="border-b-2 px-3 py-1.5 text-xs font-semibold transition-colors"
				:class="
					selectedSeries === s.key
						? 'border-ink-gray-9 text-ink-gray-9'
						: 'border-transparent text-ink-gray-6 hover:text-ink-gray-8'
				"
				@click="selectedSeries = s.key"
			>
				{{ s.label }}
			</button>
		</div>

		<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
			<div class="flex flex-wrap items-center gap-2" role="group" aria-label="Filter versions by status">
				<button
					v-for="st in statusFilters"
					:key="st.id"
					type="button"
					class="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors"
					:class="
						selectedStatus === st.id
							? 'border-ink-gray-9 bg-ink-gray-9 text-surface-white'
							: 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:bg-surface-gray-1'
					"
					@click="selectedStatus = st.id"
				>
					{{ st.label }}
				</button>
			</div>

			<div class="flex items-center gap-3">
				<FormControl
					v-model="search"
					type="search"
					placeholder="Search versions..."
					aria-label="Search versions"
					class="w-60"
				/>
				<Button
					variant="solid"
					data-testid="new-version-btn"
					:route="newVersionRoute"
				>
					New series version
				</Button>
			</div>
		</div>

		<div class="overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white">
			<div
				class="grid grid-cols-[150px_130px_170px_1fr_140px] items-center gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
			>
				<span>Version</span>
				<span>Series</span>
				<span>Status</span>
				<span>Version Note</span>
				<span class="text-right">Actions</span>
			</div>

			<ul class="divide-y divide-outline-gray-1">
				<li
					v-for="v in filtered"
					:key="v.name"
					data-testid="version-row"
					class="grid grid-cols-[150px_130px_170px_1fr_140px] items-center gap-4 px-4 py-3 text-sm transition-colors hover:bg-surface-gray-1"
				>
					<router-link
						:to="`/series-studio/versions/${encodeURIComponent(v.name)}`"
						class="font-semibold text-ink-gray-9 hover:underline"
					>
						{{ v.name }}
					</router-link>
					<span class="font-medium text-ink-gray-7">{{ v.series }}</span>
					<div class="flex items-center gap-1.5">
						<Badge :theme="statusBadge(v).theme" :label="statusBadge(v).label" />
						<Badge v-if="isActivePublished(v)" theme="blue" label="Active" />
					</div>
					<span class="truncate text-ink-gray-6">{{ v.version_note || '—' }}</span>
					<div class="flex items-center justify-end gap-2">
						<Button
							variant="outline"
							size="sm"
							:label="v.docstatus === 0 ? 'Edit rules' : 'Inspect rules'"
							:data-testid="`inspect-version-${v.name}`"
							:route="`/series-studio/versions/${encodeURIComponent(v.name)}`"
						/>
					</div>
				</li>

				<li
					v-if="!filtered.length"
					class="px-4 py-8 text-center text-sm text-ink-gray-5"
				>
					No series versions found.
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, FormControl } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import type { ProfileSeriesRow, SeriesVersionRow } from '@/studio/api'

const props = defineProps<{
	versions: SeriesVersionRow[]
	seriesList: ProfileSeriesRow[]
	initialSeries?: string
}>()

defineEmits<{
	(e: 'reload'): void
}>()

const selectedSeries = ref<string>(props.initialSeries || 'ALL')
const selectedStatus = ref<'ALL' | 'published' | 'draft'>('ALL')
const search = ref('')

watch(
	() => props.initialSeries,
	(val) => {
		if (val) selectedSeries.value = val
	},
)

const newVersionRoute = computed(() =>
	selectedSeries.value !== 'ALL'
		? `/series-studio/versions/new?series=${encodeURIComponent(selectedSeries.value)}`
		: '/series-studio/versions/new',
)

const statusFilters = [
	{ id: 'ALL' as const, label: 'All statuses' },
	{ id: 'published' as const, label: 'Published' },
	{ id: 'draft' as const, label: 'Draft' },
]

const seriesTabs = computed(() => {
	const counts = new Map<string, number>()
	for (const v of props.versions) {
		counts.set(v.series, (counts.get(v.series) || 0) + 1)
	}
	const keys = new Set<string>([
		...props.seriesList.map((s) => s.series_code || s.name),
		...counts.keys(),
	])
	return [
		{ key: 'ALL', label: `All Versions · ${props.versions.length}` },
		...Array.from(keys).map((k) => ({ key: k, label: `${k} · ${counts.get(k) || 0}` })),
	]
})

const publishedBySeries = computed(() => {
	const map = new Map<string, string>()
	for (const s of props.seriesList) {
		if (s.published_version) map.set(s.series_code || s.name, s.published_version)
	}
	return map
})

function isActivePublished(v: SeriesVersionRow): boolean {
	return publishedBySeries.value.get(v.series) === v.name
}

function statusBadge(v: SeriesVersionRow): { label: string; theme: 'green' | 'amber' | 'red' } {
	if (v.docstatus === 1) return { label: 'Published', theme: 'green' }
	if (v.docstatus === 2) return { label: 'Cancelled', theme: 'red' }
	return { label: 'Draft', theme: 'amber' }
}

const filtered = computed(() => {
	const q = search.value.trim().toLowerCase()
	return props.versions.filter((v) => {
		if (selectedSeries.value !== 'ALL' && v.series !== selectedSeries.value) return false
		if (selectedStatus.value === 'published' && v.docstatus !== 1) return false
		if (selectedStatus.value === 'draft' && v.docstatus !== 0) return false
		if (q) {
			const hay = `${v.name} ${v.series} ${v.version_note || ''}`.toLowerCase()
			if (!hay.includes(q)) return false
		}
		return true
	})
})
</script>
