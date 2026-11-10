/**
 * Pure data for Shader V2: finish detection and procedural texture pixels.
 *
 * No three.js and no canvas, so it runs the same in the browser, in vitest/jsdom
 * and in node. Everything is seeded, so a finish looks identical on every reload.
 *
 * UV convention (from three's ExtrudeGeometry, which this app uses for profiles):
 *   u = position along the section outline, in mm
 *   v = position along the extrusion (the profile length), in mm
 * so a texture's X axis runs ACROSS the profile and its Y axis runs ALONG it.
 * Grooves and wood grain that run along the profile must therefore vary with X
 * and stay constant along Y.
 */

export type FinishType = '5104-pc-brown' | 'grey' | 'mill-finish' | 'wooden-finish' | 'generic'

/** Colours that define a finish regardless of what the finish dropdown's swatch says. */
export const FINISH_BASE_HEX = {
	'5104-pc-brown': '#6B3E26',
	'mill-finish': '#D5D8DC', // raw extruded aluminium, slightly oxidised
	'wooden-finish': '#FFFFFF', // the wood texture supplies the colour; vertex colour only carries AO
} as const

/** Maps a finish label or hex to one of the canonical finishes. Unknown text is 'generic'. */
export function identifyFinish(nameOrColor?: string | null): FinishType {
	if (!nameOrColor) return 'grey'
	const s = nameOrColor.toLowerCase().trim()
	// Wood first, so "Oak Brown" is timber rather than brown powder coat.
	if (/wood|timber|oak|walnut|teak/.test(s)) return 'wooden-finish'
	if (/5104|brown|#6b3e26/.test(s)) return '5104-pc-brown'
	// Word boundaries: "raw" must not match "drawn".
	if (/\b(mill|anod\w*|raw)\b/.test(s)) return 'mill-finish'
	// "Silver Grey" is a powder coat, plain "Silver" is bare metal.
	if (/silver/.test(s) && !/gr[ae]y/.test(s)) return 'mill-finish'
	if (/gr[ae]y|charcoal|anthracite|white|black/.test(s)) return 'grey'
	return 'generic'
}

/**
 * Colour baked into the profile vertex colours (ambient occlusion is multiplied onto it).
 * Finishes that are defined by their look override the swatch; grey and generic use it as given.
 */
export function finishVertexTint(finish: FinishType, swatchHex: string): string {
	if (finish === '5104-pc-brown' || finish === 'mill-finish' || finish === 'wooden-finish') {
		return FINISH_BASE_HEX[finish]
	}
	return /^#[0-9a-f]{6}$/i.test(swatchHex) ? swatchHex : '#8A8F98'
}

// ---------------------------------------------------------------------------
// Procedural texture pixels
// ---------------------------------------------------------------------------

export interface TexData {
	data: Uint8Array
	width: number
	height: number
}

function mulberry32(seed: number) {
	let a = seed >>> 0
	return () => {
		a = (a + 0x6d2b79f5) >>> 0
		let t = a
		t = Math.imul(t ^ (t >>> 15), t | 1)
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296
	}
}

const to8 = (v: number) => Math.max(0, Math.min(255, Math.round(v)))

/** Zero mean, unit standard deviation. */
function normalise(a: Float32Array) {
	let mean = 0
	for (let i = 0; i < a.length; i++) mean += a[i]
	mean /= a.length
	let v = 0
	for (let i = 0; i < a.length; i++) v += (a[i] - mean) ** 2
	const sd = Math.sqrt(v / a.length) || 1
	for (let i = 0; i < a.length; i++) a[i] = (a[i] - mean) / sd
}

/** 3x3 box blur that wraps at the edges, so the texture still tiles. */
function blurWrapped(src: Float32Array, size: number): Float32Array {
	const out = new Float32Array(src.length)
	for (let y = 0; y < size; y++) {
		for (let x = 0; x < size; x++) {
			let s = 0
			for (let dy = -1; dy <= 1; dy++) {
				for (let dx = -1; dx <= 1; dx++) {
					s += src[((y + dy + size) % size) * size + ((x + dx + size) % size)]
				}
			}
			out[y * size + x] = s / 9
		}
	}
	return out
}

/**
 * Orange-peel for powder coat: soft, independent tilt on both axes.
 * (A tilt that is identical on X and Y only leans one way and reads as a diagonal scratch.)
 */
export function makeStippleNormal(size = 128, seed = 5104, strength = 24): TexData {
	const rand = mulberry32(seed)
	const nx = new Float32Array(size * size)
	const ny = new Float32Array(size * size)
	for (let i = 0; i < nx.length; i++) {
		nx[i] = rand() - 0.5
		ny[i] = rand() - 0.5
	}
	const bx = blurWrapped(nx, size)
	const by = blurWrapped(ny, size)
	normalise(bx)
	normalise(by)
	const data = new Uint8Array(size * size * 4)
	for (let i = 0; i < size * size; i++) {
		data[i * 4] = to8(128 + bx[i] * strength)
		data[i * 4 + 1] = to8(128 + by[i] * strength)
		data[i * 4 + 2] = 255
		data[i * 4 + 3] = 255
	}
	return { data, width: size, height: size }
}

/**
 * Fine extrusion / brushing lines that run ALONG the profile.
 * Each row is identical (nothing changes along v) and the tilt varies across u.
 * Built from whole-number sine frequencies, so it tiles seamlessly.
 */
export function makeBrushedNormal(width = 256, height = 8, seed = 88, strength = 34): TexData {
	const rand = mulberry32(seed)
	const slope = new Float32Array(width)
	const waves = 28
	for (let k = 0; k < waves; k++) {
		const freq = 4 + Math.floor(rand() * 90)
		const phase = rand() * Math.PI * 2
		const amp = 0.4 + rand() * 0.6
		for (let x = 0; x < width; x++) {
			// derivative of amp * sin(2 pi freq x / width + phase)
			slope[x] += amp * ((2 * Math.PI * freq) / width) * Math.cos((2 * Math.PI * freq * x) / width + phase)
		}
	}
	normalise(slope)
	const data = new Uint8Array(width * height * 4)
	for (let y = 0; y < height; y++) {
		for (let x = 0; x < width; x++) {
			const i = (y * width + x) * 4
			data[i] = to8(128 + slope[x] * strength)
			data[i + 1] = 128
			data[i + 2] = 255
			data[i + 3] = 255
		}
	}
	return { data, width, height }
}

/**
 * Wood-grain sublimation colour map. Grain runs along the profile (varies with X, wanders slowly with Y).
 * Periodic in both directions, so it tiles.
 */
export function makeWoodgrain(width = 256, height = 256, seed = 7): TexData {
	const rand = mulberry32(seed)
	const dark: [number, number, number] = [70, 38, 16]
	const light: [number, number, number] = [150, 88, 42]

	// Fine fibres: periodic 1D noise across the grain.
	const fibre = new Float32Array(width)
	for (let k = 0; k < 40; k++) {
		const freq = 6 + Math.floor(rand() * 110)
		const phase = rand() * Math.PI * 2
		const amp = 0.3 + rand() * 0.7
		for (let x = 0; x < width; x++) fibre[x] += amp * Math.sin((2 * Math.PI * freq * x) / width + phase)
	}
	normalise(fibre)

	const data = new Uint8Array(width * height * 4)
	for (let y = 0; y < height; y++) {
		const wander = 0.35 * Math.sin((2 * Math.PI * y) / height) // rings drift along the length
		const mottle = 0.04 * Math.sin((2 * Math.PI * 5 * y) / height + 1.3)
		for (let x = 0; x < width; x++) {
			const ring = 0.5 + 0.5 * Math.sin((2 * Math.PI * 3 * x) / width + wander)
			const tone = Math.max(0, Math.min(1, 0.15 + 0.7 * ring + 0.09 * fibre[x] + mottle))
			const i = (y * width + x) * 4
			data[i] = to8(dark[0] + (light[0] - dark[0]) * tone)
			data[i + 1] = to8(dark[1] + (light[1] - dark[1]) * tone)
			data[i + 2] = to8(dark[2] + (light[2] - dark[2]) * tone)
			data[i + 3] = 255
		}
	}
	return { data, width, height }
}

