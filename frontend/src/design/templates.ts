import { newDesign } from './tree'
import type { Design, DesignNode, SectionPieceTransform } from './types'

export interface DesignTemplate {
	id: string
	label: string
	series?: string
	defaultW?: number
	defaultH?: number
	build(width: number, height: number): Design
}

// Same glass as the blank default in newDesign.
const GLASS = '6CTG'
const sash = (hinge: 'left' | 'right' | 'top' = 'left', mesh = false): DesignNode => ({
	type: 'sash',
	glass: GLASS,
	opening: 'out',
	hinge,
	ghh: 732,
	lock: 'multipoint',
	...(mesh ? { mesh: true } : {}),
})
const fixed = (): DesignNode => ({ type: 'fixed', glass: GLASS })
const split = (dir: 'v' | 'h', at: number[], children: DesignNode[]): DesignNode => ({
	type: 'split',
	dir,
	at: at.map((a) => Math.ceil(a - 0.5)), // whole mm, halves round down
	children,
})

export const CS400_SECTION_MAP: Record<string, SectionPieceTransform> = {
	'frame:E104156': { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false },
	'mullion:E104159': { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false },
	'transom:E104159': { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false },
	'sash:E104160': { offsetAlong: 0, offsetDepth: -11.5, rotation: 0, flipX: false, flipY: false },
	'bead:E104161': { offsetAlong: 0, offsetDepth: 23, rotation: 0, flipX: false, flipY: false },
	'bead:CS4807': { offsetAlong: 0, offsetDepth: 20, rotation: 0, flipX: false, flipY: false },
	'bead:CS4808': { offsetAlong: 0, offsetDepth: 20, rotation: 0, flipX: false, flipY: false },
	'bead:CS4809': { offsetAlong: 0, offsetDepth: 22, rotation: 0, flipX: false, flipY: false },
}

export const CS4800_SECTION_MAP: Record<string, SectionPieceTransform> = {
	'frame:CS4802': { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false },
	'mullion:CS4801': { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false },
	'transom:CS4801': { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false },
	'sash:CS4803': { offsetAlong: 0, offsetDepth: -12, rotation: 0, flipX: false, flipY: false },
	'sash:CS4804': { offsetAlong: 0, offsetDepth: -12, rotation: 0, flipX: false, flipY: false },
	'bead:CS4807': { offsetAlong: 0, offsetDepth: 20, rotation: 0, flipX: false, flipY: false },
	'bead:CS4808': { offsetAlong: 0, offsetDepth: 20, rotation: 0, flipX: false, flipY: false },
	'bead:CS4809': { offsetAlong: 0, offsetDepth: 22, rotation: 0, flipX: false, flipY: false },
}

function cs400Design(w: number, h: number, root: DesignNode, withBead = true): Design {
	return {
		...newDesign(w, h, root),
		...(withBead ? { beadProfileId: 'E104161' } : {}),
		sectionMap: { ...CS400_SECTION_MAP },
	}
}

function cs4800Design(w: number, h: number, root: DesignNode, withBead = true): Design {
	return {
		...newDesign(w, h, root),
		...(withBead ? { beadProfileId: 'CS4808' } : {}),
		sectionMap: { ...CS4800_SECTION_MAP },
	}
}

