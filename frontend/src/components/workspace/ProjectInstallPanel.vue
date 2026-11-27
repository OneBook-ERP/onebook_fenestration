<template>
	<section class="space-y-4" data-testid="project-install-panel">
		<PipelineStatGrid :cards="statCards" />

		<div class="rounded-xl border border-gray-200 bg-white p-4">
			<h2 class="text-sm font-semibold text-gray-900">Site &amp; Installation Details</h2>
			<div class="mt-2 grid gap-3 text-[13px] sm:grid-cols-2">
				<div>
					<span class="text-xs text-gray-500">Customer</span>
					<p class="font-medium text-gray-900">
						{{ customer || "No customer assigned" }}
					</p>
				</div>
				<div>
					<span class="text-xs text-gray-500">Site Address</span>
					<p class="whitespace-pre-line font-medium text-gray-900">
						{{ siteAddress || "No site address recorded" }}
					</p>
				</div>
			</div>
		</div>

		<div class="overflow-hidden rounded-xl border border-gray-200 bg-white">
			<div
				class="border-b border-gray-200 bg-gray-50/70 px-4 py-2.5 text-[12px] font-semibold text-gray-700"
			>
				Delivery Notes &amp; Site Dispatch
			</div>

			<p v-if="loading" class="px-4 py-6 text-sm text-gray-500">
				Loading delivery &amp; install records…
			</p>
			<div
				v-else-if="!items.length && !pendingOrders.length"
				class="px-4 py-8 text-center text-sm text-gray-500"
			>
				No deliveries or pending dispatch orders for this project yet.
			</div>
			<ul v-else class="divide-y divide-gray-100">
				<li
					v-for="dn in items"
					:key="dn.name"
					class="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
				>
					<div>
						<div class="flex items-center gap-2">
							<span class="text-[13.5px] font-medium text-gray-900">{{
								dn.name
							}}</span>
							<span
								class="inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium"
								:class="statusBadgeClass(dn.status, dn.docstatus)"
							>
								{{ dn.status }}
							</span>
						</div>
						<div class="mt-0.5 text-[12px] text-gray-500">
							{{ dn.posting_date }} · {{ dn.total_qty }} windows ·
							{{ dn.per_installed }}% installed
						</div>
					</div>
					<div class="flex flex-wrap items-center gap-1.5">
						<FlowDocActions :actions="dnActions(dn.name)" @done="onFlowDone" />
						<Button
							size="sm"
							variant="subtle"
							label="Open in Desk"
							:href="deskDocUrl('Delivery Note', dn.name)"
							target="_blank"
						/>
					</div>
				</li>

				<li
					v-for="so in pendingOrders"
					:key="so.name"
					class="flex flex-wrap items-center justify-between gap-3 bg-amber-50/30 px-4 py-3"
				>
					<div>
						<div class="flex items-center gap-2">
							<span class="text-[13.5px] font-medium text-gray-900">{{
								so.name
							}}</span>
							<span
								class="inline-flex rounded-md bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
							>
								Pending Dispatch
							</span>
						</div>
						<div class="mt-0.5 text-[12px] text-gray-500">
							Due {{ so.delivery_date || "unscheduled" }} ·
							{{ so.total_qty }} windows · {{ so.per_delivered }}% delivered
						</div>
					</div>
					<div class="flex flex-wrap items-center gap-1.5">
						<FlowDocActions :actions="soInstallActions(so.name)" @done="onFlowDone" />
						<Button
							size="sm"
							variant="subtle"
							label="Open in Desk"
							:href="deskDocUrl('Sales Order', so.name)"
							target="_blank"
						/>
					</div>
				</li>
			</ul>
		</div>

		<div
			v-if="billingDocs.length"
			data-testid="install-billing-docs"
			class="overflow-hidden rounded-xl border border-gray-200 bg-white"
		>
			<div
				class="border-b border-gray-200 bg-gray-50/70 px-4 py-2.5 text-[12px] font-semibold text-gray-700"
			>
				Sales Invoices &amp; Customer Payments
			</div>
			<ul class="divide-y divide-gray-100">
				<li
					v-for="doc in billingDocs"
					:key="`${doc.doctype}-${doc.name}`"
					class="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
				>
					<div>
						<div class="flex items-center gap-2">
							<span class="text-[13.5px] font-medium text-gray-900">{{
								doc.name
							}}</span>
							<span class="text-[11px] text-gray-500">{{ doc.doctype }}</span>
							<span
								class="inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium"
								:class="statusBadgeClass(doc.status, doc.docstatus)"
							>
								{{ doc.status }}
							</span>
						</div>
						<div class="mt-0.5 text-[12px] text-gray-500">
							{{ doc.subtitle }}
						</div>
					</div>
					<div class="flex flex-wrap items-center gap-1.5">
						<FlowDocActions :actions="doc.actions" @done="onFlowDone" />
						<Button
							size="sm"
							variant="subtle"
							label="Open"
							:href="deskDocUrl(doc.doctype, doc.name)"
							target="_blank"
						/>
					</div>
				</li>
			</ul>
		</div>
	</section>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed, onMounted, ref, watch } from "vue";
