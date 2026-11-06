<template>
	<div class="mx-auto max-w-6xl p-6">
		<header class="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-outline-gray-2 pb-4">
			<div>
				<nav aria-label="Breadcrumb" class="mb-1 flex items-center gap-1.5 text-sm text-ink-gray-5">
					<router-link to="/series-studio?tab=versions" class="hover:text-ink-gray-8">
						Series Studio
					</router-link>
					<span aria-hidden="true">/</span>
					<router-link
						:to="doc.series ? `/series-studio?tab=versions&series=${doc.series}` : '/series-studio?tab=versions'"
						class="hover:text-ink-gray-8"
					>
						Series Version
					</router-link>
					<span aria-hidden="true">/</span>
					<span class="font-medium text-ink-gray-8">{{ isEdit ? doc.name : 'New Series Version' }}</span>
				</nav>
				<div class="flex flex-wrap items-center gap-2.5">
					<h1 class="text-xl font-semibold text-ink-gray-9">
						{{ isEdit ? doc.name : 'New Series Version' }}
					</h1>
					<Badge
						:theme="doc.docstatus === 1 ? 'green' : doc.docstatus === 2 ? 'red' : 'amber'"
						:label="doc.docstatus === 1 ? 'Published' : doc.docstatus === 2 ? 'Cancelled' : 'Draft'"
					/>
					<Badge v-if="doc.amended_from" theme="gray" :label="`Amended from ${doc.amended_from}`" />
				</div>
			</div>

			<div class="flex flex-wrap items-center gap-2">
				<Button variant="outline" label="Back to Versions" @click="goBack" />
				<template v-if="!isEdit">
					<Button
						variant="solid"
						label="Create Draft Version"
						:loading="saving"
						:disabled="!doc.series || saving"
						data-testid="save-version-btn"
						@click="saveDraft"
					/>
				</template>
				<template v-else-if="doc.docstatus === 0">
					<Button
						variant="outline"
						label="Save Draft"
						:loading="saving"
						:disabled="saving || publishing"
						data-testid="save-version-btn"
						@click="saveDraft"
					/>
					<Button
						variant="solid"
						label="Publish Version"
						:loading="publishing"
						:disabled="saving || publishing"
						data-testid="publish-version-btn"
						@click="publish"
					/>
				</template>
				<template v-else-if="doc.docstatus === 1">
					<Button
						variant="outline"
						label="Clone to New Draft"
						@click="cloneToNewDraft(false)"
					/>
					<Button
						variant="subtle"
						label="Cancel Version"
						:loading="cancelling"
						@click="cancelVersion"
					/>
				</template>
				<template v-else-if="doc.docstatus === 2">
					<Button
						variant="solid"
						label="Amend Version"
						@click="cloneToNewDraft(true)"
					/>
				</template>
			</div>
		</header>

		<div v-if="loadingDoc" class="py-12 text-center text-sm text-ink-gray-5">
			Loading series version…
		</div>

		<div v-else class="space-y-8">
			<Alert v-if="error" theme="red" :title="error" />

			<!-- Top Metadata Fields -->
			<section class="grid grid-cols-1 gap-5 md:grid-cols-3">
				<FormControl
					v-model="doc.series"
					type="select"
					label="Series *"
					placeholder="Select a Profile Series"
					:options="seriesOptions"
					:disabled="isEdit"
				/>
				<FormControl
					v-model="doc.version_note"
					type="text"
					label="Version Note"
					placeholder="e.g. Updated sash deductions and hardware rules"
					:disabled="isReadOnly"
				/>
				<FormControl
					v-if="!isEdit"
					v-model="cloneFromVersion"
					type="select"
					label="Copy Rules From Version (optional)"
					:options="cloneVersionOptions"
					@update:model-value="onCloneVersionChange"
				/>
				<FormControl
					v-else-if="doc.amended_from"
					:model-value="doc.amended_from"
					label="Amended From"
					disabled
				/>
			</section>

			<!-- Section Sub-Navigation Tabs -->
			<div class="border-b border-outline-gray-2">
				<div role="tablist" aria-label="Rule tables" class="flex flex-wrap gap-1">
					<button
						v-for="tab in ruleTabs"
						:key="tab.id"
						type="button"
						role="tab"
						:data-testid="`rule-tab-${tab.id}`"
						:aria-selected="activeRuleTab === tab.id"
						class="min-h-10 border-b-2 px-4 text-sm transition-colors"
						:class="
							activeRuleTab === tab.id
								? 'border-ink-gray-9 font-semibold text-ink-gray-9'
								: 'border-transparent font-medium text-ink-gray-6 hover:text-ink-gray-8'
						"
						@click="activeRuleTab = tab.id"
					>
						{{ tab.label }}
						<span
							class="ml-1.5 rounded-full px-2 py-0.5 text-xs"
							:class="activeRuleTab === tab.id ? 'bg-surface-gray-3 text-ink-gray-9' : 'bg-surface-gray-2 text-ink-gray-6'"
						>
							{{ tab.count }}
						</span>
					</button>
				</div>
			</div>

			<!-- 1. Deductions -->
			<section v-if="activeRuleTab === 'all' || activeRuleTab === 'deductions'" class="space-y-3">
				<div class="flex items-center justify-between gap-4">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">Deductions ({{ doc.deductions.length }})</h2>
						<p class="text-xs text-ink-gray-5">Key-value dimensional deductions in mm available to member formulas</p>
					</div>
					<Button
						v-if="!isReadOnly"
						variant="outline"
						size="sm"
						label="+ Add Deduction"
						@click="doc.deductions.push({ deduction_key: '', value: 0 })"
					/>
				</div>

				<div class="rounded-lg border border-outline-gray-2 bg-surface-white">
					<div
						class="grid grid-cols-[44px_1fr_200px_84px] items-center gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
					>
						<span>#</span>
						<span>Deduction Key *</span>
						<span>Value (mm) *</span>
						<span class="text-right">Action</span>
					</div>

					<div class="divide-y divide-outline-gray-1">
						<div
							v-for="(d, idx) in doc.deductions"
							:key="idx"
							class="grid grid-cols-[44px_1fr_200px_84px] items-center gap-4 px-4 py-2.5"
						>
							<span class="text-xs font-medium text-ink-gray-5">{{ idx + 1 }}</span>
							<FormControl
								v-model="d.deduction_key"
								type="text"
								placeholder="e.g. sash_w"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model.number="d.value"
								type="number"
								step="0.1"
								placeholder="0"
								:disabled="isReadOnly"
							/>
							<div class="text-right">
								<Button
									v-if="!isReadOnly"
									variant="ghost"
									size="sm"
									label="Remove"
									@click="doc.deductions.splice(idx, 1)"
								/>
							</div>
						</div>

						<div v-if="!doc.deductions.length" class="px-4 py-8 text-center text-sm text-ink-gray-5">
							No deductions added yet. Click <strong>+ Add Deduction</strong> to add one.
						</div>
					</div>
				</div>
			</section>

			<!-- 2. Member Rules -->
			<section v-if="activeRuleTab === 'all' || activeRuleTab === 'member_rules'" class="space-y-3">
				<div class="flex items-center justify-between gap-4">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">Member Rules ({{ doc.member_rules.length }})</h2>
						<p class="text-xs text-ink-gray-5">Profile cut length and mitre angle rules per member role</p>
					</div>
					<Button
						v-if="!isReadOnly"
						variant="outline"
						size="sm"
						label="+ Add Member Rule"
						@click="
							doc.member_rules.push({
								rule_id: '',
								role: 'frame',
								profile: seriesProfileCodes[0] || '',
								angle_start: 45,
								angle_end: 135,
								length_expr: 'W',
							})
						"
					/>
				</div>

				<div class="rounded-lg border border-outline-gray-2 bg-surface-white">
					<div
						class="grid grid-cols-[36px_140px_130px_1.3fr_96px_96px_1.3fr_76px] items-center gap-3 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
					>
						<span>#</span>
						<span>Rule Id *</span>
						<span>Role *</span>
						<span>Profile *</span>
						<span>Start °</span>
						<span>End °</span>
						<span>Length Formula *</span>
						<span class="text-right">Action</span>
					</div>

					<div class="divide-y divide-outline-gray-1">
						<div
							v-for="(m, idx) in doc.member_rules"
							:key="idx"
							class="grid grid-cols-[36px_140px_130px_1.3fr_96px_96px_1.3fr_76px] items-center gap-3 px-4 py-2.5"
						>
							<span class="text-xs font-medium text-ink-gray-5">{{ idx + 1 }}</span>
							<FormControl
								v-model="m.rule_id"
								type="text"
								placeholder="frame_top"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="m.role"
								type="select"
								:options="memberRoleOptions"
								:disabled="isReadOnly"
							/>
							<Combobox
								v-model="m.profile"
								placeholder="Select profile..."
								:options="profileComboboxOptions"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model.number="m.angle_start"
								type="number"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model.number="m.angle_end"
								type="number"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="m.length_expr"
								type="text"
								placeholder="e.g. W - sash_w"
								:disabled="isReadOnly"
							/>
							<div class="text-right">
								<Button
									v-if="!isReadOnly"
									variant="ghost"
									size="sm"
									label="Remove"
									@click="doc.member_rules.splice(idx, 1)"
								/>
							</div>
						</div>

						<div v-if="!doc.member_rules.length" class="px-4 py-8 text-center text-sm text-ink-gray-5">
							No member rules added yet. Click <strong>+ Add Member Rule</strong> to add one.
						</div>
					</div>
				</div>
			</section>

			<!-- 3. Hardware Rules (Structured 2-row cards — zero horizontal scroll, 100% frappe-ui controls) -->
			<section v-if="activeRuleTab === 'all' || activeRuleTab === 'hardware_rules'" class="space-y-3">
				<div class="flex items-center justify-between gap-4">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">Hardware Rules ({{ doc.hardware_rules.length }})</h2>
						<p class="text-xs text-ink-gray-5">BOM hardware and accessory emission formulas</p>
					</div>
					<Button
						v-if="!isReadOnly"
						variant="outline"
						size="sm"
						label="+ Add Hardware Rule"
						@click="
							doc.hardware_rules.push({
								rule_id: '',
								item: '',
								item_name: '',
								per: 'sash',
								when_expr: 'True',
								qty_expr: '1',
								length_expr: '',
								uom: 'Nos',
								bom_group: 'Fabrication Hardware',
							})
						"
					/>
				</div>

				<div class="divide-y divide-outline-gray-2 rounded-lg border border-outline-gray-2 bg-surface-white">
					<div
						v-for="(h, idx) in doc.hardware_rules"
						:key="idx"
						class="space-y-3 p-4"
					>
						<div class="flex items-center justify-between">
							<span class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5">
								Hardware Rule #{{ idx + 1 }}
							</span>
							<Button
								v-if="!isReadOnly"
								variant="ghost"
								size="sm"
								label="Remove rule"
								@click="doc.hardware_rules.splice(idx, 1)"
							/>
						</div>

						<!-- Row 1: Identity, Item, Scope & BOM Group -->
						<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
							<FormControl
								v-model="h.rule_id"
								type="text"
								label="Rule Id *"
								placeholder="e.g. hinge"
								:disabled="isReadOnly"
							/>
							<Combobox
								:model-value="h.item"
								label="Item *"
								placeholder="Search ERPNext Item..."
								:options="hardwareItemOptions"
								:disabled="isReadOnly"
								@update:model-value="(val) => onHardwareItemSelect(h, String(val || ''))"
							/>
							<FormControl
								v-model="h.item_name"
								type="text"
								label="Item Name *"
								placeholder="Fetched from Item"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="h.per"
								type="select"
								label="Per *"
								:options="hardwarePerSelectOptions"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="h.bom_group"
								type="text"
								label="BOM Group"
								placeholder="Fabrication Hardware"
								:disabled="isReadOnly"
							/>
						</div>

						<!-- Row 2: Formulas & UOM -->
						<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
							<FormControl
								v-model="h.when_expr"
								type="text"
								label="Condition (when)"
								placeholder="True"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="h.qty_expr"
								type="text"
								label="Qty Formula *"
								placeholder="e.g. 2"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="h.length_expr"
								type="text"
								label="Length Formula"
								placeholder="Optional"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="h.uom"
								type="text"
								label="UOM"
								placeholder="Nos"
								:disabled="isReadOnly"
							/>
						</div>
					</div>

					<div v-if="!doc.hardware_rules.length" class="px-4 py-8 text-center text-sm text-ink-gray-5">
						No hardware rules added yet. Click <strong>+ Add Hardware Rule</strong> to add one.
					</div>
				</div>
			</section>

			<!-- 4. Validation Rules -->
			<section v-if="activeRuleTab === 'all' || activeRuleTab === 'validation_rules'" class="space-y-3">
				<div class="flex items-center justify-between gap-4">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">Validation Rules ({{ doc.validation_rules.length }})</h2>
						<p class="text-xs text-ink-gray-5">Engineering limits and warnings checked on every window design</p>
					</div>
					<Button
						v-if="!isReadOnly"
						variant="outline"
						size="sm"
						label="+ Add Validation Rule"
						@click="
							doc.validation_rules.push({
								rule_id: '',
								when_expr: 'W > 2400',
								severity: 'warn',
								message: '',
								hint: '',
							})
						"
					/>
				</div>

				<div class="rounded-lg border border-outline-gray-2 bg-surface-white">
					<div
						class="grid grid-cols-[36px_140px_120px_1fr_1.2fr_1.2fr_76px] items-center gap-3 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
					>
						<span>#</span>
						<span>Rule Id *</span>
						<span>Severity *</span>
						<span>Condition *</span>
						<span>Message *</span>
						<span>Hint</span>
						<span class="text-right">Action</span>
					</div>

					<div class="divide-y divide-outline-gray-1">
						<div
							v-for="(v, idx) in doc.validation_rules"
							:key="idx"
							class="grid grid-cols-[36px_140px_120px_1fr_1.2fr_1.2fr_76px] items-center gap-3 px-4 py-2.5"
						>
							<span class="text-xs font-medium text-ink-gray-5">{{ idx + 1 }}</span>
							<FormControl
								v-model="v.rule_id"
								type="text"
								placeholder="max_sash_w"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="v.severity"
								type="select"
								:options="severityOptions"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="v.when_expr"
								type="text"
								placeholder="sash_w > 900"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="v.message"
								type="text"
								placeholder="Sash width exceeds limit"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model="v.hint"
								type="text"
								placeholder="Split into two sashes"
								:disabled="isReadOnly"
							/>
							<div class="text-right">
								<Button
									v-if="!isReadOnly"
									variant="ghost"
									size="sm"
									label="Remove"
									@click="doc.validation_rules.splice(idx, 1)"
								/>
							</div>
						</div>

						<div v-if="!doc.validation_rules.length" class="px-4 py-8 text-center text-sm text-ink-gray-5">
							No validation rules added yet. Click <strong>+ Add Validation Rule</strong> to add one.
						</div>
					</div>
				</div>
			</section>

			<!-- 5. Constants -->
			<section v-if="activeRuleTab === 'all' || activeRuleTab === 'constants'" class="space-y-3">
				<div class="flex items-center justify-between gap-4">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">Constants ({{ doc.constants.length }})</h2>
						<p class="text-xs text-ink-gray-5">Series-level constants exposed to all formulas</p>
					</div>
					<Button
						v-if="!isReadOnly"
						variant="outline"
						size="sm"
						label="+ Add Constant"
						@click="doc.constants.push({ constant_key: '', value: 0 })"
					/>
				</div>

				<div class="rounded-lg border border-outline-gray-2 bg-surface-white">
					<div
						class="grid grid-cols-[44px_1fr_200px_84px] items-center gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ink-gray-6"
					>
						<span>#</span>
						<span>Constant Key *</span>
						<span>Value *</span>
						<span class="text-right">Action</span>
					</div>

					<div class="divide-y divide-outline-gray-1">
						<div
							v-for="(c, idx) in doc.constants"
							:key="idx"
							class="grid grid-cols-[44px_1fr_200px_84px] items-center gap-4 px-4 py-2.5"
						>
							<span class="text-xs font-medium text-ink-gray-5">{{ idx + 1 }}</span>
							<FormControl
								v-model="c.constant_key"
								type="text"
								placeholder="e.g. glass_bite"
								:disabled="isReadOnly"
							/>
							<FormControl
								v-model.number="c.value"
								type="number"
								step="0.01"
								placeholder="0"
								:disabled="isReadOnly"
							/>
							<div class="text-right">
								<Button
									v-if="!isReadOnly"
									variant="ghost"
									size="sm"
									label="Remove"
									@click="doc.constants.splice(idx, 1)"
								/>
							</div>
						</div>

						<div v-if="!doc.constants.length" class="px-4 py-8 text-center text-sm text-ink-gray-5">
							No constants added yet. Click <strong>+ Add Constant</strong> to add one.
						</div>
					</div>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, Combobox, FormControl, toast, useList } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
	cancelSeriesVersion,
	createSeriesVersion,
	getSeriesVersionDoc,
	publishSeriesVersion,
	updateSeriesVersion,
	type FenestrationProfileRow,
	type ProfileSeriesRow,
	type SeriesHardwareRuleRow,
	type SeriesVersionDoc,
	type SeriesVersionRow,
} from '@/studio/api'

