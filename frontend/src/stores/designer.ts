import { defineStore } from 'pinia'
import { newDesign } from '@/design/tree'
import type { Design } from '@/design/types'

export const HISTORY_CAP = 50

export const useDesignerStore = defineStore('designer', {
	state: () => ({
		design: newDesign(915, 1220) as Design,
		selectedPath: 'F1' as string,
		past: [] as Design[],
		future: [] as Design[],
		result: null as unknown,
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
		},
		undo() {
			const prev = this.past.pop()
			if (!prev) return
			this.future.push(this.design)
			this.design = prev
		},
		redo() {
			const next = this.future.pop()
			if (!next) return
			this.past.push(this.design)
			this.design = next
		},
		select(path: string) {
			this.selectedPath = path
		},
	},
})
