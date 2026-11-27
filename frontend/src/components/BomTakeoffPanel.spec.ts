import { flushPromises, mount } from '@vue/test-utils'
import { toast } from 'frappe-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { makeProjectMaterialRequest, makeProjectPurchaseOrder, materialTree, type MaterialTree } from '@/api'
import BomTakeoffPanel from './BomTakeoffPanel.vue'

vi.mock('@/api', async (orig) => ({
	...(await orig<object>()),
	materialTree: vi.fn(),
	makeProjectMaterialRequest: vi.fn(),
	makeProjectPurchaseOrder: vi.fn(),
}))

vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	toast: { success: vi.fn(), error: vi.fn() },
	useList: (await import('@/test-utils')).fakeUseList({
		Supplier: [{ name: 'SUP-ALU', supplier_name: 'Hilux Extrusions Ltd' }],
	}),
}))

const sampleTree: MaterialTree = {
	project: { name: 'FP-2026-00002', project_title: 'Go builder salem', company: 'OneBook Fenestration' },
	warehouses: [
		{ name: 'Main Warehouse - OF', warehouse_name: 'Main Warehouse' },
		{ name: 'Hilux Warehouse - OF', warehouse_name: 'Hilux Warehouse' },
	],
	default_warehouse: 'Main Warehouse - OF',
	windows: [
		{
			name: 'FP-2026-00002-W01',
			design_ref: 'W01',
			design_name: 'Fixed',
			qty: 2,
			series_version: 'CS400-v1',
			finish: 'GREY',
			floor: '1',
			location: 'Hall',
			width_mm: 1200,
			height_mm: 1200,
			design_svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100"/></svg>',
			profiles: [
				{
					profile_code: 'E104156',
					item_code: 'E104156',
					item_name: '40mm Casement Frame',
					uom: 'Kg',
					kg: 6.24,
					total_mm: 9600,
					pieces: 8,
					default_supplier: 'SUP-ALU',
					cuts: [{ length_mm: 1200, pieces: 8, angles: '45/45', role: 'frame', kg: 6.24 }],
				},
			],
			glass: [
				{
					glass_code: '6CTG',
					item_code: '6CTG',
					item_name: '6 mm clear toughened',
					uom: 'Square Meter',
					area_m2: 2.599,
					pieces: 2,
					panes: [{ width_mm: 1140, height_mm: 1140, pieces: 2, area_m2: 2.599, material: 'glass' }],
				},
			],
			hardware: [
				{
					item_code: 'GASKET-1',
					item_name: 'FRAME GASKET CASEMENT',
					category: 'Gasket',
					group: 'Gasket',
					qty: 9.6,
					uom: 'Meter',
					length_mm: 9600,
				},
			],
			problems: [],
		},
	],
	summary: {
		profiles: [
			{
				item_code: 'E104156',
				profile_code: 'E104156',
				item_name: '40mm Casement Frame',
				cut_length_mm: 1200,
				pieces: 8,
				total_mm: 9600,
				kg: 6.24,
				uom: 'Kg',
				spec_note: '1200 mm x 8 pcs',
				default_supplier: 'SUP-ALU',
			},
		],
		glass: [
			{
				item_code: '6CTG',
				glass_code: '6CTG',
				item_name: '6 mm clear toughened',
				width_mm: 1140,
				height_mm: 1140,
				pieces: 2,
				area_m2: 2.599,
				uom: 'Square Meter',
				spec_note: '1140 x 1140 mm x 2 pcs',
			},
		],
		hardware: [
			{
				item_code: 'GASKET-1',
				item_name: 'FRAME GASKET CASEMENT',
				category: 'Gasket',
				group: 'Gasket',
				qty: 9.6,
				uom: 'Meter',
				spec_note: '9.6 Meter',
			},
		],
	},
	problems: [],
}