const props = defineProps<{ name?: string }>()
const route = useRoute()
const router = useRouter()

const isEdit = computed(() => Boolean(props.name))
const loadingDoc = ref(false)
const saving = ref(false)
const publishing = ref(false)
const cancelling = ref(false)
const error = ref('')
const cloneFromVersion = ref('')

type RuleTabId = 'all' | 'deductions' | 'member_rules' | 'hardware_rules' | 'validation_rules' | 'constants'
const activeRuleTab = ref<RuleTabId>('all')

const memberRoleOptions = [
	{ label: 'frame', value: 'frame' },
	{ label: 'sash', value: 'sash' },
	{ label: 'mullion', value: 'mullion' },
	{ label: 'transom', value: 'transom' },
]

const hardwarePerSelectOptions = [
	{ label: 'frame_member', value: 'frame_member' },
	{ label: 'sash_member', value: 'sash_member' },
	{ label: 'mullion', value: 'mullion' },
	{ label: 'transom_member', value: 'transom_member' },
	{ label: 'sash', value: 'sash' },
	{ label: 'glass', value: 'glass' },
	{ label: 'window', value: 'window' },
]

const severityOptions = [
	{ label: 'error', value: 'error' },
	{ label: 'warn', value: 'warn' },
]

const doc = reactive<SeriesVersionDoc>({
	name: '',
	series: String(route.query.series || ''),
	version_note: '',
	amended_from: null,
	docstatus: 0,
	deductions: [],
	constants: [],
	member_rules: [],
	hardware_rules: [],
	validation_rules: [],
})

