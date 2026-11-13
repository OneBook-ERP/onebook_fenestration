import type { SectionOutline, SectionPiece } from '@/api'
import type { SectionPieceTransform } from './types'

export interface SeatingEntry {
	piece: SectionPiece
	outline: SectionOutline | null
	start: number
	end: number
	transform: SectionPieceTransform
	needsSeat: boolean
}

/** Geometry fitting must never run on the UI thread, including on worker failure. */
export function startSectionSeating(
	entries: SeatingEntry[],
	onComplete: (transforms: (SectionPieceTransform | null)[]) => void,
	onUnavailable: () => void,
): () => void {
	let worker: Worker | undefined
	let timer: ReturnType<typeof setTimeout> | undefined
	let finished = false
	const cancel = () => {
		finished = true
		clearTimeout(timer)
		worker?.terminate()
	}
	const fail = () => {
		if (finished) return
		cancel()
		onUnavailable()
	}
	try {
		worker = new Worker(new URL('./sectionSeating.worker.ts', import.meta.url), { type: 'module' })
		worker.onmessage = (event: MessageEvent<(SectionPieceTransform | null)[]>) => {
			if (finished) return
			cancel()
			onComplete(event.data)
		}
		worker.onerror = fail
		worker.onmessageerror = fail
		// Bound background CPU usage too. The section remains editable at its
		// saved/default placement if an unusually complex outline exceeds this.
		timer = setTimeout(fail, 10000)
		// Vue's reactive proxies cannot be structured-cloned directly.
		worker.postMessage(JSON.parse(JSON.stringify(entries)))
	} catch {
		fail()
	}
	return cancel
}
