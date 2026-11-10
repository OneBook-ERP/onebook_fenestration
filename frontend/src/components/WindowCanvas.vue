<script lang="ts">
/** Workspace zoom ("pan in / pan out") and pan offset limits. */
export const MIN_ZOOM = 0.4
export const MAX_ZOOM = 3.0
export const ZOOM_STEP = 0.15
export const MAX_PAN_OFFSET = 1200
export const DEFAULT_FINISH = '#8A8F98'
</script>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { layoutGeom } from '@/design/geometry'
import { getNode } from '@/design/tree'
import type { BarGeom, CellGeom, Design, SplitNode } from '@/design/types'

const FRAME_FACE_DEFAULT = 42
const BAR_FACE_DEFAULT = 40
const SASH_FACE_DEFAULT = 50
const PAD = 60
const FONT = 'Inter, sans-serif'
const GRID_EXTENT = 2880

const PAN_KEY_STEP = 40

const C = {
	glass: '#DCEBF7',
	stroke: '#5B6470',
	select: '#2563EB',
	issue: '#D97706',
	dim: '#404040',
	cut: '#DC2626',
}

const frameFace = computed(() => {
	const widths = props.profileWidths
	if (!widths) return FRAME_FACE_DEFAULT
	const overrideCode = props.design.frameProfileId || props.design.profiles?.frame
	if (overrideCode && widths[overrideCode]) return widths[overrideCode]
	const memberCode = props.members?.find((m) => m.role === 'frame')?.profile
	if (memberCode && widths[memberCode]) return widths[memberCode]
	return FRAME_FACE_DEFAULT
})

function sashFaceFor(cell: CellGeom): number {
	const widths = props.profileWidths
	if (!widths) return SASH_FACE_DEFAULT
	const node = cell.node
	if (node.type !== 'sash') return SASH_FACE_DEFAULT
	const overrideCode = node.profile || props.design.profiles?.[cell.path]
	if (overrideCode && widths[overrideCode]) return widths[overrideCode]
	const memberCode = props.members?.find((m) => m.role === 'sash' && m.path === cell.path)?.profile
	if (memberCode && widths[memberCode]) return widths[memberCode]
	return SASH_FACE_DEFAULT
}

function barFaceFor(bar: BarGeom): number {
	const widths = props.profileWidths
	if (!widths) return BAR_FACE_DEFAULT
	const role = bar.dir === 'v' ? 'mullion' : 'transom'
	const overrideCode = props.design.profiles?.[bar.id]
	if (overrideCode && widths[overrideCode]) return widths[overrideCode]
	const memberCode = props.members?.find((m) => (m.panel === bar.id || m.path === bar.id) && (m.role === role || m.role === 'mullion' || m.role === 'transom'))?.profile
	if (memberCode && widths[memberCode]) return widths[memberCode]
	return BAR_FACE_DEFAULT
}

const props = withDefaults(
	defineProps<{
		design: Design
		selectedPath: string | null
		issuePaths: string[]
		view: 'inside' | 'outside'
		viewW?: number
		viewH?: number
		finishColor?: string
		/** Section view on: cut positions in mm (h = height of the B–B cut, v = x of the A–A cut). */
		section?: { axis: 'h' | 'v'; h: number; v: number } | null
		/** Optional computed members used to determine corner joints and exact member lengths. */
		members?: {
			role?: string
			path?: string
			panel?: string
			position?: string
			length?: number
			profile?: string
			angles?: unknown
		}[]
		/** Optional computed glass rows used to display exact glass cut width & height on selection. */
		glass?: { path?: string; panel?: string; glass?: string; width?: number; height?: number }[]
		/** Optional profile max width lookup (e.g. { E104156: 50, E104160: 60, E104159: 70 }) to dynamically size frame/sash/mullion face widths. */
		profileWidths?: Record<string, number>
	}>(),
	{ viewW: 640, viewH: 760, finishColor: '#8A8F98', section: null, members: undefined, glass: undefined, profileWidths: undefined },
)
const emit = defineEmits<{
	select: [path: string]
	'move-split': [payload: { splitPath: string; index: number; pos: number }]
	'drag-start': []
	'drag-end': []
	'update:cut': [payload: { axis: 'h' | 'v'; at: number }]
}>()

/** Mix a #RRGGBB colour towards white by `amount` (0..1). */
function lighten(hex: string, amount: number): string {
	const n = parseInt(hex.slice(1), 16)
	const mix = (shift: number) => {
		const c = (n >> shift) & 255
		return Math.round(c + (255 - c) * amount)
	}
	return '#' + [16, 8, 0].map((s) => mix(s).toString(16).padStart(2, '0')).join('').toUpperCase()
}
/** Finish colours come from a free Color field; anything but #RRGGBB falls back to the default. */
const finish = computed(() => (/^#[0-9a-f]{6}$/i.test(props.finishColor) ? props.finishColor : DEFAULT_FINISH))
const frameFill = finish
const sashFill = computed(() => lighten(finish.value, 0.1))

const svg = ref<SVGSVGElement | null>(null)
const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const shiftHeld = ref(false)
const isPanning = ref(false)
let suppressNextClick = false

function clampZoom(z: number): number {
	return Math.round(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z)) * 100) / 100
}

function clampPan(v: number): number {
	return Math.min(MAX_PAN_OFFSET, Math.max(-MAX_PAN_OFFSET, v))
}

function zoomIn() {
	zoom.value = clampZoom(zoom.value + ZOOM_STEP)
}

function zoomOut() {
	zoom.value = clampZoom(zoom.value - ZOOM_STEP)
}

function resetView() {
	zoom.value = 1
	pan.value = { x: 0, y: 0 }
}

function panBy(dx: number, dy: number) {
	pan.value = { x: clampPan(pan.value.x + dx), y: clampPan(pan.value.y + dy) }
}

const viewBoxStr = computed(() => {
	const w = props.viewW / zoom.value
	const h = props.viewH / zoom.value
	const x = (props.viewW - w) / 2 - pan.value.x
	const y = (props.viewH - h) / 2 - pan.value.y
	return `${fmt(x)} ${fmt(y)} ${fmt(w)} ${fmt(h)}`
})

const scale = computed(() =>
	Math.min((props.viewW - 2 * PAD) / props.design.width, (props.viewH - 2 * PAD) / props.design.height),
)
const originX = computed(() => (props.viewW - props.design.width * scale.value) / 2)
const originY = computed(() => (props.viewH - props.design.height * scale.value) / 2)
const geom = computed(() => layoutGeom(props.design))

const px = (mm: number) => originX.value + mm * scale.value
const py = (mm: number) => originY.value + (props.design.height - mm) * scale.value
const fmt = (n: number) => String(Math.round(n * 100) / 100)

