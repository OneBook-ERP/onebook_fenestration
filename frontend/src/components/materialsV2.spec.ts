import * as THREE from 'three'
import { afterEach, describe, expect, it } from 'vitest'
import {
	createV2Materials,
	disposeV2Textures,
	getBrushedMetalNormalMap,
	getPowderCoatNormalMap,
	getWoodgrainTexture,
	TILE_MM,
} from './materialsV2'

/**
 * Note on assertions: three.js material slots default to `null`, and `toBeDefined()` passes for
 * null. Every "has a texture" check below uses `.not.toBeNull()` so it can fail.
 */
describe('materialsV2', () => {
	afterEach(() => disposeV2Textures())

	it('makes float glass: IOR 1.52, fully transmissive, smooth, 6 mm', () => {
		const { glass, selectedGlass } = createV2Materials('5104 PC Brown')
		expect(glass.transmission).toBe(1)
		expect(glass.ior).toBeCloseTo(1.52, 2)
		expect(glass.roughness).toBeLessThan(0.05)
		expect(glass.thickness).toBe(6)
		expect(glass.transparent).toBe(false) // transmissive materials render in their own pass
		expect(glass.clearcoat).toBe(0)
		expect(selectedGlass.emissiveIntensity).toBeGreaterThan(0)
		expect(glass.emissiveIntensity).toBe(1) // default; the selected copy must not leak into it
		expect(glass.emissive.getHex()).toBe(0x000000)
	})

	it('keeps vertex colours on every finish (they carry the baked ambient occlusion)', () => {
		for (const name of ['5104 PC Brown', 'Grey', 'Mill Finish', 'Wooden Finish', 'Sunset Orange']) {
			expect(createV2Materials(name).frame.vertexColors).toBe(true)
		}
	})

	it('mill finish: metallic, brushed normal map scaled in mm', () => {
		const { frame } = createV2Materials('Mill Finish')
		expect(frame.metalness).toBeGreaterThan(0.8)
		expect(frame.roughness).toBeLessThan(0.3)
		expect(frame.normalMap).not.toBeNull()
		expect(frame.normalMap!.repeat.x).toBeCloseTo(1 / TILE_MM.brushedAcross, 6)
		expect(frame.normalMap!.repeat.y).toBeCloseTo(1 / TILE_MM.brushedAlong, 6)
	})

	it('wood finish: dielectric, colour map in sRGB, no normal map', () => {
		const { frame } = createV2Materials('Wooden Finish')
		expect(frame.metalness).toBe(0)
		expect(frame.map).not.toBeNull()
		expect(frame.map!.colorSpace).toBe(THREE.SRGBColorSpace)
		expect(frame.normalMap).toBeNull()
		expect(frame.clearcoat).toBeGreaterThan(0.3)
	})

	it('powder-coat finishes share one stipple normal map at a sane scale', () => {
		const brown = createV2Materials('5104 PC Brown').frame
		const grey = createV2Materials('Grey').frame
		expect(brown.normalMap).not.toBeNull()
		expect(brown.normalMap).toBe(grey.normalMap)
		expect(brown.normalMap!.repeat.x).toBeCloseTo(1 / TILE_MM.stipple, 6) // 0.1, not 16
		expect(brown.normalMap!.colorSpace).toBe(THREE.NoColorSpace) // normal maps are linear
	})

	it('selected frame is a copy with an emissive highlight and the same maps', () => {
		const { frame, selectedFrame } = createV2Materials('Grey')
		expect(selectedFrame).not.toBe(frame)
		expect(selectedFrame.emissiveIntensity).toBeGreaterThan(0)
		expect(selectedFrame.normalMap).toBe(frame.normalMap)
	})

	it('caches textures and rebuilds them after disposeV2Textures', () => {
		const a = getPowderCoatNormalMap()
		expect(getPowderCoatNormalMap()).toBe(a)
		expect(getBrushedMetalNormalMap().image.width).toBeGreaterThan(0)
		expect(getWoodgrainTexture().image.width).toBeGreaterThan(0)
		disposeV2Textures()
		expect(getPowderCoatNormalMap()).not.toBe(a)
	})
})

