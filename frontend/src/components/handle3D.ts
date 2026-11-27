import * as THREE from 'three'

export type HandleStyle = 'casement' | 'door' | 'sliding'

export interface HandlePlacement {
	center: number
	exteriorCenter: number
	interiorZ: number
	exteriorZ: number
}

/** Rounded rectangle (stadium) 2D shape centered at `(cx, cy)`. */
function roundedRectShape(w: number, h: number, r: number, cx = 0, cy = 0): THREE.Shape {
	const hw = w / 2
	const hh = h / 2
	const cr = Math.min(r, hw * 0.95, hh * 0.95)
	const x0 = cx - hw
	const x1 = cx + hw
	const y0 = cy - hh
	const y1 = cy + hh
	const s = new THREE.Shape()
	s.moveTo(x0 + cr, y0)
	s.lineTo(x1 - cr, y0)
	s.quadraticCurveTo(x1, y0, x1, y0 + cr)
	s.lineTo(x1, y1 - cr)
	s.quadraticCurveTo(x1, y1, x1 - cr, y1)
	s.lineTo(x0 + cr, y1)
	s.quadraticCurveTo(x0, y1, x0, y1 - cr)
	s.lineTo(x0, y0 + cr)
	s.quadraticCurveTo(x0, y0, x0 + cr, y0)
	return s
}

/**
 * One-piece sculpted architectural L-lever profile drawn in the local (Z-depth, Y-vertical)
 * plane, then extruded along X with smooth rounded chamfers.
 * Local Z grows into the room (-Z in world space once rotated onto the sash face).
 */
function createSculptedCasementLeverGeometry(): THREE.BufferGeometry {
	// Profile in 2D shape coords: shapeX = projection outward (+), shapeY = vertical (+up / -down).
	const s = new THREE.Shape()
	// Start at spindle base top-back, sweep smoothly around the elbow and down the ergonomic grip.
	s.moveTo(0, 7.2)
	s.lineTo(17.5, 7.2)
	s.quadraticCurveTo(28.5, 7.2, 28.5, -3.5)
	s.lineTo(27.2, -98.0)
	// Smooth hemispherical tip at the bottom of the lever
	s.quadraticCurveTo(26.8, -104.5, 22.0, -104.5)
	s.quadraticCurveTo(17.2, -104.5, 16.8, -98.0)
	s.lineTo(15.6, -12.5)
	// Inner concave elbow fillet back to the neck
	s.quadraticCurveTo(15.4, -7.2, 9.8, -7.2)
	s.lineTo(0, -7.2)
	s.closePath()

	const geom = new THREE.ExtrudeGeometry(s, {
		depth: 7.4,
		bevelEnabled: true,
		bevelThickness: 1.9,
		bevelSize: 1.6,
		bevelSegments: 5,
		curveSegments: 24,
	})
	// Center extrusion width around X = 0, then rotate so shapeX (+projection) points toward -Z (Inside).
	geom.translate(0, 0, -3.7)
	geom.rotateY(Math.PI / 2)
	geom.computeVertexNormals()
	return geom
}

/** One-piece sculpted horizontal door lever extruded with smooth rounded chamfers. */
function createSculptedDoorLeverGeometry(leverSign: number): THREE.BufferGeometry {
	// Profile in (X-horizontal, Z-projection) plane, extruded vertically along Y.
	const dir = leverSign >= 0 ? 1 : -1
	const s = new THREE.Shape()
	s.moveTo(-6.5 * dir, 0)
	s.lineTo(-6.5 * dir, 22.0)
	s.quadraticCurveTo(-6.5 * dir, 34.0, 6.5 * dir, 34.0)
	s.lineTo(110.0 * dir, 32.5)
	s.quadraticCurveTo(116.5 * dir, 32.2, 116.5 * dir, 26.8)
	s.quadraticCurveTo(116.5 * dir, 21.4, 110.0 * dir, 21.2)
	s.lineTo(15.0 * dir, 20.0)
	s.quadraticCurveTo(8.0 * dir, 19.8, 7.5 * dir, 12.0)
	s.lineTo(7.5 * dir, 0)
	s.closePath()

	const geom = new THREE.ExtrudeGeometry(s, {
		depth: 9.0,
		bevelEnabled: true,
		bevelThickness: 2.0,
		bevelSize: 1.7,
		bevelSegments: 5,
		curveSegments: 24,
	})
	// Center Y thickness and map shapeY (+projection) -> -Z (Inside)
	geom.translate(0, 0, -4.5)
	geom.rotateX(-Math.PI / 2)
	geom.computeVertexNormals()
	return geom
}

function addPart(
	group: THREE.Group,
	geometry: THREE.BufferGeometry,
	material: THREE.Material,
	x = 0,
	y = 0,
	z = 0,
	rx = 0,
) {
	const mesh = new THREE.Mesh(geometry, material)
	mesh.position.set(x, y, z)
	if (rx !== 0) mesh.rotation.x = rx
	mesh.castShadow = true
	mesh.receiveShadow = true
	group.add(mesh)
	return mesh
}

