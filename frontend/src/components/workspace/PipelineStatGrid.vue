<template>
	<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
		<div
			v-for="card in cards"
			:key="card.label"
			data-slot="pipeline-stat-card"
			class="flex items-start justify-between rounded-xl border border-gray-200 bg-white p-4"
		>
			<div class="min-w-0">
				<div class="text-[12px] font-medium text-gray-500">{{ card.label }}</div>
				<div class="mt-1 truncate text-2xl font-semibold tracking-tight text-gray-900">
					{{ card.value }}
				</div>
				<div class="mt-0.5 truncate text-[11px] text-gray-500">{{ card.sublabel }}</div>
			</div>
			<div class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
				<span :class="[card.icon, 'size-4']" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
export interface StatCardItem {
	label: string
	value: string | number
	sublabel: string
	icon: string
}

defineProps<{ cards: StatCardItem[] }>()
</script>

