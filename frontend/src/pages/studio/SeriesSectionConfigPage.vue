<template>
	<div class="mx-auto max-w-[1480px] px-6 py-5">
		<!-- Clean Top Header -->
		<header class="mb-5 flex flex-wrap items-center justify-between gap-4 border-b border-outline-gray-2 pb-4">
			<div>
				<nav aria-label="Breadcrumb" class="mb-1 flex items-center gap-1.5 text-xs text-ink-gray-5">
					<router-link to="/series-studio" class="hover:text-ink-gray-8">Series Studio</router-link>
					<span aria-hidden="true">/</span>
					<router-link :to="`/series-studio/series/${encodeURIComponent(seriesCode)}`" class="hover:text-ink-gray-8">
						{{ seriesCode }}
					</router-link>
					<span aria-hidden="true">/</span>
					<span class="font-medium text-ink-gray-8">Section Templates</span>
				</nav>
				<div class="flex flex-wrap items-center gap-2.5">
					<h1 class="text-lg font-semibold tracking-tight text-ink-gray-9">
						Section Templates · {{ seriesCode }}
					</h1>
					<Badge v-if="seriesDoc?.system_type" theme="blue" :label="seriesDoc.system_type" />
					<Badge
						:theme="configuredCount > 0 ? 'green' : 'gray'"
						:label="`${configuredCount} / ${visibleTemplates.length} Configured`"
					/>
					<Badge v-if="dirty" theme="amber" label="Unsaved" />
				</div>
			</div>

			<div class="flex flex-wrap items-center gap-2">
				<Button
					variant="outline"
					size="sm"
					label="Back to Series"
					:route="`/series-studio/series/${encodeURIComponent(seriesCode)}`"
				/>
				<Button
					variant="subtle"
					size="sm"
					label="Reset Template"
					data-testid="reset-template-btn"
					@click="resetActiveTemplate"
				/>
				<Button
					variant="solid"
					size="sm"
					label="Save Template"
					:loading="saving"
					:disabled="saving || loading"
					data-testid="save-section-config-btn"
					@click="saveConfig"
				/>
			</div>
		</header>

		<div v-if="loading" class="py-20 text-center text-sm text-ink-gray-5">
			Loading section templates…
		</div>

		<template v-else>
			<Alert v-if="error" theme="red" :title="error" class="mb-4" />

			<div
				v-if="!previewSeriesVersion"
				class="rounded-xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900"
			>
				<div class="font-semibold">Create a Series Version first to edit Section Templates</div>
				<p class="mt-1 text-xs text-amber-800">
					Section Templates use the series's rules and DXF profiles from a Series Version to assemble the interactive cross-section preview.
				</p>
				<div class="mt-3">
					<Button
						variant="solid"
						size="sm"
						label="Open Series Versions"
						:route="`/series-studio?tab=versions&series=${encodeURIComponent(seriesCode)}`"
					/>
				</div>
			</div>

			<div v-else class="grid grid-cols-1 gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
				<!-- Left Sidebar: 8–10 Clean Section Assembly Templates -->
				<aside
					data-testid="section-templates-sidebar"
					class="rounded-xl border border-outline-gray-2 bg-surface-white p-3"
				>
					<div class="mb-3 flex items-center justify-between px-1">
						<span class="text-xs font-semibold uppercase tracking-wider text-ink-gray-5">
							Assembly Templates
						</span>
						<span class="text-[11px] text-ink-gray-5">Auto-glass</span>
					</div>

					<div class="space-y-4">
						<div v-for="group in groupedTemplates" :key="group.id" class="space-y-1">
							<div class="px-2 text-[11px] font-semibold uppercase tracking-wider text-ink-gray-4">
								{{ group.label }}
							</div>
							<button
								v-for="tpl in group.items"
								:key="tpl.key"
								type="button"
								:data-testid="`template-item-${tpl.key}`"
								class="flex w-full items-start justify-between gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors"
								:class="
									activeTemplateKey === tpl.key
										? 'border-blue-300 bg-blue-50 text-blue-950 shadow-2xs ring-1 ring-blue-200/70'
										: 'border-transparent bg-transparent text-ink-gray-8 hover:border-outline-gray-2 hover:bg-surface-gray-1'
								"
								@click="selectTemplate(tpl.key)"
							>
								<div class="min-w-0 flex-1">
									<div class="truncate text-xs font-semibold">{{ tpl.label }}</div>
									<div
										class="mt-0.5 truncate text-[11px]"
										:class="activeTemplateKey === tpl.key ? 'text-blue-700' : 'text-ink-gray-5'"
									>
										{{ tpl.components.join(' · ') }}
									</div>
								</div>
								<span
									class="mt-1 inline-block size-2 shrink-0 rounded-full"
									:class="
										isTemplateConfigured(tpl.key)
											? 'bg-emerald-500'
											: activeTemplateKey === tpl.key
												? 'bg-blue-300'
												: 'bg-outline-gray-3'
									"
									:title="isTemplateConfigured(tpl.key) ? 'Configured' : 'Not configured yet'"
								/>
							</button>
						</div>
					</div>
				</aside>

				<!-- Right Main Editor: Controls Strip + Full Interactive SectionView -->
				<main class="flex min-w-0 flex-col gap-3">
					<!-- Controls Strip -->
					<section
						data-testid="template-controls-bar"
						class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-outline-gray-2 bg-surface-white px-4 py-3"
					>
						<div class="min-w-0">
							<div class="flex flex-wrap items-center gap-2">
								<h2 class="text-sm font-semibold text-ink-gray-9">{{ activeMeta.label }}</h2>
								<span
									v-for="comp in activeMeta.components"
									:key="comp"
									class="rounded-md bg-surface-gray-1 px-2 py-0.5 text-[11px] font-medium text-ink-gray-7"
								>
									{{ comp }}
								</span>
								<span class="rounded-md bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700">
									Auto Glass
								</span>
							</div>
							<p class="mt-0.5 text-xs text-ink-gray-5">{{ activeMeta.description }}</p>
						</div>

						<!-- Preview Glass + Optional Role Overrides -->
						<div class="flex flex-wrap items-center gap-3">
							<div class="flex items-center gap-1.5">
								<label class="text-xs font-medium text-ink-gray-5">Preview Glass</label>
								<select
									v-model="activeGlassCode"
									data-testid="preview-glass-select"
									class="h-8 rounded-lg border border-outline-gray-2 bg-surface-white px-2.5 py-0 text-xs font-medium leading-8 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
									@change="onGlassChanged"
								>
									<option v-for="g in glasses" :key="g.name" :value="g.glass_code || g.name">
										{{ g.glass_name || g.glass_code }} ({{ g.thickness_mm }} mm)
									</option>
									<option v-if="!glasses.length" value="6CTG">6 mm Default</option>
								</select>
							</div>

							<div
								v-if="resolvedGlassRule"
								data-testid="resolved-glass-rule-pill"
								class="flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50/70 px-2.5 py-1 text-[11px] text-emerald-900"
							>
								<template v-if="resolvedRuleHasNoBead">
									<span class="font-semibold">No Beading</span>
									<span class="opacity-40">·</span>
									<span>Gaskets only</span>
								</template>
								<template v-else>
									<span class="font-semibold">Bead: {{ resolvedGlassRule.bead_profile || 'Auto' }}</span>
									<span class="opacity-40">·</span>
									<span class="capitalize">{{ resolvedGlassRule.bead_side }}</span>
								</template>
								<router-link
									:to="`/series-studio/glazing-config?series=${encodeURIComponent(seriesCode)}`"
									class="ml-1 font-medium text-emerald-700 underline"
								>
									Edit
								</router-link>
							</div>
							<router-link
								v-else
								:to="`/series-studio/glazing-config?series=${encodeURIComponent(seriesCode)}`"
								class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 px-2.5 py-1 text-[11px] font-medium text-ink-gray-7 hover:bg-surface-gray-2"
							>
								Configure Bead &amp; Gasket →
							</router-link>
						</div>
					</section>

					<!-- Optional Profile Overrides Row (Frame / Mullion / Sash for this template) -->
					<section
						v-if="profileOverrideSelectors.length"
						class="flex flex-wrap items-center gap-3 rounded-xl border border-outline-gray-2 bg-surface-gray-1/50 px-4 py-2"
					>
						<span class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">
							Template Profiles
						</span>
						<div
							v-for="sel in profileOverrideSelectors"
							:key="sel.role"
							class="flex items-center gap-1.5"
						>
							<label class="text-xs text-ink-gray-6">{{ sel.label }}</label>
							<select
								:value="activeProfileOverrides[sel.role] || ''"
								:data-testid="`override-profile-${sel.role}`"
								class="h-8 rounded-md border border-outline-gray-2 bg-surface-white px-2.5 py-0 text-xs leading-8 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
								@change="onProfileOverrideChange(sel.role, ($event.target as HTMLSelectElement).value)"
							>
								<option value="">
									{{ autoTemplateProfiles[sel.role] ? `Auto (${autoTemplateProfiles[sel.role]})` : 'Series Default' }}
								</option>
								<option v-for="p in sel.options" :key="p.name" :value="p.profile_code || p.name">
									{{ p.profile_code }} · {{ p.profile_name }}{{ p.profile_type && p.profile_type !== 'Both' ? ` [${p.profile_type}]` : '' }}
								</option>
							</select>
						</div>
					</section>

					<!-- Glass Domain Bar: Keeps any glass thickness inside the glazing pocket without clipping -->
					<section
						data-testid="glass-domain-controls-bar"
						class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-outline-gray-2 bg-surface-white px-4 py-2.5"
					>
						<div class="flex flex-wrap items-center gap-2.5">
							<span class="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-gray-8">
								<span
									class="inline-block size-2.5 rounded-xs border"
									:class="
										activeGlassDomain.configured
											? 'border-red-600 bg-red-100'
											: 'border-outline-gray-3 bg-surface-gray-2'
									"
								/>
								Glass Domain
							</span>

							<template v-if="activeGlassDomain.configured">
								<span
									v-if="measuredBw && measuredBw.narrowedByBead"
									data-testid="raycast-narrowed-bw-pill"
									class="rounded-md bg-sky-50 px-2 py-0.5 font-mono text-[11px] font-semibold text-sky-800"
								>
									Pocket {{ measuredBw.pocketBwMm }} mm → Bead BW {{ measuredBw.effectiveBwMm }} mm
								</span>
								<span v-else class="rounded-md bg-red-50 px-2 py-0.5 font-mono text-[11px] font-semibold text-red-700">
									{{ effectiveDomainDepthMm }} mm depth
								</span>
								<span
									class="rounded-md px-2 py-0.5 text-[11px] font-medium"
									:class="
										previewGlassExceedsDomain
											? 'bg-amber-50 text-amber-800'
											: 'bg-emerald-50 text-emerald-700'
									"
								>
									{{
										previewGlassExceedsDomain
											? `⚠ ${activeGlassThicknessMm} mm glass exceeds domain`
											: `✓ Fits ${activeGlassThicknessMm} mm glass cleanly`
									}}
								</span>
								<span
									v-if="previewGasketMeta"
									class="rounded-md bg-surface-gray-1 px-2 py-0.5 text-[11px] font-medium text-ink-gray-7"
								>
									Gaskets: {{ previewGasketMeta.outer_code }} ({{ previewGasketMeta.outer_mm }}mm) · {{ previewGasketMeta.inner_code }} ({{ previewGasketMeta.inner_mm }}mm)
								</span>
							</template>
							<span v-else-if="isRaycastActive" class="text-xs font-medium text-sky-700">
								Move cursor inside the sash/frame glazing pocket and click once to lock the 4 ray anchors…
							</span>
							<span v-else class="text-xs text-ink-gray-5">
								Click <strong>Raycast Pocket</strong> and click inside the pocket to auto-lock the domain, bead corners &amp; gaskets.
							</span>
							<span
								data-testid="axis-sync-pill"
								class="rounded-md px-2 py-0.5 text-[11px] font-medium"
								:class="templateMirrorSync ? 'bg-blue-50 text-blue-700' : 'bg-surface-gray-1 text-ink-gray-6'"
								:title="
									templateMirrorSync
										? 'Edits in B–B Horizontal automatically sync to A–A Vertical. Turn Mirror & Sync off to customize A–A independently.'
										: 'B–B Horizontal and A–A Vertical are edited independently.'
								"
							>
								{{ templateMirrorSync ? 'B–B ↔ A–A Auto-Sync' : 'Independent A–A' }}
							</span>
						</div>

						<div class="flex flex-wrap items-center gap-2">
							<Button
								:variant="isRaycastActive ? 'solid' : 'subtle'"
								size="sm"
								:label="isRaycastActive ? 'Cancel Raycast' : 'Raycast Pocket'"
								data-testid="raycast-pocket-btn"
								@click="toggleRaycastFromBar"
							/>
							<Button
								v-if="activeGlassDomain.raycast?.enabled && measuredBw"
								variant="outline"
								size="sm"
								:loading="syncingBw"
								label="Sync BW to Config"
								data-testid="sync-bw-glazing-btn"
								@click="syncMeasuredBwToGlazingConfig"
							/>
							<template v-if="activeGlassDomain.configured">
								<span class="text-[11px] font-medium text-ink-gray-5">Align</span>
								<div class="inline-flex rounded-md border border-outline-gray-2 bg-surface-gray-1 p-0.5">
									<button
										v-for="opt in domainAlignOptions"
										:key="opt.value"
										type="button"
										:data-testid="`domain-align-${opt.value}`"
										class="rounded px-2 py-0.5 text-[11px] font-semibold transition-colors"
										:class="
											activeGlassDomain.align === opt.value
												? 'bg-white text-gray-900 shadow-2xs'
												: 'text-ink-gray-6 hover:text-ink-gray-9'
										"
										@click="setGlassDomainAlign(opt.value)"
									>
										{{ opt.label }}
									</button>
								</div>
								<button
									type="button"
									data-testid="clear-glass-domain-btn"
									class="ml-1 text-xs font-medium text-ink-gray-5 hover:text-red-600"
									@click="clearGlassDomain"
								>
									Clear
								</button>
							</template>
							<Button
								v-else
								variant="outline"
								size="sm"
								label="+ Set Glass Domain"
								data-testid="init-glass-domain-btn"
								@click="initGlassDomainFromCanvas"
							/>
						</div>
					</section>

					<!-- Full Interactive SectionView Canvas (auto-seats glass inside Glass Domain) -->
					<section
						data-testid="template-section-canvas"
						class="flex h-[600px] flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white shadow-2xs"
					>
						<SectionView
							ref="sectionViewRef"
							:key="`${activeTemplateKey}-${activeAxis}-${editorNonce}`"
							:design="templateDesign"
							:series-version="previewSeriesVersion"
							:axis="activeAxis"
							:at="null"
							:auto-glass="true"
							:glass-domain="activeGlassDomain"
							:editable-glass-domain="true"
							:gasket-meta="previewGasketMeta"
							@update:axis="onAxisChange"
							@update:mirror-sync="onMirrorSyncChange"
							@update:section-map="onSectionMapUpdate"
							@update:glass-domain="onGlassDomainUpdate"
							@update:raycast-mode="isRaycastActive = $event"
							@update:measured-bw="measuredBw = $event"
						/>
					</section>

					<!-- Subtle CAD Workflow Hint -->
					<footer class="flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-ink-gray-5">
						<span>
							Drag, rotate, or flip Frame, Mullion, Sash &amp; Bead profiles directly on the canvas — glass automatically seats between them.
						</span>
						<span>
							Saved templates apply automatically in the Window Designer &amp; 3D View.
						</span>
					</footer>
				</main>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, toast } from 'frappe-ui'