function createHandleMaterials(accentMat?: THREE.Material) {
	const primary = new THREE.MeshPhysicalMaterial({
		color: 0x1f252e,
		roughness: 0.28,
		metalness: 0.78,
		clearcoat: 0.24,
		clearcoatRoughness: 0.22,
	})
	const gasket = new THREE.MeshStandardMaterial({
		color: 0x10141a,
		roughness: 0.8,
		metalness: 0.1,
	})
	const trim = accentMat
		? accentMat.clone()
		: new THREE.MeshStandardMaterial({
			color: 0x9aa4b2,
			roughness: 0.28,
			metalness: 0.85,
		})
	return { primary, gasket, trim }
}

/**
 * Builds a realistic, bevel-sculpted architectural 3D handle group.
 * Origin `(0, 0, 0)` rests flush on the interior aluminum surface; geometry projects toward `-Z`.
 */
export function createArchitecturalHandle(
	style: HandleStyle = 'casement',
	leverSign = -1,
	accentMaterial?: THREE.Material,
): THREE.Group {
	const group = new THREE.Group()
	group.name = `handle:${style}`
	const { primary, gasket, trim } = createHandleMaterials(accentMaterial)

	if (style === 'sliding') {
		// Minimalist flush touch-lock pull housing + recessed pocket + satin thumb-latch slider
		const baseGeom = new THREE.ExtrudeGeometry(roundedRectShape(20, 144, 6.5), {
			depth: 1.5,
			bevelEnabled: false,
			curveSegments: 16,
		})
		addPart(group, baseGeom, gasket, 0, 0, -1.0)

		const housingGeom = new THREE.ExtrudeGeometry(roundedRectShape(18, 140, 5.8), {
			depth: 5.2,
			bevelEnabled: true,
			bevelThickness: 1.2,
			bevelSize: 1.0,
			bevelSegments: 4,
			curveSegments: 20,
		})
		addPart(group, housingGeom, primary, 0, 0, -6.2)

		const recessGeom = new THREE.ExtrudeGeometry(roundedRectShape(8.5, 86, 3.2), {
			depth: 1.6,
			bevelEnabled: false,
			curveSegments: 12,
		})
		addPart(group, recessGeom, gasket, 0, 0, -8.2)

		const latchGeom = new THREE.ExtrudeGeometry(roundedRectShape(7.0, 22, 2.5), {
			depth: 2.2,
			bevelEnabled: true,
			bevelThickness: 0.6,
			bevelSize: 0.5,
			bevelSegments: 3,
			curveSegments: 12,
		})
		addPart(group, latchGeom, trim, 0, 0, -10.2)
		return group
	}

	if (style === 'door') {
		// Euro-profile tall architectural backplate centered symmetrically at y = 0 + lock cylinder + sculpted lever
		const baseGeom = new THREE.ExtrudeGeometry(roundedRectShape(28, 174, 8), {
			depth: 1.5,
			bevelEnabled: false,
			curveSegments: 16,
		})
		addPart(group, baseGeom, gasket, 0, 0, -1.0)

		const plateGeom = new THREE.ExtrudeGeometry(roundedRectShape(26, 170, 7.2), {
			depth: 5.8,
			bevelEnabled: true,
			bevelThickness: 1.4,
			bevelSize: 1.2,
			bevelSegments: 4,
			curveSegments: 20,
		})
		addPart(group, plateGeom, primary, 0, 0, -6.8)

		// Euro cylinder rose & keyhole barrel in lower half of backplate
		addPart(group, new THREE.CylinderGeometry(8.5, 8.5, 3.5, 20), trim, 0, -38, -8.8, Math.PI / 2)
		addPart(group, new THREE.BoxGeometry(5.5, 13.0, 3.5), trim, 0, -45, -8.8)

		// Spindle collar + continuous sculpted horizontal lever in upper half of backplate
		addPart(group, new THREE.CylinderGeometry(9.0, 9.8, 3.0, 20), primary, 0, 28, -9.2, Math.PI / 2)
		addPart(group, createSculptedDoorLeverGeometry(leverSign), primary, 0, 28, -8.5)
		return group
	}

	// Architectural Casement Espag Handle (spindle hub slightly above origin so visual assembly centers cleanly)
	const hubY = 26
	// 1. Flush mounting gasket base (+0.6mm embed prevents hairline seam)
	const gasketGeom = new THREE.ExtrudeGeometry(roundedRectShape(23, 62, 7.2), {
		depth: 2.0,
		bevelEnabled: false,
		curveSegments: 18,
	})
	addPart(group, gasketGeom, gasket, 0, hubY, -1.4)

	// 2. Beveled architectural stadium rosette plate
	const plateGeom = new THREE.ExtrudeGeometry(roundedRectShape(21, 58, 6.4), {
		depth: 5.5,
		bevelEnabled: true,
		bevelThickness: 1.4,
		bevelSize: 1.2,
		bevelSegments: 4,
		curveSegments: 22,
	})
	addPart(group, plateGeom, primary, 0, hubY, -6.9)

	// 3. Subtle rotary hub collar ring
	addPart(group, new THREE.CylinderGeometry(7.2, 7.8, 2.4, 20), primary, 0, hubY, -8.8, Math.PI / 2)

	// 4. One-piece sculpted curved L-lever with seamless beveled shaft and rounded tip
	addPart(group, createSculptedCasementLeverGeometry(), primary, 0, hubY, -7.8)
	return group
}

