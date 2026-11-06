<script setup lang="ts">
/**
 * Cross-section strip of the profiles and glass one cut line crosses (Logikal "Cross section Drawing").
 *
 * The strip is always drawn left to right along the cut: B–B runs from the frame's left edge, A–A from its
 * bottom edge (read rotated, bottom on the left). Depth runs down the page. Every outline's y=0 (the stored
 * outer face) sits on one reference line; this alignment is an assumption to be checked visually in Task 6.
 */
import { Button } from 'frappe-ui'
import { computed, onUnmounted, ref, watch } from 'vue'
import { crossSection, type CrossSection, type CutResponse, type CutAxis as Axis, type DimChain as Chain, type SectionDim, type SectionOutline as Outline, type SectionPiece } from '@/api'
import type { Design } from '@/design/types'
import { COMPUTE_DEBOUNCE_MS } from '@/stores/designer'

const props = defineProps<{ design: Design; seriesVersion: string; axis: Axis; at: number | null }>()
const emit = defineEmits<{ 'update:axis': [axis: Axis]; cut: [at: number] }>()

const AXES = [
	{ label: 'B–B horizontal', value: 'h' },
	{ label: 'A–A vertical', value: 'v' },
] as const

/** Drawing units: the strip is laid out in a 640-wide box and scaled to the container. */
const VIEW_W = 640
const PAD_X = 28
const LABEL_H = 48
/** Room for a dimension line with a label line above it and a second label line below it. */
const ROW_H = 24
const FONT = 9
/** Estimated label width per character, in font sizes (Inter digits are about 0.6 em). */
const CHAR_EM = 0.6
/** Clear space between neighbouring labels on one line: about a character, so values never read as one. */
const LABEL_GAP = 6
const TICK = 3
/** Display stand-ins, not series data: depth of a profile with no outline and of a glass band with no thickness. */
const BOX_DEPTH_MM = 60
const GLASS_DEPTH_MM = 24
const CHAINS: Chain[] = ['profiles', 'glass', 'cells', 'overall']
const C = { profile: '#111111', fill: '#F3F4F6', glass: '#22D3EE', glassFill: '#CFFAFE', dim: '#404040' }

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

/** Where the engine last cut, on which axis: moving `at` onto it changes nothing, so it is not refetched. */
let snapped: { axis: Axis; at: number } | null = null

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
	snapped = { axis: axis.value, at: res.result.at }
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
watch(() => props.design, loadLater, { deep: true })
onUnmounted(() => {
	clearTimeout(timer)
	seq += 1
})

function pick(a: Axis) {
	if (a === axis.value) return
	axis.value = a
	emit('update:axis', a)
}

const k = computed(() => (section.value?.length ? (VIEW_W - 2 * PAD_X) / section.value.length : 1))
const sx = (mm: number) => PAD_X + mm * k.value
const fmt = (n: number) => String(Math.round(n * 100) / 100)

interface DrawnPiece {
	piece: SectionPiece
	x: number
	w: number
	depth: number
	outline: Outline | null
	transform: string
}

const drawn = computed<DrawnPiece[]>(() =>
	(section.value?.pieces ?? []).map((piece) => {
		const x = sx(piece.start)
		const w = (piece.end - piece.start) * k.value
		const outline = piece.kind === 'profile' ? (outlines.value[piece.code] ?? null) : null
		if (!outline || !(outline.width > 0)) {
			const mm = piece.kind === 'glass' ? (piece.thickness > 0 ? piece.thickness : GLASS_DEPTH_MM) : BOX_DEPTH_MM
			return { piece, x, w, depth: mm * k.value, outline: null, transform: '' }
		}
		// Uniform scale: the outline's face width becomes the piece width.
		const s = w / outline.width
		const transform = piece.mirrored
			? `translate(${fmt(x + w)} ${LABEL_H}) scale(${-s} ${s})`
			: `translate(${fmt(x)} ${LABEL_H}) scale(${s} ${s})`
		return { piece, x, w, depth: outline.depth * s, outline, transform }
	}),
)

const stripDepth = computed(() => Math.max(BOX_DEPTH_MM * k.value, ...drawn.value.filter((d) => d.piece.kind === 'profile').map((d) => d.depth)))
/** ASSUMPTION: glass sits centred in the strip's depth; the cut data has no glass depth position. */
const glassY = (d: DrawnPiece) => LABEL_H + (stripDepth.value - d.depth) / 2

const missing = computed(() => {
	const codes = new Set(drawn.value.filter((d) => d.piece.kind === 'profile' && !d.outline).map((d) => d.piece.code))
	return [...codes].sort()
})

interface PlacedDim {
	dim: SectionDim
	x: number
	/** Label baseline; null when it fits on neither label line (the value is then only in the tooltip). */
	labelY: number | null
}

const rows = computed(() => {
	const dims = section.value?.dims ?? []
	const top = LABEL_H + stripDepth.value + 10
	return CHAINS.map((chain) => dims.filter((d) => d.chain === chain))
		.filter((list) => list.length)
		.map((list, i) => {
			const y = top + (i + 1) * ROW_H
			return { y, dims: placeLabels(list, y) }
		})
})

/**
 * Each label goes above its dimension line; when it would run into a label already there it drops to a second
 * line below, and when both are taken it is left out (its value stays in the dimension's tooltip).
 */
