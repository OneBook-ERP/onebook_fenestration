<script setup lang="ts">
import { Alert, Badge, Button, TabButtons } from "frappe-ui";
import { computed, ref, watch } from "vue";
import type { BomRow, Member } from "@/api";
import { useProfileNames } from "@/composables/profiles";
import { panelLabel } from "@/design/typology";
import { formatMoney } from "@/money";
import { useDesignerStore } from "@/stores/designer";

const COLLAPSED_KEY = "fen.resultsCollapsed";

const store = useDesignerStore();
const profileNames = useProfileNames();
const tab = ref("Cut list");

function readCollapsed() {
	try {
		const stored = localStorage.getItem(COLLAPSED_KEY);
		if (stored !== null) return stored === "1";
	} catch {
		// Storage unavailable: fall through to the viewport default.
	}
	return (
		typeof window.matchMedia === "function" && window.matchMedia("(max-width: 767px)").matches
	);
}
const collapsed = ref(readCollapsed());
watch(collapsed, (v) => {
	try {
		localStorage.setItem(COLLAPSED_KEY, v ? "1" : "0");
	} catch {
		// Storage unavailable: the state just won't persist.
	}
});

const result = computed(() => store.result);
const issues = computed(() => result.value?.issues ?? []);
const errors = computed(() => issues.value.filter((i) => i.severity === "error").length);
const warnings = computed(() => issues.value.filter((i) => i.severity === "warn").length);

const shutters = computed(() => {
	const s = result.value?.shutter_kg;
	if (s == null) return [];
	return typeof s === "number" ? [["", s] as [string, number]] : Object.entries(s);
});

/** Angles arrive as an array or a string like "[45, 45]". */
function formatAngles(a: Member["angles"] | number[]): string {
	let list: unknown = a;
	if (typeof a === "string") {
		try {
			list = JSON.parse(a);
		} catch {
			return a || "\u2014";
		}
	}
	return Array.isArray(list) && list.length
		? list.map((x) => `${Number(x) === 135 ? 45 : x}\u00b0`).join(" / ")
		: "\u2014";
}
const dash = (v: unknown) => (v == null || v === "" ? "\u2014" : String(v));

const cutList = computed(() => {
	const rows = new Map<string, { m: Member; qty: number }>();
	for (const m of result.value?.members ?? []) {
		const key = `${m.profile}|${m.length}|${formatAngles(m.angles)}|${m.position}|${m.panel}`;
		const row = rows.get(key);
		if (row) row.qty += 1;
		else rows.set(key, { m, qty: 1 });
	}
	return [...rows.entries()].map(([key, r]) => ({ key, ...r }));
});
const hardware = computed<BomRow[]>(() =>
	(result.value?.bom ?? []).filter((b) => b.group !== "Gasket")
);
const gaskets = computed(() => {
	const rows = new Map<string, { item: string; name: string; metres: number }>();
	for (const b of (result.value?.bom ?? []).filter((r) => r.group === "Gasket")) {
		const row = rows.get(b.item) ?? { item: b.item, name: b.name, metres: 0 };
		row.metres += (b.length ?? 0) / 1000;
		rows.set(b.item, row);
	}
	return [...rows.values()];
});

const counts = computed<Record<string, number>>(() => ({
	"Cut list": cutList.value.length,
	Hardware: hardware.value.length,
	Gaskets: gaskets.value.length,
	Glass: result.value?.glass?.length ?? 0,
	Issues: issues.value.length,
}));
const tabOptions = computed(() =>
	["Cut list", "Hardware", "Gaskets", "Glass", "Pricing", "Issues"].map((t) => ({
		value: t,
		label:
			t === "Pricing"
				? t
				: `${
						t === "Glass" && result.value?.glass?.some((g) => g.material === "steel")
							? "Glass / Steel"
							: t
				  } \u00b7 ${counts.value[t]}`,
	}))
);

const pricing = computed(() => result.value?.pricing);
const selectedLabel = computed(() => panelLabel(store.selectedPath, store.result));
const totalCutPieces = computed(() => cutList.value.reduce((acc, r) => acc + r.qty, 0));
const totalCutMetres = computed(() =>
	cutList.value.reduce((acc, r) => acc + (Number(r.m.length) * r.qty) / 1000, 0)
);
const totalGasketMetres = computed(() => gaskets.value.reduce((acc, g) => acc + g.metres, 0));
const totalGlassAreaM2 = computed(() =>
	(result.value?.glass ?? []).reduce(
		(acc, g) => acc + (Number(g.width) * Number(g.height)) / 1_000_000,
		0
	)
);

