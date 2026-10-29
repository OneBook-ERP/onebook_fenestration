import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { toast } from 'frappe-ui'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'
import { computeDesign, getDesign, getFenestrationDefaults, saveDesign } from '@/api'
import { routes } from '@/router'
import { useDesignerStore } from '@/stores/designer'

vi.mock('@/api', () => ({
	computeDesign: vi.fn(),
	saveDesign: vi.fn(),
	getDesign: vi.fn(),
	getFenestrationDefaults: vi.fn(),
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
		vi.mocked(saveDesign).mockReset()
		vi.mocked(getDesign).mockReset()
		vi.mocked(toast.error).mockReset()
	})
	afterEach(() => vi.useRealTimers())

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
		expect(wrapper.text()).toContain('Unit price ₹16,380.72')
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

	it('view toggle exposes its state with aria-pressed', async () => {
		const { wrapper } = await setup()
		const toggle = () => wrapper.findAll('button').find((b) => b.text() === 'Outside view')!
		expect(toggle().attributes('aria-pressed')).toBe('false')
		expect(toggle().attributes('aria-label')).toBe('Outside view')
		await toggle().trigger('click')
		expect(toggle().attributes('aria-pressed')).toBe('true')
		expect(wrapper.find('svg').text()).toContain('View from outside')
	})

	it('unmount cancels pending compute', async () => {
		const { wrapper } = await setup()
		wrapper.unmount()
		await vi.advanceTimersByTimeAsync(300)
		expect(computeDesign).not.toHaveBeenCalled()
	})
})
