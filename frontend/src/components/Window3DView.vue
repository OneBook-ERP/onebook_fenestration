<template>
	<div
		class="relative flex h-full w-full flex-col overflow-hidden bg-gradient-to-b from-slate-50 to-slate-100 p-4 select-none"
		data-testid="window-3d-view"
	>
		<!-- Top 3D Control Bar -->
		<div
			class="z-10 mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white/95 px-4 py-2.5 shadow-xs backdrop-blur"
		>
			<div class="flex items-center gap-2">
				<span class="text-xs font-semibold uppercase tracking-wider text-gray-500">Camera</span>
				<div class="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5">
					<button
						type="button"
						class="rounded-md px-2.5 py-1 text-xs font-semibold transition"
						:class="activeCameraPreset === 'iso' ? 'bg-white text-gray-900 shadow-2xs' : 'text-gray-700 hover:text-gray-900'"
						@click="setCameraPreset('iso')"
					>
						Isometric
					</button>
					<button
						type="button"
						class="rounded-md px-2.5 py-1 text-xs font-semibold transition"
						:class="activeCameraPreset === 'front' ? 'bg-white text-gray-900 shadow-2xs' : 'text-gray-700 hover:text-gray-900'"
						title="Interior front view"
						@click="setCameraPreset('front')"
					>
						Front
					</button>
					<button
						type="button"
						class="rounded-md px-2.5 py-1 text-xs font-semibold transition"
						:class="activeCameraPreset === 'exterior' ? 'bg-white text-gray-900 shadow-2xs' : 'text-gray-700 hover:text-gray-900'"
						@click="setCameraPreset('exterior')"
					>
						Exterior
					</button>
					<button
						type="button"
						class="rounded-md px-2.5 py-1 text-xs font-semibold transition"
						:class="activeCameraPreset === 'mitre' ? 'bg-white text-gray-900 shadow-2xs' : 'text-gray-700 hover:text-gray-900'"
						title="Close-up inspection of 45° mitre corner"
						@click="setCameraPreset('mitre')"
					>
						Mitre Close-up
					</button>
				</div>
			</div>

			<div class="inline-flex items-center rounded-lg bg-gray-100 p-0.5 text-xs" role="group" aria-label="Shader">
				<button
					type="button"
					data-testid="shader-v1-btn"
					class="rounded-md px-2.5 py-1 font-semibold transition"
					:class="shaderMode === 'v1' ? 'bg-white text-gray-900 shadow-2xs' : 'text-gray-500 hover:text-gray-800'"
					:aria-pressed="shaderMode === 'v1'"
					title="Shader v1: fast engineering view with baked section ambient occlusion"
					@click="shaderMode = 'v1'"
				>
					Shader v1
				</button>
				<button
					type="button"
					data-testid="shader-v2-btn"
					class="rounded-md px-2.5 py-1 font-semibold transition"
					:class="shaderMode === 'v2' ? 'bg-white text-gray-900 shadow-2xs' : 'text-gray-500 hover:text-gray-800'"
					:aria-pressed="shaderMode === 'v2'"
					title="Shader v2: physical glass (IOR 1.52) and finish materials"
					@click="shaderMode = 'v2'"
				>
					Shader v2
				</button>
			</div>
		</div>

		<!-- 3D Viewport Stage -->
		<div
			ref="stageEl"
			class="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-xl border border-gray-200 bg-gradient-to-b from-white via-slate-50 to-slate-200/60"
			@click="onStageClick"
		>
			<canvas
				v-show="webGLSupported"
				ref="canvasEl"
				class="h-full w-full block cursor-grab active:cursor-grabbing outline-none"
			/>

			<div
				v-if="!webGLSupported"
				class="flex flex-col items-center justify-center p-8 text-center text-gray-500"
			>
				<p class="font-medium text-sm">WebGL 3D preview</p>
				<p class="mt-1 text-xs text-gray-400">Hardware acceleration is not available in this environment.</p>
			</div>

			<div class="pointer-events-none absolute bottom-3 left-4 flex items-center gap-3 text-xs text-gray-500 bg-white/75 px-3 py-1 rounded-full shadow-2xs backdrop-blur-xs">
				<span>Drag to orbit · Scroll to zoom · Click any member to select</span>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { toCreasedNormals } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { createSectionAO, type SectionAO } from './profileAO'
import { createV2Materials, disposeV2Textures, finishVertexTint, identifyFinish } from './materialsV2'
import { crossSection, windowAssembly, type CrossSection, type SectionOutline, type WindowAssembly } from '@/api'
import { layoutGeom } from '@/design/geometry'
import { defaultTransformForPiece, parseSvgRings, classifySectionPieceInstances } from '@/design/sectionPuzzle'
import type { Design, LeafNode, SashNode, SectionPieceTransform } from '@/design/types'
import type { SectionPiece } from '@/api'
import { useDesignerStore } from '@/stores/designer'

const props = withDefaults(
	defineProps<{
		design: Design
		selectedPath?: string | null
		finishColor?: string
		outsideFinishColor?: string
		finishName?: string
	}>(),
	{
		selectedPath: null,
		finishColor: '#8A8F98',
		outsideFinishColor: '',
		finishName: 'Grey',
	},
)

const emit = defineEmits<{
	select: [path: string]
}>()

const store = useDesignerStore()

const stageEl = ref<HTMLDivElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const openAngle = ref(0)
const shaderMode = ref<'v1' | 'v2'>('v1')
const activeCameraPreset = ref<'iso' | 'front' | 'exterior' | 'mitre'>('iso')
const webGLSupported = ref(true)

watch([shaderMode, () => props.finishName], () => rebuildSceneDebounced())

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let animFrameId: number | null = null
let resizeObserver: ResizeObserver | null = null

const profileOutlines = ref<Record<string, SectionOutline>>({})
/** Cuts through every panel centre.  Their start/end values are the same
 * deductions used by the manufacturing engine, so they are our 3D placement
 * source rather than guessed frame/sash clearances. */
const sectionCuts = ref<CrossSection[]>([])
const assembly = ref<WindowAssembly | null>(null)
const geometryCache = new Map<string, THREE.BufferGeometry>()
const interactiveMeshes: THREE.Mesh[] = []
const profileInside = new THREE.Color('#8A8F98')
const profileOutside = new THREE.Color('#8A8F98')
let frameMat: THREE.Material | null = null
let selectedFrameMat: THREE.Material | null = null
let glassMat: THREE.Material | null = null
let selectedGlassMat: THREE.Material | null = null
let gasketMat: THREE.Material | null = null
const sashPivots: {
	pivot: THREE.Group
	hinge: string
	opening: string
	initialRotY: number
	initialRotX: number
}[] = []

const raycaster = new THREE.Raycaster()
const mouseVec = new THREE.Vector2()
let pointerDownPos = { x: 0, y: 0 }

const DEFAULT_FRAME_WIDTH = 42
const DEFAULT_FRAME_DEPTH = 60
const DEFAULT_SASH_WIDTH = 50
const DEFAULT_SASH_DEPTH = 55
const DEFAULT_BAR_WIDTH = 40
const DEFAULT_BAR_DEPTH = 60
const GLASS_THICKNESS = 6
const SECTION_DEPTH_REFERENCE_MM = 140

function sectionDepthToWorldZ(depth: number) {
	return SECTION_DEPTH_REFERENCE_MM / 2 - depth
}

function checkWebGL(): boolean {
	try {
		const canvas = document.createElement('canvas')
		return Boolean(
			window.WebGLRenderingContext &&
				(canvas.getContext('webgl') || canvas.getContext('experimental-webgl')),
		)
	} catch {
		return false
	}
}