const ruleTabs = computed(() => [
	{
		id: 'all' as const,
		label: 'All Rules',
		count:
			doc.deductions.length +
			doc.member_rules.length +
			doc.hardware_rules.length +
			doc.validation_rules.length +
			doc.constants.length,
	},
	{ id: 'deductions' as const, label: 'Deductions', count: doc.deductions.length },
	{ id: 'member_rules' as const, label: 'Member Rules', count: doc.member_rules.length },
	{ id: 'hardware_rules' as const, label: 'Hardware Rules', count: doc.hardware_rules.length },
	{ id: 'validation_rules' as const, label: 'Validation Rules', count: doc.validation_rules.length },
	{ id: 'constants' as const, label: 'Constants', count: doc.constants.length },
])

const isReadOnly = computed(() => isEdit.value && doc.docstatus !== 0)

const seriesResource = useList<ProfileSeriesRow>({
	doctype: 'Profile Series',
	fields: ['name', 'series_code', 'series_title', 'published_version'],
	orderBy: 'series_code asc',
	limit: 200,
})

const versionsResource = useList<SeriesVersionRow>({
	doctype: 'Series Version',
	fields: ['name', 'series', 'version_note', 'docstatus'],
	orderBy: 'modified desc',
	limit: 200,
})

const profilesResource = useList<FenestrationProfileRow>({
	doctype: 'Fenestration Profile',
	fields: ['name', 'profile_code', 'profile_name', 'series'],
	limit: 500,
})

