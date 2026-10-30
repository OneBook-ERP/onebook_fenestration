import { newDesign } from './tree'
import type { Design, DesignNode } from './types'

export interface DesignTemplate {
	id: string
	label: string
	build(width: number, height: number): Design
}

// Same glass as the blank default in newDesign.
const GLASS = '6CTG'
const sash = (): DesignNode => ({ type: 'sash', glass: GLASS })
const fixed = (): DesignNode => ({ type: 'fixed', glass: GLASS })
const split = (dir: 'v' | 'h', at: number[], children: DesignNode[]): DesignNode => ({
	type: 'split',
	dir,
	at: at.map((a) => Math.ceil(a - 0.5)), // whole mm, halves round down
	children,
})

export const TEMPLATES: DesignTemplate[] = [
	{
		id: 'casement-2',
		label: '2-sash casement',
		build: (w, h) => newDesign(w, h, split('v', [w / 2], [sash(), sash()])),
	},
	{
		id: 'ventilator',
		label: 'Ventilator',
		build: (w, h) =>
			newDesign(w, h, split('v', [w * 0.7], [{ type: 'louver', glass: GLASS, blades: 7 }, fixed()])),
	},
	{
		id: 'sash-fixed-sash',
		label: 'Sash · fixed · sash',
		build: (w, h) => newDesign(w, h, split('v', [w / 3, (2 * w) / 3], [sash(), fixed(), sash()])),
	},
	{
		id: 'top-light',
		label: 'Top light',
		build: (w, h) => newDesign(w, h, split('h', [h * 0.25], [fixed(), sash()])),
	},
	{ id: 'blank', label: 'Blank', build: (w, h) => newDesign(w, h) },
]
