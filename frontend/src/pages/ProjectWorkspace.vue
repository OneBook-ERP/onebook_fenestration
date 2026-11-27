<template>
	<div class="p-6">
		<header data-testid="project-header" class="mb-4">
			<nav aria-label="Breadcrumb" class="mb-1 text-sm text-ink-gray-5">
				<router-link
					to="/projects"
					data-testid="breadcrumb-projects"
					class="hover:text-ink-gray-8"
					>Projects</router-link
				>
				<span aria-hidden="true"> / </span>
				<span>{{ project }}</span>
			</nav>
			<div class="flex flex-wrap items-center gap-2.5">
				<h1 class="text-xl font-semibold">{{ info?.project_title || project }}</h1>
				<Badge :theme="badge.theme" :label="badge.label" data-testid="quote-badge" />
				<Badge
					:theme="partnerBadgeTheme"
					variant="subtle"
					:label="partnerBadgeLabel"
					data-testid="partner-type-badge"
				/>
				<Badge
					v-if="isDealer && isSharedWithHilux"
					theme="green"
					variant="subtle"
					:label="manufacturingStatus"
					data-testid="share-status-badge"
				/>
				<Badge
					v-if="isDesignLocked"
					theme="amber"
					variant="outline"
					label="Designs Locked"
					data-testid="design-locked-badge"
				/>
				<span v-if="quote?.quotation" class="text-sm text-ink-gray-5">{{
					quote.quotation
				}}</span>

				<div class="ml-auto flex flex-wrap items-center gap-2">
					<Button
						v-if="isDealer && (!isSharedWithHilux || !isDesignLocked)"
						size="sm"
						variant="solid"
						icon-left="lucide-share-2"
						:label="
							isSharedWithHilux ? 'Re-share Updates to Hilux' : 'Share with Hilux'
						"
						:disabled="!designs.length"
						data-testid="share-with-hilux-btn"
						@click="openShareDialog"
					/>
					<Button
						v-if="isDealer && isSharedWithHilux && isDesignLocked"
						size="sm"
						variant="subtle"
						icon-left="lucide-unlock"
						label="Unlock for Revision"
						:loading="unlocking"
						data-testid="unlock-designs-btn"
						@click="handleUnlockDesigns"
					/>
					<Dropdown
						v-if="isDealer && isSharedWithHilux && flowState?.is_hilux_staff"
						:options="manufacturingStatusOptions"
					>
						<Button
							size="sm"
							variant="subtle"
							icon-right="lucide-chevron-down"
							:label="manufacturingStatus"
							data-testid="manufacturing-status-dropdown"
						/>
					</Dropdown>
				</div>
			</div>
			<dl class="mt-3 grid grid-cols-2 gap-3 sm:flex sm:flex-wrap">
				<div
					v-for="k in kpis"
					:key="k.id"
					:data-testid="`kpi-${k.id}`"
					class="rounded-xl border border-gray-200 bg-white px-4 py-3 sm:min-w-32 sm:flex-1"
				>
					<dt class="text-[12px] font-medium text-gray-500">{{ k.label }}</dt>
					<dd class="mt-0.5 text-lg font-semibold tracking-tight text-gray-900">
						{{ k.value }}
					</dd>
				</div>
			</dl>
		</header>

		<div
			role="tablist"
			aria-label="Project sections"
			class="mb-4 flex gap-1 overflow-x-auto border-b"
		>
			<button
				v-for="t in tabs"
				:id="`tab-${t.id}`"
				:key="t.id"
				type="button"
				role="tab"
				class="min-h-9 shrink-0 whitespace-nowrap border-b-2 px-3 text-sm"
				:class="tabClass(t)"
				:aria-selected="activeTab === t.id"
				:aria-disabled="t.disabled ? 'true' : undefined"
				:aria-describedby="t.disabled ? 'tab-soon-hint' : undefined"
				:title="t.disabled ? 'Coming soon' : undefined"
				@click="selectTab(t)"
			>
				{{ t.label }}
			</button>
		</div>
		<span id="tab-soon-hint" class="sr-only">Coming soon</span>

		<div role="tabpanel" :aria-labelledby="`tab-${activeTab}`">
			<QuotePanel
				v-if="activeTab === 'quote'"
				:project="project"
				:info="info"
				:flow="flowState"
				@changed="onQuoteChanged"
				@repriced="onRepriced"
			/>
			<ProjectOrderPanel
				v-if="activeTab === 'order'"
				:project="project"
				:quotation="quote?.quotation || info?.quotation"
				:flow="flowState"
				@changed="onQuoteChanged"
			/>
			<BomTakeoffPanel
				v-if="activeTab === 'production'"
				:project="project"
				:flow="flowState"
				@changed="onQuoteChanged"
			/>
			<ProjectInstallPanel
				v-if="activeTab === 'install'"
				:project="project"
				:customer="info?.customer"
				:site-address="info?.site_address"
				:flow="flowState"
				@changed="onQuoteChanged"
			/>
			<ProjectReportsPanel
				v-if="activeTab === 'reports'"
				:project="project"
				:quotation="quote?.quotation || info?.quotation"
			/>

			<template v-if="activeTab === 'designs'">
				<div class="mb-4 flex flex-wrap items-center gap-4">
					<FormControl
						v-model="search"
						class="ml-auto w-56"
						type="text"
						placeholder="Search designs"
						aria-label="Search designs"
					/>
					<Dropdown :options="templateOptions">
						<Button
							class="min-h-9"
							variant="solid"
							data-testid="new-design"
							:disabled="!info?.default_series_version"
							>New design</Button
						>
					</Dropdown>
				</div>

				<p v-if="designsLoading" class="text-sm text-ink-gray-5">Loading designs…</p>
				<p v-else-if="!designs.length" class="text-sm text-ink-gray-5">No designs yet.</p>
				<p v-else-if="!shown.length" class="text-sm text-ink-gray-5">No designs match.</p>
				<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
					<article
						v-for="d in shown"
						:key="d.name"
						data-testid="design-card"
						class="flex flex-col overflow-hidden rounded-xl border border-gray-200 bg-white transition-shadow hover:shadow-sm"
					>
						<div
							class="flex h-64 items-center justify-center border-b p-1.5"
							:class="thumbSrc(d) ? 'bg-white' : 'bg-surface-gray-1'"
						>
							<img
								v-if="thumbSrc(d)"
								:src="thumbSrc(d)"
								:alt="`Elevation of ${d.design_ref}`"
								class="h-full w-full object-contain"
							/>
							<span v-else class="text-xs text-ink-gray-5">No preview</span>
						</div>
						<div class="flex flex-1 flex-col gap-1.5 p-2.5">
							<div class="flex items-center gap-1.5">
								<span class="truncate text-sm font-semibold text-ink-gray-9"
									>{{ d.design_ref }} · {{ typologyOf(d) }}</span
								>
								<span class="shrink-0 text-xs text-ink-gray-5">× {{ d.qty }}</span>
								<Badge
									v-if="d.error_count"
									class="ml-auto shrink-0"
									size="sm"
									theme="red"
									:label="`${d.error_count} errors`"
								/>
								<Badge
									v-else-if="d.warning_count"
									class="ml-auto shrink-0"
									size="sm"
									theme="amber"
									:label="`${d.warning_count} warnings`"
								/>
								<Badge
									v-else
									class="ml-auto shrink-0"
									size="sm"
									theme="green"
									label="OK"
								/>
							</div>
							<p
								class="truncate text-xs text-ink-gray-6"
								:title="`${d.series_version}${
									dimensionsOf(d) ? ' · ' + dimensionsOf(d) : ''
								} · ${glassOf(d)}`"
							>
								{{ d.series_version
								}}<template v-if="dimensionsOf(d)">
									· {{ dimensionsOf(d) }}</template
								>
								· {{ glassOf(d) }}
							</p>
							<div
								class="flex items-center justify-between gap-2 text-xs text-ink-gray-6"
							>
								<span class="flex min-w-0 items-center gap-1.5">
									<span
										data-testid="finish-swatch"
										class="inline-block size-2.5 shrink-0 rounded-full border"
										:style="{ backgroundColor: finishColor(d.finish) }"
										aria-hidden="true"
									></span>
									<span class="truncate">{{ finishName(d.finish) }}</span>
								</span>
								<span class="shrink-0 tabular-nums text-ink-gray-5"
									>{{ fixed(d.area_sqft, 3) }} sq.ft ·
									{{ fixed(d.window_kg, 1) }} kg</span
								>
							</div>
							<div
								v-if="d.floor || d.location"
								data-testid="design-card-placement"
								class="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-ink-gray-5"
							>
								<span v-if="d.floor"
									>Floor:
									<span class="font-medium text-ink-gray-8">{{
										d.floor
									}}</span></span
								>
								<span v-if="d.location"
									>Location:
									<span class="font-medium text-ink-gray-8">{{
										d.location
									}}</span></span
								>
							</div>
							<div
								class="mt-auto flex items-end justify-between gap-2 rounded-md bg-surface-gray-1 px-2 py-1.5 text-xs"
							>
								<div class="leading-tight">
									<p class="font-semibold text-ink-gray-9 tabular-nums">
										Line {{ money(d.line_total) }}
									</p>
									<p class="text-[11px] text-ink-gray-5 tabular-nums">
										{{ money(d.unit_price) }} each
									</p>
								</div>
								<p v-if="pricedOn(d)" class="shrink-0 text-[11px] text-ink-gray-5">
									Priced {{ pricedOn(d) }}
								</p>
							</div>
							<div class="flex items-center gap-1.5 pt-0.5">
								<Button
									size="sm"
									variant="subtle"
									label="Edit design"
									data-testid="edit-design"
									:route="`/projects/${project}/designs/${d.name}`"
								/>
								<Button
									size="sm"
									variant="subtle"
									label="Duplicate"
									data-testid="duplicate-design"
									:disabled="duplicating"
									@click="duplicate(d.name)"
								/>
								<Tooltip text="Cutting Sheet PDF">
									<Button
										size="sm"
										variant="subtle"
										icon="lucide-file-text"
										aria-label="Cutting sheet PDF"
										data-testid="card-cutting-sheet"
										:href="
											printPdfUrl(
												'Window Design',
												d.name,
												'Window Cutting Sheet'
											)
										"
										target="_blank"
									/>
								</Tooltip>
								<Button
									size="sm"
									class="ml-auto text-red-600 hover:text-red-700 hover:bg-red-50"
									variant="subtle"
									label="Delete"
									data-testid="delete-design"
									:disabled="deleting"
									@click="promptDelete(d)"
								/>
							</div>
						</div>
					</article>
				</div>
			</template>
		</div>

		<Dialog
			v-model="showShareDialog"
			title="Share Project with Hilux"
			:options="{ title: 'Share Project with Hilux' }"
		>
			<div class="space-y-3 text-sm">
				<p class="text-ink-gray-7">
					Share
					<strong class="text-ink-gray-9">{{ info?.project_title || project }}</strong>
					with Hilux so the engineering and factory team can access your window designs
					and fabrication reports to procure materials, manufacture windows, and deliver
					them to you.
				</p>
				<div
					class="grid grid-cols-2 gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3"
				>
					<div>
						<div class="text-xs text-gray-500">Designs</div>
						<div class="font-semibold text-gray-900">
							{{ designs.length }} designs ({{ totals.windows }} windows)
						</div>
					</div>
					<div>
						<div class="text-xs text-gray-500">Validation Status</div>
						<div class="mt-0.5">
							<Badge
								:theme="erroredDesigns.length ? 'red' : 'green'"
								variant="subtle"
								:label="
									erroredDesigns.length
										? `${erroredDesigns.length} design(s) with errors`
										: 'Ready for manufacturing'
								"
							/>
						</div>
					</div>
				</div>
				<div class="rounded-lg border border-gray-200 bg-white p-3">
					<div class="mb-1.5 text-xs font-medium text-gray-600">
						Shared Manufacturing Pack
					</div>
					<ul class="list-disc space-y-0.5 pl-4 text-xs text-gray-600">
						<li>
							All {{ designs.length }} Window Designs (2D / 3D geometry &amp; series
							specs)
						</li>
						<li>
							Elevation Report, Cutting Sheet, Assembly Summary &amp; Assembly Detail
							PDFs
						</li>
						<li>Consolidated BOM Material Takeoff for procurement &amp; production</li>
					</ul>
				</div>
				<FormControl
					v-model="shareNotes"
					type="textarea"
					label="Handover notes for Hilux (optional)"
					placeholder="Delivery timeline, finish preferences, site handling instructions..."
					:rows="3"
				/>
				<FormControl
					v-model="shareLockDesigns"
					type="checkbox"
					label="Lock window designs once shared so manufacturing uses this exact revision"
				/>
				<p v-if="shareError" class="text-xs font-medium text-red-600">{{ shareError }}</p>
			</div>
			<template #actions>
				<Button variant="subtle" label="Cancel" @click="showShareDialog = false" />
				<Button
					class="ml-2"
					variant="solid"
					label="Share with Hilux"
					data-testid="confirm-share-with-hilux"
					:loading="sharing"
					:disabled="erroredDesigns.length > 0"
					@click="confirmShareWithHilux"
				/>
			</template>
		</Dialog>

		<Dialog
			v-model="showDeleteDialog"
			title="Delete design"
			:options="{ title: 'Delete design' }"
		>
			<div class="space-y-3">
				<p class="text-sm text-ink-gray-7">
					Are you sure you want to delete
					<strong class="text-ink-gray-9">{{
						designToDelete?.design_ref || designToDelete?.name
					}}</strong
					>? This design will be permanently removed from this project.
				</p>
			</div>
			<template #actions>
				<Button variant="subtle" label="Cancel" @click="showDeleteDialog = false" />
				<Button
					class="ml-2"
					variant="solid"
					theme="red"
					label="Delete"
					data-testid="confirm-delete-design"
					:loading="deleting"
					@click="executeDelete"
				/>
			</template>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, Dialog, Dropdown, FormControl, Tooltip, toast, useList } from "frappe-ui";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	copyDesign,
	deleteDesign,
	getProjectFlow,
	quoteStatus,
	shareProjectWithHilux,
	unlockProjectDesigns,
	updateManufacturingStatus,
	type PartnerType,
	type ProjectFlowState,
	type QuoteStatus,
} from "@/api";
import BomTakeoffPanel from "@/components/BomTakeoffPanel.vue";
import QuotePanel from "@/components/QuotePanel.vue";
import ProjectInstallPanel from "@/components/workspace/ProjectInstallPanel.vue";
import ProjectOrderPanel from "@/components/workspace/ProjectOrderPanel.vue";
import ProjectReportsPanel from "@/components/workspace/ProjectReportsPanel.vue";
import type { Design, DesignNode } from "@/design/types";
import { typology } from "@/design/typology";
import { generateElevationSvg } from "@/design/elevationSvg";
import { TEMPLATES } from "@/design/templates";
import { formatMoney } from "@/money";
import { printPdfUrl } from "@/print";

interface DesignRow {
	name: string;
	design_ref: string;
	qty: number;
	series_version: string;
	area_sqft: number;
	window_kg: number;
	error_count: number;
	warning_count: number;
	design_svg: string;
	design_name?: string;
	finish?: string | null;
	design_json?: Design | string | null;
	floor?: string | null;
	location: string;
	unit_price: number | null;
	line_total: number | null;
	pricing_json?: string | { priced_on?: string } | null;
}
interface ProjectInfo {
	name: string;
	project_title: string;
	default_series_version: string;
	customer?: string | null;
	site_address?: string | null;
	transport_charges?: number | null;
	quotation?: string | null;
	fen_partner_type?: PartnerType | null;
	fen_shared_with_hilux?: number | boolean;
	fen_shared_on?: string | null;
	fen_shared_by?: string | null;
	fen_share_notes?: string | null;
	fen_design_locked?: number | boolean;
	fen_manufacturing_status?: string | null;
}

const props = defineProps<{ project: string }>();
const router = useRouter();
const route = useRoute();

const projectList = useList<ProjectInfo>({
	doctype: "Fenestration Project",
	fields: [
		"name",
		"project_title",
		"default_series_version",
		"customer",
		"site_address",
		"transport_charges",
		"quotation",
		"fen_partner_type",
		"fen_shared_with_hilux",
		"fen_shared_on",
		"fen_shared_by",
		"fen_share_notes",
		"fen_design_locked",
		"fen_manufacturing_status",
	],
	filters: { name: props.project },
	limit: 1,
});
const designList = useList<DesignRow>({
	doctype: "Window Design",
	fields: [
		"name",
		"design_ref",
		"qty",
		"series_version",
		"area_sqft",
		"window_kg",
		"error_count",
		"warning_count",
		"design_svg",
		"design_name",
		"finish",
		"design_json",
		"floor",
		"location",
		"unit_price",
		"line_total",
		"pricing_json",
	],
	filters: { project: props.project },
	orderBy: "design_ref asc",
	limit: 200,
});

const glassList = useList<{ name: string; glass_name?: string }>({
	doctype: "Fenestration Glass",
	fields: ["name", "glass_name"],
	limit: 100,
});

const finishList = useList<{ name: string; finish_name?: string; color?: string }>({
	doctype: "Profile Finish",
	fields: ["name", "finish_name", "color"],
	limit: 200,
});

const quote = ref<QuoteStatus | null>(null);
const quoteError = ref(false);
const flowState = ref<ProjectFlowState | null>(null);
async function loadQuote() {
	try {
		quote.value = await quoteStatus(props.project);
		quoteError.value = false;
	} catch {
		quote.value = null;
		quoteError.value = true;
	}
}
async function loadFlow() {
	try {
		if (typeof getProjectFlow !== "function") return;
		flowState.value = await getProjectFlow(props.project);
	} catch {
		flowState.value = null;
	}
}
onMounted(() => {
	loadQuote();
	void loadFlow();
});
function onQuoteChanged() {
	projectList.reload();
	loadQuote();
	void loadFlow();
}
function onRepriced() {
	designList.reload();
	loadQuote();
	void loadFlow();
}

const badge = computed<{ label: string; theme: "gray" | "blue" | "amber" | "red" }>(() => {
	const q = quote.value;
	if (quoteError.value) return { label: "Status unavailable", theme: "gray" };
	if (!q?.quotation) return { label: "Not quoted", theme: "gray" };
	if (q.is_stale) return { label: "Out of date", theme: "red" };
	if (q.docstatus === 0) return { label: "Draft quote", theme: "amber" };
	return { label: q.status || "—", theme: "blue" };
});
const designsLoading = computed(() => designList.data == null);
const kpis = computed(() =>
	[
		{ id: "windows", label: "Windows", value: String(totals.value.windows) },
		{ id: "area", label: "Area (sq.ft)", value: totals.value.area.toFixed(3) },
		{ id: "weight", label: "Weight (kg)", value: totals.value.weight.toFixed(1) },
		{ id: "value", label: "Basic value", value: formatMoney(totals.value.value) },
		{
			id: "grand",
			label: "Grand total incl. GST",
			value:
				quote.value?.quotation && quote.value.rounded_total != null
					? formatMoney(quote.value.rounded_total)
					: "—",
		},
	].map((k) => (designsLoading.value ? { ...k, value: "—" } : k))
);

const TAB_IDS = ["designs", "quote", "order", "production", "install", "reports"] as const;
const activeTab = computed(() => {
	const t = String(route.query.tab ?? "");
	return (TAB_IDS as readonly string[]).includes(t) ? t : "designs";
});
const partnerType = computed<PartnerType>(
	() =>
		(flowState.value?.partner_type || info.value?.fen_partner_type || "Dealer") as PartnerType
);
const isDealer = computed(() => partnerType.value === "Dealer");
const isFabricationPartner = computed(() => partnerType.value === "Fabrication Partner");
const isOwnClient = computed(() => partnerType.value === "Own Client");
const partnerBadgeTheme = computed<"gray" | "blue" | "violet">(() => {
	if (isFabricationPartner.value) return "blue";
	if (isOwnClient.value) return "violet";
	return "gray";
});
const partnerBadgeLabel = computed(() => {
	if (isFabricationPartner.value) return "Fabrication Partner · Materials Only";
	if (isOwnClient.value) return "Own Client · Direct Supply & Install";
	return "Dealer · Turnkey Manufacturing";
});
const isSharedWithHilux = computed(() =>
	Boolean(flowState.value?.shared_with_hilux ?? info.value?.fen_shared_with_hilux)
);
const isDesignLocked = computed(() =>
	Boolean(flowState.value?.design_locked ?? info.value?.fen_design_locked)
);
const manufacturingStatus = computed(
	() =>
		flowState.value?.manufacturing_status ||
		info.value?.fen_manufacturing_status ||
		"Private Draft"
);
const erroredDesigns = computed(() => designs.value.filter((d) => Number(d.error_count) > 0));

const showShareDialog = ref(false);
const shareNotes = ref("");
const shareLockDesigns = ref(true);
const sharing = ref(false);
const unlocking = ref(false);
const shareError = ref("");

function openShareDialog() {
	shareNotes.value = flowState.value?.share_notes || info.value?.fen_share_notes || "";
	shareLockDesigns.value = true;
	shareError.value = "";
	showShareDialog.value = true;
}

async function confirmShareWithHilux() {
	sharing.value = true;
	shareError.value = "";
	try {
		await shareProjectWithHilux(props.project, shareNotes.value, shareLockDesigns.value);
		toast.success("Project shared with Hilux for manufacturing");
		showShareDialog.value = false;
		projectList.reload();
		await loadFlow();
	} catch (e) {
		shareError.value = e instanceof Error ? e.message : "Could not share project with Hilux.";
	} finally {
		sharing.value = false;
	}
}

async function handleUnlockDesigns() {
	unlocking.value = true;
	try {
		await unlockProjectDesigns(props.project);
		toast.success("Project designs unlocked for revision");
		await Promise.all([projectList.reload(), loadFlow()]);
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Could not unlock designs");
	} finally {
		unlocking.value = false;
	}
}

const MANUFACTURING_STATUSES = [
	"Shared with Hilux",
	"Accepted for Manufacturing",
	"Materials Procured",
	"In Fabrication",
	"Dispatched to Dealer",
];
const manufacturingStatusOptions = computed(() =>
	MANUFACTURING_STATUSES.map((status) => ({
		label: status,
		onClick: async () => {
			try {
				await updateManufacturingStatus(props.project, status);
				toast.success(`Manufacturing status updated to ${status}`);
				projectList.reload();
				await loadFlow();
			} catch (e) {
				toast.error(e instanceof Error ? e.message : "Could not update status");
			}
		},
	}))
);

const tabs = computed(() => [
	{ id: "designs", label: `Designs · ${designs.value.length}`, disabled: false },
	{
		id: "quote",
		label: isFabricationPartner.value ? "Material Quote" : "Quote",
		disabled: false,
	},
	{ id: "order", label: "Order", disabled: false },
	{
		id: "production",
		label: isFabricationPartner.value ? "Materials & BOM" : "Production",
		disabled: false,
	},
	{ id: "install", label: isFabricationPartner.value ? "Dispatch" : "Install", disabled: false },
	{ id: "reports", label: "Reports", disabled: false },
]);
type Tab = { id: string; label: string; disabled: boolean };
function selectTab(t: Tab) {
	if (t.disabled) return;
	router.replace({ query: { ...route.query, tab: t.id === "designs" ? undefined : t.id } });
}
function tabClass(t: Tab) {
	if (t.disabled) return "cursor-not-allowed border-transparent text-ink-gray-4";
	return activeTab.value === t.id
		? "border-ink-gray-9 font-medium"
		: "border-transparent text-ink-gray-6";
}
function fixed(n: number | null | undefined, dp: number): string {
	return n == null ? "—" : Number(n).toFixed(dp);
}

function parseDesignDoc(d: DesignRow): Design | null {
	try {
		return typeof d.design_json === "string"
			? JSON.parse(d.design_json || "null")
			: d.design_json ?? null;
	} catch {
		return null;
	}
}
function parseTree(d: DesignRow): DesignNode | null {
	return parseDesignDoc(d)?.root ?? null;
}
function dimensionsOf(d: DesignRow): string {
	const doc = parseDesignDoc(d);
	return doc?.width && doc?.height ? `${doc.width} × ${doc.height} mm` : "";
}
function leafGlass(node: DesignNode): string[] {
	return node.type === "split" ? node.children.flatMap(leafGlass) : [node.glass];
}
function typologyOf(d: DesignRow): string {
	const root = parseTree(d);
	return root ? typology(root) : "—";
}
const glasses = computed(() => new Map((glassList.data ?? []).map((g) => [g.name, g.glass_name])));
function glassName(code: string): string {
	return glasses.value.get(code) || code;
}
function money(n: number | null | undefined): string {
	return n == null ? "—" : formatMoney(n);
}
function glassOf(d: DesignRow): string {
	const root = parseTree(d);
	const names = root ? [...new Set(leafGlass(root).filter(Boolean).map(glassName))] : [];
	return names.length ? names.join(", ") : "—";
}
const finishes = computed(() => new Map((finishList.data ?? []).map((f) => [f.name, f])));
function finishName(code?: string | null): string {
	return code ? finishes.value.get(code)?.finish_name || code : "—";
}
function finishColor(code?: string | null): string {
	return (code && finishes.value.get(code)?.color) || "#9ca3af";
}

const info = computed(() => projectList.data?.[0]);
const designs = computed(() => designList.data ?? []);
const search = ref("");
const shown = computed(() => {
	const q = search.value.trim().toLowerCase();
	if (!q) return designs.value;
	return designs.value.filter((d) =>
		[d.design_ref, d.design_name, d.floor, d.location].some((v) =>
			(v ?? "").toLowerCase().includes(q)
		)
	);
});
const totals = computed(() => {
	let windows = 0,
		area = 0,
		weight = 0,
		value = 0;
	for (const d of designs.value) {
		windows += d.qty;
		area += d.area_sqft * d.qty;
		weight += d.window_kg * d.qty;
		value += d.line_total ?? 0;
	}
	return { windows, area, weight, value };
});

const dateFormat = new Intl.DateTimeFormat("en-IN", {
	day: "numeric",
	month: "short",
	year: "numeric",
});

function pricedOn(d: DesignRow): string {
	try {
		const pricing =
			typeof d.pricing_json === "string"
				? JSON.parse(d.pricing_json || "{}")
				: d.pricing_json;
		return pricing?.priced_on ? dateFormat.format(new Date(pricing.priced_on)) : "";
	} catch {
		return "";
	}
}

function thumb(svg: string) {
	return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
}

function thumbSrc(d: DesignRow): string {
	if (d.design_svg) return thumb(d.design_svg);
	const doc = parseDesignDoc(d);
	if (doc && doc.width && doc.height && doc.root) {
		const svg = generateElevationSvg(doc, finishColor(d.finish));
		return svg ? thumb(svg) : "";
	}
	return "";
}

// Only show the generic (non-series-specific) templates in the workspace new-design menu.
// CS400 templates are accessed from the Designer sidebar after choosing a series.
const templateOptions = TEMPLATES.filter((t) => !t.series).map((t) => ({
	label: t.label,
	onClick: () => newDesign(t.id),
}));

function newDesign(template: string) {
	router.push({
		path: `/projects/${props.project}/designs/new`,
		query: { series_version: info.value?.default_series_version, template },
	});
}

const duplicating = ref(false);
async function duplicate(name: string) {
	if (duplicating.value) return;
	duplicating.value = true;
	let copy: string;
	try {
		copy = await copyDesign(name);
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Copy failed");
		return;
	} finally {
		duplicating.value = false;
	}
	await router.push(`/projects/${props.project}/designs/${copy}`).catch(() => {
		toast.error(`Copied as ${copy}, but could not open it`);
	});
}

const showDeleteDialog = ref(false);
const designToDelete = ref<DesignRow | null>(null);
const deleting = ref(false);

function promptDelete(d: DesignRow) {
	designToDelete.value = d;
	showDeleteDialog.value = true;
}

async function executeDelete() {
	if (!designToDelete.value || deleting.value) return;
	const target = designToDelete.value;
	deleting.value = true;
	try {
		await deleteDesign(target.name);
		toast.success(`Deleted ${target.design_ref || target.name}`);
		showDeleteDialog.value = false;
		designToDelete.value = null;
		await designList.reload();
		await loadQuote();
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Delete failed");
	} finally {
		deleting.value = false;
	}
}
</script>
