import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { moveSplit, newDesign, splitCell } from '@/design/tree'
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
	it('a drag is one undo step', () => {
		const s = useDesignerStore()
		s.apply((d) => splitCell(d, 'F1', 'v'))
		const before = s.design
		const depth = s.past.length
		s.beginDrag()
		for (let i = 1; i <= 10; i++) s.dragTo((d) => moveSplit(d, 'F1', 0, 400 + i * 10))
		s.endDrag()
		expect(s.past).toHaveLength(depth + 1)
		s.undo()
		expect(s.design).toEqual(before)
	})

	it('a drag that changes nothing adds no undo step', () => {
		const s = useDesignerStore()
		s.beginDrag()
		s.endDrag()
		expect(s.past).toHaveLength(0)
	})

	it('dirty is set by edits and cleared by reset and markSaved', () => {
		const s = useDesignerStore()
		expect(s.dirty).toBe(false)
		s.apply((d) => splitCell(d, 'F1', 'v'))
		expect(s.dirty).toBe(true)
		s.markSaved()
		expect(s.dirty).toBe(false)
		s.beginDrag()
		s.dragTo((d) => moveSplit(d, 'F1', 0, 300))
		s.endDrag()
		expect(s.dirty).toBe(true)
		s.reset(newDesign(900, 900), 'SV1')
		expect(s.dirty).toBe(false)
	})
})