const itemsResource = useList<{
	name: string
	item_name?: string
	stock_uom?: string
	fen_item_kind?: string
}>({
	doctype: 'Item',
	fields: ['name', 'item_name', 'stock_uom', 'fen_item_kind'],
	limit: 500,
})

const seriesOptions = computed(() =>
	(seriesResource.data ?? []).map((s) => ({
		label: `${s.series_code || s.name} — ${s.series_title}`,
		value: s.series_code || s.name,
	})),
)

const cloneVersionOptions = computed(() => [
	{ label: 'Start empty', value: '' },
	...(versionsResource.data ?? []).map((v) => ({
		label: `${v.name} (${v.series})`,
		value: v.name,
	})),
])

const seriesProfiles = computed(() =>
	(profilesResource.data ?? []).filter((p) => !doc.series || p.series === doc.series),
)

const seriesProfileCodes = computed(() =>
	seriesProfiles.value.map((p) => p.profile_code || p.name),
)

const profileComboboxOptions = computed(() =>
	seriesProfiles.value.map((p) => {
		const code = p.profile_code || p.name
		return {
			label: p.profile_name ? `${code} — ${p.profile_name}` : code,
			value: code,
		}
	}),
)

const itemList = computed(() => itemsResource.data ?? [])

const hardwareItemOptions = computed(() => {
	const all = itemList.value
	const sorted = [...all].sort((a, b) => {
		const aHw = a.fen_item_kind === 'Hardware' || a.fen_item_kind === 'Gasket' ? 0 : 1
		const bHw = b.fen_item_kind === 'Hardware' || b.fen_item_kind === 'Gasket' ? 0 : 1
		if (aHw !== bHw) return aHw - bHw
		return a.name.localeCompare(b.name)
	})
	return sorted.map((it) => ({
		label: it.item_name ? `${it.name} — ${it.item_name}` : it.name,
		value: it.name,
	}))
})

