<template>
	<div class="flex h-full w-full flex-col overflow-hidden bg-slate-50 p-4" data-testid="window-section-view">
		<div class="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white px-4 py-2.5 shadow-xs">
			<div class="flex items-center gap-2">
				<span class="text-xs font-semibold uppercase tracking-wider text-gray-500">Section Plane</span>
				<div class="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5">
					<button
						type="button"
						class="rounded-md px-3 py-1 text-xs font-semibold transition-colors"
						:class="plane === 'h' ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-600 hover:text-gray-900'"
						@click="plane = 'h'"
					>
						Horizontal Plan (A–A)
					</button>
					<button
						type="button"
						class="rounded-md px-3 py-1 text-xs font-semibold transition-colors"
						:class="plane === 'v' ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-600 hover:text-gray-900'"
						@click="plane = 'v'"
					>
						Vertical Sill-Head (B–B)
					</button>
				</div>
			</div>

			<div class="flex items-center gap-3 text-xs text-gray-600">
				<label class="flex items-center gap-2">
					<span class="font-medium">Cut position:</span>
					<input
						v-model.number="cutRatio"
						type="range"
						min="0.1"
						max="0.9"
						step="0.05"
						class="h-1.5 w-28 cursor-pointer accent-gray-900"
					/>
					<span class="w-16 font-mono text-gray-800">
						{{ plane === 'h' ? `Y = ${Math.round(design.height * cutRatio)} mm` : `X = ${Math.round(design.width * cutRatio)} mm` }}
					</span>
				</label>
			</div>
		</div>

		<!-- Main Assembly Cross-Section SVG -->
		<div class="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-xl border border-gray-200 bg-white p-4">
			<svg
				:viewBox="`0 0 880 340`"
				class="h-full max-h-[360px] w-full"
				xmlns="http://www.w3.org/2000/svg"
			>
				<defs>
					<pattern id="sec-grid" width="20" height="20" patternUnits="userSpaceOnUse">
						<path d="M 20 0 L 0 0 0 20" fill="none" stroke="#f1f5f9" stroke-width="1" />
					</pattern>
					<pattern id="alum-hatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
						<line x1="0" y1="0" x2="0" y2="8" stroke="#475569" stroke-width="1.2" opacity="0.35" />
					</pattern>
				</defs>
				<rect x="0" y="0" width="880" height="340" fill="url(#sec-grid)" />

				<!-- Outside / Inside labels -->
				<text x="24" y="42" font-size="11" font-weight="600" fill="#64748b" letter-spacing="0.08em">OUTSIDE (EXTERIOR)</text>
				<line x1="24" y1="50" x2="856" y2="50" stroke="#e2e8f0" stroke-dasharray="4 4" />
				<text x="24" y="255" font-size="11" font-weight="600" fill="#64748b" letter-spacing="0.08em">INSIDE (ROOM SIDE)</text>

				<!-- Outer Left/Top Frame Jamb -->
				<g :transform="`translate(${secStart}, 95)`">
					<rect x="0" y="0" width="38" height="105" rx="2" :fill="finishHex" stroke="#1e293b" stroke-width="1.6" />
					<rect x="0" y="0" width="38" height="105" rx="2" fill="url(#alum-hatch)" />
					<rect x="24" y="0" width="14" height="32" fill="#f8fafc" stroke="#1e293b" stroke-width="1.2" />
					<text x="19" y="-10" text-anchor="middle" font-size="11" font-weight="700" fill="#0f172a">
						{{ frameProfile?.profile_code || 'FRAME' }}
					</text>
				</g>

				<!-- Outer Right/Bottom Frame Jamb -->
				<g :transform="`translate(${secEnd - 38}, 95)`">
					<rect x="0" y="0" width="38" height="105" rx="2" :fill="finishHex" stroke="#1e293b" stroke-width="1.6" />
					<rect x="0" y="0" width="38" height="105" rx="2" fill="url(#alum-hatch)" />
					<rect x="0" y="0" width="14" height="32" fill="#f8fafc" stroke="#1e293b" stroke-width="1.2" />
					<text x="19" y="-10" text-anchor="middle" font-size="11" font-weight="700" fill="#0f172a">
						{{ frameProfile?.profile_code || 'FRAME' }}
					</text>
				</g>

				<!-- Sliced Cells along the section line -->
				<g v-for="(slice, idx) in slices" :key="slice.path">
					<!-- Intermediate Mullion / Transom between slices -->
					<g v-if="idx > 0" :transform="`translate(${slice.xPx - 19}, 95)`">
						<rect x="0" y="0" width="38" height="105" rx="2" :fill="finishHex" stroke="#1e293b" stroke-width="1.6" />
						<rect x="0" y="0" width="38" height="105" rx="2" fill="url(#alum-hatch)" />
						<rect x="0" y="0" width="10" height="28" fill="#f8fafc" stroke="#1e293b" stroke-width="1.2" />
						<rect x="28" y="0" width="10" height="28" fill="#f8fafc" stroke="#1e293b" stroke-width="1.2" />
						<text x="19" y="-10" text-anchor="middle" font-size="11" font-weight="700" fill="#2563eb">
							{{ plane === 'h' ? `M${idx}` : `T${idx}` }} · {{ mullionProfile?.profile_code || 'MULLION' }}
						</text>
					</g>

					<!-- Sash Stile/Rail if cell is Sash -->
					<template v-if="slice.type === 'sash'">
						<!-- Left Sash stile -->
						<g :transform="`translate(${slice.xPx + 20}, 82)`">
							<rect x="0" y="0" width="34" height="96" rx="2" :fill="finishHex" stroke="#1e293b" stroke-width="1.5" />
							<rect x="0" y="0" width="34" height="96" rx="2" fill="url(#alum-hatch)" />
							<!-- Glazing Bead -->
							<rect x="34" y="48" width="14" height="30" rx="1.5" fill="#cbd5e1" stroke="#334155" stroke-width="1.2" />
							<!-- EPDM Gasket dots -->
							<circle cx="34" cy="40" r="3" fill="#0f172a" />
							<circle cx="48" cy="48" r="2.5" fill="#0f172a" />
						</g>
						<!-- Right Sash stile -->
						<g :transform="`translate(${slice.xPx + slice.wPx - 54}, 82)`">
							<rect x="0" y="0" width="34" height="96" rx="2" :fill="finishHex" stroke="#1e293b" stroke-width="1.5" />
							<rect x="0" y="0" width="34" height="96" rx="2" fill="url(#alum-hatch)" />
							<!-- Glazing Bead -->
							<rect x="-14" y="48" width="14" height="30" rx="1.5" fill="#cbd5e1" stroke="#334155" stroke-width="1.2" />
							<circle cx="0" cy="40" r="3" fill="#0f172a" />
							<circle cx="-14" cy="48" r="2.5" fill="#0f172a" />
						</g>
						<!-- Glass Pane inside Sash -->
						<rect
							:x="slice.xPx + 54"
							y="134"
							:width="Math.max(20, slice.wPx - 108)"
							height="10"
							fill="#bae6fd"
							stroke="#0284c7"
							stroke-width="1.4"
						/>
						<text
							:x="slice.xPx + slice.wPx / 2"
							y="124"
							text-anchor="middle"
							font-size="11"
							font-weight="600"
							fill="#0369a1"
						>
							Sash ({{ sashProfile?.profile_code || 'SASH' }}) · Glass {{ slice.glass }}
						</text>
					</template>

					<!-- Fixed Glass or Louver -->
					<template v-else>
						<!-- Left & Right Glazing Beads on Frame/Mullion -->
						<rect :x="slice.xPx + 20" y="142" width="14" height="30" rx="1.5" fill="#cbd5e1" stroke="#334155" stroke-width="1.2" />
						<rect :x="slice.xPx + slice.wPx - 34" y="142" width="14" height="30" rx="1.5" fill="#cbd5e1" stroke="#334155" stroke-width="1.2" />
						<rect
							:x="slice.xPx + 24"
							y="132"
							:width="Math.max(20, slice.wPx - 48)"
							height="10"
							fill="#bae6fd"
							stroke="#0284c7"
							stroke-width="1.4"
						/>
						<text
							:x="slice.xPx + slice.wPx / 2"
							y="122"
							text-anchor="middle"
							font-size="11"
							font-weight="600"
							fill="#0369a1"
						>
							{{ slice.type === 'louver' ? 'Louver' : 'Fixed' }} · Glass {{ slice.glass }}
						</text>
					</template>

					<!-- Cell Dimension Line -->
					<g stroke="#475569" stroke-width="1.1">
						<line :x1="slice.xPx" y1="280" :x2="slice.xPx + slice.wPx" y2="280" />
						<line :x1="slice.xPx" y1="274" :x2="slice.xPx" y2="286" />
						<line :x1="slice.xPx + slice.wPx" y1="274" :x2="slice.xPx + slice.wPx" y2="286" />
						<text
							:x="slice.xPx + slice.wPx / 2"
							y="273"
							text-anchor="middle"
							font-size="11"
							font-weight="600"
							fill="#0f172a"
							stroke="none"
						>
							{{ Math.round(slice.spanMm * 10) / 10 }} mm
						</text>
					</g>
				</g>

				<!-- Overall Span Dimension Line -->
				<g stroke="#0f172a" stroke-width="1.2">
					<line :x1="secStart" y1="312" :x2="secEnd" y2="312" />
					<line :x1="secStart" y1="305" :x2="secStart" y2="319" />
					<line :x1="secEnd" y1="305" :x2="secEnd" y2="319" />
					<text
						x="440"
						y="305"
						text-anchor="middle"
						font-size="12"
						font-weight="700"
						fill="#0f172a"
						stroke="none"
					>
						Overall {{ plane === 'h' ? 'Width' : 'Height' }}: {{ plane === 'h' ? design.width : design.height }} mm
					</text>
				</g>
			</svg>
		</div>

		<!-- Bottom CAD Profile Cross-Section Cards from Series Studio -->
		<div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div
				v-for="item in roleCards"
				:key="item.role"
				class="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-2.5 shadow-xs"
			>
				<div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border border-gray-100 bg-slate-50 p-1">
					<svg
						v-if="item.profile?.section_svg && item.profile.width_mm && item.profile.depth_mm"
						:viewBox="`0 0 ${svgMetrics(item.profile).cw} ${svgMetrics(item.profile).ch}`"
						class="h-full w-full"
					>
						<g :transform="`translate(${svgMetrics(item.profile).ox}, ${svgMetrics(item.profile).oy}) scale(${svgMetrics(item.profile).s})`">
							<g :transform="profileRotationTransform(item.profile)">
								<path
									:d="item.profile.section_svg"
									fill="#94a3b8"
									fill-opacity="0.85"
									stroke="#1e293b"
									:stroke-width="svgMetrics(item.profile).pathStroke"
									fill-rule="evenodd"
								/>
							</g>
						</g>
					</svg>
					<span v-else class="text-[10px] font-medium text-gray-400">DXF</span>
				</div>
				<div class="min-w-0 flex-1">
					<div class="text-[10px] font-bold uppercase tracking-wider text-gray-400">{{ item.label }}</div>
					<div class="truncate text-xs font-semibold text-gray-900">
						{{ item.profile ? item.profile.profile_code : '—' }}
					</div>
					<div class="truncate text-[11px] text-gray-500">
						<template v-if="item.profile">
							{{ Number(item.profile.width_mm || 0).toFixed(1) }}×{{ Number(item.profile.depth_mm || 0).toFixed(1) }} mm · {{ Number(item.profile.kg_per_m || 0).toFixed(3) }} kg/m
						</template>
						<template v-else>Not assigned</template>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { useList } from 'frappe-ui'
