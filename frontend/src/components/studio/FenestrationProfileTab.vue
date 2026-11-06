<template>
	<div>
		<div class="mb-4 flex flex-wrap gap-1.5 border-b border-outline-gray-2 pb-2" role="group" aria-label="Filter profiles by series">
			<button
				v-for="s in seriesTabs"
				:key="s.key"
				type="button"
				:data-testid="`profile-series-${s.key}`"
				class="border-b-2 px-3.5 py-1.5 text-xs font-semibold transition-colors"
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

		<div class="mb-5 flex flex-wrap items-center justify-between gap-3">
			<div class="flex flex-wrap gap-2" role="group" aria-label="Filter profiles by role">
				<button
					v-for="r in roles"
					:key="r"
					type="button"
					:data-testid="`role-pill-${r}`"
					class="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors"
					:class="
						selectedRole === r
							? 'border-ink-gray-9 bg-ink-gray-9 text-surface-white'
							: 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:bg-surface-gray-1'
					"
					@click="selectedRole = r"
				>
					{{ r === 'ALL' ? 'All roles' : r.charAt(0).toUpperCase() + r.slice(1) }}
				</button>
			</div>

			<div class="flex items-center gap-3">
				<FormControl
					v-model="search"
					type="search"
					placeholder="Search profiles..."
					aria-label="Search profiles"
					class="w-60"
				/>
				<Button
					variant="solid"
					data-testid="new-profile-btn"
					:route="newProfileRoute"
				>
					New profile
				</Button>
			</div>
		</div>

		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
			<article
				v-for="p in filtered"
				:key="p.name"
				data-testid="profile-card"
				class="flex flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white shadow-sm"
			>
				<div
					class="flex h-[190px] cursor-pointer items-center justify-center border-b border-outline-gray-1 bg-[#f6f6f4] p-3.5"
					@click="openDetails(p)"
				>
					<svg
						v-if="hasSvg(p)"
						:viewBox="`0 0 ${svgOf(p).cw} ${svgOf(p).ch}`"
						class="block h-full max-h-[166px] w-full max-w-full"
						xmlns="http://www.w3.org/2000/svg"
					>
						<g :transform="`translate(${svgOf(p).ox}, ${svgOf(p).oy}) scale(${svgOf(p).s})`">
							<path
								:d="p.section_svg || ''"
								fill="#94a3b8"
								fill-opacity="0.85"
								stroke="#334155"
								:stroke-width="svgOf(p).pathStroke"
								stroke-linejoin="round"
								fill-rule="evenodd"
							/>
						</g>
						<g stroke="#64748b" stroke-width="1" stroke-linecap="square">
							<line :x1="svgOf(p).ox" :y1="svgOf(p).dimY" :x2="svgOf(p).ox + svgOf(p).dw" :y2="svgOf(p).dimY" />
							<line :x1="svgOf(p).ox" :y1="svgOf(p).dimY - svgOf(p).tick" :x2="svgOf(p).ox" :y2="svgOf(p).dimY + svgOf(p).tick" />
							<line :x1="svgOf(p).ox + svgOf(p).dw" :y1="svgOf(p).dimY - svgOf(p).tick" :x2="svgOf(p).ox + svgOf(p).dw" :y2="svgOf(p).dimY + svgOf(p).tick" />

							<line :x1="svgOf(p).dimX" :y1="svgOf(p).oy" :x2="svgOf(p).dimX" :y2="svgOf(p).oy + svgOf(p).dh" />
							<line :x1="svgOf(p).dimX - svgOf(p).tick" :y1="svgOf(p).oy" :x2="svgOf(p).dimX + svgOf(p).tick" :y2="svgOf(p).oy" />
							<line :x1="svgOf(p).dimX - svgOf(p).tick" :y1="svgOf(p).oy + svgOf(p).dh" :x2="svgOf(p).dimX + svgOf(p).tick" :y2="svgOf(p).oy + svgOf(p).dh" />
						</g>
						<text
							:x="svgOf(p).ox + svgOf(p).dw / 2"
							:y="svgOf(p).dimY + 15"
							text-anchor="middle"
							fill="#0f172a"
							:font-size="svgOf(p).fontSize"
							font-weight="600"
						>
							{{ svgOf(p).widthLabel }}
						</text>
						<text
							:x="svgOf(p).vTextX"
							:y="svgOf(p).vTextY"
							text-anchor="middle"
							dominant-baseline="central"
							fill="#0f172a"
							:font-size="svgOf(p).fontSize"
							font-weight="600"
							:transform="`rotate(-90 ${svgOf(p).vTextX} ${svgOf(p).vTextY})`"
						>
							{{ svgOf(p).depthLabel }}
						</text>
					</svg>
					<div v-else class="text-xs text-ink-gray-4">No DXF preview</div>
				</div>

				<div class="flex flex-1 flex-col p-4">
					<div class="mb-1 flex items-baseline justify-between gap-2">
						<div
							class="truncate text-sm font-bold text-ink-gray-9"
							:title="`${displayProfileCode(p)} · ${p.profile_name}`"
						>
							{{ displayProfileCode(p) }} · {{ p.profile_name }}
						</div>
						<span class="shrink-0 text-xs capitalize text-ink-gray-5">{{ p.role || '—' }}</span>
					</div>

					<div class="mb-2 text-xs text-ink-gray-5">
						{{ seriesLabel(p.series) }} · Bar {{ p.bar_lengths || '4880, 5800' }} mm
					</div>

					<div class="mb-3 flex items-center justify-between gap-2">
						<div class="flex items-center gap-1.5 text-xs text-ink-gray-6">
							<span class="inline-block size-2.5 rounded-sm border border-slate-500 bg-slate-400"></span>
							<span>Al 6063-T6 · {{ Number(p.width_mm || 0).toFixed(1) }} × {{ Number(p.depth_mm || 0).toFixed(1) }} mm</span>
						</div>
						<Badge :theme="hasSvg(p) ? 'green' : 'gray'" :label="hasSvg(p) ? 'OK' : 'No DXF'" />
					</div>

					<div class="mt-auto mb-3 flex items-baseline justify-between border-t border-outline-gray-1 pt-2.5">
						<span class="text-xs text-ink-gray-5">
							{{ Number(p.area_mm2 || 0).toFixed(1) }} mm² · {{ Number(p.perimeter_mm || 0).toFixed(0) }} mm perim
						</span>
						<span class="text-sm font-bold text-ink-gray-9">
							{{ effectiveWeight(p).toFixed(3) }} kg/m
						</span>
					</div>

					<div class="grid grid-cols-2 gap-2">
						<Button
							variant="outline"
							size="sm"
							label="Edit profile"
							:data-testid="`edit-profile-${p.name}`"
							:route="`/series-studio/profiles/${encodeURIComponent(p.name)}`"
						/>
						<Button
							variant="outline"
							size="sm"
							label="Details"
							:data-testid="`details-profile-${p.name}`"
							@click="openDetails(p)"
						/>
					</div>
				</div>
			</article>

			<router-link
				:to="newProfileRoute"
				data-testid="add-profile-card"
				class="flex min-h-[320px] flex-col items-center justify-center rounded-xl border-[1.5px] border-dashed border-outline-gray-3 bg-surface-gray-1/50 text-ink-gray-6 transition-colors hover:border-ink-gray-7 hover:bg-surface-gray-1"
			>
				<span class="mb-1 text-2xl leading-none">+</span>
				<span class="text-xs font-medium">Add a fenestration profile</span>
			</router-link>
		</div>

		<ProfileSectionModal
			v-model="showDetails"
			:profile="activeProfile"
			@edit="onEditFromDetails"
		/>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, FormControl } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ProfileSectionModal from './ProfileSectionModal.vue'