function onHardwareItemSelect(row: SeriesHardwareRuleRow, itemCode: string) {
	row.item = itemCode
	const found = itemList.value.find((it) => it.name === itemCode)
	if (found) {
		if (found.item_name) row.item_name = found.item_name
		if (found.stock_uom) row.uom = found.stock_uom
	}
}

async function onCloneVersionChange(verName: string) {
	if (!verName) return
	try {
		const source = await getSeriesVersionDoc(verName)
		copyRulesFrom(source)
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not copy rules from selected version'
	}
}

function copyRulesFrom(source: SeriesVersionDoc) {
	doc.deductions = (source.deductions || []).map((d) => ({
		deduction_key: d.deduction_key,
		value: d.value,
	}))
	doc.constants = (source.constants || []).map((c) => ({
		constant_key: c.constant_key,
		value: c.value,
	}))
	doc.member_rules = (source.member_rules || []).map((m) => ({
		rule_id: m.rule_id,
		role: m.role,
		profile: m.profile,
		angle_start: m.angle_start,
		angle_end: m.angle_end,
		length_expr: m.length_expr,
	}))
	doc.hardware_rules = (source.hardware_rules || []).map((h) => ({
		rule_id: h.rule_id,
		item: h.item,
		item_name: h.item_name,
		per: h.per,
		when_expr: h.when_expr,
		qty_expr: h.qty_expr,
		length_expr: h.length_expr,
		uom: h.uom,
		bom_group: h.bom_group,
	}))
	doc.validation_rules = (source.validation_rules || []).map((v) => ({
		rule_id: v.rule_id,
		when_expr: v.when_expr,
		severity: v.severity,
		message: v.message,
		hint: v.hint,
	}))
}

