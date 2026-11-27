import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import { createGlassMaterialPair } from './glass3D'
import { createV2Materials } from './materialsV2'

describe('physical glazing', () => {
	it('uses pane thickness at the face and longer absorption paths at its edges', () => {
		const { glass, selectedGlass } = createV2Materials('Grey')
		const pair = createGlassMaterialPair(glass, selectedGlass, 600, 1000, 12)
		const faces = pair.normal as THREE.MeshPhysicalMaterial[]
		expect(faces.map(m => m.thickness)).toEqual([600, 600, 1000, 1000, 12, 12])
		expect(glass.thickness).toBe(6)
		expect(faces[4].attenuationDistance).toBe(400)
		expect(faces[4].ior).toBe(1.52)
		expect(faces[4].transmission).toBe(1)
		expect((pair.selected as THREE.MeshPhysicalMaterial[])[4].emissiveIntensity).toBeGreaterThan(0)
		for (const m of new Set([...faces, ...pair.selected as THREE.MeshPhysicalMaterial[]])) m.dispose()
	})
})
