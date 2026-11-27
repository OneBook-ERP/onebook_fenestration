import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { toast } from 'frappe-ui'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'
import { computeDesign, copyDesign, crossSection, getDesign, getFenestrationDefaults, profileCatalog, saveDesign } from '@/api'
import { routes } from '@/router'
import { useDesignerStore } from '@/stores/designer'
import { layoutGeom } from '@/design/geometry'

vi.mock('@/api', () => ({
	computeDesign: vi.fn(),
	saveDesign: vi.fn(),
	getDesign: vi.fn(),
	copyDesign: vi.fn(),
	crossSection: vi.fn(),
	windowAssembly: vi.fn().mockResolvedValue({ ok: true, result: { members: [], panes: [] }, outlines: {} }),
	getFenestrationDefaults: vi.fn(),
	profileCatalog: vi.fn().mockResolvedValue({ ok: true, items: [], next_start: null }),
	quoteStatus: vi.fn().mockResolvedValue({ quotation: null }),
}))
vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	toast: { success: vi.fn(), error: vi.fn() },
	useList: (await import('@/test-utils')).fakeUseList({
		'Profile Finish': [
			{ name: 'GREY', finish_name: 'Grey', color: '#8A8F98' },
			{ name: 'BROWN-5104', finish_name: '5104 PC Brown', color: '#6B3E26' },
		],
	}),
}))

const result = {
	members: [
		{ panel: 'F1', role: 'frame', position: 'top', profile: 'P1', length: 900, angles: '45/45', path: 'F1' },
		{ panel: 'F1', role: 'frame', position: 'bottom', profile: 'P1', length: 900, angles: '45/45', path: 'F1' },
	],
	glass: [{ panel: 'F1', number: 1, glass: '6CTG', width: 800, height: 900, path: 'F1' }],
	bom: [{ item: 'I', name: 'Hinge', qty: 2, uom: 'Nos', panel: 'S1', position: '', length: 0, group: 'Hardware' }],
	shutter_kg: { S1: 4.5 },
	window_kg: 10.1234,
	area_m2: 1.116,
	area_sqft: 12.013,
	pricing: {
		lines: [
			{ key: 'profile', label: 'Profile Cost', amount: 5000.5 },
			{ key: 'profit', label: 'Profit', amount: 11380.22 },
			{ key: 'subtotal', label: 'Material Subtotal', amount: 7000, include_in_total: false },
		],
		unit_price: 16380.72,
		rate_per_sqft: 1363.63,
	},
	issues: [
		{ severity: 'error', code: 'X', message: 'Too wide', panel: 'F1', hint: '', path: 'F1.0' },
		{ severity: 'warn', code: 'Y', message: 'Louver placeholder', panel: 'F1', hint: '', path: 'F1.1' },
	],
}

const w01 = {
	name: 'WD-1',
	project: 'P1',
	design_ref: 'W01',
	design_name: '',
	qty: 2,
	location: 'Hall',
	series_version: 'SV1',
	design_json: {
		width: 1200,
		height: 1200,
		root: {
			type: 'split',
			dir: 'v',
			at: [600],
			children: [
				{ type: 'fixed', glass: '6CTG' },
				{ type: 'fixed', glass: '6CTG' },
			],
		},
	},
	result_json: {},
	design_svg: '',
}

async function setup(path = '/projects/P1/designs/new?series_version=SV1') {
	const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
	router.push(path)
	await router.isReady()
	const wrapper = mount({ render: () => h(RouterView) }, { global: { plugins: [router] } })
	await flushPromises()
	return { wrapper, router }
}

function field(wrapper: VueWrapper, label: string) {
	const l = wrapper.findAll('label').find((x) => x.text().startsWith(label))
	if (!l) throw new Error(`no label ${label}`)
	return wrapper.find(`[id="${l.attributes("for")}"]`)
}
const button = (w: VueWrapper, name: string) => w.find(`button[aria-label="${name}"]`)
const tab = (w: VueWrapper, text: string) => w.findAll('button, [role="radio"]').find((b) => b.text().startsWith(text))!