async function loadOutlines() {
	if (!store.seriesVersion) { rebuildSceneDebounced(); return }
	const mine = ++outlineRequest
	try {
		const { cells } = layoutGeom(props.design)
		const requests = cells.flatMap((cell) => [
			crossSection(props.design, store.seriesVersion, 'h', cell.y + cell.h / 2),
			crossSection(props.design, store.seriesVersion, 'v', cell.x + cell.w / 2),
		])
		const [complete, responses] = await Promise.all([windowAssembly(props.design, store.seriesVersion), Promise.all(requests)])
		if (mine !== outlineRequest) return
		const outlines: Record<string, SectionOutline> = {}
		const cuts: CrossSection[] = []
		for (const res of responses) {
			if (!res.ok) continue
			Object.assign(outlines, res.outlines)
			cuts.push(res.result)
		}
		sectionCuts.value = cuts
		if (complete.ok) {
			assembly.value = complete.result
			profileOutlines.value = { ...outlines, ...complete.outlines }
			rebuildSceneDebounced()
			return
		}
		// Compatibility while a site has not yet received the assembly endpoint.
		assembly.value = null
		profileOutlines.value = outlines
		rebuildSceneDebounced()
	} catch (e) {
		console.warn('[3D] could not load section data', e)
	}
}

function assemblyMember(path: string, role: string) {
	return assembly.value?.members.find((member) => member.path === path && member.role === role)
}
function assemblyPane(path: string) {
	return assembly.value?.panes.find((pane) => pane.path === path)
}

/** Exact profile instance from the same cut the section workspace displays. */
function sectionPieceFor(panel: string, role: string, position: string, profile?: string): SectionPiece | undefined {
	const axis = position === 'B' || position === 'T' ? 'v' : 'h'
	const mirrored = position === 'T' || position === 'R'
	return sectionCuts.value
		.filter((cut) => cut.axis === axis)
		.flatMap((cut) => cut.pieces)
		.find(
			(piece) =>
				piece.kind === 'profile' &&
				(piece.panel === panel || (panel.startsWith('F1.') && piece.panel === 'F1') || (panel === 'F1' && piece.panel.startsWith('F1.'))) &&
				piece.role === role &&
				(!profile || piece.code === profile) &&
				piece.mirrored === mirrored,
		)
}

function getPieceTransform(
	piece: SectionPiece | undefined,
	outline?: SectionOutline | null,
	fallback?: SectionPieceTransform,
	axis?: 'h' | 'v',
	pieceIndex?: number,
): SectionPieceTransform | undefined {
	if (!piece) return fallback
	const sectionMap = props.design.sectionMap ?? {}
	const canonKey = `${piece.role}:${piece.code}`

	let effAxis = axis
	let effIndex = pieceIndex
	if (!effAxis || effIndex === undefined) {
		for (const cut of sectionCuts.value) {
			const idx = cut.pieces.indexOf(piece)
			if (idx >= 0) {
				effAxis = cut.axis
				effIndex = idx
				break
			}
		}
	}

	if (effAxis && effIndex !== undefined) {
		const cut = sectionCuts.value.find((c) => c.axis === effAxis && c.pieces[effIndex!] === piece)
		if (cut) {
			const tags = classifySectionPieceInstances(effAxis, cut.pieces, cut.length)
			const tag = tags[effIndex]
			if (tag && sectionMap[`${effAxis}:${tag}`]) {
				return sectionMap[`${effAxis}:${tag}`]
			}
		}
		if (sectionMap[`${effAxis}:${effIndex}:${canonKey}`]) {
			return sectionMap[`${effAxis}:${effIndex}:${canonKey}`]
		}
	}

	if (sectionMap[canonKey]) return sectionMap[canonKey]
	if (piece.role !== 'bead') {
		for (const k of Object.keys(sectionMap)) {
			if (k.endsWith(`:${canonKey}`)) return sectionMap[k]
		}
		if (sectionMap[piece.role]) return sectionMap[piece.role]
	}
	if (fallback) return fallback
	const base = defaultTransformForPiece(piece, outline ?? (piece.code ? profileOutlines.value[piece.code] : null))
	if (piece.role === 'bead' && props.design.beadOffset) {
		return {
			...base,
			offsetAlong: props.design.beadOffset.along ?? base.offsetAlong,
			offsetDepth: props.design.beadOffset.depth ?? base.offsetDepth,
		}
	}
	return base
}

function sectionPieces(panel: string, role?: string) {
	const seen = new Set<string>()
	return sectionCuts.value.flatMap((cut) => cut.pieces).filter((piece) => {
		const key = `${piece.kind}:${piece.role}:${piece.code}:${piece.start}:${piece.end}:${piece.mirrored}`
		if ((piece.panel !== panel && !(panel.startsWith('F1.') && piece.panel === 'F1')) || (role && piece.role !== role) || seen.has(key)) return false
		seen.add(key)
		return true
	})
}

function sectionSpan(panel: string, role: string, axis: 'h' | 'v'): { min: number; max: number } | null {
	const matchingCuts = sectionCuts.value.filter((cut) => cut.axis === axis)
	const pieces: SectionPiece[] = []
	for (const cut of matchingCuts) {
		cut.pieces.forEach((piece) => {
			if ((piece.panel === panel || (panel.startsWith('F1.') && piece.panel === 'F1')) && piece.role === role) {
				pieces.push(piece)
			}
		})
	}
	if (!pieces.length) return null

	const allCoords = pieces.flatMap((p) => [p.start, p.end])
	return {
		min: Math.min(...allCoords),
		max: Math.max(...allCoords),
	}
}

function profileFaceWidth(code: string | undefined, role: string, fallback: number) {
	if (!code) return fallback
	const pieces = sectionCuts.value.flatMap((cut) => cut.pieces).filter((p) => p.role === role && p.code === code)
	return pieces.length ? Math.max(...pieces.map((p) => p.end - p.start)) : profileOutlines.value[code]?.width || fallback
}

// ---------------------------------------------------------------------------
// 3D Geometry Generation (Profile Shape -> Extrusion -> 45° Mitre Offset)
// ---------------------------------------------------------------------------

interface ProfileShapeData {
	/** Section loops in the only renderer convention: (depth, u). */
	loops: THREE.Vector2[][]
	faceWidth: number
	depth: number
	depthOffset: number
	/** Signed local-u translation from the section editor. */
	alongOffset: number
	cacheId: string
}

function buildProfileShape(
	outline: SectionOutline | undefined,
	fallbackW: number,
	fallbackD: number,
	transform?: SectionPieceTransform,
	mirrored = false,
): ProfileShapeData {
	const rawW = outline?.width && outline.width > 0 ? outline.width : fallbackW
	const rawD = outline?.depth && outline.depth > 0 ? outline.depth : fallbackD

	const rings = parseSvgRings(outline?.svg, rawW, rawD)
	// The section editor already puts SVG x = 0 on the outer plan edge and
	// SVG y = 0 (top of the drawing) on the exterior. Rail yaw turns that
	// same section onto T and R. A second 180° flips the rebate outward and
	// measures the mitre from the inner edge, so the corner spikes and the
	// two rails intersect.
	const rot = (((transform?.rotation || 0) % 360) + 360) % 360
	const flipX = Boolean(transform?.flipX)
	const flipY = Boolean(transform?.flipY)
	const cx = transform?.originU ?? rawW / 2
	const cy = transform?.originDepth ?? rawD / 2

	const transformedRings = rings.map((ring) =>
		ring.map((p) => {
			let x = p.x - cx
			let y = p.y - cy
			if (flipX) x = -x
			if (flipY) y = -y
			if (rot === 90) [x, y] = [-y, x]
			else if (rot === 180) [x, y] = [-x, -y]
			else if (rot === 270) [x, y] = [y, -x]
			return { u: x + cx, d: y + cy }
		}),
	)

	let minU = Infinity
	let maxU = -Infinity
	let minD = Infinity
	let maxD = -Infinity
	for (const ring of transformedRings) {
		for (const p of ring) {
			if (p.u < minU) minU = p.u
			if (p.u > maxU) maxU = p.u
			if (p.d < minD) minD = p.d
			if (p.d > maxD) maxD = p.d
		}
	}

	const depthOffset = transform?.offsetDepth || 0

	let outerIdx = 0
	let maxArea = -1
	const areas = transformedRings.map((r) => {
		let a = 0
		for (let i = 0; i < r.length; i++) {
			const j = (i + 1) % r.length
			a += r[i].u * r[j].d - r[j].u * r[i].d
		}
		return Math.abs(a) / 2
	})
	for (let i = 0; i < areas.length; i++) {
		if (areas[i] > maxArea) {
			maxArea = areas[i]
			outerIdx = i
		}
	}

	// Shape X is section depth; Shape Y is u from the outer plan edge.  This
	// is intentionally the inverse of stored SVG (x = face/u, y = depth).
	const ordered = [transformedRings[outerIdx], ...transformedRings.filter((_, i) => i !== outerIdx)]
	const loops = ordered.map((ring) => ring.map((p) => new THREE.Vector2(p.d, p.u - minU)))

	return {
		loops,
		faceWidth: maxU > minU ? maxU - minU : rawW,
		depth: maxD > minD ? maxD - minD : rawD,
		depthOffset,
		// The section editor negates offsetAlong on a mirrored piece. Do the
		// same here. Do not also mirror the outline; the rail yaw already
		// points +u into the opening.
		alongOffset: (mirrored ? -1 : 1) * (transform?.offsetAlong || 0),
		cacheId: `${outline?.svg ?? `fallback:${rawW}x${rawD}`}:${rot}:${flipX ? 1 : 0}:${flipY ? 1 : 0}:${depthOffset}`,
	}
}

