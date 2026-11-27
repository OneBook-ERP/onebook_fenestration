<template>
	<section class="space-y-4" data-testid="bom-takeoff-panel">
		<Alert
			v-if="isFabricationPartner"
			theme="blue"
			title="Fabrication Partner — Raw Aluminium Frames & Materials Supply"
			description="This customer cuts and assembles windows themselves. Use the Material Quote, Sales Order, and Dispatch tabs to supply raw aluminium profiles and materials."
		/>

		<!-- Linked Procurement, Billing, Payments & Work Orders -->
		<div
			v-if="procurementCards.length"
			data-testid="production-flow-cards"
			class="rounded-xl border border-gray-200 bg-white p-3.5"
		>
			<div class="mb-2 flex items-center justify-between">
				<span class="text-[12px] font-semibold uppercase tracking-wide text-gray-500">
					Procurement, Receipts, Invoices &amp; Work Orders
				</span>
				<span class="text-[11px] text-gray-400">{{ procurementCards.length }} docs</span>
			</div>
			<div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
				<div
					v-for="doc in procurementCards"
					:key="`${doc.doctype}-${doc.name}`"
					class="flex flex-col justify-between gap-2 rounded-lg border border-gray-100 bg-gray-50/70 px-3 py-2 text-xs"
				>
					<div class="flex items-start justify-between gap-2">
						<a
							:href="deskDocUrl(doc.doctype, doc.name)"
							target="_blank"
							rel="noopener"
							class="min-w-0 flex-1 hover:underline"
						>
							<div class="truncate font-semibold text-gray-900">{{ doc.name }}</div>
							<div class="truncate text-[11px] text-gray-500">
								{{ doc.doctype }}{{ doc.subtitle ? ` · ${doc.subtitle}` : "" }}
							</div>
						</a>
						<span
							class="shrink-0 rounded px-1.5 py-0.5 text-[10.5px] font-medium"
							:class="statusBadgeClass(doc.status, doc.docstatus)"
						>
							{{ doc.status }}
						</span>
					</div>
					<FlowDocActions
						v-if="doc.actions?.length"
						:actions="doc.actions"
						:suppliers="flow?.suppliers"
						@done="onFlowDone"
					/>
				</div>
			</div>
		</div>

		<!-- Controls & Procurement Card -->
		<div class="space-y-3 rounded-xl border border-gray-200 bg-white p-4">
			<div class="flex flex-wrap items-center justify-between gap-2">
				<div
					class="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 text-xs"
				>
					<button
						type="button"
						data-testid="view-tree"
						class="rounded-md px-3 py-1.5 transition-colors"
						:class="
							viewMode === 'tree'
								? 'bg-gray-900 font-medium text-white shadow-sm'
								: 'text-gray-600 hover:text-gray-900'
						"
						@click="viewMode = 'tree'"
					>
						Window BOM Tree
					</button>
					<button
						type="button"
						data-testid="view-summary"
						class="rounded-md px-3 py-1.5 transition-colors"
						:class="
							viewMode === 'summary'
								? 'bg-gray-900 font-medium text-white shadow-sm'
								: 'text-gray-600 hover:text-gray-900'
						"
						@click="viewMode = 'summary'"
					>
						Consolidated PO Summary
					</button>
				</div>
				<Button label="Refresh" variant="subtle" :loading="loading" @click="load" />
			</div>

			<div
				v-if="!isFabricationPartner"
				class="grid grid-cols-1 items-end gap-3 border-t border-gray-100 pt-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_auto]"
			>
				<div>
					<label class="mb-1 block text-xs font-medium text-gray-600" for="bom-category"
						>Category</label
					>
					<select
						id="bom-category"
						v-model="category"
						class="h-9 w-full rounded-lg border border-gray-200 bg-white px-2.5 text-sm text-gray-800"
						data-testid="bom-category"
					>
						<option value="all">All Categories</option>
						<option value="Profile">Aluminium Profiles</option>
						<option value="Glass">Glass</option>
						<option value="Hardware">Hardware &amp; Gaskets</option>
					</select>
				</div>

				<div>
					<label class="mb-1 block text-xs font-medium text-gray-600" for="bom-warehouse"
						>Target Warehouse</label
					>
					<select
						id="bom-warehouse"
						v-model="warehouse"
						class="h-9 w-full rounded-lg border border-gray-200 bg-white px-2.5 text-sm text-gray-800"
						data-testid="bom-warehouse"
					>
						<option v-for="w in tree?.warehouses ?? []" :key="w.name" :value="w.name">
							{{ w.warehouse_name }}
						</option>
					</select>
				</div>

				<div>
					<label class="mb-1 block text-xs font-medium text-gray-600" for="bom-supplier"
						>Supplier (for direct PO)</label
					>
					<select
						id="bom-supplier"
						v-model="supplier"
						class="h-9 w-full rounded-lg border border-gray-200 bg-white px-2.5 text-sm text-gray-800"
						data-testid="bom-supplier"
					>
						<option value="">Select supplier</option>
						<option v-for="s in supplierOptions" :key="s.value" :value="s.value">
							{{ s.label }}
						</option>
					</select>
				</div>

				<div class="flex flex-wrap items-center gap-2">
					<Button
						class="h-9"
						label="Create Material Request"
						data-testid="create-mr"
						:loading="creatingMr"
						:disabled="loading || !hasItemsForCategory"
						@click="createMr"
					/>
					<Button
						class="h-9"
						variant="solid"
						label="Create Purchase Order"
						data-testid="create-po"
						:loading="creatingPo"
						:disabled="loading || !hasItemsForCategory || !supplier"
						@click="createPo"
					/>
				</div>
			</div>
		</div>

		<div
			v-if="createdDocs.length"
			class="flex flex-wrap items-center gap-2 rounded border border-green-200 bg-green-50 p-2.5 text-sm"
			data-testid="created-docs"
		>
			<span class="font-medium text-green-900">Created:</span>
			<a
				v-for="doc in createdDocs"
				:key="doc.href"
				:href="doc.href"
				target="_blank"
				rel="noopener"
				class="rounded border border-green-300 bg-white px-2 py-0.5 text-xs font-medium text-green-800 hover:underline"
			>
				{{ doc.label }}
			</a>
		</div>

		<div
			v-if="tree?.problems.length"
			class="rounded border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900"
			data-testid="bom-problems"
		>
			<p class="mb-1 font-semibold">Item / Engineering Warnings</p>
			<ul class="list-disc space-y-0.5 pl-4">
				<li v-for="(p, i) in tree.problems" :key="i">{{ p }}</li>
			</ul>
		</div>

		<p v-if="loading" class="text-sm text-ink-gray-5">Loading BOM takeoff…</p>
		<p v-else-if="!tree?.windows.length" class="text-sm text-ink-gray-5">
			No window designs in this project yet.
		</p>

		<div v-else-if="viewMode === 'tree'" class="space-y-4" data-testid="bom-tree-view">
			<article
				v-for="win in tree.windows"
				:key="win.name"
				class="overflow-hidden rounded-xl border border-gray-200 bg-white"
				data-testid="bom-window-node"
			>
				<header
					class="flex flex-wrap items-center gap-3 border-b border-gray-200 bg-gray-50/80 px-4 py-3"
				>
					<!-- Window Elevation Preview -->
					<div
						data-testid="bom-window-preview"
						class="flex size-20 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-white p-1.5 sm:size-24"
					>
						<img
							v-if="win.design_svg"
							:src="svgDataUri(win.design_svg)"
							:alt="`Elevation of ${win.design_ref}`"
							class="h-full w-full object-contain"
						/>
						<span
							v-else
							class="lucide-panels-top-left size-5 text-gray-300"
							aria-hidden="true"
						/>
					</div>

					<div class="min-w-0 flex-1">
						<div class="flex flex-wrap items-center gap-2">
							<span class="text-sm font-semibold text-gray-900">{{
								win.design_ref
							}}</span>
							<span v-if="win.design_name" class="text-sm text-gray-600"
								>· {{ win.design_name }}</span
							>
							<Badge size="sm" theme="blue" :label="`Qty ${win.qty}`" />
							<span class="text-xs text-gray-500">{{ win.series_version }}</span>
						</div>
						<div
							class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px] text-gray-500"
						>
							<span v-if="win.width_mm && win.height_mm"
								>{{ win.width_mm }} × {{ win.height_mm }} mm</span
							>
							<span v-if="win.finish">Finish: {{ win.finish }}</span>
							<span
								>{{ win.profiles.length }} profiles · {{ win.glass.length }} glass
								· {{ win.hardware.length }} hardware</span
							>
						</div>
					</div>

					<span
						v-if="win.floor || win.location"
						class="shrink-0 rounded-md bg-white px-2.5 py-1 text-xs font-medium text-gray-600 ring-1 ring-gray-200"
					>
						{{ [win.floor, win.location].filter(Boolean).join(" · ") }}
					</span>
				</header>

				<div class="divide-y">
					<div v-if="showCategory('Profile')" class="p-3">
						<h3
							class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
						>
							Profile
						</h3>
						<p v-if="!win.profiles.length" class="text-xs text-ink-gray-5">
							No profiles.
						</p>
						<div v-else class="space-y-2">
							<div
								v-for="prof in win.profiles"
								:key="prof.profile_code"
								class="rounded border p-2.5"
							>
								<div
									class="mb-1.5 flex flex-wrap items-center justify-between gap-2 text-xs"
								>
									<div>
										<span class="font-semibold text-ink-gray-9">{{
											prof.item_code || prof.profile_code
										}}</span>
										<span class="ml-1.5 text-ink-gray-6">{{
											prof.item_name
										}}</span>
									</div>
									<span class="font-medium tabular-nums text-ink-gray-8">
										{{ prof.pieces }} pcs · {{ prof.total_mm.toFixed(0) }} mm ·
										{{ prof.kg.toFixed(3) }} kg
									</span>
								</div>
								<table class="w-full text-xs">
									<thead>
										<tr class="border-b text-left text-ink-gray-5">
											<th class="py-1 pr-2">Role</th>
											<th class="py-1 pr-2">Cut Length (mm)</th>
											<th class="py-1 pr-2">Angles</th>
											<th class="py-1 pr-2 text-right">Pieces</th>
											<th class="py-1 text-right">Weight (kg)</th>
										</tr>
									</thead>
									<tbody>
										<tr
											v-for="(cut, idx) in prof.cuts"
											:key="idx"
											class="border-b last:border-0"
										>
											<td class="py-1 pr-2 capitalize">{{ cut.role }}</td>
											<td class="py-1 pr-2 font-medium tabular-nums">
												{{ cut.length_mm }}
											</td>
											<td class="py-1 pr-2 tabular-nums text-ink-gray-6">
												{{ cut.angles || "—" }}
											</td>
											<td class="py-1 pr-2 text-right tabular-nums">
												{{ cut.pieces }}
											</td>
											<td class="py-1 text-right tabular-nums">
												{{ cut.kg.toFixed(3) }}
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</div>
					</div>

					<div v-if="showCategory('Glass')" class="p-3">
						<h3
							class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
						>
							Glass
						</h3>
						<p v-if="!win.glass.length" class="text-xs text-ink-gray-5">
							No glass panes.
						</p>
						<div v-else class="space-y-2">
							<div
								v-for="g in win.glass"
								:key="g.glass_code"
								class="rounded border p-2.5"
							>
								<div
									class="mb-1.5 flex flex-wrap items-center justify-between gap-2 text-xs"
								>
									<div>
										<span class="font-semibold text-ink-gray-9">{{
											g.item_code || g.glass_code
										}}</span>
										<span class="ml-1.5 text-ink-gray-6">{{
											g.item_name
										}}</span>
									</div>
									<span class="font-medium tabular-nums text-ink-gray-8">
										{{ g.pieces }} panes · {{ g.area_m2.toFixed(3) }} m²
									</span>
								</div>
								<table class="w-full text-xs">
									<thead>
										<tr class="border-b text-left text-ink-gray-5">
											<th class="py-1 pr-2">Pane Size (W × H mm)</th>
											<th class="py-1 pr-2 text-right">Pieces</th>
											<th class="py-1 text-right">Area (m²)</th>
										</tr>
									</thead>
									<tbody>
										<tr
											v-for="(pane, idx) in g.panes"
											:key="idx"
											class="border-b last:border-0"
										>
											<td class="py-1 pr-2 font-medium tabular-nums">
												{{ pane.width_mm }} × {{ pane.height_mm }} mm
											</td>
											<td class="py-1 pr-2 text-right tabular-nums">
												{{ pane.pieces }}
											</td>
											<td class="py-1 text-right tabular-nums">
												{{ pane.area_m2.toFixed(3) }}
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</div>
					</div>

					<div v-if="showCategory('Hardware')" class="p-3">
						<h3
							class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
						>
							Other Hardware &amp; Gaskets
						</h3>
						<p v-if="!win.hardware.length" class="text-xs text-ink-gray-5">
							No hardware or gaskets.
						</p>
						<table v-else class="w-full text-xs">
							<thead>
								<tr class="border-b text-left text-ink-gray-5">
									<th class="py-1 pr-2">Item Code</th>
									<th class="py-1 pr-2">Name</th>
									<th class="py-1 pr-2">Group</th>
									<th class="py-1 pr-2 text-right">Qty</th>
									<th class="py-1">UOM</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="hw in win.hardware"
									:key="`${hw.item_code}-${hw.uom}`"
									class="border-b last:border-0"
								>
									<td class="py-1 pr-2 font-medium">{{ hw.item_code }}</td>
									<td class="py-1 pr-2">{{ hw.item_name }}</td>
									<td class="py-1 pr-2 text-ink-gray-6">{{ hw.group }}</td>
									<td class="py-1 pr-2 text-right tabular-nums">{{ hw.qty }}</td>
									<td class="py-1">{{ hw.uom }}</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</article>
		</div>

		<div v-else class="space-y-4" data-testid="bom-summary-view">
			<div v-if="showCategory('Profile')" class="rounded-lg border bg-surface-white p-3">
				<h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6">
					Consolidated Aluminium Profiles (With Cut Lengths)
				</h3>
				<table class="w-full text-xs">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="py-1.5 pr-2">Item</th>
							<th class="py-1.5 pr-2">Name</th>
							<th class="py-1.5 pr-2 text-right">Cut Length (mm)</th>
							<th class="py-1.5 pr-2 text-right">Pieces</th>
							<th class="py-1.5 pr-2 text-right">Qty (Kg)</th>
							<th class="py-1.5">Default Supplier</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="p in tree.summary.profiles"
							:key="`${p.item_code}-${p.cut_length_mm}`"
							class="border-b last:border-0"
						>
							<td class="py-1.5 pr-2 font-semibold">
								{{ p.item_code || p.profile_code }}
							</td>
							<td class="py-1.5 pr-2">{{ p.item_name }}</td>
							<td class="py-1.5 pr-2 text-right tabular-nums">
								{{ p.cut_length_mm }}
							</td>
							<td class="py-1.5 pr-2 text-right tabular-nums">{{ p.pieces }}</td>
							<td class="py-1.5 pr-2 text-right font-medium tabular-nums">
								{{ p.kg.toFixed(3) }}
							</td>
							<td class="py-1.5 text-ink-gray-6">{{ p.default_supplier || "—" }}</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div v-if="showCategory('Glass')" class="rounded-lg border bg-surface-white p-3">
				<h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6">
					Consolidated Glass Panes
				</h3>
				<table class="w-full text-xs">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="py-1.5 pr-2">Item</th>
							<th class="py-1.5 pr-2">Name</th>
							<th class="py-1.5 pr-2">Pane Size</th>
							<th class="py-1.5 pr-2 text-right">Pieces</th>
							<th class="py-1.5 pr-2 text-right">Area (m²)</th>
							<th class="py-1.5">Default Supplier</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="g in tree.summary.glass"
							:key="`${g.item_code}-${g.width_mm}-${g.height_mm}`"
							class="border-b last:border-0"
						>
							<td class="py-1.5 pr-2 font-semibold">
								{{ g.item_code || g.glass_code }}
							</td>
							<td class="py-1.5 pr-2">{{ g.item_name }}</td>
							<td class="py-1.5 pr-2 tabular-nums">
								{{ g.width_mm }} × {{ g.height_mm }} mm
							</td>
							<td class="py-1.5 pr-2 text-right tabular-nums">{{ g.pieces }}</td>
							<td class="py-1.5 pr-2 text-right font-medium tabular-nums">
								{{ g.area_m2.toFixed(3) }}
							</td>
							<td class="py-1.5 text-ink-gray-6">{{ g.default_supplier || "—" }}</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div v-if="showCategory('Hardware')" class="rounded-lg border bg-surface-white p-3">
				<h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6">
					Consolidated Hardware &amp; Gaskets
				</h3>
				<table class="w-full text-xs">
					<thead>
						<tr class="border-b text-left text-ink-gray-5">
							<th class="py-1.5 pr-2">Item</th>
							<th class="py-1.5 pr-2">Name</th>
							<th class="py-1.5 pr-2">Group</th>
							<th class="py-1.5 pr-2 text-right">Qty</th>
							<th class="py-1.5 pr-2">UOM</th>
							<th class="py-1.5">Default Supplier</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="h in tree.summary.hardware"
							:key="`${h.item_code}-${h.uom}`"
							class="border-b last:border-0"
						>
							<td class="py-1.5 pr-2 font-semibold">{{ h.item_code }}</td>
							<td class="py-1.5 pr-2">{{ h.item_name }}</td>
							<td class="py-1.5 pr-2 text-ink-gray-6">{{ h.group }}</td>
							<td class="py-1.5 pr-2 text-right font-medium tabular-nums">
								{{ h.qty }}
							</td>
							<td class="py-1.5 pr-2">{{ h.uom }}</td>
							<td class="py-1.5 text-ink-gray-6">{{ h.default_supplier || "—" }}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</section>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, toast, useList } from "frappe-ui";
