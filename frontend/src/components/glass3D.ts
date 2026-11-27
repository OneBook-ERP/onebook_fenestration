import * as THREE from 'three'

/** Box face order: ±X, ±Y, ±Z. Edge rays travel farther through glass than face rays. */
export function createGlassMaterialPair(
	base: THREE.Material, selected: THREE.Material, width: number, height: number, thickness: number, cutout = false,
): { normal: THREE.Material | THREE.Material[]; selected: THREE.Material | THREE.Material[] } {
	const forBox = (source: THREE.Material) => {
		if (!(source instanceof THREE.MeshPhysicalMaterial)) return source
		const make = (distance: number) => {
			const material = source.clone()
			material.vertexColors = false
			material.thickness = Math.max(0.1, distance)
			return material
		}
		if (cutout) return [make(thickness), make(Math.max(width, height))]
		const edgeX = make(width), edgeY = make(height), face = make(thickness)
		return [edgeX, edgeX, edgeY, edgeY, face, face]
	}
	return { normal: forBox(base), selected: forBox(selected) }
}

/** A real through-hole: both glass faces and the cylindrical cut edge are meshed. */
export function createCutGlassGeometry(width: number, height: number, thickness: number, cut: import('@/design/exhaustCut').ExhaustCut): THREE.ExtrudeGeometry {
	const face = new THREE.Shape()
	face.moveTo(0, 0); face.lineTo(width, 0); face.lineTo(width, height); face.lineTo(0, height); face.closePath()
	const hole = new THREE.Path()
	hole.absarc(cut.centerX, height - cut.centerY, cut.diameter / 2, 0, Math.PI * 2, true)
	face.holes.push(hole)
	const geometry = new THREE.ExtrudeGeometry(face, { depth: thickness, bevelEnabled: false, steps: 1, curveSegments: 48 })
	geometry.translate(-width / 2, -height / 2, -thickness / 2)
	return geometry
}

export function createSteelMaterialPair(): { normal: THREE.MeshStandardMaterial; selected: THREE.MeshStandardMaterial } {
	const normal = new THREE.MeshStandardMaterial({ color: 0xa8adb5, metalness: 0.7, roughness: 0.38, side: THREE.DoubleSide })
	const selected = normal.clone()
	selected.emissive.set(0x2563eb)
	selected.emissiveIntensity = 0.3
	return { normal, selected }
}