import { computed, onMounted, ref } from 'vue'
import SectionView from '@/components/SectionView.vue'
import type { CutAxis } from '@/api'
import type { Design, SectionPieceTransform } from '@/design/types'
import {
	createEmptyGlassDomain,
	createEmptySectionConfig,
	createEmptySectionTemplate,
	getSeriesSectionConfig,
	saveGlobalGlazingRules,
	saveSeriesSectionConfig,
	type FenestrationGlassRow,
	type FenestrationHardwareRow,
	type FenestrationProfileRow,
	type GlassDomainAlign,
	type GlassGlazingRule,
	type GlazingAutoConfig,
	type GlobalGlazingRule,
	type ProfileSeriesRow,
	type SectionGlassDomain,
	type SectionTemplateEntry,
	type SectionTemplateKey,
	type SeriesSectionConfig,
} from '@/studio/api'
import type { PaneGasketsMeta } from '@/design/glassDomain'
import { defaultGlazingAutoConfig, normalizeGlazingAutoConfig, resolveGlazingByWidth } from '@/studio/glazingSolver'
import {
	autoProfilesForTemplate,
	buildTemplateDesign,
	extractAxisTemplateData,
	getTemplateMeta,
	hasAxisTemplateData,
	mirrorAxisTemplateData,
	SECTION_TEMPLATE_LIST,
	stripGlassFromSectionMap,
	templatesForSupportedProducts,
	type SectionTemplateMeta,
} from '@/studio/sectionTemplates'