const POS_LABELS: Record<string, string> = {
	B: "Bottom",
	T: "Top",
	L: "Left",
	R: "Right",
	H: "Mullion",
	W: "Sash",
};

function posHint(pos?: string): string {
	return (pos && POS_LABELS[pos]) || "";
}

function isPanelMatch(panel?: string, path?: string): boolean {
	if (!store.selectedPath) return false;
	if (path && path === store.selectedPath) return true;
	if (!panel || !selectedLabel.value) return false;
	const tokens = panel.split(",").map((s) => s.trim().toLowerCase());
	const target = selectedLabel.value.toLowerCase();
	return tokens.includes(target) || panel.toLowerCase() === target;
}

function onRowClick(path?: string, panel?: string) {
	if (path) {
		store.select(path);
		return;
	}
	if (!panel) return;
	const firstMember = store.result?.members.find((m) => m.panel === panel && m.path);
	if (firstMember?.path) {
		store.select(firstMember.path);
		return;
	}
	const firstGlass = store.result?.glass.find((g) => g.panel === panel && g.path);
	if (firstGlass?.path) {
		store.select(firstGlass.path);
	}
}

const th =
	"sticky top-0 z-10 border-b border-gray-200 bg-gray-50/95 px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500 backdrop-blur";
const td = "px-3 py-2 text-sm text-gray-800";
</script>