import {
	getWorkspacePipeline,
	type FlowAction,
	type PipelineInstallRow,
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
	customer?: string | null;
	siteAddress?: string | null;
	flow?: ProjectFlowState | null;
}>();
const emit = defineEmits<{ changed: [] }>();

const loading = ref(true);
const items = ref<PipelineInstallRow[]>([]);
const pendingOrders = ref<PipelineOrderRow[]>([]);
const stats = ref<Record<string, number>>({});

const statCards = computed<StatCardItem[]>(() => [
	{
		label: "Delivery Notes",
		value: stats.value.total_deliveries ?? 0,
		sublabel: "Site shipments",
		icon: "lucide-truck",
	},
	{
		label: "Pending Dispatch",
		value: stats.value.pending_dispatch ?? 0,
		sublabel: "Confirmed orders awaiting delivery",
		icon: "lucide-clock",
	},
	{
		label: "Windows Dispatched",
		value: stats.value.dispatched_qty ?? 0,
		sublabel: "Delivered units",
		icon: "lucide-package-check",
	},
	{
		label: "Completed Installs",
		value: stats.value.installed_count ?? 0,
		sublabel: "100% installed deliveries",
		icon: "lucide-wrench",
	},
]);

function dnActions(name: string): FlowAction[] {
	return props.flow?.delivery_notes?.find((d) => d.name === name)?.actions ?? [];
}

function soInstallActions(name: string): FlowAction[] {
	const acts = props.flow?.sales_orders?.find((s) => s.name === name)?.actions ?? [];
	return acts.filter(
		(a) => a.target_doctype === "Delivery Note" || a.target_doctype === "Sales Invoice"
	);
}

const billingDocs = computed(() => {
	const out: Array<{
		doctype: string;
		name: string;
		status: string;
		docstatus: number;
		subtitle: string;
		actions?: FlowAction[];
	}> = [];
	for (const si of props.flow?.sales_invoices ?? []) {
		out.push({
			doctype: "Sales Invoice",
			name: si.name,
			status: si.status,
			docstatus: si.docstatus,
			subtitle: [
				si.posting_date,
				si.grand_total != null ? formatMoney(Number(si.grand_total)) : "",
			]
				.filter(Boolean)
				.join(" · "),
			actions: si.actions,
		});
	}
	for (const pe of props.flow?.payment_entries ?? []) {
		if (pe.payment_type !== "Receive") continue;
		out.push({
			doctype: "Payment Entry",
			name: pe.name,
			status: pe.status,
			docstatus: pe.docstatus,
			subtitle: [
				pe.posting_date,
				pe.paid_amount != null ? formatMoney(Number(pe.paid_amount)) : "",
			]
				.filter(Boolean)
				.join(" · "),
			actions: pe.actions,
		});
	}
	return out;
});

async function load() {
	loading.value = true;
	try {
		const res = await getWorkspacePipeline<PipelineInstallRow>("install", props.project);
		items.value = res.items ?? [];
		pendingOrders.value = res.pending_orders ?? [];
		stats.value = res.stats ?? {};
	} catch {
		items.value = [];
		pendingOrders.value = [];
	} finally {
		loading.value = false;
	}
}

async function onFlowDone() {
	await load();
	emit("changed");
}

watch(
	() => [props.flow?.delivery_notes, props.flow?.sales_invoices],
	() => {
		void load();
	}
);

onMounted(load);
</script>