const props = defineProps<{ name: string }>()
const seriesCode = computed(() => props.name)

const loading = ref(true)
const saving = ref(false)
const dirty = ref(false)
const error = ref('')

const seriesDoc = ref<ProfileSeriesRow | null>(null)
const previewSeriesVersion = ref<string | null>(null)
const config = ref<SeriesSectionConfig>(createEmptySectionConfig())
const globalGlazingRules = ref<GlobalGlazingRule[]>([])
const globalGlazingAuto = ref<GlazingAutoConfig>(defaultGlazingAutoConfig())
const gasketHardware = ref<FenestrationHardwareRow[]>([])
const profiles = ref<FenestrationProfileRow[]>([])
const glasses = ref<FenestrationGlassRow[]>([])

const activeTemplateKey = ref<SectionTemplateKey>('fixed_window')
const activeAxis = ref<CutAxis>('h')
const templateMirrorSync = ref(true)
const editorNonce = ref(0)
const liveSectionMap = ref<Record<string, SectionPieceTransform>>({})
const sectionViewRef = ref<InstanceType<typeof SectionView> | null>(null)
const isRaycastActive = ref(false)
const syncingBw = ref(false)
const measuredBw = ref<{ pocketBwMm: number; effectiveBwMm: number; narrowedByBead: boolean } | null>(null)

