import * as THREE from 'three'
import { createGlassMaterialPair } from './glass3D'
import { LOUVER_ANGLE, LOUVER_DEPTH, LOUVER_THICKNESS, louverLayout } from '@/design/louverGeometry'

/** Louvers contain individual blades and open air, with no backing glass or bead ring. */
export function createLouverGroup(
	box: { x: number; y: number; width: number; height: number },
	blades: number, path: string, material: THREE.Material, depthReference: number, bladeWidth?: number,
	options: { materialType?: 'glass' | 'metal'; inside?: THREE.Color; outside?: THREE.Color; selectedMaterial?: THREE.Material; thickness?: number } = {},
): THREE.Group {
	const group = new THREE.Group()
	group.name = `LOUVER:${path}`
	const layout = louverLayout(box.height, blades, bladeWidth)
	const thickness = options.thickness || LOUVER_THICKNESS
	const geometry = new THREE.BoxGeometry(box.width, layout.chord, thickness)
	const positions = geometry.getAttribute('position')
	const normals = geometry.getAttribute('normal')
	const uv = geometry.getAttribute('uv')
	const colors = new Float32Array(positions.count * 3)
	for (let i = 0; i < positions.count; i++) {
		const color = (normals.getZ(i) > 0 ? options.outside : options.inside) ?? new THREE.Color(0xffffff)
		color.toArray(colors, i * 3)
		// Finish maps use millimetres: across the blade, then along its length.
		uv.setXY(i, positions.getY(i) + layout.chord / 2, positions.getX(i) + box.width / 2)
	}
	geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
	const materials = options.materialType === 'glass'
		? createGlassMaterialPair(material, options.selectedMaterial ?? material, box.width, layout.chord, thickness)
		: { normal: material, selected: options.selectedMaterial ?? material }
	for (const y of layout.centres) {
		const blade = new THREE.Mesh(geometry, materials.normal)
		blade.position.set(box.x + box.width / 2, box.y + y, depthReference / 2 - LOUVER_DEPTH)
		blade.rotation.x = LOUVER_ANGLE
		blade.userData = { path, kind: 'louver', normalMaterial: materials.normal, selectedMaterial: materials.selected }
		blade.castShadow = options.materialType !== 'glass'
		blade.receiveShadow = true
		group.add(blade)
	}
	return group
}
