import { describe, expect, it } from 'vitest'
import w01 from './__fixtures__/w01.json'
import { layoutGeom } from './geometry'
import { MIN_CELL, getNode, moveSplit, newDesign, removeSplit, setLeaf, setSize, splitCell, validateDesign } from './tree'
import type { Design, DesignNode, SplitNode } from './types'

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

	it('rejects trees deeper than 32 nodes (engine MAX_DEPTH parity)', () => {
		const chain = (splits: number): Design => {
			let node: DesignNode = { type: 'fixed', glass: '6CTG' }
			for (let i = 0; i < splits; i++) node = { type: 'split', dir: 'v', at: [1], children: [{ type: 'fixed', glass: '6CTG' }, node] }
			return newDesign(100000, 100000, node)
		}
		// root is depth 1, so 31 splits + a leaf = depth 32 (ok); 32 splits + a leaf = depth 33 (too deep)
		expect(validateDesign(chain(31))).toBeNull()
		expect(validateDesign(chain(32))).toMatch(/depth exceeds 32/)
	})
})

describe('guards', () => {
	it('moveSplit ignores non-finite pos and returns the same object', () => {
		const d = w01 as Design
		for (const pos of [NaN, Infinity, -Infinity]) {
			const out = moveSplit(d, 'F1', 0, pos)
			expect(out).toBe(d)
			expect((out.root as SplitNode).at).toEqual([457.5])
		}
	})
	it('splitCell rejects count < 2', () => {
		expect(() => splitCell(base(), 'F1', 'v', 1)).toThrow('count must be an integer >= 2')
		for (const n of [2.5, NaN, Infinity]) expect(() => splitCell(base(), 'F1', 'v', n)).toThrow('count must be')
	})
	it('setSize rejects invalid sizes', () => {
		for (const [w, h] of [[0, 100], [100, -1], [NaN, 100], [100, Infinity]])
			expect(() => setSize(base(), w, h)).toThrow('invalid size')
	})
})

describe('moveSplit keeps nested splits valid', () => {
	const sq = () => newDesign(1200, 1200)
	const at = (d: Design, path: string) => (getNode(d, path) as SplitNode).at
	function expectSound(d: Design) {
		expect(validateDesign(d)).toBeNull()
		for (const c of layoutGeom(d).cells) {
			expect(c.w).toBeGreaterThanOrEqual(MIN_CELL)
			expect(c.h).toBeGreaterThanOrEqual(MIN_CELL)
		}
	}
	const extremes = (d: Design, path: string) => [0, -50, 1200, 5000].map((pos) => moveSplit(d, path, 0, pos))

	it('nested same-direction split on the left', () => {
		const d = splitCell(splitCell(sq(), 'F1', 'v'), 'F1.0', 'v')
		const moved = moveSplit(d, 'F1', 0, 200)
		expectSound(moved)
		expect(at(moved, 'F1')).toEqual([200])
		extremes(d, 'F1').forEach(expectSound)
		expect(at(moveSplit(d, 'F1', 0, 0), 'F1')).toEqual([200])
	})

	it('nested same-direction split on the right', () => {
		const d = splitCell(splitCell(sq(), 'F1', 'v'), 'F1.1', 'v', 3)
		extremes(d, 'F1').forEach(expectSound)
		expect(at(moveSplit(d, 'F1', 0, 1200), 'F1')).toEqual([900])
		const moved = moveSplit(d, 'F1', 0, 300)
		expectSound(moved)
		expect(at(moved, 'F1.1')).toEqual([300, 600])
	})

	it('nested cross-direction split needs only one cell of width', () => {
		let d = splitCell(splitCell(sq(), 'F1', 'v'), 'F1.0', 'h', 3)
		d = splitCell(d, 'F1.1', 'h')
		extremes(d, 'F1').forEach(expectSound)
		expect(at(moveSplit(d, 'F1', 0, 0), 'F1')).toEqual([100])
		expect(at(moveSplit(d, 'F1', 0, 0), 'F1.0')).toEqual(at(d, 'F1.0'))
	})

	it('cross split holding a same-direction split takes the max', () => {
		let d = splitCell(splitCell(sq(), 'F1', 'v'), 'F1.0', 'h')
		d = splitCell(d, 'F1.0.1', 'v', 3)
		extremes(d, 'F1').forEach(expectSound)
		expect(at(moveSplit(d, 'F1', 0, 0), 'F1')).toEqual([300])
	})

	it('middle bar of three with nested splits on both sides', () => {
		let d = splitCell(newDesign(1500, 1200), 'F1', 'v', 3)
		d = splitCell(splitCell(d, 'F1.0', 'v'), 'F1.1', 'v')
		for (const pos of [0, 2000]) expectSound(moveSplit(d, 'F1', 1, pos))
		for (const pos of [0, 2000]) expectSound(moveSplit(d, 'F1', 0, pos))
	})

	it('keeps 0.1 mm grid and >= 100 mm after an odd split', () => {
		const d = splitCell(splitCell(newDesign(1000, 1000), 'F1', 'v', 3), 'F1.2', 'v', 3)
		for (const pos of [0, 1000, 412.37]) {
			const m = moveSplit(d, 'F1', 1, pos)
			expectSound(m)
			for (const a of [...at(m, 'F1'), ...at(m, 'F1.2')]) expect(Math.round(a * 10) / 10).toBe(a)
		}
	})
})
