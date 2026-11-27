<template>
	<Teleport to="body">
		<Transition
			enter-active-class="transition duration-150 ease-out"
			enter-from-class="opacity-0"
			enter-to-class="opacity-100"
			leave-active-class="transition duration-100 ease-in"
			leave-from-class="opacity-100"
			leave-to-class="opacity-0"
		>
			<div
				v-if="open"
				data-slot="sidebar-quick-search"
				class="fixed inset-0 z-50 flex items-start justify-center bg-black/25 px-4 pt-[14vh] backdrop-blur-[1px]"
				@mousedown.self="close"
			>
				<div
					role="dialog"
					aria-modal="true"
					aria-label="Quick search"
					class="w-full max-w-md overflow-hidden rounded-xl bg-white shadow-2xl ring-1 ring-black/10"
				>
					<div class="flex h-11 items-center gap-2 border-b border-gray-200 px-3">
						<span class="lucide-search size-4 shrink-0 text-gray-400" />
						<input
							ref="inputRef"
							v-model="query"
							type="text"
							placeholder="Jump to project or page..."
							class="h-full min-w-0 flex-1 border-0 bg-transparent text-[13px] text-gray-900 placeholder:text-gray-400 outline-none focus:outline-none focus:ring-0"
							@keydown.down.prevent="move(1)"
							@keydown.up.prevent="move(-1)"
							@keydown.enter.prevent="selectActive"
							@keydown.escape.prevent="close"
						/>
						<kbd
							class="rounded border border-gray-200 bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500"
						>
							Esc
						</kbd>
					</div>

					<div class="max-h-72 overflow-y-auto p-1.5">
						<div
							v-if="filtered.length === 0"
							class="px-3 py-6 text-center text-[13px] text-gray-500"
						>
							No matching results
						</div>
						<button
							v-for="(item, idx) in filtered"
							:key="item.route"
							type="button"
							class="flex w-full items-center gap-2.5 rounded-[8px] px-2.5 py-2 text-left text-[13px] transition-colors"
							:class="
								idx === activeIndex
									? 'bg-gray-100 text-gray-900'
									: 'text-gray-700 hover:bg-gray-50'
							"
							@mouseenter="activeIndex = idx"
							@click="navigate(item.route)"
						>
							<span :class="[item.icon, 'size-4 shrink-0 text-gray-500']" />
							<span class="min-w-0 flex-1 truncate font-medium">{{
								item.label
							}}</span>
							<span class="shrink-0 text-[11px] text-gray-500">{{
								item.group
							}}</span>
						</button>
					</div>
				</div>
			</div>
		</Transition>
	</Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";

export interface QuickSearchItem {
	label: string;
	group: string;
	icon: string;
	route: string;
}

const props = defineProps<{
	open: boolean;
	items: QuickSearchItem[];
}>();

const emit = defineEmits<{
	"update:open": [value: boolean];
}>();

const router = useRouter();
const inputRef = ref<HTMLInputElement | null>(null);
const query = ref("");
const activeIndex = ref(0);

const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	if (!q) return props.items;
	return props.items.filter(
		(item) => item.label.toLowerCase().includes(q) || item.group.toLowerCase().includes(q)
	);
});

watch(
	() => props.open,
	async (isOpen) => {
		if (!isOpen) return;
		query.value = "";
		activeIndex.value = 0;
		await nextTick();
		inputRef.value?.focus();
	}
);

watch(filtered, () => {
	activeIndex.value = 0;
});

function close() {
	emit("update:open", false);
}

function move(delta: number) {
	if (!filtered.value.length) return;
	const len = filtered.value.length;
	activeIndex.value = (activeIndex.value + delta + len) % len;
}

function selectActive() {
	const item = filtered.value[activeIndex.value];
	if (item) navigate(item.route);
}

function navigate(route: string) {
	close();
	router.push(route);
}
</script>
