import { describe, expect, it } from 'vitest'
import {
	buildTemplateDesign,
	extractAxisTemplateData,
	SECTION_TEMPLATE_LIST,
	stripGlassFromSectionMap,
} from './sectionTemplates'

describe('sectionTemplates', () => {
	it('builds valid synthetic designs for fixed, openable, mullion, door, and sliding templates', () => {
		expect(SECTION_TEMPLATE_LIST).toHaveLength(10)

		const fixedWin = buildTemplateDesign('fixed_window', 'h', '6CTG', {}, {}, 'CS400')
		expect(fixedWin.root.type).toBe('fixed')
		expect(fixedWin.frameConfig).toBe('4-side')

		const fixedDoorMullionH = buildTemplateDesign('fixed_door_mullion', 'h', '6CTG', {}, {}, 'CS400')
		expect(fixedDoorMullionH.frameConfig).toBe('3-side-threshold')
		expect(fixedDoorMullionH.root.type).toBe('split')
		if (fixedDoorMullionH.root.type === 'split') {
			expect(fixedDoorMullionH.root.dir).toBe('v')
			expect(fixedDoorMullionH.root.children).toHaveLength(2)
		}

		// Vertical cut switches split direction to horizontal transom
		const fixedDoorMullionV = buildTemplateDesign('fixed_door_mullion', 'v', '6CTG', {}, {}, 'CS400')
		if (fixedDoorMullionV.root.type === 'split') {
			expect(fixedDoorMullionV.root.dir).toBe('h')
		}

		const openableDoor = buildTemplateDesign('openable_door', 'h', '24DGU', { sash: 'E104160' }, {}, 'CS400')
		expect(openableDoor.root.type).toBe('sash')
		expect(openableDoor.profiles).toEqual({ sash: 'E104160' })

		const slidingWin = buildTemplateDesign('sliding_window', 'h', '6CTG', {}, {}, 'SL200')
		expect(slidingWin.isSliding).toBe(true)
	})

	it('extracts canonical role transforms, adjacency-specific bead transforms, and strips glass entries', () => {
		const cleaned = stripGlassFromSectionMap({
			'h:OFL': { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false },
			'h:OGL': { offsetAlong: 0, offsetDepth: 12, rotation: 0, flipX: false, flipY: false },
			'GLASS:F1': { offsetAlong: 0, offsetDepth: 12, rotation: 0, flipX: false, flipY: false },
		})
		expect(Object.keys(cleaned)).toEqual(['h:OFL'])

		const data = extractAxisTemplateData(
			{
				axis: 'h',
				pieces: [
					{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 0, end: 42, mirrored: false, thickness: 0 },
					{ kind: 'profile', code: 'CS4807', role: 'bead', panel: 'F1', start: 22, end: 45, mirrored: false, thickness: 0 },
					{ kind: 'glass', code: '6CTG', role: 'glass', panel: 'F1.0', start: 42, end: 760, mirrored: false, thickness: 6 },
					{ kind: 'profile', code: 'CS4807', role: 'bead', panel: 'F1', start: 740, end: 763, mirrored: true, thickness: 0 },
					{ kind: 'profile', code: 'E104159', role: 'mullion', panel: 'M1', start: 770, end: 830, mirrored: false, thickness: 0 },
				],
				tags: ['OFL', 'OBL', 'OGL', 'OBR', 'M1'],
				transforms: [
					{ offsetAlong: 0, offsetDepth: 1, rotation: 0, flipX: false, flipY: false },
					{ offsetAlong: 3.5, offsetDepth: 18, rotation: 90, flipX: true, flipY: false },
					{ offsetAlong: 0, offsetDepth: 12, rotation: 0, flipX: false, flipY: false },
					{ offsetAlong: -2.0, offsetDepth: 17, rotation: 90, flipX: true, flipY: false },
					{ offsetAlong: 0, offsetDepth: -1, rotation: 0, flipX: false, flipY: false },
				],
				sectionMap: {
					'h:OBL': { offsetAlong: 3.5, offsetDepth: 18, rotation: 90, flipX: true, flipY: false },
					'h:OGL': { offsetAlong: 0, offsetDepth: 12, rotation: 0, flipX: false, flipY: false },
				},
			},
			undefined,
		)

		expect(data.roleTransforms.frame.offsetDepth).toBe(1)
		expect(data.roleTransforms.mullion.offsetDepth).toBe(-1)
		expect(data.roleTransforms.bead_frame.offsetAlong).toBe(3.5)
		// Mirrored OBR (-2.0) becomes canonical +2.0 for bead_mullion
		expect(data.roleTransforms.bead_mullion.offsetAlong).toBe(2)
		expect(data.beadByCode['CS4807:frame'].offsetAlong).toBe(3.5)
		expect(data.beadByCode['CS4807:mullion'].offsetAlong).toBe(2)
		expect(data.sectionMap['h:OGL']).toBeUndefined()
	})
})

