import { describe, expect, it } from 'vitest'
import w01 from './__fixtures__/w01.json'
import { MIN_CELL, getNode, moveSplit, newDesign, removeSplit, setLeaf, setSize, splitCell, validateDesign } from './tree'
import type { Design, SplitNode } from './types'

const base = () => newDesign(915, 1220)

describe('tree', () => {
	it('newDesign defaults to a fixed 6CTG root', () => {
		expect(base().root).toEqual({ type: 'fixed', glass: '6CTG' })
	})

	it('splitCell v gives at [457.5] and two copies', () => {
		const d = splitCell(base(), 'F1', 'v')
		const root = d.root as SplitNode
		expect(root.at).toEqual([457.5])
		expect(root.children).toHaveLength(2)
		expect(root.children[0]).toEqual({ type: 'fixed', glass: '6CTG' })
	})

	it('splitCell does not mutate the input', () => {
		const d = base()
		splitCell(d, 'F1', 'v')
		expect(d.root.type).toBe('fixed')
	})

	it('splitCell into 3 rounds to 0.1 mm', () => {
		const root = splitCell(base(), 'F1', 'v', 3).root as SplitNode
		expect(root.at).toEqual([305, 610])
	})

	it('splitCell on a split throws', () => {
		const d = splitCell(base(), 'F1', 'v')
		expect(() => splitCell(d, 'F1', 'h')).toThrow('not a leaf: F1')
	})

	it('getNode throws on a bad path', () => {
		expect(() => getNode(base(), 'F1.3')).toThrow('no node at F1.3')
	})

	it('moveSplit clamps to MIN_CELL', () => {
		const d = splitCell(base(), 'F1', 'v')
		expect(((moveSplit(d, 'F1', 0, 5).root) as SplitNode).at).toEqual([MIN_CELL])
		expect(((moveSplit(d, 'F1', 0, 900).root) as SplitNode).at).toEqual([815])
		expect(((moveSplit(d, 'F1', 0, 300).root) as SplitNode).at).toEqual([300])
	})

	it('removeSplit keeps the first child', () => {
		const d = setLeaf(splitCell(base(), 'F1', 'v'), 'F1.0', { type: 'sash', glass: '4' })
		expect(removeSplit(d, 'F1').root).toEqual({ type: 'sash', glass: '4' })
	})

	it('setLeaf replaces a leaf', () => {
		const d = setLeaf(base(), 'F1', { type: 'louver', glass: '6', blades: 5 })
		expect(d.root).toEqual({ type: 'louver', glass: '6', blades: 5 })
	})

	it('setSize doubles at', () => {
		const d = setSize(splitCell(base(), 'F1', 'v'), 1830, 1220)
		expect(d.width).toBe(1830)
		expect((d.root as SplitNode).at).toEqual([915])
	})

	it('setSize scales nested splits against their own cell', () => {
		let d = splitCell(base(), 'F1', 'v') // cells 457.5 wide
		d = splitCell(d, 'F1.0', 'h') // at [610] of height 1220
		d = setSize(d, 1830, 610)
		const root = d.root as SplitNode
		expect(root.at).toEqual([915])
		expect((root.children[0] as SplitNode).at).toEqual([305])
	})

	it('setSize clamps so cells stay >= MIN_CELL', () => {
		const d = setSize(moveSplit(splitCell(base(), 'F1', 'v'), 'F1', 0, 200), 400, 1220)
		expect((d.root as SplitNode).at).toEqual([100])
	})

	it('setSize leaves equal division when impossible', () => {
		const d = setSize(splitCell(base(), 'F1', 'v', 3), 250, 1220)
		const at = (d.root as SplitNode).at
		expect(at[0]).toBeCloseTo(250 / 3, 0)
		expect(at[1]).toBeCloseTo(500 / 3, 0)
	})
})

describe('validateDesign', () => {
	it('accepts W01', () => {
		expect(validateDesign(w01 as Design)).toBeNull()
	})
	it('rejects at [0]', () => {
		const d = splitCell(base(), 'F1', 'v')
		;(d.root as SplitNode).at = [0]
		expect(validateDesign(d)).not.toBeNull()
	})
	it('rejects unknown types', () => {
		const d = { width: 10, height: 10, root: { type: 'wat' } } as unknown as Design
		expect(validateDesign(d)).toMatch(/unknown/)
	})
	it('rejects bad size, at length, and non-string glass', () => {
		expect(validateDesign({ ...base(), width: 0 })).not.toBeNull()
		const d = splitCell(base(), 'F1', 'v')
		;(d.root as SplitNode).at = [100, 200]
		expect(validateDesign(d)).not.toBeNull()
		expect(validateDesign({ width: 10, height: 10, root: { type: 'fixed', glass: 5 } } as unknown as Design)).not.toBeNull()
	})
})