function ensureTemplate(key: SectionTemplateKey): SectionTemplateEntry {
	if (!config.value.templates) {
		config.value.templates = createEmptySectionConfig().templates!
	}
	if (!config.value.templates[key]) {
		config.value.templates[key] = createEmptySectionTemplate()
	}
	return config.value.templates[key]
}

const activeTemplate = computed<SectionTemplateEntry>(() => ensureTemplate(activeTemplateKey.value))
const activeMeta = computed<SectionTemplateMeta>(() => getTemplateMeta(activeTemplateKey.value))

const visibleTemplates = computed(() =>
	templatesForSupportedProducts(seriesDoc.value?.supported_products),
)

const groupedTemplates = computed(() => {
	const isSlidingSeries = String(seriesDoc.value?.system_type || '').toLowerCase() === 'sliding'
	const allowed = visibleTemplates.value
	const fixedGroup = {
		id: 'fixed',
		label: 'Fixed',
		items: allowed.filter((t) => t.group === 'fixed'),
	}
	const openableGroup = {
		id: 'openable',
		label: 'Openable',
		items: allowed.filter((t) => t.group === 'openable'),
	}
	const slidingGroup = {
		id: 'sliding',
		label: 'Sliding',
		items: allowed.filter((t) => t.group === 'sliding'),
	}
	const ordered = isSlidingSeries ? [slidingGroup, fixedGroup, openableGroup] : [fixedGroup, openableGroup, slidingGroup]
	return ordered.filter((g) => g.items.length > 0)
})

function isTemplateConfigured(key: SectionTemplateKey): boolean {
	return Boolean(config.value.templates?.[key]?.configured)
}

