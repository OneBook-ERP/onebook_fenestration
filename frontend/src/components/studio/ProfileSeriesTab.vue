<template>
	<div>
		<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
			<div class="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by system type">
				<button
					v-for="st in systemTypes"
					:key="st"
					type="button"
					:data-testid="`filter-system-${st.toLowerCase()}`"
					class="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors"
					:class="
						selectedType === st
							? 'border-ink-gray-9 bg-ink-gray-9 text-surface-white'
							: 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:bg-surface-gray-1'
					"
					@click="selectedType = st"
				>
					{{ st === 'ALL' ? `All systems · ${seriesList.length}` : st }}
				</button>
			</div>

			<div class="flex items-center gap-3">
				<FormControl
					v-model="search"
					type="search"
					placeholder="Search profile series..."
					aria-label="Search profile series"
					class="w-60"
				/>
				<Button
					variant="solid"
					data-testid="new-series-btn"
					route="/series-studio/series/new"
				>
					New profile series
				</Button>
			</div>
		</div>

		<div class="overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white">
			<div
				class="grid grid-cols-[120px_1fr_130px_160px_110px_210px] items-center gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
			>
				<span>Series Code</span>
				<span>Series Title</span>
				<span>System Type</span>
				<span>Published Version</span>
				<span>Profiles</span>
				<span class="text-right">Actions</span>
			</div>

			<ul class="divide-y divide-outline-gray-1">
				<li
					v-for="row in filtered"
					:key="row.name"
					data-testid="series-row"
					class="grid grid-cols-[120px_1fr_130px_160px_110px_210px] items-center gap-4 px-4 py-3 text-sm transition-colors hover:bg-surface-gray-1"
				>
					<router-link
						:to="`/series-studio/series/${encodeURIComponent(row.name)}`"
						class="font-semibold text-ink-gray-9 hover:underline"
					>
						{{ row.series_code || row.name }}
					</router-link>
					<router-link
						:to="`/series-studio/series/${encodeURIComponent(row.name)}`"
						class="truncate font-medium text-ink-gray-8 hover:underline"
					>
						{{ row.series_title }}
					</router-link>
					<div>
						<Badge :theme="systemTheme(row.system_type)" :label="row.system_type || 'Casement'" />
					</div>
					<div>
						<Badge
							v-if="row.published_version"
							theme="green"
							:label="row.published_version"
						/>
						<Badge v-else theme="gray" label="Unpublished" />
					</div>
					<span class="text-xs font-medium text-ink-gray-6">
						{{ profileCount(row.series_code || row.name) }} profiles
					</span>
					<div class="flex items-center justify-end gap-1.5">
						<Button
							variant="subtle"
							size="sm"
							label="Profiles"
							:data-testid="`view-profiles-${row.name}`"
							@click="$emit('select-series-profiles', row.series_code || row.name)"
						/>
						<Button
							variant="subtle"
							size="sm"
							label="Versions"
							:data-testid="`view-versions-${row.name}`"
							@click="$emit('select-series-versions', row.series_code || row.name)"
						/>
						<Button
							variant="outline"
							size="sm"
							label="Edit"
							:data-testid="`edit-series-${row.name}`"
							:route="`/series-studio/series/${encodeURIComponent(row.name)}`"
						/>
					</div>
				</li>

				<li
					v-if="!filtered.length"
					class="px-4 py-8 text-center text-sm text-ink-gray-5"
				>
					No profile series found.
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, FormControl } from 'frappe-ui'
import { computed, ref } from 'vue'
import type { FenestrationProfileRow, ProfileSeriesRow } from '@/studio/api'

const props = defineProps<{
	seriesList: ProfileSeriesRow[]
	profiles: FenestrationProfileRow[]
}>()

defineEmits<{
	(e: 'reload'): void
	(e: 'select-series-profiles', seriesCode: string): void
	(e: 'select-series-versions', seriesCode: string): void
}>()

const systemTypes = ['ALL', 'Casement', 'Sliding', 'Door'] as const
const selectedType = ref<string>('ALL')
const search = ref('')

const filtered = computed(() => {
	const q = search.value.trim().toLowerCase()
	return props.seriesList.filter((row) => {
		if (selectedType.value !== 'ALL' && row.system_type !== selectedType.value) return false
		if (q) {
			const hay = `${row.series_code || ''} ${row.series_title || ''} ${row.system_type || ''} ${row.published_version || ''}`.toLowerCase()
			if (!hay.includes(q)) return false
		}
		return true
	})
})

const countsBySeries = computed(() => {
	const map = new Map<string, number>()
	for (const p of props.profiles) {
		if (!p.series) continue
		map.set(p.series, (map.get(p.series) || 0) + 1)
	}
	return map
})

function profileCount(seriesCode: string): number {
	return countsBySeries.value.get(seriesCode) || 0
}

function systemTheme(systemType?: string): 'blue' | 'amber' | 'gray' {
	if (systemType === 'Casement') return 'blue'
	if (systemType === 'Sliding') return 'amber'
	return 'gray'
}
</script>