beforeEach(() => {
	vi.mocked(materialTree).mockReset().mockResolvedValue(sampleTree)
	vi.mocked(makeProjectMaterialRequest).mockReset()
	vi.mocked(makeProjectPurchaseOrder).mockReset()
	vi.mocked(toast.success).mockClear()
	vi.mocked(toast.error).mockClear()
})

describe('BomTakeoffPanel', () => {
	it('renders the Project -> Window -> Profile / Glass / Hardware tree with cut lengths', async () => {
		const w = mount(BomTakeoffPanel, { props: { project: 'FP-2026-00002' } })
		await flushPromises()
		expect(w.text()).toContain('W01')
		expect(w.text()).toContain('E104156')
		expect(w.text()).toContain('1200')
		expect(w.text()).toContain('6CTG')
		expect(w.text()).toContain('1140 × 1140 mm')
		expect(w.text()).toContain('FRAME GASKET CASEMENT')
	})

	it('switches between Window BOM Tree and Consolidated PO Summary views', async () => {
		const w = mount(BomTakeoffPanel, { props: { project: 'FP-2026-00002' } })
		await flushPromises()
		expect(w.find('[data-testid="bom-tree-view"]').exists()).toBe(true)
		await w.get('[data-testid="view-summary"]').trigger('click')
		expect(w.find('[data-testid="bom-summary-view"]').exists()).toBe(true)
		expect(w.text()).toContain('Consolidated Aluminium Profiles')
		expect(w.text()).toContain('SUP-ALU')
	})

	it('creates a Material Request for selected category and target warehouse', async () => {
		vi.mocked(makeProjectMaterialRequest).mockResolvedValue({ ok: true, material_request: 'MAT-MR-0001' })
		const w = mount(BomTakeoffPanel, { props: { project: 'FP-2026-00002' } })
		await flushPromises()
		await w.get('[data-testid="bom-category"]').setValue('Profile')
		await w.get('[data-testid="bom-warehouse"]').setValue('Hilux Warehouse - OF')
		await w.get('[data-testid="create-mr"]').trigger('click')
		await flushPromises()
		expect(makeProjectMaterialRequest).toHaveBeenCalledWith('FP-2026-00002', 'Profile', 'Hilux Warehouse - OF')
		expect(w.get('[data-testid="created-docs"]').text()).toContain('MAT-MR-0001')
	})

	it('creates a Purchase Order when a supplier is selected', async () => {
		vi.mocked(makeProjectPurchaseOrder).mockResolvedValue({ ok: true, purchase_order: 'PUR-ORD-0001' })
		const w = mount(BomTakeoffPanel, { props: { project: 'FP-2026-00002' } })
		await flushPromises()
		await w.get('[data-testid="bom-category"]').setValue('Profile')
		await w.get('[data-testid="bom-supplier"]').setValue('SUP-ALU')
		await w.get('[data-testid="create-po"]').trigger('click')
		await flushPromises()
		expect(makeProjectPurchaseOrder).toHaveBeenCalledWith('FP-2026-00002', 'SUP-ALU', 'Profile', 'Main Warehouse - OF')
		expect(w.get('[data-testid="created-docs"]').text()).toContain('PUR-ORD-0001')
	})

	it('renders the window elevation preview image and dimensions in the BOM tree', async () => {
		const w = mount(BomTakeoffPanel, { props: { project: 'FP-2026-00002' } })
		await flushPromises()
		const preview = w.get('[data-testid="bom-window-preview"]')
		const img = preview.find('img')
		expect(img.exists()).toBe(true)
		expect(img.attributes('src')).toContain('data:image/svg+xml')
		const node = w.get('[data-testid="bom-window-node"]')
		expect(node.text()).toContain('1200 × 1200 mm')
		const treeToggle = w.get('[data-testid="view-tree"]')
		expect(treeToggle.classes()).toContain('bg-gray-900')
		expect(treeToggle.classes()).toContain('text-white')
	})
})