describe('Designer page', () => {
	enableAutoUnmount(afterEach)
	beforeEach(() => {
		setActivePinia(createPinia())
		vi.useFakeTimers()
		vi.mocked(computeDesign).mockReset()
		vi.mocked(computeDesign).mockResolvedValue({ ok: true, result } as never)
		vi.mocked(getFenestrationDefaults).mockReset()
		vi.mocked(getFenestrationDefaults).mockResolvedValue({ default_finish: 'GREY', default_price_structure: 'Standard' })
		vi.mocked(crossSection).mockReset()
		vi.mocked(crossSection).mockImplementation(async (_d, _sv, axis, at) => ({
			ok: true,
			result: { axis, at: at ?? 200, length: 0, pieces: [], dims: [], issues: [] },
			outlines: {},
		}))
		vi.mocked(saveDesign).mockReset()
		vi.mocked(getDesign).mockReset()
		vi.mocked(profileCatalog).mockReset()
		vi.mocked(profileCatalog).mockResolvedValue({ ok: true, items: [], next_start: null } as never)
		vi.mocked(toast.error).mockReset()
	})
	afterEach(() => vi.useRealTimers())

	it('uses a column layout on phone and side-by-side from md', async () => {
		const { wrapper } = await setup()
		const aside = wrapper.find('aside')
		expect(aside.exists()).toBe(true)
		const body = aside.element.parentElement!
		expect(body.className).toContain('flex-col')
		expect(body.className).toContain('md:flex-row')
		expect(aside.classes()).toContain('md:w-72')
		expect(wrapper.get('main').classes()).toContain('min-h-[50vh]')
		expect(wrapper.get('main').classes()).toContain('md:min-h-0')
		expect(wrapper.find('[data-testid="eva-fab-dock"]').exists()).toBe(true)
		expect(wrapper.find('[data-testid="eva-3d-fabs"]').exists()).toBe(true)
	})

	it('applies the template from the query on a new design', async () => {
		await setup('/projects/P1/designs/new?series_version=SV1&template=ventilator')
		const root = useDesignerStore().design.root
		expect(root).toMatchObject({ type: 'split', dir: 'v' })
		expect(root.type === 'split' && root.children.some((c) => c.type === 'louver')).toBe(true)
	})

	it('choosing a finish recomputes with it and recolours the frame', async () => {
		const { wrapper } = await setup()
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		expect(vi.mocked(computeDesign).mock.calls[0][2]).toBe('GREY')
		expect(vi.mocked(computeDesign).mock.calls[0][3]).toBe('Standard')
		useDesignerStore().setFinish('BROWN-5104')
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		const last = vi.mocked(computeDesign).mock.calls.at(-1)!
		expect(last[2]).toBe('BROWN-5104')
		expect(wrapper.find('svg > rect:nth-of-type(2)').attributes('fill')).toBe('#6B3E26')
		expect(useDesignerStore().dirty).toBe(true)
	})

	it('results bar shows unit price and rate, and the Pricing tab lists heads', async () => {
		const { wrapper } = await setup()
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		expect(wrapper.text()).toContain('Live price ₹16,380.72')
		expect(wrapper.text()).toContain('₹1,363.63/sq.ft')
		await tab(wrapper, 'Pricing').trigger('click')
		await flushPromises()
		expect(wrapper.text()).toContain('Profile Cost')
		expect(wrapper.text()).toContain('₹5,000.50')
		expect(wrapper.text()).toContain('Profit')
		expect(wrapper.text()).toContain('₹11,380.22')
	})

	it('Pricing tab shows heads left out of the total in grey italics', async () => {
		const { wrapper } = await setup()
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		await tab(wrapper, 'Pricing').trigger('click')
		await flushPromises()
		const rows = wrapper.findAll('tr').filter((r) => r.text().includes('Subtotal') || r.text().includes('Profit'))
		const [profit, subtotal] = rows
		expect(subtotal.text()).toContain('Material Subtotal')
		expect(subtotal.classes()).toEqual(expect.arrayContaining(['italic', 'text-gray-500']))
		expect(profit.classes()).not.toContain('italic')
	})

	it('tools explain their disabled state', async () => {
		const { wrapper } = await setup()
		expect(button(wrapper, 'Sash').attributes('disabled')).toBeUndefined()
		useDesignerStore().select('nope')
		await flushPromises()
		expect(button(wrapper, 'Sash').attributes('disabled')).toBeDefined()
	})

	it('split vertical shows M1 on canvas', async () => {
		const { wrapper } = await setup()
		await wrapper.find('[data-path="F1"]').trigger('click')
		await button(wrapper, 'Split vertical').trigger('click')
		expect(wrapper.find('svg').text()).toContain('M1')
	})

	it('results bar shows computed area', async () => {
		const { wrapper } = await setup()
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		expect(wrapper.text()).toContain('12.013')
		expect(wrapper.text()).toContain('10.123')
	})

	it('save sends svg and width 915', async () => {
		vi.mocked(saveDesign).mockResolvedValue({ ok: true, name: 'WD-1', results: {} } as never)
		const { wrapper, router } = await setup()
		await field(wrapper, 'Design ref').setValue('W01')
		const w = field(wrapper, 'Width')
		await w.setValue('915')
		await w.trigger('change')
		await button(wrapper, 'Save').trigger('click')
		await flushPromises()
		const args = vi.mocked(saveDesign).mock.calls[0][0]
		expect(args.svg.startsWith('<svg')).toBe(true)
		expect(args.design.width).toBe(915)
		expect(args.design_ref).toBe('W01')
		expect(router.currentRoute.value.path).toBe('/projects/P1/designs/WD-1')
	})

	it('save while in 3d view still sends valid svg', async () => {
		vi.mocked(saveDesign).mockResolvedValue({ ok: true, name: 'WD-1', results: {} } as never)
		const { wrapper } = await setup()
		await field(wrapper, 'Design ref').setValue('W02')
		const btn3d = wrapper.findAll('button').find((b) => b.text() === '3D')
		await btn3d?.trigger('click')
		await flushPromises()
		await button(wrapper, 'Save').trigger('click')
		await flushPromises()
		const args = vi.mocked(saveDesign).mock.calls[0][0]
		expect(args.svg.startsWith('<svg')).toBe(true)
		expect(args.svg).toContain('</svg>')
	})

	it('save ok:false toasts the message', async () => {
		vi.mocked(saveDesign).mockResolvedValue({ ok: false, message: 'Nope' })
		const { wrapper } = await setup()
		await field(wrapper, 'Design ref').setValue('W01')
		await button(wrapper, 'Save').trigger('click')
		await flushPromises()
		expect(toast.error).toHaveBeenCalledWith('Nope')
	})

	it('save without ref shows validation and does not call api', async () => {
		const { wrapper } = await setup()
		await button(wrapper, 'Save').trigger('click')
		await flushPromises()
		expect(wrapper.text()).toContain('Design ref is required')
		expect(saveDesign).not.toHaveBeenCalled()
	})

	it('counts engine error and warn severities', async () => {
		const { wrapper } = await setup()
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		expect(wrapper.text()).toContain('1 errors')
		expect(wrapper.text()).toContain('1 warnings')
		await tab(wrapper, 'Issues').trigger('click')
		await flushPromises()
		expect(wrapper.find('[data-issue-path="F1.0"] .text-red-700').exists()).toBe(true)
		expect(wrapper.find('[data-issue-path="F1.1"] .text-amber-700').exists()).toBe(true)
	})

	it('clicking an issue row selects its path', async () => {
		const { wrapper } = await setup()
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		await tab(wrapper, 'Issues').trigger('click')
		await flushPromises()
		await wrapper.find('[data-issue-path="F1.0"]').trigger('click')
		expect(useDesignerStore().selectedPath).toBe('F1.0')
	})

	it('error banner keeps previous results visible', async () => {
		const { wrapper } = await setup()
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		useDesignerStore().error = 'Engine exploded'
		await flushPromises()
		expect(wrapper.find('[role="alert"]').text()).toContain('Engine exploded')
		expect(wrapper.text()).toContain('12.013')
	})

	it('loads a saved design returned as an object', async () => {
		vi.mocked(getDesign).mockResolvedValue(w01 as never)
		const { wrapper } = await setup('/projects/P1/designs/WD-1')
		expect(wrapper.find('svg').text()).toContain('M1')
		expect((field(wrapper, 'Design ref').element as HTMLInputElement).value).toBe('W01')
		expect(field(wrapper, 'Design ref').attributes('readonly')).toBeDefined()
		expect(button(wrapper, 'Save').attributes('disabled')).toBeUndefined()
	})

	it('locked design shows the lock banner, disables Save and copies to a new design', async () => {
		vi.mocked(getDesign).mockResolvedValue({ ...w01, locked_by: { doctype: 'Quotation', name: 'SAL-QTN-1' } } as never)
		vi.mocked(copyDesign).mockResolvedValue('WD-2')
		const { wrapper, router } = await setup('/projects/P1/designs/WD-1')
		expect(wrapper.text()).toContain('W01 is on Quotation SAL-QTN-1. Copy the design to change it.')
		expect(button(wrapper, 'Save').attributes('disabled')).toBeDefined()
		await button(wrapper, 'Copy design').trigger('click')
		await flushPromises()
		expect(copyDesign).toHaveBeenCalledWith('WD-1')
		expect(router.currentRoute.value.params.name).toBe('WD-2')
	})

	it('unlocked design shows no lock banner', async () => {
		vi.mocked(getDesign).mockResolvedValue({ ...w01, locked_by: null } as never)
		const { wrapper } = await setup('/projects/P1/designs/WD-1')
		expect(button(wrapper, 'Copy design').exists()).toBe(false)
		expect(button(wrapper, 'Save').attributes('disabled')).toBeUndefined()
	})

	it('save disabled while loading and after load failure', async () => {
		let resolve!: (v: never) => void
		vi.mocked(getDesign).mockImplementationOnce(() => new Promise((r) => (resolve = r as never)))
		const { wrapper } = await setup('/projects/P1/designs/WD-1')
		expect(button(wrapper, 'Save').attributes('disabled')).toBeDefined()
		expect(wrapper.find('svg').exists()).toBe(false)
		resolve(w01 as never)
		await flushPromises()
		expect(button(wrapper, 'Save').attributes('disabled')).toBeUndefined()
	})

	it('save disabled when load rejects', async () => {
		vi.mocked(getDesign).mockRejectedValue(new Error('gone'))
		const { wrapper } = await setup('/projects/P1/designs/WD-1')
		expect(button(wrapper, 'Save').attributes('disabled')).toBeDefined()
		expect(wrapper.text()).toContain('gone')
	})

	it('one bar drag is one undo step', async () => {
		vi.mocked(getDesign).mockResolvedValue(w01 as never)
		const { wrapper } = await setup('/projects/P1/designs/WD-1')
		const store = useDesignerStore()
		const before = store.design
		const depth = store.past.length
		const bar = wrapper.find('[data-bar="M1"]')
		await bar.trigger('pointerdown', { clientX: 100, pointerId: 1 })
		for (let i = 1; i <= 10; i++) await bar.trigger('pointermove', { clientX: 100 + i * 5, pointerId: 1 })
		await bar.trigger('pointerup', { clientX: 150, pointerId: 1 })
		expect(store.past).toHaveLength(depth + 1)
		await button(wrapper, 'Undo').trigger('click')
		expect(store.design).toEqual(before)
	})

	it('undo works when the drag ends on window pointerup or lostpointercapture', async () => {
		vi.mocked(getDesign).mockResolvedValue(w01 as never)
		const { wrapper } = await setup('/projects/P1/designs/WD-1')
		const store = useDesignerStore()
		const bar = () => wrapper.find('[data-bar="M1"]')
		for (const end of ['window', 'lost']) {
			await bar().trigger('pointerdown', { clientX: 100, pointerId: 1 })
			await bar().trigger('pointermove', { clientX: 60, pointerId: 1 })
			if (end === 'window') window.dispatchEvent(new Event('pointerup'))
			else await bar().trigger('lostpointercapture', { pointerId: 1 })
			await flushPromises()
			expect(store.past).toHaveLength(1)
			expect(button(wrapper, 'Undo').attributes('disabled')).toBeUndefined()
			await button(wrapper, 'Undo').trigger('click')
			expect((store.design.root as { at: number[] }).at).toEqual([600])
			store.past = []
			store.future = []
		}
	})

	it('asks before leaving with unsaved changes and stays on cancel', async () => {
		const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
		const { wrapper, router } = await setup()
		await wrapper.find('[data-path="F1"]').trigger('click')
		await button(wrapper, 'Split vertical').trigger('click')
		await router.push('/projects/P1')
		await flushPromises()
		expect(confirm).toHaveBeenCalledWith('Discard unsaved changes?')
		expect(router.currentRoute.value.name).toBe('NewDesign')
		confirm.mockRestore()
	})

	it('does not ask after a successful save', async () => {
		const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
		vi.mocked(saveDesign).mockResolvedValue({ ok: true, name: 'WD-1', results: {} } as never)
		const { wrapper, router } = await setup()
		await button(wrapper, 'Split vertical').trigger('click')
		await field(wrapper, 'Design ref').setValue('W01')
		await button(wrapper, 'Save').trigger('click')
		await flushPromises()
		await router.push('/projects/P1')
		await flushPromises()
		expect(confirm).not.toHaveBeenCalled()
		expect(router.currentRoute.value.name).toBe('Project')
		confirm.mockRestore()
	})

	it('blocks unload only while dirty', async () => {
		const { wrapper } = await setup()
		const unload = () => {
			const e = new Event('beforeunload', { cancelable: true })
			window.dispatchEvent(e)
			return e.defaultPrevented
		}
		expect(unload()).toBe(false)
		await button(wrapper, 'Split vertical').trigger('click')
		expect(unload()).toBe(true)
		wrapper.unmount()
		expect(unload()).toBe(false)
	})

	it('a stale load failure does not touch the current route', async () => {
		let reject!: (e: Error) => void
		vi.mocked(getDesign)
			.mockImplementationOnce(() => new Promise((_, r) => (reject = r)))
			.mockResolvedValueOnce({ ...w01, name: 'WD-2', design_ref: 'W02' } as never)
		const { wrapper, router } = await setup('/projects/P1/designs/WD-1')
		await router.push('/projects/P1/designs/WD-2')
		await flushPromises()
		reject(new Error('gone'))
		await flushPromises()
		expect(wrapper.find('[role="alert"]').exists()).toBe(false)
		expect(button(wrapper, 'Save').attributes('disabled')).toBeUndefined()
		expect((field(wrapper, 'Design ref').element as HTMLInputElement).value).toBe('W02')
	})

	it('a stale load finishing does not clear loading for the current route', async () => {
		let resolve1!: (v: never) => void
		let resolve2!: (v: never) => void
		vi.mocked(getDesign)
			.mockImplementationOnce(() => new Promise((r) => (resolve1 = r as never)))
			.mockImplementationOnce(() => new Promise((r) => (resolve2 = r as never)))
		const { wrapper, router } = await setup('/projects/P1/designs/WD-1')
		await router.push('/projects/P1/designs/WD-2')
		await flushPromises()
		resolve1(w01 as never)
		await flushPromises()
		expect(wrapper.text()).toContain('Loading design...')
		expect(button(wrapper, 'Save').attributes('disabled')).toBeDefined()
		resolve2({ ...w01, name: 'WD-2', design_ref: 'W02' } as never)
		await flushPromises()
		expect(wrapper.text()).not.toContain('Loading design...')
	})

	it('view toggle is a segmented control exposing its state with aria-pressed', async () => {
		const { wrapper } = await setup()
		const seg = (t: string) => wrapper.findAll('button').find((b) => b.text() === t)!
		expect(seg('Inside').attributes('aria-pressed')).toBe('true')
		expect(seg('Outside').attributes('aria-pressed')).toBe('false')
		await seg('Outside').trigger('click')
		expect(seg('Outside').attributes('aria-pressed')).toBe('true')
		expect(seg('Inside').attributes('aria-pressed')).toBe('false')
		expect(wrapper.find('svg').text()).toContain('View from outside')
	})

	it('breadcrumb links to the project and shows ref and typology', async () => {
		vi.mocked(getDesign).mockResolvedValue(w01 as never)
		const { wrapper } = await setup('/projects/P1/designs/WD-1')
		const link = wrapper.find('header a[href$="/projects/P1"]')
		expect(link.text()).toBe('Projects / P1')
		expect(wrapper.find('header').text()).toContain('W01 · Fixed')
	})

	it('undo, redo, clear, and fit to view buttons appear in the center toolbar', async () => {
		const { wrapper } = await setup()
		expect(button(wrapper, 'Undo').text()).toBe('Undo')
		expect(button(wrapper, 'Redo').text()).toBe('Redo')
		expect(button(wrapper, 'Clear').text()).toBe('Clear')
		expect(button(wrapper, 'Fit to view').text()).toBe('Fit to view')
	})

	it('unmount cancels pending compute', async () => {
		const { wrapper } = await setup()
		wrapper.unmount()
		await vi.advanceTimersByTimeAsync(300)
		expect(computeDesign).not.toHaveBeenCalled()
	})
	it('section toggle shows the cut view and a cell click moves the cut', async () => {
		const { wrapper } = await setup()
		const seg = (t: string) => wrapper.findAll('button').find((b) => b.text() === t)
		const last = () => vi.mocked(crossSection).mock.calls.at(-1)!
		expect(seg('B–B horizontal')).toBeUndefined()
		expect(button(wrapper, 'Section').attributes('aria-pressed')).toBe('false')
		await button(wrapper, 'Section').trigger('click')
		await flushPromises()
		expect(button(wrapper, 'Section').attributes('aria-pressed')).toBe('true')
		expect(wrapper.get('main').classes()).toContain('md:flex-row')
		expect(wrapper.find('[data-testid="section-split-pane"]').exists()).toBe(true)
		const resizer = wrapper.find('[data-testid="workspace-resizer"]')
		expect(resizer.exists()).toBe(true)
		await resizer.trigger('pointerdown', { clientX: 500, button: 0, pointerId: 1 })
		await resizer.trigger('pointermove', { clientX: 350, pointerId: 1 })
		await resizer.trigger('pointerup', { pointerId: 1 })
		expect(wrapper.get('[data-testid="designer-left-pane"]').attributes('style')).toContain('width: 35%')
		await resizer.trigger('dblclick')
		expect(wrapper.get('[data-testid="designer-left-pane"]').attributes('style')).toContain('width: 50%')
		expect(seg('B–B horizontal')).toBeDefined()
		expect(wrapper.findAll('[data-cut]')).toHaveLength(2)
		expect(last().slice(1)).toEqual(['SV1', 'h', null])
		await seg('A–A vertical')!.trigger('click')
		await flushPromises()
		expect(last()[2]).toBe('v')
		const cell = layoutGeom(useDesignerStore().design).cells.at(-1)!
		await wrapper.find(`[data-path="${cell.path}"]`).trigger('click')
		await flushPromises()
		expect(last().slice(2)).toEqual(['v', cell.x + cell.w / 2])
		await button(wrapper, 'Section').trigger('click')
		expect(wrapper.findAll('[data-cut]')).toHaveLength(0)
		expect(seg('B–B horizontal')).toBeUndefined()
	})

	it('design edits with no cut picked fetch the section once, after the debounce', async () => {
		const { wrapper } = await setup()
		await button(wrapper, 'Section').trigger('click')
		await flushPromises()
		const before = vi.mocked(crossSection).mock.calls.length
		const store = useDesignerStore()
		for (const width of [1000, 1010, 1020]) store.apply((d) => ({ ...d, width }))
		await flushPromises()
		expect(vi.mocked(crossSection).mock.calls.length).toBe(before)
		await vi.advanceTimersByTimeAsync(300)
		await flushPromises()
		expect(vi.mocked(crossSection).mock.calls.length).toBe(before + 1)
		const call = vi.mocked(crossSection).mock.calls.at(-1)!
		expect(call[0].width).toBe(1020)
		expect(call[3]).toBeNull()
	})

	it('markers follow the engine-snapped cut without refetching', async () => {
		const { wrapper } = await setup()
		await button(wrapper, 'Section').trigger('click')
		await flushPromises()
		const n = vi.mocked(crossSection).mock.calls.length
		// The mock engine snaps the default B–B cut to y=200 mm; the marker sits there.
		const { width, height } = useDesignerStore().design
		const scale = Math.min(520 / width, 640 / height)
		const py = (760 - height * scale) / 2 + (height - 200) * scale
		expect(Number(wrapper.get('[data-cut="h"] line').attributes('y1'))).toBeCloseTo(py, 6)
		await flushPromises()
		expect(vi.mocked(crossSection).mock.calls.length).toBe(n)
	})

	it('edit group: delete enabled/disabled states and actions for sash, fan, and split', async () => {
		const { wrapper } = await setup()
		const store = useDesignerStore()

		// Plain fixed glass panel
		const editGroup = wrapper.find('[data-testid="edit-group-card"]')
		expect(editGroup.exists()).toBe(true)
		const delBtn = editGroup.find('button[aria-label="Delete"]')
		expect(delBtn.attributes('aria-disabled')).toBe('true')
		expect(delBtn.text()).toContain('Delete')

		// Convert to sash
		await button(wrapper, 'Sash').trigger('click')
		await flushPromises()
		expect(delBtn.attributes('aria-disabled')).toBe('false')
		expect(delBtn.text()).toContain('Delete sash')

		// Click delete -> becomes fixed glass, undo restores it
		await delBtn.trigger('click')
		await flushPromises()
		expect(store.design.root.type).toBe('fixed')
		store.undo()
		await flushPromises()
		expect(store.design.root.type).toBe('sash')

		// Convert to louver -> selection chip stays single-line nowrap and delete button aligns cleanly
		await button(wrapper, 'Louver').trigger('click')
		await flushPromises()
		expect(editGroup.text()).toContain('Louver F1 selected')
		expect(delBtn.attributes('aria-disabled')).toBe('false')
		expect(delBtn.text()).toContain('Delete louver')
		const chipEl = editGroup.find('span[title="Louver F1 selected"]')
		expect(chipEl.attributes('style')).toContain('white-space: nowrap')

		// Reset panel button returns to fixed
		const resetBtn = editGroup.find('button[aria-label="Reset panel"]')
		expect(resetBtn.attributes('aria-disabled')).toBe('false')
		await resetBtn.trigger('click')
		await flushPromises()
		expect(store.design.root.type).toBe('fixed')
	})

	it('keyboard shortcut: Delete key deletes selected item on canvas but not inside an input', async () => {
		const { wrapper } = await setup()
		const store = useDesignerStore()

		// Convert to sash
		await button(wrapper, 'Sash').trigger('click')
		await flushPromises()
		expect(store.design.root.type).toBe('sash')

		// Dispatch Delete while typing in an input
		const input = document.createElement('input')
		document.body.appendChild(input)
		input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true }))
		await flushPromises()
		expect(store.design.root.type).toBe('sash')
		document.body.removeChild(input)

		// Dispatch Delete on canvas / window
		window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true }))
		await flushPromises()
		expect(store.design.root.type).toBe('fixed')
	})

	it('Save button turns into Exit after saving, reverts to Save on any change, and Exit returns to project', async () => {
		vi.mocked(saveDesign).mockResolvedValue({ ok: true, name: 'WD-1', results: {} } as never)
		const { wrapper, router } = await setup()
		await field(wrapper, 'Design ref').setValue('W01')
		await flushPromises()

		// Initially displays Save
		expect(wrapper.find('button[aria-label="Save"]').exists()).toBe(true)
		expect(wrapper.find('button[aria-label="Exit"]').exists()).toBe(false)

		// Save turns the button into Exit
		await button(wrapper, 'Save').trigger('click')
		await flushPromises()
		expect(wrapper.find('button[aria-label="Exit"]').exists()).toBe(true)
		expect(wrapper.find('button[aria-label="Save"]').exists()).toBe(false)

		// Any subsequent change turns Exit back into Save
		await field(wrapper, 'Location').setValue('Hall')
		await flushPromises()
		expect(wrapper.find('button[aria-label="Save"]').exists()).toBe(true)
		expect(wrapper.find('button[aria-label="Exit"]').exists()).toBe(false)

		// Saving again returns to Exit, and clicking Exit navigates back to project
		await button(wrapper, 'Save').trigger('click')
		await flushPromises()
		expect(wrapper.find('button[aria-label="Exit"]').exists()).toBe(true)
		await button(wrapper, 'Exit').trigger('click')
		await flushPromises()
		expect(router.currentRoute.value.path).toBe('/projects/P1')
	})

	it('auto-prompts profile picker on adding mullion, sash, or bead-on but not louver', async () => {
		vi.mocked(profileCatalog).mockResolvedValue({
			ok: true,
			next_start: null,
			items: [
				{
					name: 'E104159',
					profile_code: 'E104159',
					profile_name: '40mm Casement Mullion',
					role: 'mullion',
					width_mm: 60,
					depth_mm: 40,
					section_svg: 'M 0 0 L 40 0 L 40 60 L 0 60 Z',
					has_outline: true,
					current_series: true,
				},
				{
					name: 'E104160',
					profile_code: 'E104160',
					profile_name: '40mm Casement Sash',
					role: 'sash',
					width_mm: 60,
					depth_mm: 40,
					section_svg: 'M 0 0 L 40 0 L 40 60 L 0 60 Z',
					has_outline: true,
					current_series: true,
				},
				{
					name: 'CS4807-CS400',
					profile_code: 'CS4807-CS400',
					profile_name: '6 & 8mm Glass Beading',
					role: 'bead',
					width_mm: 23,
					depth_mm: 20,
					section_svg: 'M 0 0 L 23 0 L 23 20 L 0 20 Z',
					has_outline: true,
					current_series: true,
				},
			],
		} as never)

		const { wrapper } = await setup()
		const store = useDesignerStore()
		await flushPromises()

		// Split vertical -> immediately prompts mullion picker and assigns selection to M1
		await wrapper.get('[data-path="F1"]').trigger('click')
		await button(wrapper, 'Split vertical').trigger('click')
		await flushPromises()
		const mullionModal = wrapper.get('[data-testid="profile-picker-modal"]')
		expect(mullionModal.text()).toContain('Select mullion profile')
		await mullionModal.findAll('[data-testid="profile-card-item"]').find((c) => c.text().includes('E104159'))!.trigger('click')
		await flushPromises()
		expect((store.design as { profiles?: Record<string, string> }).profiles?.M1).toBe('E104159')

		// Sash on F1.0 -> immediately prompts sash picker; cancelling keeps default
		await wrapper.get('[data-path="F1.0"]').trigger('click')
		await button(wrapper, 'Sash').trigger('click')
		await flushPromises()
		const sashModal = wrapper.get('[data-testid="profile-picker-modal"]')
		expect(sashModal.text()).toContain('Select sash profile')
		await sashModal.findAll('button').find((b) => b.text().trim() === 'Close')!.trigger('click')
		await flushPromises()
		expect(wrapper.find('[data-testid="profile-picker-modal"]').exists()).toBe(false)

		// Louver on F1.1 -> no profile picker
		await wrapper.get('[data-path="F1.1"]').trigger('click')
		await button(wrapper, 'Louver').trigger('click')
		await flushPromises()
		expect(wrapper.find('[data-testid="profile-picker-modal"]').exists()).toBe(false)

		// Convert back to Fixed glass -> beading is automatically enabled without requiring a manual bead toggle
		await button(wrapper, 'Fixed glass').trigger('click')
		await flushPromises()
		expect(wrapper.find('[data-testid="profile-picker-modal"]').exists()).toBe(false)
		expect((store.design.root as { children: { bead?: boolean }[] }).children[1].bead).toBe(true)
	})

	it('divider spec popover inserts exact number of mullions (no off-by-one) and handles drops cleanly', async () => {
		const { wrapper } = await setup()
		const store = useDesignerStore()
		await flushPromises()

		// Open Divider palette -> click Mullion -> confirm default count = 1
		await wrapper.get('button[aria-label="Divider tools"]').trigger('click')
		await flushPromises()
		await wrapper.get('[data-testid="eva-divider-palette"] button[title="mullion"]').trigger('click')
		await flushPromises()
		const pop = wrapper.get('[data-testid="eva-divider-spec-popover"]')
		await pop.findAll('button').find((b) => b.text().trim() === 'Confirm')!.trigger('click')
		await flushPromises()

		// Exactly 1 mullion (M1) -> 2 bays, NOT 2 mullions (3 bays)
		const root = store.design.root as { type: string; at: number[]; children: unknown[] }
		expect(root.type).toBe('split')
		expect(root.at).toHaveLength(1)
		expect(root.children).toHaveLength(2)

		// Drop Bottom Hung onto F1.1 via canvas drop-tool event -> sets bottom hinge without popping blocking modal
		const canvas = wrapper.findComponent({ name: 'WindowCanvas' })
		canvas.vm.$emit('drop-tool', { kind: 'openable', id: 'Bottom Hung', cellPath: 'F1.1' })
		await flushPromises()
		expect((store.design.root as { children: { hinge?: string; type: string }[] }).children[1]).toMatchObject({
			type: 'sash',
			hinge: 'bottom',
		})
		expect(wrapper.find('[data-testid="profile-picker-modal"]').exists()).toBe(false)

		// Apply 2 Track X-2X-X Panel -> exactly 3 panels with 1:2:1 ratios and center fixed
		await wrapper.get('button[aria-label="Designs & Templates"]').trigger('click')
		await flushPromises()
		await wrapper.get('[data-testid="eva-designs-palette"] button[title="2 Track X-2X-X Panel"]').trigger('click')
		await flushPromises()
		const sRoot = store.design.root as { type: string; at: number[]; children: { isSliding?: boolean; slideFixed?: boolean }[] }
		expect(store.design.isSliding).toBe(true)
		expect(sRoot.children).toHaveLength(3)
		expect(sRoot.at).toEqual([300, 900])
		expect(sRoot.children[1].slideFixed).toBe(true)

		// Switching to Approx 3D keeps the top-left Eva FAB dock visible and supports drag-and-drop
		await button(wrapper, '3D').trigger('click')
		await flushPromises()
		expect(wrapper.get('[data-testid="eva-fab-dock"]').isVisible()).toBe(true)
		expect(wrapper.find('[data-testid="sidebar-series-select"]').exists()).toBe(false)

		;(window as unknown as { __fenDragPayload?: string }).__fenDragPayload = JSON.stringify({
			kind: 'openable',
			id: 'Top Hung',
		})
		await wrapper.get('[data-testid="approx-3d-view"]').trigger('drop', { clientX: 200, clientY: 200 })
		await flushPromises()
		expect(store.design.isSliding).toBe(false)
	})

	it('does not double-rotate pre-transformed profileCatalog outlines while rotating raw catalog rows', async () => {
		vi.mocked(profileCatalog).mockResolvedValue({
			ok: true,
			next_start: null,
			items: [
				{
					name: 'P1',
					profile_code: 'P1',
					profile_name: '40mm Casement Frame',
					role: 'frame',
					width_mm: 50,
					depth_mm: 40,
					section_svg: 'M 0 0 L 50 0 L 50 40 L 0 40 Z',
					section_rotation: '90',
					section_flip_x: 1,
					outline_transformed: true,
					has_outline: true,
					current_series: true,
				},
			],
		} as never)

		const { wrapper } = await setup()
		vi.advanceTimersByTime(500)
		await flushPromises()

		// Sidebar thumbnail uses pre-transformed SVG directly without re-applying transform
		expect(wrapper.get('[data-testid="profile-thumb-frame"] svg g').attributes('transform')).toBeUndefined()

		await wrapper.get('[data-testid="profile-picker-btn-frame"]').trigger('click')
		await flushPromises()
		await wrapper.get('[data-testid="profile-dropdown-frame"] [data-testid="profile-dropdown-browse-all"]').trigger('click')
		await flushPromises()
		const modal = wrapper.get('[data-testid="profile-picker-modal"]')
		expect(modal.get('[data-testid="profile-card-item"] svg g').attributes('transform')).toBe('')
	})

	it('disables Cutting sheet button until saved and links to Window Cutting Sheet PDF once saved', async () => {
		vi.mocked(getDesign).mockResolvedValue({ ...w01 } as never)
		const { wrapper: unsaved } = await setup('/projects/P1/designs/new?series_version=SV1')
		const unsavedBtn = unsaved.get('[data-testid="designer-cutting-sheet"]')
		expect(unsavedBtn.attributes('disabled')).toBeDefined()
		unsaved.unmount()

		const { wrapper: saved } = await setup('/projects/P1/designs/WD-1')
		const savedBtn = saved.get('[data-testid="designer-cutting-sheet"]')
		expect(savedBtn.attributes('disabled')).toBeUndefined()
		expect(savedBtn.attributes('href')).toContain('doctype=Window+Design')
		expect(savedBtn.attributes('href')).toContain('name=WD-1')
		expect(savedBtn.attributes('href')).toContain('format=Window+Cutting+Sheet')
	})

	it('keeps right 3D FABs and Inside/Outside pill visible with Section open, closes left FAB palette on click out, and drops tools in realistic 3D', async () => {
		const { wrapper } = await setup()
		const store = useDesignerStore()
		await flushPromises()

		// 1. Open Section split -> right 3D FABs & Inside/Outside pill stay visible inside left designer pane
		await button(wrapper, 'Section').trigger('click')
		await flushPromises()
		expect(wrapper.find('[data-testid="section-split-pane"]').exists()).toBe(true)
		expect(wrapper.get('[data-testid="designer-left-pane"] [data-testid="eva-3d-fabs"]').isVisible()).toBe(true)
		expect(wrapper.get('[data-testid="designer-left-pane"] [data-testid="eva-side-pill"]').isVisible()).toBe(true)

		// 2. Left FAB palette closes when clicking outside
		const palEl = wrapper.get('[data-testid="eva-divider-palette"]').element as HTMLElement
		expect(palEl.style.display).toBe('none')
		await wrapper.get('button[aria-label="Divider tools"]').trigger('click')
		await flushPromises()
		expect(palEl.style.display).toBe('')
		await wrapper.get('[data-testid="designer-left-pane"]').trigger('pointerdown')
		await flushPromises()
		expect(palEl.style.display).toBe('none')

		// 3. Switch to Realistic 3D view and drop a sash onto the 3D model
		await wrapper.get('button[aria-label="Realistic 3D"]').trigger('click')
		await flushPromises()
		expect(wrapper.find('[data-testid="window-3d-view"]').exists()).toBe(true)
		;(window as unknown as { __fenDragPayload?: string }).__fenDragPayload = JSON.stringify({
			kind: 'openable',
			id: 'Left Openable',
		})
		await wrapper.get('[data-testid="window-3d-view"]').trigger('drop', { clientX: 200, clientY: 200 })
		await flushPromises()
		expect((store.design.root as { type: string }).type).toBe('sash')
	})

	it('prompts confirmation before replacing entire design when dropping onto empty space in 3D views and supports 1-step Undo', async () => {
		const { wrapper } = await setup()
		const store = useDesignerStore()
		await flushPromises()

		// Build a split casement design first so we verify the entire old design is cleared on replace
		await button(wrapper, 'Split vertical').trigger('click')
		await flushPromises()
		expect(store.design.root.type).toBe('split')

		// Switch to Approx 3D and drop onto empty canvas corner (10, 10) -> opens confirmation modal
		await button(wrapper, '3D').trigger('click')
		await flushPromises()
		;(window as unknown as { __fenDragPayload?: string }).__fenDragPayload = JSON.stringify({
			kind: 'openable',
			id: 'Top Hung',
		})
		await wrapper.get('[data-testid="approx-3d-view"]').trigger('drop', { clientX: 10, clientY: 10 })
		await flushPromises()

		const modal = wrapper.get('[data-testid="replace-design-confirm-modal"]')
		expect(modal.text()).toContain('Replace current design?')
		expect(modal.text()).toContain('Top Hung')
		// Old split design is still untouched before confirmation
		expect(store.design.root.type).toBe('split')

		// Cancelling preserves old design untouched
		await modal.findAll('button').find((b) => b.text().trim() === 'Cancel')!.trigger('click')
		await flushPromises()
		expect(wrapper.find('[data-testid="replace-design-confirm-modal"]').exists()).toBe(false)
		expect(store.design.root.type).toBe('split')

		// Re-drop in empty space from Realistic 3D view and confirm replacement
		await wrapper.get('button[aria-label="Realistic 3D"]').trigger('click')
		await flushPromises()
		wrapper.findComponent({ name: 'Window3DView' }).vm.$emit('drop-tool', {
			kind: 'sliding',
			id: '2 Track 2 Panel',
			cellPath: '',
			replaceDesign: true,
		})
		await flushPromises()

		await wrapper.get('[data-testid="confirm-replace-design-btn"]').trigger('click')
		await flushPromises()
		expect(wrapper.find('[data-testid="replace-design-confirm-modal"]').exists()).toBe(false)
		expect(store.design.isSliding).toBe(true)
		expect(store.design.trackCount).toBe(2)

		// Single Undo restores the previous 2-bay split design atomically
		store.undo()
		await flushPromises()
		expect(store.design.isSliding).toBeFalsy()
		expect(store.design.root.type).toBe('split')
	})

	it('seeds catalog profile widths before compute resolves so initial widths are available immediately', async () => {
		vi.mocked(profileCatalog).mockResolvedValue({
			ok: true,
			next_start: null,
			items: [
				{ name: 'F1P', profile_code: 'F1P', profile_name: '44mm Frame', role: 'frame', width_mm: 44, depth_mm: 60, current_series: true },
				{ name: 'S1P', profile_code: 'S1P', profile_name: '64mm Sash', role: 'sash', width_mm: 64, depth_mm: 55, current_series: true },
			],
		} as never)

		await setup()
		const store = useDesignerStore()
		expect(store.catalogProfileWidths).toMatchObject({ F1P: 44, S1P: 64 })
		expect(store.catalogRoleDefaults).toMatchObject({ frame: 'F1P', sash: 'S1P' })
	})
})
