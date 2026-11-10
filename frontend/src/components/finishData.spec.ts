import { describe, expect, it } from 'vitest'
import {
	finishVertexTint,
	identifyFinish,
	makeBrushedNormal,
	makeStippleNormal,
	makeWoodgrain,
	type TexData,
} from './finishData'

/** Mean absolute difference between neighbouring pixels along one axis, for one channel. */
function roughness(t: TexData, channel: number, axis: 'x' | 'y') {
	let sum = 0
	let n = 0
	for (let y = 0; y < t.height; y++) {
		for (let x = 0; x < t.width; x++) {
			const nx = axis === 'x' ? (x + 1) % t.width : x
			const ny = axis === 'y' ? (y + 1) % t.height : y
			sum += Math.abs(t.data[(y * t.width + x) * 4 + channel] - t.data[(ny * t.width + nx) * 4 + channel])
			n++
		}
	}
	return sum / n
}

function channel(t: TexData, c: number) {
	const out: number[] = []
	for (let i = c; i < t.data.length; i += 4) out.push(t.data[i])
	return out
}

function correlation(a: number[], b: number[]) {
	const ma = a.reduce((s, v) => s + v, 0) / a.length
	const mb = b.reduce((s, v) => s + v, 0) / b.length
	let num = 0
	let da = 0
	let db = 0
	for (let i = 0; i < a.length; i++) {
		num += (a[i] - ma) * (b[i] - mb)
		da += (a[i] - ma) ** 2
		db += (b[i] - mb) ** 2
	}
	return num / Math.sqrt(da * db)
}

describe('identifyFinish', () => {
	it('maps the four finishes', () => {
		expect(identifyFinish('5104 PC Brown')).toBe('5104-pc-brown')
		expect(identifyFinish('#6B3E26')).toBe('5104-pc-brown')
		expect(identifyFinish('Mill Finish')).toBe('mill-finish')
		expect(identifyFinish('Raw Anodised')).toBe('mill-finish')
		expect(identifyFinish('Wooden Finish')).toBe('wooden-finish')
		expect(identifyFinish('Golden Oak Timber')).toBe('wooden-finish')
		expect(identifyFinish('Grey')).toBe('grey')
		expect(identifyFinish('RAL 7016 Anthracite Grey')).toBe('grey')
		expect(identifyFinish(null)).toBe('grey')
	})

	it('does not mistake powder coats and unknown text for bare metal', () => {
		expect(identifyFinish('Silver Grey')).toBe('grey') // powder coat
		expect(identifyFinish('Silver')).toBe('mill-finish')
		expect(identifyFinish('Drawn aluminium')).toBe('generic') // "raw" inside "drawn"
		expect(identifyFinish('Oak Brown')).toBe('wooden-finish') // timber wins over brown
		expect(identifyFinish('Sunset Orange')).toBe('generic')
	})
})

describe('finishVertexTint', () => {
	it('defines wood, mill and 5104 by their own look and passes other swatches through', () => {
		expect(finishVertexTint('wooden-finish', '#8A8F98')).toBe('#FFFFFF')
		expect(finishVertexTint('5104-pc-brown', '#8A8F98')).toBe('#6B3E26')
		expect(finishVertexTint('mill-finish', '#8A8F98')).toBe('#D5D8DC')
		expect(finishVertexTint('grey', '#445566')).toBe('#445566')
		expect(finishVertexTint('generic', 'not-a-colour')).toBe('#8A8F98')
	})
})

describe('procedural finish textures', () => {
	it('are deterministic per seed', () => {
		expect(makeStippleNormal(64, 1).data).toEqual(makeStippleNormal(64, 1).data)
		expect(makeStippleNormal(64, 1).data).not.toEqual(makeStippleNormal(64, 2).data)
		expect(makeWoodgrain(64, 64, 3).data).toEqual(makeWoodgrain(64, 64, 3).data)
	})

	it('stipple tilts independently on X and Y and averages flat', () => {
		const t = makeStippleNormal(128)
		const r = channel(t, 0)
		const g = channel(t, 1)
		expect(Math.abs(correlation(r, g))).toBeLessThan(0.2)
		expect(Math.abs(r.reduce((s, v) => s + v, 0) / r.length - 128)).toBeLessThan(2)
		expect(new Set(channel(t, 2))).toEqual(new Set([255]))
	})

	it('brushed lines run along the profile: rows identical, tilt only across', () => {
		const t = makeBrushedNormal(256, 8)
		for (let y = 1; y < t.height; y++) {
			for (let x = 0; x < t.width; x++) {
				expect(t.data[(y * t.width + x) * 4]).toBe(t.data[x * 4])
			}
		}
		expect(roughness(t, 0, 'x')).toBeGreaterThan(5)
		expect(roughness(t, 0, 'y')).toBe(0)
		expect(new Set(channel(t, 1))).toEqual(new Set([128])) // no tilt along the length
	})

	it('wood grain varies across the profile far more than along it', () => {
		const t = makeWoodgrain(256, 256)
		expect(roughness(t, 0, 'x')).toBeGreaterThan(roughness(t, 0, 'y') * 3)
		const r = channel(t, 0).reduce((s, v) => s + v, 0)
		const g = channel(t, 1).reduce((s, v) => s + v, 0)
		const b = channel(t, 2).reduce((s, v) => s + v, 0)
		expect(r).toBeGreaterThan(g) // brown: R > G > B
		expect(g).toBeGreaterThan(b)
	})
})

