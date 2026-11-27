<template>
	<div data-slot="sidebar-nav-group" class="flex flex-col">
		<button
			type="button"
			:aria-expanded="expanded"
			class="group flex h-[30px] w-full items-center rounded-[7px] px-2 text-left text-[13px] font-normal text-ink-gray-7 transition-colors duration-150 hover:bg-surface-gray-2/80 hover:text-ink-gray-9 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
			@click="expanded = !expanded"
		>
			<span v-if="icon" class="grid size-4 shrink-0 place-items-center text-ink-gray-6 group-hover:text-ink-gray-8">
				<span :class="[icon, 'size-4']" />
			</span>
			<span class="min-w-0 flex-1 truncate" :class="icon ? 'ml-2' : ''">{{ label }}</span>
			<span
				class="lucide-chevron-right ml-1.5 size-3.5 shrink-0 text-ink-gray-4 transition-transform duration-200 ease-out group-hover:text-ink-gray-6"
				:class="{ 'rotate-90 text-ink-gray-6': expanded }"
			/>
		</button>

		<div
			class="grid transition-[grid-template-rows,opacity] duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]"
			:class="expanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'"
		>
			<div class="overflow-hidden">
				<div
					role="group"
					:aria-label="label"
					class="ml-3.5 mt-0.5 flex flex-col gap-0.5 border-l border-outline-gray-1 pl-2"
				>
					<slot />
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = withDefaults(
	defineProps<{
		label: string
		icon?: string
		defaultOpen?: boolean
	}>(),
	{
		defaultOpen: true,
	},
)

const expanded = ref(props.defaultOpen)
</script>
