<template>
	<section class="space-y-4" data-testid="project-order-panel">
		<PipelineStatGrid :cards="statCards" />

		<div
			class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white p-4"
		>
			<div>
				<h2 class="text-sm font-semibold text-gray-900">Project Sales Orders</h2>
				<p class="text-[12px] text-gray-500">
					Sales orders linked to this project's quotation and customer commitments.
				</p>
			</div>
			<div class="flex flex-wrap items-center gap-2">
				<Button
					v-if="quotation"
					variant="subtle"
					label="Open Quotation in Desk"
					:href="deskDocUrl('Quotation', quotation)"
					target="_blank"
				/>
				<Button
					variant="solid"
					label="Create Sales Order"
					:loading="creating"
					@click="createOrder"
				/>
			</div>
		</div>

		<div class="overflow-hidden rounded-xl border border-gray-200 bg-white">
			<div
				class="hidden grid-cols-[minmax(160px,1.3fr)_120px_100px_120px_110px_minmax(190px,auto)] items-center gap-3 border-b border-gray-200 bg-gray-50/70 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500 md:grid"
			>
				<div>Sales Order</div>
				<div>Status</div>
				<div>Delivery Date</div>
				<div>Fulfillment</div>
				<div class="text-right">Amount</div>
				<div class="text-right">Actions</div>
			</div>

			<p v-if="loading" class="px-4 py-6 text-sm text-gray-500">Loading project orders…</p>
			<div v-else-if="!items.length" class="px-4 py-8 text-center text-sm text-gray-500">
				No sales orders for this project yet. Submit the quotation and click
				<strong>Create Sales Order</strong>.
			</div>
			<ul v-else class="divide-y divide-gray-100">
				<li
					v-for="o in items"
					:key="o.name"
					class="grid grid-cols-1 items-center gap-2 px-4 py-3 md:grid-cols-[minmax(160px,1.3fr)_120px_100px_120px_110px_minmax(190px,auto)] md:gap-3"
				>
					<div>
						<div class="text-[13.5px] font-medium text-gray-900">{{ o.name }}</div>
						<div class="text-[12px] text-gray-500">
							{{ o.customer || "—" }} · {{ o.total_qty }} qty
						</div>
					</div>
					<div>
						<span
							class="inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium"
							:class="statusBadgeClass(o.status, o.docstatus)"
						>
							{{ o.status }}
						</span>
					</div>
					<div class="text-[12px] text-gray-600">{{ o.delivery_date || "—" }}</div>
					<div>
						<div class="flex items-center justify-between text-[11px] text-gray-500">
							<span>Delivered</span>
							<span class="tabular-nums">{{ o.per_delivered }}%</span>
						</div>
						<div class="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
							<div
								class="h-full rounded-full bg-blue-500 transition-all"
								:style="{ width: `${Math.min(100, o.per_delivered)}%` }"
							/>
						</div>
					</div>
					<div class="text-right text-[13px] font-medium tabular-nums text-gray-900">
						{{ formatMoney(o.amount) }}
					</div>
					<div class="flex flex-wrap items-center justify-end gap-1.5">
						<FlowDocActions
							:actions="orderActions(o.name)"
							:suppliers="flow?.suppliers"
							@done="onFlowDone"
						/>
						<Button
							size="sm"
							variant="subtle"
							label="Open"
							:href="deskDocUrl('Sales Order', o.name)"
							target="_blank"
						/>
					</div>
				</li>
			</ul>
		</div>
	</section>
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { computed, onMounted, ref, watch } from "vue";
import {
	getWorkspacePipeline,
	makeSalesOrder,
	type FlowAction,
	type PipelineOrderRow,
	type ProjectFlowState,
} from "@/api";
import { formatMoney } from "@/money";
import FlowDocActions from "./FlowDocActions.vue";
import PipelineStatGrid from "./PipelineStatGrid.vue";
import type { StatCardItem } from "./pipelineConfig";
import { deskDocUrl, statusBadgeClass } from "./statusStyle";

const props = defineProps<{
	project: string;
	quotation?: string | null;
	flow?: ProjectFlowState | null;
}>();
const emit = defineEmits<{ changed: [] }>();

const loading = ref(true);
const creating = ref(false);
const items = ref<PipelineOrderRow[]>([]);
const stats = ref<Record<string, number>>({});

const actionsByOrder = computed(() => {
	const map = new Map<string, FlowAction[]>();
	for (const so of props.flow?.sales_orders ?? []) {
		if (so.actions?.length) map.set(so.name, so.actions);
	}
	return map;
});

function orderActions(name: string): FlowAction[] {
	return actionsByOrder.value.get(name) ?? [];
}

async function onFlowDone() {
	await load();
	emit("changed");
}

watch(
	() => props.flow?.sales_orders,
	() => {
		void load();
	}
);

const statCards = computed<StatCardItem[]>(() => [
	{
		label: "Sales Orders",
		value: stats.value.total ?? 0,
		sublabel: `${stats.value.draft ?? 0} draft`,
		icon: "lucide-package",
	},
	{
		label: "To Deliver",
		value: stats.value.to_deliver ?? 0,
		sublabel: "Pending dispatch",
		icon: "lucide-truck",
	},
	{
		label: "Completed",
		value: stats.value.completed ?? 0,
		sublabel: "Delivered & billed",
		icon: "lucide-check-circle",
	},
	{
		label: "Order Value",
		value: formatMoney(stats.value.total_value ?? 0),
		sublabel: "Total committed",
		icon: "lucide-indian-rupee",
	},
]);

async function load() {
	loading.value = true;
	try {
		const res = await getWorkspacePipeline<PipelineOrderRow>("orders", props.project);
		items.value = res.items ?? [];
		stats.value = res.stats ?? {};
	} catch {
		items.value = [];
	} finally {
		loading.value = false;
	}
}

async function createOrder() {
	creating.value = true;
	try {
		const res = await makeSalesOrder(props.project);
		if (!res.ok) {
			toast.error(res.message);
			return;
		}
		toast.success(`Sales Order ${res.sales_order} created`);
		await load();
		emit("changed");
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Could not create Sales Order");
	} finally {
		creating.value = false;
	}
}

onMounted(load);
</script>
