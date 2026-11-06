<template>
	<div>
		<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
			<div class="text-sm text-ink-gray-6">
				Showing <strong class="text-ink-gray-9">{{ filtered.length }}</strong> of {{ glassList.length }} glass specifications
			</div>

			<div class="flex items-center gap-3">
				<FormControl
					v-model="search"
					type="search"
					placeholder="Search glass..."
					aria-label="Search glass"
					class="w-60"
				/>
				<Button
					variant="solid"
					data-testid="new-glass-btn"
					route="/series-studio/glass/new"
				>
					New glass
				</Button>
			</div>
		</div>

		<div class="overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white">
			<div
				class="grid grid-cols-[150px_1fr_140px_160px_100px] items-center gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
			>
				<span>Glass Code</span>
				<span>Glass Name</span>
				<span>Thickness</span>
				<span>ERPNext Item</span>
				<span class="text-right">Actions</span>
			</div>

			<ul class="divide-y divide-outline-gray-1">
				<li
					v-for="g in filtered"
					:key="g.name"
					data-testid="glass-row"
					class="grid grid-cols-[150px_1fr_140px_160px_100px] items-center gap-4 px-4 py-3 text-sm transition-colors hover:bg-surface-gray-1"
				>
					<router-link
						:to="`/series-studio/glass/${encodeURIComponent(g.name)}`"
						class="font-semibold text-ink-gray-9 hover:underline"
					>
						{{ g.glass_code || g.name }}
					</router-link>
					<router-link
						:to="`/series-studio/glass/${encodeURIComponent(g.name)}`"
						class="truncate font-medium text-ink-gray-8 hover:underline"
					>
						{{ g.glass_name }}
					</router-link>
					<div>
						<Badge theme="blue" :label="`${Number(g.thickness_mm || 0)} mm`" />
					</div>
					<span class="truncate font-mono text-xs text-ink-gray-6">{{ g.item || '—' }}</span>
					<div class="flex items-center justify-end">
						<Button
							variant="outline"
							size="sm"
							label="Edit"
							:data-testid="`edit-glass-${g.name}`"
							:route="`/series-studio/glass/${encodeURIComponent(g.name)}`"
						/>
					</div>
				</li>

				<li
					v-if="!filtered.length"
					class="px-4 py-8 text-center text-sm text-ink-gray-5"
				>
					No fenestration glass records found.
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, FormControl } from 'frappe-ui'
import { computed, ref } from 'vue'
import type { FenestrationGlassRow } from '@/studio/api'

const props = defineProps<{
	glassList: FenestrationGlassRow[]
}>()

defineEmits<{
	(e: 'reload'): void
}>()

const search = ref('')

const filtered = computed(() => {
	const q = search.value.trim().toLowerCase()
	if (!q) return props.glassList
	return props.glassList.filter((g) => {
		const hay = `${g.glass_code || ''} ${g.glass_name || ''} ${g.thickness_mm || ''} ${g.item || ''}`.toLowerCase()
		return hay.includes(q)
	})
})
</script>