const configuredCount = computed(() => visibleTemplates.value.filter((t) => isTemplateConfigured(t.key)).length)

const defaultGlassCode = computed(() => {
	const first = glasses.value[0]
	return first ? first.glass_code || first.name : '6CTG'
})

const activeGlassCode = computed({
	get: () => activeTemplate.value.glass || defaultGlassCode.value,
	set: (val: string) => {
		ensureTemplate(activeTemplateKey.value).glass = val
	},
})

const activeGlassDoc = computed<FenestrationGlassRow | null>(
	() => glasses.value.find((g) => (g.glass_code || g.name) === activeGlassCode.value) ?? glasses.value[0] ?? null,
)

const activeGlassThicknessMm = computed(() => Number(activeGlassDoc.value?.thickness_mm || 6))

const domainAlignOptions: Array<{ value: GlassDomainAlign; label: string }> = [
	{ value: 'center', label: 'Center' },
	{ value: 'top', label: 'Outer (Top)' },
	{ value: 'bottom', label: 'Inner (Bottom)' },
]

function syncOtherAxisIfEnabled(tpl: SectionTemplateEntry, fromAxis: CutAxis) {
	if (!templateMirrorSync.value) return
	const srcKey = fromAxis === 'h' ? 'axis_h' : 'axis_v'
	const dstKey = fromAxis === 'h' ? 'axis_v' : 'axis_h'
	const toAxis: CutAxis = fromAxis === 'h' ? 'v' : 'h'
	if (!hasAxisTemplateData(tpl[srcKey])) return
	tpl[dstKey] = mirrorAxisTemplateData(tpl[srcKey], fromAxis, toAxis)
}

function onMirrorSyncChange(val: boolean) {
	templateMirrorSync.value = val
	if (val) {
		const tpl = ensureTemplate(activeTemplateKey.value)
		captureCurrentAxisIntoConfig(false)
		syncOtherAxisIfEnabled(tpl, activeAxis.value)
	}
}

const activeGlassDomain = computed<SectionGlassDomain>(() => {
	const tpl = ensureTemplate(activeTemplateKey.value)
	const axisKey = activeAxis.value === 'h' ? 'axis_h' : 'axis_v'
	const primary = tpl[axisKey]?.glassDomain
	if (primary?.configured) return primary
	if (templateMirrorSync.value) {
		const otherKey = activeAxis.value === 'h' ? 'axis_v' : 'axis_h'
		const fallback = tpl[otherKey]?.glassDomain
		if (fallback?.configured) return { ...fallback }
	}
	return primary ?? createEmptyGlassDomain()
})

const glassDomainDepthMm = computed(() => {
	const d = activeGlassDomain.value
	if (!d.configured) return '0'
	return String(Math.round(Math.max(0, d.maxY - d.minY) * 10) / 10)
})

const effectiveDomainDepthNum = computed(() => {
	if (measuredBw.value?.effectiveBwMm) return measuredBw.value.effectiveBwMm
	const d = activeGlassDomain.value
	if (!d.configured) return 0
	return Math.round(Math.max(0, d.maxY - d.minY) * 10) / 10
})

const effectiveDomainDepthMm = computed(() => String(effectiveDomainDepthNum.value))

const previewGlassExceedsDomain = computed(() => {
	const d = activeGlassDomain.value
	if (!d.configured) return false
	return activeGlassThicknessMm.value > effectiveDomainDepthNum.value + 0.05
})

function onGlassDomainUpdate(domain: SectionGlassDomain) {
	const tpl = ensureTemplate(activeTemplateKey.value)
	const axisKey = activeAxis.value === 'h' ? 'axis_h' : 'axis_v'
	tpl[axisKey] = {
		sectionMap: tpl[axisKey]?.sectionMap ?? {},
		roleTransforms: tpl[axisKey]?.roleTransforms ?? {},
		beadByCode: tpl[axisKey]?.beadByCode ?? {},
		glassDomain: { ...domain },
	}
	if (templateMirrorSync.value) {
		const otherKey = activeAxis.value === 'h' ? 'axis_v' : 'axis_h'
		tpl[otherKey] = {
			sectionMap: tpl[otherKey]?.sectionMap ?? {},
			roleTransforms: tpl[otherKey]?.roleTransforms ?? {},
			beadByCode: tpl[otherKey]?.beadByCode ?? {},
			glassDomain: { ...domain },
		}
	}
	dirty.value = true
}

function initGlassDomainFromCanvas() {
	sectionViewRef.value?.initOrToggleGlassDomain?.()
}

function toggleRaycastFromBar() {
	sectionViewRef.value?.startRaycastDomain?.()
}