function shapeOf(loops: THREE.Vector2[][]): THREE.Shape {
	const [outer, ...holes] = loops
	const shape = new THREE.Shape(outer)
	for (const hole of holes) shape.holes.push(new THREE.Path(hole))
	return shape
}

const aoCache = new Map<string, SectionAO>()

function getOrCreateAO(shapeData: ProfileShapeData): SectionAO {
	const cached = aoCache.get(shapeData.cacheId)
	if (cached) return cached
	const loops = shapeData.loops.map((loop) => loop.map((p) => ({ x: p.x, y: p.y })))
	const ao = createSectionAO(loops, {
		rays: 16,
		maxDist: 14,
		strength: 0.75,
		falloff: 1,
	})
	aoCache.set(shapeData.cacheId, ao)
	return ao
}

function paintProfileColors(
	geom: THREE.BufferGeometry,
	inside: THREE.Color,
	outside: THREE.Color,
	shapeData?: ProfileShapeData,
) {
	const pos = geom.getAttribute('position')
	const norm = geom.getAttribute('normal')
	let zMin = Infinity
	let zMax = -Infinity
	for (let i = 0; i < pos.count; i++) {
		const z = pos.getZ(i)
		if (z < zMin) zMin = z
		if (z > zMax) zMax = z
	}
	const colors = new Float32Array(pos.count * 3)
	const color = new THREE.Color()
	const span = zMax - zMin || 1

	let ao: SectionAO | null = null
	if (shapeData && shapeData.loops && shapeData.loops.length > 0) {
		ao = getOrCreateAO(shapeData)
	}

	const depthTotal = SECTION_DEPTH_REFERENCE_MM
	const depthOffset = shapeData?.depthOffset ?? 0

	for (let i = 0; i < pos.count; i++) {
		color.copy(inside).lerp(outside, (pos.getZ(i) - zMin) / span)
		if (ao && norm) {
			const u = pos.getY(i)
			const depth = depthTotal / 2 - depthOffset - pos.getZ(i)
			const nx = -norm.getZ(i)
			const ny = norm.getY(i)
			const factor = ao(depth, u, nx, ny)
			color.multiplyScalar(factor)
		}
		colors[i * 3] = color.r
		colors[i * 3 + 1] = color.g
		colors[i * 3 + 2] = color.b
	}
	geom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
}

function getExtrudedMemberGeometry(
	shapeData: ProfileShapeData,
	length: number,
	isMitred = true,
	cacheKey?: string,
	colors?: { inside: THREE.Color; outside: THREE.Color },
	mitreStart = 0,
	mitreEnd = 0,
): THREE.BufferGeometry {
	const inside = colors?.inside ?? profileInside
	const outside = colors?.outside ?? profileOutside
	const key = cacheKey
		? `${cacheKey}:${shapeData.cacheId}:${Math.round(length)}:${isMitred ? 'm' : 's'}:${Math.round(mitreStart * 100)}:${Math.round(mitreEnd * 100)}:${inside.getHexString()}:${outside.getHexString()}`
		: null
	if (key && geometryCache.has(key)) {
		return geometryCache.get(key)!
	}

	const geom = new THREE.ExtrudeGeometry(shapeOf(shapeData.loops), {
		depth: length,
		steps: 1,
		bevelEnabled: false,
	})

	// ExtrudeGeometry starts as (depth, u, length).  Move the caps for mitres
	// then remap once to (length, u, global wall depth), exactly as a ring rail
	// is physically oriented before its Z rotation.
	const pos = geom.getAttribute('position')
	const depthTotal = SECTION_DEPTH_REFERENCE_MM
	let zMin = Infinity
	let zMax = -Infinity
	for (let i = 0; i < pos.count; i++) {
		const z = pos.getZ(i)
		if (z < zMin) zMin = z
		if (z > zMax) zMax = z
	}
	const zMid = (zMin + zMax) / 2
	// Past the shared 45° plane just enough that the two caps overlap instead
	// of leaving a hairline crack. The outer corner only grows by this amount.
	const mitreOverlap = 0.8
	for (let i = 0; i < pos.count; i++) {
		const depth = pos.getX(i)
		const u = pos.getY(i)
		const z = pos.getZ(i)
		let t = z
		if (isMitred) {
			// Anchor each 45° cut to the neighbouring rail's inward offset at
			// that corner. Adjacent rails can have different section transforms.
			t = z <= zMid
				? u + mitreStart - mitreOverlap
				: length - u - mitreEnd + mitreOverlap
		}
		pos.setXYZ(i, t, u, depthTotal / 2 - (depth + shapeData.depthOffset))
	}
	pos.needsUpdate = true

	geom.computeVertexNormals()
	const creased = toCreasedNormals(geom, THREE.MathUtils.degToRad(32))
	paintProfileColors(creased, inside, outside, shapeData)
	if (key) {
		geometryCache.set(key, creased)
	}
	return creased
}

// ---------------------------------------------------------------------------
// 3D Ring Assembly (Bottom, Top, Left, Right mitred 45° members)
// ---------------------------------------------------------------------------

function createMitredRing(
	box: { x0: number; y0: number; w: number; h: number },
	shapeData: ProfileShapeData,
	material: THREE.Material,
	path = 'FRAME',
	cachePrefix = 'frame',
	colors?: { inside: THREE.Color; outside: THREE.Color },
): THREE.Group {
	const group = new THREE.Group()
	group.name = path
	const kind = path.startsWith('GASKET') ? 'gasket' : path.startsWith('BEAD') ? 'bead' : 'member'

	const geomH = getExtrudedMemberGeometry(shapeData, box.w, true, `${cachePrefix}:h`, colors)
	const geomV = getExtrudedMemberGeometry(shapeData, box.h, true, `${cachePrefix}:v`, colors)
	const place = (mesh: THREE.Mesh, x: number, y: number, rotation: number) => {
		mesh.position.set(x, y, 0)
		mesh.rotation.z = rotation
		mesh.userData = { path, kind }
	}

	// 1. Bottom rail ('B')
	const meshB = new THREE.Mesh(geomH, material)
	place(meshB, box.x0, box.y0, 0)
	meshB.castShadow = true
	meshB.receiveShadow = true
	group.add(meshB)
	interactiveMeshes.push(meshB)

	// 2. Top rail ('T')
	const meshT = new THREE.Mesh(geomH, material)
	place(meshT, box.x0 + box.w, box.y0 + box.h, Math.PI)
	meshT.castShadow = true
	meshT.receiveShadow = true
	group.add(meshT)
	interactiveMeshes.push(meshT)

	// 3. Left jamb ('L')
	const meshL = new THREE.Mesh(geomV, material)
	place(meshL, box.x0, box.y0 + box.h, -Math.PI / 2)
	meshL.castShadow = true
	meshL.receiveShadow = true
	group.add(meshL)
	interactiveMeshes.push(meshL)

	// 4. Right jamb ('R')
	const meshR = new THREE.Mesh(geomV, material)
	place(meshR, box.x0 + box.w, box.y0, Math.PI / 2)
	meshR.castShadow = true
	meshR.receiveShadow = true
	group.add(meshR)
	interactiveMeshes.push(meshR)

	return group
}

