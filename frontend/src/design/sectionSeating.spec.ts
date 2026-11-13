import { afterEach, describe, expect, it, vi } from 'vitest'
import { startSectionSeating, type SeatingEntry } from './sectionSeating'
import { reactive } from 'vue'
class FakeWorker {
	static last: FakeWorker
	onmessage: ((event: { data: unknown }) => void) | null = null
	onerror: (() => void) | null = null
	onmessageerror: (() => void) | null = null
	postMessage = vi.fn()
	terminate = vi.fn()
	constructor() { FakeWorker.last = this }
}
const entries = [{
	piece: { kind: 'profile', role: 'sash', code: 'S1', panel: 'F1', start: 18, end: 78, thickness: 0, mirrored: false },
	outline: null, start: 18, end: 78, needsSeat: true,
	transform: { offsetAlong: 0, offsetDepth: -11.5, rotation: 0, flipX: false, flipY: false },
}] satisfies SeatingEntry[]
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
describe('background section fitting', () => {
	it('sends cloneable geometry and releases the worker after completion', () => {
		vi.stubGlobal('Worker', FakeWorker)
		const complete = vi.fn(); const failed = vi.fn()
		startSectionSeating(reactive(entries), complete, failed)
		const worker = FakeWorker.last
		expect(structuredClone(worker.postMessage.mock.calls[0][0])).toEqual(entries)
		const transforms = entries.map(e => e.transform)
		worker.onmessage!({ data: transforms })
		expect(complete).toHaveBeenCalledWith(transforms)
		expect(worker.terminate).toHaveBeenCalledOnce()
		expect(failed).not.toHaveBeenCalled()
	})
	it('ignores late results after cancelling an obsolete cut', () => {
		vi.stubGlobal('Worker', FakeWorker)
		const complete = vi.fn()
		const cancel = startSectionSeating(entries, complete, vi.fn())
		cancel(); FakeWorker.last.onmessage!({ data: [] })
		expect(complete).not.toHaveBeenCalled()
		expect(FakeWorker.last.terminate).toHaveBeenCalledOnce()
	})
	it('terminates runaway fitting without a synchronous fallback', () => {
		vi.useFakeTimers(); vi.stubGlobal('Worker', FakeWorker)
		const complete = vi.fn(); const failed = vi.fn()
		startSectionSeating(entries, complete, failed)
		vi.advanceTimersByTime(10000)
		expect(FakeWorker.last.terminate).toHaveBeenCalledOnce()
		expect(failed).toHaveBeenCalledOnce()
		expect(complete).not.toHaveBeenCalled()
	})
	it('keeps defaults when worker creation fails', () => {
		vi.stubGlobal('Worker', class { constructor() { throw new Error('blocked') } })
		const failed = vi.fn()
		expect(() => startSectionSeating(entries, vi.fn(), failed)).not.toThrow()
		expect(failed).toHaveBeenCalledOnce()
	})
})
