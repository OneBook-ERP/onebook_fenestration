import { describe, expect, it } from 'vitest'
import { resolveGlazingByWidth } from './glazingSolver'

const GASKETS = [
	{ name: 'G22', hardware_code: 'G22', hardware_name: 'Gasket 2mm', category: 'Gasket', item: 'G22', thickness_mm: 2 },
	{ name: 'G23', hardware_code: 'G23', hardware_name: 'Gasket 3mm', category: 'Gasket', item: 'G23', thickness_mm: 3 },
	{ name: 'G24', hardware_code: 'G24', hardware_name: 'Gasket 4mm', category: 'Gasket', item: 'G24', thickness_mm: 4 },
	{ name: 'G25', hardware_code: 'G25', hardware_name: 'Gasket 5mm', category: 'Gasket', item: 'G25', thickness_mm: 5 },
]

const AUTO_CFG = {
	enabled: true,
	max_compression_mm: 1.0,
	loose_tolerance_mm: 0.05,
	thicker_gasket_side: 'outer' as const,
	gasket_pool: [],
	channels: [
		{
			id: 'ch_12',
			series: 'CS4800',
			label: '5-8mm Bead',
			profile_type: 'both' as const,
			host: 'both' as const,
			bead_profile: 'HSL3409',
			no_bead: false,
			bead_width_mm: 12.01,
			bead_side: 'inside' as const,
		},
		{
			id: 'ch_18',
			series: 'CS4800',
			label: '12-15mm Bead',
			profile_type: 'both' as const,
			host: 'both' as const,
			bead_profile: 'HSL3410',
			no_bead: false,
			bead_width_mm: 18.01,
			bead_side: 'inside' as const,
		},
		{
			id: 'ch_28',
			series: 'CS4800',
			label: 'Sash Pocket (No Bead)',
			profile_type: 'both' as const,
			host: 'both' as const,
			bead_profile: '',
			no_bead: true,
			bead_width_mm: 28.0,
			bead_side: 'inside' as const,
		},
	],
}

describe('resolveGlazingByWidth (BW - GT = R)', () => {
	it('matches all notebook bead/pocket and gasket combinations with thicker gasket on outer', () => {
		const cases: Array<[number, string, boolean, number, number]> = [
			[5, 'HSL3409', false, 4, 3],
			[6, 'HSL3409', false, 3, 3],
			[8, 'HSL3409', false, 2, 2],
			[12, 'HSL3410', false, 3, 3],
			[13, 'HSL3410', false, 3, 2],
			[13.5, 'HSL3410', false, 3, 2], // 4.51 -> rejects 2+2 (loose) and picks 3+2 (+0.49mm tight)
			[15, 'HSL3410', false, 2, 2], // 3.01 -> picks 2+2 (+0.99mm tight <= 1mm)
			[24, '', true, 2, 2], // No Bead 28mm sash pocket -> 4mm -> 2+2
		]

		for (const [gt, expectedBead, expectedNoBead, expectedOuter, expectedInner] of cases) {
			const res = resolveGlazingByWidth(AUTO_CFG, GASKETS, gt, 'CS4800', 'frame', 'window')
			expect(res, `GT=${gt}`).not.toBeNull()
			expect(res!.ok, `GT=${gt}`).toBe(true)
			if (res && res.ok) {
				expect(res.bead_profile, `GT=${gt} bead`).toBe(expectedBead)
				expect(res.no_bead, `GT=${gt} no_bead`).toBe(expectedNoBead)
				expect(res.outer_gasket_mm, `GT=${gt} outer`).toBe(expectedOuter)
				expect(res.inner_gasket_mm, `GT=${gt} inner`).toBe(expectedInner)
			}
		}
	})

	it('rejects combinations exceeding 1mm compression or leaving loose fit, and enforces no-bead on window sashes', () => {
		const tight = resolveGlazingByWidth(AUTO_CFG, GASKETS, 26, 'CS4800', 'frame', 'window')
		expect(tight?.ok).toBe(false)

		const tooThick = resolveGlazingByWidth(AUTO_CFG, GASKETS, 29, 'CS4800', 'frame', 'window')
		expect(tooThick?.ok).toBe(false)
		if (tooThick && !tooThick.ok) {
			expect(tooThick.reason).toBe('exceeds_max_bw')
		}

		// Window sash skips beaded channels and only uses No Bead pocket channels
		const winSash = resolveGlazingByWidth(AUTO_CFG, GASKETS, 24, 'CS4800', 'sash', 'window')
		expect(winSash?.ok).toBe(true)
		if (winSash && winSash.ok) {
			expect(winSash.no_bead).toBe(true)
			expect(winSash.bead_width_mm).toBe(28)
		}

		// Different series with no default fallback returns null
		expect(resolveGlazingByWidth(AUTO_CFG, GASKETS, 6, 'CS400', 'frame', 'window')).toBeNull()
	})
})