/**
 * A ring whose four rails are four real section instances.  B-B supplies the
 * two vertical rails, A-A supplies the horizontal rails.  This is deliberately
 * not a "profile repeated four times": the section editor's mirrored pieces,
 * transforms and offsets are retained for each physical side.
 */
function createSectionRing(
	box: { x0: number; y0: number; w: number; h: number },
	sides: Record<'B' | 'R' | 'T' | 'L', ProfileShapeData>,
	material: THREE.Material,
	path: string,
	cachePrefix: string,
	colors?: { inside: THREE.Color; outside: THREE.Color },
): THREE.Group {
	const group = new THREE.Group()
	group.name = path
	const kind = path.startsWith('GASKET') ? 'gasket' : path.startsWith('BEAD') ? 'bead' : 'member'
	const definitions: { side: 'B' | 'R' | 'T' | 'L'; x: number; y: number; rotation: number; length: number }[] = [
		{ side: 'B', x: box.x0, y: box.y0, rotation: 0, length: box.w },
		{ side: 'R', x: box.x0 + box.w, y: box.y0, rotation: Math.PI / 2, length: box.h },
		{ side: 'T', x: box.x0 + box.w, y: box.y0 + box.h, rotation: Math.PI, length: box.w },
		{ side: 'L', x: box.x0, y: box.y0 + box.h, rotation: -Math.PI / 2, length: box.h },
	]
	const neighbours = {
		B: { start: 'L', end: 'R' },
		R: { start: 'B', end: 'T' },
		T: { start: 'R', end: 'L' },
		L: { start: 'T', end: 'B' },
	} as const
	for (const def of definitions) {
		const neighbour = neighbours[def.side]
		const mesh = new THREE.Mesh(
			getExtrudedMemberGeometry(
				sides[def.side],
				def.length,
				true,
				`${cachePrefix}:${def.side}`,
				colors,
				sides[neighbour.start].alongOffset,
				sides[neighbour.end].alongOffset,
			),
			material,
		)
		// Local +u is the direction into the opening.  Offset it exactly as the
		// B-B/A-A editor does, after each rail's orientation is established.
		const u = sides[def.side].alongOffset
		mesh.position.set(def.x - Math.sin(def.rotation) * u, def.y + Math.cos(def.rotation) * u, 0)
		mesh.rotation.z = def.rotation
		mesh.userData = { path, part: def.side, kind }
		mesh.castShadow = true
		mesh.receiveShadow = true
		group.add(mesh)
		interactiveMeshes.push(mesh)
	}
	return group
}

// ---------------------------------------------------------------------------
// Bars (Mullions & Transoms)
// ---------------------------------------------------------------------------

function createBarMember(
	bar: { id: string; dir: 'v' | 'h'; x: number; y: number; length: number },
	shapeData: ProfileShapeData,
	material: THREE.Material,
	frameFace: number,
	zOffset = 0,
	colors?: { inside: THREE.Color; outside: THREE.Color },
): THREE.Mesh {
	const geom = getExtrudedMemberGeometry(shapeData, bar.length, false, `bar:${bar.id}`, colors)
	const mesh = new THREE.Mesh(geom, material)
	mesh.matrixAutoUpdate = false
	mesh.name = bar.id
	mesh.userData = { path: bar.id, kind: 'bar' }
	mesh.castShadow = true
	mesh.receiveShadow = true

	const halfW = shapeData.faceWidth / 2
	const along = shapeData.alongOffset || 0
	if (bar.dir === 'v') {
		// Local length (+X) rotates into +Y; local u (+Y) faces left.
		mesh.matrixAutoUpdate = true
		mesh.position.set(bar.x + halfW - along, bar.y, zOffset)
		mesh.rotation.z = Math.PI / 2
	} else {
		mesh.matrixAutoUpdate = true
		mesh.position.set(bar.x, bar.y - halfW + along, zOffset)
	}

	interactiveMeshes.push(mesh)
	return mesh
}

// ---------------------------------------------------------------------------
// Glass Pane Construction
// ---------------------------------------------------------------------------

function createGlassMesh(
	w: number,
	h: number,
	thickness = GLASS_THICKNESS,
	material: THREE.Material,
	path: string,
): THREE.Mesh {
	const geom = new THREE.BoxGeometry(Math.max(2, w), Math.max(2, h), thickness)
	const mesh = new THREE.Mesh(geom, material)
	mesh.userData = { path, kind: 'glass' }
	mesh.castShadow = false
	mesh.receiveShadow = true
	interactiveMeshes.push(mesh)
	return mesh
}

// ---------------------------------------------------------------------------
// Casement Hardware (Handle Marker)
// ---------------------------------------------------------------------------

function createHandleMesh(material: THREE.Material): THREE.Mesh {
	// A small subtle rectangular marker/indicator on the sash stile instead of a bulky lever
	const geom = new THREE.BoxGeometry(4, 22, 2.5)
	const mesh = new THREE.Mesh(geom, material)
	mesh.castShadow = true
	mesh.receiveShadow = true
	return mesh
}

// ---------------------------------------------------------------------------
// Scene Rebuild
// ---------------------------------------------------------------------------

let rebuildTimer: ReturnType<typeof setTimeout> | undefined
let outlineTimer: ReturnType<typeof setTimeout> | undefined
let outlineRequest = 0
let animatedOpenAngle = 0
let hasFramedOnce = false

function rebuildSceneDebounced() {
	clearTimeout(rebuildTimer)
	rebuildTimer = setTimeout(() => rebuild3DWindow(), 80)
}

function loadOutlinesDebounced() {
	clearTimeout(outlineTimer)
	outlineTimer = setTimeout(() => void loadOutlines(), 100)
}

function disposeWindowObject(object: THREE.Object3D) {
	const cached = new Set(geometryCache.values())
	const disposedMaterials = new Set<THREE.Material>()
	object.traverse((child) => {
		if (!(child instanceof THREE.Mesh)) return
		if (!cached.has(child.geometry)) child.geometry.dispose()
		for (const material of Array.isArray(child.material) ? child.material : [child.material]) {
			if (!disposedMaterials.has(material)) { material.dispose(); disposedMaterials.add(material) }
		}
	})
}

function createMaterials() {
	const frame = new THREE.MeshStandardMaterial({
		color: 0xffffff,
		vertexColors: true,
		roughness: 0.58,
		metalness: 0.18,
		side: THREE.DoubleSide,
	})
	const selectedFrame = new THREE.MeshStandardMaterial({
		color: 0xffffff,
		vertexColors: true,
		emissive: new THREE.Color(0x2563eb),
		emissiveIntensity: 0.45,
		roughness: 0.45,
		metalness: 0.2,
		side: THREE.DoubleSide,
	})
	const glass = new THREE.MeshStandardMaterial({
		color: new THREE.Color(0xbae6fd),
		roughness: 0.1,
		metalness: 0.05,
		transparent: true,
		opacity: 0.45,
		depthWrite: false,
		side: THREE.DoubleSide,
	})
	const selectedGlass = new THREE.MeshStandardMaterial({
		color: new THREE.Color(0x93c5fd),
		emissive: new THREE.Color(0x3b82f6),
		emissiveIntensity: 0.35,
		roughness: 0.1,
		transparent: true,
		opacity: 0.6,
		depthWrite: false,
		side: THREE.DoubleSide,
	})
	const gasket = new THREE.MeshStandardMaterial({
		color: 0x20252b,
		roughness: 0.85,
		metalness: 0,
		side: THREE.DoubleSide,
	})
	const hardware = new THREE.MeshStandardMaterial({
		color: new THREE.Color(0x1e293b),
		roughness: 0.4,
		metalness: 0.5,
	})
	return { frame, selectedFrame, glass, selectedGlass, gasket, hardware }
}

