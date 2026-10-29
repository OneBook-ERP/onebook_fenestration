import { defineStore } from 'pinia'
import { computeDesign, type ComputeResult } from '@/api'
import { getNode, newDesign, validateDesign } from '@/design/tree'
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
		finish: '' as string,
		priceStructure: '' as string,
		error: null as string | null,
		computing: false,
		requestSeq: 0,
		dirty: false,
		dragOrigin: null as Design | null,
	}),
	actions: {
		apply(fn: (d: Design) => Design) {
			const next = fn(this.design)
			if (next === this.design) return
			this.pushHistory(this.design)
			this.setDesign(next)
		},
		/** Start a drag: later dragTo calls skip history and endDrag records one undo step. */
		beginDrag() {
			this.dragOrigin = JSON.parse(JSON.stringify(this.design))
		},
		dragTo(fn: (d: Design) => Design) {
			if (!this.dragOrigin) return this.apply(fn)
			const next = fn(this.design)
			if (next !== this.design) this.setDesign(next)
		},
		endDrag() {
			const origin = this.dragOrigin
			this.dragOrigin = null
			if (origin && JSON.stringify(origin) !== JSON.stringify(this.design)) this.pushHistory(origin)
		},
		markDirty() {
			this.dirty = true
		},
		markSaved() {
			this.dirty = false
		},
		pushHistory(design: Design) {
			this.past.push(design)
			if (this.past.length > HISTORY_CAP) this.past.shift()
			this.future = []
		},
		setDesign(design: Design) {
			this.design = design
			this.dirty = true
			this.scheduleCompute()
		},
		undo() {
			const prev = this.past.pop()
			if (!prev) return
			this.future.push(this.design)
			this.setDesign(prev)
			this.keepSelection()
		},
		redo() {
			const next = this.future.pop()
			if (!next) return
			this.past.push(this.design)
			this.setDesign(next)
			this.keepSelection()
		},
		/** After undo/redo the selected node may be gone: select its nearest existing ancestor. */
		keepSelection() {
			let path = this.selectedPath
			while (path.includes('.') && !hasNode(this.design, path)) path = path.slice(0, path.lastIndexOf('.'))
			this.selectedPath = path
		},
		select(path: string) {
			this.selectedPath = path
		},
		setFinish(finish: string) {
			if (finish === this.finish) return
			this.finish = finish
			this.dirty = true
			this.scheduleCompute()
		},
		reset(design: Design, seriesVersion: string, finish = '', priceStructure = '') {
			this.$patch({ design, seriesVersion, finish, priceStructure, selectedPath: 'F1', past: [], future: [], result: null, error: null, dirty: false, dragOrigin: null })
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
				res = await computeDesign(this.design, this.seriesVersion, this.finish, this.priceStructure)
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

function hasNode(design: Design, path: string): boolean {
	try {
		getNode(design, path)
		return true
	} catch {
		return false
	}
}