import { computed, ref } from 'vue'
import { layoutGeom } from '@/design/geometry'
import type { Design } from '@/design/types'
import type { FenestrationProfileRow } from '@/studio/api'
import { computeCardSvgMetrics, profileRotationTransform } from '@/studio/sectionSvg'

const props = withDefaults(
	defineProps<{
		design: Design
		seriesVersion?: string
		finishColor?: string
	}>(),
	{ seriesVersion: '', finishColor: '#8A8F98' },
)

const plane = ref<'h' | 'v'>('h')
const cutRatio = ref(0.5)

const secStart = 80
const secEnd = 800
const totalPx = secEnd - secStart

const finishHex = computed(() =>
	/^#[0-9a-f]{6}$/i.test(props.finishColor || '') ? props.finishColor! : '#8A8F98',
)

const seriesCode = computed(() => {
	const sv = props.seriesVersion || ''
	return sv.includes('-') ? sv.split('-')[0] : sv || 'CS400'
})

const profileResource = useList<FenestrationProfileRow>({
	doctype: 'Fenestration Profile',
	fields: [
		'name',
		'profile_code',
		'profile_name',
		'series',
		'role',
		'kg_per_m',
		'width_mm',
		'depth_mm',
		'section_svg',
		'section_rotation',
	],
	limit: 200,
})