function rebuild3DWindow() {
	if (!scene) return

	// Clear previous model objects
	const toRemove = scene.children.filter((c) => c.name === 'window-root')
	for (const obj of toRemove) {
		disposeWindowObject(obj)
		scene.remove(obj)
	}
	interactiveMeshes.length = 0
	sashPivots.length = 0

	const rootGroup = new THREE.Group()
	rootGroup.name = 'window-root'
	// The plan is drawn from inside (+X to the right).  Mirror the assembled
	// exterior-space model once, rather than mirroring individual rails.
	rootGroup.scale.x = -1
	rootGroup.position.x = props.design.width
	scene.add(rootGroup)

	const design = props.design
	const geom = layoutGeom(design)
	const sectionMap = design.sectionMap ?? {}
	const transformFor = (piece: SectionPiece | undefined, outline: SectionOutline | undefined, fallback: SectionPieceTransform | undefined) => {
		return getPieceTransform(piece, outline, fallback)
	}
	const sideShape = (panel: string, role: string, position: 'B' | 'R' | 'T' | 'L', profile: string | undefined, outline: SectionOutline | undefined, fallbackW: number, fallbackD: number, fallback?: SectionPieceTransform) => {
		const piece = profile ? sectionPieceFor(panel, role, position, profile) : undefined
		const posAxis = position === 'B' || position === 'T' ? 'v' : 'h'
		const transform = getPieceTransform(piece, outline, fallback, posAxis)
		return buildProfileShape(
			outline, fallbackW, fallbackD, transform,
			Boolean(piece?.mirrored ?? (position === 'T' || position === 'R')),
		)
	}

	const frameHex = /^#[0-9a-f]{6}$/i.test(props.finishColor ?? '') ? props.finishColor! : '#8A8F98'
	const outsideHex = /^#[0-9a-f]{6}$/i.test(props.outsideFinishColor ?? '') ? props.outsideFinishColor! : frameHex

	const v2 = shaderMode.value === 'v2'
	const finish = identifyFinish(props.finishName)
	// V2: wood and mill carry their own colour; grey/generic still use the swatch.
	profileInside.set(v2 ? finishVertexTint(finish, frameHex) : frameHex)
	profileOutside.set(v2 ? finishVertexTint(finish, outsideHex) : outsideHex)
	const profileColors = { inside: profileInside, outside: profileOutside }

	const mats = v2 ? createV2Materials(props.finishName) : createMaterials()
	frameMat = mats.frame
	selectedFrameMat = mats.selectedFrame
	glassMat = mats.glass
	selectedGlassMat = mats.selectedGlass
	gasketMat = mats.gasket
	const hardwareMat = mats.hardware

	// 1. Resolve Frame Profile & Build Outer Frame Ring
	const frameCode = design.frameProfileId || design.profiles?.frame || store.seriesInfo?.role_defaults?.frame
	const frameOutline = frameCode ? profileOutlines.value[frameCode] : undefined
	const frameFaceWidth = profileFaceWidth(frameCode, 'frame', frameOutline?.width || DEFAULT_FRAME_WIDTH)
	const frameSides = {
		B: sideShape('F1', 'frame', 'B', frameCode, frameOutline, frameFaceWidth, DEFAULT_FRAME_DEPTH),
		R: sideShape('F1', 'frame', 'R', frameCode, frameOutline, frameFaceWidth, DEFAULT_FRAME_DEPTH),
		T: sideShape('F1', 'frame', 'T', frameCode, frameOutline, frameFaceWidth, DEFAULT_FRAME_DEPTH),
		L: sideShape('F1', 'frame', 'L', frameCode, frameOutline, frameFaceWidth, DEFAULT_FRAME_DEPTH),
	}
	const frameShape = frameSides.B
	const outerRingGroup = createSectionRing(
		{ x0: 0, y0: 0, w: design.width, h: design.height },
		frameSides,
		frameMat!,
		'FRAME',
		`frame:${frameCode || 'default'}`,
		profileColors,
	)
	rootGroup.add(outerRingGroup)

	// 2. Mullions and Transoms (Bars)
	for (const bar of geom.bars) {
		const barRole = bar.dir === 'v' ? 'mullion' : 'transom'
		const barCode = design.profiles?.[bar.id] || store.seriesInfo?.role_defaults?.[barRole]
		const barOutline = barCode ? profileOutlines.value[barCode] : undefined
		const barFaceWidth = profileFaceWidth(barCode, barRole, barOutline?.width || DEFAULT_BAR_WIDTH)
		const barPiece = sectionPieces(bar.id, barRole)[0]
		const barTransform = transformFor(
			barPiece,
			barOutline,
			sectionMap[`${barRole}:${barCode}`] || sectionMap[bar.id] || sectionMap[barRole],
		)

		const effectiveBarTransform = {
			...(barTransform || { offsetAlong: 0, offsetDepth: 0, rotation: 0, flipX: false, flipY: false }),
			offsetDepth: barTransform?.offsetDepth || 0,
		}
		const barShape = buildProfileShape(barOutline, barFaceWidth, DEFAULT_BAR_DEPTH, effectiveBarTransform)
		// Bars terminate at the frame's inner face.  Layout gives their design
		// span centre-to-centre; the section profile gives the frame take-up.
		// Do not run an extrusion through the frame and hide it with overlap.
		const placedBar = assemblyMember(bar.id, barRole)
		const innerBar = bar.dir === 'v'
			? { ...bar, y: placedBar?.y ?? bar.y + frameShape.faceWidth, length: placedBar?.length ?? Math.max(1, bar.length - 2 * frameShape.faceWidth) }
			: { ...bar, x: placedBar?.x ?? bar.x + frameShape.faceWidth, length: placedBar?.length ?? Math.max(1, bar.length - 2 * frameShape.faceWidth) }
		const barMesh = createBarMember(
			innerBar,
			barShape,
			frameMat!,
			frameShape.faceWidth,
			0,
			profileColors,
		)
		rootGroup.add(barMesh)
	}

	// 3. Cells (Sashes, Fixed Glass, Louvers)
	for (const cell of geom.cells) {
		if (cell.node.type === 'sash') {
			const sashNode = cell.node as SashNode
			const sashCode = sashNode.profile || design.profiles?.[cell.path] || store.seriesInfo?.role_defaults?.sash
			const sashOutline = sashCode ? profileOutlines.value[sashCode] : undefined
			const sashFaceWidth = profileFaceWidth(sashCode, 'sash', sashOutline?.width || DEFAULT_SASH_WIDTH)
			// Cut pieces are keyed by panel (F1-S1), not the design path (F1.0).
			const sashPanel = panelFor(cell.path, 'sash')

			// The section engine has already made all side deductions.  A B-B cut
			// supplies X bounds and an A-A cut supplies Y bounds for this sash.
			const sashXSpan = sectionSpan(sashPanel, 'sash', 'h')
			const sashYSpan = sectionSpan(sashPanel, 'sash', 'v')
			const sashAssembly = assemblyMember(cell.path, 'sash')
			const l = cell.x === 0 ? frameShape.faceWidth : DEFAULT_BAR_WIDTH / 2
			const b = cell.y === 0 ? frameShape.faceWidth : DEFAULT_BAR_WIDTH / 2
			const sashX = sashAssembly?.x ?? sashXSpan?.min ?? cell.x + l
			const sashY = sashAssembly?.y ?? sashYSpan?.min ?? cell.y + b
			const sashW = Math.max(20, sashAssembly?.width ?? (sashXSpan ? sashXSpan.max - sashXSpan.min : cell.w - 2 * l))
			const sashH = Math.max(20, sashAssembly?.height ?? (sashYSpan ? sashYSpan.max - sashYSpan.min : cell.h - 2 * b))
			// `buildProfileShape` already applies the section depth transform;
			// keeping the pivot at zero avoids applying it twice when swinging.
			const sashZ = 0

			const sashSides = {
				B: sideShape(sashPanel, 'sash', 'B', sashCode, sashOutline, sashFaceWidth, DEFAULT_SASH_DEPTH, sectionMap[cell.path]),
				R: sideShape(sashPanel, 'sash', 'R', sashCode, sashOutline, sashFaceWidth, DEFAULT_SASH_DEPTH, sectionMap[cell.path]),
				T: sideShape(sashPanel, 'sash', 'T', sashCode, sashOutline, sashFaceWidth, DEFAULT_SASH_DEPTH, sectionMap[cell.path]),
				L: sideShape(sashPanel, 'sash', 'L', sashCode, sashOutline, sashFaceWidth, DEFAULT_SASH_DEPTH, sectionMap[cell.path]),
			}
			const sashShape = sashSides.B

			// Sash Group containing mitred frame, glass, and handle
			const sashGroup = new THREE.Group()
			sashGroup.name = `sash-group:${cell.path}`

			const sashRing = createSectionRing(
				{ x0: 0, y0: 0, w: sashW, h: sashH },
				sashSides,
				frameMat!,
				cell.path,
				`sash:${sashCode || 'default'}`,
				profileColors,
			)
			sashGroup.add(sashRing)

			// Internal Sash Glass
			const glassPiece = findGlassPieceForCell(cell)
			const glassTransform = getGlassTransformForCell(cell, glassPiece)
			const glassXSpan = sectionSpan(sashPanel, 'glass', 'h')
			const glassYSpan = sectionSpan(sashPanel, 'glass', 'v')
			const paneAssembly = assemblyPane(cell.path)
			const glassW = Math.max(10, paneAssembly?.width ?? (glassXSpan ? glassXSpan.max - glassXSpan.min : sashW - 2 * sashShape.faceWidth))
			const glassH = Math.max(10, paneAssembly?.height ?? (glassYSpan ? glassYSpan.max - glassYSpan.min : sashH - 2 * sashShape.faceWidth))
			const glassThickness = glassPiece?.thickness || GLASS_THICKNESS
			const glassMesh = createGlassMesh(
				glassW,
				glassH,
				glassThickness,
				glassMat!,
				`GLASS:${cell.path}`,
			)
			const beadOffsetDepth = Number(props.design.beadOffset?.depth ?? 23)
			const defaultGlassDepth = Math.max(14, beadOffsetDepth - glassThickness / 2)
			const effGlassDepth =
				glassTransform?.offsetDepth !== undefined && glassTransform.offsetDepth !== 0
					? glassTransform.offsetDepth
					: defaultGlassDepth

			glassMesh.position.set(
				paneAssembly ? paneAssembly.x + paneAssembly.width / 2 - sashX : glassXSpan ? (glassXSpan.min + glassXSpan.max) / 2 - sashX : sashW / 2,
				paneAssembly ? paneAssembly.y + paneAssembly.height / 2 - sashY : glassYSpan ? (glassYSpan.min + glassYSpan.max) / 2 - sashY : sashH / 2,
				sectionDepthToWorldZ(effGlassDepth),
			)
			sashGroup.add(glassMesh)

			// Beads/gaskets are real catalog profiles too.  Their section
			// cuts define the 4-sided ring around the pane.
			for (const role of ['bead', 'gasket']) {
				const beadPanel = panelFor(cell.path, role)
				const bead = sectionPieces(beadPanel, role)[0]
				const bx = sectionSpan(beadPanel, role, 'h')
				const by = sectionSpan(beadPanel, role, 'v')
				if (!bead || !bx || !by) continue
				const outline = profileOutlines.value[bead.code]
				const beadFaceWidth = profileFaceWidth(bead.code, role, 12)
				const beadSides = {
					B: sideShape(beadPanel, role, 'B', bead.code, outline, beadFaceWidth, DEFAULT_SASH_DEPTH),
					R: sideShape(beadPanel, role, 'R', bead.code, outline, beadFaceWidth, DEFAULT_SASH_DEPTH),
					T: sideShape(beadPanel, role, 'T', bead.code, outline, beadFaceWidth, DEFAULT_SASH_DEPTH),
					L: sideShape(beadPanel, role, 'L', bead.code, outline, beadFaceWidth, DEFAULT_SASH_DEPTH),
				}
				const gasketColors = { inside: new THREE.Color(0x20252b), outside: new THREE.Color(0x20252b) }
				const beadRing = createSectionRing(
					{ x0: bx.min - sashX, y0: by.min - sashY, w: bx.max - bx.min, h: by.max - by.min },
					beadSides,
					role === 'gasket' ? gasketMat! : frameMat!,
					`${role.toUpperCase()}:${cell.path}`,
					`${role}:${bead.code}`,
					role === 'gasket' ? gasketColors : profileColors,
				)
				sashGroup.add(beadRing)
			}

			// Casement Handle Marker on closing stile (opposite side of hinge)
			const handleMesh = createHandleMesh(hardwareMat)
			const isLeftHinge = (sashNode.hinge || 'left') === 'left'
			const stileInset = sashShape.faceWidth / 2
			let handleX = isLeftHinge ? sashW - stileInset : stileInset
			let handleY = sashH / 2
			if (sashNode.hinge === 'top') {
				handleX = sashW / 2
				handleY = stileInset
				handleMesh.rotation.z = Math.PI / 2
			} else {
				const targetY = typeof sashNode.ghh === 'number' && sashNode.ghh > 0
					? Math.max(sashShape.faceWidth + 20, Math.min(sashH - sashShape.faceWidth - 20, sashNode.ghh - sashY))
					: sashH / 2
				handleY = targetY
			}
			const interiorZ = sectionDepthToWorldZ(sashShape.depth + sashShape.depthOffset) - 1.25
			handleMesh.position.set(handleX, handleY, interiorZ)
			sashGroup.add(handleMesh)

			// Pivot setup for swing opening animation
			const hinge = sashNode.hinge || 'left'
			const opening = sashNode.opening || 'out'
			const pivotGroup = new THREE.Group()

			if (hinge === 'left') {
				pivotGroup.position.set(sashX, sashY, sashZ)
				sashGroup.position.set(0, 0, 0)
			} else if (hinge === 'right') {
				pivotGroup.position.set(sashX + sashW, sashY, sashZ)
				sashGroup.position.set(-sashW, 0, 0)
			} else if (hinge === 'top') {
				pivotGroup.position.set(sashX, sashY + sashH, sashZ)
				sashGroup.position.set(0, -sashH, 0)
			} else {
				pivotGroup.position.set(sashX, sashY, sashZ)
				sashGroup.position.set(0, 0, 0)
			}

			pivotGroup.add(sashGroup)
			rootGroup.add(pivotGroup)

			sashPivots.push({
				pivot: pivotGroup,
				hinge,
				opening,
				initialRotY: pivotGroup.rotation.y,
				initialRotX: pivotGroup.rotation.x,
			})
		} else {
			// Fixed Glass or Louver Cell. Fixed panes share panel F1.
			const paneAssembly = assemblyPane(cell.path)
			const glassPiece = findGlassPieceForCell(cell)
			const glassTransform = getGlassTransformForCell(cell, glassPiece)
			const glassPanel = panelFor(cell.path, 'glass')
			const glassXSpan = sectionSpan(glassPanel, 'glass', 'h')
			const glassYSpan = sectionSpan(glassPanel, 'glass', 'v')
			const l = cell.x === 0 ? frameShape.faceWidth : DEFAULT_BAR_WIDTH / 2
			const b = cell.y === 0 ? frameShape.faceWidth : DEFAULT_BAR_WIDTH / 2
			const cellW = Math.max(10, paneAssembly?.width ?? (glassXSpan ? glassXSpan.max - glassXSpan.min : cell.w - 2 * l))
			const cellH = Math.max(10, paneAssembly?.height ?? (glassYSpan ? glassYSpan.max - glassYSpan.min : cell.h - 2 * b))
			const glassThickness = glassPiece?.thickness || GLASS_THICKNESS
			const glassMesh = createGlassMesh(
				cellW,
				cellH,
				glassThickness,
				glassMat!,
				`GLASS:${cell.path}`,
			)

			const beadOffsetDepth = Number(props.design.beadOffset?.depth ?? 23)
			const defaultGlassDepth = Math.max(14, beadOffsetDepth - glassThickness / 2)
			const effGlassDepth =
				glassTransform?.offsetDepth !== undefined && glassTransform.offsetDepth !== 0
					? glassTransform.offsetDepth
					: defaultGlassDepth

			glassMesh.position.set(
				paneAssembly ? paneAssembly.x + paneAssembly.width / 2 : glassXSpan ? (glassXSpan.min + glassXSpan.max) / 2 : cell.x + cell.w / 2,
				paneAssembly ? paneAssembly.y + paneAssembly.height / 2 : glassYSpan ? (glassYSpan.min + glassYSpan.max) / 2 : cell.y + cell.h / 2,
				sectionDepthToWorldZ(effGlassDepth),
			)
			rootGroup.add(glassMesh)

			for (const role of ['bead', 'gasket']) {
				const beadPanel = panelFor(cell.path, role)
				const bead = sectionPieces(beadPanel, role)[0]
				const bx = sectionSpan(beadPanel, role, 'h')
				const by = sectionSpan(beadPanel, role, 'v')
				if (!bead || !bx || !by) continue
				const outline = profileOutlines.value[bead.code]
				const beadFaceWidth = profileFaceWidth(bead.code, role, 12)
				const beadSides = {
					B: sideShape(beadPanel, role, 'B', bead.code, outline, beadFaceWidth, DEFAULT_SASH_DEPTH),
					R: sideShape(beadPanel, role, 'R', bead.code, outline, beadFaceWidth, DEFAULT_SASH_DEPTH),
					T: sideShape(beadPanel, role, 'T', bead.code, outline, beadFaceWidth, DEFAULT_SASH_DEPTH),
					L: sideShape(beadPanel, role, 'L', bead.code, outline, beadFaceWidth, DEFAULT_SASH_DEPTH),
				}
				const gasketColors = { inside: new THREE.Color(0x20252b), outside: new THREE.Color(0x20252b) }
				rootGroup.add(createSectionRing(
					{ x0: bx.min, y0: by.min, w: bx.max - bx.min, h: by.max - by.min },
					beadSides,
					role === 'gasket' ? gasketMat! : frameMat!,
					`${role.toUpperCase()}:${cell.path}`,
					`${role}:${bead.code}`,
					role === 'gasket' ? gasketColors : profileColors,
				))
			}

			// Louver blades if louver
			if (cell.node.type === 'louver') {
				const blades = (cell.node as LeafNode).blades || 7
				const bladeH = cellH / blades
				const bladeMat = new THREE.MeshStandardMaterial({
					color: new THREE.Color(0x94a3b8),
					roughness: 0.5,
					transparent: true,
					opacity: 0.8,
					side: THREE.DoubleSide,
				})
				for (let i = 0; i < blades; i++) {
					const bladeGeom = new THREE.BoxGeometry(cellW - 8, bladeH * 0.9, 4)
					const bladeMesh = new THREE.Mesh(bladeGeom, bladeMat)
					bladeMesh.position.set(
						glassMesh.position.x,
						glassMesh.position.y - cellH / 2 + i * bladeH + bladeH / 2,
						4,
					)
					bladeMesh.rotation.x = THREE.MathUtils.degToRad(32)
					rootGroup.add(bladeMesh)
				}
			}
		}
	}

	updateSashOpeningAngles()
	highlightSelection()
	// Only frame camera on first mount; preserving user orbit/zoom during design & profile edits
	if (!hasFramedOnce) {
		setCameraPreset(activeCameraPreset.value)
		hasFramedOnce = true
	}
}

