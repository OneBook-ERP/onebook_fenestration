<template>
	<section class="mb-4 space-y-4" data-testid="quote-panel">
		<!-- Quote Status Header & Actions -->
		<div class="space-y-1.5 rounded-xl border border-gray-200 bg-white p-4">
			<div class="flex flex-wrap items-center justify-between gap-2">
				<div class="text-[12px] font-medium text-gray-500">Quotation</div>
				<div class="flex flex-wrap items-center justify-end gap-2">
					<Button
						v-if="status?.quotation"
						variant="subtle"
						label="Edit in ERPNext"
						:href="`/app/quotation/${encodeURIComponent(status.quotation)}`"
						target="_blank"
					/>
					<Button label="Reprice" :loading="repricing" @click="reprice" />
					<Button
						:variant="(hasSubmitted || hasDraft) && !status?.is_stale ? 'outline' : 'solid'"
						:label="quoteButtonLabel"
						:loading="quoting"
						@click="quote"
					/>
					<FlowDocActions
						:actions="flow?.quotation?.actions"
						:suppliers="flow?.suppliers"
						size="md"
						:create-variant="status?.is_stale ? 'outline' : 'solid'"
						@done="onFlowActionDone"
					/>
				</div>
			</div>

			<div v-if="status?.quotation" class="flex flex-wrap items-center gap-2 text-sm" data-testid="quote-status">
				<span class="font-semibold text-gray-900">{{ status.quotation }}</span>
				<Badge :theme="statusTheme" :label="statusLabel" />
				<span class="font-semibold tabular-nums text-gray-900">{{ formatMoney(status.rounded_total ?? status.grand_total) }}</span>
			</div>
			<p v-else class="text-sm text-gray-500">No quotation created for this project yet.</p>
		</div>

		<!-- Quote Gate / Action Error -->
		<div
			v-if="quoteError"
			class="flex w-full items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50/80 p-3 text-sm text-red-900"
			data-testid="quote-error"
			role="alert"
		>
			<div class="flex flex-wrap items-center gap-2">
				<Badge theme="red" label="Quotation blocked" />
				<span>{{ quoteError }}</span>
			</div>
			<button
				type="button"
				class="text-xs font-medium text-red-700 hover:underline"
				@click="quoteError = ''"
			>
				Dismiss
			</button>
		</div>

		<!-- Stale Quote Alert -->
		<div
			v-if="status?.is_stale"
			class="flex w-full flex-wrap items-center gap-2 rounded-xl border border-amber-200 bg-amber-50/70 p-3 text-sm"
			data-testid="quote-stale"
		>
			<Badge theme="orange" label="Designs changed since quotation" />
			<span>{{ staleDetail }}</span>
			<span class="text-ink-gray-5">{{ staleHint }}</span>
		</div>

		<!-- Commercial Settings & Printable Documents -->
		<div class="grid gap-4 lg:grid-cols-[1.1fr_1.4fr]">
			<div class="rounded-xl border border-gray-200 bg-white p-4">
				<h3 class="mb-3 text-[13px] font-semibold text-gray-900">Commercial Settings</h3>
				<div class="grid gap-3 sm:grid-cols-2">
					<Combobox
						:model-value="info?.customer || ''"
						label="Customer"
						placeholder="Select a customer"
						:options="customerOptions"
						@update:model-value="saveCustomer"
					/>
					<FormControl
						v-model="transport"
						type="number"
						label="Transport charges"
						@blur="queueTransportSave"
						@keydown.enter="queueTransportSave"
					/>
				</div>
			</div>

			<div class="rounded-xl border border-gray-200 bg-white p-4">
				<h3 class="mb-3 text-[13px] font-semibold text-gray-900">Quote &amp; Engineering PDFs</h3>
				<div class="flex flex-wrap gap-2">
					<Button label="Quotation" :href="quotationUrl" :disabled="!quotationUrl" />
					<Button label="Elevation Report" :href="elevationUrl" />
					<Button label="Estimate Confirmation" :href="estimateUrl" />
					<Button label="Assembly Summary" :href="assemblySummaryUrl" />
					<Button label="Assembly Detail" :href="assemblyDetailUrl" />
				</div>
			</div>
		</div>

		<!-- Full Read-Only Quotation Details -->
		<QuotationDetailsCard v-if="details" :details="details" />
		<div v-else-if="detailsLoading" class="rounded-xl border border-gray-200 bg-white px-4 py-6 text-center text-sm text-gray-500">
			Loading quotation details…
		</div>
	</section>
</template>

<script setup lang="ts">
import { Badge, Button, Combobox, FormControl, toast, useList } from 'frappe-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
	getQuotationDetails,
	makeQuotation,
	quoteStatus,
	repriceProject,
	setProjectField,
	type ProjectFlowState,
	type QuotationDetail,
	type QuoteStatus,
} from '@/api'
import FlowDocActions from '@/components/workspace/FlowDocActions.vue'
import QuotationDetailsCard from '@/components/workspace/QuotationDetailsCard.vue'
import { formatMoney } from '@/money'
import { printPdfUrl } from '@/print'

interface QuoteInfo {
	customer?: string | null
	transport_charges?: number | null
	quotation?: string | null
}

const props = defineProps<{ project: string; info?: QuoteInfo; flow?: ProjectFlowState | null }>()
const emit = defineEmits<{ changed: []; repriced: [] }>()

