import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createLouverGroup } from './louver3D'
import { louverSectionRings } from '@/design/louverGeometry'

describe('louver assembly', () => {
	it('contains only the requested blades, selectable as their owning panel', () => {
		const material = new THREE.MeshStandardMaterial()
		const group = createLouverGroup({ x: 24, y: 24, width: 637, height: 562 }, 9, 'F1.0', material, 60, 80)
		expect(group.children).toHaveLength(9)
		for (const blade of group.children as THREE.Mesh[]) {
			expect(blade.userData).toMatchObject({ path: 'F1.0', kind: 'louver' })
			expect((blade.geometry as THREE.BoxGeometry).parameters.width).toBe(637)
			expect(blade.position.x).toBe(342.5)
		}
		expect(group.getObjectByName('GLASS:F1.0')).toBeUndefined()
		material.dispose()
		;(group.children[0] as THREE.Mesh).geometry.dispose()
	})
	it('supplies finish vertex colours to metal blades instead of rendering them black', () => {
		const material = new THREE.MeshStandardMaterial({ vertexColors: true })
		const tint = new THREE.Color('#8A8F98')
		const group = createLouverGroup({ x: 0, y: 0, width: 500, height: 900 }, 9, 'F1', material, 60, 60,
			{ materialType: 'metal', inside: tint, outside: tint })
		const mesh = group.children[0] as THREE.Mesh
		const colors = mesh.geometry.getAttribute('color')
		expect(colors.count).toBe(mesh.geometry.getAttribute('position').count)
		expect(colors.getX(0)).toBeCloseTo(tint.r)
		expect(colors.getY(0)).toBeCloseTo(tint.g)
		expect(colors.getZ(0)).toBeCloseTo(tint.b)
		mesh.geometry.dispose()
		material.dispose()
	})
	it('uses transmissive glass for glass blades and retains glass when highlighted', () => {
		const material = new THREE.MeshPhysicalMaterial({ transmission: 1 })
		const selected = material.clone()
		const group = createLouverGroup({ x: 0, y: 0, width: 500, height: 900 }, 9, 'F1', material, 60, 60,
			{ materialType: 'glass', selectedMaterial: selected, thickness: 6 })
		const mesh = group.children[0] as THREE.Mesh
		for (const materials of [mesh.userData.normalMaterial, mesh.userData.selectedMaterial]) {
			expect(materials[4].transmission).toBe(1)
			expect(materials[4].thickness).toBe(6)
			for (const m of new Set<THREE.Material>(materials)) m.dispose()
		}
		expect(mesh.castShadow).toBe(false)
		expect((mesh.geometry as THREE.BoxGeometry).parameters.depth).toBe(6)
		mesh.geometry.dispose()
		material.dispose()
		selected.dispose()
	})

	it('uses the same blade profile in the 3D model and vertical section', () => {
		const material = new THREE.MeshStandardMaterial()
		const group = createLouverGroup({ x: 0, y: 24, width: 637, height: 562 }, 9, 'F1.0', material, 60, 80)
		const rings = louverSectionRings('v', 24, 586, 562, 9, 80)
		group.updateMatrixWorld(true)
		for (const [index, mesh] of (group.children as THREE.Mesh[]).entries()) {
			const bounds = new THREE.Box3().setFromObject(mesh)
			expect(Math.min(...rings[index].map(p => p.x))).toBeCloseTo(bounds.min.y, 4)
			expect(Math.max(...rings[index].map(p => p.y))).toBeCloseTo(30 - bounds.min.z, 4)
		}
		material.dispose()
		;(group.children[0] as THREE.Mesh).geometry.dispose()
	})
})
