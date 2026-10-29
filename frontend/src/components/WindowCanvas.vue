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
const C = {
	frame: '#8A8F98',
	sash: '#9BA0A8',
	glass: '#DCEBF7',
	stroke: '#5B6470',
	select: '#2563EB',
	issue: '#D97706',
	dim: '#404040',
}

const props = withDefaults(
	defineProps<{
		design: Design
		selectedPath: string | null
		issuePaths: string[]
		view: 'inside' | 'outside'
		viewW?: number
		viewH?: number
	}>(),
	{ viewW: 640, viewH: 760 },
)
const emit = defineEmits<{
	select: [path: string]
	'move-split': [payload: { splitPath: string; index: number; pos: number }]
	'drag-start': []
	'drag-end': []
}>()

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

interface CellView {
	cell: CellGeom
	box: Box
	glass: Box
	panelId: string
	glassNo: number
	stroke: string
	strokeWidth: number
	lines: string[]
}

type HingeSide = 'left' | 'right' | 'top'

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
			stroke: selected ? C.select : issue ? C.issue : C.stroke,
			strokeWidth: selected ? 3 : issue ? 2 : 1,
			lines: side ? openingLines(glass, side) : [],
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
		<rect
			:x="frameBox.x"
			:y="frameBox.y"
			:width="frameBox.w"
			:height="frameBox.h"
			:fill="C.frame"
			:stroke="C.stroke"
		/>

		<g v-for="v in cells" :key="v.cell.path">
			<rect
				:data-path="v.cell.path"
				:x="v.box.x"
				:y="v.box.y"
				:width="v.box.w"
				:height="v.box.h"
				:fill="v.cell.node.type === 'sash' ? C.sash : C.glass"
				:stroke="v.stroke"
				:stroke-width="v.strokeWidth"
				:class="{ hl: v.stroke !== C.stroke }"
				style="cursor: pointer"
				@click="emit('select', v.cell.path)"
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
			<g v-if="v.cell.node.type === 'fixed'" pointer-events="none" :stroke="C.stroke">
				<line :x1="v.box.x + v.box.w / 2 - 8" :x2="v.box.x + v.box.w / 2 + 8" :y1="v.box.y + v.box.h / 2" :y2="v.box.y + v.box.h / 2" />
				<line :x1="v.box.x + v.box.w / 2" :x2="v.box.x + v.box.w / 2" :y1="v.box.y + v.box.h / 2 - 8" :y2="v.box.y + v.box.h / 2 + 8" />
			</g>
			<text
				v-if="v.panelId"
				:x="v.glass.x + v.glass.w / 2"
				:y="v.glass.y + v.glass.h / 2 - 8"
				text-anchor="middle"
				font-size="16"
				font-weight="600"
				:fill="C.dim"
				pointer-events="none"
			>{{ v.panelId }}</text>
			<g v-if="v.cell.node.type === 'sash' && v.cell.node.opening" pointer-events="none">
				<rect
					:x="v.glass.x + v.glass.w / 2 - 18"
					:y="v.glass.y + v.glass.h / 2 + 26"
					width="36"
					height="20"
					fill="#FFFFFF"
					:stroke="C.dim"
				/>
				<text
					:x="v.glass.x + v.glass.w / 2"
					:y="v.glass.y + v.glass.h / 2 + 41"
					text-anchor="middle"
					font-size="12"
					:fill="C.dim"
				>{{ v.cell.node.opening === 'out' ? 'OUT' : 'IN' }}</text>
			</g>
			<text
				:x="v.glass.x + v.glass.w / 2"
				:y="v.glass.y + v.glass.h / 2 + 14"
				text-anchor="middle"
				font-size="14"
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
				:fill="C.frame"
				:stroke="C.stroke"
				:style="{ cursor: bar.dir === 'v' ? 'ew-resize' : 'ns-resize', touchAction: 'none' }"
				@pointerdown="onPointerDown($event, bar)"
				@pointermove="onPointerMove"
				@pointerup="endDrag"
				@pointercancel="endDrag"
				@lostpointercapture="endDrag"
			/>
			<text
				:x="bar.dir === 'v' ? px(bar.x) : frameBox.x - 6"
				:y="bar.dir === 'v' ? frameBox.y - 8 : py(bar.y) + 4"
				:text-anchor="bar.dir === 'v' ? 'middle' : 'end'"
				font-size="12"
				:fill="C.dim"
				pointer-events="none"
			>{{ bar.id }}</text>
		</g>

		<text
			v-if="ghh"
			:x="frameBox.x + frameBox.w"
			:y="frameBox.y - 8"
			text-anchor="end"
			font-size="12"
			:fill="C.dim"
		>GHH = {{ fmt(ghh) }}</text>
		<text :x="viewW / 2" :y="viewH - 8" text-anchor="middle" font-size="12" :fill="C.dim">
			{{ view === 'inside' ? 'View from inside' : 'View from outside' }}
		</text>

		<g :stroke="C.dim" :fill="C.dim" font-size="12">
			<g v-for="(d, i) in cols" :key="`c${i}`">
				<line :x1="px(d.from)" :x2="px(d.to)" :y1="frameBox.y + frameBox.h + 20" :y2="frameBox.y + frameBox.h + 20" />
				<text :x="(px(d.from) + px(d.to)) / 2" :y="frameBox.y + frameBox.h + 16" text-anchor="middle" stroke="none">{{ d.label }}</text>
			</g>
			<line :x1="frameBox.x" :x2="frameBox.x + frameBox.w" :y1="frameBox.y + frameBox.h + 44" :y2="frameBox.y + frameBox.h + 44" />
			<text :x="frameBox.x + frameBox.w / 2" :y="frameBox.y + frameBox.h + 40" text-anchor="middle" stroke="none">{{ fmt(design.width) }}</text>

			<g v-for="(d, i) in rows" :key="`r${i}`">
				<line :x1="frameBox.x - 20" :x2="frameBox.x - 20" :y1="py(d.from)" :y2="py(d.to)" />
				<text :transform="`translate(${frameBox.x - 24} ${(py(d.from) + py(d.to)) / 2}) rotate(-90)`" text-anchor="middle" stroke="none">{{ d.label }}</text>
			</g>
			<line :x1="frameBox.x - 44" :x2="frameBox.x - 44" :y1="frameBox.y" :y2="frameBox.y + frameBox.h" />
			<text :transform="`translate(${frameBox.x - 48} ${frameBox.y + frameBox.h / 2}) rotate(-90)`" text-anchor="middle" stroke="none">{{ fmt(design.height) }}</text>
		</g>
	</svg>
</template>
