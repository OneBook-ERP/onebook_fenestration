import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { splitCell } from '@/design/tree'
import { computeDesign } from '@/api'
import { useDesignerStore } from './designer'

vi.mock('@/api', () => ({ computeDesign: vi.fn() }))
const mocked = vi.mocked(computeDesign)

const res = (area: number) => ({ ok: true as const, result: { area_sqft: area } as never })

describe('designer compute', () => {
	beforeEach(() => {
		setActivePinia(createPinia())
		vi.useFakeTimers()
		mocked.mockReset()
	})
	afterEach(() => vi.useRealTimers())

	it('debounces three applies into one call', async () => {
		mocked.mockResolvedValue(res(1))
		const s = useDesignerStore()
		s.seriesVersion = 'SV1'
		s.apply((d) => ({ ...d, width: 1000 }))
		s.apply((d) => ({ ...d, width: 1100 }))
		s.apply((d) => ({ ...d, width: 1200 }))
		await vi.advanceTimersByTimeAsync(299)
		expect(mocked).not.toHaveBeenCalled()
		await vi.advanceTimersByTimeAsync(1)
		expect(mocked).toHaveBeenCalledTimes(1)
		expect(mocked.mock.calls[0][1]).toBe('SV1')
	})

	it('ignores out-of-order responses', async () => {
		let resolveFirst!: (v: never) => void
		mocked.mockImplementationOnce(() => new Promise((r) => (resolveFirst = r as never)))
		mocked.mockResolvedValueOnce(res(2))
		const s = useDesignerStore()
		s.seriesVersion = 'SV1'
		s.apply((d) => ({ ...d, width: 1000 }))
		await vi.advanceTimersByTimeAsync(300)
		s.apply((d) => ({ ...d, width: 1100 }))
		await vi.advanceTimersByTimeAsync(300)
		expect((s.result as { area_sqft: number }).area_sqft).toBe(2)
		resolveFirst(res(1) as never)
		await vi.advanceTimersByTimeAsync(0)
		expect((s.result as { area_sqft: number }).area_sqft).toBe(2)
	})

	it('ok:false sets error and keeps previous result', async () => {
		mocked.mockResolvedValueOnce(res(1))
		mocked.mockResolvedValueOnce({ ok: false, message: 'boom' })
		const s = useDesignerStore()
		s.seriesVersion = 'SV1'
		s.apply((d) => ({ ...d, width: 1000 }))
		await vi.advanceTimersByTimeAsync(300)
		s.apply((d) => ({ ...d, width: 1100 }))
		await vi.advanceTimersByTimeAsync(300)
		expect(s.error).toBe('boom')
		expect((s.result as { area_sqft: number }).area_sqft).toBe(1)
	})

	it('invalid design sets error and skips compute', async () => {
		const s = useDesignerStore()
		s.seriesVersion = 'SV1'
		s.apply((d) => ({ ...d, width: -5 }))
		await vi.advanceTimersByTimeAsync(300)
		expect(mocked).not.toHaveBeenCalled()
		expect(s.error).toMatch(/positive/)
	})

	it('undo/redo also recompute', async () => {
		mocked.mockResolvedValue(res(1))
		const s = useDesignerStore()
		s.seriesVersion = 'SV1'
		s.apply((d) => splitCell(d, 'F1', 'v'))
		await vi.advanceTimersByTimeAsync(300)
		s.undo()
		await vi.advanceTimersByTimeAsync(300)
		expect(mocked).toHaveBeenCalledTimes(2)
	})

	it('response landing after a newer apply but before its debounce is dropped', async () => {
		let resolveA!: (v: never) => void
		mocked.mockImplementationOnce(() => new Promise((r) => (resolveA = r as never)))
		const s = useDesignerStore()
		s.seriesVersion = 'SV1'
		s.apply((d) => ({ ...d, width: 1000 }))
		await vi.advanceTimersByTimeAsync(300)
		s.apply((d) => ({ ...d, width: 1100 }))
		await vi.advanceTimersByTimeAsync(100)
		resolveA(res(1) as never)
		await vi.advanceTimersByTimeAsync(0)
		expect(s.result).toBeNull()
	})

	it('cancelCompute drops pending timer', async () => {
		mocked.mockResolvedValue(res(1))
		const s = useDesignerStore()
		s.apply((d) => ({ ...d, width: 1000 }))
		s.cancelCompute()
		await vi.advanceTimersByTimeAsync(300)
		expect(mocked).not.toHaveBeenCalled()
	})
})