<template>
	<section class="border-t border-gray-200 bg-white">
		<Alert v-if="store.error" role="alert" theme="red" :title="store.error" />
		<div :class="{ 'opacity-50': store.error && result }">
			<div
				v-if="result"
				class="flex flex-wrap items-center gap-2 border-b border-gray-200 bg-slate-50/80 px-3 py-2 text-xs"
			>
				<div
					class="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-gray-800 shadow-2xs tabular-nums"
				>
					<span class="font-medium"
						>Area {{ result.area_m2.toFixed(3) }} m&sup2; &middot;
						{{ result.area_sqft.toFixed(3) }} sq.ft</span
					>
				</div>
				<div
					class="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-gray-800 shadow-2xs tabular-nums"
				>
					<span class="font-medium">Window {{ result.window_kg.toFixed(3) }} kg</span>
				</div>
				<div
					v-for="[panel, kg] in shutters"
					:key="panel"
					class="inline-flex items-center rounded-md border border-gray-200 bg-white px-2.5 py-1 font-medium text-gray-700 shadow-2xs tabular-nums"
				>
					Shutter {{ panel }} {{ Number(kg).toFixed(3) }} kg
				</div>
				<div
					v-if="pricing"
					class="inline-flex flex-wrap items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50/70 px-2.5 py-1 text-emerald-950 tabular-nums"
				>
					<span class="font-semibold"
						>Live price {{ formatMoney(pricing.unit_price) }}</span
					>
					<span class="text-emerald-700"
						>{{ formatMoney(pricing.rate_per_sqft) }}/sq.ft</span
					>
				</div>
				<span v-if="pricing" class="text-[11px] text-gray-500"
					>From current rates; saved designs keep their priced value until
					repriced.</span
				>
				<Badge :theme="errors ? 'red' : 'green'" :label="`${errors} errors`" />
				<Badge v-if="warnings" theme="amber" :label="`${warnings} warnings`" />
				<Button
					class="ml-auto min-h-9"
					variant="subtle"
					:label="collapsed ? 'Show results' : 'Hide results'"
					:aria-expanded="!collapsed"
					@click="collapsed = !collapsed"
				/>
			</div>
			<div
				v-else-if="!store.error"
				class="flex items-center border-b border-gray-100 bg-slate-50/60 px-3 py-2 text-sm text-gray-500"
			>
				<span>Computing...</span>
				<Button
					class="ml-auto min-h-9"
					variant="subtle"
					:label="collapsed ? 'Show results' : 'Hide results'"
					:aria-expanded="!collapsed"
					@click="collapsed = !collapsed"
				/>
			</div>

			<div
				v-if="!collapsed"
				class="flex min-w-0 items-center justify-between gap-3 border-b border-gray-100 bg-white px-3 py-1.5"
			>
				<!-- The tab strip is wider than a phone; it scrolls here instead of widening the page. -->
				<div data-testid="results-tabs" class="min-w-0 overflow-x-auto">
					<TabButtons v-model="tab" :options="tabOptions" />
				</div>
				<div
					v-if="result"
					class="hidden shrink-0 items-center gap-2 text-xs text-gray-500 sm:flex tabular-nums"
				>
					<template v-if="tab === 'Cut list'">
						<span class="rounded bg-gray-100 px-2 py-0.5 font-medium text-gray-700"
							>{{ totalCutPieces }} pcs</span
						>
						<span class="rounded bg-gray-100 px-2 py-0.5 font-medium text-gray-700"
							>{{ totalCutMetres.toFixed(2) }} m total cut</span
						>
					</template>
					<template v-else-if="tab === 'Gaskets'">
						<span class="rounded bg-gray-100 px-2 py-0.5 font-medium text-gray-700"
							>{{ totalGasketMetres.toFixed(3) }} m total</span
						>
					</template>
					<template v-else-if="tab === 'Glass'">
						<span class="rounded bg-gray-100 px-2 py-0.5 font-medium text-gray-700"
							>{{ totalGlassAreaM2.toFixed(3) }} m&sup2; total</span
						>
					</template>
				</div>
			</div>

			<div v-if="!collapsed" class="max-h-56 overflow-auto bg-white">
				<table v-if="tab === 'Cut list'" class="w-full border-collapse">
					<thead>
						<tr>
							<th :class="th">Profile</th>
							<th :class="th">Code</th>
							<th :class="[th, 'text-right']">Length (mm)</th>
							<th :class="th">Angles</th>
							<th :class="[th, 'text-right']">Qty</th>
							<th :class="th">Position</th>
							<th :class="th">Panel</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100">
						<tr
							v-for="r in cutList"
							:key="r.key"
							:class="
								isPanelMatch(r.m.panel, r.m.path)
									? 'bg-blue-50/80 font-medium text-blue-950'
									: 'even:bg-gray-50/40 cursor-pointer hover:bg-blue-50/40'
							"
							@click="onRowClick(r.m.path, r.m.panel)"
						>
							<td :class="td">
								<div class="flex items-center gap-2">
									<span class="font-medium text-gray-900">{{
										dash(profileNames[r.m.profile])
									}}</span>
									<span
										v-if="r.m.role"
										class="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium capitalize text-slate-600"
										>{{ r.m.role }}</span
									>
								</div>
							</td>
							<td :class="td">
								<span
									class="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-700"
									>{{ r.m.profile }}</span
								>
							</td>
							<td :class="[td, 'text-right font-semibold tabular-nums']">
								{{ Number(r.m.length).toFixed(1) }}
							</td>
							<td
								:class="[
									td,
									'text-xs text-gray-600 whitespace-nowrap tabular-nums',
								]"
							>
								{{ formatAngles(r.m.angles) }}
							</td>
							<td :class="[td, 'text-right font-semibold tabular-nums']">
								{{ r.qty }}
							</td>
							<td :class="td" :title="posHint(r.m.position)">
								<span
									class="inline-flex items-center rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 font-mono text-xs font-medium text-gray-700"
									>{{ dash(r.m.position) }}</span
								>
							</td>
							<td :class="td">
								<span
									class="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs font-semibold text-slate-800"
									>{{ dash(r.m.panel) }}</span
								>
							</td>
						</tr>
						<tr v-if="!cutList.length">
							<td colspan="7" class="px-3 py-6 text-center text-sm text-gray-500">
								No profile cuts generated yet.
							</td>
						</tr>
					</tbody>
					<tfoot v-if="cutList.length">
						<tr
							class="border-t border-gray-200 bg-slate-50/90 text-xs font-semibold text-gray-700 tabular-nums"
						>
							<td colspan="2" class="px-3 py-2">
								Totals ({{ cutList.length }} unique cuts)
							</td>
							<td class="px-3 py-2 text-right">{{ totalCutMetres.toFixed(2) }} m</td>
							<td class="px-3 py-2"></td>
							<td class="px-3 py-2 text-right">{{ totalCutPieces }}</td>
							<td colspan="2" class="px-3 py-2"></td>
						</tr>
					</tfoot>
				</table>
				<table v-else-if="tab === 'Hardware'" class="w-full border-collapse">
					<thead>
						<tr>
							<th :class="th">Item</th>
							<th :class="th">Name</th>
							<th :class="[th, 'text-right']">Qty</th>
							<th :class="th">UOM</th>
							<th :class="th">Panel</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100">
						<tr
							v-for="(b, i) in hardware"
							:key="i"
							:class="
								isPanelMatch(b.panel)
									? 'bg-blue-50/80 font-medium text-blue-950'
									: b.panel
									? 'even:bg-gray-50/40 cursor-pointer hover:bg-blue-50/40'
									: 'even:bg-gray-50/40'
							"
							@click="onRowClick(undefined, b.panel)"
						>
							<td :class="td">
								<span
									class="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-700"
									>{{ b.item }}</span
								>
							</td>
							<td :class="td">
								<span class="font-medium text-gray-900">{{ b.name }}</span>
								<span
									v-if="b.group"
									class="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
									>{{ b.group }}</span
								>
							</td>
							<td :class="[td, 'text-right font-semibold tabular-nums']">
								{{ b.qty }}
							</td>
							<td :class="[td, 'text-xs text-gray-600']">{{ b.uom }}</td>
							<td :class="td">
								<span
									v-if="b.panel"
									class="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs font-semibold text-slate-800"
									>{{ b.panel }}</span
								>
								<span v-else class="text-gray-400">&mdash;</span>
							</td>
						</tr>
						<tr v-if="!hardware.length">
							<td colspan="5" class="px-3 py-6 text-center text-sm text-gray-500">
								No hardware items required.
							</td>
						</tr>
					</tbody>
				</table>
				<table v-else-if="tab === 'Gaskets'" class="w-full border-collapse">
					<thead>
						<tr>
							<th :class="th">Item</th>
							<th :class="th">Name</th>
							<th :class="[th, 'text-right']">Length (m)</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100">
						<tr
							v-for="g in gaskets"
							:key="g.item"
							class="even:bg-gray-50/40 hover:bg-gray-50"
						>
							<td :class="td">
								<span
									class="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-700"
									>{{ g.item }}</span
								>
							</td>
							<td :class="[td, 'font-medium text-gray-900']">{{ g.name }}</td>
							<td :class="[td, 'text-right font-semibold tabular-nums']">
								{{ g.metres.toFixed(3) }}
							</td>
						</tr>
						<tr v-if="!gaskets.length">
							<td colspan="3" class="px-3 py-6 text-center text-sm text-gray-500">
								No gasket runs in this design.
							</td>
						</tr>
					</tbody>
					<tfoot v-if="gaskets.length">
						<tr
							class="border-t border-gray-200 bg-slate-50/90 text-xs font-semibold text-gray-700 tabular-nums"
						>
							<td colspan="2" class="px-3 py-2">Total gasket length</td>
							<td class="px-3 py-2 text-right">
								{{ totalGasketMetres.toFixed(3) }} m
							</td>
						</tr>
					</tfoot>
				</table>
				<table v-else-if="tab === 'Glass'" class="w-full border-collapse">
					<thead>
						<tr>
							<th :class="th">Panel</th>
							<th :class="[th, 'text-right']">No.</th>
							<th :class="th">Material</th>
							<th :class="[th, 'text-right']">Width</th>
							<th :class="[th, 'text-right']">Height</th>
							<th :class="th">Exhaust cut</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100">
						<tr
							v-for="g in result?.glass ?? []"
							:key="g.path"
							:class="
								isPanelMatch(g.panel, g.path)
									? 'bg-blue-50/80 font-medium text-blue-950'
									: g.path
									? 'even:bg-gray-50/40 cursor-pointer hover:bg-blue-50/40'
									: 'even:bg-gray-50/40'
							"
							@click="onRowClick(g.path, g.panel)"
						>
							<td :class="td">
								<span
									class="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs font-semibold text-slate-800"
									>{{ g.panel }}</span
								>
							</td>
							<td
								:class="[
									td,
									'text-right font-mono text-xs text-gray-600 tabular-nums',
								]"
							>
								{{ g.number }}
							</td>
							<td :class="td">
								<span
									class="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium"
									:class="
										g.material === 'steel'
											? 'bg-slate-200 text-slate-800'
											: 'bg-sky-50 text-sky-900 border border-sky-200'
									"
								>
									{{
										g.material === "steel"
											? `Steel sheet · ${g.thickness} mm`
											: g.glass
									}}
								</span>
							</td>
							<td :class="[td, 'text-right font-semibold tabular-nums']">
								{{ g.width }}
							</td>
							<td :class="[td, 'text-right font-semibold tabular-nums']">
								{{ g.height }}
							</td>
							<td :class="[td, 'text-xs text-gray-600']">
								{{
									g.cutout
										? `Ø${g.cutout.diameter} mm · centre ${g.cutout.centerX} mm from left, ${g.cutout.centerY} mm from top`
										: "—"
								}}
							</td>
						</tr>
						<tr v-if="!result?.glass?.length">
							<td colspan="6" class="px-3 py-6 text-center text-sm text-gray-500">
								No glass or steel panels.
							</td>
						</tr>
					</tbody>
					<tfoot v-if="result?.glass?.length">
						<tr
							class="border-t border-gray-200 bg-slate-50/90 text-xs font-semibold text-gray-700 tabular-nums"
						>
							<td colspan="4" class="px-3 py-2">
								{{ result.glass.length }} panes total
							</td>
							<td colspan="2" class="px-3 py-2 text-right">
								{{ totalGlassAreaM2.toFixed(3) }} m&sup2;
							</td>
						</tr>
					</tfoot>
				</table>
				<table v-else-if="tab === 'Pricing'" class="w-full border-collapse">
					<thead>
						<tr>
							<th :class="th">Cost head</th>
							<th :class="[th, 'text-right']">Amount</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100">
						<tr
							v-for="l in pricing?.lines ?? []"
							:key="l.key"
							class="even:bg-gray-50/40"
							:class="{ 'italic text-gray-500': l.include_in_total === false }"
							:title="
								l.include_in_total === false ? 'Not added to the total' : undefined
							"
						>
							<td :class="td">
								<span>{{ l.label }}</span>
								<span
									v-if="l.include_in_total === false"
									class="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-normal not-italic text-gray-500"
									>Info only</span
								>
							</td>
							<td :class="[td, 'text-right font-medium tabular-nums']">
								{{ formatMoney(l.amount) }}
							</td>
						</tr>
					</tbody>
					<tfoot v-if="pricing">
						<tr class="border-t-2 border-gray-300 bg-slate-50 font-bold text-gray-900">
							<td :class="td">
								Total
								<span class="ml-2 text-xs font-normal text-gray-500 tabular-nums"
									>({{ formatMoney(pricing.rate_per_sqft) }}/sq.ft)</span
								>
							</td>
							<td :class="[td, 'text-right tabular-nums']">
								{{ formatMoney(pricing.unit_price) }}
							</td>
						</tr>
					</tfoot>
				</table>
				<ul v-else class="divide-y divide-gray-100">
					<li v-for="(i, n) in issues" :key="n">
						<button
							:data-issue-path="i.path"
							class="flex min-h-9 w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-gray-50"
							@click="store.select(i.path)"
						>
							<span
								class="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-600"
								>{{ i.path }}</span
							>
							<span
								class="rounded px-2 py-0.5 text-xs font-semibold uppercase"
								:class="
									i.severity === 'error'
										? 'bg-red-50 text-red-700 border border-red-200'
										: 'bg-amber-50 text-amber-700 border border-amber-200'
								"
							>
								{{ i.severity }}
							</span>
							<span class="text-gray-800"
								>{{ i.message
								}}<template v-if="i.hint">
									&mdash;
									<span class="text-gray-500">{{ i.hint }}</span></template
								></span
							>
						</button>
					</li>
					<li v-if="!issues.length" class="px-3 py-6 text-center text-sm text-gray-500">
						No issues.
					</li>
				</ul>
			</div>
		</div>
	</section>
</template>