const previewGasketMeta = computed<PaneGasketsMeta | null>(() => {
	const host = activeMeta.value.group === 'fixed' ? 'frame' : 'sash'
	const app = activeMeta.value.application
	const t = activeGlassThicknessMm.value
	const autoRes = resolveGlazingByWidth(
		globalGlazingAuto.value,
		gasketHardware.value,
		t,
		seriesCode.value,
		host,
		app,
	)
	if (autoRes?.ok) {
		return {
			outer_code: autoRes.outer_gasket_hardware,
			outer_name: autoRes.outer_gasket_name,
			outer_mm: autoRes.outer_gasket_mm,
			inner_code: autoRes.inner_gasket_hardware,
			inner_name: autoRes.inner_gasket_name,
			inner_mm: autoRes.inner_gasket_mm,
			bead_side: autoRes.bead_side,
			no_bead: autoRes.no_bead,
		}
	}
	const r = resolvedGlassRule.value
	if (!r) return null
	const outerCode = ('outer_gasket_hardware' in r ? r.outer_gasket_hardware : '') || r.outer_gasket_item || ''
	const innerCode = ('inner_gasket_hardware' in r ? r.inner_gasket_hardware : '') || r.inner_gasket_item || ''
	if (!outerCode && !innerCode) return null
	const findMm = (code: string) =>
		Number(
			gasketHardware.value.find(
				(h) => (h.hardware_code || h.name) === code || h.item === code,
			)?.thickness_mm || 3,
		)
	return {
		outer_code: outerCode,
		outer_name: r.outer_gasket_name || outerCode,
		outer_mm: findMm(outerCode),
		inner_code: innerCode,
		inner_name: r.inner_gasket_name || innerCode,
		inner_mm: findMm(innerCode),
		bead_side: r.bead_side || 'inside',
		no_bead: resolvedRuleHasNoBead.value,
	}
})

async function syncMeasuredBwToGlazingConfig() {
	if (!measuredBw.value) return
	syncingBw.value = true
	try {
		const host = activeMeta.value.group === 'fixed' ? 'frame' : 'sash'
		const app = activeMeta.value.application
		const nextAuto = normalizeGlazingAutoConfig(globalGlazingAuto.value)
		nextAuto.enabled = true
		const upsertChannel = (beadCode: string, noBead: boolean, bw: number) => {
			if (!(bw > 0)) return
			const existing = nextAuto.channels.find(
				(c) =>
					c.series.toLowerCase() === seriesCode.value.toLowerCase() &&
					c.no_bead === noBead &&
					(noBead ? c.host === host || c.host === 'both' : c.bead_profile === beadCode),
			)
			if (existing) {
				existing.bead_width_mm = bw
			} else {
				nextAuto.channels.push({
					id: `glazing_ch_${Date.now()}_${nextAuto.channels.length + 1}`,
					series: seriesCode.value,
					label: noBead ? `${host === 'sash' ? 'Sash' : 'Frame'} Pocket (No Bead)` : '',
					profile_type: app,
					host,
					bead_profile: noBead ? '' : beadCode,
					no_bead: noBead,
					bead_width_mm: bw,
					bead_side: resolvedGlassRule.value?.bead_side || 'inside',
				})
			}
		}

		// Always record the raw pocket width for sash/no-bead glazing when applicable
		if (host === 'sash' || resolvedRuleHasNoBead.value) {
			upsertChannel('', true, measuredBw.value.pocketBwMm)
		}
		// If a bead narrowed the pocket, also record that bead's measured BW
		const activeBead = resolvedGlassRule.value?.bead_profile || ''
		if (activeBead && !resolvedRuleHasNoBead.value) {
			upsertChannel(activeBead, false, measuredBw.value.effectiveBwMm)
		}

		const res = await saveGlobalGlazingRules(globalGlazingRules.value, nextAuto)
		if (res.auto_config) globalGlazingAuto.value = normalizeGlazingAutoConfig(res.auto_config)
		toast.success(`Synced measured BW (${measuredBw.value.effectiveBwMm} mm) to Bead & Gasket Config`)
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Could not sync BW to Glazing Config')
	} finally {
		syncingBw.value = false
	}
}

function setGlassDomainAlign(align: GlassDomainAlign) {
	if (!activeGlassDomain.value.configured) return
	onGlassDomainUpdate({ ...activeGlassDomain.value, align })
}

function clearGlassDomain() {
	onGlassDomainUpdate(createEmptyGlassDomain())
}

