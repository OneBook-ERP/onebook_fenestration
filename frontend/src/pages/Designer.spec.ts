import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { toast } from 'frappe-ui'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { computeDesign, getDesign, saveDesign } from '@/api'
import { routes } from '@/router'
import { useDesignerStore } from '@/stores/designer'
import Designer from './Designer.vue'

vi.mock('@/api', () => ({ computeDesign: vi.fn(), saveDesign: vi.fn(), getDesign: vi.fn() }))
vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	toast: { success: vi.fn(), error: vi.fn() },
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
	issues: [{ severity: 'Error', code: 'X', message: 'Too wide', panel: 'F1', hint: '', path: 'F1.0' }],
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
	const wrapper = mount(Designer, { global: { plugins: [router] } })
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
	beforeEach(() => {
		setActivePinia(createPinia())
		vi.useFakeTimers()
		vi.mocked(computeDesign).mockReset()
		vi.mocked(computeDesign).mockResolvedValue({ ok: true, result } as never)
		vi.mocked(saveDesign).mockReset()
		vi.mocked(getDesign).mockReset()
		vi.mocked(toast.error).mockReset()
	})
	afterEach(() => vi.useRealTimers())

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

	it('unmount cancels pending compute', async () => {
		const { wrapper } = await setup()
		wrapper.unmount()
		await vi.advanceTimersByTimeAsync(300)
		expect(computeDesign).not.toHaveBeenCalled()
	})
})