function panelFor(path: string, role: string): string {
	const members = assembly.value?.members ?? []
	const exact = members.find((member) => member.path === path && member.role === role)
	if (exact) return exact.panel
	// Sash glass, bead and gasket are cut on the sash panel (F1-S1), not the cell path (F1.0).
	// Fixed panes share panel F1, so they stay on the cell path and do not merge into one span.
	const sash = members.find((member) => member.path === path && member.role === 'sash')
	if (sash) return sash.panel
	if (role === 'glass') {
		const pane = assembly.value?.panes?.find((p) => p.path === path)
		if (pane) return pane.panel
	}
	return path
}

function findGlassPieceForCell(cell: { path: string; x: number; y: number; w: number; h: number }): SectionPiece | undefined {
	const allGlass = sectionCuts.value
		.flatMap((c) => c.pieces)
		.filter((p) => p.kind === 'glass' || p.role === 'glass')
	if (!allGlass.length) return undefined

	const pane = assemblyPane(cell.path)
	if (pane) {
		const match = allGlass.find((p) => {
			if (p.code && pane.glass && p.code !== pane.glass) return false
			const mid = (p.start + p.end) / 2
			return mid >= pane.x - 25 && mid <= pane.x + pane.width + 25
		})
		if (match) return match
	}

	const matchX = allGlass.find((p) => {
		const mid = (p.start + p.end) / 2
		return mid >= cell.x - 15 && mid <= cell.x + cell.w + 15
	})
	if (matchX) return matchX

	const sashPanel = panelFor(cell.path, 'sash')
	return allGlass.find((p) => p.panel === sashPanel || p.panel === 'F1') ?? allGlass[0]
}