import { computed, onMounted, ref } from "vue";
import {
	getWorkspacePipeline,
	makeProjectMaterialRequest,
	makeProjectPurchaseOrder,
	materialTree,
	type FlowAction,
	type MaterialTree,
	type PipelineProductionRow,
	type ProjectFlowState,
} from "@/api";
import FlowDocActions from "@/components/workspace/FlowDocActions.vue";
import { deskDocUrl, statusBadgeClass } from "@/components/workspace/statusStyle";
import { formatMoney } from "@/money";

const props = defineProps<{ project: string; flow?: ProjectFlowState | null }>();
const emit = defineEmits<{ changed: [] }>();
const isFabricationPartner = computed(() => props.flow?.partner_type === "Fabrication Partner");

const tree = ref<MaterialTree | null>(null);
const linkedDocs = ref<PipelineProductionRow[]>([]);
const loading = ref(false);
const viewMode = ref<"tree" | "summary">("tree");
const category = ref<"all" | "Profile" | "Glass" | "Hardware">("all");
const warehouse = ref<string>("");
const supplier = ref<string>("");
const creatingMr = ref(false);
const creatingPo = ref(false);
const createdDocs = ref<{ label: string; href: string }[]>([]);

const supplierList = useList<{ name: string; supplier_name?: string }>({
	doctype: "Supplier",
	fields: ["name", "supplier_name"],
	limit: 500,
});
const supplierOptions = computed(() =>
	(supplierList.data ?? []).map((s) => ({ label: s.supplier_name || s.name, value: s.name }))
);

