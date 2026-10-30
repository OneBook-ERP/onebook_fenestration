import { describe, expect, it } from 'vitest'
import { panelLabel, typology } from '@/design/typology'
import type { DesignNode } from '@/design/types'

const sash: DesignNode = { type: 'sash', glass: 'G' }
const fixed: DesignNode = { type: 'fixed', glass: 'G' }
const louver: DesignNode = { type: 'louver', glass: 'G', blades: 9 }
const split = (...children: DesignNode[]): DesignNode => ({ type: 'split', dir: 'v', at: [1], children })

describe('typology', () => {
	it('typology fixed only', () => {
		expect(typology(fixed)).toBe('Fixed')
		expect(typology(split(fixed, fixed))).toBe('Fixed')
	})
	it('a lone sash is Casement', () => expect(typology(sash)).toBe('Casement'))
	it('all sash is n-sash casement', () => expect(typology(split(sash, sash))).toBe('2-sash casement'))
	it('mixed joins the unique kinds', () => expect(typology(split(sash, fixed))).toBe('Casement + fixed'))
	it('any louver is Ventilator', () => expect(typology(split(sash, louver))).toBe('Ventilator'))
	it('reads nested trees', () => {
		expect(typology(split(sash, split(fixed, sash)))).toBe('Casement + fixed')
	})
})

describe('panel label', () => {
	const result = {
		members: [{ panel: 'F1-S1', path: 'F1.0' }],
		glass: [{ panel: 'F1-S2', path: 'F1.1' }],
	} as never
	it('uses the member panel id', () => expect(panelLabel('F1.0', result)).toBe('F1-S1'))
	it('falls back to a glass row', () => expect(panelLabel('F1.1', result)).toBe('F1-S2'))
	it('falls back to the path', () => {
		expect(panelLabel('F1.2', result)).toBe('F1.2')
		expect(panelLabel('F1.2', null)).toBe('F1.2')
	})
})