function applyLoaded(loaded: SeriesVersionDoc) {
	doc.name = loaded.name
	doc.series = loaded.series
	doc.version_note = loaded.version_note || ''
	doc.amended_from = loaded.amended_from || null
	doc.docstatus = loaded.docstatus ?? 0
	copyRulesFrom(loaded)
}

onMounted(async () => {
	if (!props.name) return
	loadingDoc.value = true
	try {
		const loaded = await getSeriesVersionDoc(props.name)
		applyLoaded(loaded)
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not load series version'
	} finally {
		loadingDoc.value = false
	}
})

function goBack() {
	router.push({
		path: '/series-studio',
		query: {
			tab: 'versions',
			...(doc.series ? { series: doc.series } : {}),
		},
	})
}

async function saveDraft() {
	if (!doc.series) return
	saving.value = true
	error.value = ''
	try {
		if (!isEdit.value) {
			const created = await createSeriesVersion(doc)
			applyLoaded(created)
			toast.success(`Created ${created.name}`)
			router.replace(`/series-studio/versions/${encodeURIComponent(created.name)}`)
		} else {
			const updated = await updateSeriesVersion(doc)
			applyLoaded(updated)
			toast.success('Draft saved')
		}
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Failed to save version'
	} finally {
		saving.value = false
	}
}

async function publish() {
	publishing.value = true
	error.value = ''
	try {
		const published = await publishSeriesVersion(doc)
		applyLoaded(published)
		toast.success(`Published ${published.name}`)
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Failed to publish version'
	} finally {
		publishing.value = false
	}
}

async function cancelVersion() {
	if (!doc.name) return
	cancelling.value = true
	error.value = ''
	try {
		const cancelled = await cancelSeriesVersion(doc.name)
		applyLoaded(cancelled)
		toast.success('Version cancelled')
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Failed to cancel version'
	} finally {
		cancelling.value = false
	}
}

async function cloneToNewDraft(isAmend: boolean) {
	saving.value = true
	error.value = ''
	try {
		const created = await createSeriesVersion({
			series: doc.series,
			version_note: isAmend ? `Amended from ${doc.name}` : `Cloned from ${doc.name}`,
			amended_from: isAmend ? doc.name : null,
			deductions: doc.deductions,
			constants: doc.constants,
			member_rules: doc.member_rules,
			hardware_rules: doc.hardware_rules,
			validation_rules: doc.validation_rules,
		})
		toast.success(`Created draft ${created.name}`)
		router.push(`/series-studio/versions/${encodeURIComponent(created.name)}`)
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Failed to clone version'
	} finally {
		saving.value = false
	}
}
</script>