function showCategory(cat: "Profile" | "Glass" | "Hardware"): boolean {
	return category.value === "all" || category.value === cat;
}

function svgDataUri(svg: string): string {
	return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
}

const hasItemsForCategory = computed(() => {
	const s = tree.value?.summary;
	if (!s) return false;
	if (category.value === "Profile") return s.profiles.length > 0;
	if (category.value === "Glass") return s.glass.length > 0;
	if (category.value === "Hardware") return s.hardware.length > 0;
	return s.profiles.length + s.glass.length + s.hardware.length > 0;
});

async function loadLinkedDocs() {
	try {
		if (typeof getWorkspacePipeline === "function") {
			const res = await getWorkspacePipeline<PipelineProductionRow>(
				"production",
				props.project
			);
			linkedDocs.value = res.items ?? [];
		}
	} catch {
		linkedDocs.value = [];
	}
}

async function load() {
	loading.value = true;
	try {
		const data = await materialTree(props.project);
		tree.value = data;
		if (!warehouse.value && data.default_warehouse) {
			warehouse.value = data.default_warehouse;
		}
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Could not load project BOM takeoff");
	} finally {
		loading.value = false;
	}
	loadLinkedDocs();
}

interface ProcurementCard {
	doctype: string;
	name: string;
	subtitle: string;
	status: string;
	docstatus: number;
	actions?: FlowAction[];
}

