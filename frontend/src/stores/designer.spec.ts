import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { newDesign, splitCell } from '@/design/tree'
import { useDesignerStore } from './designer'

describe('designer store', () => {
	beforeEach(() => setActivePinia(createPinia()))

	it('apply, undo, redo', () => {
		const s = useDesignerStore()
		s.design = newDesign(915, 1220)
		const first = s.design
		s.apply((d) => splitCell(d, 'F1', 'v'))
		expect(s.design.root.type).toBe('split')
		s.undo()
		expect(s.design).toEqual(first)
		s.redo()
		expect(s.design.root.type).toBe('split')
	})

	it('new apply clears future', () => {
		const s = useDesignerStore()
		s.apply((d) => splitCell(d, 'F1', 'v'))
		s.undo()
		s.apply((d) => ({ ...d, width: 1000 }))
		expect(s.future).toHaveLength(0)
	})

	it('no-op apply does not push history', () => {
		const s = useDesignerStore()
		s.apply((d) => d)
		expect(s.past).toHaveLength(0)
	})

	it('caps history at 50', () => {
		const s = useDesignerStore()
		for (let i = 0; i < 60; i++) s.apply((d) => ({ ...d, width: 500 + i }))
		expect(s.past).toHaveLength(50)
	})

	it('select sets selectedPath', () => {
		const s = useDesignerStore()
		s.select('F1.0')
		expect(s.selectedPath).toBe('F1.0')
	})
})
