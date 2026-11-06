<template>
	<div class="mx-auto max-w-6xl p-6">
		<header class="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-outline-gray-2 pb-4">
			<div>
				<nav aria-label="Breadcrumb" class="mb-1 flex items-center gap-1.5 text-sm text-ink-gray-5">
					<router-link to="/series-studio" class="hover:text-ink-gray-8">
						Series Studio
					</router-link>
					<span aria-hidden="true">/</span>
					<router-link to="/series-studio" class="hover:text-ink-gray-8">
						Profile Series
					</router-link>
					<span aria-hidden="true">/</span>
					<span class="font-medium text-ink-gray-8">{{ isEdit ? form.series_code : 'New Profile Series' }}</span>
				</nav>
				<div class="flex flex-wrap items-center gap-3">
					<h1 class="text-xl font-semibold text-ink-gray-9">
						{{ isEdit ? `${form.series_code} · ${form.series_title || 'Series'}` : (form.series_title || 'New Profile Series') }}
					</h1>
					<Badge :theme="form.system_type === 'Casement' ? 'blue' : form.system_type === 'Sliding' ? 'amber' : 'gray'" :label="form.system_type" />
					<Badge v-if="form.published_version" theme="green" :label="`Published: ${form.published_version}`" />
					<Badge v-else theme="gray" label="Unpublished" />
				</div>
			</div>

			<div class="flex flex-wrap items-center gap-2">
				<Button
					v-if="isEdit"
					variant="subtle"
					label="All Profiles (Card View)"
					:route="`/series-studio?tab=profiles&series=${form.series_code}`"
				/>
				<Button
					v-if="isEdit"
					variant="subtle"
					label="Series Versions"
					:route="`/series-studio?tab=versions&series=${form.series_code}`"
				/>
				<Button variant="outline" label="Back" route="/series-studio" />
				<Button
					variant="solid"
					:label="isEdit ? 'Save Changes' : 'Create Series'"
					:loading="saving"
					:disabled="!canSave"
					data-testid="save-series-btn"
					@click="save"
				/>
			</div>
		</header>

		<div v-if="loadingDoc" class="py-12 text-center text-sm text-ink-gray-5">
			Loading profile series…
		</div>

		<div v-else class="space-y-8">
			<Alert v-if="error" theme="red" :title="error" />

			<!-- Section 1: Series Details -->
			<section>
				<h2 class="mb-4 text-base font-semibold text-ink-gray-9">Series Details</h2>
				<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
					<div class="space-y-4">
						<FormControl
							v-model="form.series_code"
							label="Series Code *"
							placeholder="e.g. CS400"
							:disabled="isEdit"
						/>
						<FormControl
							v-model="form.series_title"
							label="Series Title *"
							placeholder="e.g. CS400 Economical Casement"
						/>
					</div>

					<div class="space-y-4">
						<FormControl
							v-model="form.system_type"
							type="select"
							label="System Type *"
							:options="systemTypeOptions"
						/>
						<div>
							<FormControl
								:model-value="form.published_version || '—'"
								label="Published Version"
								disabled
							/>
							<div v-if="form.published_version" class="mt-1.5">
								<router-link
									:to="`/series-studio/versions/${encodeURIComponent(form.published_version)}`"
									class="text-xs font-medium text-blue-600 hover:underline"
								>
									Open {{ form.published_version }} rules &rarr;
								</router-link>
							</div>
						</div>
					</div>
				</div>
			</section>

			<!-- Section 2: Series Profiles (from profile_series.js) -->
			<section class="border-t border-outline-gray-2 pt-6">
				<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
					<h2 class="text-base font-semibold text-ink-gray-9">Series Profiles</h2>
					<Button
						v-if="isEdit"
						variant="outline"
						size="sm"
						label="+ Add Profile to Series"
						:route="`/series-studio/profiles/new?series=${encodeURIComponent(form.series_code)}`"
					/>
				</div>

				<div v-if="!isEdit" class="py-6 text-sm text-ink-gray-5">
					Save the series to view and manage its profiles.
				</div>

				<template v-else>
					<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
						<div class="flex flex-wrap gap-2">
							<button
								v-for="r in roles"
								:key="r"
								type="button"
								class="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors"
								:class="
									selectedRole === r
										? 'border-ink-gray-9 bg-ink-gray-9 text-surface-white'
										: 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:bg-surface-gray-1'
								"
								@click="selectedRole = r"
							>
								{{ r === 'ALL' ? `All · ${seriesProfiles.length}` : r.charAt(0).toUpperCase() + r.slice(1) }}
							</button>
						</div>
						<FormControl
							v-model="profileSearch"
							type="search"
							placeholder="Search series profiles..."
							class="w-56"
						/>
					</div>

					<div v-if="!filteredProfiles.length" class="py-8 text-center text-sm text-ink-gray-5">
						No profiles match in this series.
					</div>

					<div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
						<article
							v-for="p in filteredProfiles"
							:key="p.name"
							class="flex flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white"
						>
							<div
								class="flex h-[180px] cursor-pointer items-center justify-center border-b border-outline-gray-1 bg-[#f6f6f4] p-3"
								@click="router.push(`/series-studio/profiles/${encodeURIComponent(p.name)}`)"
							>
								<svg
									v-if="p.section_svg && p.width_mm && p.depth_mm"
									:viewBox="`0 0 ${svgOf(p).cw} ${svgOf(p).ch}`"
									class="block h-full max-h-[155px] w-full max-w-full"
									xmlns="http://www.w3.org/2000/svg"
								>
									<g :transform="`translate(${svgOf(p).ox}, ${svgOf(p).oy}) scale(${svgOf(p).s})`">
										<path
											:d="p.section_svg"
											fill="#94a3b8"
											fill-opacity="0.85"
											stroke="#334155"
											:stroke-width="svgOf(p).pathStroke"
											stroke-linejoin="round"
											fill-rule="evenodd"
										/>
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
								<div v-else class="text-xs text-ink-gray-4">No DXF</div>
							</div>

							<div class="flex flex-1 flex-col p-4">
								<div class="mb-1 flex items-baseline justify-between gap-2">
									<div class="truncate text-sm font-bold text-ink-gray-9">
										{{ displayProfileCode(p) }} · {{ p.profile_name }}
									</div>
									<span class="text-xs capitalize text-ink-gray-5">{{ p.role || '—' }}</span>
								</div>
								<div class="mb-2 text-xs text-ink-gray-5">
									{{ Number(p.width_mm || 0).toFixed(1) }} × {{ Number(p.depth_mm || 0).toFixed(1) }} mm · Bar {{ p.bar_lengths || '4880, 5800' }} mm
								</div>
								<div class="mt-auto mb-3 flex items-baseline justify-between border-t border-outline-gray-1 pt-2.5">
									<span class="text-xs text-ink-gray-5">
										{{ Number(p.area_mm2 || 0).toFixed(1) }} mm² · {{ Number(p.perimeter_mm || 0).toFixed(0) }} mm
									</span>
									<span class="text-sm font-bold text-ink-gray-9">
										{{ effectiveWeight(p).toFixed(3) }} kg/m
									</span>
								</div>
								<Button
									variant="outline"
									size="sm"
									label="Open profile"
									:route="`/series-studio/profiles/${encodeURIComponent(p.name)}`"
								/>
							</div>
						</article>
					</div>
				</template>
			</section>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, FormControl, toast, useList } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
	getProfileSeriesDoc,
	saveProfileSeries,
	type FenestrationProfileRow,
} from '@/studio/api'
import { computeCardSvgMetrics, displayProfileCode, effectiveWeight } from '@/studio/sectionSvg'