export const TEMPLATES: DesignTemplate[] = [
	// ─── CS400 SERIES (6 TEMPLATES) ──────────────────────────────────
	{
		id: 'cs400-fixed',
		label: 'Fixed window',
		series: 'CS400',
		defaultW: 915,
		defaultH: 1220,
		build: (w, h) => cs400Design(w, h, fixed(), true),
	},
	{
		id: 'cs400-fixmull',
		label: 'Fixed with mullion',
		series: 'CS400',
		defaultW: 1220,
		defaultH: 1220,
		build: (w, h) => cs400Design(w, h, split('v', [w / 2], [fixed(), fixed()]), true),
	},
	{
		id: 'cs400-single',
		label: 'Single open',
		series: 'CS400',
		defaultW: 915,
		defaultH: 1220,
		build: (w, h) => cs400Design(w, h, sash('left'), false),
	},
	{
		id: 'cs400-double',
		label: 'Double open',
		series: 'CS400',
		defaultW: 1220,
		defaultH: 1220,
		build: (w, h) => cs400Design(w, h, split('v', [w / 2], [sash('left'), sash('right')]), false),
	},
	{
		id: 'cs400-triple',
		label: 'Triple open',
		series: 'CS400',
		defaultW: 1830,
		defaultH: 1220,
		build: (w, h) =>
			cs400Design(w, h, split('v', [w / 3, (2 * w) / 3], [sash('left'), sash('left'), sash('right')]), false),
	},
	{
		id: 'cs400-dcf',
		label: 'Double open cum fixed',
		series: 'CS400',
		defaultW: 1220,
		defaultH: 1520,
		build: (w, h) => {
			const splitPos = h - 450 > 300 ? h - 450 : h * 0.7
			return cs400Design(
				w,
				h,
				split('h', [splitPos], [split('v', [w / 2], [sash('left'), sash('right')]), fixed()]),
				true,
			)
		},
	},

	// ─── CS4800 SERIES (11 TEMPLATES) ─────────────────────────────────
	{
		id: 'cs4800-fixed',
		label: 'Fixed window',
		series: 'CS4800',
		defaultW: 1200,
		defaultH: 1200,
		build: (w, h) => cs4800Design(w, h, fixed(), true),
	},
	{
		id: 'cs4800-fixmull',
		label: 'Fixed with center mullion',
		series: 'CS4800',
		defaultW: 1200,
		defaultH: 1200,
		build: (w, h) => cs4800Design(w, h, split('v', [w / 2], [fixed(), fixed()]), true),
	},
	{
		id: 'cs4800-single',
		label: 'Single open / Top hung',
		series: 'CS4800',
		defaultW: 900,
		defaultH: 1200,
		build: (w, h) => cs4800Design(w, h, sash('left'), false),
	},
	{
		id: 'cs4800-double',
		label: 'Double open window',
		series: 'CS4800',
		defaultW: 1200,
		defaultH: 1200,
		build: (w, h) => cs4800Design(w, h, split('v', [w / 2], [sash('left'), sash('right')]), false),
	},
	{
		id: 'cs4800-triple',
		label: 'Triple open window',
		series: 'CS4800',
		defaultW: 1800,
		defaultH: 1200,
		build: (w, h) =>
			cs4800Design(w, h, split('v', [w / 3, (2 * w) / 3], [sash('left'), sash('left'), sash('right')]), false),
	},
	{
		id: 'cs4800-single-mesh',
		label: 'Single open with grill & mesh',
		series: 'CS4800',
		defaultW: 900,
		defaultH: 1200,
		build: (w, h) => cs4800Design(w, h, sash('left', true), false),
	},
	{
		id: 'cs4800-double-mesh',
		label: 'Double open with grill & mesh',
		series: 'CS4800',
		defaultW: 1200,
		defaultH: 1200,
		build: (w, h) => cs4800Design(w, h, split('v', [w / 2], [sash('left', true), sash('right', true)]), false),
	},
	{
		id: 'cs4800-door-single',
		label: 'Casement door single open',
		series: 'CS4800',
		defaultW: 900,
		defaultH: 2100,
		build: (w, h) => cs4800Design(w, h, sash('left'), false),
	},
	{
		id: 'cs4800-door-single-thresh',
		label: 'Single door with threshold',
		series: 'CS4800',
		defaultW: 900,
		defaultH: 2100,
		build: (w, h) => cs4800Design(w, h, sash('left'), false),
	},
	{
		id: 'cs4800-door-double',
		label: 'Casement double door',
		series: 'CS4800',
		defaultW: 1800,
		defaultH: 2100,
		build: (w, h) => cs4800Design(w, h, split('v', [w / 2], [sash('left'), sash('right')]), false),
	},
	{
		id: 'cs4800-door-dcf',
		label: 'Double door cum fixed',
		series: 'CS4800',
		defaultW: 1800,
		defaultH: 2400,
		build: (w, h) => {
			const splitPos = h - 500 > 500 ? h - 500 : h * 0.75
			return cs4800Design(
				w,
				h,
				split('h', [splitPos], [split('v', [w / 2], [sash('left'), sash('right')]), fixed()]),
				true,
			)
		},
	},

	// ─── GENERIC TEMPLATES (WORKSPACE & STANDARD) ─────────────────────
	{
		id: 'casement-2',
		label: '2-sash casement',
		defaultW: 1220,
		defaultH: 1220,
		build: (w, h) => newDesign(w, h, split('v', [w / 2], [sash('left'), sash('right')])),
	},
	{
		id: 'ventilator',
		label: 'Ventilator',
		defaultW: 1200,
		defaultH: 1200,
		build: (w, h) =>
			newDesign(w, h, split('v', [w * 0.7], [{ type: 'louver', glass: GLASS, blades: 7 }, fixed()])),
	},
	{
		id: 'sash-fixed-sash',
		label: 'Sash · fixed · sash',
		defaultW: 1200,
		defaultH: 1200,
		build: (w, h) => newDesign(w, h, split('v', [w / 3, (2 * w) / 3], [sash('left'), fixed(), sash('right')])),
	},
	{
		id: 'top-light',
		label: 'Top light',
		defaultW: 1200,
		defaultH: 1200,
		build: (w, h) => newDesign(w, h, split('h', [h * 0.25], [fixed(), sash('top')])),
	},
	{ id: 'blank', label: 'Blank', build: (w, h) => newDesign(w, h) },
]
