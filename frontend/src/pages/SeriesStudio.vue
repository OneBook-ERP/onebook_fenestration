<template>
	<div class="mx-auto max-w-7xl p-6">
		<header data-testid="studio-header" class="mb-5">
			<div class="flex flex-wrap items-center justify-between gap-3">
				<div>
					<h1 class="text-xl font-semibold text-ink-gray-9">{{ currentSection.title }}</h1>
					<p class="mt-0.5 text-sm text-ink-gray-5">
						{{ currentSection.description }}
					</p>
				</div>
			</div>
		</header>

		<div>
			<ProfileSeriesTab
				v-if="activeTab === 'series'"
				:series-list="seriesList"
				:profiles="profiles"
				@reload="reloadAll"
				@select-series-profiles="goToSeriesProfiles"
				@select-series-versions="goToSeriesVersions"
			/>

			<SeriesVersionTab
				v-else-if="activeTab === 'versions'"
				:versions="versions"
				:series-list="seriesList"
				:initial-series="seriesFilter"
				@reload="reloadAll"
			/>

			<FenestrationProfileTab
				v-else-if="activeTab === 'profiles'"
				:profiles="profiles"
				:series-list="seriesList"
				:initial-series="seriesFilter"
				@reload="reloadAll"
			/>

			<FenestrationGlassTab
				v-else-if="activeTab === 'glass'"
				:glass-list="glasses"
				@reload="reloadAll"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { useList } from 'frappe-ui'
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FenestrationGlassTab from '@/components/studio/FenestrationGlassTab.vue'
import FenestrationProfileTab from '@/components/studio/FenestrationProfileTab.vue'
import ProfileSeriesTab from '@/components/studio/ProfileSeriesTab.vue'
import SeriesVersionTab from '@/components/studio/SeriesVersionTab.vue'
import type {
	FenestrationGlassRow,
	FenestrationProfileRow,
	ProfileSeriesRow,
	SeriesVersionRow,
} from '@/studio/api'

const STUDIO_TABS = ['series', 'versions', 'profiles', 'glass'] as const
export type StudioTabId = (typeof STUDIO_TABS)[number]

const route = useRoute()
const router = useRouter()

const seriesResource = useList<ProfileSeriesRow>({
	doctype: 'Profile Series',
	fields: ['name', 'series_code', 'series_title', 'system_type', 'published_version', 'modified'],
	orderBy: 'series_code asc',
	limit: 200,
})

const versionResource = useList<SeriesVersionRow>({
	doctype: 'Series Version',
	fields: ['name', 'series', 'version_note', 'docstatus', 'modified'],
	orderBy: 'modified desc',
	limit: 200,
})

const profileResource = useList<FenestrationProfileRow>({
	doctype: 'Fenestration Profile',
	fields: [
		'name',
		'profile_code',
		'profile_name',
		'series',
		'role',
		'item',
		'kg_per_m',
		'computed_kg_per_m',
		'use_computed_weight',
		'width_mm',
		'depth_mm',
		'area_mm2',
		'perimeter_mm',
		'total_perimeter_mm',
		'visible_perimeter_mm',
		'ix_mm4',
		'iy_mm4',
		'bar_lengths',
		'dxf_file',
		'section_svg',
		'section_rotation',
		'section_warnings',
	],
	orderBy: 'series asc, profile_code asc',
	limit: 500,
})

const glassResource = useList<FenestrationGlassRow>({
	doctype: 'Fenestration Glass',
	fields: ['name', 'glass_code', 'glass_name', 'thickness_mm', 'item', 'modified'],
	orderBy: 'thickness_mm asc, glass_code asc',
	limit: 200,
})

const seriesList = computed(() => seriesResource.data ?? [])
const versions = computed(() => versionResource.data ?? [])
const profiles = computed(() => profileResource.data ?? [])
const glasses = computed(() => glassResource.data ?? [])

const activeTab = computed<StudioTabId>(() => {
	const t = String(route.query.tab ?? '')
	return (STUDIO_TABS as readonly string[]).includes(t) ? (t as StudioTabId) : 'series'
})

const seriesFilter = computed(() => (route.query.series ? String(route.query.series) : undefined))

const SECTION_META: Record<StudioTabId, { title: string; description: string }> = {
	series: {
		title: 'Profile Series',
		description: 'Manage casement, sliding, and door profile series and their active published rule versions.',
	},
	versions: {
		title: 'Series Version',
		description: 'Manage versioned dimensional deductions, member formulas, hardware rules, and engineering validations.',
	},
	profiles: {
		title: 'Fenestration Profile',
		description: 'Browse and inspect extrusion CAD cross-sections, dimensions, and linear weights.',
	},
	glass: {
		title: 'Fenestration Glass',
		description: 'Manage glazing specifications, thicknesses, and linked ERPNext items.',
	},
}

const currentSection = computed(() => SECTION_META[activeTab.value])

function goToSeriesProfiles(seriesCode: string) {
	router.replace({
		path: '/series-studio',
		query: { tab: 'profiles', series: seriesCode },
	})
}

function goToSeriesVersions(seriesCode: string) {
	router.replace({
		path: '/series-studio',
		query: { tab: 'versions', series: seriesCode },
	})
}

function reloadAll() {
	seriesResource.reload()
	versionResource.reload()
	profileResource.reload()
	glassResource.reload()
}

onMounted(() => {
	reloadAll()
})

watch(
	() => route.fullPath,
	() => {
		if (activeTab.value === 'profiles') {
			profileResource.reload()
		}
	},
)
</script>