const seriesProfiles = computed(() =>
	(profileResource.data ?? []).filter((p) => !seriesCode.value || p.series === seriesCode.value),
)

const frameProfile = computed(() => seriesProfiles.value.find((p) => p.role === 'frame'))
const mullionProfile = computed(() => seriesProfiles.value.find((p) => p.role === 'mullion'))
const sashProfile = computed(() => seriesProfiles.value.find((p) => p.role === 'sash'))
const beadProfile = computed(() => seriesProfiles.value.find((p) => p.role === 'bead'))

const roleCards = computed(() => [
	{ role: 'frame', label: 'Outer Frame', profile: frameProfile.value },
	{ role: 'mullion', label: 'Mullion / Transom', profile: mullionProfile.value },
	{ role: 'sash', label: 'Window Sash', profile: sashProfile.value },
	{ role: 'bead', label: 'Glazing Bead', profile: beadProfile.value },
])

function svgMetrics(p: FenestrationProfileRow) {
	return computeCardSvgMetrics(p.width_mm, p.depth_mm)
}

const slices = computed(() => {
	const geom = layoutGeom(props.design)
	const { width, height } = props.design
	if (plane.value === 'h') {
		const yCut = height * cutRatio.value
		const hit = geom.cells
			.filter((c) => yCut >= c.y && yCut <= c.y + c.h)
			.sort((a, b) => a.x - b.x)
		const list = hit.length ? hit : geom.cells
		return list.map((c) => ({
			path: c.path,
			type: c.node.type,
			glass: c.node.glass,
			spanMm: c.w,
			xPx: secStart + (c.x / width) * totalPx,
			wPx: (c.w / width) * totalPx,
		}))
	} else {
		const xCut = width * cutRatio.value
		const hit = geom.cells
			.filter((c) => xCut >= c.x && xCut <= c.x + c.w)
			.sort((a, b) => b.y - a.y)
		const list = hit.length ? hit : geom.cells
		return list.map((c) => ({
			path: c.path,
			type: c.node.type,
			glass: c.node.glass,
			spanMm: c.h,
			xPx: secStart + ((height - (c.y + c.h)) / height) * totalPx,
			wPx: (c.h / height) * totalPx,
		}))
	}
})
</script>