const procurementCards = computed<ProcurementCard[]>(() => {
	const cards: ProcurementCard[] = [];
	const seen = new Set<string>();
	const pushCard = (c: ProcurementCard) => {
		const key = `${c.doctype}-${c.name}`;
		if (seen.has(key)) return;
		seen.add(key);
		cards.push(c);
	};

	const f = props.flow;
	if (f) {
		for (const mr of f.material_requests ?? []) {
			pushCard({
				doctype: "Material Request",
				name: mr.name,
				subtitle: String(mr.schedule_date || mr.material_request_type || ""),
				status: mr.status,
				docstatus: mr.docstatus,
				actions: mr.actions,
			});
		}
		for (const po of f.purchase_orders ?? []) {
			pushCard({
				doctype: "Purchase Order",
				name: po.name,
				subtitle: [
					po.supplier_name || po.supplier,
					po.grand_total != null ? formatMoney(Number(po.grand_total)) : "",
				]
					.filter(Boolean)
					.join(" · "),
				status: po.status,
				docstatus: po.docstatus,
				actions: po.actions,
			});
		}
		for (const pr of f.purchase_receipts ?? []) {
			pushCard({
				doctype: "Purchase Receipt",
				name: pr.name,
				subtitle: [pr.supplier_name || pr.supplier, pr.posting_date]
					.filter(Boolean)
					.join(" · "),
				status: pr.status,
				docstatus: pr.docstatus,
				actions: pr.actions,
			});
		}
		for (const pi of f.purchase_invoices ?? []) {
			pushCard({
				doctype: "Purchase Invoice",
				name: pi.name,
				subtitle: [
					pi.supplier_name || pi.supplier,
					pi.grand_total != null ? formatMoney(Number(pi.grand_total)) : "",
				]
					.filter(Boolean)
					.join(" · "),
				status: pi.status,
				docstatus: pi.docstatus,
				actions: pi.actions,
			});
		}
		for (const pe of f.payment_entries ?? []) {
			if (pe.payment_type !== "Pay") continue;
			pushCard({
				doctype: "Payment Entry",
				name: pe.name,
				subtitle: [
					pe.party_name || pe.party,
					pe.paid_amount != null ? formatMoney(Number(pe.paid_amount)) : "",
				]
					.filter(Boolean)
					.join(" · "),
				status: pe.status,
				docstatus: pe.docstatus,
				actions: pe.actions,
			});
		}
	}

	for (const doc of linkedDocs.value) {
		pushCard({
			doctype: doc.doctype,
			name: doc.name,
			subtitle: doc.subtitle || "",
			status: doc.status,
			docstatus: doc.docstatus,
		});
	}
	return cards;
});

function onFlowDone() {
	void loadLinkedDocs();
	emit("changed");
}

async function createMr() {
	creatingMr.value = true;
	try {
		const res = await makeProjectMaterialRequest(
			props.project,
			category.value,
			warehouse.value || null
		);
		createdDocs.value.unshift({
			label: `Material Request: ${res.material_request}`,
			href: `/app/material-request/${encodeURIComponent(res.material_request)}`,
		});
		toast.success(`Created Material Request ${res.material_request}`);
		loadLinkedDocs();
		emit("changed");
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Could not create Material Request");
	} finally {
		creatingMr.value = false;
	}
}

async function createPo() {
	if (!supplier.value) return;
	creatingPo.value = true;
	try {
		const res = await makeProjectPurchaseOrder(
			props.project,
			supplier.value,
			category.value,
			warehouse.value || null
		);
		createdDocs.value.unshift({
			label: `Purchase Order: ${res.purchase_order}`,
			href: `/app/purchase-order/${encodeURIComponent(res.purchase_order)}`,
		});
		toast.success(`Created Purchase Order ${res.purchase_order}`);
		loadLinkedDocs();
		emit("changed");
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Could not create Purchase Order");
	} finally {
		creatingPo.value = false;
	}
}

onMounted(load);
</script>