function measureFaceBand(
	verts: { t: number; z: number }[],
	faceZ: number,
	isExterior: boolean,
	closingSide: 'L' | 'R' | 'B' | 'T',
	occluderBoxes: THREE.Box3[],
	fallbackMin: number,
	fallbackMax: number,
): { center: number; surfaceZ: number } {
	let visMin = Infinity
	let visMax = -Infinity
	for (const pt of verts) {
		const onFace = isExterior ? pt.z >= faceZ - 4.0 : pt.z <= faceZ + 4.0
		if (!onFace) continue
		if (pt.t < visMin) visMin = pt.t
		if (pt.t > visMax) visMax = pt.t
	}
	if (!Number.isFinite(visMin) || !Number.isFinite(visMax)) {
		visMin = fallbackMin
		visMax = fallbackMax
	}

	// Clip only the outer seam if a structural frame/mullion physically occludes this face.
	// Do NOT clip against glassBox: glass sits inside the glazing pocket behind the visible metal sightline.
	for (const occ of occluderBoxes) {
		const occCoversFace = isExterior ? occ.max.z >= faceZ - 1.5 : occ.min.z <= faceZ + 1.5
		if (!occCoversFace) continue
		if (closingSide === 'R') {
			if (occ.max.x >= visMax - 2 && occ.min.x > visMin + 10 && occ.min.x < visMax) {
				visMax = Math.min(visMax, occ.min.x)
			}
		} else if (closingSide === 'L') {
			if (occ.min.x <= visMin + 2 && occ.max.x < visMax - 10 && occ.max.x > visMin) {
				visMin = Math.max(visMin, occ.max.x)
			}
		} else if (closingSide === 'B') {
			if (occ.min.y <= visMin + 2 && occ.max.y < visMax - 10 && occ.max.y > visMin) {
				visMin = Math.max(visMin, occ.max.y)
			}
		} else if (occ.max.y >= visMax - 2 && occ.min.y > visMin + 10 && occ.min.y < visMax) {
			visMax = Math.min(visMax, occ.min.y)
		}
	}

	const center = (visMin + visMax) / 2
	let localZ = isExterior ? -Infinity : Infinity
	for (const pt of verts) {
		if (Math.abs(pt.t - center) > 9.0) continue
		if (isExterior ? pt.z > localZ : pt.z < localZ) localZ = pt.z
	}
	return { center, surfaceZ: Number.isFinite(localZ) ? localZ : faceZ }
}

/**
 * Measures the exact visible interior and exterior stile bands and flush Z depths directly
 * from the assembled 3D closing rail mesh, clipped only against structural frame/mullion
 * occluders on each respective face.
 */
export function measureClosingStilePlacement(
	closingMesh: THREE.Mesh,
	closingSide: 'L' | 'R' | 'B' | 'T',
	_glassBox?: { minX: number; maxX: number; minY: number; maxY: number },
	occluderBoxes: THREE.Box3[] = [],
): HandlePlacement {
	void _glassBox
	closingMesh.updateMatrix()
	const pos = closingMesh.geometry.getAttribute('position')
	const v = new THREE.Vector3()
	const isVertical = closingSide === 'L' || closingSide === 'R'

	let zMin = Infinity
	let zMax = -Infinity
	let fullMin = Infinity
	let fullMax = -Infinity
	const verts: { t: number; z: number }[] = []

	for (let i = 0; i < pos.count; i++) {
		v.fromBufferAttribute(pos, i).applyMatrix4(closingMesh.matrix)
		const t = isVertical ? v.x : v.y
		verts.push({ t, z: v.z })
		if (v.z < zMin) zMin = v.z
		if (v.z > zMax) zMax = v.z
		if (t < fullMin) fullMin = t
		if (t > fullMax) fullMax = t
	}

	if (!Number.isFinite(zMin) || !Number.isFinite(fullMin)) {
		return { center: 0, exteriorCenter: 0, interiorZ: 0, exteriorZ: 0 }
	}

	const interior = measureFaceBand(verts, zMin, false, closingSide, occluderBoxes, fullMin, fullMax)
	const exterior = measureFaceBand(verts, zMax, true, closingSide, occluderBoxes, fullMin, fullMax)

	return {
		center: interior.center,
		exteriorCenter: exterior.center,
		interiorZ: interior.surfaceZ,
		exteriorZ: exterior.surfaceZ,
	}
}

