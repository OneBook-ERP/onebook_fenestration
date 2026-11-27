import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import { exhaustCut } from './exhaustCut'
import { buildPlacedShape, compactPieceSpans } from './sectionPuzzle'
import { createCutGlassGeometry, createSteelMaterialPair } from '@/components/glass3D'

describe('exhaust openings', () => {
	it('keeps legacy fan flags compatible and rejects cuts beyond the glass', () => {
		expect(exhaustCut({ fan: true }, 600, 500)).toEqual({ diameter: 180, centerX: 300, centerY: 250 })
		expect(exhaustCut({ fan: false }, 600, 500)).toBeNull()
		expect(exhaustCut({ fan: true, type: 'louver' }, 600, 500)).toBeNull()
		for (const fanCut of [{ diameter: 700 }, { diameter: -1 }, { centerX: 20 }, { centerY: NaN }]) {
			expect(exhaustCut({ fan: true, fanCut }, 600, 500)).toBeNull()
		}
	})
	it('keeps the default centre fixed as diameter changes and preserves explicit positions', () => {
		for (const diameter of [100, 180, 300]) {
			expect(exhaustCut({ fan: true, fanCut: { diameter } }, 600, 500)).toEqual({ diameter, centerX: 300, centerY: 250 })
		}
		expect(exhaustCut({ fan: true, fanCut: { diameter: 100, centerX: 200, centerY: 150 } }, 600, 500)).toEqual({ diameter: 100, centerX: 200, centerY: 150 })
	})
	it('uses opaque metal for the sheet and its selected state in either shader', () => {
		const pair = createSteelMaterialPair()
		for (const material of [pair.normal, pair.selected]) {
			expect(material.transparent).toBe(false)
			expect(material.opacity).toBe(1)
			expect(material.depthWrite).toBe(true)
			expect(material.metalness).toBeGreaterThan(0.5)
			material.dispose()
		}
	})
	it('creates a genuine through-hole visible from both sides while retaining surrounding glass', () => {
		const cut = exhaustCut({ fan: true }, 600, 500)!
		const geometry = createCutGlassGeometry(600, 500, 6, cut)
		const material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide })
		const mesh = new THREE.Mesh(geometry, material)
		mesh.updateMatrixWorld()
		for (const sign of [-1, 1]) {
			const ray = new THREE.Raycaster(new THREE.Vector3(0, 250 - cut.centerY, sign * 100), new THREE.Vector3(0, 0, -sign))
			expect(ray.intersectObject(mesh)).toHaveLength(0)
			ray.ray.origin.x = 200
			expect(ray.intersectObject(mesh).length).toBeGreaterThan(0)
		}
		geometry.dispose(); material.dispose()
	})
	it('keeps focused profile positions unchanged by exhaust diameter in either section axis', () => {
		const pane = { kind: 'glass' as const, role: 'glass', code: 'Steel', material: 'steel' as const, panel: 'F1.1', start: 650, end: 1180, mirrored: false, thickness: 1.2 }
		const profile = (start: number, end: number) => ({ kind: 'profile' as const, role: 'frame', code: 'FRAME', panel: 'F1', start, end, mirrored: false, thickness: 0 })
		const pieces = [profile(0, 50), { ...pane, kind: 'louver' as const, role: 'louver', start: 40, end: 570, blades: 9, opening_height: 1140 }, profile(575, 645), pane, profile(1170, 1220)]
		for (const axis of ['h', 'v'] as const) {
			const baseline = compactPieceSpans(pieces, true, axis)
			for (const diameter of [180, 300, 500]) {
				const cutout = { start: 915 - diameter / 2, end: 915 + diameter / 2, diameter }
				const cutPieces = pieces.map((p, i) => i === 3 ? { ...p, cutout } : p)
				expect(compactPieceSpans(cutPieces, true, axis)).toEqual(baseline)
				const full = compactPieceSpans(cutPieces, false, axis)
				const shape = buildPlacedShape(3, { ...pane, cutout }, full.starts[3], full.ends[3], null, { offsetAlong: 0, offsetDepth: 0, rotation: 0 })
				expect(Math.min(...shape.rings[1].map(p => p.x)) - Math.max(...shape.rings[0].map(p => p.x))).toBeCloseTo(diameter)
			}
		}
	})
	it('splits section glass geometry around the opening at full and compact scales', () => {
		const piece = { kind: 'glass' as const, role: 'glass', code: '6CTG', panel: 'F1', start: 30, end: 630, mirrored: false, thickness: 6, cutout: { start: 240, end: 420, diameter: 180 } }
		for (const compact of [false, true]) {
			const { starts, ends } = compactPieceSpans([piece], compact)
			const shape = buildPlacedShape(0, piece, starts[0], ends[0], null, { offsetAlong: 0, offsetDepth: 0, rotation: 0 })
			expect(shape.rings).toHaveLength(2)
			expect(Math.max(...shape.rings[0].map(p => p.x))).toBeLessThan(Math.min(...shape.rings[1].map(p => p.x)))
			expect(shape.bbox.width).toBeCloseTo(ends[0] - starts[0])
		}
	})
})
