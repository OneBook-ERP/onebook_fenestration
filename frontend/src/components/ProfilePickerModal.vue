<script setup lang="ts">
import { computed, ref, watch } from 'vue'

export interface ProfileItem {
	code: string
	name?: string
	series?: string
	role?: string
	width_mm?: number
	depth_mm?: number
	maxWidth?: number
	svg?: string
	hasOutline?: boolean
	currentSeries?: boolean
}

const props = withDefaults(
	defineProps<{
		modelValue: boolean
		title?: string
		targetRole?: 'frame' | 'sash' | 'mullion' | 'transom' | 'bead' | 'all'
		currentProfile?: string
		series?: string
		profiles: ProfileItem[]
	}>(),
	{
		title: 'Select Profile',
		targetRole: 'all',
		currentProfile: '',
		series: '',
	},
)

const emit = defineEmits<{
	'update:modelValue': [val: boolean]
	select: [code: string]
}>()

const searchQuery = ref('')
const selectedRoleFilter = ref<string>(props.targetRole !== 'all' ? props.targetRole : 'all')
const selectedSeriesFilter = ref<string>('all')
const viewMode = ref<'card' | 'list'>('card')
const showAllProfiles = ref(false)

watch(
	() => props.targetRole,
	(newRole) => {
		if (newRole && newRole !== 'all') {
			selectedRoleFilter.value = newRole
		}
	},
	{ immediate: true },
)

watch(
	() => props.modelValue,
	(open) => {
		if (open && props.targetRole !== 'all') {
			selectedRoleFilter.value = props.targetRole
		}
	},
)

const ALL_ROLES = [
	{ label: 'All Roles', value: 'all' },
	{ label: 'Frame', value: 'frame' },
	{ label: 'Sash', value: 'sash' },
	{ label: 'Mullion', value: 'mullion' },
	{ label: 'Transom', value: 'transom' },
	{ label: 'Beading', value: 'bead' },
	{ label: 'Accessory', value: 'accessory' },
]

const visibleRoles = computed(() => {
	if (props.targetRole === 'frame') return [{ label: 'Frame', value: 'frame' }]
	if (props.targetRole === 'sash') return [{ label: 'Sash', value: 'sash' }]
	if (props.targetRole === 'mullion' || props.targetRole === 'transom') {
		return [
			{ label: 'Mullion', value: 'mullion' },
			{ label: 'Transom', value: 'transom' },
		]
	}
	if (props.targetRole === 'bead') return [{ label: 'Beading', value: 'bead' }]
	return ALL_ROLES
})

const availableSeries = computed(() => {
	const set = new Set<string>()
	for (const p of props.profiles) {
		if (p.series) set.add(p.series)
	}
	return ['all', ...Array.from(set).sort()]
})

const filteredProfiles = computed(() => {
	const q = searchQuery.value.trim().toLowerCase()
	const target = props.targetRole !== 'all' ? props.targetRole : selectedRoleFilter.value
	const matchesTarget = (role?: string) => {
		if (target === 'all') return true
		if (target === 'mullion' || target === 'transom') return role === 'mullion' || role === 'transom'
		return role === target
	}
	return props.profiles.filter((p) => {
		const pRole = (p.role || '').toLowerCase()
		if (props.targetRole === 'all' && selectedRoleFilter.value !== 'all') {
			if (pRole !== selectedRoleFilter.value.toLowerCase()) return false
		}
		if (!showAllProfiles.value && (!p.currentSeries || !p.hasOutline)) return false
		if (selectedSeriesFilter.value !== 'all') {
			if ((p.series || '').toLowerCase() !== selectedSeriesFilter.value.toLowerCase()) return false
		}
		if (q) {
			const matchCode = (p.code || '').toLowerCase().includes(q)
			const matchName = (p.name || '').toLowerCase().includes(q)
			const matchSeries = (p.series || '').toLowerCase().includes(q)
			if (!matchCode && !matchName && !matchSeries) return false
		}
		return true
	}).sort((a, b) => Number(matchesTarget(b.role)) - Number(matchesTarget(a.role)) || Number(Boolean(b.currentSeries)) - Number(Boolean(a.currentSeries)) || a.code.localeCompare(b.code))
})

function onSelectProfile(code: string) {
	emit('select', code)
	emit('update:modelValue', false)
}

function close() {
	emit('update:modelValue', false)
}
</script>

