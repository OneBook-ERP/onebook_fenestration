import * as THREE from 'three'

/** Box face order: ±X, ±Y, ±Z. Edge rays travel farther through glass than face rays. */
export function createGlassMaterialPair(
	base: THREE.Material, selected: THREE.Material, width: number, height: number, thickness: number,
): { normal: THREE.Material | THREE.Material[]; selected: THREE.Material | THREE.Material[] } {
	const forBox = (source: THREE.Material) => {
		if (!(source instanceof THREE.MeshPhysicalMaterial)) return source
		const make = (distance: number) => {
			const material = source.clone()
			material.vertexColors = false
			material.thickness = Math.max(0.1, distance)
			return material
		}
		const edgeX = make(width), edgeY = make(height), face = make(thickness)
		return [edgeX, edgeX, edgeY, edgeY, face, face]
	}
	return { normal: forBox(base), selected: forBox(selected) }
}