const resolvedGlassRule = computed<GlobalGlazingRule | GlassGlazingRule | null>(() => {
	const host = activeMeta.value.group === 'fixed' ? 'frame' : 'sash'
	const app = activeMeta.value.application
	const t = activeGlassThicknessMm.value
	const autoRes = resolveGlazingByWidth(
		globalGlazingAuto.value,
		gasketHardware.value,
		t,
		seriesCode.value,
		host,
		app,
	)
	if (autoRes?.ok) {
		return {
			id: autoRes.id,
			label: autoRes.label,
			profile_type: autoRes.profile_type,
			min_glass_mm: t,
			max_glass_mm: t,
			host: autoRes.host,
			bead_profile: autoRes.bead_profile,
			no_bead: autoRes.no_bead,
			bead_side: autoRes.bead_side,
			inner_gasket_hardware: autoRes.inner_gasket_hardware,
			inner_gasket_item: autoRes.inner_gasket_item,
			inner_gasket_name: autoRes.inner_gasket_name,
			outer_gasket_hardware: autoRes.outer_gasket_hardware,
			outer_gasket_item: autoRes.outer_gasket_item,
			outer_gasket_name: autoRes.outer_gasket_name,
		}
	}
	let bestGlobal: GlobalGlazingRule | null = null
	let bestScore = -1
	for (const r of globalGlazingRules.value) {
		const rHost = r.host || 'both'
		if (rHost !== 'both' && rHost !== host) continue
		const rType = r.profile_type || 'both'
		if (rType !== 'both' && rType !== app) continue
		if (t < Number(r.min_glass_mm) - 1e-6 || t > Number(r.max_glass_mm) + 1e-6) continue
		const score = (rType === app ? 2 : 1) * 10 + (rHost === host ? 2 : 1)
		if (score > bestScore) {
			bestScore = score
			bestGlobal = r
		}
	}
	if (bestGlobal) return bestGlobal
	const g = activeGlassDoc.value
	const rules = g?.glazing_rules ?? []
	const sLower = seriesCode.value.toLowerCase()
	return (
		rules.find(
			(r) =>
				String(r.series || '').trim().toLowerCase() === sLower &&
				(r.host === 'both' || r.host === host),
		) ?? null
	)
})

const resolvedRuleHasNoBead = computed(() => {
	if (activeMeta.value.group !== 'fixed' && activeMeta.value.application === 'window') return true
	const r = resolvedGlassRule.value
	if (!r) return false
	if ('no_bead' in r && r.no_bead) return true
	return !String(r.bead_profile || '').trim()
})

const autoTemplateProfiles = computed<Record<string, string>>(() =>
	autoProfilesForTemplate(activeMeta.value, profiles.value),
)

const activeProfileOverrides = computed<Record<string, string>>(() => activeTemplate.value.profiles || {})

const effectiveTemplateProfiles = computed<Record<string, string>>(() => ({
	...autoTemplateProfiles.value,
	...activeProfileOverrides.value,
}))

function sortProfilesForApplication(list: FenestrationProfileRow[], app: 'window' | 'door'): FenestrationProfileRow[] {
	const target = app === 'door' ? 'Door' : 'Window'
	const rank = (p: FenestrationProfileRow) =>
		p.profile_type === target ? 0 : !p.profile_type || p.profile_type === 'Both' ? 1 : 2
	return [...list].sort((a, b) => rank(a) - rank(b) || (a.profile_code || a.name).localeCompare(b.profile_code || b.name))
}

const profileOverrideSelectors = computed(() => {
	const meta = activeMeta.value
	const selectors: Array<{ role: string; label: string; options: FenestrationProfileRow[] }> = []
	const frames = sortProfilesForApplication(
		profiles.value.filter((p) => p.role === 'frame'),
		meta.application,
	)
	if (frames.length > 1) {
		selectors.push({ role: 'frame', label: 'Frame', options: frames })
	}
	if (meta.group !== 'fixed') {
		const sashes = sortProfilesForApplication(
			profiles.value.filter((p) => p.role === 'sash'),
			meta.application,
		)
		if (sashes.length > 1) {
			selectors.push({ role: 'sash', label: 'Sash', options: sashes })
		}
	}
	if (meta.hasMullion) {
		const barRole = activeAxis.value === 'v' ? 'transom' : 'mullion'
		const bars = sortProfilesForApplication(
			profiles.value.filter((p) => p.role === barRole || p.role === 'mullion' || p.role === 'transom'),
			meta.application,
		)
		if (bars.length > 1) {
			selectors.push({ role: barRole, label: barRole === 'transom' ? 'Transom' : 'Mullion', options: bars })
		}
	}
	return selectors
})

const templateDesign = computed<Design>(() =>
	buildTemplateDesign(
		activeTemplateKey.value,
		activeAxis.value,
		activeGlassCode.value,
		effectiveTemplateProfiles.value,
		liveSectionMap.value,
		seriesCode.value,
		templateMirrorSync.value,
	),
)

function loadLiveMapFromTemplate() {
	const tpl = ensureTemplate(activeTemplateKey.value)
	const axisKey = activeAxis.value === 'h' ? 'axis_h' : 'axis_v'
	const otherKey = activeAxis.value === 'h' ? 'axis_v' : 'axis_h'
	const fromAxis: CutAxis = activeAxis.value === 'h' ? 'v' : 'h'
	if (templateMirrorSync.value && !hasAxisTemplateData(tpl[axisKey]) && hasAxisTemplateData(tpl[otherKey])) {
		tpl[axisKey] = mirrorAxisTemplateData(tpl[otherKey], fromAxis, activeAxis.value)
	}
	liveSectionMap.value = { ...(tpl[axisKey]?.sectionMap ?? {}) }
}

