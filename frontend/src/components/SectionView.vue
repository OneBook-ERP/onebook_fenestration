<script setup lang="ts">
/**
 * Interactive Cross-Section Viewer & Puzzle Editor.
 *
 * - Splits the workspace side-by-side with the Window Designer.
 * - Shares the same workspace zoom & drag-to-pan feel as WindowCanvas (wheel zoom, +/-/reset zoom pill,
 *   drag empty canvas or Shift+drag to pan, keyboard zoom/pan shortcuts).
 * - Keeps the Glass stationary in the center (y = 0 datum) as the fixed reference point.
 * - Draws profiles at true 1:1 relative mm scale without cluttered dimension chains.
 * - Shows a neat, minimal floating control pill directly above the selected profile.
 * - Supports dragging profiles in Ghost Mode and snapping/resolving wall collisions on release.
 * - Mirrors edits across opposite corners (Left <-> Right, Bottom <-> Top) and syncs shared profile
 *   roles (`frame`, `sash`, `bead`, `gasket`) between B-B (Top/Horizontal) and A-A (Side/Vertical) views.
 */
import { Button, toast } from 'frappe-ui'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
	crossSection,
	setProfileOrientation,
	type CrossSection,
	type CutAxis as Axis,
	type CutResponse,
	type SectionOutline as Outline,
	type SectionPiece,
} from '@/api'
import {
	buildPlacedShape,
	canonicalPieceKey,
	classifySectionPieceInstances,
	compactPieceSpans,
	computeBBox,
	canPiecesOverlap,
	DEFAULT_PROFILE_DEPTH_MM,
	defaultTransformForPiece,
	getTwinTag,
	MIRROR_OF,
	seatedDefaultTransform,
	GLASS_REF_THICKNESS_MM,
	instancePieceKey,
	isPieceMoveable,
	magneticAutoJoin,
	resolvePuzzleDrop,
	shapesCollide,
	type PlacedShape,
} from '@/design/sectionPuzzle'
import { computeSmartGuides, measureGuides, type Rect, type SmartGuideResult } from './sectionSmartGuides'
import { layoutGeom } from '@/design/geometry'
import type { Design, SectionPieceTransform, SectionViewportState } from '@/design/types'
import { COMPUTE_DEBOUNCE_MS } from '@/stores/designer'

const props = withDefaults(
	defineProps<{
		design: Design
		seriesVersion: string
		axis: Axis
		at: number | null
		selectedPath?: string | null
	}>(),
	{ selectedPath: null },
)

const emit = defineEmits<{
	'update:axis': [axis: Axis]
	cut: [at: number]
	'update:section-map': [map: Record<string, SectionPieceTransform>]
	'update:mirror-sync': [val: boolean]
	'update:compact-glass': [val: boolean]
	'update:section-viewport': [axis: Axis, vp: SectionViewportState]
	'open-profile-picker': [piece: SectionPiece]
	select: [path: string]
}>()

const AXES = [
	{ label: 'B–B horizontal', value: 'h' },
	{ label: 'A–A vertical', value: 'v' },
] as const

const PAD_MM = 20
const MIN_SECTION_ZOOM = 0.2
const MAX_SECTION_ZOOM = 25.0
const SECTION_ZOOM_STEP = 0.15
const MAX_SECTION_PAN_MM = 600
const PAN_KEY_STEP_MM = 15

const ROLE_COLORS: Record<string, { stroke: string; fill: string; label: string }> = {
	sash: { stroke: '#EA580C', fill: '#FED7AA', label: 'Sash' },
	frame: { stroke: '#334155', fill: '#CBD5E1', label: 'Outer Frame' },
	mullion: { stroke: '#475569', fill: '#CBD5E1', label: 'Mullion' },
	transom: { stroke: '#475569', fill: '#CBD5E1', label: 'Transom' },
	bead: { stroke: '#0F766E', fill: '#99F6E4', label: 'Bead / Gasket' },
	glass_adaptor: { stroke: '#0F766E', fill: '#99F6E4', label: 'Adaptor / Gasket' },
	gasket: { stroke: '#0F766E', fill: '#99F6E4', label: 'Gasket' },
	glass: { stroke: '#0284C7', fill: '#BAE6FD', label: 'Stationary Glass' },
}

const axis = ref<Axis>(props.axis)
watch(
	() => props.axis,
	(a) => (axis.value = a),
)

const section = ref<CrossSection | null>(null)
const outlines = ref<Record<string, Outline>>({})
const error = ref('')
let seq = 0
let timer: ReturnType<typeof setTimeout> | undefined
let snapped: { axis: Axis; at: number } | null = null

/** Mirror & Sync mode: mirrors Left <-> Right corners and syncs B-B (Top) <-> A-A (Side) views. */
const localMirrorSync = ref(props.design.mirrorSync ?? true)
watch(
	() => props.design.mirrorSync,
	(v) => {
		if (v !== undefined) localMirrorSync.value = v
	},
)
const mirrorSync = computed({
	get: () => localMirrorSync.value,
	set: (val: boolean) => {
		localMirrorSync.value = val
		emit('update:mirror-sync', val)
	},
})

/** Compact glass mode keeps glass stationary in the center at a compact span so profile scale is large & clear. */
const localCompactGlass = ref(props.design.compactGlass ?? true)
watch(
	() => props.design.compactGlass,
	(v) => {
		if (v !== undefined) localCompactGlass.value = v
	},
)
const compactGlass = computed({
	get: () => localCompactGlass.value,
	set: (val: boolean) => {
		localCompactGlass.value = val
		emit('update:compact-glass', val)
	},
})
function toggleCompactGlass() {
	compactGlass.value = !compactGlass.value
	resetView()
}
watch(compactGlass, () => {
	resetView()
})
const selectedIndex = ref<number | null>(null)

const currentViewport = computed(() => props.design.sectionViewport?.[axis.value])
const sectionZoom = ref(currentViewport.value?.zoom ?? 1)
const sectionPan = ref({
	x: currentViewport.value?.pan?.x ?? 0,
	y: currentViewport.value?.pan?.y ?? 0,
})

watch(currentViewport, (vp) => {
	if (vp) {
		sectionZoom.value = vp.zoom
		sectionPan.value = { ...vp.pan }
	}
})

function emitViewport() {
	emit('update:section-viewport', axis.value, {
		zoom: sectionZoom.value,
		pan: { ...sectionPan.value },
	})
}
const shiftHeld = ref(false)
const isPanning = ref(false)
let suppressNextBgClick = false

/** Tracked container dimensions so SVG viewBox and floating toolbar anchor align 1:1. */
const canvasWrapEl = ref<HTMLDivElement | null>(null)
const svgEl = ref<SVGSVGElement | null>(null)
const containerSize = ref({ width: 640, height: 520 })
let resizeObs: ResizeObserver | null = null

function updateContainerSize() {
	const el = canvasWrapEl.value
	if (!el) return
	const { clientWidth: w, clientHeight: h } = el
	if (w > 0 && h > 0 && (w !== containerSize.value.width || h !== containerSize.value.height)) {
		containerSize.value = { width: w, height: h }
	}
}

/** Local fallback map when used standalone without parent v-model/event persistence. */
const localSectionMap = ref<Record<string, SectionPieceTransform>>({})
watch(
	() => props.design.sectionMap,
	(m) => {
		localSectionMap.value = m ? { ...m } : {}
	},
	{ immediate: true, deep: true },
)

const activeMap = computed<Record<string, SectionPieceTransform>>(() => ({
	...localSectionMap.value,
	...(props.design.sectionMap ?? {}),
}))

/** Active ghost drag state while moving a profile piece. */
const ghostDrag = ref<{
	index: number
	piece: SectionPiece
	tag?: string
	twinIndex?: number
	twinTag?: string
	twinPiece?: SectionPiece
	startClientX: number
	startClientY: number
	origTransform: SectionPieceTransform
	origTwinTransform?: SectionPieceTransform
	currentTransform: SectionPieceTransform
	twinTransform?: SectionPieceTransform
	pointerId: number
} | null>(null)

/** Active workspace pan drag state (dragging empty workspace or Shift+drag). */
let panDrag: {
	startX: number
	startY: number
	origX: number
	origY: number
	pointerId: number
	moved: boolean
} | null = null

const lastSnapNotice = ref('')
const activeSmartGuides = ref<SmartGuideResult | null>(null)
/** mm per screen pixel, refreshed on every drag move. The template reads this, never svgUnitsPerPixel(). */
const guideScale = ref(0.5)
let lastMoveEvent: PointerEvent | null = null

async function load() {
	clearTimeout(timer)
	const mine = ++seq
	let res: CutResponse
	try {
		res = await crossSection(props.design, props.seriesVersion, axis.value, props.at)
	} catch (e) {
		if (mine === seq) error.value = e instanceof Error ? e.message : 'Could not cut the design'
		return
	}
	if (mine !== seq) return
	if (!res?.ok) {
		error.value = res?.message ?? 'Could not cut the design'
		section.value = null
		snapped = null
		return
	}
	error.value = ''
	section.value = res.result
	outlines.value = res.outlines ?? {}
	seedDefaultSeats(res.result)
	snapped = { axis: axis.value, at: res.result.at }
	if (selectedIndex.value !== null && selectedIndex.value >= res.result.pieces.length) {
		selectedIndex.value = null
	}
	emit('cut', res.result.at)
}

function loadLater() {
	clearTimeout(timer)
	timer = setTimeout(load, COMPUTE_DEBOUNCE_MS)
}

load()

