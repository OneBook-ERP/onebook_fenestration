<template>
	<div class="p-6">
		<div class="mb-4 flex flex-wrap items-center gap-4">
			<div>
				<h1 class="text-xl font-semibold">{{ info?.project_title || project }}</h1>
				<p class="text-sm text-ink-gray-5">
					{{ totals.windows }} windows · {{ totals.area.toFixed(3) }} sq.ft · {{ totals.weight.toFixed(3) }} kg
				</p>
			</div>
			<Button class="ml-auto" variant="solid" data-testid="new-design" :disabled="!info?.default_series_version" @click="newDesign">
				New design
			</Button>
		</div>

		<p v-if="!designs.length" class="text-sm text-ink-gray-5">No designs yet.</p>
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			<article v-for="d in designs" :key="d.name" data-testid="design-card" class="rounded border p-3">
				<div class="mb-2 flex h-40 items-center justify-center rounded bg-surface-gray-1">
					<img v-if="d.design_svg" :src="thumb(d.design_svg)" :alt="`Elevation of ${d.design_ref}`" class="max-h-full max-w-full" />
					<span v-else class="text-xs text-ink-gray-5">No preview</span>
				</div>
				<div class="flex items-center gap-2">
					<span class="font-medium">{{ d.design_ref }} × {{ d.qty }}</span>
					<Badge v-if="d.error_count" theme="red" :label="`${d.error_count} errors`" />
					<Badge v-else-if="d.warning_count" theme="orange" :label="`${d.warning_count} warnings`" />
				</div>
				<p class="text-sm text-ink-gray-5">{{ d.series_version }} · {{ d.area_sqft }} sq.ft<template v-if="d.location"> · {{ d.location }}</template></p>
				<RouterLink :to="`/projects/${project}/designs/${d.name}`" class="mt-2 inline-block text-sm text-ink-blue-3">Edit design</RouterLink>
			</article>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, useList } from 'frappe-ui'
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

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
	location: string
}
interface ProjectInfo {
	name: string
	project_title: string
	default_series_version: string
}

const props = defineProps<{ project: string }>()
const router = useRouter()

const projectList = useList<ProjectInfo>({
	doctype: 'Fenestration Project',
	fields: ['name', 'project_title', 'default_series_version'],
	filters: { name: props.project },
	limit: 1,
})
const designList = useList<DesignRow>({
	doctype: 'Window Design',
	fields: [
		'name', 'design_ref', 'qty', 'series_version', 'area_sqft', 'window_kg',
		'error_count', 'warning_count', 'design_svg', 'location',
	],
	filters: { project: props.project },
	orderBy: 'design_ref asc',
	limit: 200,
})

const info = computed(() => projectList.data?.[0])
const designs = computed(() => designList.data ?? [])
const totals = computed(() => {
	let windows = 0, area = 0, weight = 0
	for (const d of designs.value) {
		windows += d.qty
		area += d.area_sqft * d.qty
		weight += d.window_kg * d.qty
	}
	return { windows, area, weight }
})

function thumb(svg: string) {
	return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg)
}

function newDesign() {
	router.push({ path: `/projects/${props.project}/designs/new`, query: { series_version: info.value?.default_series_version } })
}
</script>
