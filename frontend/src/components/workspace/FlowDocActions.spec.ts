import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FlowAction } from '@/api'

const { submitFlowDoc, createFlowDoc, toastSuccess, toastError } = vi.hoisted(() => ({
	submitFlowDoc: vi.fn(),
	createFlowDoc: vi.fn(),
	toastSuccess: vi.fn(),
	toastError: vi.fn(),
}))

vi.mock('@/api', () => ({
	submitFlowDoc,
	createFlowDoc,
}))

vi.mock('frappe-ui', async () => {
	const { defineComponent, h } = await import('vue')
	const Button = defineComponent({
		props: { label: String, loading: Boolean, disabled: Boolean, variant: String, size: String },
		emits: ['click'],
		setup(props, { emit, slots }) {
			return () =>
				h(
					'button',
					{ type: 'button', disabled: props.disabled, onClick: (e: MouseEvent) => emit('click', e) },
					slots.default?.() ?? props.label,
				)
		},
	})
	return { Button, toast: { success: toastSuccess, error: toastError } }
})

import FlowDocActions from './FlowDocActions.vue'

beforeEach(() => {
	vi.clearAllMocks()
	submitFlowDoc.mockResolvedValue({ ok: true, doctype: 'Quotation', name: 'QTN-1', status: 'Open', docstatus: 1 })
	createFlowDoc.mockResolvedValue({ ok: true, doctype: 'Sales Order', name: 'SO-1', status: 'Draft', docstatus: 0 })
})

describe('FlowDocActions', () => {
	it('submits a draft action directly and emits done', async () => {
		const actions: FlowAction[] = [
			{ id: 'submit-q', kind: 'submit', label: 'Submit Quotation', doctype: 'Quotation', name: 'QTN-1', primary: true },
		]
		const w = mount(FlowDocActions, { props: { actions } })
		await w.get('[data-testid="submit-q"]').trigger('click')
		await flushPromises()
		expect(submitFlowDoc).toHaveBeenCalledWith('Quotation', 'QTN-1')
		expect(w.emitted('done')).toHaveLength(1)
	})

	it('organizes create actions in the Create dropdown and handles Distributor PO# + Save & Submit', async () => {
		const actions: FlowAction[] = [
			{
				id: 'create-so',
				kind: 'create',
				label: 'Create Sales Order',
				source_doctype: 'Quotation',
				source_name: 'QTN-1',
				target_doctype: 'Sales Order',
				supports_po_no: true,
			},
			{
				id: 'create-po',
				kind: 'create',
				label: 'Create Purchase Order',
				source_doctype: 'Quotation',
				source_name: 'QTN-1',
				target_doctype: 'Purchase Order',
				requires_supplier: true,
			},
		]
		const w = mount(FlowDocActions, {
			props: {
				actions,
				suppliers: [{ name: 'SUP-1', supplier_name: 'AluSupplier' }],
			},
		})
		await w.get('[data-testid="flow-create-dropdown"]').trigger('click')
		const items = w.findAll('[role="menuitem"]')
		expect(items.map((el) => el.text())).toEqual(['Sales OrderCreate', 'Purchase OrderCreate'])

		await w.get('[data-testid="create-so"]').trigger('click')
		await w.get('[data-testid="flow-po-no-input"]').setValue('DIST-PO-12')
		await w.get('[data-testid="flow-submit-checkbox"]').setValue(true)
		await w.get('[data-testid="flow-prompt-confirm"]').trigger('click')
		await flushPromises()

		expect(createFlowDoc).toHaveBeenCalledWith('Quotation', 'QTN-1', 'Sales Order', {
			supplier: undefined,
			poNo: 'DIST-PO-12',
			submit: true,
		})
	})

	it('requires supplier selection for Purchase Order creation and toasts backend rejections', async () => {
		createFlowDoc.mockResolvedValue({ ok: false, message: 'No items left to order' })
		const actions: FlowAction[] = [
			{
				id: 'create-po',
				kind: 'create',
				label: 'Create Purchase Order',
				source_doctype: 'Material Request',
				source_name: 'MR-1',
				target_doctype: 'Purchase Order',
				requires_supplier: true,
			},
		]
		const w = mount(FlowDocActions, {
			props: {
				actions,
				suppliers: [
					{ name: 'SUP-1', supplier_name: 'First Supplier' },
					{ name: 'SUP-2', supplier_name: 'Second Supplier' },
				],
			},
		})
		await w.get('[data-testid="flow-create-dropdown"]').trigger('click')
		await w.get('[data-testid="create-po"]').trigger('click')
		await w.get('[data-testid="flow-supplier-select"]').setValue('SUP-2')
		await w.get('[data-testid="flow-prompt-confirm"]').trigger('click')
		await flushPromises()

		expect(createFlowDoc).toHaveBeenCalledWith('Material Request', 'MR-1', 'Purchase Order', {
			supplier: 'SUP-2',
			poNo: undefined,
			submit: false,
		})
		expect(toastError).toHaveBeenCalledWith('No items left to order')
	})
})

