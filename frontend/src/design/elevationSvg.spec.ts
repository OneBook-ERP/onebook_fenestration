import { describe, expect, it } from 'vitest'
import { generateElevationSvg } from './elevationSvg'
import type { Design } from './types'

describe('generateElevationSvg', () => {
	it('generates svg for fixed window', () => {
		const design: Design = {
			width: 1200,
			height: 1200,
			root: { type: 'fixed', glass: '6CTG' },
		}
		const svg = generateElevationSvg(design)
		expect(svg).toContain('<svg')
		expect(svg).toContain('</svg>')
		expect(svg).toContain('viewBox="0 0 640 760"')
		expect(svg).toContain('>1200<')
		expect(svg).toContain('#DCEBF7')
	})

	it('generates svg for 2-sash split window with swing lines', () => {
		const design: Design = {
			width: 915,
			height: 1220,
			root: {
				type: 'split',
				dir: 'v',
				at: [457.5],
				children: [
					{ type: 'sash', glass: '6CTG', hinge: 'right' },
					{ type: 'sash', glass: '6CTG', hinge: 'left' },
				],
			},
		}
		const svg = generateElevationSvg(design, '#3B82F6')
		expect(svg).toContain('<svg')
		expect(svg).toContain('#3B82F6')
		expect(svg).toContain('stroke-dasharray="6 4"')
		expect(svg).toContain('>915<')
		expect(svg).toContain('>1220<')
	})

	it('returns empty string for invalid designs', () => {
		expect(generateElevationSvg({ width: 0, height: 100, root: { type: 'fixed', glass: '' } })).toBe('')
		expect(generateElevationSvg({ width: 100, height: 0, root: { type: 'fixed', glass: '' } })).toBe('')
	})
})