<template>
	<div
		v-if="modelValue"
		data-testid="profile-picker-modal"
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-2xs"
		@click.self="close"
	>
		<div
			class="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden border border-gray-200 animate-in fade-in zoom-in-95 duration-100"
		>
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
				<div class="flex items-center gap-3">
					<div class="flex size-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
						<svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="3" y="3" width="18" height="18" rx="2" />
							<path d="M3 9h18M9 21V9" />
						</svg>
					</div>
					<div>
						<h3 class="text-base font-semibold text-gray-900">{{ title }}</h3>
						<p class="text-xs text-gray-500">Search and visually select aluminium extrusion profiles by cross-section</p>
					</div>
				</div>
				<button
					type="button"
					aria-label="Close modal"
					class="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
					@click="close"
				>
					<svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M18 6 6 18M6 6l12 12" />
					</svg>
				</button>
			</div>

			<!-- Search & Filter Controls Toolbar -->
			<div class="flex flex-wrap items-center gap-3 border-b border-gray-100 bg-gray-50/70 px-6 py-3">
				<!-- Search box -->
				<div class="relative flex-1 min-w-[220px]">
					<input
						v-model="searchQuery"
						type="text"
						data-testid="profile-search-input"
						placeholder="Search profile code, name, series..."
						class="w-full rounded-lg border border-gray-300 bg-white px-3.5 py-1.5 pl-9 text-xs text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-hidden"
					/>
					<svg class="pointer-events-none absolute left-3 top-2.5 size-4 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="11" cy="11" r="8" />
						<path d="m21 21-4.3-4.3" />
					</svg>
				</div>

				<!-- Role Filter Pills -->
				<div class="flex items-center gap-1 overflow-x-auto py-0.5">
					<button
						v-for="r in visibleRoles"
						:key="r.value"
						type="button"
						:data-testid="`filter-role-${r.value}`"
						:class="[
							'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
							selectedRoleFilter === r.value
								? 'bg-blue-600 text-white shadow-2xs'
								: 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200',
						]"
						@click="selectedRoleFilter = r.value"
					>
						{{ r.label }}
					</button>
				</div>
				<label class="flex items-center gap-1.5 text-xs font-medium text-gray-600">
					<input v-model="showAllProfiles" type="checkbox" class="accent-blue-600" /> All profiles
				</label>

				<!-- Series Filter Dropdown -->
				<div v-if="availableSeries.length > 2" class="flex items-center gap-1 text-xs">
					<label class="text-gray-500 font-medium">Series:</label>
					<select
						v-model="selectedSeriesFilter"
						class="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-800 focus:border-blue-500 focus:outline-hidden"
					>
						<option value="all">All Series</option>
						<option v-for="s in availableSeries.filter((x) => x !== 'all')" :key="s" :value="s">
							{{ s }}
						</option>
					</select>
				</div>

				<!-- Card / List View Mode Toggle -->
				<div class="flex rounded-md border border-gray-200 bg-white p-0.5 ml-auto">
					<button
						type="button"
						data-testid="view-mode-card"
						:class="['rounded px-2 py-1 text-xs font-medium transition-colors', viewMode === 'card' ? 'bg-gray-100 text-gray-900 font-semibold' : 'text-gray-500 hover:text-gray-700']"
						@click="viewMode = 'card'"
					>
						Cards
					</button>
					<button
						type="button"
						data-testid="view-mode-list"
						:class="['rounded px-2 py-1 text-xs font-medium transition-colors', viewMode === 'list' ? 'bg-gray-100 text-gray-900 font-semibold' : 'text-gray-500 hover:text-gray-700']"
						@click="viewMode = 'list'"
					>
						List
					</button>
				</div>
			</div>

			<!-- Profiles Gallery / List Body -->
			<div class="flex-1 overflow-y-auto p-6 max-h-[60vh]">
				<!-- Empty Search State -->
				<div v-if="!filteredProfiles.length" class="flex flex-col items-center justify-center py-16 text-center text-gray-500">
					<svg class="size-12 text-gray-300 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
						<circle cx="11" cy="11" r="8" />
						<path d="m21 21-4.3-4.3" />
					</svg>
					<p class="text-sm font-medium text-gray-700">No profiles found</p>
					<p class="text-xs text-gray-400 mt-1">Try adjusting your search query or filters.</p>
				</div>

				<!-- Card View Mode -->
				<div v-else-if="viewMode === 'card'" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
					<button
						v-for="p in filteredProfiles"
						:key="p.code"
						type="button"
						data-testid="profile-card-item"
						:class="[
							'group flex flex-col rounded-xl border p-3 text-left transition-all hover:border-blue-500 hover:shadow-md focus:outline-hidden',
							currentProfile === p.code
								? 'border-blue-600 bg-blue-50/40 ring-2 ring-blue-500'
								: 'border-gray-200 bg-white hover:bg-gray-50/50',
						]"
						@click="onSelectProfile(p.code)"
					>
						<!-- Profile SVG Section Preview -->
						<div class="relative flex h-32 w-full items-center justify-center rounded-lg bg-gray-50/80 p-2 overflow-hidden border border-gray-100 group-hover:bg-white transition-colors">
							<svg
								v-if="p.svg"
								xmlns="http://www.w3.org/2000/svg"
								viewBox="-5 -5 80 80"
								class="max-h-full max-w-full drop-shadow-2xs"
								preserveAspectRatio="xMidYMid meet"
							>
								<path
									:d="p.svg"
									fill="#CBD5E1"
									stroke="#334155"
									stroke-width="1.5"
									fill-rule="evenodd"
									vector-effect="non-scaling-stroke"
								/>
							</svg>
							<div v-else class="text-center font-mono text-xs font-semibold text-gray-400">
								{{ p.code }}
							</div>
							<span
								v-if="p.maxWidth"
								class="absolute bottom-1.5 right-1.5 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[10px] font-medium text-white backdrop-blur-2xs"
							>
								Max {{ Math.round(p.maxWidth) }} mm
							</span>
						</div>

						<!-- Details -->
						<div class="mt-3 flex flex-col gap-1">
							<div class="flex items-center justify-between">
								<span class="font-mono text-xs font-bold text-gray-900 group-hover:text-blue-600">
									{{ p.code }}
								</span>
								<span
									v-if="p.role"
									class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-gray-600"
								>
									{{ p.role }}
								</span>
							<span v-if="p.currentSeries" class="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">series</span>
							</div>
							<p v-if="p.name && p.name !== p.code" class="truncate text-xs text-gray-600" :title="p.name">
								{{ p.name }}
							</p>
							<div class="flex items-center justify-between text-[11px] text-gray-400 mt-1">
								<span>{{ p.series || 'Standard' }}</span>
								<span v-if="p.width_mm && p.depth_mm" class="font-mono">
									{{ Math.round(p.width_mm) }} × {{ Math.round(p.depth_mm) }} mm
								</span>
							</div>
						</div>
					</button>
				</div>

				<!-- List View Mode -->
				<div v-else class="flex flex-col divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white overflow-hidden">
					<button
						v-for="p in filteredProfiles"
						:key="p.code"
						type="button"
						data-testid="profile-list-item"
						:class="[
							'group flex items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-blue-50/50',
							currentProfile === p.code ? 'bg-blue-50/70' : '',
						]"
						@click="onSelectProfile(p.code)"
					>
						<!-- Thumbnail SVG -->
						<div class="flex size-14 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 p-1 group-hover:bg-white">
							<svg
								v-if="p.svg"
								xmlns="http://www.w3.org/2000/svg"
								viewBox="-5 -5 80 80"
								class="max-h-full max-w-full"
								preserveAspectRatio="xMidYMid meet"
							>
								<path
									:d="p.svg"
									fill="#CBD5E1"
									stroke="#334155"
									stroke-width="1.5"
									fill-rule="evenodd"
									vector-effect="non-scaling-stroke"
								/>
							</svg>
							<span v-else class="font-mono text-[10px] text-gray-400">{{ p.code }}</span>
						</div>

						<!-- Info -->
						<div class="flex flex-1 flex-col">
							<div class="flex items-center gap-2">
								<span class="font-mono text-sm font-bold text-gray-900 group-hover:text-blue-600">
									{{ p.code }}
								</span>
								<span
									v-if="p.role"
									class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-gray-600"
								>
									{{ p.role }}
								</span>
								<span v-if="p.series" class="text-xs text-gray-400">
									· {{ p.series }}
								</span>
							</div>
							<p v-if="p.name && p.name !== p.code" class="text-xs text-gray-600">
								{{ p.name }}
							</p>
						</div>

						<!-- Dimensions -->
						<div class="text-right">
							<div v-if="p.maxWidth" class="font-mono text-xs font-semibold text-gray-900">
								Max width: {{ Math.round(p.maxWidth) }} mm
							</div>
							<div v-if="p.width_mm && p.depth_mm" class="font-mono text-[11px] text-gray-400">
								{{ Math.round(p.width_mm) }} × {{ Math.round(p.depth_mm) }} mm
							</div>
						</div>
					</button>
				</div>
			</div>

			<!-- Footer -->
			<div class="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-6 py-3 text-xs text-gray-500">
				<span>Showing {{ filteredProfiles.length }} of {{ profiles.length }} profiles</span>
				<button
					type="button"
					class="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100"
					@click="close"
				>
					Close
				</button>
			</div>
		</div>
	</div>
</template>