watch(
	() => [axis.value, props.seriesVersion, props.at] as const,
	([a, sv, at], [prevA, prevSv]) => {
		const onlyAtMoved = a === prevA && sv === prevSv
		if (onlyAtMoved && snapped && snapped.axis === a && at === snapped.at) return
		load()
	},
)
watch(
	() => [props.design.width, props.design.height, props.design.root, props.design.profiles],
	loadLater,
	{ deep: true },
)

onMounted(() => {
	updateContainerSize()
	if (typeof ResizeObserver !== 'undefined' && canvasWrapEl.value) {
		resizeObs = new ResizeObserver(() => updateContainerSize())
		resizeObs.observe(canvasWrapEl.value)
	}
	window.addEventListener('keydown', onKeyDown)
	window.addEventListener('keyup', onKeyUp)
	window.addEventListener('blur', onWindowBlur)
})

onUnmounted(() => {
	clearTimeout(timer)
	seq += 1
	endPieceDrag()
	endWorkspacePan()
	resizeObs?.disconnect()
	window.removeEventListener('keydown', onKeyDown)
	window.removeEventListener('keyup', onKeyUp)
	window.removeEventListener('blur', onWindowBlur)
})

function pick(a: Axis) {
	if (a === axis.value) return
	axis.value = a
	emit('update:axis', a)
	const vp = props.design.sectionViewport?.[a]
	sectionZoom.value = vp?.zoom ?? 1
	sectionPan.value = { x: vp?.pan?.x ?? 0, y: vp?.pan?.y ?? 0 }
}

const fmt = (n: number) => String(Math.round(n * 100) / 100)

function clampZoom(z: number): number {
	return Math.round(Math.min(MAX_SECTION_ZOOM, Math.max(MIN_SECTION_ZOOM, z)) * 100) / 100
}

function clampPan(v: number): number {
	const limit = Math.max(3000, cutLength.value * 2)
	return Math.min(limit, Math.max(-limit, v))
}

function zoomIn() {
	const cur = sectionZoom.value
	const step = cur < 1.95 ? 0.15 : cur < 5 ? 0.5 : cur < 10 ? 1.0 : 2.5
	sectionZoom.value = clampZoom(cur + step)
	emitViewport()
}

function zoomOut() {
	const cur = sectionZoom.value
	const step = cur <= 2.0 ? 0.15 : cur <= 5 ? 0.5 : cur <= 10 ? 1.0 : 2.5
	sectionZoom.value = clampZoom(cur - step)
	emitViewport()
}

function resetView() {
	sectionZoom.value = 1
	sectionPan.value = { x: 0, y: 0 }
	emitViewport()
}

function panBy(dxMm: number, dyMm: number) {
	sectionPan.value = {
		x: clampPan(sectionPan.value.x + dxMm),
		y: clampPan(sectionPan.value.y + dyMm),
	}
	emitViewport()
}

const pieceTags = computed(() => {
	const len = section.value?.length ?? props.design.width ?? 1220
	return classifySectionPieceInstances(axis.value, section.value?.pieces ?? [], len)
})

function getTransformForPiece(index: number, piece: SectionPiece, outline: Outline | null): SectionPieceTransform {
	if (ghostDrag.value) {
		const gd = ghostDrag.value
		if (gd.index === index) return gd.currentTransform
		if (mirrorSync.value && gd.twinIndex === index && gd.twinTransform) {
			return gd.twinTransform
		}
	}
	const tag = pieceTags.value[index]
	const instKey = tag ? instancePieceKey(axis.value, tag, piece) : null
	const legacyInstKey = instancePieceKey(axis.value, index, piece)
	const canonKey = canonicalPieceKey(piece)

	if (instKey && activeMap.value[instKey]) {
		return activeMap.value[instKey]
	}
	if (activeMap.value[legacyInstKey]) {
		return activeMap.value[legacyInstKey]
	}
	if (tag && activeMap.value[tag]) {
		return activeMap.value[tag]
	}
	if (piece.role !== 'bead' && activeMap.value[canonKey]) {
		return activeMap.value[canonKey]
	}
	return defaultTransformForPiece(piece, outline)
}

/** Persist automatic seating so the section workspace and Three renderer use
 * exactly the same sash and glass depth unless the user moves a piece. */
function seedDefaultSeats(cut: CrossSection) {
	const nextMap = { ...activeMap.value }
	const { starts, ends } = compactPieceSpans(cut.pieces, compactGlass.value)
	const placed: PlacedShape[] = []
	let changed = false
	for (let index = 0; index < cut.pieces.length; index++) {
		const piece = cut.pieces[index]
		const outline = piece.kind === 'profile' ? (outlines.value[piece.code] ?? null) : null
		const key = canonicalPieceKey(piece)
		const tag = pieceTags.value[index]
		const instKey = tag ? instancePieceKey(axis.value, tag, piece) : instancePieceKey(axis.value, index, piece)
		let transform = nextMap[instKey] ?? nextMap[key] ?? defaultTransformForPiece(piece, outline)
		const hasGlazingRebate = placed.some((shape) =>
			['bead', 'gasket', 'glass_adaptor'].includes(shape.piece.role) ||
			(shape.piece.role === 'sash' && shape.rings.some((ring) => ring.length > 5)),
		)
		if (!nextMap[key] && !nextMap[instKey] && (piece.role === 'sash' || (piece.kind === 'glass' && hasGlazingRebate))) {
			transform = seatedDefaultTransform(index, piece, starts[index] ?? piece.start, ends[index] ?? piece.end, outline, placed)
			nextMap[instKey] = transform
			changed = true
		}
		placed.push(buildPlacedShape(index, piece, starts[index] ?? piece.start, ends[index] ?? piece.end, outline, transform))
	}
	if (changed) {
		localSectionMap.value = nextMap
		emit('update:section-map', nextMap)
	}
}

function commitTransformForPiece(index: number, piece: SectionPiece, nextTransform: SectionPieceTransform) {
	const nextMap = { ...activeMap.value }
	const tag = pieceTags.value[index]
	const instKey = tag ? instancePieceKey(axis.value, tag, piece) : instancePieceKey(axis.value, index, piece)
	const prevTransform = getTransformForPiece(index, piece, outlines.value[piece.code] ?? null)
	const deltaAlong = nextTransform.offsetAlong - prevTransform.offsetAlong
	const deltaDepth = nextTransform.offsetDepth - prevTransform.offsetDepth
	const deltaRot = (nextTransform.rotation || 0) - (prevTransform.rotation || 0)
	const deltaFlipX = nextTransform.flipX !== prevTransform.flipX
	const deltaFlipY = nextTransform.flipY !== prevTransform.flipY

	nextMap[instKey] = nextTransform
	const legacyInstKey = instancePieceKey(axis.value, index, piece)
	if (legacyInstKey !== instKey) {
		nextMap[legacyInstKey] = nextTransform
	}
	let twinNext: SectionPieceTransform | null = null
	if (mirrorSync.value && tag) {
		const twinTag = getTwinTag(tag)
		if (twinTag) {
			const twinIdx = pieceTags.value.indexOf(twinTag)
			if (twinIdx >= 0) {
				const twinPiece = section.value?.pieces[twinIdx]
				if (twinPiece) {
					const twinOutline = twinPiece.kind === 'profile' ? outlines.value[twinPiece.code] ?? null : null
					const twinPrev = getTransformForPiece(twinIdx, twinPiece, twinOutline)
					const twinInstKey = instancePieceKey(axis.value, twinTag, twinPiece)
					const twinRot = ((((twinPrev.rotation || 0) - deltaRot) % 360) + 360) % 360
					twinNext = {
						...twinPrev,
						offsetAlong: Math.round((twinPrev.offsetAlong - deltaAlong) * 10) / 10,
						offsetDepth: Math.round((twinPrev.offsetDepth + deltaDepth) * 10) / 10,
						rotation: twinRot,
						flipX: deltaFlipX ? !twinPrev.flipX : twinPrev.flipX,
						flipY: deltaFlipY ? !twinPrev.flipY : twinPrev.flipY,
					}
					nextMap[twinInstKey] = twinNext
					const legacyTwinKey = instancePieceKey(axis.value, twinIdx, twinPiece)
					if (legacyTwinKey !== twinInstKey) {
						nextMap[legacyTwinKey] = twinNext
					}
				}
			}
		}
	}

	if (piece.role !== 'bead') {
		const canonKey = canonicalPieceKey(piece)
		nextMap[canonKey] = piece.mirrored && twinNext ? twinNext : nextTransform
	}

	localSectionMap.value = nextMap
	emit('update:section-map', nextMap)
}

function toggleMirrorSync() {
	mirrorSync.value = !mirrorSync.value
}

const compacted = computed(() => compactPieceSpans(section.value?.pieces ?? [], compactGlass.value))

interface DrawnPiece {
	index: number
	piece: SectionPiece
	baseStart: number
	baseEnd: number
	x: number
	y: number
	w: number
	depth: number
	outline: Outline | null
	transform: string
	pieceTransform: SectionPieceTransform
	shape: PlacedShape
	labelPos: { x: number; y: number }
	fontSize: number
	maxTextWidth: number
	moveable: boolean
	selected: boolean
	mirroredTwinSelected: boolean
	ghost: boolean
	colliding: boolean
	colors: { stroke: string; fill: string; label: string }
}

const placedShapes = computed<PlacedShape[]>(() => {
	const pieces = section.value?.pieces ?? []
	const { starts, ends } = compacted.value
	return pieces.map((piece, i) => {
		const outline = piece.kind === 'profile' ? (outlines.value[piece.code] ?? null) : null
		const t = getTransformForPiece(i, piece, outline)
		return buildPlacedShape(i, piece, starts[i] ?? piece.start, ends[i] ?? piece.end, outline, t)
	})
})