import type { FenestrationProfileRow, ProfileSeriesRow } from '@/studio/api'
import {
	computeCardSvgMetrics,
	displayProfileCode,
	effectiveWeight,
} from '@/studio/sectionSvg'

const props = defineProps<{
	profiles: FenestrationProfileRow[]
	seriesList: ProfileSeriesRow[]
	initialSeries?: string
}>()

defineEmits<{
	(e: 'reload'): void
}>()

const router = useRouter()
const roles = ['ALL', 'frame', 'sash', 'mullion', 'transom', 'bead', 'accessory'] as const
const selectedSeries = ref<string>(props.initialSeries || 'ALL')
const selectedRole = ref<string>('ALL')
const search = ref('')

watch(
	() => props.initialSeries,
	(val) => {
		if (val) selectedSeries.value = val
	},
)

const newProfileRoute = computed(() =>
	selectedSeries.value !== 'ALL'
		? `/series-studio/profiles/new?series=${encodeURIComponent(selectedSeries.value)}`
		: '/series-studio/profiles/new',
)

const seriesTitleMap = computed(() => {
	const map = new Map<string, string>()
	for (const s of props.seriesList) {
		map.set(s.series_code || s.name, s.series_title)
	}
	return map
})

function seriesLabel(seriesCode: string): string {
	return seriesTitleMap.value.get(seriesCode) || seriesCode || '—'
}

const seriesTabs = computed(() => {
	const counts = new Map<string, number>()
	for (const p of props.profiles) {
		const s = p.series || 'Other'
		counts.set(s, (counts.get(s) || 0) + 1)
	}
	const keys = new Set<string>([
		...props.seriesList.map((s) => s.series_code || s.name),
		...counts.keys(),
	])
	return [
		{ key: 'ALL', label: `All Profiles · ${props.profiles.length}` },
		...Array.from(keys).map((k) => ({ key: k, label: `${k} · ${counts.get(k) || 0}` })),
	]
})

const filtered = computed(() => {
	const q = search.value.trim().toLowerCase()
	return props.profiles.filter((p) => {
		if (selectedSeries.value !== 'ALL' && p.series !== selectedSeries.value) return false
		if (selectedRole.value !== 'ALL' && p.role !== selectedRole.value) return false
		if (q) {
			const hay = `${p.profile_code || ''} ${p.profile_name || ''} ${p.series || ''} ${p.role || ''}`.toLowerCase()
			if (!hay.includes(q)) return false
		}
		return true
	})
})

function hasSvg(p: FenestrationProfileRow): boolean {
	return Boolean(p.section_svg && p.width_mm && p.depth_mm)
}

function svgOf(p: FenestrationProfileRow) {
	return computeCardSvgMetrics(p.width_mm, p.depth_mm)
}

const showDetails = ref(false)
const activeProfile = ref<FenestrationProfileRow | null>(null)

function openDetails(p: FenestrationProfileRow) {
	activeProfile.value = p
	showDetails.value = true
}

function onEditFromDetails(p: FenestrationProfileRow) {
	showDetails.value = false
	router.push(`/series-studio/profiles/${encodeURIComponent(p.name)}`)
}
</script>
