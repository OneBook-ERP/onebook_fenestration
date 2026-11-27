import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createArchitecturalHandle, measureClosingStilePlacement } from './handle3D'

describe('handle3D', () => {
	it('builds sculpted beveled architectural handles for casement, door, and sliding styles protruding into -Z', () => {
		for (const style of ['casement', 'door', 'sliding'] as const) {
			const group = createArchitecturalHandle(style, -1)
			expect(group.name).toBe(`handle:${style}`)
			expect(group.children.length).toBeGreaterThanOrEqual(4)
			const box = new THREE.Box3().setFromObject(group)
			// Protrudes cleanly into the room (-Z) and seats slightly into z >= 0 with zero gap
			expect(box.min.z).toBeLessThan(-8)
			expect(box.max.z).toBeGreaterThanOrEqual(0)
			expect(box.max.z).toBeLessThan(2)
		}
	})

	it('centers the door handle backplate symmetrically around y = 0 and reverses lever direction with leverSign', () => {
		const rightLever = createArchitecturalHandle('door', 1)
		const leftLever = createArchitecturalHandle('door', -1)
		const rBox = new THREE.Box3().setFromObject(rightLever)
		const lBox = new THREE.Box3().setFromObject(leftLever)
		// Backplate spans [-87..+87] so the door handle centers cleanly at sashH / 2
		expect((rBox.min.y + rBox.max.y) / 2).toBeCloseTo(0, 1)
		expect(rBox.max.x).toBeGreaterThan(100)
		expect(lBox.min.x).toBeLessThan(-100)
	})

	it('centers the handle on the true visible stile face without clipping against recessed glass pocket', () => {
		// Right closing stile R spanning X in [485..555], Z in [-20..20]
		const geom = new THREE.BoxGeometry(70, 1100, 40)
		const mesh = new THREE.Mesh(geom, new THREE.MeshBasicMaterial())
		mesh.position.set(520, 550, 0)

		// Glass extends 10 mm inside the glazing pocket (maxX = 495); mullion occludes X = 540..610 on interior only
		const mullionBox = new THREE.Box3(new THREE.Vector3(540, 0, -22), new THREE.Vector3(610, 1100, 10))
		const placed = measureClosingStilePlacement(
			mesh,
			'R',
			{ minX: 55, maxX: 495, minY: 55, maxY: 1045 },
			[mullionBox],
		)
		// Visible interior face runs from 485 (sash sightline) to 540 (mullion edge) -> dead center = 512.5
		expect(placed.center).toBeCloseTo(512.5, 2)
		// Exterior face (z = +20) is unoccluded by mullion (max.z = 10) -> full [485..555], center = 520
		expect(placed.exteriorCenter).toBeCloseTo(520, 2)
		expect(placed.interiorZ).toBeCloseTo(-20, 2)
		expect(placed.exteriorZ).toBeCloseTo(20, 2)
	})

	it('centers left closing stile L symmetrically against an occluding mullion on both faces', () => {
		const geom = new THREE.BoxGeometry(70, 1100, 40)
		const mesh = new THREE.Mesh(geom, new THREE.MeshBasicMaterial())
		mesh.position.set(35, 550, 0)

		// Mullion on the left covers X in [-40..15] across full depth Z in [-22..22]
		const mullionBox = new THREE.Box3(new THREE.Vector3(-40, 0, -22), new THREE.Vector3(15, 1100, 22))
		const placed = measureClosingStilePlacement(
			mesh,
			'L',
			{ minX: 60, maxX: 495, minY: 55, maxY: 1045 },
			[mullionBox],
		)
		// Visible aluminum face runs from 15 (mullion edge) to 70 (sash inner sightline) -> dead center = 42.5
		expect(placed.center).toBeCloseTo(42.5, 2)
		expect(placed.exteriorCenter).toBeCloseTo(42.5, 2)
		expect(placed.interiorZ).toBeCloseTo(-20, 2)
		expect(placed.exteriorZ).toBeCloseTo(20, 2)
	})
})

