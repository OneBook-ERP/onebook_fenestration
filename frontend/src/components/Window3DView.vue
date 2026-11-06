<template>
	<div
		class="relative flex h-full w-full flex-col overflow-hidden bg-gradient-to-b from-slate-50 to-slate-100 p-4 select-none"
		data-testid="window-3d-view"
	>
		<!-- Top 3D Control Bar -->
		<div class="z-10 mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white/95 px-4 py-2.5 shadow-xs backdrop-blur">
			<div class="flex items-center gap-2">
				<span class="text-xs font-semibold uppercase tracking-wider text-gray-500">Camera</span>
				<div class="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5">
					<button
						type="button"
						class="rounded-md px-2.5 py-1 text-xs font-semibold text-gray-700 hover:bg-white hover:text-gray-900"
						@click="setCamera(-28, 16, 1)"
					>
						Isometric
					</button>
					<button
						type="button"
						class="rounded-md px-2.5 py-1 text-xs font-semibold text-gray-700 hover:bg-white hover:text-gray-900"
						@click="setCamera(0, 0, 1)"
					>
						Front
					</button>
					<button
						type="button"
						class="rounded-md px-2.5 py-1 text-xs font-semibold text-gray-700 hover:bg-white hover:text-gray-900"
						@click="setCamera(152, 14, 1)"
					>
						Exterior
					</button>
				</div>
			</div>

			<div class="flex flex-wrap items-center gap-4 text-xs text-gray-600">
				<label class="flex items-center gap-2">
					<span class="font-medium">Swing sashes:</span>
					<input
						v-model.number="openAngle"
						type="range"
						min="0"
						max="45"
						step="1"
						class="h-1.5 w-28 cursor-pointer accent-gray-900"
					/>
					<span class="w-9 font-mono text-gray-800">{{ openAngle }}°</span>
				</label>
				<button
					type="button"
					class="rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50"
					@click="openAngle = openAngle > 0 ? 0 : 30"
				>
					{{ openAngle > 0 ? 'Close All' : 'Open All (30°)' }}
				</button>
			</div>
		</div>

		<!-- 3D Viewport Stage -->
		<div
			class="relative flex min-h-0 flex-1 cursor-grab items-center justify-center overflow-hidden rounded-xl border border-gray-200 bg-gradient-to-b from-white via-slate-50 to-slate-200/60 active:cursor-grabbing"
			@pointerdown="onPointerDown"
			@pointermove="onPointerMove"
			@pointerup="onPointerUp"
			@pointercancel="onPointerUp"
			@wheel.prevent="onWheel"
		>
			<div
				class=" stage-3d"
				:style="{
					transform: `perspective(1200px) scale(${zoom}) rotateX(${pitch}deg) rotateY(${yaw}deg)`,
				}"
			>
				<!-- Outer Frame 3D Box -->
				<div
					class="relative"
					:style="{
						width: `${wPx}px`,
						height: `${hPx}px`,
						transformStyle: 'preserve-3d',
					}"
				>
					<!-- Floor Shadow -->
					<div
						class="pointer-events-none absolute left-1/2 -bottom-10 -translate-x-1/2 rounded-full bg-slate-900/15 blur-md"
						:style="{
							width: `${wPx * 1.08}px`,
							height: '28px',
							transform: 'rotateX(90deg)',
						}"
					/>

					<!-- Outer Frame Front/Back & Extruded Depth Sides -->
					<!-- Top Rail -->
					<div class="abs-3d" :style="barBoxStyle(0, 0, wPx, frameT, depthPx, frameHex, outsideHex)" />
					<!-- Bottom Sill -->
					<div class="abs-3d" :style="barBoxStyle(0, hPx - frameT, wPx, frameT, depthPx, frameHex, outsideHex)" />
					<!-- Left Jamb -->
					<div class="abs-3d" :style="barBoxStyle(0, frameT, frameT, hPx - 2 * frameT, depthPx, frameHex, outsideHex)" />
					<!-- Right Jamb -->
					<div class="abs-3d" :style="barBoxStyle(wPx - frameT, frameT, frameT, hPx - 2 * frameT, depthPx, frameHex, outsideHex)" />

					<!-- Mullions and Transoms -->
					<div
						v-for="bar in bars3d"
						:key="bar.id"
						class="abs-3d"
						:style="barBoxStyle(bar.x, bar.y, bar.w, bar.h, depthPx, frameHex, outsideHex)"
					/>

					<!-- Cells (Sashes, Fixed Glass, Louvers) -->
					<div
						v-for="cell in cells3d"
						:key="cell.path"
						class="abs-3d cursor-pointer"
						:style="cellTransformStyle(cell)"
						@click.stop="emit('select', cell.path)"
					>
						<!-- Sash Perimeter Rails if Sash -->
						<template v-if="cell.type === 'sash'">
							<div :style="flatRailStyle(0, 0, cell.w, sashT, sashHex)" />
							<div :style="flatRailStyle(0, cell.h - sashT, cell.w, sashT, sashHex)" />
							<div :style="flatRailStyle(0, sashT, sashT, cell.h - 2 * sashT, sashHex)" />
							<div :style="flatRailStyle(cell.w - sashT, sashT, sashT, cell.h - 2 * sashT, sashHex)" />

							<!-- Casement Handle on Opposite Side of Hinge -->
							<div
								class="pointer-events-none absolute rounded-xs bg-slate-800 shadow-xs"
								:style="handleStyle(cell)"
							/>
						</template>

						<!-- Glass Pane -->
						<div
							class="absolute overflow-hidden border border-sky-300/60"
							:style="{
								left: `${cell.type === 'sash' ? sashT : 0}px`,
								top: `${cell.type === 'sash' ? sashT : 0}px`,
								width: `${Math.max(0, cell.w - (cell.type === 'sash' ? 2 * sashT : 0))}px`,
								height: `${Math.max(0, cell.h - (cell.type === 'sash' ? 2 * sashT : 0))}px`,
								background: 'linear-gradient(135deg, rgba(186,230,253,0.58) 0%, rgba(224,242,254,0.32) 48%, rgba(125,211,252,0.52) 100%)',
								boxShadow: cell.selected ? 'inset 0 0 0 2px #2563eb' : 'none',
							}"
						>
							<!-- Specular Glass Reflection Diagonal -->
							<div
								class="pointer-events-none absolute -inset-y-8 left-1/4 w-10 rotate-12 bg-white/35 blur-[1px]"
							/>

							<!-- Louver Blades -->
							<template v-if="cell.type === 'louver'">
								<div
									v-for="b in cell.blades"
									:key="b"
									class="w-full border-b border-slate-500/60 bg-slate-300/45"
									:style="{ height: `${100 / cell.blades}%` }"
								/>
							</template>

							<!-- Exhaust Fan Cutout -->
							<div
								v-if="cell.fan"
								class="pointer-events-none absolute top-4 left-1/2 flex h-14 w-14 -translate-x-1/2 items-center justify-center rounded-full border-2 border-slate-600 bg-white/75 shadow-inner"
							>
								<div class="h-8 w-8 rounded-full border border-dashed border-slate-500" />
							</div>

							<!-- Panel Tag -->
							<span
								v-if="cell.label"
								class="pointer-events-none absolute top-2 left-2 rounded bg-slate-900/75 px-1.5 py-0.5 text-[10px] font-bold text-white"
							>
								{{ cell.label }}
							</span>
						</div>
					</div>
				</div>
			</div>

			<div class="pointer-events-none absolute bottom-3 left-4 flex items-center gap-3 text-xs text-gray-500">
				<span>Drag to orbit · Scroll to zoom · Click a panel to select</span>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { layoutGeom } from '@/design/geometry'