interface Box {
	x: number
	y: number
	w: number
	h: number
}

/** Pixel box of the visible opening of a cell: frame at the outside, half a bar at inner edges. */
function cellBox(c: CellGeom): Box {
	const { width, height } = props.design
	const ff = frameFace.value
	const l = c.x === 0 ? ff : BAR_FACE_DEFAULT / 2
	const r = c.x + c.w === width ? ff : BAR_FACE_DEFAULT / 2
	const b = c.y === 0 ? ff : BAR_FACE_DEFAULT / 2
	const t = c.y + c.h === height ? ff : BAR_FACE_DEFAULT / 2
	return {
		x: px(c.x + l),
		y: py(c.y + c.h - t),
		w: (c.w - l - r) * scale.value,
		h: (c.h - t - b) * scale.value,
	}
}

function inset(b: Box, mm: number): Box {
	const d = mm * scale.value
	return { x: b.x + d, y: b.y + d, w: Math.max(0, b.w - 2 * d), h: Math.max(0, b.h - 2 * d) }
}

type HingeSide = 'left' | 'right' | 'top'
type CutAngle = 45 | 90

interface LineSeg {
	x1: number
	y1: number
	x2: number
	y2: number
}

interface HandlePos {
	x: number
	y: number
	w: number
	h: number
}

interface CellView {
	cell: CellGeom
	box: Box
	glass: Box
	panelId: string
	glassNo: number
	selected: boolean
	glassSelected: boolean
	issue: boolean
	stroke: string
	strokeWidth: number
	lines: string[]
	side: HingeSide | null
	hingeLine: LineSeg | null
	corners: LineSeg[]
	cutAngle: CutAngle
	handle: HandlePos | null
	hasBead: boolean
	beadBox: Box
	sashW: number | null
	sashH: number | null
	glassW: number
	glassH: number
}

interface BarView {
	bar: BarGeom
	rect: Box
	selected: boolean
	cutLength: number
	spanLength: number
	faceWidth: number
	pos: number
}

function parseCutAngle(angles: unknown): CutAngle {
	if (Array.isArray(angles)) {
		return angles.some((a) => Number(a) === 90) && !angles.some((a) => Number(a) === 45 || Number(a) === 135) ? 90 : 45
	}
	if (typeof angles === 'string') {
		const nums = (angles.match(/\d+/g) ?? []).map(Number)
		if (nums.includes(90) && !nums.includes(45) && !nums.includes(135)) return 90
	}
	return 45
}

function roleCutAngle(role: string, path?: string): CutAngle {
	const list = props.members
	if (!list?.length) return 45
	const match = (path ? list.find((m) => m.role === role && m.path === path) : undefined) ?? list.find((m) => m.role === role)
	return match ? parseCutAngle(match.angles) : 45
}

/** 45° corner miter lines or 90° butt joint lines at all 4 corners between outer and inner boxes. */
function cornerLines(outer: Box, inner: Box, angle: CutAngle): LineSeg[] {
	if (angle === 90) {
		return [
			{ x1: outer.x, y1: inner.y, x2: inner.x, y2: inner.y },
			{ x1: inner.x + inner.w, y1: inner.y, x2: outer.x + outer.w, y2: inner.y },
			{ x1: outer.x, y1: inner.y + inner.h, x2: inner.x, y2: inner.y + inner.h },
			{ x1: inner.x + inner.w, y1: inner.y + inner.h, x2: outer.x + outer.w, y2: inner.y + inner.h },
		]
	}
	return [
		{ x1: outer.x, y1: outer.y, x2: inner.x, y2: inner.y },
		{ x1: outer.x + outer.w, y1: outer.y, x2: inner.x + inner.w, y2: inner.y },
		{ x1: outer.x, y1: outer.y + outer.h, x2: inner.x, y2: inner.y + inner.h },
		{ x1: outer.x + outer.w, y1: outer.y + outer.h, x2: inner.x + inner.w, y2: inner.y + inner.h },
	]
}

function hingeSide(c: CellGeom): HingeSide | null {
	const node = c.node
	if (node.type !== 'sash' || !node.hinge) return null
	if (node.hinge === 'top') return 'top'
	const h = node.hinge === 'right' ? 'right' : 'left'
	if (props.view === 'inside') return h
	return h === 'left' ? 'right' : 'left'
}

function computeHingeLine(box: Box, side: HingeSide | null): LineSeg | null {
	if (!side) return null
	if (side === 'top') {
		return { x1: box.x, y1: box.y, x2: box.x + box.w, y2: box.y }
	}
	const x = side === 'left' ? box.x : box.x + box.w
	return { x1: x, y1: box.y, x2: x, y2: box.y + box.h }
}

/** Swing triangle: the apex sits on the hinged edge. */
function openingLines(b: Box, side: HingeSide): string[] {
	if (side === 'top') return [`${b.x},${b.y + b.h} ${b.x + b.w / 2},${b.y} ${b.x + b.w},${b.y + b.h}`]
	const apexX = side === 'left' ? b.x : b.x + b.w
	const farX = side === 'left' ? b.x + b.w : b.x
	const midY = b.y + b.h / 2
	return [
		`${farX},${b.y} ${apexX},${midY} ${farX},${b.y + b.h}`,
	]
}

/** Handle placed at the center of each sash on the rail opposite to the hinge. */
function computeHandlePos(cell: CellGeom, box: Box, glass: Box, side: HingeSide | null): HandlePos | null {
	if (cell.node.type !== 'sash') return null
	const hSide = side || 'left'
	if (hSide === 'top') {
		const railCenterY = glass.y + glass.h + (box.y + box.h - (glass.y + glass.h)) / 2
		return {
			x: box.x + box.w / 2 - 12,
			y: railCenterY - 2.5,
			w: 24,
			h: 5,
		}
	}
	const handleCenterY = box.y + box.h / 2
	const railCenterX =
		hSide === 'left'
			? glass.x + glass.w + (box.x + box.w - (glass.x + glass.w)) / 2
			: box.x + (glass.x - box.x) / 2
	return {
		x: railCenterX - 2.5,
		y: handleCenterY - 13,
		w: 5,
		h: 26,
	}
}

function round1(n: number): number {
	return Math.round(n * 10) / 10
}

