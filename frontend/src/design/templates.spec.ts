import { describe, expect, it } from 'vitest'
import { TEMPLATES } from './templates'
import type { DesignNode } from './types'

const leaves = (n: DesignNode): number => (n.type === 'split' ? n.children.reduce((a, c) => a + leaves(c), 0) : 1)
const tpl = (id: string) => TEMPLATES.find((t) => t.id === id)!

describe('TEMPLATES', () => {
	it('builds valid trees with the expected leaf counts', () => {
		const counts = Object.fromEntries(TEMPLATES.map((t) => [t.id, leaves(t.build(1200, 1200).root)]))
		expect(counts).toEqual({
			'cs400-fixed': 1,
			'cs400-fixmull': 2,
			'cs400-single': 1,
			'cs400-double': 2,
			'cs400-triple': 3,
			'cs400-dcf': 3,
			'cs4800-fixed': 1,
			'cs4800-fixmull': 2,
			'cs4800-single': 1,
			'cs4800-double': 2,
			'cs4800-triple': 3,
			'cs4800-single-mesh': 1,
			'cs4800-double-mesh': 2,
			'cs4800-door-single': 1,
			'cs4800-door-single-thresh': 1,
			'cs4800-door-double': 2,
			'cs4800-door-dcf': 3,
			'casement-2': 2,
			ventilator: 2,
			'sash-fixed-sash': 3,
			'top-light': 2,
			blank: 1,
		})
		for (const t of TEMPLATES) {
			const d = t.build(900, 1000)
			expect([d.width, d.height]).toEqual([900, 1000])
			const check = (n: DesignNode) => {
				if (n.type === 'split') {
					expect(n.children).toHaveLength(n.at.length + 1)
					n.children.forEach(check)
				}
			}
			check(d.root)
		}
	})

	it('rounds split positions to whole mm', () => {
		const root = tpl('casement-2').build(915, 1220).root
		expect(root.type === 'split' && root.at).toEqual([457])
	})

	it('places ventilator, thirds and top-light splits', () => {
		const v = tpl('ventilator').build(1000, 1200).root
		expect(v).toMatchObject({ type: 'split', dir: 'v', at: [700] })
		expect(v.type === 'split' && v.children[0]).toMatchObject({ type: 'louver', blades: 7 })
		expect(tpl('sash-fixed-sash').build(1200, 1200).root).toMatchObject({ dir: 'v', at: [400, 800] })
		const t = tpl('top-light').build(1000, 1200).root
		expect(t).toMatchObject({ dir: 'h', at: [300] })
		expect(t.type === 'split' && t.children.map((c) => c.type)).toEqual(['fixed', 'sash'])
	})
})