function placeLabels(dims: SectionDim[], y: number): PlacedDim[] {
	const lines = [y - 3, y + FONT + 2]
	const taken: [number, number][][] = lines.map(() => [])
	return dims.map((dim) => {
		const x = (sx(dim.start) + sx(dim.end)) / 2
		const half = (dim.label.length * FONT * CHAR_EM) / 2 + LABEL_GAP / 2
		const span: [number, number] = [x - half, x + half]
		const line = taken.findIndex((spans) => spans.every(([a, b]) => span[1] <= a || span[0] >= b))
		if (line < 0) return { dim, x, labelY: null }
		taken[line].push(span)
		return { dim, x, labelY: lines[line] }
	})
}

const viewH = computed(() => LABEL_H + stripDepth.value + 10 + rows.value.length * ROW_H + FONT + 6)
const title = computed(() => (axis.value === 'h' ? 'Section B–B, left to right' : 'Section A–A, bottom to top'))
const issues = computed(() => section.value?.issues ?? [])
</script>

<template>
	<section class="flex w-full min-w-0 flex-col gap-2 border-t border-gray-200 bg-white p-2" aria-label="Cross section">
		<div class="flex flex-wrap items-center gap-2">
			<div class="flex rounded-md border border-gray-200 p-0.5" role="group" aria-label="Cut">
				<Button
					v-for="a in AXES"
					:key="a.value"
					:label="a.label"
					:variant="axis === a.value ? 'subtle' : 'ghost'"
					:aria-pressed="axis === a.value"
					class="min-h-9"
					@click="pick(a.value)"
				/>
			</div>
			<span class="text-xs text-gray-600">{{ title }}</span>
		</div>
		<p v-if="error" role="alert" class="text-sm text-red-600">{{ error }}</p>
		<template v-else-if="section">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				role="img"
				:aria-label="`${title}, ${section.pieces.length} pieces`"
				:viewBox="`0 0 ${VIEW_W} ${fmt(viewH)}`"
				width="100%"
				class="block max-h-72"
				preserveAspectRatio="xMidYMin meet"
				font-family="Inter, sans-serif"
			>
				<rect x="0" y="0" :width="VIEW_W" :height="viewH" fill="#FFFFFF" />
				<line :x1="sx(0)" :x2="sx(section.length)" :y1="LABEL_H" :y2="LABEL_H" :stroke="C.dim" stroke-width="0.5" stroke-dasharray="4 3" />
				<template v-for="(d, i) in drawn" :key="i">
					<rect
						v-if="d.piece.kind === 'glass'"
						:data-piece="i"
						data-kind="glass"
						:x="d.x"
						:y="glassY(d)"
						:width="d.w"
						:height="d.depth"
						:fill="C.glassFill"
						:stroke="C.glass"
					/>
					<path
						v-else-if="d.outline"
						:data-piece="i"
						data-kind="profile"
						:d="d.outline.svg"
						:transform="d.transform"
						:fill="C.fill"
						:stroke="C.profile"
						stroke-width="1"
						vector-effect="non-scaling-stroke"
					/>
					<rect
						v-else
						:data-piece="i"
						data-kind="profile"
						:x="d.x"
						:y="LABEL_H"
						:width="d.w"
						:height="d.depth"
						:fill="C.fill"
						:stroke="C.profile"
						stroke-dasharray="3 2"
					/>
					<text
						v-if="d.piece.kind === 'glass'"
						:x="d.x + d.w / 2"
						:y="glassY(d) + d.depth / 2 + 3"
						text-anchor="middle"
						font-size="9"
						:fill="C.dim"
					>{{ d.piece.code }}</text>
					<text
						v-else
						:transform="`translate(${fmt(d.x + d.w / 2 + 3)} ${LABEL_H - 3}) rotate(-90)`"
						font-size="8"
						:fill="C.dim"
					>{{ d.piece.code }}</text>
				</template>
				<g :stroke="C.dim" stroke-width="0.75" :font-size="FONT" :fill="C.dim">
					<g v-for="row in rows" :key="row.y" :data-chain="row.dims[0].dim.chain">
						<g v-for="({ dim: dm, x, labelY }, j) in row.dims" :key="j">
							<title>{{ dm.label }} mm</title>
							<line :x1="sx(dm.start)" :x2="sx(dm.end)" :y1="row.y" :y2="row.y" />
							<line :x1="sx(dm.start)" :x2="sx(dm.start)" :y1="row.y - TICK - 1" :y2="row.y + TICK + 1" />
							<line :x1="sx(dm.end)" :x2="sx(dm.end)" :y1="row.y - TICK - 1" :y2="row.y + TICK + 1" />
							<line :x1="sx(dm.start) - TICK" :x2="sx(dm.start) + TICK" :y1="row.y + TICK" :y2="row.y - TICK" />
							<line :x1="sx(dm.end) - TICK" :x2="sx(dm.end) + TICK" :y1="row.y + TICK" :y2="row.y - TICK" />
							<text v-if="labelY !== null" :x="x" :y="labelY" text-anchor="middle" stroke="none">{{ dm.label }}</text>
						</g>
					</g>
				</g>
			</svg>
			<p v-if="missing.length" data-testid="missing-outlines" class="text-xs text-gray-600">
				No section outline for {{ missing.join(', ') }}; drawn as boxes.
			</p>
			<p v-for="(iss, i) in issues" :key="i" class="text-xs text-amber-700">{{ iss.message }}</p>
		</template>
		<p v-else class="text-sm text-gray-500">Cutting...</p>
	</section>
</template>