const cells = computed<CellView[]>(() => {
	// Fixed panes show only their glass number; F<n> would clash with the frame id.
	const counts: Record<string, number> = { S: 0, L: 0 }
	const memberList = props.members ?? []
	const glassList = props.glass ?? []
	return geom.value.cells.map((cell, i) => {
		const prefix = cell.node.type === 'sash' ? 'S' : cell.node.type === 'louver' ? 'L' : ''
		const box = cellBox(cell)
		const isSash = cell.node.type === 'sash'
		const selected = cell.path === props.selectedPath
		const glassSelected = props.selectedPath === `GLASS:${cell.path}`
		const issue = props.issuePaths.includes(cell.path)
		const side = hingeSide(cell)
		const sf = sashFaceFor(cell)
		const glass = isSash ? inset(box, sf) : box
		const cutAngle = isSash ? roleCutAngle('sash', cell.path) : 45

		const sashMembers = isSash ? memberList.filter((m) => m.role === 'sash' && m.path === cell.path) : []
		const wMember = sashMembers.find((m) => m.position === 'B' || m.position === 'T')
		const hMember = sashMembers.find((m) => m.position === 'L' || m.position === 'R')
		const openW = round1(box.w / scale.value)
		const openH = round1(box.h / scale.value)
		const sashW = isSash ? (wMember?.length !== undefined ? round1(Number(wMember.length)) : openW) : null
		const sashH = isSash ? (hMember?.length !== undefined ? round1(Number(hMember.length)) : openH) : null

		const gRow = glassList.find((g) => g.path === cell.path)
		const geomGlassW = round1(glass.w / scale.value)
		const geomGlassH = round1(glass.h / scale.value)
		const glassW = gRow?.width !== undefined ? round1(Number(gRow.width)) : geomGlassW
		const glassH = gRow?.height !== undefined ? round1(Number(gRow.height)) : geomGlassH
		const hasBead = (cell.node.type === 'fixed' || cell.node.type === 'sash') && cell.node.bead !== false
		const beadInsetMm = Math.min(14, Math.max(4, openW * 0.08), Math.max(4, openH * 0.08))
		const beadBox = inset(glass, beadInsetMm)

		return {
			cell,
			box,
			glass,
			panelId: prefix ? `${prefix}${++counts[prefix]}` : '',
			glassNo: i + 1,
			selected,
			glassSelected,
			issue,
			stroke: selected ? C.select : issue ? C.issue : C.stroke,
			strokeWidth: selected ? 3 : issue ? 2 : 1,
			lines: side ? openingLines(glass, side) : [],
			side,
			hingeLine: isSash ? computeHingeLine(box, side) : null,
			corners: isSash ? cornerLines(box, glass, cutAngle) : [],
			cutAngle,
			handle: computeHandlePos(cell, box, glass, side),
			hasBead,
			beadBox,
			sashW,
			sashH,
			glassW,
			glassH,
		}
	})
})

function louverYs(v: CellView): number[] {
	const node = v.cell.node
	if (node.type !== 'louver' || node.blades < 1) return []
	const step = v.box.h / node.blades
	return Array.from({ length: node.blades - 1 }, (_, k) => v.box.y + step * (k + 1))
}

const ghh = computed(() => {
	const sash = geom.value.cells.find((c) => c.node.type === 'sash' && c.node.ghh)
	return sash && sash.node.type === 'sash' ? sash.node.ghh : null
})

function barRect(bar: BarGeom): Box {
	const { width, height } = props.design
	const ff = frameFace.value
	const bf = barFaceFor(bar)
	if (bar.dir === 'v') {
		const b = bar.y === 0 ? ff : bf / 2
		const t = bar.y + bar.length === height ? ff : bf / 2
		return {
			x: px(bar.x - bf / 2),
			y: py(bar.y + bar.length - t),
			w: bf * scale.value,
			h: Math.max(0, (bar.length - b - t) * scale.value),
		}
	}
	const l = bar.x === 0 ? ff : bf / 2
	const r = bar.x + bar.length === width ? ff : bf / 2
	return {
		x: px(bar.x + l),
		y: py(bar.y + bf / 2),
		w: Math.max(0, (bar.length - l - r) * scale.value),
		h: bf * scale.value,
	}
}

const bars = computed<BarView[]>(() => {
	const memberList = props.members ?? []
	return geom.value.bars.map((bar) => {
		const rect = barRect(bar)
		const selected = props.selectedPath === bar.id
		const mRow = memberList.find((m) => m.panel === bar.id || m.path === bar.id)
		const geomCut = round1((bar.dir === 'v' ? rect.h : rect.w) / scale.value)
		const cutLength = mRow?.length !== undefined ? round1(Number(mRow.length)) : geomCut
		const bf = barFaceFor(bar)
		return {
			bar,
			rect,
			selected,
			cutLength,
			spanLength: round1(bar.length),
			faceWidth: bf,
			pos: round1(bar.dir === 'v' ? bar.x : bar.y),
		}
	})
})

const frameBox = computed<Box>(() => ({
	x: px(0),
	y: py(props.design.height),
	w: props.design.width * scale.value,
	h: props.design.height * scale.value,
}))

const frameInner = computed<Box>(() => inset(frameBox.value, frameFace.value))
const frameSelected = computed(() => props.selectedPath === 'FRAME' || props.selectedPath === 'F1')
const frameCutAngle = computed<CutAngle>(() => roleCutAngle('frame', 'F1'))
const frameCorners = computed<LineSeg[]>(() => cornerLines(frameBox.value, frameInner.value, frameCutAngle.value))

const gridMinorPath = computed(() => {
	const step = 24
	const minX = -GRID_EXTENT
	const maxX = props.viewW + GRID_EXTENT
	const minY = -GRID_EXTENT
	const maxY = props.viewH + GRID_EXTENT
	const parts: string[] = []
	for (let x = minX; x <= maxX; x += step) {
		if (x % 120 === 0) continue
		parts.push(`M ${x} ${minY} L ${x} ${maxY}`)
	}
	for (let y = minY; y <= maxY; y += step) {
		if (y % 120 === 0) continue
		parts.push(`M ${minX} ${y} L ${maxX} ${y}`)
	}
	return parts.join(' ')
})

const gridMajorPath = computed(() => {
	const step = 120
	const minX = -GRID_EXTENT
	const maxX = props.viewW + GRID_EXTENT
	const minY = -GRID_EXTENT
	const maxY = props.viewH + GRID_EXTENT
	const parts: string[] = []
	for (let x = minX; x <= maxX; x += step) {
		parts.push(`M ${x} ${minY} L ${x} ${maxY}`)
	}
	for (let y = minY; y <= maxY; y += step) {
		parts.push(`M ${minX} ${y} L ${maxX} ${y}`)
	}
	return parts.join(' ')
})

interface Dim {
	from: number
	to: number
	label: string
}

function segments(total: number, at: number[]): Dim[] {
	const bounds = [0, ...at, total]
	return bounds.slice(1).map((b, i) => ({ from: bounds[i], to: b, label: fmt(b - bounds[i]) }))
}

const root = computed(() => props.design.root)
const cols = computed<Dim[]>(() => {
	const r = root.value
	return r.type === 'split' && r.dir === 'v' ? segments(props.design.width, r.at) : []
})
const rows = computed<Dim[]>(() => {
	const r = root.value
	return r.type === 'split' && r.dir === 'h' ? segments(props.design.height, r.at) : []
})

