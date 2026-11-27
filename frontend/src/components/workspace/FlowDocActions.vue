<template>
	<div v-if="submitActions.length || createActions.length" class="inline-flex flex-wrap items-center gap-1.5">
		<Button
			v-for="act in submitActions"
			:key="act.id"
			:size="buttonSize"
			variant="solid"
			:data-testid="act.id"
			:loading="busyId === act.id"
			:disabled="Boolean(busyId && busyId !== act.id)"
			@click="runSubmit(act)"
		>
			{{ act.label }}
		</Button>

		<div v-if="createActions.length" ref="menuRef" class="relative">
			<Button
				:size="buttonSize"
				:variant="createButtonVariant"
				data-testid="flow-create-dropdown"
				:loading="busyId.startsWith('create-') || busyId === '__creating__'"
				:disabled="Boolean(busyId)"
				@click="toggleMenu"
			>
				{{ createLabel || 'Create' }} ▾
			</Button>

			<div
				v-if="menuOpen"
				role="menu"
				class="absolute right-0 z-30 mt-1.5 w-64 rounded-lg border border-gray-200 bg-white shadow-lg"
			>
				<div v-if="!promptAction" class="py-1">
					<button
						v-for="act in createActions"
						:key="act.id"
						type="button"
						role="menuitem"
						:data-testid="act.id"
						class="flex w-full items-center justify-between px-3 py-2 text-left text-xs text-gray-800 hover:bg-gray-50"
						@click="pickCreateAction(act)"
					>
						<span class="font-medium">{{ shortCreateLabel(act.label) }}</span>
						<span class="ml-2 text-[11px] text-gray-400">Create</span>
					</button>
				</div>

				<div v-else data-testid="flow-create-prompt" class="space-y-2.5 p-3 text-xs">
					<div class="flex items-center justify-between gap-2 border-b border-gray-100 pb-2">
						<button
							type="button"
							class="text-[11px] font-medium text-gray-500 hover:text-gray-800"
							@click="promptAction = null"
						>
							← Back
						</button>
						<span class="truncate font-semibold text-gray-800">{{ promptAction.label }}</span>
					</div>

					<label v-if="promptAction.requires_supplier" class="block space-y-1">
						<span class="block text-[11px] font-medium text-gray-600">Supplier</span>
						<select
							v-model="chosenSupplier"
							data-testid="flow-supplier-select"
							class="h-7 w-full rounded border border-gray-300 bg-white px-2 text-xs"
						>
							<option value="">Select supplier...</option>
							<option v-for="s in suppliers || []" :key="s.name" :value="s.name">
								{{ s.supplier_name || s.name }}
							</option>
						</select>
					</label>

					<label v-if="promptAction.supports_po_no" class="block space-y-1">
						<span class="block text-[11px] font-medium text-gray-600">Customer / Distributor PO #</span>
						<input
							v-model="poNo"
							type="text"
							placeholder="Optional PO number"
							data-testid="flow-po-no-input"
							class="h-7 w-full rounded border border-gray-300 bg-white px-2 text-xs"
						/>
					</label>

					<label class="flex items-center gap-1.5 text-gray-600">
						<input
							v-model="submitImmediately"
							data-testid="flow-submit-checkbox"
							type="checkbox"
							class="rounded border-gray-300"
						/>
						<span>Save &amp; Submit</span>
					</label>

					<div class="flex items-center justify-end gap-1.5 pt-1">
						<Button size="sm" variant="subtle" :disabled="Boolean(busyId)" @click="closeMenu">Cancel</Button>
						<Button
							size="sm"
							variant="solid"
							data-testid="flow-prompt-confirm"
							:loading="busyId === promptAction.id"
							:disabled="Boolean(promptAction.requires_supplier && !chosenSupplier)"
							@click="confirmPrompt"
						>
							Create
						</Button>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Button, toast } from 'frappe-ui'
import { createFlowDoc, submitFlowDoc, type FlowAction, type FlowMutationResult } from '@/api'

const props = defineProps<{
	actions?: FlowAction[]
	suppliers?: Array<{ name: string; supplier_name?: string }>
	size?: 'sm' | 'md'
	createLabel?: string
	createVariant?: 'solid' | 'outline' | 'subtle'
}>()

const emit = defineEmits<{
	done: [result: Extract<FlowMutationResult, { ok: true }>]
}>()

const busyId = ref('')
const menuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const promptAction = ref<FlowAction | null>(null)
const chosenSupplier = ref('')
const poNo = ref('')
const submitImmediately = ref(false)

const buttonSize = computed(() => props.size ?? 'sm')
const submitActions = computed(() => (props.actions ?? []).filter((a) => a.kind === 'submit'))
const createActions = computed(() => (props.actions ?? []).filter((a) => a.kind === 'create'))
const createButtonVariant = computed(() => props.createVariant ?? (submitActions.value.length ? 'outline' : 'solid'))

function shortCreateLabel(label: string): string {
	return label.replace(/^Create\s+/i, '').trim() || label
}

function toggleMenu() {
	if (menuOpen.value) {
		closeMenu()
	} else {
		menuOpen.value = true
	}
}

function closeMenu() {
	menuOpen.value = false
	promptAction.value = null
}

function pickCreateAction(act: FlowAction) {
	if (act.requires_supplier || act.supports_po_no) {
		promptAction.value = act
		if (act.requires_supplier) {
			if (!chosenSupplier.value && props.suppliers?.length === 1) {
				chosenSupplier.value = props.suppliers[0].name
			}
		} else {
			chosenSupplier.value = ''
		}
		submitImmediately.value = false
		return
	}
	closeMenu()
	void runCreate(act)
}

function confirmPrompt() {
	if (!promptAction.value) return
	void runCreate(promptAction.value, {
		supplier: chosenSupplier.value || undefined,
		poNo: poNo.value.trim() || undefined,
		submit: submitImmediately.value,
	})
}

async function runSubmit(act: FlowAction) {
	if (!act.doctype || !act.name) return
	busyId.value = act.id
	try {
		const res = await submitFlowDoc(act.doctype, act.name)
		if (!res.ok) {
			toast.error(res.message)
			return
		}
		toast.success(`${res.doctype} ${res.name} submitted`)
		emit('done', res)
	} catch (err) {
		toast.error(err instanceof Error ? err.message : 'Submit failed')
	} finally {
		busyId.value = ''
	}
}

async function runCreate(
	act: FlowAction,
	opts: { supplier?: string; poNo?: string; submit?: boolean } = {},
) {
	if (!act.source_doctype || !act.source_name || !act.target_doctype) return
	busyId.value = act.id
	try {
		const res = await createFlowDoc(act.source_doctype, act.source_name, act.target_doctype, opts)
		if (!res.ok) {
			toast.error(res.message)
			return
		}
		const verb = res.docstatus === 1 ? 'created & submitted' : 'created'
		toast.success(`${res.doctype} ${res.name} ${verb}`)
		poNo.value = ''
		closeMenu()
		emit('done', res)
	} catch (err) {
		toast.error(err instanceof Error ? err.message : 'Create failed')
	} finally {
		busyId.value = ''
	}
}

function handleOutsideClick(event: MouseEvent) {
	if (menuOpen.value && menuRef.value && !menuRef.value.contains(event.target as Node)) {
		closeMenu()
	}
}

onMounted(() => document.addEventListener('click', handleOutsideClick))
onBeforeUnmount(() => document.removeEventListener('click', handleOutsideClick))
</script>