function captureCurrentAxisIntoConfig(markConfigured = false) {
	const tpl = ensureTemplate(activeTemplateKey.value)
	const axisKey = activeAxis.value === 'h' ? 'axis_h' : 'axis_v'
	const snap = sectionViewRef.value?.getSectionSnapshot?.()
	if (snap && snap.pieces.length > 0) {
		tpl[axisKey] = extractAxisTemplateData(snap, tpl[axisKey])
		syncOtherAxisIfEnabled(tpl, activeAxis.value)
		if (markConfigured) tpl.configured = true
	} else if (Object.keys(liveSectionMap.value).length > 0) {
		tpl[axisKey] = {
			...(tpl[axisKey] ?? { sectionMap: {}, roleTransforms: {}, beadByCode: {} }),
			sectionMap: stripGlassFromSectionMap(liveSectionMap.value),
		}
		syncOtherAxisIfEnabled(tpl, activeAxis.value)
		if (markConfigured) tpl.configured = true
	}
}

function selectTemplate(key: SectionTemplateKey) {
	if (key === activeTemplateKey.value) return
	if (dirty.value) captureCurrentAxisIntoConfig(false)
	activeTemplateKey.value = key
	activeAxis.value = 'h'
	loadLiveMapFromTemplate()
	editorNonce.value += 1
}

function onAxisChange(nextAxis: CutAxis) {
	if (nextAxis === activeAxis.value) return
	captureCurrentAxisIntoConfig(false)
	if (templateMirrorSync.value) {
		syncOtherAxisIfEnabled(ensureTemplate(activeTemplateKey.value), activeAxis.value)
	}
	activeAxis.value = nextAxis
	loadLiveMapFromTemplate()
}

function onSectionMapUpdate(nextMap: Record<string, SectionPieceTransform>) {
	liveSectionMap.value = { ...nextMap }
	const tpl = ensureTemplate(activeTemplateKey.value)
	const axisKey = activeAxis.value === 'h' ? 'axis_h' : 'axis_v'
	const snap = sectionViewRef.value?.getSectionSnapshot?.()
	if (snap && snap.pieces.length > 0) {
		tpl[axisKey] = extractAxisTemplateData(
			{ ...snap, sectionMap: nextMap },
			tpl[axisKey],
		)
	} else {
		tpl[axisKey] = {
			...(tpl[axisKey] ?? { sectionMap: {}, roleTransforms: {}, beadByCode: {} }),
			sectionMap: stripGlassFromSectionMap(nextMap),
		}
	}
	syncOtherAxisIfEnabled(tpl, activeAxis.value)
	dirty.value = true
}

function onGlassChanged() {
	captureCurrentAxisIntoConfig(false)
	dirty.value = true
	editorNonce.value += 1
}

function onProfileOverrideChange(role: string, code: string) {
	const tpl = ensureTemplate(activeTemplateKey.value)
	const next = { ...(tpl.profiles ?? {}) }
	if (code) next[role] = code
	else delete next[role]
	tpl.profiles = next
	dirty.value = true
	editorNonce.value += 1
}

function resetActiveTemplate() {
	if (!config.value.templates) config.value.templates = createEmptySectionConfig().templates!
	config.value.templates[activeTemplateKey.value] = createEmptySectionTemplate()
	liveSectionMap.value = {}
	dirty.value = true
	editorNonce.value += 1
	toast.info(`Reset ${activeMeta.value.label} template`)
}

async function loadData() {
	loading.value = true
	error.value = ''
	try {
		const res = await getSeriesSectionConfig(seriesCode.value)
		seriesDoc.value = res.series
		previewSeriesVersion.value = res.preview_series_version || res.series.published_version || null
		config.value = {
			...createEmptySectionConfig(),
			...(res.config ?? {}),
			templates: {
				...createEmptySectionConfig().templates!,
				...(res.config?.templates ?? {}),
			},
		}
		globalGlazingRules.value = res.global_glazing_rules ?? []
		globalGlazingAuto.value = res.global_glazing_auto ?? defaultGlazingAutoConfig()
		gasketHardware.value = res.gasket_hardware ?? []
		profiles.value = res.profiles ?? []
		glasses.value = res.glasses ?? []

		const allowedKeys = visibleTemplates.value.map((t) => t.key)
		if (String(res.series?.system_type || '').toLowerCase() === 'sliding' && allowedKeys.includes('sliding_window')) {
			activeTemplateKey.value = 'sliding_window'
		} else if (allowedKeys.length && !allowedKeys.includes(activeTemplateKey.value)) {
			activeTemplateKey.value = allowedKeys[0]
		}
		loadLiveMapFromTemplate()
		dirty.value = false
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not load section templates'
	} finally {
		loading.value = false
	}
}

async function saveConfig() {
	saving.value = true
	error.value = ''
	try {
		captureCurrentAxisIntoConfig(true)
		ensureTemplate(activeTemplateKey.value).glass = activeGlassCode.value
		const res = await saveSeriesSectionConfig(seriesCode.value, config.value)
		config.value = {
			...createEmptySectionConfig(),
			...(res.config ?? config.value),
			templates: {
				...createEmptySectionConfig().templates!,
				...(res.config?.templates ?? config.value.templates ?? {}),
			},
		}
		loadLiveMapFromTemplate()
		dirty.value = false
		toast.success(`Saved ${activeMeta.value.label} template for ${seriesCode.value}`)
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not save section templates'
		toast.error(error.value)
	} finally {
		saving.value = false
	}
}

onMounted(() => {
	loadData()
})
</script>
