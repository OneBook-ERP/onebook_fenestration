<template>
	<Dialog
		:model-value="modelValue"
		:options="{ size: '2xl' }"
		:title="profile ? `${displayProfileCode(profile)} · ${profile.profile_name}` : 'Profile Details'"
		@update:model-value="$emit('update:modelValue', $event)"
	>
		<div v-if="profile" class="space-y-4">
			<div class="flex flex-wrap items-start justify-between gap-3">
				<div>
					<div class="text-xs text-ink-gray-6">
						Series: <strong class="text-ink-gray-9">{{ profile.series }}</strong> · Role:
						<strong class="capitalize text-ink-gray-9">{{ profile.role }}</strong> · DXF:
						<code class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs">{{ cleanDxfFilename(profile.dxf_file) }}</code>
					</div>
					<div v-if="hasSvg" class="mt-1 text-xs text-ink-gray-5">
						{{ metrics.loops }} closed loop{{ metrics.loops === 1 ? '' : 's' }}
						<template v-if="metrics.chambers > 0">
							({{ metrics.chambers }} chamber{{ metrics.chambers === 1 ? '' : 's' }})
						</template>
						· Bar lengths: {{ profile.bar_lengths || '4880, 5800' }} mm
					</div>
				</div>

				<div class="flex items-center gap-2">
					<div
						v-if="hasSvg"
						class="inline-flex overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-gray-1"
					>
						<button
							type="button"
							class="px-2.5 py-1 text-xs font-semibold transition-colors"
							:class="showGrid ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
							@click="showGrid = !showGrid"
						>
							Grid
						</button>
						<button
							type="button"
							class="border-l border-outline-gray-2 px-2.5 py-1 text-xs font-semibold transition-colors"
							:class="showDims ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
							@click="showDims = !showDims"
						>
							Dimensions
						</button>
						<button
							type="button"
							class="border-l border-outline-gray-2 px-2.5 py-1 text-xs font-semibold transition-colors"
							:class="showCentroid ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
							@click="showCentroid = !showCentroid"
						>
							Centroid
						</button>
					</div>
					<Badge :theme="hasSvg ? 'green' : 'gray'" :label="hasSvg ? 'Parsed' : 'No DXF'" />
				</div>
			</div>

			<div
				class="flex min-h-[280px] items-center justify-center overflow-hidden rounded-xl border border-outline-gray-2 bg-slate-50"
			>
				<svg
					v-if="hasSvg"
					:viewBox="`0 0 ${metrics.cw} ${metrics.ch}`"
					class="block h-[300px] w-full"
					xmlns="http://www.w3.org/2000/svg"
				>
					<defs>
						<pattern
							id="studio-grid-min"
							:width="metrics.minorPx"
							:height="metrics.minorPx"
							patternUnits="userSpaceOnUse"
							:patternTransform="`translate(${metrics.ox}, ${metrics.oy})`"
						>
							<path
								:d="`M ${metrics.minorPx} 0 L 0 0 0 ${metrics.minorPx}`"
								fill="none"
								stroke="#e2e8f0"
								stroke-width="0.7"
							/>
						</pattern>
						<pattern
							id="studio-grid-maj"
							:width="metrics.majorPx"
							:height="metrics.majorPx"
							patternUnits="userSpaceOnUse"
							:patternTransform="`translate(${metrics.ox}, ${metrics.oy})`"
						>
							<rect :width="metrics.majorPx" :height="metrics.majorPx" fill="url(#studio-grid-min)" />
							<path
								:d="`M ${metrics.majorPx} 0 L 0 0 0 ${metrics.majorPx}`"
								fill="none"
								stroke="#cbd5e1"
								stroke-width="1.1"
							/>
						</pattern>
					</defs>

					<rect
						v-if="showGrid"
						x="0"
						y="0"
						:width="metrics.cw"
						:height="metrics.ch"
						fill="url(#studio-grid-maj)"
					/>

					<g :transform="`translate(${metrics.ox}, ${metrics.oy}) scale(${metrics.s})`">
						<path
							:d="profile.section_svg || ''"
							fill="#94a3b8"
							fill-opacity="0.86"
							stroke="#1e293b"
							:stroke-width="metrics.pathStroke"
							stroke-linejoin="round"
							fill-rule="evenodd"
						/>
					</g>

					<g v-if="showDims" stroke="#475569" stroke-width="1.15" stroke-linecap="square">
						<line :x1="metrics.ox" :y1="metrics.dimY" :x2="metrics.ox + metrics.dw" :y2="metrics.dimY" />
						<line :x1="metrics.ox" :y1="metrics.dimY - metrics.tick" :x2="metrics.ox" :y2="metrics.dimY + metrics.tick" />
						<line :x1="metrics.ox + metrics.dw" :y1="metrics.dimY - metrics.tick" :x2="metrics.ox + metrics.dw" :y2="metrics.dimY + metrics.tick" />

						<line :x1="metrics.dimX" :y1="metrics.oy" :x2="metrics.dimX" :y2="metrics.oy + metrics.dh" />
						<line :x1="metrics.dimX - metrics.tick" :y1="metrics.oy" :x2="metrics.dimX + metrics.tick" :y2="metrics.oy" />
						<line :x1="metrics.dimX - metrics.tick" :y1="metrics.oy + metrics.dh" :x2="metrics.dimX + metrics.tick" :y2="metrics.oy + metrics.dh" />
					</g>
					<template v-if="showDims">
						<text
							:x="metrics.ox + metrics.dw / 2"
							:y="metrics.dimY + 18"
							text-anchor="middle"
							fill="#0f172a"
							:font-size="metrics.fontSize"
							font-weight="600"
						>
							{{ metrics.widthLabel }}
						</text>
						<text
							:x="metrics.vTextX"
							:y="metrics.vTextY"
							text-anchor="middle"
							dominant-baseline="central"
							fill="#0f172a"
							:font-size="metrics.fontSize"
							font-weight="600"
							:transform="`rotate(-90 ${metrics.vTextX} ${metrics.vTextY})`"
						>
							{{ metrics.depthLabel }}
						</text>
					</template>

					<g v-if="showCentroid">
						<circle :cx="metrics.cx" :cy="metrics.cy" r="3.4" fill="#2563eb" stroke="#ffffff" stroke-width="1.2" />
						<text
							:x="metrics.cx + 6.5"
							:y="metrics.cy - 2.5"
							fill="#2563eb"
							stroke="#f8fafc"
							stroke-width="3"
							paint-order="stroke"
							font-size="11.5"
							font-weight="600"
						>
							centroid
						</text>
					</g>
				</svg>
				<div v-else class="p-6 text-center text-sm text-ink-gray-5">
					No DXF section attached to this profile yet.
				</div>
			</div>

			<div class="grid grid-cols-2 gap-x-8 gap-y-4 border-t border-outline-gray-1 pt-4 sm:grid-cols-3">
				<div>
					<div class="text-xs text-ink-gray-5">Section area</div>
					<div class="text-base font-bold text-ink-gray-9">{{ Number(profile.area_mm2 || 0).toFixed(1) }} mm²</div>
				</div>
				<div>
					<div class="text-xs text-ink-gray-5">Weight</div>
					<div class="text-base font-bold text-ink-gray-9">{{ effectiveWeight(profile).toFixed(3) }} kg/m</div>
				</div>
				<div>
					<div class="text-xs text-ink-gray-5">Width × depth</div>
					<div class="text-base font-bold text-ink-gray-9">
						{{ Number(profile.width_mm || 0).toFixed(1) }} × {{ Number(profile.depth_mm || 0).toFixed(1) }} mm
					</div>
				</div>
				<div>
					<div class="text-xs text-ink-gray-5">Outer perimeter</div>
					<div class="text-base font-bold text-ink-gray-9">{{ Number(profile.perimeter_mm || 0).toFixed(1) }} mm</div>
				</div>
				<div>
					<div class="text-xs text-ink-gray-5">Ix / Iy</div>
					<div class="text-base font-bold text-ink-gray-9">
						{{ Math.round(profile.ix_mm4 || 0).toLocaleString('en-IN') }} / {{ Math.round(profile.iy_mm4 || 0).toLocaleString('en-IN') }} mm⁴
					</div>
				</div>
				<div>
					<div class="text-xs text-ink-gray-5">Material</div>
					<div class="text-base font-bold text-ink-gray-9">Al 6063-T6</div>
				</div>
			</div>
		</div>

		<template #actions>
			<Button v-if="profile" variant="solid" @click="$emit('edit', profile)">
				Edit Profile
			</Button>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Badge, Button, Dialog } from 'frappe-ui'
import { computed, ref } from 'vue'
import type { FenestrationProfileRow } from '@/studio/api'
import {
	cleanDxfFilename,
	computeBlueprintSvgMetrics,
	displayProfileCode,
	effectiveWeight,
} from '@/studio/sectionSvg'

const props = defineProps<{
	modelValue: boolean
	profile: FenestrationProfileRow | null
}>()

defineEmits<{
	(e: 'update:modelValue', v: boolean): void
	(e: 'edit', p: FenestrationProfileRow): void
}>()

const showGrid = ref(true)
const showDims = ref(true)
const showCentroid = ref(true)

const hasSvg = computed(() =>
	Boolean(props.profile?.section_svg && props.profile?.width_mm && props.profile?.depth_mm),
)

const metrics = computed(() =>
	computeBlueprintSvgMetrics(
		props.profile || {
			name: '',
			profile_code: '',
			profile_name: '',
			series: '',
			role: 'frame',
			kg_per_m: 0,
			bar_lengths: '',
		},
		showDims.value,
	),
)
</script>