const props = defineProps<{ name?: string }>()
const router = useRouter()

const isEdit = computed(() => Boolean(props.name))
const loadingDoc = ref(false)
const saving = ref(false)
const error = ref('')

const systemTypeOptions = [
	{ label: 'Casement', value: 'Casement' },
	{ label: 'Sliding', value: 'Sliding' },
	{ label: 'Door', value: 'Door' },
]

const form = reactive({
	series_code: '',
	series_title: '',
	system_type: 'Casement' as 'Casement' | 'Sliding' | 'Door',
	published_version: '' as string | null | undefined,
})

const canSave = computed(() =>
	Boolean(form.series_code.trim() && form.series_title.trim() && form.system_type && !saving.value),
)

const roles = ['ALL', 'frame', 'sash', 'mullion', 'transom', 'bead', 'accessory'] as const
const selectedRole = ref<string>('ALL')
const profileSearch = ref('')

const profileResource = useList<FenestrationProfileRow>({
	doctype: 'Fenestration Profile',
	fields: [
		'name',
		'profile_code',
		'profile_name',
		'series',
		'role',
		'kg_per_m',
		'computed_kg_per_m',
		'use_computed_weight',
		'width_mm',
		'depth_mm',
		'area_mm2',
		'perimeter_mm',
		'bar_lengths',
		'dxf_file',
		'section_svg',
	],
	orderBy: 'profile_code asc',
	limit: 500,
})

const seriesProfiles = computed(() =>
	(profileResource.data ?? []).filter((p) => p.series === (form.series_code || props.name)),
)

const filteredProfiles = computed(() => {
	const q = profileSearch.value.trim().toLowerCase()
	return seriesProfiles.value.filter((p) => {
		if (selectedRole.value !== 'ALL' && p.role !== selectedRole.value) return false
		if (q) {
			const hay = `${p.profile_code || ''} ${p.profile_name || ''} ${p.role || ''}`.toLowerCase()
			if (!hay.includes(q)) return false
		}
		return true
	})
})

function svgOf(p: FenestrationProfileRow) {
	return computeCardSvgMetrics(p.width_mm, p.depth_mm)
}

onMounted(async () => {
	if (!props.name) return
	loadingDoc.value = true
	try {
		const doc = await getProfileSeriesDoc(props.name)
		form.series_code = doc.series_code || doc.name
		form.series_title = doc.series_title || ''
		form.system_type = doc.system_type || 'Casement'
		form.published_version = doc.published_version || null
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not load profile series'
	} finally {
		loadingDoc.value = false
	}
})

async function save() {
	if (!canSave.value) return
	saving.value = true
	error.value = ''
	try {
		const savedName = await saveProfileSeries(
			{
				series_code: form.series_code.trim(),
				series_title: form.series_title.trim(),
				system_type: form.system_type,
			},
			props.name || null,
		)
		toast.success(isEdit.value ? 'Profile series updated' : 'Profile series created')
		if (!isEdit.value) {
			router.replace(`/series-studio/series/${encodeURIComponent(savedName)}`)
		}
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not save profile series'
	} finally {
		saving.value = false
	}
}
</script>