import type { CellGeom, Design } from '@/design/types'

const props = withDefaults(
	defineProps<{
		design: Design
		selectedPath: string | null
		finishColor?: string
		outsideFinishColor?: string
	}>(),
	{ finishColor: '#8A8F98', outsideFinishColor: '' },
)

const emit = defineEmits<{
	select: [path: string]
}>()

const yaw = ref(-26)
const pitch = ref(14)
const zoom = ref(1)
const openAngle = ref(25)

let dragging = false
let startX = 0
let startY = 0
let startYaw = 0
let startPitch = 0

function setCamera(y: number, p: number, z: number) {
	yaw.value = y
	pitch.value = p
	zoom.value = z
}

function onPointerDown(e: PointerEvent) {
	dragging = true
	startX = e.clientX
	startY = e.clientY
	startYaw = yaw.value
	startPitch = pitch.value
}

function onPointerMove(e: PointerEvent) {
	if (!dragging) return
	yaw.value = startYaw + (e.clientX - startX) * 0.45
	pitch.value = Math.max(-65, Math.min(65, startPitch - (e.clientY - startY) * 0.35))
}

function onPointerUp() {
	dragging = false
}

function onWheel(e: WheelEvent) {
	const next = zoom.value - e.deltaY * 0.001
	zoom.value = Math.max(0.55, Math.min(1.8, next))
}

const scale3d = computed(() => Math.min(380 / props.design.width, 420 / props.design.height))
const wPx = computed(() => props.design.width * scale3d.value)
const hPx = computed(() => props.design.height * scale3d.value)
const frameT = computed(() => Math.max(12, 42 * scale3d.value))
const barT = computed(() => Math.max(10, 40 * scale3d.value))
const sashT = computed(() => Math.max(12, 46 * scale3d.value))
const depthPx = 22

const frameHex = computed(() =>
	/^#[0-9a-f]{6}$/i.test(props.finishColor || '') ? props.finishColor! : '#8A8F98',
)
const outsideHex = computed(() =>
	/^#[0-9a-f]{6}$/i.test(props.outsideFinishColor || '') ? props.outsideFinishColor! : frameHex.value,
)
const sashHex = computed(() => frameHex.value)

const geom = computed(() => layoutGeom(props.design))