function pathForPiece(piece: SectionPiece): string {
	if (piece.role === 'frame') return 'FRAME'
	if (piece.role === 'mullion' || piece.role === 'transom') return piece.panel
	const g = layoutGeom(props.design)
	let sashCount = 0
	let targetCell = null
	for (const c of g.cells) {
		if (c.node.type === 'sash') {
			sashCount++
			const panelId = `F1-S${sashCount}`
			if (piece.panel === panelId || piece.panel === `S${sashCount}`) {
				targetCell = c
				break
			}
		}
	}
	if (targetCell) {
		if (piece.kind === 'glass') return `GLASS:${targetCell.path}`
		if (piece.role === 'bead') return `BEAD:${targetCell.path}`
		return targetCell.path
	}

	// Fixed glass or fixed panel bead/gasket
	const mid = (piece.start + piece.end) / 2
	const fixedCell = g.cells.find((c) => {
		if (axis.value === 'h') {
			return mid >= c.x - 5 && mid <= c.x + c.w + 5
		} else {
			return mid >= c.y - 5 && mid <= c.y + c.h + 5
		}
	}) ?? g.cells[0]

	if (fixedCell) {
		if (piece.kind === 'glass') return `GLASS:${fixedCell.path}`
		if (piece.role === 'bead') return `BEAD:${fixedCell.path}`
		return fixedCell.path
	}
	return ''
}

function isPieceSelected(piece: SectionPiece, index: number): boolean {
	if (selectedIndex.value === index) return true
	const sel = props.selectedPath
	if (!sel) return false
	if (sel.startsWith('BEAD:')) {
		if (piece.role !== 'bead') return false
		const cellPath = sel.replace(/^BEAD:/, '')
		const pPath = pathForPiece(piece)
		return pPath === sel || pPath === cellPath || pPath === `BEAD:${cellPath}`
	}
	if (sel === 'FRAME' || sel === 'F1') {
		return piece.role === 'frame'
	}
	if (/^[MT]\d+$/.test(sel)) {
		return (piece.role === 'mullion' || piece.role === 'transom') && piece.panel === sel
	}
	if (sel.startsWith('GLASS:')) {
		if (piece.kind !== 'glass') return false
		const cellPath = sel.replace(/^GLASS:/, '')
		const pPath = pathForPiece(piece)
		return pPath === sel || pPath === cellPath
	}
	const pPath = pathForPiece(piece)
	return pPath === sel
}

watch(
	() => props.selectedPath,
	() => {
		if (selectedIndex.value !== null) {
			const pieces = section.value?.pieces ?? []
			const piece = pieces[selectedIndex.value]
			if (piece && !isPieceSelected(piece, selectedIndex.value)) {
				selectedIndex.value = null
			}
		}
	},
)

function onPieceClick(d: DrawnPiece) {
	selectedIndex.value = d.index
	const path = pathForPiece(d.piece)
	if (path) emit('select', path)
}

const drawn = computed<DrawnPiece[]>(() => {
	const pieces = section.value?.pieces ?? []
	const { starts, ends } = compacted.value
	const shapes = placedShapes.value
	const selPiece = selectedIndex.value !== null ? pieces[selectedIndex.value] : null

	const rawDrawn = pieces.map((piece, i) => {
		const baseStart = starts[i] ?? piece.start
		const baseEnd = ends[i] ?? piece.end
		const outline = piece.kind === 'profile' ? (outlines.value[piece.code] ?? null) : null
		const t = getTransformForPiece(i, piece, outline)
		const shape = shapes[i]
		const rawW = outline?.width && outline.width > 0 ? outline.width : Math.max(4, baseEnd - baseStart)
		const rawD =
			piece.kind === 'glass'
				? piece.thickness > 0
					? piece.thickness
					: GLASS_REF_THICKNESS_MM
				: outline?.depth && outline.depth > 0
					? outline.depth
					: DEFAULT_PROFILE_DEPTH_MM

		const moveable = isPieceMoveable(piece)
		const x = baseStart + t.offsetAlong
		const y = piece.kind === 'glass' ? -rawD / 2 + t.offsetDepth : t.offsetDepth
		const w = piece.kind === 'glass' ? Math.max(4, baseEnd - baseStart) : rawW

		const pieceW = Math.max(4, baseEnd - baseStart)
		const s = outline && outline.width > 0 ? (compactGlass.value ? 1 : pieceW / outline.width) : 1
		const effFlipX = Boolean(piece.mirrored) !== Boolean(t.flipX)
		const effFlipY = Boolean(t.flipY)
		const effRot = (((piece.mirrored ? -t.rotation : t.rotation) % 360) + 360) % 360
		const cx = (rawW * s) / 2
		const cy = (rawD * s) / 2
		const sxScale = effFlipX ? -s : s
		const syScale = effFlipY ? -s : s

		let svgTransform = ''
		if (outline && outline.width > 0) {
			if (effRot === 0 && !effFlipY && t.flipX !== true) {
				svgTransform = effFlipX
					? `translate(${fmt(x + rawW * s)} ${fmt(y)}) scale(${fmt(-s)} ${fmt(s)})`
					: `translate(${fmt(x)} ${fmt(y)}) scale(${fmt(s)} ${fmt(s)})`
			} else {
				svgTransform = `translate(${fmt(x + cx)} ${fmt(y + cy)}) rotate(${effRot}) scale(${fmt(sxScale)} ${fmt(syScale)}) translate(${fmt(-rawW / 2)} ${fmt(-rawD / 2)})`
			}
		}

		const isGhost = Boolean(
			ghostDrag.value &&
				(ghostDrag.value.index === i ||
					(mirrorSync.value && ghostDrag.value.twinIndex === i)),
		)
		const colliding =
			piece.kind === 'profile' &&
			shapes.some((other) => other.index !== i && !canPiecesOverlap(piece, other.piece) && shapesCollide(shape, other))

		const selected = isPieceSelected(piece, i)
		const tag = pieceTags.value[i]
		const selTag = selectedIndex.value !== null ? pieceTags.value[selectedIndex.value] : null
		const mirroredTwinSelected = Boolean(
			!selected &&
				mirrorSync.value &&
				selTag &&
				tag &&
				getTwinTag(selTag) === tag,
		)

		const colors = ROLE_COLORS[piece.role] ?? ROLE_COLORS.frame
		const codeStr = piece.code || ''
		const availW = Math.max(4, (shape.bbox.width > 0 ? shape.bbox.width : rawW) - 3)
		const fontSize = Math.min(2.2, Math.max(1.3, availW / (Math.max(1, codeStr.length) * 0.65)))
		const maxTextWidth = Math.min(codeStr.length * 1.3, availW)
		return {
			index: i,
			piece,
			baseStart,
			baseEnd,
			x,
			y,
			w: rawW * s,
			depth: rawD * s,
			outline,
			transform: svgTransform,
			pieceTransform: t,
			shape,
			labelPos: { ...shape.labelPos },
			fontSize,
			maxTextWidth,
			moveable,
			selected,
			mirroredTwinSelected,
			ghost: isGhost,
			colliding,
			colors,
		}
	})

	// Ensure profile code labels inside/between profile chambers never overlap
	for (let i = 0; i < rawDrawn.length; i++) {
		for (let j = i + 1; j < rawDrawn.length; j++) {
			const a = rawDrawn[i]
			const b = rawDrawn[j]
			if (Math.abs(a.labelPos.x - b.labelPos.x) < 16 && Math.abs(a.labelPos.y - b.labelPos.y) < 5) {
				a.labelPos.y -= 3.2
				b.labelPos.y += 3.2
			}
		}
	}

	return rawDrawn
})

const selectedDrawn = computed<DrawnPiece | null>(() =>
	selectedIndex.value !== null ? (drawn.value[selectedIndex.value] ?? null) : null,
)

const selectedVisualRotation = computed(() => {
	const d = selectedDrawn.value
	if (!d) return 0
	const rot = d.pieceTransform.rotation || 0
	return (((d.piece.mirrored ? -rot : rot) % 360) + 360) % 360
})

const cutLength = computed(() => section.value?.length ?? (axis.value === 'h' ? props.design.width : props.design.height))
const effectiveCutLength = computed(() =>
	compactGlass.value ? compacted.value.totalSpan : cutLength.value,
)
const bottomWallY = computed(() => {
	const pieces = section.value?.pieces ?? []
	if (!pieces.length) return 20

	// Baseline outer depth boundary is defined by the frame & bar profile depths
	const baseDepths: number[] = []
	for (const p of pieces) {
		if (p.kind === 'profile' && (p.role === 'frame' || p.role === 'mullion' || p.role === 'transom')) {
			const outline = outlines.value[p.code]
			const d = outline?.depth && outline.depth > 0 ? outline.depth : DEFAULT_PROFILE_DEPTH_MM
			baseDepths.push(d)
		}
	}
	if (baseDepths.length) {
		return Math.round(Math.max(...baseDepths) * 10) / 10
	}

	const shapes = placedShapes.value
	if (shapes.length) {
		return Math.round(Math.max(...shapes.map((s) => s.bbox.maxY)) * 10) / 10
	}

	return 40
})

const GUIDE_COLORS: Record<'edge' | 'center', string> = { edge: '#e11d48', center: '#c026d3' }

function shapeToRect(s: PlacedShape): Rect {
	return {
		id: `piece-${s.index}`,
		x: s.bbox.minX,
		y: s.bbox.minY,
		w: s.bbox.maxX - s.bbox.minX,
		h: s.bbox.maxY - s.bbox.minY,
	}
}

/**
 * Guide-only reference lines. They give you a centre guide even when no other piece is
 * centred, the glass plane (y = 0, where the stationary glass sits), and the walls.
 */
