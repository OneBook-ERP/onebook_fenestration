import { describe, expect, it } from 'vitest'
import { applyGlassDomainDrag, fitGlassInDomain, glassDomainFromPiece, suggestInitialGlassDomain } from './glassDomain'
import type { SectionGlassDomain } from '@/studio/api'

describe('glassDomain', () => {
	const domain: SectionGlassDomain = {
		configured: true,
		minY: 10,
		maxY: 34,
		insetLow: -6,
		insetHigh: -6,
		align: 'center',
	}

	it('keeps any fitting glass thickness strictly inside domain boundaries across center/top/bottom alignments', () => {
		for (const thickness of [5, 6, 8, 12, 18, 24]) {
			for (const align of ['center', 'top', 'bottom'] as const) {
				const fit = fitGlassInDomain(100, 300, thickness, { ...domain, align })
				expect(fit.exceedsDomain).toBe(false)
				expect(fit.y).toBeGreaterThanOrEqual(domain.minY - 1e-6)
				expect(fit.y + fit.depth).toBeLessThanOrEqual(domain.maxY + 1e-6)
				expect(fit.x).toBe(94)
				expect(fit.w).toBe(212)
				expect(fit.offsetDepth).toBeCloseTo(fit.y + thickness / 2, 1)
			}
		}
	})

	it('anchors flush to outer/inner stop when align is top or bottom', () => {
		const top6 = fitGlassInDomain(100, 300, 6, { ...domain, align: 'top' })
		expect(top6.y).toBe(10)
		expect(top6.offsetDepth).toBe(13)

		const top24 = fitGlassInDomain(100, 300, 24, { ...domain, align: 'top' })
		expect(top24.y).toBe(10)
		expect(top24.y + top24.depth).toBe(34)

		const bot6 = fitGlassInDomain(100, 300, 6, { ...domain, align: 'bottom' })
		expect(bot6.y).toBe(28)
		expect(bot6.y + bot6.depth).toBe(34)
	})

	it('flags exceedsDomain when glass thickness is larger than domain height', () => {
		const fit = fitGlassInDomain(100, 300, 32, domain)
		expect(fit.exceedsDomain).toBe(true)
		expect(fit.offsetDepth).toBe(22) // centered at (10+34)/2
	})

	it('supports mirrored and asymmetric edge dragging without inverting domain', () => {
		const mirrored = applyGlassDomainDrag(domain, 'w', 3, 0, 200, true)
		expect(mirrored.insetLow).toBe(-3)
		expect(mirrored.insetHigh).toBe(-3)

		const asym = applyGlassDomainDrag(domain, 'e', -4, 0, 200, false)
		expect(asym.insetLow).toBe(-6)
		expect(asym.insetHigh).toBe(-2)

		const clampedTop = applyGlassDomainDrag(domain, 'n', 0, 100, 200, true)
		expect(clampedTop.minY).toBeLessThan(clampedTop.maxY)
		expect(clampedTop.maxY - clampedTop.minY).toBeGreaterThanOrEqual(2)
	})

	it('extracts glass domain from backend config_placement and suggests a sensible initial domain', () => {
		const parsed = glassDomainFromPiece({
			kind: 'glass',
			code: '6CTG',
			role: 'glass',
			panel: 'F1',
			start: 40,
			end: 1160,
			mirrored: false,
			thickness: 6,
			config_placement: {
				source: 'series_section_template_glass_domain',
				minY: 8,
				maxY: 30,
				insetLow: -4,
				insetHigh: -2,
				align: 'top',
			},
		})
		expect(parsed).toEqual({
			configured: true,
			minY: 8,
			maxY: 30,
			insetLow: -4,
			insetHigh: -2,
			align: 'top',
		})

		const suggested = suggestInitialGlassDomain([
			{
				index: 0,
				piece: { kind: 'profile', code: 'E104160', role: 'sash', panel: 'F1-S1', start: 0, end: 64, mirrored: false, thickness: 0 },
				rings: [],
				bbox: { minX: 0, minY: 0, maxX: 64, maxY: 40, width: 64, height: 40 },
				labelPos: { x: 32, y: 20 },
			},
		])
		expect(suggested.configured).toBe(true)
		expect(suggested.minY).toBeGreaterThan(0)
		expect(suggested.maxY).toBeLessThan(40)
	})
})