const bars3d = computed(() =>
	geom.value.bars.map((b) => {
		if (b.dir === 'v') {
			return {
				id: b.id,
				x: b.x * scale3d.value - barT.value / 2,
				y: (props.design.height - (b.y + b.length)) * scale3d.value,
				w: barT.value,
				h: b.length * scale3d.value,
			}
		}
		return {
			id: b.id,
			x: b.x * scale3d.value,
			y: (props.design.height - b.y) * scale3d.value - barT.value / 2,
			w: b.length * scale3d.value,
			h: barT.value,
		}
	}),
)

interface Cell3D {
	path: string
	type: 'sash' | 'fixed' | 'louver'
	x: number
	y: number
	w: number
	h: number
	hinge?: string
	opening?: string
	blades: number
	fan?: boolean
	label: string
	selected: boolean
}

const cells3d = computed<Cell3D[]>(() => {
	let sCount = 0
	let lCount = 0
	const { width, height } = props.design
	return geom.value.cells.map((c: CellGeom) => {
		const l = c.x === 0 ? frameT.value : barT.value / 2
		const r = c.x + c.w === width ? frameT.value : barT.value / 2
		const b = c.y === 0 ? frameT.value : barT.value / 2
		const t = c.y + c.h === height ? frameT.value : barT.value / 2
		const x = c.x * scale3d.value + l
		const y = (height - (c.y + c.h)) * scale3d.value + t
		const w = c.w * scale3d.value - l - r
		const h = c.h * scale3d.value - t - b
		const label =
			c.node.type === 'sash'
				? `S${++sCount}`
				: c.node.type === 'louver'
					? `L${++lCount}`
					: ''
		return {
			path: c.path,
			type: c.node.type,
			x,
			y,
			w: Math.max(10, w),
			h: Math.max(10, h),
			hinge: c.node.type === 'sash' ? c.node.hinge || 'left' : undefined,
			opening: c.node.type === 'sash' ? c.node.opening || 'out' : undefined,
			blades: c.node.type === 'louver' ? c.node.blades || 7 : 0,
			fan: Boolean(c.node.fan),
			label,
			selected: c.path === props.selectedPath,
		}
	})
})

function barBoxStyle(
	x: number,
	y: number,
	w: number,
	h: number,
	depth: number,
	insideColor: string,
	_outsideColor: string,
) {
	return {
		position: 'absolute' as const,
		left: `${x}px`,
		top: `${y}px`,
		width: `${w}px`,
		height: `${h}px`,
		backgroundColor: insideColor,
		border: '1px solid rgba(30,41,59,0.45)',
		transform: `translateZ(${depth / 2}px)`,
		boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.25), 0 4px 10px rgba(15,23,42,0.12)',
	}
}

function flatRailStyle(x: number, y: number, w: number, h: number, color: string) {
	return {
		position: 'absolute' as const,
		left: `${x}px`,
		top: `${y}px`,
		width: `${w}px`,
		height: `${h}px`,
		backgroundColor: color,
		border: '1px solid rgba(30,41,59,0.45)',
		boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.22)',
	}
}

function cellTransformStyle(c: Cell3D) {
	let transformOrigin = 'center center'
	let rotate = ''
	if (c.type === 'sash' && openAngle.value > 0 && c.opening !== 'none') {
		const dirSign = c.opening === 'in' ? 1 : -1
		if (c.hinge === 'left') {
			transformOrigin = '0% 50%'
			rotate = `rotateY(${dirSign * openAngle.value}deg)`
		} else if (c.hinge === 'right') {
			transformOrigin = '100% 50%'
			rotate = `rotateY(${-dirSign * openAngle.value}deg)`
		} else if (c.hinge === 'top') {
			transformOrigin = '50% 0%'
			rotate = `rotateX(${-dirSign * openAngle.value}deg)`
		}
	}
	return {
		position: 'absolute' as const,
		left: `${c.x}px`,
		top: `${c.y}px`,
		width: `${c.w}px`,
		height: `${c.h}px`,
		transformOrigin,
		transform: `translateZ(10px) ${rotate}`,
		transition: 'transform 180ms ease-out',
		transformStyle: 'preserve-3d' as const,
	}
}

function handleStyle(c: Cell3D) {
	if (c.hinge === 'top') {
		return {
			bottom: `${Math.max(2, sashT.value / 2 - 2.5)}px`,
			left: `${c.w / 2 - 12}px`,
			width: '24px',
			height: '5px',
		}
	}
	const isLeftHinge = c.hinge !== 'right'
	return {
		top: `${c.h * 0.5 - 14}px`,
		left: isLeftHinge ? `${c.w - sashT.value / 2 - 2.5}px` : `${sashT.value / 2 - 2.5}px`,
		width: '5px',
		height: '28px',
	}
}
</script>

<style scoped>
.stage-3d {
	transform-style: preserve-3d;
	transition: transform 60ms linear;
}
.abs-3d {
	transform-style: preserve-3d;
}
</style>

