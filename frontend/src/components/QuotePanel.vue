<template>
	<section class="mb-4 flex flex-wrap items-end gap-4 rounded border p-3" data-testid="quote-panel">
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
		<Button label="Reprice" :loading="repricing" @click="reprice" />
		<Button variant="solid" :label="hasDraft ? 'Update quotation' : 'Create quotation'" :loading="quoting" @click="quote" />
		<div v-if="status?.quotation" class="flex items-center gap-2 text-sm" data-testid="quote-status">
			<span>{{ status.quotation }}</span>
			<Badge :theme="statusTheme" :label="statusLabel" />
			<span class="font-medium">{{ formatMoney(status.grand_total) }}</span>
		</div>
		<div class="ml-auto flex flex-wrap gap-2">
			<Button label="Quotation" :href="quotationUrl" :disabled="!quotationUrl" />
			<Button label="Elevation Report" :href="elevationUrl" />
			<Button label="Estimate Confirmation" :href="estimateUrl" />
		</div>
	</section>
</template>

<script setup lang="ts">
import { Badge, Button, Combobox, FormControl, toast, useList } from 'frappe-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
	makeQuotation, quoteStatus, repriceProject, setProjectField,
	type QuoteStatus,
} from '@/api'
import { formatMoney } from '@/money'
import { printPdfUrl } from '@/print'

interface QuoteInfo {
	customer?: string | null
	transport_charges?: number | null
	quotation?: string | null
}

const props = defineProps<{ project: string; info?: QuoteInfo }>()
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
const repricing = ref(false)
const quoting = ref(false)
const transport = ref<string | number>(props.info?.transport_charges ?? 0)
let savedTransport = Number(props.info?.transport_charges ?? 0)
let timer: ReturnType<typeof setTimeout> | undefined

const hasDraft = computed(() => !!status.value?.quotation && status.value.docstatus === 0)
const statusLabel = computed(() => ['Draft', 'Submitted', 'Cancelled'][status.value?.docstatus ?? 0] ?? status.value?.status ?? 'Unknown')
const statusTheme = computed(() => (['orange', 'green', 'red'] as const)[status.value?.docstatus ?? 0] ?? 'gray')
const quotationUrl = computed(() =>
	status.value?.quotation ? printPdfUrl('Quotation', status.value.quotation, 'Fenestration Quotation') : undefined,
)
const elevationUrl = computed(() => printPdfUrl('Fenestration Project', props.project, 'Fenestration Elevation'))
const estimateUrl = computed(() => printPdfUrl('Fenestration Project', props.project, 'Fenestration Estimate Confirmation'))

async function refreshStatus() {
	try {
		status.value = await quoteStatus(props.project)
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Could not load quotation status')
	}
}
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
	const verb = hasDraft.value ? 'updated' : 'created'
	let res
	try {
		res = await makeQuotation(props.project)
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Quotation failed')
		quoting.value = false
		return
	}
	if (!res.ok) {
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
