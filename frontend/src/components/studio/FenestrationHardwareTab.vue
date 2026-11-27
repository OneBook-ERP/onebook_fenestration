<template>
	<div>
		<!-- Filter & Action Toolbar -->
		<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
			<div class="flex flex-wrap items-center gap-1.5">
				<button
					type="button"
					class="rounded-md border px-2.5 py-1 text-xs font-medium transition-colors"
					:class="
						selectedCategory === 'all'
							? 'border-blue-300 bg-blue-50 text-blue-950'
							: 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:bg-surface-gray-1'
					"
					@click="selectedCategory = 'all'"
				>
					All · {{ hardwareList.length }}
				</button>
				<button
					v-for="cat in categoryCounts"
					:key="cat.name"
					type="button"
					:data-testid="`hardware-cat-${cat.name}`"
					class="rounded-md border px-2.5 py-1 text-xs font-medium transition-colors"
					:class="
						selectedCategory === cat.name
							? 'border-blue-300 bg-blue-50 text-blue-950'
							: 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:bg-surface-gray-1'
					"
					@click="selectedCategory = cat.name"
				>
					{{ cat.name }} · {{ cat.count }}
				</button>
			</div>

			<div class="flex items-center gap-3">
				<FormControl
					v-model="search"
					type="search"
					placeholder="Search hardware..."
					aria-label="Search hardware"
					class="w-60"
				/>
				<Button
					variant="solid"
					data-testid="new-hardware-btn"
					route="/series-studio/hardware/new"
				>
					New hardware
				</Button>
			</div>
		</div>

		<!-- Card Grid -->
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
			<article
				v-for="hw in filtered"
				:key="hw.name"
				data-testid="hardware-card"
				class="flex flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white transition-shadow hover:shadow-sm"
			>
				<!-- CAD Section Preview -->
				<div
					class="flex h-44 items-center justify-center border-b border-outline-gray-1 bg-[#f6f6f4] p-3"
				>
					<svg
						v-if="hw.section_svg && hw.width_mm && hw.depth_mm"
						:viewBox="cardViewBox(hw)"
						class="h-full w-full"
					>
						<g :transform="cardRotationTransform(hw)">
							<path
								:d="hw.section_svg"
								fill="#94a3b8"
								fill-opacity="0.85"
								stroke="#1e293b"
								:stroke-width="
									Math.max(
										0.25,
										Math.max(Number(hw.width_mm), Number(hw.depth_mm)) * 0.014
									)
								"
								stroke-linejoin="round"
								fill-rule="evenodd"
							/>
						</g>
					</svg>
					<div v-else class="text-center text-xs text-ink-gray-4">
						<div class="font-medium text-ink-gray-5">{{ hw.category }}</div>
						<div class="mt-0.5 text-[11px]">No DXF attached</div>
					</div>
				</div>

				<!-- Card Metadata -->
				<div class="flex flex-1 flex-col p-4">
					<div class="flex items-start justify-between gap-2">
						<div class="min-w-0">
							<h3 class="truncate text-sm font-semibold text-ink-gray-9">
								{{ hw.hardware_code || hw.name }} · {{ hw.hardware_name }}
							</h3>
							<div
								class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-ink-gray-5"
							>
								<span v-if="hw.width_mm && hw.depth_mm">
									{{ Number(hw.width_mm).toFixed(1) }} ×
									{{ Number(hw.depth_mm).toFixed(1) }} mm
								</span>
								<span v-if="hw.thickness_mm">
									Gap/Thk: {{ Number(hw.thickness_mm) }} mm
								</span>
								<span v-if="hw.uom">{{ hw.uom }}</span>
							</div>
						</div>
						<Badge theme="blue" :label="hw.category || 'Accessory'" />
					</div>

					<div class="mt-3 flex items-center justify-between text-xs text-ink-gray-5">
						<span class="truncate font-mono">{{ hw.item || "No ERPNext Item" }}</span>
						<span v-if="hw.weight_kg" class="shrink-0 font-semibold text-ink-gray-8">
							{{ Number(hw.weight_kg).toFixed(3) }} kg
						</span>
					</div>

					<div class="mt-4 pt-1">
						<Button
							variant="outline"
							class="w-full"
							label="Open hardware"
							:route="`/series-studio/hardware/${encodeURIComponent(hw.name)}`"
						/>
					</div>
				</div>
			</article>

			<!-- Dashed Add Hardware Card -->
			<router-link
				to="/series-studio/hardware/new"
				data-testid="add-hardware-card"
				class="flex min-h-[280px] flex-col items-center justify-center rounded-xl border-2 border-dashed border-outline-gray-3 bg-surface-gray-1/40 p-6 text-center transition-colors hover:border-blue-400 hover:bg-blue-50/30"
			>
				<div class="text-sm font-semibold text-ink-gray-8">+ Add Hardware</div>
				<p class="mt-1 max-w-[220px] text-xs text-ink-gray-5">
					Import gaskets (G22–G25), beadings, handles, hinges, locks, or rollers with
					optional DXF CAD geometry.
				</p>
			</router-link>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, FormControl } from "frappe-ui";
import { computed, ref } from "vue";
import { HARDWARE_CATEGORIES, type FenestrationHardwareRow } from "@/studio/api";
import { profileRotationTransform } from "@/studio/sectionSvg";

const props = defineProps<{
	hardwareList: FenestrationHardwareRow[];
}>();

defineEmits<{
	(e: "reload"): void;
}>();

const search = ref("");
const selectedCategory = ref<string>("all");

const categoryCounts = computed(() => {
	const counts = new Map<string, number>();
	for (const hw of props.hardwareList) {
		const cat = hw.category || "Accessory";
		counts.set(cat, (counts.get(cat) ?? 0) + 1);
	}
	return HARDWARE_CATEGORIES.filter((c) => counts.has(c)).map((c) => ({
		name: c,
		count: counts.get(c) ?? 0,
	}));
});

const filtered = computed(() => {
	const q = search.value.trim().toLowerCase();
	return props.hardwareList.filter((hw) => {
		if (selectedCategory.value !== "all" && hw.category !== selectedCategory.value)
			return false;
		if (!q) return true;
		const hay = `${hw.hardware_code || ""} ${hw.hardware_name || ""} ${hw.category || ""} ${
			hw.item || ""
		}`.toLowerCase();
		return hay.includes(q);
	});
});

function cardViewBox(hw: FenestrationHardwareRow): string {
	const w = Math.max(4, Number(hw.width_mm || 10));
	const d = Math.max(4, Number(hw.depth_mm || 10));
	const pad = Math.max(w, d) * 0.16;
	return `${-pad} ${-pad} ${w + pad * 2} ${d + pad * 2}`;
}

function cardRotationTransform(hw: FenestrationHardwareRow): string {
	return profileRotationTransform({
		section_rotation: hw.section_rotation,
		section_flip_x: hw.section_flip_x,
		section_flip_y: hw.section_flip_y,
		width_mm: hw.width_mm,
		depth_mm: hw.depth_mm,
	});
}
</script>