function getGlassTransformForCell(
	cell: { path: string },
	piece?: SectionPiece,
): SectionPieceTransform | undefined {
	const sectionMap = props.design.sectionMap ?? {}

	if (sectionMap[`GLASS:${cell.path}`]) return sectionMap[`GLASS:${cell.path}`]
	if (sectionMap[cell.path]) return sectionMap[cell.path]

	if (piece) {
		const canonKey = `${piece.role}:${piece.code}`
		if (sectionMap[canonKey]) return sectionMap[canonKey]
		for (const k of Object.keys(sectionMap)) {
			if (k.endsWith(`:${canonKey}`)) return sectionMap[k]
		}
		if (sectionMap[piece.role]) return sectionMap[piece.role]
	}

	for (const k of Object.keys(sectionMap)) {
		if (k.startsWith('glass:') || k.endsWith(':glass') || k === 'glass') {
			return sectionMap[k]
		}
	}

	if (piece) {
		return defaultTransformForPiece(piece, null)
	}

	return undefined
}

function highlightSelection() {
	if (!frameMat || !selectedFrameMat || !glassMat || !selectedGlassMat || !gasketMat) return
	const sel = props.selectedPath || ''
	for (const mesh of interactiveMeshes) {
		const path = String(mesh.userData.path || '')
		const kind = String(mesh.userData.kind || '')
		const selected = sel === 'FRAME' || sel === 'F1'
			? path === 'FRAME'
			: sel.startsWith('GLASS:')
				? path === sel
				: kind !== 'glass' && path === sel
		if (kind === 'glass') mesh.material = selected ? selectedGlassMat : glassMat
		else if (kind === 'gasket') mesh.material = gasketMat
		else mesh.material = selected ? selectedFrameMat : frameMat
	}
}

// ---------------------------------------------------------------------------
// Sash Opening Angle Synchronization
// ---------------------------------------------------------------------------

function updateSashOpeningAngles() {
	const deg = animatedOpenAngle
	const rad = THREE.MathUtils.degToRad(deg)

	for (const sp of sashPivots) {
		if (sp.opening === 'none') {
			sp.pivot.rotation.y = sp.initialRotY
			sp.pivot.rotation.x = sp.initialRotX
			continue
		}
		const outward = sp.opening !== 'in'
		if (sp.hinge === 'left') {
			sp.pivot.rotation.y = sp.initialRotY + (outward ? -rad : rad)
		} else if (sp.hinge === 'right') {
			sp.pivot.rotation.y = sp.initialRotY + (outward ? rad : -rad)
		} else if (sp.hinge === 'top') {
			sp.pivot.rotation.x = sp.initialRotX + (outward ? -rad : rad)
		}
	}
}

watch(openAngle, () => undefined)

// ---------------------------------------------------------------------------
// Camera Presets
// ---------------------------------------------------------------------------

