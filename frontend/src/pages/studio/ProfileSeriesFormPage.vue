<template>
	<div class="mx-auto max-w-6xl p-6">
		<header
			class="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-outline-gray-2 pb-4"
		>
			<div>
				<nav
					aria-label="Breadcrumb"
					class="mb-1 flex items-center gap-1.5 text-sm text-ink-gray-5"
				>
					<router-link to="/series-studio" class="hover:text-ink-gray-8">
						Series Studio
					</router-link>
					<span aria-hidden="true">/</span>
					<router-link to="/series-studio" class="hover:text-ink-gray-8">
						Profile Series
					</router-link>
					<span aria-hidden="true">/</span>
					<span class="font-medium text-ink-gray-8">{{
						isEdit ? form.series_code : "New Profile Series"
					}}</span>
				</nav>
				<div class="flex flex-wrap items-center gap-3">
					<h1 class="text-xl font-semibold text-ink-gray-9">
						{{
							isEdit
								? `${form.series_code} · ${form.series_title || "Series"}`
								: form.series_title || "New Profile Series"
						}}
					</h1>
					<Badge
						:theme="
							form.system_type === 'Casement'
								? 'blue'
								: form.system_type === 'Sliding'
								? 'amber'
								: 'gray'
						"
						:label="form.system_type"
					/>
					<Badge
						v-if="form.published_version"
						theme="green"
						:label="`Published: ${form.published_version}`"
					/>
					<Badge v-else theme="gray" label="Unpublished" />
				</div>
			</div>

			<div class="flex flex-wrap items-center gap-2">
				<Button
					v-if="isEdit"
					variant="subtle"
					label="All Profiles (Card View)"
					:route="`/series-studio?tab=profiles&series=${form.series_code}`"
				/>
				<Button
					v-if="isEdit"
					variant="subtle"
					label="Series Versions"
					:route="`/series-studio?tab=versions&series=${form.series_code}`"
				/>
				<Button variant="outline" label="Back" route="/series-studio" />
				<Button
					variant="solid"
					:label="isEdit ? 'Save Changes' : 'Create Series'"
					:loading="saving"
					:disabled="!canSave"
					data-testid="save-series-btn"
					@click="save"
				/>
			</div>
		</header>

		<div v-if="loadingDoc" class="py-12 text-center text-sm text-ink-gray-5">
			Loading profile series…
		</div>

		<div v-else class="space-y-8">
			<Alert v-if="error" theme="red" :title="error" />

			<!-- Section 1: Series Details -->
			<section>
				<h2 class="mb-4 text-base font-semibold text-ink-gray-9">Series Details</h2>
				<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
					<div class="space-y-4">
						<FormControl
							v-model="form.series_code"
							label="Series Code *"
							placeholder="e.g. CS400"
							:disabled="isEdit"
						/>
						<FormControl
							v-model="form.series_title"
							label="Series Title *"
							placeholder="e.g. CS400 Economical Casement"
						/>
						<div>
							<label class="mb-1.5 block text-xs font-medium text-ink-gray-6">
								Supported Products *
							</label>
							<Popover side="bottom" align="start" :match-trigger-width="true">
								<template #trigger="{ open }">
									<button
										type="button"
										data-testid="supported-products-trigger"
										class="flex min-h-9 w-full flex-wrap items-center justify-between gap-1.5 rounded-lg border border-outline-gray-2 bg-surface-gray-2/70 px-2.5 py-1.5 text-left text-sm transition-colors hover:border-outline-gray-3 focus:border-outline-gray-4 focus:outline-none"
									>
										<span
											v-if="!form.supported_products.length"
											class="text-xs text-ink-gray-5"
										>
											Select Window, Door, Sliding Window, Sliding Door…
										</span>
										<span v-else class="flex flex-wrap items-center gap-1">
											<Badge
												v-for="item in form.supported_products"
												:key="item"
												size="sm"
												variant="subtle"
												theme="blue"
												:label="item"
											>
												<template #suffix>
													<span
														role="button"
														:aria-label="`Remove ${item}`"
														class="ml-0.5 cursor-pointer opacity-70 hover:opacity-100"
														@click.stop="toggleSupportedProduct(item)"
													>
														×
													</span>
												</template>
											</Badge>
										</span>
										<span
											class="ml-auto size-4 shrink-0 text-ink-gray-5 transition-transform"
											:class="
												open ? 'lucide-chevron-up' : 'lucide-chevron-down'
											"
										/>
									</button>
								</template>
								<template #default>
									<div
										data-testid="supported-products-menu"
										class="min-w-64 space-y-0.5 p-1"
									>
										<button
											v-for="opt in SUPPORTED_PRODUCT_OPTIONS"
											:key="opt.value"
											type="button"
											:data-testid="`supported-product-opt-${opt.value
												.toLowerCase()
												.replace(/\s+/g, '-')}`"
											class="flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left transition-colors hover:bg-surface-gray-1"
											@click="toggleSupportedProduct(opt.value)"
										>
											<div class="min-w-0">
												<div class="text-xs font-semibold text-ink-gray-9">
													{{ opt.label }}
												</div>
												<div class="text-[11px] text-ink-gray-5">
													{{ opt.hint }}
												</div>
											</div>
											<span
												class="flex size-4 shrink-0 items-center justify-center rounded border text-[11px]"
												:class="
													form.supported_products.includes(opt.value)
														? 'border-gray-900 bg-gray-900 text-white'
														: 'border-outline-gray-3 bg-white text-transparent'
												"
											>
												✓
											</span>
										</button>
									</div>
								</template>
							</Popover>
							<p class="mt-1 text-[11px] text-ink-gray-5">
								Only selected product types appear in Section Templates; Designer
								warns if an unsupported type is used.
							</p>
						</div>
					</div>

					<div class="space-y-4">
						<FormControl
							v-model="form.system_type"
							type="select"
							label="System Type *"
							:options="systemTypeOptions"
						/>
						<div>
							<FormControl
								:model-value="form.published_version || '—'"
								label="Published Version"
								disabled
							/>
							<div v-if="form.published_version" class="mt-1.5">
								<router-link
									:to="`/series-studio/versions/${encodeURIComponent(
										form.published_version
									)}`"
									class="text-xs font-medium text-blue-600 hover:underline"
								>
									Open {{ form.published_version }} rules &rarr;
								</router-link>
							</div>
						</div>
					</div>
				</div>
			</section>

			<!-- Section 2: Series Profiles (from profile_series.js) -->
			<section class="border-t border-outline-gray-2 pt-6">
				<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
					<h2 class="text-base font-semibold text-ink-gray-9">Series Profiles</h2>
					<div v-if="isEdit" class="flex flex-wrap items-center gap-2">
						<Button
							variant="outline"
							size="sm"
							label="Section Configuration"
							data-testid="section-config-btn"
							:route="`/series-studio/series/${encodeURIComponent(
								form.series_code || props.name || ''
							)}/section-config`"
						/>
						<Button
							variant="outline"
							size="sm"
							label="+ Add Profile to Series"
							:route="`/series-studio/profiles/new?series=${encodeURIComponent(
								form.series_code
							)}`"
						/>
					</div>
				</div>

				<div v-if="!isEdit" class="py-6 text-sm text-ink-gray-5">
					Save the series to view and manage its profiles.
				</div>

				<template v-else>
					<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
						<div class="flex flex-wrap gap-2">
							<button
								v-for="r in roles"
								:key="r"
								type="button"
								class="rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors"
								:class="
									selectedRole === r
										? 'border-ink-gray-9 bg-ink-gray-9 text-surface-white'
										: 'border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:bg-surface-gray-1'
								"
								@click="selectedRole = r"
							>
								{{
									r === "ALL"
										? `All · ${seriesProfiles.length}`
										: r.charAt(0).toUpperCase() + r.slice(1)
								}}
							</button>
						</div>
						<FormControl
							v-model="profileSearch"
							type="search"
							placeholder="Search series profiles..."
							class="w-56"
						/>
					</div>

					<div
						v-if="!filteredProfiles.length"
						class="py-8 text-center text-sm text-ink-gray-5"
					>
						No profiles match in this series.
					</div>

					<div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
						<article
							v-for="p in filteredProfiles"
							:key="p.name"
							class="flex flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white"
						>
							<div
								class="flex h-[180px] cursor-pointer items-center justify-center border-b border-outline-gray-1 bg-[#f6f6f4] p-3"
								@click="
									router.push(
										`/series-studio/profiles/${encodeURIComponent(p.name)}`
									)
								"
							>
								<svg
									v-if="p.section_svg && p.width_mm && p.depth_mm"
									:viewBox="`0 0 ${svgOf(p).cw} ${svgOf(p).ch}`"
									class="block h-full max-h-[155px] w-full max-w-full"
									xmlns="http://www.w3.org/2000/svg"
								>
									<g
										:transform="`translate(${svgOf(p).ox}, ${
											svgOf(p).oy
										}) scale(${svgOf(p).s})`"
									>
										<g :transform="profileRotationTransform(p)">
											<path
												:d="p.section_svg"
												fill="#94a3b8"
												fill-opacity="0.85"
												stroke="#334155"
												:stroke-width="svgOf(p).pathStroke"
												stroke-linejoin="round"
												fill-rule="evenodd"
											/>
										</g>
									</g>
									<text
										:x="svgOf(p).ox + svgOf(p).dw / 2"
										:y="svgOf(p).dimY + 15"
										text-anchor="middle"
										fill="#0f172a"
										:font-size="svgOf(p).fontSize"
										font-weight="600"
									>
										{{ svgOf(p).widthLabel }}
									</text>
									<text
										:x="svgOf(p).vTextX"
										:y="svgOf(p).vTextY"
										text-anchor="middle"
										dominant-baseline="central"
										fill="#0f172a"
										:font-size="svgOf(p).fontSize"
										font-weight="600"
										:transform="`rotate(-90 ${svgOf(p).vTextX} ${
											svgOf(p).vTextY
										})`"
									>
										{{ svgOf(p).depthLabel }}
									</text>
								</svg>
								<div v-else class="text-xs text-ink-gray-4">No DXF</div>
							</div>

							<div class="flex flex-1 flex-col p-4">
								<div class="mb-1 flex items-baseline justify-between gap-2">
									<div class="truncate text-sm font-bold text-ink-gray-9">
										{{ displayProfileCode(p) }} · {{ p.profile_name }}
									</div>
									<span class="text-xs capitalize text-ink-gray-5">{{
										p.role || "—"
									}}</span>
								</div>
								<div class="mb-2 text-xs text-ink-gray-5">
									{{ Number(p.width_mm || 0).toFixed(1) }} ×
									{{ Number(p.depth_mm || 0).toFixed(1) }} mm · Bar
									{{ p.bar_lengths || "4880, 5800" }} mm
								</div>
								<div
									class="mt-auto mb-3 flex items-baseline justify-between border-t border-outline-gray-1 pt-2.5"
								>
									<span class="text-xs text-ink-gray-5">
										{{ Number(p.area_mm2 || 0).toFixed(1) }} mm² ·
										{{ Number(p.perimeter_mm || 0).toFixed(0) }} mm
									</span>
									<span class="text-sm font-bold text-ink-gray-9">
										{{ effectiveWeight(p).toFixed(3) }} kg/m
									</span>
								</div>
								<Button
									variant="outline"
									size="sm"
									label="Open profile"
									:route="`/series-studio/profiles/${encodeURIComponent(
										p.name
									)}`"
								/>
							</div>
						</article>
					</div>
				</template>
			</section>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, FormControl, Popover, toast, useList } from "frappe-ui";
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
	getProfileSeriesDoc,
	parseSupportedProducts,
	saveProfileSeries,
	SUPPORTED_PRODUCT_OPTIONS,
	type FenestrationProfileRow,
	type SupportedProduct,
} from "@/studio/api";
import {
	computeCardSvgMetrics,
	displayProfileCode,
	effectiveWeight,
	profileRotationTransform,
} from "@/studio/sectionSvg";

const props = defineProps<{ name?: string }>();
const router = useRouter();

const isEdit = computed(() => Boolean(props.name));
const loadingDoc = ref(false);
const saving = ref(false);
const error = ref("");

const systemTypeOptions = [
	{ label: "Casement", value: "Casement" },
	{ label: "Sliding", value: "Sliding" },
	{ label: "Door", value: "Door" },
];

function defaultProductsForSystem(
	systemType: "Casement" | "Sliding" | "Door"
): SupportedProduct[] {
	if (systemType === "Sliding") return ["Sliding Window", "Sliding Door"];
	if (systemType === "Door") return ["Door"];
	return ["Window"];
}

const form = reactive({
	series_code: "",
	series_title: "",
	system_type: "Casement" as "Casement" | "Sliding" | "Door",
	supported_products: ["Window"] as SupportedProduct[],
	published_version: "" as string | null | undefined,
});

const userEditedProducts = ref(false);
watch(
	() => form.system_type,
	(next) => {
		if (!isEdit.value && !userEditedProducts.value) {
			form.supported_products = defaultProductsForSystem(next);
		}
	}
);

function toggleSupportedProduct(val: SupportedProduct) {
	userEditedProducts.value = true;
	const set = new Set<SupportedProduct>(form.supported_products);
	if (set.has(val)) set.delete(val);
	else set.add(val);
	form.supported_products = SUPPORTED_PRODUCT_OPTIONS.map((o) => o.value).filter((v) =>
		set.has(v)
	);
}

const canSave = computed(() =>
	Boolean(
		form.series_code.trim() &&
			form.series_title.trim() &&
			form.system_type &&
			form.supported_products.length > 0 &&
			!saving.value
	)
);

const roles = [
	"ALL",
	"frame",
	"sash",
	"mullion",
	"transom",
	"bead",
	"gasket",
	"accessory",
] as const;
const selectedRole = ref<string>("ALL");
const profileSearch = ref("");

const profileResource = useList<FenestrationProfileRow>({
	doctype: "Fenestration Profile",
	fields: [
		"name",
		"profile_code",
		"profile_name",
		"series",
		"role",
		"kg_per_m",
		"computed_kg_per_m",
		"use_computed_weight",
		"width_mm",
		"depth_mm",
		"area_mm2",
		"perimeter_mm",
		"bar_lengths",
		"dxf_file",
		"section_svg",
		"section_rotation",
		"section_flip_x",
		"section_flip_y",
	],
	orderBy: "profile_code asc",
	limit: 500,
});

const seriesProfiles = computed(() =>
	(profileResource.data ?? []).filter((p) => p.series === (form.series_code || props.name))
);

const filteredProfiles = computed(() => {
	const q = profileSearch.value.trim().toLowerCase();
	return seriesProfiles.value.filter((p) => {
		if (selectedRole.value !== "ALL" && p.role !== selectedRole.value) return false;
		if (q) {
			const hay = `${p.profile_code || ""} ${p.profile_name || ""} ${
				p.role || ""
			}`.toLowerCase();
			if (!hay.includes(q)) return false;
		}
		return true;
	});
});

function svgOf(p: FenestrationProfileRow) {
	return computeCardSvgMetrics(p.width_mm, p.depth_mm);
}

onMounted(async () => {
	if (!props.name) return;
	loadingDoc.value = true;
	try {
		const doc = await getProfileSeriesDoc(props.name);
		form.series_code = doc.series_code || doc.name;
		form.series_title = doc.series_title || "";
		form.system_type = doc.system_type || "Casement";
		const parsedProducts = parseSupportedProducts(doc.supported_products);
		form.supported_products = parsedProducts.length
			? parsedProducts
			: defaultProductsForSystem(form.system_type);
		form.published_version = doc.published_version || null;
	} catch (e) {
		error.value = e instanceof Error ? e.message : "Could not load profile series";
	} finally {
		loadingDoc.value = false;
	}
});

async function save() {
	if (!canSave.value) return;
	saving.value = true;
	error.value = "";
	try {
		const savedName = await saveProfileSeries(
			{
				series_code: form.series_code.trim(),
				series_title: form.series_title.trim(),
				system_type: form.system_type,
				supported_products: form.supported_products,
			},
			props.name || null
		);
		toast.success(isEdit.value ? "Profile series updated" : "Profile series created");
		if (!isEdit.value) {
			router.replace(`/series-studio/series/${encodeURIComponent(savedName)}`);
		}
	} catch (e) {
		error.value = e instanceof Error ? e.message : "Could not save profile series";
	} finally {
		saving.value = false;
	}
}
</script>
