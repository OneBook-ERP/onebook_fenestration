import { defineStore } from 'pinia'
import { computeDesign, type ComputeResult } from '@/api'
import { newDesign, validateDesign } from '@/design/tree'
import type { Design } from '@/design/types'

export const HISTORY_CAP = 50
export const COMPUTE_DEBOUNCE_MS = 300

let timer: ReturnType<typeof setTimeout> | undefined

export const useDesignerStore = defineStore('designer', {
	state: () => ({
		design: newDesign(915, 1220) as Design,
		selectedPath: 'F1' as string,
		past: [] as Design[],
		future: [] as Design[],
		result: null as ComputeResult | null,
		seriesVersion: '',
		error: null as string | null,
		computing: false,
		requestSeq: 0,
	}),
	actions: {
		apply(fn: (d: Design) => Design) {
			const next = fn(this.design)
			if (next === this.design) return
			this.past.push(this.design)
			if (this.past.length > HISTORY_CAP) this.past.shift()
			this.future = []
			this.design = next
			this.scheduleCompute()
		},
		undo() {
			const prev = this.past.pop()
			if (!prev) return
			this.future.push(this.design)
			this.design = prev
			this.scheduleCompute()
		},
		redo() {
			const next = this.future.pop()
			if (!next) return
			this.past.push(this.design)
			this.design = next
			this.scheduleCompute()
		},
		select(path: string) {
			this.selectedPath = path
		},
		reset(design: Design, seriesVersion: string) {
			this.$patch({ design, seriesVersion, selectedPath: 'F1', past: [], future: [], result: null, error: null })
			this.scheduleCompute()
		},
		cancelCompute() {
			clearTimeout(timer)
			this.requestSeq += 1
			this.computing = false
		},
		scheduleCompute() {
			clearTimeout(timer)
			this.requestSeq += 1
			const invalid = validateDesign(this.design)
			if (invalid) {
				this.error = invalid
				this.computing = false
				return
			}
			timer = setTimeout(() => this.runCompute(), COMPUTE_DEBOUNCE_MS)
		},
		async runCompute() {
			const seq = this.requestSeq
			this.computing = true
			let res
			try {
				res = await computeDesign(this.design, this.seriesVersion)
			} catch (e) {
				res = { ok: false as const, message: e instanceof Error ? e.message : String(e) }
			}
			if (seq !== this.requestSeq) return
			this.computing = false
			if (res.ok) {
				this.result = res.result
				this.error = null
			} else {
				this.error = res.message
			}
		},
	},
})
