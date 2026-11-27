<script setup lang="ts">
import { computed, ref } from 'vue'

export interface GlassItem {
	code: string
	name: string
	thickness_mm?: number
	inSeries: boolean
}

const props = withDefaults(
	defineProps<{
		modelValue: boolean
		title?: string
		currentGlass?: string
		series?: string
		glasses: GlassItem[]
	}>(),
	{
		title: 'Select Glass',
		currentGlass: '',
		series: '',
	},
)

const emit = defineEmits<{
	'update:modelValue': [val: boolean]
	select: [code: string]
}>()

const searchQuery = ref('')
const showAllGlasses = ref(false)

const filteredGlasses = computed(() => {
	const q = searchQuery.value.trim().toLowerCase()
	return props.glasses
		.filter((g) => {
			if (!showAllGlasses.value && !g.inSeries) return false
			if (!q) return true
			return (
				g.code.toLowerCase().includes(q) ||
				g.name.toLowerCase().includes(q) ||
				(g.thickness_mm ? `${g.thickness_mm}`.includes(q) : false)
			)
		})
		.sort((a, b) => Number(b.inSeries) - Number(a.inSeries) || a.code.localeCompare(b.code))
})

function onSelectGlass(code: string) {
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
		data-testid="glass-picker-modal"
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-2xs"
		@click.self="close"
	>
		<div class="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
				<div class="flex items-center gap-3">
					<div class="flex size-9 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
						<svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="4" y="3" width="16" height="18" rx="1.5" />
							<path d="M8 7l3-2M8 12l6-4" />
						</svg>
					</div>
					<div>
						<h3 class="text-base font-semibold text-gray-900">{{ title }}</h3>
						<p class="text-xs text-gray-500">Search and select glass specifications{{ series ? ` for ${series}` : '' }}</p>
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

			<!-- Search & Filter Bar -->
			<div class="flex flex-wrap items-center gap-3 border-b border-gray-100 bg-gray-50/70 px-6 py-3">
				<div class="relative min-w-[220px] flex-1">
					<input
						v-model="searchQuery"
						type="text"
						data-testid="glass-search-input"
						placeholder="Search glass code, thickness, type..."
						class="w-full rounded-lg border border-gray-300 bg-white px-3.5 py-1.5 pl-9 text-xs text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-hidden"
					/>
					<svg class="pointer-events-none absolute top-2.5 left-3 size-4 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="11" cy="11" r="8" />
						<path d="m21 21-4.3-4.3" />
					</svg>
				</div>

				<label class="flex items-center gap-1.5 text-xs font-medium text-gray-600">
					<input v-model="showAllGlasses" type="checkbox" class="accent-blue-600" />
					All glasses
				</label>
			</div>

			<!-- List -->
			<div class="max-h-[60vh] flex-1 overflow-y-auto p-6">
				<div v-if="!filteredGlasses.length" class="flex flex-col items-center justify-center py-14 text-center text-gray-500">
					<p class="text-sm font-medium text-gray-700">No glass options found</p>
					<p class="mt-1 text-xs text-gray-400">Try clearing your search or checking "All glasses".</p>
				</div>

				<div v-else class="flex flex-col divide-y divide-gray-100 overflow-hidden rounded-xl border border-gray-200 bg-white">
					<button
						v-for="g in filteredGlasses"
						:key="g.code"
						type="button"
						data-testid="glass-list-item"
						:class="[
							'group flex items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-blue-50/50',
							currentGlass === g.code ? 'bg-blue-50/70' : '',
						]"
						@click="onSelectGlass(g.code)"
					>
						<div class="min-w-0 flex-1">
							<div class="flex items-center gap-2">
								<span class="truncate font-mono text-sm font-bold text-gray-900 group-hover:text-blue-600">{{ g.code }}</span>
								<span v-if="g.inSeries" class="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">series</span>
								<span v-else class="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">other</span>
							</div>
							<p v-if="g.name && g.name !== g.code" class="truncate text-xs text-gray-600">{{ g.name }}</p>
						</div>
						<span v-if="g.thickness_mm" class="shrink-0 font-mono text-xs font-semibold text-gray-700">
							{{ Number(g.thickness_mm.toFixed(2)) }} mm
						</span>
					</button>
				</div>
			</div>

			<!-- Footer -->
			<div class="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-6 py-3 text-xs text-gray-500">
				<span>Showing {{ filteredGlasses.length }} of {{ glasses.length }} glasses</span>
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