const datumRects = computed<Rect[]>(() => {
	const len = effectiveCutLength.value
	const wall = bottomWallY.value
	return [
		{ id: 'datum-center-x', x: len / 2, y: 0, w: 0, h: wall, guide: 'center' },
		{ id: 'datum-glass-plane', x: 0, y: 0, w: len, h: 0, guide: 'center' },
		{ id: 'wall-left', x: 0, y: 0, w: 0, h: wall, guide: 'edge' },
		{ id: 'wall-right', x: len, y: 0, w: 0, h: wall, guide: 'edge' },
		{ id: 'wall-bottom', x: 0, y: wall, w: len, h: 0, guide: 'edge' },
	]
})

function nonEmpty(res: SmartGuideResult): SmartGuideResult | null {
	return res.lines.length || res.gaps.length ? res : null
}

/** Pre-computed geometry for the distance markers (both axes), so the template stays dumb. */
const guideGapShapes = computed(() => {
	const tick = 4 * guideScale.value
	return (activeSmartGuides.value?.gaps ?? []).map((g, key) => {
		const horizontal = g.axis === 'x'
		const at = (along: number, across: number) => (horizontal ? { x: along, y: across } : { x: across, y: along })
		const p1 = at(g.start, g.perpPos)
		const p2 = at(g.end, g.perpPos)
		const cap = (p: { x: number; y: number }) =>
			horizontal
				? { x1: p.x, y1: p.y - tick, x2: p.x, y2: p.y + tick }
				: { x1: p.x - tick, y1: p.y, x2: p.x + tick, y2: p.y }
		const label = fmt(g.gap)
		return {
			key,
			gap: g,
			label,
			line: { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y },
			ticks: [cap(p1), cap(p2)],
			pill: { ...at((g.start + g.end) / 2, g.perpPos), w: Math.max(24, 8 + label.length * 6.2) },
		}
	})
})

const sceneBBox = computed(() => {
	const shapes = placedShapes.value
	if (!shapes.length) {
		return { minX: -20, minY: -60, maxX: 300, maxY: 60, width: 320, height: 120 }
	}
	const allRings = shapes.flatMap((s) => s.rings)
	const b = computeBBox(allRings)
	const padX = compactGlass.value ? 16 : 28
	const minX = Math.min(b.minX - padX, -10)
	const maxX = Math.max(b.maxX + padX, effectiveCutLength.value + 10)
	const minY = Math.min(b.minY - 20, -50)
	const maxY = Math.max(b.maxY, bottomWallY.value) + 12
	return {
		minX,
		minY,
		maxX,
		maxY,
		width: Math.max(100, maxX - minX),
		height: Math.max(80, maxY - minY),
	}
})

/** Overall assembly section dimensions (Width × Depth in mm), matching CAD section callout. */
const sectionExtentLabel = computed(() => {
	const profileShapes = placedShapes.value.filter((s) => s.piece.kind === 'profile')
	if (!profileShapes.length) return '0 + 0 mm'
	const firstJoint = profileShapes.filter((s) => !s.piece.mirrored)
	const target = firstJoint.length ? firstJoint : profileShapes
	const b = computeBBox(target.flatMap((s) => s.rings))
	return `${Math.round(b.width)} + ${Math.round(b.height)} mm`
})

/** Computed viewBox rectangle matching container aspect ratio for 1:1 coordinate projection. */
const viewBoxRect = computed(() => {
	const b = sceneBBox.value
	const baseW = b.width / sectionZoom.value
	const baseH = b.height / sectionZoom.value
	const cw = Math.max(1, containerSize.value.width)
	const ch = Math.max(1, containerSize.value.height)
	const aspect = cw / ch

	let w = baseW
	let h = baseH
	if (baseW / baseH > aspect) {
		h = baseW / aspect
	} else {
		w = baseH * aspect
	}

	const cx = (b.minX + b.maxX) / 2 - sectionPan.value.x
	const cy = (b.minY + b.maxY) / 2 - sectionPan.value.y
	return {
		x: cx - w / 2,
		y: cy - h / 2,
		w,
		h,
	}
})

const viewBoxStr = computed(() => {
	const vb = viewBoxRect.value
	return `${fmt(vb.x)} ${fmt(vb.y)} ${fmt(vb.w)} ${fmt(vb.h)}`
})

/**
 * Floating control toolbar anchor style positioned directly on top of the selected profile.
 * Clamped safely inside the viewport so it never clips off the edges.
 */
const selectedFloatingStyle = computed<Record<string, string>>(() => {
	const d = selectedDrawn.value
	if (!d) return { left: '50%', top: '12%', transform: 'translate(-50%, -100%)' }
	const vb = viewBoxRect.value
	const anchorX = d.shape.bbox.minX + d.shape.bbox.width / 2
	const anchorY = d.shape.bbox.minY - 7
	const rawLeftPct = ((anchorX - vb.x) / vb.w) * 100
	const rawTopPct = ((anchorY - vb.y) / vb.h) * 100
	const leftPct = Math.min(82, Math.max(18, rawLeftPct))
	const topPct = Math.min(88, Math.max(11, rawTopPct))
	return {
		left: `${fmt(leftPct)}%`,
		top: `${fmt(topPct)}%`,
		transform: 'translate(-50%, -100%)',
	}
})

const missing = computed(() => {
	const codes = new Set(drawn.value.filter((d) => d.piece.kind === 'profile' && !d.outline).map((d) => d.piece.code))
	return [...codes].sort()
})

const title = computed(() =>
	axis.value === 'h'
		? 'Section B–B (Top / Horizontal Cut)'
		: 'Section A–A (Side / Vertical Cut)',
)
const issues = computed(() => section.value?.issues ?? [])

function svgUnitsPerPixel(): number {
	updateContainerSize()
	const el = svgEl.value
	const vb = viewBoxRect.value
	if (!el) return vb.w / 640
	const r = el.getBoundingClientRect()
	if (!r.width || !r.height) return 0.5
	return Math.max(vb.w / r.width, vb.h / r.height)
}

function onPiecePointerDown(e: PointerEvent, d: DrawnPiece) {
	// If Shift or middle mouse is held, pan the workspace instead of dragging the profile
	if (e.shiftKey || shiftHeld.value || e.button === 1) {
		onCanvasPointerDown(e)
		return
	}
	if (e.button !== 0 && e.button !== undefined) return
	e.stopPropagation()
	e.preventDefault()
	selectedIndex.value = d.index
	lastSnapNotice.value = ''
	activeSmartGuides.value = null
	const path = pathForPiece(d.piece)
	if (path) emit('select', path)

	// All profiles, mullions, transoms, sashes, and beads are draggable
	const orig = getTransformForPiece(d.index, d.piece, d.outline)
	const tag = pieceTags.value[d.index]
	const twinTag = mirrorSync.value && tag ? getTwinTag(tag) : null
	const twinIdx = twinTag ? pieceTags.value.indexOf(twinTag) : -1
	const twinPiece = twinIdx >= 0 ? section.value?.pieces[twinIdx] : null
	const twinOutline = twinPiece && twinPiece.kind === 'profile' ? outlines.value[twinPiece.code] ?? null : null
	const twinOrig = twinPiece ? getTransformForPiece(twinIdx, twinPiece, twinOutline) : null

	ghostDrag.value = {
		index: d.index,
		piece: d.piece,
		tag,
		twinIndex: twinIdx >= 0 ? twinIdx : undefined,
		twinTag: twinTag ?? undefined,
		twinPiece: twinPiece ?? undefined,
		startClientX: e.clientX,
		startClientY: e.clientY,
		origTransform: { ...orig },
		origTwinTransform: twinOrig ? { ...twinOrig } : undefined,
		currentTransform: { ...orig },
		twinTransform: twinOrig ? { ...twinOrig } : undefined,
		pointerId: e.pointerId,
	}
	window.addEventListener('pointermove', onPiecePointerMove)
	window.addEventListener('pointerup', endPieceDrag)
	window.addEventListener('pointercancel', endPieceDrag)
}

function clampTransformToBoundary(
	piece: SectionPiece,
	baseStart: number,
	baseEnd: number,
	t: SectionPieceTransform,
	outline?: Outline | null,
): SectionPieceTransform {
	const len = effectiveCutLength.value
	const minAlong = -baseStart
	const maxAlong = Math.max(minAlong, len - baseEnd)
	const clampedAlong = Math.min(maxAlong, Math.max(minAlong, t.offsetAlong))
	let candidate: SectionPieceTransform = {
		...t,
		offsetAlong: Math.round(clampedAlong * 10) / 10,
	}

	// Clamp depth so the piece's bottom edge never exceeds bottomWallY
	const shape = buildPlacedShape(0, piece, baseStart, baseEnd, outline ?? null, candidate)
	const limitY = bottomWallY.value
	if (shape.bbox.maxY > limitY) {
		const over = shape.bbox.maxY - limitY
		candidate = {
			...candidate,
			offsetDepth: Math.round((candidate.offsetDepth - over) * 10) / 10,
		}
	}

	return candidate
}