/** A–A is the vertical cut line, B–B the horizontal one; the badges sit on the frame member at each end. */
const cuts = computed(() => {
	const s = props.section
	if (!s) return []
	const f = frameBox.value
	const face = (frameFace.value / 2) * scale.value
	const ends = 10
	const x = px(s.v)
	const y = py(s.h)
	return [
		{ axis: 'v' as const, letter: 'A', x1: x, x2: x, y1: f.y - ends, y2: f.y + f.h + ends, badges: [[x, f.y + face], [x, f.y + f.h - face]] },
		{ axis: 'h' as const, letter: 'B', x1: f.x - ends, x2: f.x + f.w + ends, y1: y, y2: y, badges: [[f.x + face, y], [f.x + f.w - face, y]] },
	].map((c) => ({ ...c, active: c.axis === s.axis }))
})

function onFrameClick(e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false
		return
	}
	emit('select', 'FRAME')
}

function onGlassClick(c: CellGeom, e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false
		return
	}
	emit('select', `GLASS:${c.path}`)
	const s = props.section
	if (s) emit('update:cut', { axis: s.axis, at: s.axis === 'h' ? c.y + c.h / 2 : c.x + c.w / 2 })
}

function onCellClick(c: CellGeom, e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false
		return
	}
	emit('select', c.path)
	const s = props.section
	if (s) emit('update:cut', { axis: s.axis, at: s.axis === 'h' ? c.y + c.h / 2 : c.x + c.w / 2 })
}

let barSelectedOnPointerDown = false

function onBarClick(bar: BarGeom, e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false
		barSelectedOnPointerDown = false
		return
	}
	if (barSelectedOnPointerDown) {
		barSelectedOnPointerDown = false
		return
	}
	emit('select', bar.id)
	const s = props.section
	if (s) emit('update:cut', { axis: s.axis, at: s.axis === 'h' ? bar.y : bar.x })
}

function onBackgroundClick(e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false
		return
	}
	emit('select', '')
}

const ariaLabel = computed(
	() => `Window ${fmt(props.design.width)} by ${fmt(props.design.height)} mm, ${geom.value.cells.length} panels`,
)

function screenToViewFactor(): number {
	const r = svg.value?.getBoundingClientRect()
	// preserveAspectRatio "meet" scales both axes by the smaller ratio.
	const meet = r && r.width && r.height ? Math.min(r.width / props.viewW, r.height / props.viewH) : 0
	return (meet ? 1 / meet : 1) / zoom.value
}

interface Drag {
	bar: BarGeom
	start: number
	original: number
	el: Element
	pointerId: number
}
let drag: Drag | null = null

interface PanDrag {
	startX: number
	startY: number
	origX: number
	origY: number
	pointerId: number
	moved: boolean
}
let panDrag: PanDrag | null = null

function onPointerDown(e: PointerEvent, bar: BarGeom) {
	if (e.shiftKey === false) shiftHeld.value = false
	if (e.shiftKey || shiftHeld.value) return
	if (e.button !== 0 && e.button !== undefined) return
	e.preventDefault()
	barSelectedOnPointerDown = true
	emit('select', bar.id)
	const split = getNode(props.design, bar.splitPath) as SplitNode
	const el = e.currentTarget as Element
	drag = { bar, start: bar.dir === 'v' ? e.clientX : e.clientY, original: split.at[bar.index], el, pointerId: e.pointerId }
	if (el.setPointerCapture) el.setPointerCapture(e.pointerId)
	// Belt and braces: the up event may miss the bar, so any of these ends the drag.
	window.addEventListener('pointerup', endDrag)
	window.addEventListener('pointercancel', endDrag)
	emit('drag-start')
}

function onPointerMove(e: PointerEvent) {
	if (!drag) return
	const vertical = drag.bar.dir === 'v'
	const k = screenToViewFactor()
	const cur = vertical ? e.clientX : e.clientY
	const delta = ((cur - drag.start) * k) / scale.value
	const pos = drag.bar.dir === 'v' ? drag.original + delta : drag.original - delta
	emit('move-split', { splitPath: drag.bar.splitPath, index: drag.bar.index, pos })
}

function endDrag() {
	setTimeout(() => {
		barSelectedOnPointerDown = false
	}, 0)
	if (!drag) return
	const { el, pointerId } = drag
	drag = null
	window.removeEventListener('pointerup', endDrag)
	window.removeEventListener('pointercancel', endDrag)
	if (el.releasePointerCapture && el.hasPointerCapture?.(pointerId)) el.releasePointerCapture(pointerId)
	emit('drag-end')
}

function onCanvasPointerDown(e: PointerEvent) {
	if (e.shiftKey === false && e.button === 0) shiftHeld.value = false
	if (!(e.shiftKey || shiftHeld.value || e.button === 1)) return
	if (e.button !== 0 && e.button !== 1 && e.button !== undefined) return
	e.preventDefault()
	panDrag = {
		startX: e.clientX,
		startY: e.clientY,
		origX: pan.value.x,
		origY: pan.value.y,
		pointerId: e.pointerId,
		moved: false,
	}
	isPanning.value = true
	if (svg.value?.setPointerCapture) svg.value.setPointerCapture(e.pointerId)
	window.addEventListener('pointermove', onCanvasPointerMove)
	window.addEventListener('pointerup', endPan)
	window.addEventListener('pointercancel', endPan)
}

function onCanvasPointerMove(e: PointerEvent) {
	if (!panDrag) return
	const k = screenToViewFactor()
	const dx = (e.clientX - panDrag.startX) * k
	const dy = (e.clientY - panDrag.startY) * k
	if (Math.abs(e.clientX - panDrag.startX) > 2 || Math.abs(e.clientY - panDrag.startY) > 2) {
		panDrag.moved = true
	}
	pan.value = {
		x: clampPan(panDrag.origX + dx),
		y: clampPan(panDrag.origY + dy),
	}
}

function endPan() {
	if (!panDrag) return
	const { pointerId, moved } = panDrag
	panDrag = null
	isPanning.value = false
	if (moved) {
		suppressNextClick = true
		setTimeout(() => {
			suppressNextClick = false
		}, 0)
	}
	window.removeEventListener('pointermove', onCanvasPointerMove)
	window.removeEventListener('pointerup', endPan)
	window.removeEventListener('pointercancel', endPan)
	if (svg.value?.releasePointerCapture && svg.value.hasPointerCapture?.(pointerId)) {
		svg.value.releasePointerCapture(pointerId)
	}
}

function onWheel(e: WheelEvent) {
	if (e.deltaY === 0) return
	e.preventDefault()
	if (e.deltaY < 0) zoomIn()
	else zoomOut()
}

