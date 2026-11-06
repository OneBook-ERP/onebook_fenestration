<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { layoutGeom } from '@/design/geometry'
import { getNode } from '@/design/tree'
import type { BarGeom, CellGeom, Design, SplitNode } from '@/design/types'

const FRAME_FACE = 42
const BAR_FACE = 40
const SASH_FACE = 50
const PAD = 60
const FONT = 'Inter, sans-serif'
const DEFAULT_FINISH = '#8A8F98'
const C = {
	glass: '#DCEBF7',
	stroke: '#5B6470',
	select: '#2563EB',
	issue: '#D97706',
	dim: '#404040',
	cut: '#DC2626',
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
	}>(),
	{ viewW: 640, viewH: 760, finishColor: DEFAULT_FINISH, section: null },
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
	const l = c.x === 0 ? FRAME_FACE : BAR_FACE / 2
	const r = c.x + c.w === width ? FRAME_FACE : BAR_FACE / 2
	const b = c.y === 0 ? FRAME_FACE : BAR_FACE / 2
	const t = c.y + c.h === height ? FRAME_FACE : BAR_FACE / 2
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
	stroke: string
	strokeWidth: number
	lines: string[]
	side: HingeSide | null
	handle: HandlePos | null
}

function hingeSide(c: CellGeom): HingeSide | null {
	const node = c.node
	if (node.type !== 'sash' || !node.hinge) return null
	if (node.hinge === 'top') return 'top'
	const h = node.hinge === 'right' ? 'right' : 'left'
	if (props.view === 'inside') return h
	return h === 'left' ? 'right' : 'left'
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

function computeHandlePos(cell: CellGeom, box: Box, glass: Box, side: HingeSide | null): HandlePos | null {
	if (cell.node.type !== 'sash') return null
	const hSide = side || 'left'
	if (hSide === 'top') {
		return {
			x: box.x + box.w / 2 - 12,
			y: glass.y + glass.h + Math.max(2, (box.y + box.h - (glass.y + glass.h)) / 2 - 2.5),
			w: 24,
			h: 5,
		}
	}
	const ghhMm = cell.node.ghh || cell.h * 0.5
	const clampedGhh = Math.max(cell.y + 120, Math.min(cell.y + cell.h - 120, ghhMm))
	const handleCenterY = py(clampedGhh)
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

const cells = computed<CellView[]>(() => {
	// Fixed panes show only their glass number; F<n> would clash with the frame id.
	const counts: Record<string, number> = { S: 0, L: 0 }
	return geom.value.cells.map((cell, i) => {
		const prefix = cell.node.type === 'sash' ? 'S' : cell.node.type === 'louver' ? 'L' : ''
		const box = cellBox(cell)
		const isSash = cell.node.type === 'sash'
		const selected = cell.path === props.selectedPath
		const issue = props.issuePaths.includes(cell.path)
		const side = hingeSide(cell)
		const glass = isSash ? inset(box, SASH_FACE) : box
		return {
			cell,
			box,
			glass,
			panelId: prefix ? `${prefix}${++counts[prefix]}` : '',
			glassNo: i + 1,
			selected,
			stroke: selected ? C.select : issue ? C.issue : C.stroke,
			strokeWidth: selected ? 3 : issue ? 2 : 1,
			lines: side ? openingLines(glass, side) : [],
			side,
			handle: computeHandlePos(cell, box, glass, side),
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
	if (bar.dir === 'v') {
		return { x: px(bar.x - BAR_FACE / 2), y: py(bar.y + bar.length), w: BAR_FACE * scale.value, h: bar.length * scale.value }
	}
	return { x: px(bar.x), y: py(bar.y + BAR_FACE / 2), w: bar.length * scale.value, h: BAR_FACE * scale.value }
}

const frameBox = computed<Box>(() => ({
	x: px(0),
	y: py(props.design.height),
	w: props.design.width * scale.value,
	h: props.design.height * scale.value,
}))

const gridPath = computed(() => {
	const step = 24
	const parts: string[] = []
	for (let x = step; x < props.viewW; x += step) {
		parts.push(`M ${x} 0 L ${x} ${props.viewH}`)
	}
	for (let y = step; y < props.viewH; y += step) {
		parts.push(`M 0 ${y} L ${props.viewW} ${y}`)
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
	const face = (FRAME_FACE / 2) * scale.value
	const ends = 10
	const x = px(s.v)
	const y = py(s.h)
	return [
		{ axis: 'v' as const, letter: 'A', x1: x, x2: x, y1: f.y - ends, y2: f.y + f.h + ends, badges: [[x, f.y + face], [x, f.y + f.h - face]] },
		{ axis: 'h' as const, letter: 'B', x1: f.x - ends, x2: f.x + f.w + ends, y1: y, y2: y, badges: [[f.x + face, y], [f.x + f.w - face, y]] },
	].map((c) => ({ ...c, active: c.axis === s.axis }))
})

function onCellClick(c: CellGeom) {
	emit('select', c.path)
	const s = props.section
	if (s) emit('update:cut', { axis: s.axis, at: s.axis === 'h' ? c.y + c.h / 2 : c.x + c.w / 2 })
}

const ariaLabel = computed(
	() => `Window ${fmt(props.design.width)} by ${fmt(props.design.height)} mm, ${geom.value.cells.length} panels`,
)

interface Drag {
	bar: BarGeom
	start: number
	original: number
	el: Element
	pointerId: number
}
let drag: Drag | null = null

function onPointerDown(e: PointerEvent, bar: BarGeom) {
	if (e.button !== 0 && e.button !== undefined) return
	e.preventDefault()
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
	const r = svg.value?.getBoundingClientRect()
	// preserveAspectRatio "meet" scales both axes by the smaller ratio.
	const meet = r && r.width && r.height ? Math.min(r.width / props.viewW, r.height / props.viewH) : 0
	const k = meet ? 1 / meet : 1
	const cur = vertical ? e.clientX : e.clientY
	const delta = ((cur - drag.start) * k) / scale.value
	const pos = drag.bar.dir === 'v' ? drag.original + delta : drag.original - delta
	emit('move-split', { splitPath: drag.bar.splitPath, index: drag.bar.index, pos })
}

function endDrag() {
	if (!drag) return
	const { el, pointerId } = drag
	drag = null
	window.removeEventListener('pointerup', endDrag)
	window.removeEventListener('pointercancel', endDrag)
	if (el.releasePointerCapture && el.hasPointerCapture?.(pointerId)) el.releasePointerCapture(pointerId)
	emit('drag-end')
}
onUnmounted(endDrag)

function getSvgMarkup(): string {
	if (!svg.value) return ''
	const clone = svg.value.cloneNode(true) as SVGSVGElement
	clone.querySelectorAll('[data-cut]').forEach((el) => el.remove())
	clone.setAttribute('width', String(props.viewW))
	clone.setAttribute('height', String(props.viewH))
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
defineExpose({ getSvgMarkup })
</script>

<template>
	<svg
		ref="svg"
		xmlns="http://www.w3.org/2000/svg"
		role="img"
		:aria-label="ariaLabel"
		:viewBox="`0 0 ${viewW} ${viewH}`"
		width="100%"
		height="100%"
		preserveAspectRatio="xMidYMid meet"
		:font-family="FONT"
	>
		<rect x="0" y="0" :width="viewW" :height="viewH" fill="#FFFFFF" />
		<g pointer-events="none">
			<path :d="gridPath" fill="none" stroke="#F1F5F9" stroke-width="1" />
		</g>
		<rect
			:x="frameBox.x"
			:y="frameBox.y"
			:width="frameBox.w"
			:height="frameBox.h"
			:fill="frameFill"
			:stroke="C.stroke"
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
				@click="onCellClick(v.cell)"
			/>
			<rect
				v-if="v.cell.node.type === 'sash'"
				:x="v.glass.x"
				:y="v.glass.y"
				:width="v.glass.w"
				:height="v.glass.h"
				:fill="C.glass"
				:stroke="C.stroke"
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
			<g v-if="v.panelId" pointer-events="none">
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
			<!-- Circled Pane Number -->
			<circle
				:cx="v.glass.x + v.glass.w / 2"
				:cy="v.glass.y + v.glass.h / 2 - 14"
				r="11"
				fill="#FFFFFF"
				fill-opacity="0.9"
				:stroke="C.dim"
				stroke-width="1.1"
				pointer-events="none"
			/>
			<text
				:x="v.glass.x + v.glass.w / 2"
				:y="v.glass.y + v.glass.h / 2 - 10"
				text-anchor="middle"
				font-size="12"
				font-weight="600"
				:fill="C.dim"
				pointer-events="none"
			>{{ v.glassNo }}</text>
		</g>

		<g v-for="bar in geom.bars" :key="bar.id">
			<rect
				:data-bar="bar.id"
				:x="barRect(bar).x"
				:y="barRect(bar).y"
				:width="barRect(bar).w"
				:height="barRect(bar).h"
				:fill="frameFill"
				:stroke="C.stroke"
				:style="{ cursor: bar.dir === 'v' ? 'ew-resize' : 'ns-resize', touchAction: 'none' }"
				@pointerdown="onPointerDown($event, bar)"
				@pointermove="onPointerMove"
				@pointerup="endDrag"
				@pointercancel="endDrag"
				@lostpointercapture="endDrag"
			/>
			<rect
				:x="bar.dir === 'v' ? px(bar.x) - 13 : frameBox.x - 32"
				:y="bar.dir === 'v' ? frameBox.y - 22 : py(bar.y) - 9"
				width="26"
				height="17"
				rx="3"
				fill="#FFFFFF"
				:stroke="C.stroke"
				pointer-events="none"
			/>
			<text
				:x="bar.dir === 'v' ? px(bar.x) : frameBox.x - 19"
				:y="bar.dir === 'v' ? frameBox.y - 10 : py(bar.y) + 4"
				text-anchor="middle"
				font-size="11"
				font-weight="600"
				:fill="C.dim"
				pointer-events="none"
			>{{ bar.id }}</text>
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
</template>