function onPiecePointerMove(e: PointerEvent) {
	const gd = ghostDrag.value
	if (!gd) return
	if (e === lastMoveEvent) return // bound on both <g> and window; handle each native event once
	lastMoveEvent = e

	const scaleMm = svgUnitsPerPixel()
	guideScale.value = scaleMm
	const dxMm = (e.clientX - gd.startClientX) * scaleMm
	const dyMm = (e.clientY - gd.startClientY) * scaleMm
	const candidate: SectionPieceTransform = {
		...gd.origTransform,
		offsetAlong: Math.round((gd.origTransform.offsetAlong + dxMm) * 10) / 10,
		offsetDepth: Math.round((gd.origTransform.offsetDepth + dyMm) * 10) / 10,
	}

	const cur = drawn.value[gd.index]
	if (!cur) {
		gd.currentTransform = candidate
		activeSmartGuides.value = null
	} else {
		const clamp = (t: SectionPieceTransform) =>
			clampTransformToBoundary(gd.piece, cur.baseStart, cur.baseEnd, t, cur.outline)
		const build = (t: SectionPieceTransform) =>
			buildPlacedShape(gd.index, gd.piece, cur.baseStart, cur.baseEnd, cur.outline, t)

		const obstacles = placedShapes.value.filter(
			(obs) => obs.index !== gd.index && (gd.twinIndex === undefined || obs.index !== gd.twinIndex),
		)
		const targets: Rect[] = [...obstacles.map(shapeToRect), ...datumRects.value]

		const clamped = clamp(candidate)
		const movingShape = build(clamped)
		let finalT = clamped

		if (!(e.altKey || e.ctrlKey)) {
			const joined = magneticAutoJoin(movingShape, clamped, gd.piece, obstacles)
			if (joined) {
				finalT = clamp(joined)
			} else {
				const snap = computeSmartGuides(shapeToRect(movingShape), targets, {
					scaleMmPerPixel: scaleMm,
					tolerancePx: 6,
				})
				if (snap.deltaX !== 0 || snap.deltaY !== 0) {
					finalT = clamp({
						...clamped,
						offsetAlong: Math.round((clamped.offsetAlong + snap.deltaX) * 10) / 10,
						offsetDepth: Math.round((clamped.offsetDepth + snap.deltaY) * 10) / 10,
					})
				}
			}
		}

		gd.currentTransform = finalT
		const finalShape = finalT === clamped ? movingShape : build(finalT)
		activeSmartGuides.value = nonEmpty(measureGuides(shapeToRect(finalShape), targets))
	}

	// Update twin ghost transform in real-time
	if (gd.origTwinTransform && gd.twinIndex !== undefined) {
		const deltaAlong = gd.currentTransform.offsetAlong - gd.origTransform.offsetAlong
		const deltaDepth = gd.currentTransform.offsetDepth - gd.origTransform.offsetDepth
		gd.twinTransform = {
			...gd.origTwinTransform,
			offsetAlong: Math.round((gd.origTwinTransform.offsetAlong - deltaAlong) * 10) / 10,
			offsetDepth: Math.round((gd.origTwinTransform.offsetDepth + deltaDepth) * 10) / 10,
			flipX: !gd.currentTransform.flipX,
		}
	}
}

function endPieceDrag() {
	const gd = ghostDrag.value
	if (!gd) return
	window.removeEventListener('pointermove', onPiecePointerMove)
	window.removeEventListener('pointerup', endPieceDrag)
	window.removeEventListener('pointercancel', endPieceDrag)

	const idx = gd.index
	const piece = gd.piece
	const desired = gd.currentTransform
	const twinIdx = gd.twinIndex
	ghostDrag.value = null
	activeSmartGuides.value = null

	const d = drawn.value[idx]
	if (!d) return

	const obstacles = placedShapes.value.filter((obs) => {
		if (obs.index === idx) return false
		if (twinIdx !== undefined && obs.index === twinIdx) return false
		return true
	})

	const resolved = resolvePuzzleDrop(
		idx,
		piece,
		d.baseStart,
		d.baseEnd,
		d.outline,
		desired,
		obstacles,
	)
	const finalClamped = clampTransformToBoundary(piece, d.baseStart, d.baseEnd, resolved.transform, d.outline)
	commitTransformForPiece(idx, piece, finalClamped)
	if (resolved.resolvedCollision) {
		lastSnapNotice.value = 'Snapped flush to profile border'
	} else if (resolved.snapped) {
		lastSnapNotice.value = 'Snapped to mating rebate edge'
	}
}

/**
 * Start dragging/panning the cross-section workspace.
 * Works when dragging empty canvas background OR holding Shift + dragging anywhere (or middle click).
 */
function onCanvasPointerDown(e: PointerEvent) {
	if (ghostDrag.value) return
	if (e.shiftKey === false && e.button === 0) shiftHeld.value = false
	if (e.button !== 0 && e.button !== 1 && e.button !== undefined) return
	e.preventDefault()
	panDrag = {
		startX: e.clientX,
		startY: e.clientY,
		origX: sectionPan.value.x,
		origY: sectionPan.value.y,
		pointerId: e.pointerId,
		moved: false,
	}
	isPanning.value = true
	if (svgEl.value?.setPointerCapture && e.pointerId !== undefined) {
		try {
			svgEl.value.setPointerCapture(e.pointerId)
		} catch {
			// Ignore synthetic pointer events in tests
		}
	}
	window.addEventListener('pointermove', onCanvasPointerMove)
	window.addEventListener('pointerup', endWorkspacePan)
	window.addEventListener('pointercancel', endWorkspacePan)
}

function onCanvasPointerMove(e: PointerEvent) {
	if (!panDrag) return
	const scaleMm = svgUnitsPerPixel()
	const dxMm = (e.clientX - panDrag.startX) * scaleMm
	const dyMm = (e.clientY - panDrag.startY) * scaleMm
	if (Math.abs(e.clientX - panDrag.startX) > 2 || Math.abs(e.clientY - panDrag.startY) > 2) {
		panDrag.moved = true
	}
	sectionPan.value = {
		x: clampPan(panDrag.origX + dxMm),
		y: clampPan(panDrag.origY + dyMm),
	}
}

function endWorkspacePan() {
	if (!panDrag) return
	const { pointerId, moved } = panDrag
	panDrag = null
	isPanning.value = false
	if (moved) {
		suppressNextBgClick = true
		setTimeout(() => {
			suppressNextBgClick = false
		}, 0)
	}
	window.removeEventListener('pointermove', onCanvasPointerMove)
	window.removeEventListener('pointerup', endWorkspacePan)
	window.removeEventListener('pointercancel', endWorkspacePan)
	if (svgEl.value?.releasePointerCapture && pointerId !== undefined && svgEl.value.hasPointerCapture?.(pointerId)) {
		try {
			svgEl.value.releasePointerCapture(pointerId)
		} catch {
			// Ignore synthetic pointer events
		}
	}
}

function onBackgroundClick() {
	if (suppressNextBgClick) {
		suppressNextBgClick = false
		return
	}
	selectedIndex.value = null
	emit('select', '')
}

function rotateSelected(deltaDeg: number) {
	const d = selectedDrawn.value
	if (!d || d.piece.kind !== 'profile') return
	const cur = d.pieceTransform
	// Mirrored pieces are rendered with effRot = -rotation in SVG.
	// Inverting deltaDeg for mirrored pieces ensures clicking rotate clockwise (+90°)
	// visually rotates the mirrored profile clockwise (+90°) rather than counter-clockwise.
	const effectiveDelta = d.piece.mirrored ? -deltaDeg : deltaDeg
	const nextRot = (((cur.rotation + effectiveDelta) % 360) + 360) % 360
	const next: SectionPieceTransform = { ...cur, rotation: nextRot }
	const tag = pieceTags.value[d.index]
	const twinTag = mirrorSync.value && tag ? getTwinTag(tag) : null
	const twinIdx = twinTag ? pieceTags.value.indexOf(twinTag) : -1
	const obstacles = placedShapes.value.filter(
		(obs) => obs.index !== d.index && obs.index !== twinIdx,
	)
	const resolved = resolvePuzzleDrop(d.index, d.piece, d.baseStart, d.baseEnd, d.outline, next, obstacles)
	commitTransformForPiece(d.index, d.piece, resolved.transform)
}

function flipSelected(dir: 'x' | 'y') {
	const d = selectedDrawn.value
	if (!d || d.piece.kind !== 'profile') return
	const cur = d.pieceTransform
	const next: SectionPieceTransform = {
		...cur,
		flipX: dir === 'x' ? !cur.flipX : cur.flipX,
		flipY: dir === 'y' ? !cur.flipY : cur.flipY,
	}
	commitTransformForPiece(d.index, d.piece, next)
}

const savingOrientation = ref(false)

async function saveSelectedAsDefaultOrientation() {
	const d = selectedDrawn.value
	if (!d || d.piece.kind !== 'profile') return
	const code = d.piece.code
	const pieceRot = d.pieceTransform.rotation || 0
	const visualRot = (((d.piece.mirrored ? -pieceRot : pieceRot) % 360) + 360) % 360

	savingOrientation.value = true
	try {
		const res = await setProfileOrientation(code, { delta: visualRot })
		const key = instancePieceKey(axis.value, pieceTags.value[d.index] ?? d.index, d.piece)
		const nextMap = { ...activeMap.value }
		if (nextMap[key]) {
			nextMap[key] = { ...nextMap[key], rotation: 0 }
		}
		if (mirrorSync.value) {
			const canon = canonicalPieceKey(d.piece)
			for (const k in nextMap) {
				if (k.startsWith(canon) || k.endsWith(canon)) {
					nextMap[k] = { ...nextMap[k], rotation: 0 }
				}
			}
		}
		localSectionMap.value = nextMap
		emit('update:section-map', nextMap)
		toast.success(`Default orientation updated to ${res.section_rotation}° for ${code}`)
		await load()
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Could not set default orientation')
	} finally {
		savingOrientation.value = false
	}
}

function selectedDatum(): 'center' | 'outer' | null {
	const d = selectedDrawn.value
	if (!d || d.piece.kind !== 'profile') return null
	const w = d.outline?.width || d.shape.bbox.width
	const depth = d.outline?.depth || d.depth
	const u = d.pieceTransform.originU
	const dep = d.pieceTransform.originDepth
	if (u == null || dep == null) return 'center'
	if (Math.abs(u) < 0.5 && Math.abs(dep) < 0.5) return 'outer'
	if (Math.abs(u - w / 2) < 0.5 && Math.abs(dep - depth / 2) < 0.5) return 'center'
	return null
}