function isEditableTarget(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) return false
	const tag = target.tagName
	return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable
}

function onKeyDown(e: KeyboardEvent) {
	if (e.key === 'Shift' || e.shiftKey) shiftHeld.value = true
	if (isEditableTarget(e.target)) return
	if (e.key === '+' || e.key === '=') {
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
		panBy(PAN_KEY_STEP, 0)
	} else if (e.key === 'ArrowRight') {
		e.preventDefault()
		panBy(-PAN_KEY_STEP, 0)
	} else if (e.key === 'ArrowUp') {
		e.preventDefault()
		panBy(0, PAN_KEY_STEP)
	} else if (e.key === 'ArrowDown') {
		e.preventDefault()
		panBy(0, -PAN_KEY_STEP)
	}
}

function onKeyUp(e: KeyboardEvent) {
	if (e.key === 'Shift' || !e.shiftKey) shiftHeld.value = false
}

function onWindowBlur() {
	shiftHeld.value = false
}

onMounted(() => {
	window.addEventListener('keydown', onKeyDown)
	window.addEventListener('keyup', onKeyUp)
	window.addEventListener('blur', onWindowBlur)
})

onUnmounted(() => {
	endDrag()
	endPan()
	window.removeEventListener('keydown', onKeyDown)
	window.removeEventListener('keyup', onKeyUp)
	window.removeEventListener('blur', onWindowBlur)
})

function getSvgMarkup(): string {
	if (!svg.value) return ''
	const clone = svg.value.cloneNode(true) as SVGSVGElement
	clone.removeAttribute('style')
	clone.querySelectorAll('[data-cut], [data-highlight]').forEach((el) => el.remove())
	clone.setAttribute('viewBox', `0 0 ${props.viewW} ${props.viewH}`)
	clone.setAttribute('width', String(props.viewW))
	clone.setAttribute('height', String(props.viewH))
	const bgRect = clone.querySelector('rect')
	if (bgRect) {
		bgRect.setAttribute('x', '0')
		bgRect.setAttribute('y', '0')
		bgRect.setAttribute('width', String(props.viewW))
		bgRect.setAttribute('height', String(props.viewH))
	}
	clone.querySelectorAll('*').forEach((el) => {
		for (const a of Array.from(el.attributes)) {
			if (a.name.startsWith('data-') || a.name === 'style') el.removeAttribute(a.name)
		}
		if (el.classList.contains('hl')) {
			el.setAttribute('stroke', C.stroke)
			el.setAttribute('stroke-width', '1')
			el.removeAttribute('class')
		}
		if (el.classList.contains('hl-badge')) {
			el.setAttribute('fill', '#FFFFFF')
			el.setAttribute('stroke', C.dim)
			el.removeAttribute('class')
		}
		if (el.classList.contains('hl-badge-text')) {
			el.setAttribute('fill', C.dim)
			el.removeAttribute('class')
		}
	})
	return clone.outerHTML
}
defineExpose({ getSvgMarkup, zoom, pan, zoomIn, zoomOut, resetView, panBy })
</script>

