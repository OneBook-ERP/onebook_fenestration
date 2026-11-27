<template>
	<section class="space-y-4" data-testid="project-reports-panel">
		<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			<article
				v-for="r in reports"
				:key="r.title"
				class="flex flex-col justify-between rounded-xl border border-gray-200 bg-white p-4 transition-shadow hover:shadow-sm"
			>
				<div>
					<div class="flex items-center gap-2.5">
						<div
							class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-700"
						>
							<span :class="[r.icon, 'size-4']" />
						</div>
						<h3 class="text-sm font-semibold text-gray-900">{{ r.title }}</h3>
					</div>
					<p class="mt-2 text-[12.5px] leading-relaxed text-gray-500">
						{{ r.description }}
					</p>
				</div>
				<div class="mt-4 flex items-center justify-between border-t border-gray-100 pt-3">
					<span class="text-[11px] font-medium text-gray-400">{{ r.tag }}</span>
					<Button
						size="sm"
						variant="subtle"
						label="Download PDF"
						:href="r.url"
						:disabled="!r.url"
						target="_blank"
					/>
				</div>
			</article>
		</div>
	</section>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed } from "vue";
import { printPdfUrl } from "@/print";

const props = defineProps<{
	project: string;
	quotation?: string | null;
}>();

const reports = computed(() => [
	{
		title: "Elevation Report",
		description:
			"Architectural window elevations, dimensions, glass specs, and placement schedule.",
		icon: "lucide-panels-top-left",
		tag: "Engineering PDF",
		url: printPdfUrl("Fenestration Project", props.project, "Fenestration Elevation"),
	},
	{
		title: "Estimate Confirmation",
		description:
			"Itemized customer confirmation sheet with unit rates, quantities, and totals.",
		icon: "lucide-file-check",
		tag: "Commercial PDF",
		url: printPdfUrl(
			"Fenestration Project",
			props.project,
			"Fenestration Estimate Confirmation"
		),
	},
	{
		title: "Cutting Sheet",
		description:
			"Profile cut optimisation with stock bar diagrams, miter angles, residuals, and wastage summary.",
		icon: "lucide-scissors",
		tag: "Cut Optimisation PDF",
		url: printPdfUrl("Fenestration Project", props.project, "Fenestration Cutting Sheet"),
	},
	{
		title: "Assembly Summary",
		description:
			"Consolidated profile bars, glass panels, and hardware summary for fabrication.",
		icon: "lucide-layers",
		tag: "Production PDF",
		url: printPdfUrl("Fenestration Project", props.project, "Fenestration Assembly Summary"),
	},
	{
		title: "Assembly Detail",
		description: "Detailed per-window member cut lengths, angles, and hardware breakdown.",
		icon: "lucide-ruler",
		tag: "Shop Floor PDF",
		url: printPdfUrl("Fenestration Project", props.project, "Fenestration Assembly Detail"),
	},
	{
		title: "Quotation PDF",
		description: props.quotation
			? `Formal commercial quotation (${props.quotation}) with terms and tax breakdown.`
			: "Generate a quotation on the Quote tab first to download the Quotation PDF.",
		icon: "lucide-file-text",
		tag: props.quotation ? props.quotation : "Not quoted yet",
		url: props.quotation
			? printPdfUrl("Quotation", props.quotation, "Fenestration Quotation")
			: undefined,
	},
]);
</script>