function setSelectedOrigin(kind: 'center' | 'outer') {
	const d = selectedDrawn.value
	if (!d || d.piece.kind !== 'profile') return
	const w = d.outline?.width || d.shape.bbox.width
	const depth = d.outline?.depth || d.depth
	commitTransformForPiece(d.index, d.piece, {
		...d.pieceTransform,
		originU: kind === 'center' ? w / 2 : 0,
		originDepth: kind === 'center' ? depth / 2 : 0,
	})
	lastSnapNotice.value = kind === 'center' ? 'Profile datum set to geometric centre' : 'Profile datum set to outer corner'
}

function resetSelectedPiece() {
	const d = selectedDrawn.value
	if (!d || d.piece.kind !== 'profile') return
	commitTransformForPiece(d.index, d.piece, defaultTransformForPiece(d.piece, d.outline))
	lastSnapNotice.value = 'Reset profile to default datum'
}

function resetAllPieces() {
	localSectionMap.value = {}
	emit('update:section-map', {})
	lastSnapNotice.value = 'Reset all profiles to default assembly'
}

function onSectionWheel(e: WheelEvent) {
	if (e.deltaY === 0) return
	e.preventDefault()
	const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
	const oldZoom = sectionZoom.value
	const nextZoom = clampZoom(oldZoom * factor)
	if (nextZoom === oldZoom) return

	updateContainerSize()
	const el = canvasWrapEl.value
	if (el) {
		const rect = el.getBoundingClientRect()
		const mx = e.clientX - rect.left
		const my = e.clientY - rect.top
		const cw = rect.width || containerSize.value.width
		const ch = rect.height || containerSize.value.height

		const rx = mx / cw - 0.5
		const ry = my / ch - 0.5

		const vb = viewBoxRect.value
		const dw = vb.w * (1 - oldZoom / nextZoom)
		const dh = vb.h * (1 - oldZoom / nextZoom)

		sectionPan.value = {
			x: clampPan(sectionPan.value.x - rx * dw),
			y: clampPan(sectionPan.value.y - ry * dh),
		}
	}
	sectionZoom.value = nextZoom
}

function isEditableTarget(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) return false
	const tag = target.tagName
	return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable
}

function onKeyDown(e: KeyboardEvent) {
	if (e.key === 'Shift' || e.shiftKey) shiftHeld.value = true
	if (isEditableTarget(e.target)) return
	if (e.key === 'r' || e.key === 'R') {
		if (selectedIndex.value !== null) {
			e.preventDefault()
			rotateSelected(e.shiftKey ? -90 : 90)
		}
	} else if (e.key === '+' || e.key === '=') {
		e.preventDefault()
		zoomIn()
	} else if (e.key === '-' || e.key === '_') {
		e.preventDefault()
		zoomOut()
	} else if (e.key === '0') {
		e.preventDefault()
		resetView()
	} else if (e.key === 'ArrowLeft') {
		e.preventDefault()
		panBy(PAN_KEY_STEP_MM, 0)
	} else if (e.key === 'ArrowRight') {
		e.preventDefault()
		panBy(-PAN_KEY_STEP_MM, 0)
	} else if (e.key === 'ArrowUp') {
		e.preventDefault()
		panBy(0, PAN_KEY_STEP_MM)
	} else if (e.key === 'ArrowDown') {
		e.preventDefault()
		panBy(0, -PAN_KEY_STEP_MM)
	} else if (e.key === 'Escape') {
		selectedIndex.value = null
	}
}

function onKeyUp(e: KeyboardEvent) {
	if (e.key === 'Shift' || !e.shiftKey) shiftHeld.value = false
}

function onWindowBlur() {
	shiftHeld.value = false
}

defineExpose({ sectionZoom, sectionPan, zoomIn, zoomOut, resetView, panBy })
</script>