<template>
	<div class="relative flex h-full w-full flex-1 items-center justify-center overflow-hidden bg-white select-none">
		<svg
			ref="svg"
			xmlns="http://www.w3.org/2000/svg"
			role="img"
			:aria-label="ariaLabel"
			:viewBox="viewBoxStr"
			width="100%"
			height="100%"
			preserveAspectRatio="xMidYMid meet"
			:font-family="FONT"
			:style="{ cursor: isPanning ? 'grabbing' : shiftHeld ? 'grab' : 'default' }"
			@wheel="onWheel"
			@pointerdown="onCanvasPointerDown"
			@pointermove="onCanvasPointerMove"
			@pointerup="endPan"
			@pointercancel="endPan"
			@lostpointercapture="endPan"
		>
			<rect
				data-workspace-bg="true"
				:x="-GRID_EXTENT"
				:y="-GRID_EXTENT"
				:width="viewW + GRID_EXTENT * 2"
				:height="viewH + GRID_EXTENT * 2"
				fill="#FFFFFF"
				@click="onBackgroundClick($event)"
			/>
			<g pointer-events="none">
				<path :d="gridMinorPath" fill="none" stroke="#F1F5F9" stroke-width="1" vector-effect="non-scaling-stroke" />
				<path :d="gridMajorPath" fill="none" stroke="#E2E8F0" stroke-width="1" vector-effect="non-scaling-stroke" />
			</g>
			<rect
				data-frame="FRAME"
				:x="frameBox.x"
				:y="frameBox.y"
				:width="frameBox.w"
				:height="frameBox.h"
				:fill="frameFill"
				:stroke="frameSelected ? C.select : C.stroke"
				:stroke-width="frameSelected ? 2.5 : 1"
				:class="{ hl: frameSelected }"
				style="cursor: pointer"
				@click="onFrameClick($event)"
			/>
			<rect
				:x="frameInner.x"
				:y="frameInner.y"
				:width="frameInner.w"
				:height="frameInner.h"
				fill="none"
				:stroke="frameSelected ? C.select : C.stroke"
				:stroke-width="frameSelected ? 1.5 : 1"
				vector-effect="non-scaling-stroke"
				pointer-events="none"
			/>

			<g v-for="v in cells" :key="v.cell.path">
				<rect
					:data-path="v.cell.path"
					:x="v.box.x"
					:y="v.box.y"
					:width="v.box.w"
					:height="v.box.h"
					:fill="v.cell.node.type === 'sash' ? sashFill : C.glass"
					:stroke="v.stroke"
					:stroke-width="v.strokeWidth"
					:class="{ hl: v.stroke !== C.stroke }"
					style="cursor: pointer"
					@click="onCellClick(v.cell, $event)"
				/>
				<rect
					v-if="v.cell.node.type === 'sash'"
					:data-glass="v.cell.path"
					:x="v.glass.x"
					:y="v.glass.y"
					:width="v.glass.w"
					:height="v.glass.h"
					:fill="C.glass"
					:stroke="v.glassSelected ? C.select : C.stroke"
					:stroke-width="v.glassSelected ? 2.5 : 1"
					:class="{ hl: v.glassSelected }"
					style="cursor: pointer"
					@click.stop="onGlassClick(v.cell, $event)"
				/>
				<!-- Glazing Bead Inner Outline -->
				<rect
					v-if="v.hasBead"
					data-bead="true"
					:x="v.beadBox.x"
					:y="v.beadBox.y"
					:width="v.beadBox.w"
					:height="v.beadBox.h"
					fill="none"
					stroke="#94A3B8"
					stroke-width="0.9"
					stroke-dasharray="4 3"
					vector-effect="non-scaling-stroke"
					pointer-events="none"
				/>
				<!-- Sash Corner Cut Lines (45° miter or 90° butt) -->
				<line
					v-for="(ln, ci) in v.corners"
					:key="`sc${ci}`"
					data-corner-cut="sash"
					:data-cut-angle="v.cutAngle"
					:x1="ln.x1"
					:y1="ln.y1"
					:x2="ln.x2"
					:y2="ln.y2"
					:stroke="C.stroke"
					stroke-width="1.5"
					stroke-linecap="square"
					vector-effect="non-scaling-stroke"
					pointer-events="none"
				/>
				<polyline
					v-for="(pts, i) in v.lines"
					:key="i"
					:points="pts"
					fill="none"
					:stroke="C.dim"
					stroke-dasharray="6 4"
					pointer-events="none"
				/>
				<line
					v-for="(y, i) in louverYs(v)"
					:key="`l${i}`"
					:x1="v.box.x"
					:x2="v.box.x + v.box.w"
					:y1="y"
					:y2="y"
					:stroke="C.stroke"
					pointer-events="none"
				/>
				<!-- Exhaust Fan Cutout Graphic -->
				<g
					v-if="v.cell.node.fan"
					pointer-events="none"
					:transform="`translate(${v.glass.x + v.glass.w / 2}, ${v.glass.y + Math.min(v.glass.h * 0.28, 54)})`"
				>
					<circle cx="0" cy="0" :r="Math.min(28, v.glass.w * 0.25)" fill="#FFFFFF" fill-opacity="0.82" :stroke="C.dim" stroke-width="1.4" />
					<circle cx="0" cy="0" :r="Math.min(22, v.glass.w * 0.2)" fill="none" :stroke="C.stroke" stroke-dasharray="3 2" />
					<circle cx="0" cy="0" r="4" :fill="C.dim" />
					<line x1="-14" y1="0" x2="14" y2="0" :stroke="C.dim" stroke-width="1.2" />
					<line x1="0" y1="-14" x2="0" y2="14" :stroke="C.dim" stroke-width="1.2" />
				</g>
				<!-- Casement Handle Graphic -->
				<rect
					v-if="v.handle"
					data-handle="true"
					:x="v.handle.x"
					:y="v.handle.y"
					:width="v.handle.w"
					:height="v.handle.h"
					rx="2"
					fill="#1E293B"
					pointer-events="none"
				/>
				<g v-if="v.cell.node.type === 'fixed'" pointer-events="none" :stroke="C.stroke">
					<line :x1="v.box.x + v.box.w / 2 - 8" :x2="v.box.x + v.box.w / 2 + 8" :y1="v.box.y + v.box.h / 2" :y2="v.box.y + v.box.h / 2" />
					<line :x1="v.box.x + v.box.w / 2" :x2="v.box.x + v.box.w / 2" :y1="v.box.y + v.box.h / 2 - 8" :y2="v.box.y + v.box.h / 2 + 8" />
				</g>
				<!-- Top-left Panel Tag Badge (S1 / S2 / L1) -->
				<g
					v-if="v.panelId"
					:data-panel-badge="v.cell.path"
					style="cursor: pointer"
					@click.stop="onCellClick(v.cell, $event)"
				>
					<rect
						:x="v.glass.x + 8"
						:y="v.glass.y + 8"
						width="26"
						height="18"
						rx="3"
						:fill="v.selected ? C.select : '#FFFFFF'"
						:stroke="v.selected ? C.select : C.stroke"
						:class="{ 'hl-badge': v.selected }"
					/>
					<text
						:x="v.glass.x + 21"
						:y="v.glass.y + 21"
						text-anchor="middle"
						font-size="11"
						font-weight="700"
						:fill="v.selected ? '#FFFFFF' : C.dim"
						:class="{ 'hl-badge-text': v.selected }"
					>{{ v.panelId }}</text>
				</g>
				<g v-if="v.cell.node.type === 'sash' && v.cell.node.opening" pointer-events="none">
					<rect
						:x="v.glass.x + v.glass.w / 2 - 20"
						:y="v.glass.y + v.glass.h / 2 + 26"
						width="40"
						height="20"
						rx="3"
						fill="#FFFFFF"
						:stroke="C.dim"
					/>
					<text
						:x="v.glass.x + v.glass.w / 2"
						:y="v.glass.y + v.glass.h / 2 + 40"
						text-anchor="middle"
						font-size="11"
						font-weight="600"
						:fill="C.dim"
					>{{ v.cell.node.opening === 'out' ? 'OUT' : 'IN' }}</text>
				</g>
				<!-- Circled Pane / Glass Number (Click to select Glass directly) -->
				<g
					:data-glass-badge="v.cell.path"
					style="cursor: pointer"
					@click.stop="onGlassClick(v.cell, $event)"
				>
					<circle
						:cx="v.glass.x + v.glass.w / 2"
						:cy="v.glass.y + v.glass.h / 2 - 14"
						r="11"
						:fill="v.glassSelected ? C.select : '#FFFFFF'"
						fill-opacity="0.95"
						:stroke="v.glassSelected ? C.select : C.dim"
						stroke-width="1.2"
						:class="{ 'hl-badge': v.glassSelected }"
					/>
					<text
						:x="v.glass.x + v.glass.w / 2"
						:y="v.glass.y + v.glass.h / 2 - 10"
						text-anchor="middle"
						font-size="12"
						font-weight="600"
						:fill="v.glassSelected ? '#FFFFFF' : C.dim"
						:class="{ 'hl-badge-text': v.glassSelected }"
					>{{ v.glassNo }}</text>
				</g>
			</g>

			<!-- Mitres sit above the glass fill so the joint stays a true 45° line. -->
			<g pointer-events="none" :stroke="frameSelected ? C.select : C.stroke" stroke-width="1.5" stroke-linecap="square">
				<line
					v-for="(ln, ci) in frameCorners"
					:key="`fc${ci}`"
					data-corner-cut="frame"
					:data-cut-angle="frameCutAngle"
					:x1="ln.x1"
					:y1="ln.y1"
					:x2="ln.x2"
					:y2="ln.y2"
					vector-effect="non-scaling-stroke"
				/>
			</g>

			<g v-for="b in bars" :key="b.bar.id">
				<rect
					:data-bar="b.bar.id"
					:x="b.rect.x"
					:y="b.rect.y"
					:width="b.rect.w"
					:height="b.rect.h"
					:fill="frameFill"
					:stroke="b.selected ? C.select : C.stroke"
					:stroke-width="b.selected ? 2.5 : 1"
					:class="{ hl: b.selected }"
					:style="{ cursor: b.bar.dir === 'v' ? 'ew-resize' : 'ns-resize', touchAction: 'none' }"
					@pointerdown="onPointerDown($event, b.bar)"
					@pointermove="onPointerMove"
					@pointerup="endDrag"
					@pointercancel="endDrag"
					@lostpointercapture="endDrag"
					@click="onBarClick(b.bar, $event)"
				/>
				<g
					:data-bar-badge="b.bar.id"
					style="cursor: pointer"
					@click="onBarClick(b.bar, $event)"
				>
					<rect
						:x="b.bar.dir === 'v' ? px(b.bar.x) - 13 : frameBox.x - 32"
						:y="b.bar.dir === 'v' ? frameBox.y - 22 : py(b.bar.y) - 9"
						width="26"
						height="17"
						rx="3"
						:fill="b.selected ? C.select : '#FFFFFF'"
						:stroke="b.selected ? C.select : C.stroke"
						:class="{ 'hl-badge': b.selected }"
					/>
					<text
						:x="b.bar.dir === 'v' ? px(b.bar.x) : frameBox.x - 19"
						:y="b.bar.dir === 'v' ? frameBox.y - 10 : py(b.bar.y) + 4"
						text-anchor="middle"
						font-size="11"
						font-weight="600"
						:fill="b.selected ? '#FFFFFF' : C.dim"
						:class="{ 'hl-badge-text': b.selected }"
					>{{ b.bar.id }}</text>
				</g>
			</g>

			<!-- Active Selection / Issue Outlines, Red Hinge Side Indicator Lines & Selected Dimension Callouts -->
			<g pointer-events="none">
				<template v-for="v in cells" :key="`ov-${v.cell.path}`">
					<rect
						v-if="v.selected || v.issue"
						data-highlight="true"
						:x="v.box.x"
						:y="v.box.y"
						:width="v.box.w"
						:height="v.box.h"
						fill="none"
						:stroke="v.stroke"
						:stroke-width="v.strokeWidth"
					/>
					<rect
						v-if="v.glassSelected"
						data-highlight="true"
						:x="v.glass.x"
						:y="v.glass.y"
						:width="v.glass.w"
						:height="v.glass.h"
						fill="none"
						:stroke="C.select"
						stroke-width="2.5"
					/>
					<line
						v-if="v.hingeLine"
						data-hinge-line="true"
						:x1="v.hingeLine.x1"
						:y1="v.hingeLine.y1"
						:x2="v.hingeLine.x2"
						:y2="v.hingeLine.y2"
						:stroke="C.cut"
						stroke-width="2.5"
						stroke-linecap="round"
					/>
					<!-- Selected Cell / Sash / Glass Specific Dimensions Overlay -->
					<g
						v-if="v.selected || v.glassSelected"
						data-highlight="true"
						:data-selected-dims="v.cell.path"
					>
						<!-- Top Glass Width Callout Pill -->
						<g :transform="`translate(${v.glass.x + v.glass.w / 2}, ${v.glass.y + 15})`">
							<rect x="-46" y="-8" width="92" height="16" rx="3" fill="#FFFFFF" fill-opacity="0.92" :stroke="C.select" stroke-width="1" />
							<text x="0" y="3.5" text-anchor="middle" font-size="9.5" font-weight="600" :fill="C.select">
								Glass W: {{ fmt(v.glassW) }}
							</text>
						</g>
						<!-- Side Glass Height Callout Pill -->
						<g :transform="`translate(${v.glass.x + v.glass.w - 14}, ${v.glass.y + v.glass.h / 2}) rotate(-90)`">
							<rect x="-46" y="-8" width="92" height="16" rx="3" fill="#FFFFFF" fill-opacity="0.92" :stroke="C.select" stroke-width="1" />
							<text x="0" y="3.5" text-anchor="middle" font-size="9.5" font-weight="600" :fill="C.select">
								Glass H: {{ fmt(v.glassH) }}
							</text>
						</g>
						<!-- Summary Card inside Selected Pane -->
						<g
							v-if="v.selected && v.cell.node.type === 'sash' && v.sashW !== null && v.sashH !== null"
							:transform="`translate(${v.glass.x + v.glass.w / 2}, ${v.glass.y + v.glass.h - 28})`"
						>
							<rect x="-78" y="-17" width="156" height="34" rx="4" fill="#FFFFFF" fill-opacity="0.95" :stroke="C.select" stroke-width="1.2" />
							<text x="0" y="-4" text-anchor="middle" font-size="9.5" font-weight="700" :fill="C.select">
								Sash: {{ fmt(v.sashW) }} × {{ fmt(v.sashH) }} mm
							</text>
							<text x="0" y="10" text-anchor="middle" font-size="9.5" font-weight="600" :fill="C.dim">
								Glass: {{ fmt(v.glassW) }} × {{ fmt(v.glassH) }} mm
							</text>
						</g>
						<g
							v-else
							:transform="`translate(${v.glass.x + v.glass.w / 2}, ${v.glass.y + v.glass.h - 20})`"
						>
							<rect x="-76" y="-10" width="152" height="20" rx="4" fill="#FFFFFF" fill-opacity="0.95" :stroke="C.select" stroke-width="1.2" />
							<text x="0" y="3.5" text-anchor="middle" font-size="9.5" font-weight="700" :fill="C.select">
								Glass: {{ fmt(v.glassW) }} × {{ fmt(v.glassH) }} mm
							</text>
						</g>
					</g>
				</template>

				<!-- Selected Outer Frame Outline & Specific Dimensions Overlay -->
				<g
					v-if="frameSelected"
					data-highlight="true"
					data-frame-dims="FRAME"
				>
					<rect
						:x="frameBox.x"
						:y="frameBox.y"
						:width="frameBox.w"
						:height="frameBox.h"
						fill="none"
						:stroke="C.select"
						stroke-width="2.5"
					/>
					<rect
						:x="frameInner.x"
						:y="frameInner.y"
						:width="frameInner.w"
						:height="frameInner.h"
						fill="none"
						:stroke="C.select"
						stroke-width="2"
					/>
					<g :transform="`translate(${frameBox.x + frameBox.w / 2}, ${frameBox.y + 14})`">
						<rect x="-92" y="-10" width="184" height="20" rx="4" fill="#FFFFFF" fill-opacity="0.96" :stroke="C.select" stroke-width="1.2" />
						<text x="0" y="3.5" text-anchor="middle" font-size="9.5" font-weight="700" :fill="C.select">
							Outer Frame: {{ fmt(design.width) }} × {{ fmt(design.height) }} mm
						</text>
					</g>
				</g>

				<!-- Selected Mullion / Transom Outline & Specific Dimensions Overlay -->
				<template v-for="b in bars" :key="`bov-${b.bar.id}`">
					<g
						v-if="b.selected"
						data-highlight="true"
						:data-bar-dims="b.bar.id"
					>
						<rect
							:x="b.rect.x"
							:y="b.rect.y"
							:width="b.rect.w"
							:height="b.rect.h"
							fill="none"
							:stroke="C.select"
							stroke-width="2.5"
						/>
						<g :transform="`translate(${b.rect.x + b.rect.w / 2}, ${b.rect.y + b.rect.h / 2})`">
							<rect x="-78" y="-17" width="156" height="34" rx="4" fill="#FFFFFF" fill-opacity="0.96" :stroke="C.select" stroke-width="1.2" />
							<text x="0" y="-4" text-anchor="middle" font-size="9.5" font-weight="700" :fill="C.select">
								{{ b.bar.id }}: {{ fmt(b.cutLength) }} × {{ fmt(b.faceWidth) }} mm
							</text>
							<text x="0" y="10" text-anchor="middle" font-size="9.5" font-weight="600" :fill="C.dim">
								Pos: {{ fmt(b.pos) }} mm · Span: {{ fmt(b.spanLength) }} mm
							</text>
						</g>
					</g>
				</template>
			</g>

		<g
			v-for="c in cuts"
			:key="c.axis"
			:data-cut="c.axis"
			:opacity="c.active ? 1 : 0.35"
			pointer-events="none"
		>
			<line :x1="c.x1" :x2="c.x2" :y1="c.y1" :y2="c.y2" :stroke="C.cut" :stroke-width="c.active ? 2 : 1" stroke-dasharray="12 4 3 4" />
			<g v-for="([bx, by], i) in c.badges" :key="i">
				<circle :cx="bx" :cy="by" r="9" fill="#FFFFFF" :stroke="C.cut" />
				<text :x="bx" :y="by + 4" text-anchor="middle" font-size="12" font-weight="700" :fill="C.cut">{{ c.letter }}</text>
			</g>
		</g>

		<text
			v-if="ghh"
			:x="frameBox.x + frameBox.w"
			:y="frameBox.y - 8"
			text-anchor="end"
			font-size="12"
			font-weight="600"
			:fill="C.dim"
		>GHH = {{ fmt(ghh) }}</text>
		<text :x="viewW / 2" :y="viewH - 8" text-anchor="middle" font-size="12" :fill="C.dim">
			{{ view === 'inside' ? 'View from inside' : 'View from outside' }}
		</text>

		<g :stroke="C.dim" :fill="C.dim" font-size="12">
			<g v-for="(d, i) in cols" :key="`c${i}`">
				<line :x1="px(d.from)" :x2="px(d.to)" :y1="frameBox.y + frameBox.h + 20" :y2="frameBox.y + frameBox.h + 20" />
				<line :x1="px(d.from)" :x2="px(d.from)" :y1="frameBox.y + frameBox.h + 15" :y2="frameBox.y + frameBox.h + 25" />
				<line :x1="px(d.to)" :x2="px(d.to)" :y1="frameBox.y + frameBox.h + 15" :y2="frameBox.y + frameBox.h + 25" />
				<text :x="(px(d.from) + px(d.to)) / 2" :y="frameBox.y + frameBox.h + 16" text-anchor="middle" stroke="none">{{ d.label }}</text>
			</g>
			<line :x1="frameBox.x" :x2="frameBox.x + frameBox.w" :y1="frameBox.y + frameBox.h + 44" :y2="frameBox.y + frameBox.h + 44" />
			<line :x1="frameBox.x" :x2="frameBox.x" :y1="frameBox.y + frameBox.h + 39" :y2="frameBox.y + frameBox.h + 49" />
			<line :x1="frameBox.x + frameBox.w" :x2="frameBox.x + frameBox.w" :y1="frameBox.y + frameBox.h + 39" :y2="frameBox.y + frameBox.h + 49" />
			<text :x="frameBox.x + frameBox.w / 2" :y="frameBox.y + frameBox.h + 40" text-anchor="middle" font-weight="600" stroke="none">{{ fmt(design.width) }}</text>

			<g v-for="(d, i) in rows" :key="`r${i}`">
				<line :x1="frameBox.x - 20" :x2="frameBox.x - 20" :y1="py(d.from)" :y2="py(d.to)" />
				<line :x1="frameBox.x - 25" :x2="frameBox.x - 15" :y1="py(d.from)" :y2="py(d.from)" />
				<line :x1="frameBox.x - 25" :x2="frameBox.x - 15" :y1="py(d.to)" :y2="py(d.to)" />
				<text :transform="`translate(${frameBox.x - 24} ${(py(d.from) + py(d.to)) / 2}) rotate(-90)`" text-anchor="middle" stroke="none">{{ d.label }}</text>
			</g>
			<line :x1="frameBox.x - 44" :x2="frameBox.x - 44" :y1="frameBox.y" :y2="frameBox.y + frameBox.h" />
			<line :x1="frameBox.x - 49" :x2="frameBox.x - 39" :y1="frameBox.y" :y2="frameBox.y" />
			<line :x1="frameBox.x - 49" :x2="frameBox.x - 39" :y1="frameBox.y + frameBox.h" :y2="frameBox.y + frameBox.h" />
			<text :transform="`translate(${frameBox.x - 48} ${frameBox.y + frameBox.h / 2}) rotate(-90)`" text-anchor="middle" font-weight="600" stroke="none">{{ fmt(design.height) }}</text>
		</g>
		</svg>

		<!-- Workspace Zoom & Pan Controls -->
		<div
			class="pointer-events-auto absolute right-3 bottom-3 flex items-center gap-1 rounded-lg border border-gray-200 bg-white/95 px-1.5 py-1 shadow-xs backdrop-blur-xs"
			role="toolbar"
			aria-label="Workspace controls"
		>
			<span class="hidden px-1.5 text-[11px] text-gray-500 sm:inline">Shift + drag to pan</span>
			<div class="hidden h-3.5 w-px bg-gray-200 sm:block" />
			<button
				type="button"
				aria-label="Zoom out"
				title="Zoom out (-)"
				:disabled="zoom <= MIN_ZOOM"
				class="flex h-6 w-6 items-center justify-center rounded text-sm font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-40"
				@click="zoomOut"
			>
				−
			</button>
			<button
				type="button"
				aria-label="Reset zoom"
				title="Reset view (0)"
				class="min-w-12 rounded px-1.5 py-0.5 text-center font-mono text-xs font-medium text-gray-700 hover:bg-gray-100"
				@click="resetView"
			>
				{{ Math.round(zoom * 100) }}%
			</button>
			<button
				type="button"
				aria-label="Zoom in"
				title="Zoom in (+)"
				:disabled="zoom >= MAX_ZOOM"
				class="flex h-6 w-6 items-center justify-center rounded text-sm font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-40"
				@click="zoomIn"
			>
				+
			</button>
		</div>
	</div>
</template>