const customers = useList<{ name: string; customer_name: string }>({
	doctype: 'Customer',
	fields: ['name', 'customer_name'],
	limit: 500,
})
const customerOptions = computed(() =>
	(customers.data ?? []).map((c) => ({ label: c.customer_name || c.name, value: c.name })),
)

const status = ref<QuoteStatus | null>(null)
const details = ref<QuotationDetail | null>(null)
const detailsLoading = ref(false)
const repricing = ref(false)
const quoting = ref(false)
const quoteError = ref('')
const transport = ref<string | number>(props.info?.transport_charges ?? 0)
let savedTransport = Number(props.info?.transport_charges ?? 0)
let timer: ReturnType<typeof setTimeout> | undefined

const hasDraft = computed(() => !!status.value?.quotation && status.value.docstatus === 0)
const hasSubmitted = computed(() => !!status.value?.quotation && status.value.docstatus === 1)
const quoteButtonLabel = computed(() =>
	hasDraft.value ? 'Update quotation' : hasSubmitted.value ? 'New quotation revision' : 'Create quotation',
)
const staleHint = computed(() =>
	hasSubmitted.value
		? 'Current quotation is Submitted — click New quotation revision to create a refreshed Draft (then submit it and recreate any Draft Sales Order from the new quotation).'
		: `Use ${hasDraft.value ? 'Update quotation' : 'Create quotation'} to refresh.`,
)
const statusLabel = computed(() => ['Draft', 'Submitted', 'Cancelled'][status.value?.docstatus ?? 0] ?? status.value?.status ?? 'Unknown')
const statusTheme = computed(() => (['orange', 'green', 'red'] as const)[status.value?.docstatus ?? 0] ?? 'gray')
const staleDetail = computed(() => {
	const stale = status.value?.stale
	if (!stale) return ''
	const parts = [
		stale.changed.length ? `Changed: ${stale.changed.join(', ')}` : '',
		stale.added.length ? `Added: ${stale.added.join(', ')}` : '',
		stale.removed.length ? `Removed: ${stale.removed.join(', ')}` : '',
		stale.transport_changed ? 'Transport charges changed' : '',
	]
	return parts.filter(Boolean).join(' · ')
})
const quotationUrl = computed(() =>
	status.value?.quotation ? printPdfUrl('Quotation', status.value.quotation, 'Fenestration Quotation') : undefined,
)
const elevationUrl = computed(() => printPdfUrl('Fenestration Project', props.project, 'Fenestration Elevation'))
const estimateUrl = computed(() => printPdfUrl('Fenestration Project', props.project, 'Fenestration Estimate Confirmation'))
const assemblySummaryUrl = computed(() => printPdfUrl('Fenestration Project', props.project, 'Fenestration Assembly Summary'))
const assemblyDetailUrl = computed(() => printPdfUrl('Fenestration Project', props.project, 'Fenestration Assembly Detail'))

async function loadDetails(quotationName?: string | null) {
	if (!quotationName) {
		details.value = null
		return
	}
	detailsLoading.value = true
	try {
		if (typeof getQuotationDetails === 'function') {
			details.value = await getQuotationDetails(quotationName)
		}
	} catch {
		details.value = null
	} finally {
		detailsLoading.value = false
	}
}

async function refreshStatus() {
	try {
		status.value = await quoteStatus(props.project)
		await loadDetails(status.value?.quotation)
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Could not load quotation status')
	}
}
async function onFlowActionDone() {
	await refreshStatus()
	emit('changed')
}
watch(
	() => props.flow?.quotation?.docstatus,
	() => {
		if (status.value?.quotation) void refreshStatus()
	},
)
watch(
	() => props.info?.quotation,
	(name) => {
		if (!name || status.value?.quotation !== name) refreshStatus()
	},
	{ immediate: true },
)
watch(() => props.info?.transport_charges, (v) => {
	transport.value = v ?? 0
	savedTransport = Number(v ?? 0)
})

async function saveField(fieldname: string, value: string | number): Promise<boolean> {
	try {
		await setProjectField(props.project, fieldname, value)
		emit('changed')
		return true
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Save failed')
		return false
	}
}

function saveCustomer(value: string | number | null) {
	saveField('customer', value ? String(value) : '')
}

function queueTransportSave() {
	clearTimeout(timer)
	timer = setTimeout(async () => {
		const value = Number(transport.value) || 0
		if (value === savedTransport) return
		if (await saveField('transport_charges', value)) savedTransport = value
	}, 300)
}
onBeforeUnmount(() => clearTimeout(timer))

async function reprice() {
	repricing.value = true
	try {
		const res = await repriceProject(props.project)
		const failed = res.failed?.length ? `, ${res.failed.length} failed` : ''
		toast.success(`Repriced ${res.repriced} designs${failed}`)
		emit('repriced')
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Reprice failed')
	} finally {
		repricing.value = false
	}
}

async function quote() {
	quoting.value = true
	quoteError.value = ''
	const verb = hasDraft.value ? 'updated' : 'created'
	let res
	try {
		res = await makeQuotation(props.project)
	} catch (e) {
		const msg = e instanceof Error ? e.message : 'Quotation failed'
		quoteError.value = msg
		toast.error(msg)
		quoting.value = false
		return
	}
	if (!res.ok) {
		quoteError.value = res.message
		toast.error(res.message)
		quoting.value = false
		return
	}
	toast.success(`Quotation ${res.quotation} ${verb}`)
	await refreshStatus()
	emit('changed')
	quoting.value = false
}
</script>
