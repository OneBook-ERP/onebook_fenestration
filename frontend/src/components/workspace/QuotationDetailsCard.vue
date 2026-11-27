<template>
	<div data-testid="quotation-details-card" class="overflow-hidden rounded-xl border border-gray-200 bg-white">
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 bg-gray-50/70 px-4 py-3">
			<div>
				<div class="flex items-center gap-2">
					<h3 class="text-[13.5px] font-semibold text-gray-900">Quotation Details</h3>
					<span class="font-mono text-[12px] text-gray-500">{{ details.name }}</span>
					<Badge :theme="docTheme" :label="docLabel" />
				</div>
				<p class="mt-0.5 text-[12px] text-gray-500">
					Read-only preview from ERPNext · To edit or submit, open in ERPNext Desk.
				</p>
			</div>
			<div class="flex items-center gap-2">
				<slot name="actions" />
				<Button
					size="sm"
					variant="subtle"
					label="Edit in ERPNext"
					:href="`/app/quotation/${encodeURIComponent(details.name)}`"
					target="_blank"
				/>
			</div>
		</div>

		<!-- Party, Dates & Totals Summary -->
		<div class="grid gap-4 border-b border-gray-100 p-4 sm:grid-cols-3">
			<div>
				<div class="text-[11px] font-medium uppercase tracking-wide text-gray-400">Customer &amp; Billing</div>
				<div class="mt-1 text-[13px] font-semibold text-gray-900">{{ details.customer_name || '—' }}</div>
				<div v-if="cleanAddress" class="mt-0.5 whitespace-pre-line text-[12px] text-gray-500">
					{{ cleanAddress }}
				</div>
				<div v-if="details.contact_display || details.contact_mobile" class="mt-1 text-[11.5px] text-gray-500">
					{{ [details.contact_display, details.contact_mobile].filter(Boolean).join(' · ') }}
				</div>
			</div>

			<div>
				<div class="text-[11px] font-medium uppercase tracking-wide text-gray-400">Schedule</div>
				<dl class="mt-1 space-y-1 text-[12.5px]">
					<div class="flex justify-between gap-2 sm:justify-start">
						<dt class="text-gray-500">Date:</dt>
						<dd class="font-medium text-gray-800">{{ details.transaction_date || '—' }}</dd>
					</div>
					<div class="flex justify-between gap-2 sm:justify-start">
						<dt class="text-gray-500">Valid Till:</dt>
						<dd class="font-medium text-gray-800">{{ details.valid_till || '—' }}</dd>
					</div>
					<div v-if="details.tc_name" class="flex justify-between gap-2 sm:justify-start">
						<dt class="text-gray-500">Terms:</dt>
						<dd class="font-medium text-gray-800">{{ details.tc_name }}</dd>
					</div>
				</dl>
			</div>

			<div>
				<div class="text-[11px] font-medium uppercase tracking-wide text-gray-400">Amounts</div>
				<dl class="mt-1 space-y-1 text-[12.5px]">
					<div class="flex justify-between gap-2">
						<dt class="text-gray-500">Net Total</dt>
						<dd class="font-medium tabular-nums text-gray-800">{{ formatMoney(details.net_total) }}</dd>
					</div>
					<div class="flex justify-between gap-2">
						<dt class="text-gray-500">Taxes &amp; Charges</dt>
						<dd class="font-medium tabular-nums text-gray-800">{{ formatMoney(details.total_taxes_and_charges) }}</dd>
					</div>
					<div class="flex justify-between gap-2 border-t border-gray-100 pt-1">
						<dt class="font-semibold text-gray-900">Grand Total</dt>
						<dd class="font-semibold tabular-nums text-gray-900">{{ formatMoney(details.rounded_total) }}</dd>
					</div>
				</dl>
			</div>
		</div>

		<!-- Line Items Table -->
		<div class="overflow-x-auto">
			<table class="w-full border-collapse text-left text-[12.5px]">
				<thead>
					<tr class="border-b border-gray-200 bg-gray-50/50 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
						<th class="px-4 py-2 w-10">#</th>
						<th class="px-3 py-2">Item</th>
						<th class="px-3 py-2">Specification</th>
						<th class="px-3 py-2 text-right">Qty</th>
						<th class="px-3 py-2">UOM</th>
						<th class="px-3 py-2 text-right">Rate</th>
						<th class="px-4 py-2 text-right">Amount</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-100">
					<tr v-for="item in details.items" :key="item.idx" class="hover:bg-gray-50/60">
						<td class="px-4 py-2.5 text-gray-400 tabular-nums">{{ item.idx }}</td>
						<td class="px-3 py-2.5">
							<div class="font-medium text-gray-900">{{ item.item_name }}</div>
							<div class="text-[11px] text-gray-400">{{ item.item_code }}</div>
						</td>
						<td class="px-3 py-2.5 text-gray-600 max-w-md">
							<div class="line-clamp-2 whitespace-pre-line">{{ plainText(item.description) || '—' }}</div>
						</td>
						<td class="px-3 py-2.5 text-right font-medium tabular-nums text-gray-800">{{ item.qty }}</td>
						<td class="px-3 py-2.5 text-gray-500">{{ item.uom }}</td>
						<td class="px-3 py-2.5 text-right tabular-nums text-gray-700">{{ formatMoney(item.rate) }}</td>
						<td class="px-4 py-2.5 text-right font-semibold tabular-nums text-gray-900">{{ formatMoney(item.amount) }}</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Taxes & Terms Footer -->
		<div v-if="details.taxes.length || cleanTerms" class="grid gap-4 border-t border-gray-200 bg-gray-50/40 p-4 sm:grid-cols-2">
			<div v-if="details.taxes.length">
				<div class="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-500">Tax Breakdown</div>
				<ul class="space-y-1 text-[12px]">
					<li v-for="t in details.taxes" :key="t.idx" class="flex justify-between gap-2 text-gray-700">
						<span class="truncate">{{ plainText(t.description) }} ({{ t.rate }}%)</span>
						<span class="shrink-0 font-medium tabular-nums">{{ formatMoney(t.tax_amount) }}</span>
					</li>
				</ul>
			</div>
			<div v-if="cleanTerms">
				<div class="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-500">Terms &amp; Conditions</div>
				<p class="line-clamp-4 whitespace-pre-line text-[12px] text-gray-600">{{ cleanTerms }}</p>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button } from 'frappe-ui'
import { computed } from 'vue'
import type { QuotationDetail } from '@/api'
import { formatMoney } from '@/money'

const props = defineProps<{ details: QuotationDetail }>()

const docLabel = computed(
	() => ['Draft', 'Submitted', 'Cancelled'][props.details.docstatus] ?? props.details.status ?? 'Draft',
)
const docTheme = computed(
	() => (['amber', 'green', 'red'] as const)[props.details.docstatus] ?? 'gray',
)

function plainText(raw: string): string {
	if (!raw) return ''
	return raw
		.replace(/<br\s*\/?>/gi, '\n')
		.replace(/<\/(p|div|li|tr)>/gi, '\n')
		.replace(/<[^>]+>/g, '')
		.replace(/&nbsp;/gi, ' ')
		.replace(/&amp;/gi, '&')
		.replace(/\n{3,}/g, '\n\n')
		.trim()
}

const cleanAddress = computed(() => plainText(props.details.address_display))
const cleanTerms = computed(() => plainText(props.details.terms))
</script>

