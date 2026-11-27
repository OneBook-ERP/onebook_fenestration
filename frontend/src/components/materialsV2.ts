/**
 * Shader V2: physically based materials for the 3D window viewport.
 *
 * Differences from the first draft of this file:
 *  - Textures are THREE.DataTexture built from seeded pixel data (finishData.ts), not canvas
 *    textures. They work in vitest/jsdom, where canvas.getContext('2d') is null, and they
 *    look the same on every reload.
 *  - Texture repeat is 1 / tile-size-in-mm. Extrude UVs are in millimetres, so the old
 *    repeat of 16 or 32 meant dozens of tiles per millimetre (invisible shimmer).
 *  - Brushed grooves and wood grain run ALONG the profile (see finishData.ts for the UV axes).
 *  - Wood and mill finishes get their colour from finishVertexTint(), so the vertex colours
 *    (which also carry the baked ambient occlusion) do not tint the wood map grey.
 *  - Glass is fully transmissive (1.0), not 0.94: the remaining 6 % was drawn as milky diffuse.
 */

import * as THREE from 'three'
import {
	finishVertexTint,
	identifyFinish,
	makeBrushedNormal,
	makeStippleNormal,
	makeWoodgrain,
	type FinishType,
	type TexData,
} from './finishData'

export { finishVertexTint, identifyFinish }
export type { FinishType }

/** Size in mm that one texture tile covers. Extrude UVs are in mm, so repeat = 1 / tile. */
export const TILE_MM = {
	stipple: 10,
	brushedAcross: 8,
	brushedAlong: 400,
	woodAcross: 80,
	woodAlong: 600,
} as const

const textureCache = new Map<string, THREE.DataTexture>()

function dataTexture(
	key: string,
	make: () => TexData,
	tileAcrossMm: number,
	tileAlongMm: number,
	srgb = false,
): THREE.DataTexture {
	const hit = textureCache.get(key)
	if (hit) return hit
	const t = make()
	const tex = new THREE.DataTexture(t.data, t.width, t.height, THREE.RGBAFormat)
	tex.wrapS = THREE.RepeatWrapping
	tex.wrapT = THREE.RepeatWrapping
	tex.magFilter = THREE.LinearFilter
	tex.minFilter = THREE.LinearMipmapLinearFilter
	tex.generateMipmaps = true
	tex.anisotropy = 8
	tex.repeat.set(1 / tileAcrossMm, 1 / tileAlongMm)
	if (srgb) tex.colorSpace = THREE.SRGBColorSpace // colour maps only; normal maps stay linear
	tex.needsUpdate = true
	textureCache.set(key, tex)
	return tex
}

export const getPowderCoatNormalMap = () =>
	dataTexture('stipple', () => makeStippleNormal(), TILE_MM.stipple, TILE_MM.stipple)

export const getBrushedMetalNormalMap = () =>
	dataTexture('brushed', () => makeBrushedNormal(), TILE_MM.brushedAcross, TILE_MM.brushedAlong)

export const getWoodgrainTexture = () =>
	dataTexture('wood', () => makeWoodgrain(), TILE_MM.woodAcross, TILE_MM.woodAlong, true)

/** Call from onUnmounted. Materials do not dispose their textures. */
export function disposeV2Textures() {
	for (const tex of textureCache.values()) tex.dispose()
	textureCache.clear()
}

export interface V2Options {
	/** Only needed if you want a per-material environment. Normally scene.environment is used. */
	envMap?: THREE.Texture | null
}

export interface V2Materials {
	finish: FinishType
	glass: THREE.MeshPhysicalMaterial
	selectedGlass: THREE.MeshPhysicalMaterial
	frame: THREE.MeshPhysicalMaterial
	selectedFrame: THREE.MeshPhysicalMaterial
	gasket: THREE.MeshStandardMaterial
	hardware: THREE.MeshStandardMaterial
}

export function createV2Materials(finishNameOrColor?: string | null, opts: V2Options = {}): V2Materials {
	const finish = identifyFinish(finishNameOrColor)
	const envMap = opts.envMap

	// Clear float glass with Fresnel reflections and subtle green absorption.
	// The geometry assigns ray distances per face, so edges absorb more light.
	const glass = new THREE.MeshPhysicalMaterial({
		color: 0xffffff,
		transmission: 1,
		thickness: 6,
		ior: 1.52,
		roughness: 0.015,
		metalness: 0,
		specularIntensity: 1,
		attenuationColor: new THREE.Color(0xd6eee1),
		attenuationDistance: 400,
		envMapIntensity: 1.1,
		dispersion: 0.015,
		side: THREE.FrontSide,
		...(envMap ? { envMap } : {}),
	})
	const selectedGlass = glass.clone()
	selectedGlass.emissive = new THREE.Color(0x3b82f6)
	selectedGlass.emissiveIntensity = 0.3

	const common: Record<string, any> = { color: 0xffffff, vertexColors: true, side: THREE.DoubleSide }
	if (envMap) common.envMap = envMap
	let frame: THREE.MeshPhysicalMaterial

	switch (finish) {
		case '5104-pc-brown':
			// Architectural polyester powder coat: satin, faint metallic flake, orange-peel.
			frame = new THREE.MeshPhysicalMaterial({
				...common,
				roughness: 0.38,
				metalness: 0.12,
				clearcoat: 0.35,
				clearcoatRoughness: 0.3,
				normalMap: getPowderCoatNormalMap(),
				normalScale: new THREE.Vector2(0.35, 0.35),
			})
			break

		case 'mill-finish':
			// Raw extruded aluminium: metallic, with fine die lines running along the profile.
			// For true anisotropic highlights you could also set `anisotropy` (three r153+);
			// it is left off here because it needs a tangent frame that has not been checked on
			// these extruded UVs.
			frame = new THREE.MeshPhysicalMaterial({
				...common,
				roughness: 0.26,
				metalness: 0.88,
				clearcoat: 0.1,
				clearcoatRoughness: 0.2,
				normalMap: getBrushedMetalNormalMap(),
				normalScale: new THREE.Vector2(0.6, 0.6),
			})
			break

		case 'wooden-finish':
			// Sublimation over aluminium: dielectric, lacquered. The map supplies the colour,
			// and the vertex tint is white so only ambient occlusion modulates it.
			frame = new THREE.MeshPhysicalMaterial({
				...common,
				map: getWoodgrainTexture(),
				roughness: 0.42,
				metalness: 0,
				clearcoat: 0.45,
				clearcoatRoughness: 0.22,
			})
			break

		case 'grey':
		case 'generic':
		default:
			frame = new THREE.MeshPhysicalMaterial({
				...common,
				roughness: 0.45,
				metalness: 0.14,
				clearcoat: 0.25,
				clearcoatRoughness: 0.35,
				normalMap: getPowderCoatNormalMap(),
				normalScale: new THREE.Vector2(0.3, 0.3),
			})
			break
	}

	const selectedFrame = frame.clone()
	selectedFrame.emissive = new THREE.Color(0x2563eb)
	selectedFrame.emissiveIntensity = 0.45

	const gasket = new THREE.MeshStandardMaterial({
		color: 0x1a202c,
		roughness: 0.88,
		metalness: 0,
		side: THREE.DoubleSide,
		...(envMap ? { envMap } : {}),
	})

	const hardware = new THREE.MeshStandardMaterial({
		color: 0x94a3b8,
		roughness: 0.3,
		metalness: 0.85,
		...(envMap ? { envMap } : {}),
	})

	return { finish, glass, selectedGlass, frame, selectedFrame, gasket, hardware }
}