function setCameraPreset(preset: 'iso' | 'front' | 'exterior' | 'mitre') {
	activeCameraPreset.value = preset
	if (!camera || !controls) return

	// Always frame the actual assembled model, rather than a guessed canvas
	// scale.  This prevents a deep section profile from making a 1:1 window
	// appear as an edge-on strip.
	const root = scene?.getObjectByName('window-root')
	const bounds = root ? new THREE.Box3().setFromObject(root) : new THREE.Box3()
	const center = bounds.isEmpty()
		? new THREE.Vector3(props.design.width / 2, props.design.height / 2, 0)
		: bounds.getCenter(new THREE.Vector3())
	const size = bounds.isEmpty()
		? new THREE.Vector3(props.design.width, props.design.height, 80)
		: bounds.getSize(new THREE.Vector3())
	const span = Math.max(size.x, size.y, 100)
	const aspect = Math.max(0.1, stageEl.value?.clientWidth && stageEl.value?.clientHeight
		? stageEl.value.clientWidth / stageEl.value.clientHeight : 1)
	const fitHeight = Math.max(size.y, size.x / aspect) * 1.12
	const frontDistance = fitHeight / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)))
	camera.aspect = aspect
	camera.near = 0.1
	camera.far = 20000
	camera.updateProjectionMatrix()

	controls.target.copy(center)
	let target = center.clone()

	if (preset === 'iso') {
		// Strong enough Z angle to read actual profile depth, without hiding the
		// plan opening behind the front rail.
		camera.position.set(center.x + frontDistance * 0.55, center.y + frontDistance * 0.34, center.z + frontDistance * 0.92)
	} else if (preset === 'front') {
		camera.position.set(center.x, center.y, center.z - frontDistance)
	} else if (preset === 'exterior') {
		camera.position.set(center.x, center.y, center.z + frontDistance)
	} else if (preset === 'mitre') {
		// Close-up inspection of top-left 45° mitre corner seam
		const frameFace = Math.max(20, size.x > 0 ? Math.min(size.x, size.y) * 0.06 : DEFAULT_FRAME_WIDTH)
		target.set(bounds.min.x + frameFace, bounds.max.y - frameFace, center.z)
		controls.target.copy(target)
		camera.position.set(target.x + frameFace * 5, target.y - frameFace * 4, target.z + frameFace * 9)
	}
	camera.lookAt(target)

	controls.update()
}

// ---------------------------------------------------------------------------
// Interactive Object Selection (Raycaster)
// ---------------------------------------------------------------------------

function onStageClick(e: MouseEvent) {
	if (!stageEl.value || !camera || !scene) return

	// Ignore drag releases
	const dx = e.clientX - pointerDownPos.x
	const dy = e.clientY - pointerDownPos.y
	if (Math.hypot(dx, dy) > 6) return

	const rect = stageEl.value.getBoundingClientRect()
	mouseVec.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
	mouseVec.y = -((e.clientY - rect.top) / rect.height) * 2 + 1

	raycaster.setFromCamera(mouseVec, camera)
	const hits = raycaster.intersectObjects(interactiveMeshes, false)

	if (hits.length > 0) {
		const hit = hits[0]
		const path = (hit.object.userData?.path as string) || ''
		if (path) {
			emit('select', path)
			return
		}
	}
	emit('select', '')
}

function onPointerDown(e: PointerEvent) {
	pointerDownPos = { x: e.clientX, y: e.clientY }
}

// ---------------------------------------------------------------------------
// Three.js Lifecycle & Animation Loop
// ---------------------------------------------------------------------------

function initThree() {
	if (!canvasEl.value || !stageEl.value) return
	if (!checkWebGL()) {
		webGLSupported.value = false
		return
	}

	const width = stageEl.value.clientWidth || 800
	const height = stageEl.value.clientHeight || 600

	scene = new THREE.Scene()
	scene.background = new THREE.Color(0xf8fafc)

	camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 20000)

	try {
		renderer = new THREE.WebGLRenderer({
			canvas: canvasEl.value,
			antialias: true,
			alpha: true,
			logarithmicDepthBuffer: false,
			powerPreference: 'high-performance',
		})
		renderer.setSize(width, height)
		renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
		renderer.shadowMap.enabled = true
		renderer.shadowMap.type = THREE.PCFSoftShadowMap
		renderer.toneMapping = THREE.ACESFilmicToneMapping
		renderer.toneMappingExposure = 1.0
	} catch {
		webGLSupported.value = false
		return
	}

	controls = new OrbitControls(camera, renderer.domElement)
	controls.enableDamping = true
	controls.dampingFactor = 0.08
	controls.maxDistance = 15000
	controls.minDistance = 50

	// Studio Lighting Setup
	const pmrem = new THREE.PMREMGenerator(renderer)
	scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
	;(scene as unknown as { environmentIntensity?: number }).environmentIntensity = 0.85
	pmrem.dispose()

	const ambientLight = new THREE.AmbientLight(0xffffff, 0.15)
	scene.add(ambientLight)

	const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.6)
	dirLight1.position.set(1200, 2000, 2400)
	dirLight1.castShadow = true
	dirLight1.shadow.mapSize.width = 2048
	dirLight1.shadow.mapSize.height = 2048
	scene.add(dirLight1)

	const dirLight2 = new THREE.DirectionalLight(0xe0f2fe, 0.4)
	dirLight2.position.set(-1400, 800, -1800)
	scene.add(dirLight2)

	const hemiLight = new THREE.HemisphereLight(0xffffff, 0x64748b, 0.25)
	scene.add(hemiLight)

	setCameraPreset('iso')
	hasFramedOnce = true
	rebuild3DWindow()

	stageEl.value.addEventListener('pointerdown', onPointerDown)

	const animate = () => {
		animFrameId = requestAnimationFrame(animate)
		// Keep geometry static and ease only pivot transforms.
		const target = openAngle.value
		if (Math.abs(animatedOpenAngle - target) > 0.05) {
			animatedOpenAngle += (target - animatedOpenAngle) * 0.18
			updateSashOpeningAngles()
		} else if (animatedOpenAngle !== target) {
			animatedOpenAngle = target
			updateSashOpeningAngles()
		}
		controls?.update()
		if (camera && controls) {
			const dist = Math.max(1, camera.position.distanceTo(controls.target))
			const near = Math.min(5, Math.max(0.05, dist * 0.002))
			const far = Math.max(4000, dist * 12)
			if (Math.abs(camera.near - near) > near * 0.2 || Math.abs(camera.far - far) > far * 0.2) {
				camera.near = near
				camera.far = far
				camera.updateProjectionMatrix()
			}
		}
		if (renderer && scene && camera) {
			renderer.render(scene, camera)
		}
	}
	animate()

	resizeObserver = new ResizeObserver(() => {
		if (!stageEl.value || !renderer || !camera) return
		const w = stageEl.value.clientWidth
		const h = stageEl.value.clientHeight
		if (w > 0 && h > 0) {
		camera.aspect = w / h
			camera.updateProjectionMatrix()
			renderer.setSize(w, h)
		}
	})
	resizeObserver.observe(stageEl.value)
}

onMounted(() => {
	initThree()
	loadOutlines()
})

onUnmounted(() => {
	clearTimeout(rebuildTimer)
	clearTimeout(outlineTimer)
	if (animFrameId !== null) cancelAnimationFrame(animFrameId)
	if (stageEl.value) stageEl.value.removeEventListener('pointerdown', onPointerDown)
	resizeObserver?.disconnect()

	controls?.dispose()
	renderer?.dispose()
	disposeV2Textures()

	for (const geom of geometryCache.values()) {
		geom.dispose()
	}
	geometryCache.clear()
})

// Watchers for reactive updates
watch(
	() => props.design,
	() => { loadOutlinesDebounced() },
	{ deep: true },
)

watch(
	() => [props.design?.sectionMap, props.design?.beadOffset],
	() => rebuildSceneDebounced(),
	{ deep: true },
)

watch(
	() => [props.finishColor, props.outsideFinishColor],
	() => rebuildSceneDebounced(),
)

watch(
	() => props.selectedPath,
	() => highlightSelection(),
)

watch(
	() => store.seriesVersion,
	() => loadOutlines(),
)
</script>

<style scoped>
canvas {
	touch-action: none;
}
</style>
