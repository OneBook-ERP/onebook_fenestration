<script setup lang="ts">
import { computed } from "vue";
import type { CutAxis } from "@/api";
import type {
	DynamicDomainState,
	GasketPlacement,
	PocketProbeResult,
} from "@/design/pocketRaycast";
import type { Point } from "@/design/sectionPuzzle";

const props = withDefaults(
	defineProps<{
		axis: CutAxis;
		raycastMode: boolean;
		hoverPoint: Point | null;
		hoverProbe: PocketProbeResult | null;
		showAnchors: boolean;
		dynamicStates: DynamicDomainState[];
		gaskets: GasketPlacement[];
		mmPerPx?: number;
	}>(),
	{ mmPerPx: 0.25 }
);

const r1 = (n: number) => Math.round(n * 10) / 10;
const lockedDotR = computed(() => Math.min(0.55, Math.max(0.18, props.mmPerPx * 2.4)));
const hoverDotR = computed(() => Math.min(0.68, Math.max(0.22, props.mmPerPx * 2.8)));
const reticleR = computed(() => Math.min(0.85, Math.max(0.28, props.mmPerPx * 3.4)));
</script>

<template>
	<g data-testid="section-raycast-overlay" pointer-events="none">
		<!-- 1. Seated Outer & Inner Glazing Gaskets centered on Vertical Ray Anchors (hidden while aiming in Raycast Mode) -->
		<g
			v-if="!raycastMode && gaskets.length"
			data-testid="section-gasket-layer"
			pointer-events="auto"
		>
			<g v-for="g in gaskets" :key="g.id" :data-testid="`section-gasket-${g.id}`">
				<title>{{ g.code }} ({{ g.nominalMm }} mm {{ g.face }} gasket)</title>
				<rect
					:x="g.x"
					:y="g.y"
					:width="g.w"
					:height="g.h"
					:rx="Math.min(0.9, g.w * 0.25, g.h * 0.3)"
					fill="#1E293B"
					fill-opacity="0.88"
					stroke="#0F172A"
					stroke-width="0.7"
					vector-effect="non-scaling-stroke"
				/>
				<ellipse
					v-if="g.h >= 2.2"
					:cx="g.x + g.w / 2"
					:cy="g.y + g.h / 2"
					:rx="Math.max(0.4, g.w * 0.18)"
					:ry="Math.max(0.3, g.h * 0.18)"
					fill="#475569"
				/>
			</g>
		</g>

		<!-- 2. Fixed Raycast Anchor Points & Vertical Guidelines (Steps 3, 5 & 6) -->
		<g v-if="showAnchors && dynamicStates.length" data-testid="raycast-vertical-anchors">
			<g v-for="(st, idx) in dynamicStates" :key="`dyn-${idx}`">
				<!-- Outer pocket wall ticks when narrowed by a bead -->
				<template v-if="st.narrowedByBead">
					<line
						:x1="st.leftWallX"
						:x2="st.lowAnchorX + 2"
						:y1="st.pocketMinY"
						:y2="st.pocketMinY"
						stroke="#64748B"
						stroke-width="0.85"
						stroke-dasharray="2 2"
						vector-effect="non-scaling-stroke"
					/>
					<line
						:x1="st.leftWallX"
						:x2="st.lowAnchorX + 2"
						:y1="st.pocketMaxY"
						:y2="st.pocketMaxY"
						stroke="#64748B"
						stroke-width="0.85"
						stroke-dasharray="2 2"
						vector-effect="non-scaling-stroke"
					/>
				</template>

				<!-- Left & Right Horizontal Back-Wall Anchors -->
				<circle
					:cx="st.leftWallX"
					:cy="(st.effectiveMinY + st.effectiveMaxY) / 2"
					:r="lockedDotR"
					fill="#0284C7"
					stroke="#FFFFFF"
					stroke-width="0.6"
					vector-effect="non-scaling-stroke"
				/>
				<circle
					:cx="st.rightWallX"
					:cy="(st.effectiveMinY + st.effectiveMaxY) / 2"
					:r="lockedDotR"
					fill="#0284C7"
					stroke="#FFFFFF"
					stroke-width="0.6"
					vector-effect="non-scaling-stroke"
				/>

				<!-- Low & High Vertical Gasket Anchor Guidelines + Clamping Lip Dots -->
				<template v-for="ax in [st.lowAnchorX, st.highAnchorX]" :key="ax">
					<line
						:x1="ax"
						:x2="ax"
						:y1="st.effectiveMinY - 2"
						:y2="st.effectiveMaxY + 2"
						stroke="#0EA5E9"
						stroke-width="1"
						stroke-dasharray="3 2"
						vector-effect="non-scaling-stroke"
					/>
					<circle
						:cx="ax"
						:cy="st.effectiveMinY"
						:r="lockedDotR"
						fill="#E11D48"
						stroke="#FFFFFF"
						stroke-width="0.6"
						vector-effect="non-scaling-stroke"
					/>
					<circle
						:cx="ax"
						:cy="st.effectiveMaxY"
						:r="lockedDotR"
						fill="#E11D48"
						stroke="#FFFFFF"
						stroke-width="0.6"
						vector-effect="non-scaling-stroke"
					/>
				</template>
			</g>
		</g>

		<!-- 3. Live 4-Way Raycast Crosshair Preview (Steps 2 & 3) -->
		<g v-if="raycastMode && (hoverProbe || hoverPoint)" data-testid="raycast-hover-preview">
			<template v-if="hoverProbe">
				<!-- Preview Pocket Domain Fill -->
				<rect
					:x="hoverProbe.leftWallX"
					:y="hoverProbe.pocketMinY"
					:width="Math.max(1, hoverProbe.rightWallX - hoverProbe.leftWallX)"
					:height="Math.max(1, hoverProbe.pocketMaxY - hoverProbe.pocketMinY)"
					fill="#0EA5E9"
					fill-opacity="0.12"
					stroke="#0284C7"
					stroke-width="1.3"
					stroke-dasharray="4 2.5"
					vector-effect="non-scaling-stroke"
				/>

				<!-- Left <-> Right Horizontal Ray -->
				<line
					:x1="hoverProbe.leftHit.point.x"
					:y1="hoverProbe.origin.y"
					:x2="hoverProbe.rightHit.point.x"
					:y2="hoverProbe.origin.y"
					stroke="#0284C7"
					stroke-width="1.1"
					stroke-dasharray="3.5 2"
					vector-effect="non-scaling-stroke"
				/>

				<!-- Top <-> Bottom Vertical Clamping Ray -->
				<line
					:x1="hoverProbe.topHit.x"
					:y1="hoverProbe.topHit.y"
					:x2="hoverProbe.bottomHit.x"
					:y2="hoverProbe.bottomHit.y"
					stroke="#E11D48"
					stroke-width="1.15"
					stroke-dasharray="3 2"
					vector-effect="non-scaling-stroke"
				/>

				<!-- 4 Small Wall Anchor Hit Dots -->
				<circle
					:cx="hoverProbe.leftHit.point.x"
					:cy="hoverProbe.origin.y"
					:r="hoverDotR"
					fill="#0284C7"
					stroke="#FFFFFF"
					stroke-width="0.7"
					vector-effect="non-scaling-stroke"
				/>
				<circle
					:cx="hoverProbe.rightHit.point.x"
					:cy="hoverProbe.origin.y"
					:r="hoverDotR"
					fill="#0284C7"
					stroke="#FFFFFF"
					stroke-width="0.7"
					vector-effect="non-scaling-stroke"
				/>
				<circle
					:cx="hoverProbe.topHit.x"
					:cy="hoverProbe.topHit.y"
					:r="hoverDotR"
					fill="#E11D48"
					stroke="#FFFFFF"
					stroke-width="0.7"
					vector-effect="non-scaling-stroke"
				/>
				<circle
					:cx="hoverProbe.bottomHit.x"
					:cy="hoverProbe.bottomHit.y"
					:r="hoverDotR"
					fill="#E11D48"
					stroke="#FFFFFF"
					stroke-width="0.7"
					vector-effect="non-scaling-stroke"
				/>

				<!-- Compact Pointer Origin Reticle -->
				<circle
					:cx="hoverProbe.origin.x"
					:cy="hoverProbe.origin.y"
					:r="reticleR"
					fill="#FFFFFF"
					fill-opacity="0.8"
					stroke="#0F172A"
					stroke-width="1"
					vector-effect="non-scaling-stroke"
				/>

				<!-- Live Measured BW Readout -->
				<text
					:x="(hoverProbe.leftWallX + hoverProbe.rightWallX) / 2"
					:y="hoverProbe.pocketMinY - 3.2"
					text-anchor="middle"
					font-size="3"
					font-weight="700"
					fill="#0369A1"
					:transform="
						axis === 'v'
							? `rotate(90 ${(hoverProbe.leftWallX + hoverProbe.rightWallX) / 2} ${
									hoverProbe.pocketMinY - 3.2
							  })`
							: undefined
					"
				>
					Pocket BW {{ r1(hoverProbe.pocketWidthMm) }} mm · Click to lock
				</text>
			</template>

			<!-- Aiming cursor when pointer is outside an open pocket -->
			<g v-else-if="hoverPoint">
				<circle
					:cx="hoverPoint.x"
					:cy="hoverPoint.y"
					:r="reticleR"
					fill="none"
					stroke="#64748B"
					stroke-width="1"
					vector-effect="non-scaling-stroke"
				/>
			</g>
		</g>
	</g>
</template>