<template>
	<section
		class="flex h-full w-full min-w-0 flex-1 flex-col bg-white text-gray-900 select-none"
		aria-label="Cross section"
	>
		<!-- Compact Top Bar: Axis Toggle + Mirror & Sync + 1:1 Profile Focus -->
		<div class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-200 bg-white px-3 py-1.5">
			<div class="flex flex-wrap items-center gap-2">
				<div class="flex rounded-md border border-gray-200 bg-gray-50 p-0.5" role="group" aria-label="Cut">
					<Button
						v-for="a in AXES"
						:key="a.value"
						:label="a.label"
						:variant="axis === a.value ? 'subtle' : 'ghost'"
						:aria-pressed="axis === a.value"
						class="min-h-7 text-xs"
						@click="pick(a.value)"
					/>
				</div>
				<span class="text-xs font-medium text-gray-500">{{ title }}</span>
			</div>

			<div class="flex flex-wrap items-center gap-1.5">
				<button
					type="button"
					data-testid="toggle-mirror-sync"
					:aria-pressed="mirrorSync"
					class="flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium transition-colors"
					:style="
						mirrorSync
							? { backgroundColor: '#EFF6FF', borderColor: '#3B82F6', color: '#1D4ED8' }
							: { backgroundColor: '#F9FAFB', borderColor: '#D1D5DB', color: '#4B5563' }
					"
					title="Mirror changes on opposite corners (Left <-> Right) and sync B-B (Top) with A-A (Side)"
					@click="toggleMirrorSync"
				>
					<span>⇄ Mirror &amp; Sync</span>
				</button>
				<button
					type="button"
					data-testid="toggle-compact-glass"
					:aria-pressed="compactGlass"
					class="rounded-md border px-2 py-1 text-xs font-medium transition-colors"
					:style="
						compactGlass
							? { backgroundColor: '#ECFEFF', borderColor: '#06B6D4', color: '#0E7490' }
							: { backgroundColor: '#F9FAFB', borderColor: '#D1D5DB', color: '#4B5563' }
					"
					title="Keep glass compact in the center so profile scale is large and easy to assemble"
					@click="toggleCompactGlass"
				>
					1:1 Profile Focus
				</button>
				<button
					type="button"
					data-testid="reset-all-profiles"
					class="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
					@click="resetAllPieces"
				>
					Reset All
				</button>
			</div>
		</div>

		<p v-if="error" role="alert" class="p-3 text-sm text-red-600">{{ error }}</p>

		<!-- Main Cross-Section Workspace (Same CAD Grid, Zoom & Drag-to-Pan as WindowCanvas) -->
		<template v-else-if="section">
			<div
				ref="canvasWrapEl"
				class="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-white"
			>
				<svg
					ref="svgEl"
					xmlns="http://www.w3.org/2000/svg"
					role="img"
					:aria-label="`${title}, ${section.pieces.length} pieces`"
					:viewBox="viewBoxStr"
					width="100%"
					height="100%"
					class="block h-full w-full"
					preserveAspectRatio="xMidYMid meet"
					font-family="Inter, sans-serif"
					:style="{ cursor: isPanning ? 'grabbing' : shiftHeld ? 'grab' : 'grab' }"
					@wheel="onSectionWheel"
					@pointerdown="onCanvasPointerDown"
					@pointermove="onCanvasPointerMove"
					@pointerup="endWorkspacePan"
					@pointercancel="endWorkspacePan"
					@lostpointercapture="endWorkspacePan"
				>
					<defs>
						<!-- Minor 5mm & Major 25mm CAD Grid matching WindowCanvas workspace -->
						<pattern id="section-minor-grid" width="5" height="5" patternUnits="userSpaceOnUse">
							<path d="M 5 0 L 0 0 0 5" fill="none" stroke="#E2E8F0" stroke-width="0.3" />
						</pattern>
						<pattern id="section-major-grid" width="25" height="25" patternUnits="userSpaceOnUse">
							<rect width="25" height="25" fill="url(#section-minor-grid)" />
							<path d="M 25 0 L 0 0 0 25" fill="none" stroke="#CBD5E1" stroke-width="0.5" />
						</pattern>
					</defs>

					<!-- Infinite Pan/Zoom CAD Canvas Base Background -->
					<rect
						data-section-bg="true"
						:x="-5000"
						:y="-5000"
						width="10000"
						height="10000"
						fill="#FFFFFF"
						@click="onBackgroundClick"
					/>

					<!-- Workspace Boundary Walls (Cool Light Grey Area) -->
					<!-- Left Wall (x < 0) -->
					<rect
						:x="-4000"
						:y="-4000"
						width="4000"
						height="8000"
						fill="#F1F5F9"
						pointer-events="none"
					/>

					<!-- Right Wall (x > effectiveCutLength) -->
					<rect
						:x="effectiveCutLength"
						:y="-4000"
						width="4000"
						height="8000"
						fill="#F1F5F9"
						pointer-events="none"
					/>

					<!-- Bottom Wall (y > bottomWallY) -->
					<rect
						x="0"
						:y="bottomWallY"
						:width="effectiveCutLength"
						height="4000"
						fill="#F1F5F9"
						pointer-events="none"
					/>

					<!-- Infinite Pan/Zoom CAD Grid Lines (Rendered across entire workspace so grids are visible in boundary walls too) -->
					<rect
						:x="-5000"
						:y="-5000"
						width="10000"
						height="10000"
						fill="url(#section-major-grid)"
						pointer-events="none"
					/>

					<!-- Invisible Bottom Datum Line for test anchoring -->
					<line
						data-testid="bottom-boundary-line"
						x1="0"
						:x2="effectiveCutLength"
						:y1="bottomWallY"
						:y2="bottomWallY"
						stroke="none"
						stroke-width="0"
						pointer-events="none"
					/>

					<!-- Pieces: Stationary Mullions + Moveable Glass & Profile Puzzle Pieces -->
					<template v-for="(d, i) in drawn" :key="i">
						<!-- Glass Piece (Moveable Reference) -->
						<g
							v-if="d.piece.kind === 'glass'"
							:data-piece-group="i"
							:data-ghost="d.ghost ? 'true' : undefined"
							:opacity="d.ghost ? 0.6 : 1"
							:style="{ cursor: shiftHeld ? 'grab' : d.moveable ? 'move' : 'default' }"
							@pointerdown="onPiecePointerDown($event, d)"
							@pointermove="onPiecePointerMove"
							@pointerup="endPieceDrag"
							@click.stop="onPieceClick(d)"
						>
							<rect
								:data-piece="i"
								data-kind="glass"
								:data-stationary="d.moveable ? undefined : 'true'"
								:x="d.x"
								:y="d.y"
								:width="d.w"
								:height="d.depth"
								fill="#BAE6FD"
								:fill-opacity="d.ghost ? 0.45 : 0.65"
								:stroke="d.selected ? '#2563EB' : '#0284C7'"
								:stroke-width="d.selected ? 2 : 1"
								:stroke-dasharray="d.ghost ? '3 2' : undefined"
								vector-effect="non-scaling-stroke"
							/>
							<!-- Center Break Lines on Compacted Glass -->
							<line
								v-if="compactGlass"
								:x1="d.x + d.w / 2 - 1.5"
								:x2="d.x + d.w / 2 - 0.5"
								:y1="d.y - 2"
								:y2="d.y + d.depth + 2"
								stroke="#0284C7"
								stroke-width="0.9"
								vector-effect="non-scaling-stroke"
							/>
							<line
								v-if="compactGlass"
								:x1="d.x + d.w / 2 + 0.5"
								:x2="d.x + d.w / 2 + 1.5"
								:y1="d.y - 2"
								:y2="d.y + d.depth + 2"
								stroke="#0284C7"
								stroke-width="0.9"
								vector-effect="non-scaling-stroke"
							/>
							<!-- Profile Code / Name inside chamber / between profiles with 70% opacity -->
							<text
								:x="d.labelPos.x"
								:y="d.labelPos.y"
								text-anchor="middle"
								dominant-baseline="middle"
								:font-size="d.fontSize"
								font-weight="600"
								opacity="0.7"
								:fill="d.selected ? '#1D4ED8' : '#0369A1'"
								pointer-events="none"
								:textLength="d.piece.code.length > 5 ? d.maxTextWidth : undefined"
								lengthAdjust="spacingAndGlyphs"
							>{{ d.piece.code }}</text>
						</g>

						<!-- Mullion / Transom (Stationary at exact center / design position) or Draggable Profile Piece -->
						<g
							v-else
							:data-piece-group="i"
							:data-ghost="d.ghost ? 'true' : undefined"
							:data-colliding="d.colliding ? 'true' : undefined"
							:opacity="d.ghost ? 0.55 : 1"
							:style="{ cursor: shiftHeld ? 'grab' : d.moveable ? 'move' : 'pointer' }"
							@pointerdown="onPiecePointerDown($event, d)"
							@pointermove="onPiecePointerMove"
							@pointerup="endPieceDrag"
							@click.stop="onPieceClick(d)"
						>
							<path
								v-if="d.outline"
								:data-piece="i"
								data-kind="profile"
								:data-stationary="d.moveable ? undefined : 'true'"
								:d="d.outline.svg"
								:transform="d.transform"
								:fill="d.selected ? '#3B82F6' : d.colors.fill"
								:fill-opacity="d.selected ? 0.82 : d.ghost ? 0.45 : 0.7"
								:stroke="
									d.colliding
										? '#DC2626'
										: d.selected
											? '#1D4ED8'
											: d.mirroredTwinSelected
												? '#3B82F6'
												: d.colors.stroke
								"
								:stroke-width="d.selected ? 2.5 : d.mirroredTwinSelected ? 2 : 1.35"
								:stroke-dasharray="d.ghost ? '4 2' : undefined"
								vector-effect="non-scaling-stroke"
							/>
							<rect
								v-else
								:data-piece="i"
								data-kind="profile"
								:data-stationary="d.moveable ? undefined : 'true'"
								:x="d.x"
								:y="d.y"
								:width="d.w"
								:height="d.depth"
								:fill="d.selected ? '#3B82F6' : d.colors.fill"
								:fill-opacity="d.selected ? 0.82 : 0.6"
								:stroke="d.selected ? '#1D4ED8' : d.colors.stroke"
								:stroke-width="d.selected ? 2.5 : 1.35"
								stroke-dasharray="3 2"
								vector-effect="non-scaling-stroke"
							/>
							<!-- Profile Code / Name inside profile chamber / in-between profile walls at 70% opacity -->
							<text
								:x="d.labelPos.x"
								:y="d.labelPos.y"
								text-anchor="middle"
								dominant-baseline="middle"
								:font-size="d.fontSize"
								font-weight="700"
								:opacity="d.selected ? 1 : 0.7"
								:fill="d.selected ? '#FFFFFF' : '#334155'"
								pointer-events="none"
								:textLength="d.piece.code.length > 5 ? d.maxTextWidth : undefined"
								lengthAdjust="spacingAndGlyphs"
							>{{ d.piece.code }}</text>
						</g>
					</template>

					<!-- Smart guides: solid red = edge alignment, dashed magenta = centre / glass plane.
					     Pills show distance in mm; filled red = equal to the opposite gap or a gap elsewhere. -->
					<g v-if="activeSmartGuides && ghostDrag" data-testid="smart-guides-overlay" pointer-events="none">
						<line
							v-for="(l, i) in activeSmartGuides.lines"
							:key="`guide-${i}`"
							data-testid="smart-guide-line"
							:data-guide-type="l.type"
							:data-guide-axis="l.axis"
							:x1="l.axis === 'x' ? l.pos : l.start"
							:y1="l.axis === 'x' ? l.start : l.pos"
							:x2="l.axis === 'x' ? l.pos : l.end"
							:y2="l.axis === 'x' ? l.end : l.pos"
							:stroke="GUIDE_COLORS[l.type]"
							stroke-width="1.2"
							:stroke-dasharray="l.type === 'center' ? '5 3' : undefined"
							vector-effect="non-scaling-stroke"
						/>

						<g
							v-for="s in guideGapShapes"
							:key="`gap-${s.key}`"
							data-testid="smart-guide-gap"
							:data-gap="s.gap.gap"
							:data-equal="s.gap.equal ? 'true' : 'false'"
							:opacity="s.gap.equal ? 1 : 0.85"
						>
							<line
								:x1="s.line.x1"
								:y1="s.line.y1"
								:x2="s.line.x2"
								:y2="s.line.y2"
								stroke="#e11d48"
								stroke-width="1.2"
								vector-effect="non-scaling-stroke"
							/>
							<line
								v-for="(t, ti) in s.ticks"
								:key="ti"
								:x1="t.x1"
								:y1="t.y1"
								:x2="t.x2"
								:y2="t.y2"
								stroke="#e11d48"
								stroke-width="1.2"
								vector-effect="non-scaling-stroke"
							/>
							<g :transform="`translate(${s.pill.x}, ${s.pill.y}) scale(${guideScale})`">
								<rect
									:x="-s.pill.w / 2"
									y="-8"
									:width="s.pill.w"
									height="16"
									rx="3"
									:fill="s.gap.equal ? '#e11d48' : '#ffffff'"
									stroke="#e11d48"
									stroke-width="1"
								/>
								<text
									x="0"
									y="0"
									text-anchor="middle"
									dominant-baseline="central"
									:fill="s.gap.equal ? '#ffffff' : '#e11d48'"
									font-size="10"
									font-weight="700"
									font-family="system-ui, -apple-system, sans-serif"
								>{{ s.label }}</text>
							</g>
						</g>
					</g>
				</svg>

				<!-- Slim Floating Profile Control Bar Positioned Directly Above Selected Profile -->
				<div
					v-if="selectedDrawn && selectedDrawn.piece.kind === 'profile'"
					data-testid="profile-inspector"
					class="absolute z-20 flex flex-col items-center transition-opacity duration-75"
					:class="ghostDrag ? 'pointer-events-none opacity-75' : 'pointer-events-auto opacity-100'"
					:style="selectedFloatingStyle"
					@pointerdown.stop
					@click.stop
				>
					<div class="flex h-13 items-center gap-0.5 rounded-md border border-gray-200 bg-white px-2.5 text-gray-900 shadow-[0_6px_20px_rgba(20,30,50,0.16)]">

						<!-- Profile Label & Catalog Picker trigger -->
						<button
							type="button"
							class="flex h-9 items-center gap-2 rounded px-2 transition hover:bg-gray-100"
							title="Click to search and change profile in catalog"
							@click="emit('open-profile-picker', selectedDrawn.piece)"
						>
							<span
								class="inline-block size-2 rounded-full"
								:style="{ backgroundColor: selectedDrawn.colors.stroke }"
							/>
							<span class="text-[11px] font-semibold uppercase tracking-wider text-blue-800">
								{{ selectedDrawn.piece.role }}
							</span>
							<span class="text-[13px] font-semibold text-gray-900">
								{{ selectedDrawn.piece.code }}
							</span>
						</button>

						<div class="mx-1.5 h-5.5 w-px bg-gray-200" />

						<!-- 1. Centre Datum (Pivot at Center) -->
						<button
							type="button"
							aria-label="Centre datum"
							title="Rotate and flip around profile centre"
							class="flex size-9 items-center justify-center rounded hover:bg-gray-100"
							:class="selectedDatum() === 'center' ? 'bg-blue-50 text-blue-800' : 'text-gray-900'"
							@click="setSelectedOrigin('center')"
						>
							<svg viewBox="0 0 16 16" class="size-4.5" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
								<circle cx="8" cy="8" r="2.2" />
								<path d="M8 1.6v2.2M8 12.2v2.2M1.6 8h2.2M12.2 8h2.2" stroke-linecap="round" />
							</svg>
						</button>

						<!-- 2. Outer Corner Datum (Pivot at Outer Corner) -->
						<button
							type="button"
							aria-label="Outer datum"
							title="Rotate and flip around profile outer corner"
							class="flex size-9 items-center justify-center rounded hover:bg-gray-100"
							:class="selectedDatum() === 'outer' ? 'bg-blue-50 text-blue-800' : 'text-gray-900'"
							@click="setSelectedOrigin('outer')"
						>
							<svg viewBox="0 0 16 16" class="size-4.5" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
								<path d="M4 4v8h8" stroke-linecap="round" stroke-linejoin="round" />
								<circle cx="4" cy="12" r="1.1" fill="currentColor" stroke="none" />
							</svg>
						</button>

						<div class="mx-1.5 h-5.5 w-px bg-gray-200" />

						<!-- 3. Rotate Counter-Clockwise (-90°) -->
						<button
							type="button"
							aria-label="Rotate counter-clockwise"
							title="Rotate -90° (Shift+R)"
							class="flex size-9 items-center justify-center rounded text-gray-900 hover:bg-gray-100"
							@click="rotateSelected(-90)"
						>
							<svg viewBox="0 0 640 640" class="size-4.5" fill="currentColor" aria-hidden="true">
								<path d="M88 256L232 256C241.7 256 250.5 250.2 254.2 241.2C257.9 232.2 255.9 221.9 249 215L202.3 168.3C277.6 109.7 386.6 115 455.8 184.2C530.8 259.2 530.8 380.7 455.8 455.7C380.8 530.7 259.3 530.7 184.3 455.7C174.1 445.5 165.3 434.4 157.9 422.7C148.4 407.8 128.6 403.4 113.7 412.9C98.8 422.4 94.4 442.2 103.9 457.1C113.7 472.7 125.4 487.5 139 501C239 601 401 601 501 501C601 401 601 239 501 139C406.8 44.7 257.3 39.3 156.7 122.8L105 71C98.1 64.2 87.8 62.1 78.8 65.8C69.8 69.5 64 78.3 64 88L64 232C64 245.3 74.7 256 88 256z" />
							</svg>
						</button>

						<!-- Visual Rotation Degree Readout -->
						<span class="min-w-9 text-center text-[13px] font-semibold text-gray-900">
							{{ selectedVisualRotation }}°
						</span>

						<!-- 4. Rotate Clockwise (+90°) -->
						<button
							type="button"
							aria-label="Rotate clockwise"
							title="Rotate +90° (R)"
							class="flex size-9 items-center justify-center rounded text-gray-900 hover:bg-gray-100"
							@click="rotateSelected(90)"
						>
							<svg viewBox="0 0 640 640" class="size-4.5" fill="currentColor" aria-hidden="true">
								<path d="M552 256L408 256C398.3 256 389.5 250.2 385.8 241.2C382.1 232.2 384.1 221.9 391 215L437.7 168.3C362.4 109.7 253.4 115 184.2 184.2C109.2 259.2 109.2 380.7 184.2 455.7C259.2 530.7 380.7 530.7 455.7 455.7C463.9 447.5 471.2 438.8 477.6 429.6C487.7 415.1 507.7 411.6 522.2 421.7C536.7 431.8 540.2 451.8 530.1 466.3C521.6 478.5 511.9 490.1 501 501C401 601 238.9 601 139 501C39.1 401 39 239 139 139C233.3 44.7 382.7 39.4 483.3 122.8L535 71C541.9 64.1 552.2 62.1 561.2 65.8C570.2 69.5 576 78.3 576 88L576 232C576 245.3 565.3 256 552 256z" />
							</svg>
						</button>

						<div class="mx-1.5 h-5.5 w-px bg-gray-200" />

						<!-- 5. Flip Horizontally -->
						<button
							type="button"
							aria-label="Flip horizontal"
							title="Flip horizontally"
							class="flex size-9 items-center justify-center rounded hover:bg-gray-100"
							:class="selectedDrawn.pieceTransform.flipX ? 'bg-blue-50 text-blue-800' : 'text-gray-900'"
							@click="flipSelected('x')"
						>
							<svg viewBox="0 0 16 16" class="size-4.5" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
								<path d="M8 2.4v11.2" stroke-linecap="round" />
								<path d="M5.6 5.4 3.2 8l2.4 2.6M10.4 5.4 12.8 8l-2.4 2.6" stroke-linecap="round" stroke-linejoin="round" />
							</svg>
						</button>

						<!-- 6. Flip Vertically -->
						<button
							type="button"
							aria-label="Flip vertical"
							title="Flip vertically"
							class="flex size-9 items-center justify-center rounded hover:bg-gray-100"
							:class="selectedDrawn.pieceTransform.flipY ? 'bg-blue-50 text-blue-800' : 'text-gray-900'"
							@click="flipSelected('y')"
						>
							<svg viewBox="0 0 16 16" class="size-4.5" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
								<path d="M2.4 8h11.2" stroke-linecap="round" />
								<path d="M5.4 5.6 8 3.2l2.6 2.4M5.4 10.4 8 12.8l2.6-2.4" stroke-linecap="round" stroke-linejoin="round" />
							</svg>
						</button>

						<div class="mx-1.5 h-5.5 w-px bg-gray-200" />

						<!-- 7. Set As Default Orientation (Persists to DocType) -->
						<button
							type="button"
							aria-label="Set as default orientation"
							title="Save current orientation as default for this profile"
							class="flex h-9 items-center rounded px-3 text-[13px] font-medium transition-colors hover:bg-gray-100"
							:class="selectedVisualRotation !== 0 ? 'text-blue-800 font-semibold' : 'text-gray-900'"
							:disabled="savingOrientation"
							@click="saveSelectedAsDefaultOrientation"
						>
							Set default
						</button>

						<!-- 8. Reset Profile Position & Orientation -->
						<button
							type="button"
							aria-label="Reset selected profile"
							title="Reset this profile"
							class="flex size-9 items-center justify-center rounded text-gray-900 hover:bg-gray-100"
							@click="resetSelectedPiece"
						>
							<svg viewBox="0 0 16 16" class="size-4.5" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
								<path d="M12.6 8a4.6 4.6 0 1 1-1.2-3.1" stroke-linecap="round" />
								<path d="M11.2 2.2v3H8.2" stroke-linecap="round" stroke-linejoin="round" />
							</svg>
						</button>
					</div>

					<!-- Downward Pointer Caret Anchored Above the Profile -->
					<div class="h-1.5 w-3 overflow-hidden">
						<div class="mx-auto size-2 -translate-y-1 rotate-45 border-r border-b border-gray-200 bg-white" />
					</div>
				</div>

				<!-- Bottom-Left CAD Section Summary Readout -->
				<div
					class="pointer-events-none absolute bottom-3 left-3 flex items-center gap-3 rounded-lg border border-gray-200 bg-white/95 px-2.5 py-1 font-mono text-xs text-gray-600 shadow-xs backdrop-blur-xs"
				>
					<span>Section</span>
					<span class="font-semibold text-gray-900">{{ sectionExtentLabel }}</span>
					<span v-if="ghostDrag" class="font-sans font-medium text-amber-600">
						Ghost Mode · release to snap
					</span>
					<span v-else-if="lastSnapNotice" class="font-sans font-medium" style="color: #059669">
						{{ lastSnapNotice }}
					</span>
				</div>

				<!-- Bottom-Right Workspace Zoom & Pan Controls (Identical to WindowCanvas) -->
				<div
					class="pointer-events-auto absolute right-3 bottom-3 flex items-center gap-1 rounded-lg border border-gray-200 bg-white/95 px-1.5 py-1 shadow-xs backdrop-blur-xs"
					role="toolbar"
					aria-label="Section workspace controls"
				>
					<span class="hidden px-1.5 text-[11px] text-gray-500 sm:inline">Drag or Shift + drag to pan</span>
					<div class="hidden h-3.5 w-px bg-gray-200 sm:block" />
					<button
						type="button"
						aria-label="Zoom out section"
						title="Zoom out (-)"
						:disabled="sectionZoom <= MIN_SECTION_ZOOM"
						class="flex h-6 w-6 items-center justify-center rounded text-sm font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-40"
						@click="zoomOut"
					>
						−
					</button>
					<button
						type="button"
						aria-label="Reset section zoom"
						title="Reset view (0)"
						class="min-w-12 rounded px-1.5 py-0.5 text-center font-mono text-xs font-medium text-gray-700 hover:bg-gray-100"
						@click="resetView"
					>
						{{ Math.round(sectionZoom * 100) }}%
					</button>
					<button
						type="button"
						aria-label="Zoom in section"
						title="Zoom in (+)"
						:disabled="sectionZoom >= MAX_SECTION_ZOOM"
						class="flex h-6 w-6 items-center justify-center rounded text-sm font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-40"
						@click="zoomIn"
					>
						+
					</button>
				</div>
			</div>

			<div v-if="missing.length || issues.length" class="border-t border-gray-200 bg-gray-50 px-3 py-1.5">
				<p v-if="missing.length" data-testid="missing-outlines" class="text-xs text-gray-500">
					No section outline for {{ missing.join(', ') }}; drawn as boxes.
				</p>
				<p v-for="(iss, i) in issues" :key="i" class="text-xs text-amber-600">{{ iss.message }}</p>
			</div>
		</template>
		<p v-else class="p-4 text-sm text-gray-400">Cutting...</p>
	</section>
</template>
