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
import { grillMembers, grillConfig, type Grill } from "@/design/grill";
import { snapGrill, type GrillBox, type GrillGuide } from "@/design/grillSnap";
import { getNode } from "@/design/tree";
import { Tooltip, toast } from "frappe-ui";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import {
	crossSection,
	setProfileOrientation,
	type CrossSection,
	type CutAxis as Axis,
	type CutResponse,
	type SectionOutline as Outline,
	type SectionPiece,
} from "@/api";
import {
	buildPlacedShape,
	canonicalPieceKey,
	canonicalTransformForPiece,
	mirroredOrientation,
	profileContactGuides,
	classifySectionPieceInstances,
	compactPieceSpans,
	computeBBox,
	canPiecesOverlap,
	DEFAULT_PROFILE_DEPTH_MM,
	defaultTransformForPiece,
	getTwinTag,
	GLASS_REF_THICKNESS_MM,
	instancePieceKey,
	isPieceMoveable,
	magneticAutoJoin,
	resolvePuzzleDrop,
	shapesCollide,
	type PlacedShape,
} from "@/design/sectionPuzzle";
import {
	computeSmartGuides,
	measureGuides,
	type Rect,
	type SmartGuideResult,
} from "./sectionSmartGuides";
import { layoutGeom } from "@/design/geometry";
import { startSectionSeating } from "@/design/sectionSeating";
import {
	applyGlassDomainDrag,
	fitGlassInDomain,
	glassDomainFromPiece,
	paneGasketsFromPiece,
	roundTenth,
	suggestInitialGlassDomain,
	type DomainDragHandle,
	type PaneGasketsMeta,
	type ResolvedGlassBounds,
} from "@/design/glassDomain";
import {
	PocketRaycaster,
	type DynamicDomainState,
	type GasketPlacement,
	type PocketProbeResult,
} from "@/design/pocketRaycast";
import SectionRaycastOverlay from "./SectionRaycastOverlay.vue";
import type { Point } from "@/design/sectionPuzzle";
import type { Design, SectionPieceTransform, SectionViewportState } from "@/design/types";
import type { SectionGlassDomain } from "@/studio/api";
import { COMPUTE_DEBOUNCE_MS } from "@/stores/designer";

const props = withDefaults(
	defineProps<{
		design: Design;
		seriesVersion: string;
		axis: Axis;
		at: number | null;
		selectedPath?: string | null;
		/** When true, glass is auto-generated/seated between profiles and not manually dragged. */
		autoGlass?: boolean;
		/** Active template Glass Domain override for live preview & interactive editing in Studio. */
		glassDomain?: SectionGlassDomain | null;
		/** When true, shows interactive Glass Domain boundary & drag/resize handles on the canvas. */
		editableGlassDomain?: boolean;
		/** Optional live gasket preview metadata from Series Studio before saving. */
		gasketMeta?: PaneGasketsMeta | null;
	}>(),
	{
		selectedPath: null,
		autoGlass: false,
		glassDomain: null,
		editableGlassDomain: false,
		gasketMeta: null,
	}
);

const emit = defineEmits<{
	"update:grill": [path: string, grill: Grill];
	"update:axis": [axis: Axis];
	cut: [at: number];
	"update:section-map": [map: Record<string, SectionPieceTransform>];
	"update:mirror-sync": [val: boolean];
	"update:compact-glass": [val: boolean];
	"update:section-viewport": [axis: Axis, vp: SectionViewportState];
	"update:glass-domain": [domain: SectionGlassDomain];
	"update:raycast-mode": [active: boolean];
	"update:measured-bw": [
		info: { pocketBwMm: number; effectiveBwMm: number; narrowedByBead: boolean } | null
	];
	"open-profile-picker": [piece: SectionPiece];
	"profile-orientation-updated": [code: string];
	"section-loaded": [cut: CrossSection];
	select: [path: string];
}>();

const AXES = [
	{ label: "B–B horizontal", value: "h" },
	{ label: "A–A vertical", value: "v" },
] as const;

const PAD_MM = 20;
const MIN_SECTION_ZOOM = 0.2;
const MAX_SECTION_ZOOM = 25.0;
const SECTION_ZOOM_STEP = 0.15;
const MAX_SECTION_PAN_MM = 600;
const PAN_KEY_STEP_MM = 15;

const ROLE_COLORS: Record<string, { stroke: string; fill: string; label: string }> = {
	sash: { stroke: "#EA580C", fill: "#FED7AA", label: "Sash" },
	frame: { stroke: "#334155", fill: "#CBD5E1", label: "Outer Frame" },
	mullion: { stroke: "#475569", fill: "#CBD5E1", label: "Mullion" },
	transom: { stroke: "#475569", fill: "#CBD5E1", label: "Transom" },
	bead: { stroke: "#0F766E", fill: "#99F6E4", label: "Bead / Gasket" },
	glass_adaptor: { stroke: "#0F766E", fill: "#99F6E4", label: "Adaptor / Gasket" },
	gasket: { stroke: "#0F766E", fill: "#99F6E4", label: "Gasket" },
	glass: { stroke: "#0284C7", fill: "#BAE6FD", label: "Stationary Glass" },
};

const axis = ref<Axis>(props.axis);
watch(
	() => props.axis,
	(a) => (axis.value = a)
);

const section = ref<CrossSection | null>(null);
const outlines = ref<Record<string, Outline>>({});
const error = ref("");
let seq = 0;
let timer: ReturnType<typeof setTimeout> | undefined;
let snapped: { axis: Axis; at: number } | null = null;

/** Mirror & Sync mode: mirrors Left <-> Right corners and syncs B-B (Top) <-> A-A (Side) views. */
const localMirrorSync = ref(props.design.mirrorSync ?? true);
watch(
	() => props.design.mirrorSync,
	(v) => {
		if (v !== undefined) localMirrorSync.value = v;
	}
);
const mirrorSync = computed({
	get: () => localMirrorSync.value,
	set: (val: boolean) => {
		localMirrorSync.value = val;
		emit("update:mirror-sync", val);
	},
});

/** Compact glass mode keeps glass stationary in the center at a compact span so profile scale is large & clear. */
const localCompactGlass = ref(props.design.compactGlass ?? true);
watch(
	() => props.design.compactGlass,
	(v) => {
		if (v !== undefined) localCompactGlass.value = v;
	}
);
const compactGlass = computed({
	get: () => localCompactGlass.value,
	set: (val: boolean) => {
		localCompactGlass.value = val;
		emit("update:compact-glass", val);
	},
});
function toggleCompactGlass() {
	compactGlass.value = !compactGlass.value;
	resetView();
}
watch(compactGlass, () => {
	resetView();
});
const selectedIndex = ref<number | null>(null);

const currentViewport = computed(() => props.design.sectionViewport?.[axis.value]);
const sectionZoom = ref(currentViewport.value?.zoom ?? 1);
const sectionPan = ref({
	x: currentViewport.value?.pan?.x ?? 0,
	y: currentViewport.value?.pan?.y ?? 0,
});

watch(currentViewport, (vp) => {
	if (vp) {
		sectionZoom.value = vp.zoom;
		sectionPan.value = { ...vp.pan };
	}
});

function emitViewport() {
	emit("update:section-viewport", axis.value, {
		zoom: sectionZoom.value,
		pan: { ...sectionPan.value },
	});
}
const shiftHeld = ref(false);
const isPanning = ref(false);
let suppressNextBgClick = false;

/** Tracked container dimensions so SVG viewBox and floating toolbar anchor align 1:1. */
const canvasWrapEl = ref<HTMLDivElement | null>(null);
const svgEl = ref<SVGSVGElement | null>(null);
const containerSize = ref({ width: 640, height: 520 });
let resizeObs: ResizeObserver | null = null;

function updateContainerSize() {
	const el = canvasWrapEl.value;
	if (!el) return;
	const { clientWidth: w, clientHeight: h } = el;
	if (w > 0 && h > 0 && (w !== containerSize.value.width || h !== containerSize.value.height)) {
		containerSize.value = { width: w, height: h };
	}
}

/** Local fallback map when used standalone without parent v-model/event persistence. */
const localSectionMap = ref<Record<string, SectionPieceTransform>>({});
watch(
	() => props.design.sectionMap,
	(m) => {
		localSectionMap.value = m ? { ...m } : {};
	},
	{ immediate: true, deep: true }
);

const activeMap = computed<Record<string, SectionPieceTransform>>(() => ({
	...localSectionMap.value,
	...(props.design.sectionMap ?? {}),
}));

/** Active ghost drag state while moving a profile piece. */
const ghostDrag = ref<{
	index: number;
	piece: SectionPiece;
	tag?: string;
	twinIndex?: number;
	twinTag?: string;
	twinPiece?: SectionPiece;
	startClientX: number;
	startClientY: number;
	origTransform: SectionPieceTransform;
	origTwinTransform?: SectionPieceTransform;
	currentTransform: SectionPieceTransform;
	twinTransform?: SectionPieceTransform;
	moved?: boolean;
	snapDisabled?: boolean;
	pointerId: number;
} | null>(null);

/** Active workspace pan drag state (dragging empty workspace or Shift+drag). */
let panDrag: {
	startX: number;
	startY: number;
	origX: number;
	origY: number;
	pointerId: number;
	moved: boolean;
} | null = null;

const lastSnapNotice = ref("");
const activeSmartGuides = ref<SmartGuideResult | null>(null);
/** mm per screen pixel, refreshed on every drag move. The template reads this, never svgUnitsPerPixel(). */
const guideScale = ref(0.5);
let lastMoveEvent: PointerEvent | null = null;

let cancelSeating: (() => void) | undefined;

let lastLoadedBeadSig = "";

async function load() {
	cancelSeating?.();
	clearTimeout(timer);
	const mine = ++seq;
	let res: CutResponse;
	try {
		res = await crossSection(props.design, props.seriesVersion, axis.value, props.at);
	} catch (e) {
		if (mine === seq)
			error.value = e instanceof Error ? e.message : "Could not cut the design";
		return;
	}
	if (mine !== seq) return;
	if (!res?.ok) {
		error.value = res?.message ?? "Could not cut the design";
		section.value = null;
		snapped = null;
		return;
	}
	error.value = "";
	section.value = res.result;
	outlines.value = res.outlines ?? {};
	const nextBeadSig = res.result.pieces
		.filter((p) => p.role === "bead" || p.role === "glass_adaptor")
		.map((p) => `${p.role}:${p.code}`)
		.join(",");
	if (
		lastLoadedBeadSig !== "" &&
		nextBeadSig !== lastLoadedBeadSig &&
		nextBeadSig !== "" &&
		props.glassDomain?.raycast?.enabled
	) {
		autoSeatBeadsForDomain(props.glassDomain);
	}
	lastLoadedBeadSig = nextBeadSig;
	seedDefaultSeats(res.result);
	snapped = { axis: axis.value, at: res.result.at };
	if (selectedIndex.value !== null && selectedIndex.value >= res.result.pieces.length) {
		selectedIndex.value = null;
	}
	emit("section-loaded", res.result);
	emit("cut", res.result.at);
}

function loadLater() {
	clearTimeout(timer);
	timer = setTimeout(load, COMPUTE_DEBOUNCE_MS);
}

load();

watch(
	() => [axis.value, props.seriesVersion, props.at] as const,
	([a, sv, at], [prevA, prevSv]) => {
		const onlyAtMoved = a === prevA && sv === prevSv;
		if (onlyAtMoved && snapped && snapped.axis === a && at === snapped.at) return;
		load();
	}
);
watch(
	() => [props.design.width, props.design.height, props.design.root, props.design.profiles],
	loadLater,
	{ deep: true }
);

onMounted(() => {
	updateContainerSize();
	if (typeof ResizeObserver !== "undefined" && canvasWrapEl.value) {
		resizeObs = new ResizeObserver(() => updateContainerSize());
		resizeObs.observe(canvasWrapEl.value);
	}
	window.addEventListener("keydown", onKeyDown);
	window.addEventListener("keyup", onKeyUp);
	window.addEventListener("blur", onWindowBlur);
});

onUnmounted(() => {
	cancelSeating?.();
	clearTimeout(timer);
	seq += 1;
	endPieceDrag();
	endWorkspacePan();
	resizeObs?.disconnect();
	window.removeEventListener("keydown", onKeyDown);
	window.removeEventListener("keyup", onKeyUp);
	window.removeEventListener("blur", onWindowBlur);
});

function pick(a: Axis) {
	if (a === axis.value) return;
	axis.value = a;
	emit("update:axis", a);
	const vp = props.design.sectionViewport?.[a];
	sectionZoom.value = vp?.zoom ?? 1;
	sectionPan.value = { x: vp?.pan?.x ?? 0, y: vp?.pan?.y ?? 0 };
}

const fmt = (n: number) => String(Math.round(n * 100) / 100);

function clampZoom(z: number): number {
	return Math.round(Math.min(MAX_SECTION_ZOOM, Math.max(MIN_SECTION_ZOOM, z)) * 100) / 100;
}

function clampPan(v: number): number {
	const limit = Math.max(3000, cutLength.value * 2);
	return Math.min(limit, Math.max(-limit, v));
}

function zoomIn() {
	const cur = sectionZoom.value;
	const step = cur < 1.95 ? 0.15 : cur < 5 ? 0.5 : cur < 10 ? 1.0 : 2.5;
	sectionZoom.value = clampZoom(cur + step);
	emitViewport();
}

function zoomOut() {
	const cur = sectionZoom.value;
	const step = cur <= 2.0 ? 0.15 : cur <= 5 ? 0.5 : cur <= 10 ? 1.0 : 2.5;
	sectionZoom.value = clampZoom(cur - step);
	emitViewport();
}

function resetView() {
	sectionZoom.value = 1;
	sectionPan.value = { x: 0, y: 0 };
	emitViewport();
}

function panBy(dxMm: number, dyMm: number) {
	sectionPan.value = {
		x: clampPan(sectionPan.value.x + dxMm),
		y: clampPan(sectionPan.value.y + dyMm),
	};
	emitViewport();
}

const pieceTags = computed(() => {
	const len = section.value?.length ?? props.design.width ?? 1220;
	return classifySectionPieceInstances(axis.value, section.value?.pieces ?? [], len);
});

const showGlassDomainOverlay = ref(true);
const raycastMode = ref(false);
const raycastHoverPoint = ref<Point | null>(null);

function setRaycastMode(active: boolean) {
	if (raycastMode.value === active) return;
	raycastMode.value = active;
	if (!active) raycastHoverPoint.value = null;
	emit("update:raycast-mode", active);
}

function rawGlassDomainForPiece(piece: SectionPiece, index: number): SectionGlassDomain | null {
	if (piece.kind !== "glass") return null;
	if (props.glassDomain?.configured && props.glassDomain.maxY - props.glassDomain.minY >= 1) {
		const pieces = section.value?.pieces ?? [];
		const glassIndices = pieces.reduce<number[]>((acc, p, idx) => {
			if (p.kind === "glass") acc.push(idx);
			return acc;
		}, []);
		if (glassIndices.length > 1) {
			const bayIdx = glassIndices.indexOf(index);
			const mullionInset =
				props.glassDomain.insetMullion != null
					? props.glassDomain.insetMullion
					: props.glassDomain.insetHigh;
			const rc = props.glassDomain.raycast;
			const rcMul =
				rc?.pocketInsetMullion != null ? rc.pocketInsetMullion : rc?.pocketInsetHigh ?? 0;
			if (bayIdx === 0) {
				return {
					...props.glassDomain,
					insetLow: props.glassDomain.insetLow,
					insetHigh: mullionInset,
					...(rc ? { raycast: { ...rc, pocketInsetHigh: rcMul } } : {}),
				};
			}
			if (bayIdx === glassIndices.length - 1) {
				return {
					...props.glassDomain,
					insetLow: mullionInset,
					insetHigh: props.glassDomain.insetLow,
					...(rc
						? {
								raycast: {
									...rc,
									pocketInsetLow: rcMul,
									pocketInsetHigh: rc.pocketInsetLow,
								},
						  }
						: {}),
				};
			}
			return {
				...props.glassDomain,
				insetLow: mullionInset,
				insetHigh: mullionInset,
				...(rc
					? { raycast: { ...rc, pocketInsetLow: rcMul, pocketInsetHigh: rcMul } }
					: {}),
			};
		}
		return props.glassDomain;
	}
	return glassDomainFromPiece(piece);
}

function effectiveGlassDomainForPiece(
	piece: SectionPiece,
	index: number
): SectionGlassDomain | null {
	if (piece.kind !== "glass") return null;
	return dynamicBayStates.value.get(index)?.domain ?? rawGlassDomainForPiece(piece, index);
}

function findOwningGlassIndexForBead(beadIndex: number, pieces: SectionPiece[]): number {
	const bead = pieces[beadIndex];
	if (bead?.path) {
		const byPath = pieces.findIndex((p) => p.kind === "glass" && p.path === bead.path);
		if (byPath >= 0) return byPath;
	}
	let bestIdx = -1;
	let bestDist = Infinity;
	const beadMid = ((bead?.start ?? 0) + (bead?.end ?? 0)) / 2;
	for (let i = 0; i < pieces.length; i++) {
		if (pieces[i].kind !== "glass") continue;
		const gMid = (pieces[i].start + pieces[i].end) / 2;
		const dist = Math.abs(gMid - beadMid);
		if (dist < bestDist) {
			bestDist = dist;
			bestIdx = i;
		}
	}
	return bestIdx;
}

function getHostOnlyTransform(
	index: number,
	piece: SectionPiece,
	outline: Outline | null
): SectionPieceTransform {
	if (ghostDrag.value) {
		const gd = ghostDrag.value;
		if (gd.index === index) return gd.currentTransform;
		if (mirrorSync.value && gd.twinIndex === index && gd.twinTransform)
			return gd.twinTransform;
	}
	const tag = pieceTags.value[index];
	const instKey = tag ? instancePieceKey(axis.value, tag, piece) : null;
	const legacyInstKey = instancePieceKey(axis.value, index, piece);
	const canonKey = canonicalPieceKey(piece);
	if (instKey && activeMap.value[instKey]) return activeMap.value[instKey];
	if (activeMap.value[legacyInstKey]) return activeMap.value[legacyInstKey];
	if (tag && activeMap.value[tag]) return activeMap.value[tag];
	const pathKey = pathForPiece(piece);
	if (pathKey && activeMap.value[pathKey]) return activeMap.value[pathKey];
	const cfg = piece.config_placement;
	if (cfg && cfg.source === "series_section_template" && piece.kind === "profile") {
		const tplRot =
			typeof cfg.rotation === "number"
				? ((((cfg.rotation % 360) + 360) % 360) as 0 | 90 | 180 | 270)
				: 0;
		const tplTransform: SectionPieceTransform = {
			offsetAlong: typeof cfg.offsetAlong === "number" ? cfg.offsetAlong : 0,
			offsetDepth: typeof cfg.offsetDepth === "number" ? cfg.offsetDepth : 0,
			rotation: tplRot,
			flipX: Boolean(cfg.flipX),
			flipY: Boolean(cfg.flipY),
		};
		if (typeof cfg.originU === "number") tplTransform.originU = cfg.originU;
		if (typeof cfg.originDepth === "number") tplTransform.originDepth = cfg.originDepth;
		return tplTransform;
	}
	if (activeMap.value[canonKey])
		return canonicalTransformForPiece(piece, activeMap.value[canonKey]);
	const base = defaultTransformForPiece(piece, outline);
	if (cfg && piece.role === "sash") {
		return {
			...base,
			rotation:
				typeof cfg.rotation === "number"
					? ((((cfg.rotation % 360) + 360) % 360) as 0 | 90 | 180 | 270)
					: base.rotation,
			flipX:
				typeof cfg.flipX === "boolean"
					? piece.mirrored
						? !cfg.flipX
						: cfg.flipX
					: base.flipX,
			flipY: typeof cfg.flipY === "boolean" ? cfg.flipY : base.flipY,
			offsetAlong:
				typeof cfg.offsetAlong === "number"
					? base.offsetAlong + cfg.offsetAlong
					: base.offsetAlong,
			offsetDepth:
				typeof cfg.offsetDepth === "number"
					? base.offsetDepth + cfg.offsetDepth
					: base.offsetDepth,
		};
	}
	return base;
}

const hostRaycaster = computed(() => {
	const pieces = section.value?.pieces ?? [];
	const { starts, ends } = compacted.value;
	const hostShapes: PlacedShape[] = [];
	for (let i = 0; i < pieces.length; i++) {
		const p = pieces[i];
		if (
			p.kind !== "profile" ||
			p.role === "bead" ||
			p.role === "glass_adaptor" ||
			p.role === "gasket"
		) {
			continue;
		}
		const outline = outlines.value[p.code] ?? null;
		const t = getHostOnlyTransform(i, p, outline);
		hostShapes.push(
			buildPlacedShape(i, p, starts[i] ?? p.start, ends[i] ?? p.end, outline, t, axis.value)
		);
	}
	return new PocketRaycaster(hostShapes);
});

const fullRaycaster = computed(() => new PocketRaycaster(nonGlassShapes.value));

const raycastHoverProbe = computed<PocketProbeResult | null>(() => {
	if (!raycastMode.value || !raycastHoverPoint.value) return null;
	return fullRaycaster.value.probeAt(raycastHoverPoint.value);
});

function hasManualOverrideForPiece(index: number, piece: SectionPiece): boolean {
	const tag = pieceTags.value[index];
	const instKey = tag ? instancePieceKey(axis.value, tag, piece) : null;
	const legacyInstKey = instancePieceKey(axis.value, index, piece);
	const pathKey = pathForPiece(piece);
	return Boolean(
		(instKey && activeMap.value[instKey]) ||
			activeMap.value[legacyInstKey] ||
			(tag && activeMap.value[tag]) ||
			(pathKey && activeMap.value[pathKey])
	);
}

function resolvedGlassFitForPiece(index: number, piece: SectionPiece): ResolvedGlassBounds | null {
	if (piece.kind !== "glass") return null;
	const domain = effectiveGlassDomainForPiece(piece, index);
	if (!domain) return null;
	if (!props.autoGlass && hasManualOverrideForPiece(index, piece)) return null;
	const { starts, ends } = compacted.value;
	const baseStart = starts[index] ?? piece.start;
	const baseEnd = ends[index] ?? piece.end;
	const meta = props.gasketMeta ?? paneGasketsFromPiece(piece);
	const ratio = meta ? { outerMm: meta.outer_mm, innerMm: meta.inner_mm } : null;
	return fitGlassInDomain(baseStart, baseEnd, piece.thickness, domain, ratio);
}

function getTransformForPiece(
	index: number,
	piece: SectionPiece,
	outline: Outline | null
): SectionPieceTransform {
	if (ghostDrag.value) {
		const gd = ghostDrag.value;
		if (gd.index === index) return gd.currentTransform;
		if (mirrorSync.value && gd.twinIndex === index && gd.twinTransform) {
			return gd.twinTransform;
		}
	}
	if (piece.kind === "glass") {
		const glassFit = resolvedGlassFitForPiece(index, piece);
		if (glassFit) {
			return {
				offsetAlong: 0,
				offsetDepth: glassFit.offsetDepth,
				rotation: 0,
				flipX: false,
				flipY: false,
			};
		}
	}
	const tag = pieceTags.value[index];
	const instKey = tag ? instancePieceKey(axis.value, tag, piece) : null;
	const legacyInstKey = instancePieceKey(axis.value, index, piece);
	const canonKey = canonicalPieceKey(piece);

	if (instKey && activeMap.value[instKey]) {
		return activeMap.value[instKey];
	}
	if (activeMap.value[legacyInstKey]) {
		return activeMap.value[legacyInstKey];
	}
	if (tag && activeMap.value[tag]) {
		return activeMap.value[tag];
	}
	const isBeadRole = piece.role === "bead" || piece.role === "glass_adaptor";
	if (!isBeadRole) {
		const pathKey = pathForPiece(piece);
		if (pathKey && activeMap.value[pathKey]) {
			return activeMap.value[pathKey];
		}
	}
	const cfg = piece.config_placement;
	if (isBeadRole && outline) {
		const pieces = section.value?.pieces ?? [];
		const glassIdx = findOwningGlassIndexForBead(index, pieces);
		const glassPiece = glassIdx >= 0 ? pieces[glassIdx] : null;
		const rawDom = glassPiece ? rawGlassDomainForPiece(glassPiece, glassIdx) : null;
		const hasCodeMatch = Boolean(
			cfg && cfg.source === "series_section_template" && cfg.matchedCode
		);
		// 1-sided clip-in frame beads (e.g. CS4807/CS4808/CS4809/E104161) all snap into the same saved frame/mullion groove.
		const hasSavedFrameBeadSeat = Boolean(
			piece.role === "bead" && cfg && cfg.source === "series_section_template"
		);
		if (rawDom?.raycast?.enabled && !hasCodeMatch && !hasSavedFrameBeadSeat && glassPiece) {
			const { starts, ends } = compacted.value;
			const beadSide =
				props.gasketMeta?.bead_side ??
				paneGasketsFromPiece(glassPiece)?.bead_side ??
				"inside";
			const autoBeadT = hostRaycaster.value.seatBeadAtDomainCorner(
				piece,
				index,
				starts[index] ?? piece.start,
				ends[index] ?? piece.end,
				starts[glassIdx] ?? glassPiece.start,
				ends[glassIdx] ?? glassPiece.end,
				outline,
				rawDom,
				beadSide
			);
			if (autoBeadT) return autoBeadT;
		}
	}
	if (cfg && cfg.source === "series_section_template" && piece.kind === "profile") {
		const tplRot =
			typeof cfg.rotation === "number"
				? ((((cfg.rotation % 360) + 360) % 360) as 0 | 90 | 180 | 270)
				: 0;
		const tplTransform: SectionPieceTransform = {
			offsetAlong: typeof cfg.offsetAlong === "number" ? cfg.offsetAlong : 0,
			offsetDepth: typeof cfg.offsetDepth === "number" ? cfg.offsetDepth : 0,
			rotation: tplRot,
			flipX: Boolean(cfg.flipX),
			flipY: Boolean(cfg.flipY),
		};
		if (typeof cfg.originU === "number") tplTransform.originU = cfg.originU;
		if (typeof cfg.originDepth === "number") tplTransform.originDepth = cfg.originDepth;
		return tplTransform;
	}
	if (!isBeadRole && activeMap.value[canonKey]) {
		return canonicalTransformForPiece(piece, activeMap.value[canonKey]);
	}
	const base = defaultTransformForPiece(piece, outline);
	if (
		cfg &&
		(piece.role === "bead" || piece.role === "glass_adaptor" || piece.role === "sash")
	) {
		return {
			...base,
			rotation:
				typeof cfg.rotation === "number"
					? ((((cfg.rotation % 360) + 360) % 360) as 0 | 90 | 180 | 270)
					: base.rotation,
			flipX:
				typeof cfg.flipX === "boolean"
					? piece.mirrored
						? !cfg.flipX
						: cfg.flipX
					: base.flipX,
			flipY: typeof cfg.flipY === "boolean" ? cfg.flipY : base.flipY,
			offsetAlong:
				typeof cfg.offsetAlong === "number"
					? base.offsetAlong + cfg.offsetAlong
					: base.offsetAlong,
			offsetDepth:
				typeof cfg.offsetDepth === "number"
					? base.offsetDepth + cfg.offsetDepth
					: base.offsetDepth,
		};
	}
	return base;
}

/** Persist automatic seating so the section workspace and Three renderer use
 * exactly the same sash and glass depth unless the user moves a piece. */
function seedDefaultSeats(cut: CrossSection) {
	const initialMap = activeMap.value;
	const generation = seq;
	const { starts, ends } = compactPieceSpans(cut.pieces, compactGlass.value, axis.value);
	const keys: string[] = [];
	const entries = cut.pieces.map((piece, index) => {
		const outline = piece.kind === "profile" ? outlines.value[piece.code] ?? null : null;
		const key = canonicalPieceKey(piece);
		const tag = pieceTags.value[index];
		const instKey = instancePieceKey(axis.value, tag ?? index, piece);
		keys.push(instKey);
		const hasTemplateSash =
			piece.role === "sash" &&
			Boolean(
				piece.config_placement &&
					(piece.config_placement.source === "series_section_template" ||
						piece.config_placement.offsetAlong ||
						piece.config_placement.offsetDepth)
			);
		const hasGlassDomain =
			piece.kind === "glass" && Boolean(effectiveGlassDomainForPiece(piece, index));
		const forceGlassSeat = Boolean(
			props.autoGlass && piece.kind === "glass" && !hasGlassDomain
		);
		const hasSavedSeat =
			Boolean(initialMap[key]) ||
			Boolean(initialMap[instKey]) ||
			Boolean(initialMap[instancePieceKey(axis.value, index, piece)]) ||
			Boolean(tag && initialMap[tag]);
		return {
			piece,
			outline,
			start: starts[index] ?? piece.start,
			end: ends[index] ?? piece.end,
			transform: getTransformForPiece(index, piece, outline),
			needsSeat:
				(forceGlassSeat || !hasSavedSeat) &&
				!hasTemplateSash &&
				!hasGlassDomain &&
				(piece.role === "sash" || piece.kind === "glass"),
		};
	});
	if (!entries.some((entry) => entry.needsSeat)) return;
	cancelSeating = startSectionSeating(
		entries,
		(transforms) => {
			// Never overwrite an edit or a new cut with a late background result.
			if (seq !== generation || activeMap.value !== initialMap || ghostDrag.value) return;
			const nextMap = { ...initialMap };
			entries.forEach((entry, index) => {
				const fitted = transforms[index];
				if (entry.needsSeat && fitted) {
					nextMap[keys[index]] = fitted;
					if (mirrorSync.value && entry.piece.role === "sash") {
						nextMap[canonicalPieceKey(entry.piece)] = canonicalTransformForPiece(
							entry.piece,
							fitted
						);
						nextMap[`${axis.value === "h" ? "v" : "h"}:${pieceTags.value[index]}`] =
							fitted;
					}
				}
			});
			if (!transforms.some(Boolean)) return;
			localSectionMap.value = nextMap;
			emit("update:section-map", nextMap);
		},
		() => {
			if (seq === generation && activeMap.value === initialMap) {
				toast.error(
					"Automatic fitting could not finish. The section is editable at its saved or default positions."
				);
			}
		}
	);
}

// Stop obsolete work immediately when a profile is edited or the design changes.
watch(
	() => [
		props.design.root,
		props.design.width,
		props.design.height,
		props.design.profiles,
		activeMap.value,
	],
	() => cancelSeating?.(),
	{ deep: true }
);

function commitTransformForPiece(
	index: number,
	piece: SectionPiece,
	nextTransform: SectionPieceTransform
) {
	const nextMap = { ...activeMap.value };
	const tag = pieceTags.value[index];
	const instKey = tag
		? instancePieceKey(axis.value, tag, piece)
		: instancePieceKey(axis.value, index, piece);
	const prevTransform = getTransformForPiece(index, piece, outlines.value[piece.code] ?? null);
	const deltaAlong = nextTransform.offsetAlong - prevTransform.offsetAlong;
	const deltaDepth = nextTransform.offsetDepth - prevTransform.offsetDepth;

	nextMap[instKey] = nextTransform;
	const legacyInstKey = instancePieceKey(axis.value, index, piece);
	if (legacyInstKey !== instKey) {
		nextMap[legacyInstKey] = nextTransform;
	}
	let twinNext: SectionPieceTransform | null = null;
	if (mirrorSync.value && tag) {
		const twinTag = getTwinTag(tag);
		if (twinTag) {
			const twinIdx = pieceTags.value.indexOf(twinTag);
			if (twinIdx >= 0) {
				const twinPiece = section.value?.pieces[twinIdx];
				if (twinPiece) {
					const twinOutline =
						twinPiece.kind === "profile"
							? outlines.value[twinPiece.code] ?? null
							: null;
					const twinPrev = getTransformForPiece(twinIdx, twinPiece, twinOutline);
					const twinInstKey = instancePieceKey(axis.value, twinTag, twinPiece);
					twinNext = {
						...twinPrev,
						...mirroredOrientation(piece, twinPiece, nextTransform),
						offsetAlong: Math.round((twinPrev.offsetAlong - deltaAlong) * 10) / 10,
						offsetDepth: Math.round((twinPrev.offsetDepth + deltaDepth) * 10) / 10,
					};
					nextMap[twinInstKey] = twinNext;
					const legacyTwinKey = instancePieceKey(axis.value, twinIdx, twinPiece);
					if (legacyTwinKey !== twinInstKey) {
						nextMap[legacyTwinKey] = twinNext;
					}
					const twinPath = pathForPiece(twinPiece);
					if (twinPath) {
						nextMap[twinPath] = twinNext;
					}
				}
			}
		}
	}

	const isBead = piece.role === "bead" || piece.role === "glass_adaptor";
	const piecePath = pathForPiece(piece);
	if (piecePath && !isBead) {
		nextMap[piecePath] = nextTransform;
	}

	if (!isBead) {
		const canonKey = canonicalPieceKey(piece);
		if (piece.kind !== "glass" || !tag) {
			nextMap[canonKey] = canonicalTransformForPiece(piece, nextTransform);
		}
	}

	if (mirrorSync.value && tag) {
		const otherAxis = axis.value === "h" ? "v" : "h";
		nextMap[`${otherAxis}:${tag}`] = nextTransform;
		const twinTag = getTwinTag(tag);
		if (twinTag && twinNext) nextMap[`${otherAxis}:${twinTag}`] = twinNext;
	}
	if (props.autoGlass && piece.kind === "profile") {
		for (const k of Object.keys(nextMap)) {
			if (
				k.startsWith("GLASS:") ||
				k.startsWith("glass:") ||
				/^[hv]:(OGL|OGR|MGL|MGR|OG_\d+|MG_\d+|GLASS:)/.test(k) ||
				/^[hv]:\d+:glass:/.test(k)
			) {
				delete nextMap[k];
			}
		}
	}
	localSectionMap.value = nextMap;
	emit("update:section-map", nextMap);
	if (props.autoGlass && piece.kind === "profile") {
		nextTick(() => {
			if (section.value) seedDefaultSeats(section.value);
		});
	}
}

function toggleMirrorSync() {
	mirrorSync.value = !mirrorSync.value;
}

const compacted = computed(() =>
	compactPieceSpans(section.value?.pieces ?? [], compactGlass.value, axis.value)
);

const grillDrag = ref<{
	path: string;
	startX: number;
	startY: number;
	scale: number;
	alongScale: number;
	config: Grill;
	along: number;
	depth: number;
	box: GrillBox;
	targets: GrillBox[];
	guides: GrillGuide[];
} | null>(null);
function selectGrill(path: string) {
	selectedIndex.value = null;
	emit("select", `GRILL:${path}`);
}
function startGrillDrag(
	e: PointerEvent,
	bar: { path: string; alongScale: number; x: number; y: number; w: number; h: number }
) {
	if (e.button !== 0) return;
	const node = getNode(props.design, bar.path);
	if (node.type === "split" || !node.grill) return;
	selectGrill(bar.path);
	grillDrag.value = {
		path: bar.path,
		startX: e.clientX,
		startY: e.clientY,
		scale: svgUnitsPerPixel(),
		alongScale: bar.alongScale,
		config: grillConfig(node.grill),
		along: 0,
		depth: 0,
		box: { x: bar.x, y: bar.y, w: bar.w, h: bar.h },
		targets: [
			...placedShapes.value.map((s) => ({
				x: s.bbox.minX,
				y: s.bbox.minY,
				w: s.bbox.width,
				h: s.bbox.height,
			})),
			...grillSections.value.filter((g) => g.path !== bar.path),
			{ x: bar.x, y: bar.y, w: bar.w, h: bar.h },
		],
		guides: [],
	};
	window.addEventListener("pointermove", moveGrillDrag);
	window.addEventListener("pointerup", endGrillDrag);
	window.addEventListener("pointercancel", cancelGrillDrag);
}
function moveGrillDrag(e: PointerEvent) {
	const d = grillDrag.value;
	if (!d) return;
	const dx = (e.clientX - d.startX) * d.scale,
		dy = (e.clientY - d.startY) * d.scale;
	const along = axis.value === "v" ? -dy : dx,
		depth = axis.value === "v" ? dx : dy;
	const result = e.altKey
		? { along, depth, guides: [] }
		: snapGrill(d.box, along, depth, d.targets, 8 * d.scale);
	d.along = result.along;
	d.depth = result.depth;
	d.guides = result.guides;
}
function cancelGrillDrag() {
	grillDrag.value = null;
	window.removeEventListener("pointermove", moveGrillDrag);
	window.removeEventListener("pointerup", endGrillDrag);
	window.removeEventListener("pointercancel", cancelGrillDrag);
}
function endGrillDrag() {
	const d = grillDrag.value;
	if (d && (Math.abs(d.along) > 0.01 || Math.abs(d.depth) > 0.01)) {
		const key = axis.value === "v" ? "shiftY" : "shiftX";
		emit(
			"update:grill",
			d.path,
			grillConfig({
				...d.config,
				offset: d.config.offset + d.depth,
				[key]: d.config[key] + d.along / d.alongScale,
			})
		);
	}
	cancelGrillDrag();
}
onUnmounted(cancelGrillDrag);

const grillSections = computed(() => {
	const cut = section.value;
	if (!cut) return [];
	const spans = compacted.value;
	const map = (position: number) => {
		if (!compactGlass.value) return position;
		// Only shorten the middle of an opening. End clearances remain real mm,
		// just like the profile outlines used as snapping targets.
		const anchors = cut.pieces.flatMap((p, i) => [
			{ from: p.start, to: spans.starts[i] },
			{ from: p.end, to: spans.ends[i] },
		]);
		const nearest = anchors.sort(
			(a, b) => Math.abs(a.from - position) - Math.abs(b.from - position)
		)[0];
		return nearest ? position + nearest.to - nearest.from : position;
	};
	const members = grillMembers(props.design);
	const paths = [...new Set(members.map((m) => m.path))];
	return paths.flatMap((path) => {
		const bars = members.filter((m) => m.path === path);
		const x = Math.min(...bars.map((b) => b.x)),
			y = Math.min(...bars.map((b) => b.y));
		const right = Math.max(...bars.map((b) => b.x + b.w)),
			top = Math.max(...bars.map((b) => b.y + b.h));
		if (cut.at < (axis.value === "h" ? y : x) || cut.at > (axis.value === "h" ? top : right))
			return [];
		const start = axis.value === "h" ? x : y,
			end = axis.value === "h" ? right : top;
		const node = getNode(props.design, path);
		if (node.type === "split" || !node.grill) return [];
		const config = grillConfig(node.grill);
		const count = axis.value === "h" ? config.vertical : config.horizontal;
		const shift = axis.value === "h" ? config.shiftX : config.shiftY;
		// Anchor before applying the user's translation, so a drag cannot change
		// anchors, resize the band or magnify a small snap into a large 3D offset.
		const mappedStart = map(start - shift),
			mappedEnd = map(end - shift);
		const w = Math.max(1, mappedEnd - mappedStart);
		// A schematic continuous grill band; internal stripes count the selected-axis bars.
		const marks = Array.from({ length: count }, (_, i) => (w * (i + 1)) / (count + 1));
		return [
			{
				path,
				x: mappedStart + shift,
				y: config.offset - config.depth / 2,
				w,
				h: config.depth,
				alongScale: 1,
				marks,
				count,
			},
		];
	});
});

interface DrawnPiece {
	index: number;
	piece: SectionPiece;
	baseStart: number;
	baseEnd: number;
	x: number;
	y: number;
	w: number;
	depth: number;
	outline: Outline | null;
	transform: string;
	pieceTransform: SectionPieceTransform;
	shape: PlacedShape;
	labelPos: { x: number; y: number };
	fontSize: number;
	maxTextWidth: number;
	moveable: boolean;
	selected: boolean;
	mirroredTwinSelected: boolean;
	ghost: boolean;
	colliding: boolean;
	colors: { stroke: string; fill: string; label: string };
}

const nonGlassShapes = computed<PlacedShape[]>(() => {
	const pieces = section.value?.pieces ?? [];
	const { starts, ends } = compacted.value;
	const out: PlacedShape[] = [];
	for (let i = 0; i < pieces.length; i++) {
		const piece = pieces[i];
		if (piece.kind === "glass") continue;
		const outline = piece.kind === "profile" ? outlines.value[piece.code] ?? null : null;
		const t = getTransformForPiece(i, piece, outline);
		out.push(
			buildPlacedShape(
				i,
				piece,
				starts[i] ?? piece.start,
				ends[i] ?? piece.end,
				outline,
				t,
				axis.value
			)
		);
	}
	return out;
});

const dynamicBayStates = computed<Map<number, DynamicDomainState>>(() => {
	const map = new Map<number, DynamicDomainState>();
	const pieces = section.value?.pieces ?? [];
	if (!pieces.length) return map;
	const { starts, ends } = compacted.value;
	const raycaster = new PocketRaycaster(nonGlassShapes.value);
	for (let i = 0; i < pieces.length; i++) {
		const piece = pieces[i];
		if (piece.kind !== "glass") continue;
		const rawDom = rawGlassDomainForPiece(piece, i);
		if (!rawDom) continue;
		map.set(
			i,
			raycaster.recalculateDynamicDomain(
				rawDom,
				starts[i] ?? piece.start,
				ends[i] ?? piece.end
			)
		);
	}
	return map;
});

const activeDynamicDomainList = computed<DynamicDomainState[]>(() => [
	...dynamicBayStates.value.values(),
]);

watch(
	activeDynamicDomainList,
	(states) => {
		const primary = states[0];
		if (!primary) {
			emit("update:measured-bw", null);
			return;
		}
		emit("update:measured-bw", {
			pocketBwMm: primary.pocketBwMm,
			effectiveBwMm: primary.effectiveBwMm,
			narrowedByBead: primary.narrowedByBead,
		});
	},
	{ immediate: true }
);

const gasketPlacements = computed<GasketPlacement[]>(() => {
	const pieces = section.value?.pieces ?? [];
	const out: GasketPlacement[] = [];
	for (let i = 0; i < pieces.length; i++) {
		const piece = pieces[i];
		if (piece.kind !== "glass") continue;
		const dyn = dynamicBayStates.value.get(i);
		const fit = resolvedGlassFitForPiece(i, piece);
		if (!dyn || !fit) continue;
		const meta = props.gasketMeta ?? paneGasketsFromPiece(piece);
		out.push(...PocketRaycaster.computeGasketPlacements(dyn, fit, meta));
	}
	return out;
});

const placedShapes = computed<PlacedShape[]>(() => {
	const pieces = section.value?.pieces ?? [];
	const { starts, ends } = compacted.value;
	const byIndex = new Map<number, PlacedShape>();
	for (const s of nonGlassShapes.value) byIndex.set(s.index, s);
	return pieces.map((piece, i) => {
		const pre = byIndex.get(i);
		if (pre) return pre;
		const t = getTransformForPiece(i, piece, null);
		const glassFit = resolvedGlassFitForPiece(i, piece);
		const s = glassFit ? glassFit.x : starts[i] ?? piece.start;
		const e = glassFit ? glassFit.x + glassFit.w : ends[i] ?? piece.end;
		return buildPlacedShape(i, piece, s, e, null, t, axis.value);
	});
});

function pathForPiece(piece: SectionPiece): string {
	if (piece.role === "frame") return "FRAME";
	const isBead = piece.role === "bead" || piece.role === "glass_adaptor";
	if (piece.path) {
		if (piece.kind === "glass") return `GLASS:${piece.path}`;
		if (isBead) return `BEAD:${piece.path}`;
		return piece.path;
	}
	if (piece.role === "mullion" || piece.role === "transom") return piece.panel;
	const g = layoutGeom(props.design);
	let sashCount = 0;
	let targetCell = null;
	for (const c of g.cells) {
		if (c.node.type === "sash") {
			sashCount++;
			const panelId = `F1-S${sashCount}`;
			if (piece.panel === panelId || piece.panel === `S${sashCount}`) {
				targetCell = c;
				break;
			}
		}
	}
	if (targetCell) {
		if (piece.kind === "glass") return `GLASS:${targetCell.path}`;
		if (isBead) return `BEAD:${targetCell.path}`;
		return targetCell.path;
	}

	// Fixed glass or fixed panel bead/gasket
	const mid = (piece.start + piece.end) / 2;
	const fixedCell =
		g.cells.find((c) => {
			if (axis.value === "h") {
				return mid >= c.x - 5 && mid <= c.x + c.w + 5;
			} else {
				return mid >= c.y - 5 && mid <= c.y + c.h + 5;
			}
		}) ?? g.cells[0];

	if (fixedCell) {
		if (piece.kind === "glass") return `GLASS:${fixedCell.path}`;
		if (isBead) return `BEAD:${fixedCell.path}`;
		return fixedCell.path;
	}
	return "";
}

function isPieceSelected(piece: SectionPiece, index: number): boolean {
	if (selectedIndex.value === index) return true;
	const sel = props.selectedPath;
	if (!sel) return false;
	if (sel.startsWith("BEAD:")) {
		if (piece.role !== "bead" && piece.role !== "glass_adaptor") return false;
		const cellPath = sel.replace(/^BEAD:/, "");
		const pPath = pathForPiece(piece);
		return pPath === sel || pPath === cellPath || pPath === `BEAD:${cellPath}`;
	}
	if (sel === "FRAME" || sel === "F1") {
		return piece.role === "frame";
	}
	if (/^[MT]\d+$/.test(sel)) {
		return (piece.role === "mullion" || piece.role === "transom") && piece.panel === sel;
	}
	if (sel.startsWith("GLASS:")) {
		if (piece.kind !== "glass") return false;
		const cellPath = sel.replace(/^GLASS:/, "");
		const pPath = pathForPiece(piece);
		return pPath === sel || pPath === cellPath;
	}
	const pPath = pathForPiece(piece);
	return pPath === sel;
}

watch(
	() => props.selectedPath,
	() => {
		if (props.selectedPath?.startsWith("GRILL:")) {
			selectedIndex.value = null;
			return;
		}
		if (selectedIndex.value !== null) {
			const pieces = section.value?.pieces ?? [];
			const piece = pieces[selectedIndex.value];
			if (piece && !isPieceSelected(piece, selectedIndex.value)) {
				selectedIndex.value = null;
			}
		}
	}
);

function onPieceClick(d: DrawnPiece) {
	if (raycastMode.value || suppressNextBgClick) return;
	selectedIndex.value = d.index;
	const path = pathForPiece(d.piece);
	if (path) emit("select", path);
}

const drawn = computed<DrawnPiece[]>(() => {
	const pieces = section.value?.pieces ?? [];
	const { starts, ends } = compacted.value;
	const shapes = placedShapes.value;
	const selPiece = selectedIndex.value !== null ? pieces[selectedIndex.value] : null;

	const rawDrawn = pieces.map((piece, i) => {
		const glassFit = resolvedGlassFitForPiece(i, piece);
		const baseStart = glassFit ? glassFit.x : starts[i] ?? piece.start;
		const baseEnd = glassFit ? glassFit.x + glassFit.w : ends[i] ?? piece.end;
		const outline = piece.kind === "profile" ? outlines.value[piece.code] ?? null : null;
		const t = getTransformForPiece(i, piece, outline);
		const shape = shapes[i];
		const rawW =
			outline?.width && outline.width > 0 ? outline.width : Math.max(4, baseEnd - baseStart);
		const rawD =
			piece.kind === "glass"
				? piece.thickness > 0
					? piece.thickness
					: GLASS_REF_THICKNESS_MM
				: outline?.depth && outline.depth > 0
				? outline.depth
				: DEFAULT_PROFILE_DEPTH_MM;

		const moveable = isPieceMoveable(piece) && !(props.autoGlass && piece.kind === "glass");
		const x = baseStart + t.offsetAlong;
		const y = piece.kind === "glass" ? -rawD / 2 + t.offsetDepth : t.offsetDepth;
		const w = piece.kind === "glass" ? Math.max(4, baseEnd - baseStart) : rawW;

		// Zoom changes the viewport, never the physical profile dimensions. The
		// visible outlines must match buildPlacedShape's snap targets and 3D.
		const s = 1;
		const effFlipX = Boolean(piece.mirrored) !== Boolean(t.flipX);
		const effFlipY = Boolean(t.flipY);
		const effRot = (((piece.mirrored ? -t.rotation : t.rotation) % 360) + 360) % 360;
		const cx = (rawW * s) / 2;
		const cy = (rawD * s) / 2;
		const sxScale = effFlipX ? -s : s;
		const syScale = effFlipY ? -s : s;

		let svgTransform = "";
		if (outline && outline.width > 0) {
			if (effRot === 0 && !effFlipY && t.flipX !== true) {
				svgTransform = effFlipX
					? `translate(${fmt(x + rawW * s)} ${fmt(y)}) scale(${fmt(-s)} ${fmt(s)})`
					: `translate(${fmt(x)} ${fmt(y)}) scale(${fmt(s)} ${fmt(s)})`;
			} else {
				svgTransform = `translate(${fmt(x + cx)} ${fmt(
					y + cy
				)}) rotate(${effRot}) scale(${fmt(sxScale)} ${fmt(syScale)}) translate(${fmt(
					-rawW / 2
				)} ${fmt(-rawD / 2)})`;
			}
		}

		const isGhost = Boolean(
			ghostDrag.value &&
				(ghostDrag.value.index === i ||
					(mirrorSync.value && ghostDrag.value.twinIndex === i))
		);
		const colliding =
			piece.kind === "profile" &&
			shapes.some(
				(other) =>
					other.index !== i &&
					!canPiecesOverlap(piece, other.piece) &&
					shapesCollide(shape, other)
			);

		const selected = isPieceSelected(piece, i);
		const tag = pieceTags.value[i];
		const selTag = selectedIndex.value !== null ? pieceTags.value[selectedIndex.value] : null;
		const mirroredTwinSelected = Boolean(
			!selected && mirrorSync.value && selTag && tag && getTwinTag(selTag) === tag
		);

		const colors = ROLE_COLORS[piece.role] ?? ROLE_COLORS.frame;
		const codeStr = piece.code || "";
		const availW = Math.max(4, (shape.bbox.width > 0 ? shape.bbox.width : rawW) - 3);
		const fontSize = Math.min(
			2.2,
			Math.max(1.3, availW / (Math.max(1, codeStr.length) * 0.65))
		);
		const maxTextWidth = Math.min(codeStr.length * 1.3, availW);
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
		};
	});

	// Ensure profile code labels inside/between profile chambers never overlap
	for (let i = 0; i < rawDrawn.length; i++) {
		for (let j = i + 1; j < rawDrawn.length; j++) {
			const a = rawDrawn[i];
			const b = rawDrawn[j];
			if (
				Math.abs(a.labelPos.x - b.labelPos.x) < 16 &&
				Math.abs(a.labelPos.y - b.labelPos.y) < 5
			) {
				a.labelPos.y -= 3.2;
				b.labelPos.y += 3.2;
			}
		}
	}

	return rawDrawn;
});

// Keep louver labels beyond every profile's depth envelope, in both views.
const louverLabelDepth = computed(
	() => Math.min(...placedShapes.value.map((s) => s.bbox.minY), 0) - 6
);

const selectedDrawn = computed<DrawnPiece | null>(() =>
	selectedIndex.value !== null ? drawn.value[selectedIndex.value] ?? null : null
);

const selectedVisualRotation = computed(() => {
	const d = selectedDrawn.value;
	if (!d) return 0;
	const rot = d.pieceTransform.rotation || 0;
	return (((d.piece.mirrored ? -rot : rot) % 360) + 360) % 360;
});

const cutLength = computed(
	() => section.value?.length ?? (axis.value === "h" ? props.design.width : props.design.height)
);
const effectiveCutLength = computed(() =>
	compactGlass.value ? compacted.value.totalSpan : cutLength.value
);
const bottomWallY = computed(() => {
	const pieces = section.value?.pieces ?? [];
	if (!pieces.length) return 20;

	// Baseline outer depth boundary is defined by the frame & bar profile depths
	const baseDepths: number[] = [];
	for (const p of pieces) {
		if (
			p.kind === "profile" &&
			(p.role === "frame" || p.role === "mullion" || p.role === "transom")
		) {
			const outline = outlines.value[p.code];
			const d =
				outline?.depth && outline.depth > 0 ? outline.depth : DEFAULT_PROFILE_DEPTH_MM;
			baseDepths.push(d);
		}
	}
	if (baseDepths.length) {
		return Math.round(Math.max(...baseDepths) * 10) / 10;
	}

	const shapes = placedShapes.value;
	if (shapes.length) {
		return Math.round(Math.max(...shapes.map((s) => s.bbox.maxY)) * 10) / 10;
	}

	return 40;
});

const GUIDE_COLORS: Record<"edge" | "center", string> = { edge: "#e11d48", center: "#c026d3" };

function shapeToRect(s: PlacedShape): Rect {
	return {
		id: `piece-${s.index}`,
		x: s.bbox.minX,
		y: s.bbox.minY,
		w: s.bbox.maxX - s.bbox.minX,
		h: s.bbox.maxY - s.bbox.minY,
	};
}

/**
 * Guide-only reference lines. They give you a centre guide even when no other piece is
 * centred, the glass plane (y = 0, where the stationary glass sits), and the walls.
 */
const datumRects = computed<Rect[]>(() => {
	const len = effectiveCutLength.value;
	const wall = bottomWallY.value;
	return [
		{ id: "datum-center-x", x: len / 2, y: 0, w: 0, h: wall, guide: "center" },
		{ id: "datum-glass-plane", x: 0, y: 0, w: len, h: 0, guide: "center" },
		{ id: "wall-left", x: 0, y: 0, w: 0, h: wall, guide: "edge" },
		{ id: "wall-right", x: len, y: 0, w: 0, h: wall, guide: "edge" },
		{ id: "wall-bottom", x: 0, y: wall, w: len, h: 0, guide: "edge" },
	];
});

function nonEmpty(res: SmartGuideResult): SmartGuideResult | null {
	return res.lines.length || res.gaps.length ? res : null;
}

/** Pre-computed geometry for the distance markers (both axes), so the template stays dumb. */
const guideGapShapes = computed(() => {
	const tick = 4 * guideScale.value;
	return (activeSmartGuides.value?.gaps ?? []).map((g, key) => {
		const horizontal = g.axis === "x";
		const at = (along: number, across: number) =>
			horizontal ? { x: along, y: across } : { x: across, y: along };
		const p1 = at(g.start, g.perpPos);
		const p2 = at(g.end, g.perpPos);
		const cap = (p: { x: number; y: number }) =>
			horizontal
				? { x1: p.x, y1: p.y - tick, x2: p.x, y2: p.y + tick }
				: { x1: p.x - tick, y1: p.y, x2: p.x + tick, y2: p.y };
		const label = fmt(g.gap);
		return {
			key,
			gap: g,
			label,
			line: { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y },
			ticks: [cap(p1), cap(p2)],
			pill: {
				...at((g.start + g.end) / 2, g.perpPos),
				w: Math.max(24, 8 + label.length * 6.2),
			},
		};
	});
});

const sceneBBox = computed(() => {
	const shapes = placedShapes.value;
	if (!shapes.length) {
		return { minX: -20, minY: -60, maxX: 300, maxY: 60, width: 320, height: 120 };
	}
	const allRings = shapes.flatMap((s) => s.rings);
	const b = computeBBox(allRings);
	const padX = compactGlass.value ? 16 : 28;
	const minX = Math.min(b.minX - padX, -10);
	const maxX = Math.max(b.maxX + padX, effectiveCutLength.value + 10);
	const labelPadding =
		axis.value === "v" && shapes.some((s) => s.piece.kind === "louver") ? 60 : 20;
	const minY = Math.min(b.minY - labelPadding, -50, ...grillSections.value.map((g) => g.y - 18));
	const maxY =
		Math.max(b.maxY, bottomWallY.value, ...grillSections.value.map((g) => g.y + g.h)) + 12;
	return {
		minX,
		minY,
		maxX,
		maxY,
		width: Math.max(100, maxX - minX),
		height: Math.max(80, maxY - minY),
	};
});

/** Overall assembly section dimensions (Width × Depth in mm), matching CAD section callout. */
const sectionExtentLabel = computed(() => {
	const profileShapes = placedShapes.value.filter((s) => s.piece.kind === "profile");
	if (!profileShapes.length) return "0 + 0 mm";
	const firstJoint = profileShapes.filter((s) => !s.piece.mirrored);
	const target = firstJoint.length ? firstJoint : profileShapes;
	const b = computeBBox(target.flatMap((s) => s.rings));
	return `${Math.round(b.width)} + ${Math.round(b.height)} mm`;
});

/** Computed viewBox rectangle matching container aspect ratio for 1:1 coordinate projection. */
const viewBoxRect = computed(() => {
	const scene = sceneBBox.value;
	// A–A runs bottom to top: (along, depth) -> (depth, -along).
	const b =
		axis.value === "v"
			? {
					minX: scene.minY,
					maxX: scene.maxY,
					minY: -scene.maxX,
					maxY: -scene.minX,
					width: scene.height,
					height: scene.width,
			  }
			: scene;
	const baseW = b.width / sectionZoom.value;
	const baseH = b.height / sectionZoom.value;
	const cw = Math.max(1, containerSize.value.width);
	const ch = Math.max(1, containerSize.value.height);
	const aspect = cw / ch;

	let w = baseW;
	let h = baseH;
	if (baseW / baseH > aspect) {
		h = baseW / aspect;
	} else {
		w = baseH * aspect;
	}

	const cx = (b.minX + b.maxX) / 2 - sectionPan.value.x;
	const cy = (b.minY + b.maxY) / 2 - sectionPan.value.y;
	return {
		x: cx - w / 2,
		y: cy - h / 2,
		w,
		h,
	};
});

const viewBoxStr = computed(() => {
	const vb = viewBoxRect.value;
	return `${fmt(vb.x)} ${fmt(vb.y)} ${fmt(vb.w)} ${fmt(vb.h)}`;
});

/**
 * Floating control toolbar anchor style positioned directly on top of the selected profile.
 * Clamped safely inside the viewport so it never clips off the edges.
 */
const selectedFloatingStyle = computed<Record<string, string>>(() => {
	const d = selectedDrawn.value;
	if (!d) return { left: "50%", top: "12%", transform: "translate(-50%, -100%)" };
	const vb = viewBoxRect.value;
	const anchorX = d.shape.bbox.minX + d.shape.bbox.width / 2;
	const anchorY = d.shape.bbox.minY - 7;
	const screenX = axis.value === "v" ? anchorY : anchorX;
	const screenY = axis.value === "v" ? -anchorX : anchorY;
	const rawLeftPct = ((screenX - vb.x) / vb.w) * 100;
	const rawTopPct = ((screenY - vb.y) / vb.h) * 100;
	const leftPct = Math.min(82, Math.max(18, rawLeftPct));
	const topPct = Math.min(88, Math.max(11, rawTopPct));
	return {
		left: `${fmt(leftPct)}%`,
		top: `${fmt(topPct)}%`,
		transform: "translate(-50%, -100%)",
	};
});

const missing = computed(() => {
	const codes = new Set(
		drawn.value
			.filter((d) => d.piece.kind === "profile" && !d.outline)
			.map((d) => d.piece.code)
	);
	return [...codes].sort();
});

const title = computed(() =>
	axis.value === "h" ? "Section B–B (Top / Horizontal Cut)" : "Section A–A (Side / Vertical Cut)"
);
const issues = computed(() => section.value?.issues ?? []);

function svgUnitsPerPixel(): number {
	updateContainerSize();
	const el = svgEl.value;
	const vb = viewBoxRect.value;
	if (!el) return vb.w / 640;
	const r = el.getBoundingClientRect();
	if (!r.width || !r.height) return 0.5;
	return Math.max(vb.w / r.width, vb.h / r.height);
}

function svgEventToSectionPoint(e: MouseEvent | PointerEvent): Point | null {
	updateContainerSize();
	const el = svgEl.value;
	if (!el) return null;
	const r = el.getBoundingClientRect();
	const rw = r.width || containerSize.value.width;
	const rh = r.height || containerSize.value.height;
	if (!(rw > 0 && rh > 0)) return null;
	const vb = viewBoxRect.value;
	const scale = Math.min(rw / vb.w, rh / vb.h);
	const padX = (rw - vb.w * scale) / 2;
	const padY = (rh - vb.h * scale) / 2;
	const vx = vb.x + (e.clientX - r.left - padX) / scale;
	const vy = vb.y + (e.clientY - r.top - padY) / scale;
	return axis.value === "v" ? { x: -vy, y: vx } : { x: vx, y: vy };
}

function domainForBayIndex(
	base: SectionGlassDomain,
	bayIdx: number,
	bayCount: number
): SectionGlassDomain {
	if (bayCount <= 1) return base;
	const mullionInset = base.insetMullion != null ? base.insetMullion : base.insetHigh;
	const rc = base.raycast;
	const rcMul =
		rc?.pocketInsetMullion != null ? rc.pocketInsetMullion : rc?.pocketInsetHigh ?? 0;
	if (bayIdx === 0) {
		return {
			...base,
			insetLow: base.insetLow,
			insetHigh: mullionInset,
			...(rc ? { raycast: { ...rc, pocketInsetHigh: rcMul } } : {}),
		};
	}
	if (bayIdx === bayCount - 1) {
		return {
			...base,
			insetLow: mullionInset,
			insetHigh: base.insetLow,
			...(rc
				? { raycast: { ...rc, pocketInsetLow: rcMul, pocketInsetHigh: rc.pocketInsetLow } }
				: {}),
		};
	}
	return {
		...base,
		insetLow: mullionInset,
		insetHigh: mullionInset,
		...(rc ? { raycast: { ...rc, pocketInsetLow: rcMul, pocketInsetHigh: rcMul } } : {}),
	};
}

function autoSeatBeadsForDomain(domain: SectionGlassDomain) {
	if (!domain.raycast?.enabled) return;
	const pieces = section.value?.pieces ?? [];
	const hasSashAdaptor = pieces.some((p) => p.kind === "profile" && p.role === "glass_adaptor");
	if (!hasSashAdaptor) return;
	const { starts, ends } = compacted.value;
	const glassIndices = pieces.reduce<number[]>((acc, p, idx) => {
		if (p.kind === "glass") acc.push(idx);
		return acc;
	}, []);
	const nextMap = { ...activeMap.value };
	for (const k of Object.keys(nextMap)) {
		if (
			k.startsWith("BEAD:") ||
			k.startsWith("glass_adaptor:") ||
			/^[hv]:(OBL|OBR|MBL|MBR|OB_\d+|MB_\d+)$/.test(k) ||
			/^[hv]:\d+:glass_adaptor:/.test(k)
		) {
			delete nextMap[k];
		}
	}
	let changed = false;
	for (let i = 0; i < pieces.length; i++) {
		const p = pieces[i];
		if (p.kind !== "profile" || p.role !== "glass_adaptor") continue;
		const outline = outlines.value[p.code] ?? null;
		const glassIdx = findOwningGlassIndexForBead(i, pieces);
		if (glassIdx < 0) continue;
		const gp = pieces[glassIdx];
		const bayIdx = glassIndices.indexOf(glassIdx);
		const bayDomain = domainForBayIndex(domain, Math.max(0, bayIdx), glassIndices.length);
		const beadSide =
			props.gasketMeta?.bead_side ?? paneGasketsFromPiece(gp)?.bead_side ?? "inside";
		const seated = hostRaycaster.value.seatBeadAtDomainCorner(
			p,
			i,
			starts[i] ?? p.start,
			ends[i] ?? p.end,
			starts[glassIdx] ?? gp.start,
			ends[glassIdx] ?? gp.end,
			outline,
			bayDomain,
			beadSide
		);
		if (!seated) continue;
		const tag = pieceTags.value[i];
		const instKey = tag
			? instancePieceKey(axis.value, tag, p)
			: instancePieceKey(axis.value, i, p);
		nextMap[instKey] = seated;
		nextMap[instancePieceKey(axis.value, i, p)] = seated;
		if (mirrorSync.value && tag) {
			const otherAxis = axis.value === "h" ? "v" : "h";
			nextMap[`${otherAxis}:${tag}`] = seated;
		}
		changed = true;
	}
	if (changed) {
		localSectionMap.value = nextMap;
		emit("update:section-map", nextMap);
	}
}

function clearBeadOverridesForRaycast() {
	const nextMap = { ...activeMap.value };
	for (const k of Object.keys(nextMap)) {
		if (
			k.startsWith("BEAD:") ||
			k.startsWith("bead:") ||
			k.startsWith("glass_adaptor:") ||
			/^[hv]:(OBL|OBR|MBL|MBR|OB_\d+|MB_\d+)$/.test(k) ||
			/^[hv]:\d+:(bead|glass_adaptor):/.test(k)
		) {
			delete nextMap[k];
		}
	}
	let changed = false;
	for (const k of Object.keys(nextMap)) {
		if (
			k.startsWith("BEAD:") ||
			k.startsWith("bead:") ||
			k.startsWith("glass_adaptor:") ||
			/^[hv]:(OBL|OBR|MBL|MBR|OB_\d+|MB_\d+)$/.test(k) ||
			/^[hv]:\d+:(bead|glass_adaptor):/.test(k)
		) {
			delete nextMap[k];
			changed = true;
		}
	}
	if (changed) {
		localSectionMap.value = nextMap;
		emit("update:section-map", nextMap);
	}
}

function commitRaycastProbe(probe: PocketProbeResult) {
	const pieces = section.value?.pieces ?? [];
	const { starts, ends } = compacted.value;
	const probeMidX = (probe.leftWallX + probe.rightWallX) / 2;
	const glassIndices: number[] = [];
	let targetGlassIdx = -1;
	let bestDist = Infinity;
	for (let i = 0; i < pieces.length; i++) {
		if (pieces[i].kind !== "glass") continue;
		glassIndices.push(i);
		const gMid = ((starts[i] ?? pieces[i].start) + (ends[i] ?? pieces[i].end)) / 2;
		const dist = Math.abs(gMid - probeMidX);
		if (dist < bestDist) {
			bestDist = dist;
			targetGlassIdx = i;
		}
	}
	if (targetGlassIdx < 0) return;
	const baseStart = starts[targetGlassIdx] ?? pieces[targetGlassIdx].start;
	const baseEnd = ends[targetGlassIdx] ?? pieces[targetGlassIdx].end;
	const nextDomain = PocketRaycaster.toGlassDomain(probe, baseStart, baseEnd);
	// On the right bay of a mullioned template, jamb is on the high side and mullion is on the low side.
	const bayIdx = glassIndices.indexOf(targetGlassIdx);
	if (glassIndices.length > 1 && bayIdx === glassIndices.length - 1 && nextDomain.raycast) {
		const jambInset = nextDomain.insetHigh;
		const mullionInset = nextDomain.insetLow;
		nextDomain.insetLow = jambInset;
		nextDomain.insetHigh = mullionInset;
		nextDomain.insetMullion = mullionInset;
		const jambPocket = nextDomain.raycast.pocketInsetHigh;
		const mulPocket = nextDomain.raycast.pocketInsetLow;
		nextDomain.raycast.pocketInsetLow = jambPocket;
		nextDomain.raycast.pocketInsetHigh = mulPocket;
		nextDomain.raycast.pocketInsetMullion = mulPocket;
	}
	showGlassDomainOverlay.value = true;
	suppressNextBgClick = true;
	setTimeout(() => {
		suppressNextBgClick = false;
	}, 0);
	setRaycastMode(false);
	// When raycasting an empty sash/frame pocket (not an already-positioned bead wall), auto-seat every bead into its pocket corners.
	if (!probe.hitBeadWall) {
		autoSeatBeadsForDomain(nextDomain);
	}
	emit("update:glass-domain", nextDomain);
	lastSnapNotice.value = `Pocket locked (${probe.pocketWidthMm} mm) · beads & anchors fixed`;
}

function onPiecePointerDown(e: PointerEvent, d: DrawnPiece) {
	if (raycastMode.value && !e.shiftKey && !shiftHeld.value && e.button === 0) {
		onCanvasPointerDown(e);
		return;
	}
	// If Shift or middle mouse is held, pan the workspace instead of dragging the profile
	if (e.shiftKey || shiftHeld.value || e.button === 1) {
		onCanvasPointerDown(e);
		return;
	}
	if (e.button !== 0 && e.button !== undefined) return;
	e.stopPropagation();
	e.preventDefault();
	selectedIndex.value = d.index;
	lastSnapNotice.value = "";
	activeSmartGuides.value = null;
	const path = pathForPiece(d.piece);
	if (path) emit("select", path);
	if (!d.moveable) return;

	// All profiles, mullions, transoms, sashes, and beads are draggable
	const orig = getTransformForPiece(d.index, d.piece, d.outline);
	const tag = pieceTags.value[d.index];
	const twinTag = mirrorSync.value && tag ? getTwinTag(tag) : null;
	const twinIdx = twinTag ? pieceTags.value.indexOf(twinTag) : -1;
	const twinPiece = twinIdx >= 0 ? section.value?.pieces[twinIdx] : null;
	const twinOutline =
		twinPiece && twinPiece.kind === "profile" ? outlines.value[twinPiece.code] ?? null : null;
	const twinOrig = twinPiece ? getTransformForPiece(twinIdx, twinPiece, twinOutline) : null;

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
	};
	window.addEventListener("pointermove", onPiecePointerMove);
	window.addEventListener("pointerup", endPieceDrag);
	window.addEventListener("pointercancel", endPieceDrag);
}

function clampTransformToBoundary(
	piece: SectionPiece,
	baseStart: number,
	baseEnd: number,
	t: SectionPieceTransform,
	outline?: Outline | null
): SectionPieceTransform {
	const len = effectiveCutLength.value;
	const minAlong = -baseStart;
	const maxAlong = Math.max(minAlong, len - baseEnd);
	const clampedAlong = Math.min(maxAlong, Math.max(minAlong, t.offsetAlong));
	let candidate: SectionPieceTransform = {
		...t,
		offsetAlong: Math.round(clampedAlong * 10) / 10,
	};

	// Depth is free: sash rebates can legitimately extend past the frame depth.

	return candidate;
}

function onPiecePointerMove(e: PointerEvent) {
	const gd = ghostDrag.value;
	if (!gd) return;
	if (e === lastMoveEvent) return; // bound on both <g> and window; handle each native event once
	lastMoveEvent = e;

	const scaleMm = svgUnitsPerPixel();
	guideScale.value = scaleMm;
	const screenDx = (e.clientX - gd.startClientX) * scaleMm;
	const screenDy = (e.clientY - gd.startClientY) * scaleMm;
	const dxMm = axis.value === "v" ? -screenDy : screenDx;
	const dyMm = axis.value === "v" ? screenDx : screenDy;
	const candidate: SectionPieceTransform = {
		...gd.origTransform,
		offsetAlong: Math.round((gd.origTransform.offsetAlong + dxMm) * 10) / 10,
		offsetDepth: Math.round((gd.origTransform.offsetDepth + dyMm) * 10) / 10,
	};

	gd.moved = gd.moved || e.clientX !== gd.startClientX || e.clientY !== gd.startClientY;
	gd.snapDisabled = e.altKey || e.ctrlKey;

	const cur = drawn.value[gd.index];
	if (!cur) {
		gd.currentTransform = candidate;
		activeSmartGuides.value = null;
	} else {
		const clamp = (t: SectionPieceTransform) =>
			clampTransformToBoundary(gd.piece, cur.baseStart, cur.baseEnd, t, cur.outline);
		const build = (t: SectionPieceTransform) =>
			buildPlacedShape(gd.index, gd.piece, cur.baseStart, cur.baseEnd, cur.outline, t);

		const obstacles = placedShapes.value.filter(
			(obs) =>
				obs.index !== gd.index &&
				(gd.twinIndex === undefined || obs.index !== gd.twinIndex)
		);
		const targets: Rect[] = [...obstacles.map(shapeToRect), ...datumRects.value];

		const clamped = clamp(candidate);
		const movingShape = build(clamped);
		let finalT = clamped;

		if (!(e.altKey || e.ctrlKey)) {
			const joined = magneticAutoJoin(
				movingShape,
				clamped,
				gd.piece,
				obstacles,
				Math.max(0.01, 6 * scaleMm)
			);
			if (joined) {
				finalT = clamp(joined);
			} else {
				const snap = computeSmartGuides(shapeToRect(movingShape), targets, {
					scaleMmPerPixel: scaleMm,
					tolerancePx: 6,
				});
				if (snap.deltaX !== 0 || snap.deltaY !== 0) {
					finalT = clamp({
						...clamped,
						offsetAlong: Math.round((clamped.offsetAlong + snap.deltaX) * 10) / 10,
						offsetDepth: Math.round((clamped.offsetDepth + snap.deltaY) * 10) / 10,
					});
				}
			}
		}

		gd.currentTransform = finalT;
		const finalShape = finalT === clamped ? movingShape : build(finalT);
		const measured = measureGuides(shapeToRect(finalShape), targets);
		measured.lines = [...profileContactGuides(finalShape, obstacles), ...measured.lines].slice(
			0,
			8
		);
		activeSmartGuides.value = nonEmpty(measured);
	}

	// Update twin ghost transform in real-time
	if (gd.origTwinTransform && gd.twinIndex !== undefined) {
		const deltaAlong = gd.currentTransform.offsetAlong - gd.origTransform.offsetAlong;
		const deltaDepth = gd.currentTransform.offsetDepth - gd.origTransform.offsetDepth;
		gd.twinTransform = {
			...gd.origTwinTransform,
			...mirroredOrientation(gd.piece, gd.twinPiece!, gd.currentTransform),
			offsetAlong: Math.round((gd.origTwinTransform.offsetAlong - deltaAlong) * 10) / 10,
			offsetDepth: Math.round((gd.origTwinTransform.offsetDepth + deltaDepth) * 10) / 10,
		};
	}
}

function endPieceDrag() {
	const gd = ghostDrag.value;
	if (!gd) return;
	window.removeEventListener("pointermove", onPiecePointerMove);
	window.removeEventListener("pointerup", endPieceDrag);
	window.removeEventListener("pointercancel", endPieceDrag);

	const idx = gd.index;
	const piece = gd.piece;
	const desired = gd.currentTransform;
	const twinIdx = gd.twinIndex;
	ghostDrag.value = null;
	activeSmartGuides.value = null;

	if (!gd.moved) return;
	const d = drawn.value[idx];
	if (!d) return;

	const obstacles = placedShapes.value.filter(
		(shape) => shape.index !== idx && shape.index !== twinIdx
	);
	// Keep the visible snap on release. Only resolve actual collisions, with
	// magnetic snapping disabled; Alt/Ctrl preserves the exact free placement.
	const resolved = gd.snapDisabled
		? { transform: desired, resolvedCollision: false }
		: resolvePuzzleDrop(idx, piece, d.baseStart, d.baseEnd, d.outline, desired, obstacles, 0);
	const finalClamped = clampTransformToBoundary(
		piece,
		d.baseStart,
		d.baseEnd,
		resolved.transform,
		d.outline
	);
	if (resolved.resolvedCollision)
		lastSnapNotice.value = "Moved clear of overlapping profile walls";
	commitTransformForPiece(idx, piece, finalClamped);
}

/**
 * Start dragging/panning the cross-section workspace.
 * Works when dragging empty canvas background OR holding Shift + dragging anywhere (or middle click).
 */
function onCanvasPointerDown(e: PointerEvent) {
	if (ghostDrag.value) return;
	if (raycastMode.value && !e.shiftKey && !shiftHeld.value && e.button === 0) {
		const pt = svgEventToSectionPoint(e);
		if (pt) raycastHoverPoint.value = pt;
		const probe = pt ? fullRaycaster.value.probeAt(pt) : raycastHoverProbe.value;
		if (probe) {
			e.stopPropagation();
			e.preventDefault();
			commitRaycastProbe(probe);
			return;
		}
	}
	if (e.shiftKey === false && e.button === 0) shiftHeld.value = false;
	if (e.button !== 0 && e.button !== 1 && e.button !== undefined) return;
	e.preventDefault();
	panDrag = {
		startX: e.clientX,
		startY: e.clientY,
		origX: sectionPan.value.x,
		origY: sectionPan.value.y,
		pointerId: e.pointerId,
		moved: false,
	};
	isPanning.value = true;
	if (svgEl.value?.setPointerCapture && e.pointerId !== undefined) {
		try {
			svgEl.value.setPointerCapture(e.pointerId);
		} catch {
			// Ignore synthetic pointer events in tests
		}
	}
	window.addEventListener("pointermove", onCanvasPointerMove);
	window.addEventListener("pointerup", endWorkspacePan);
	window.addEventListener("pointercancel", endWorkspacePan);
}

function onCanvasPointerMove(e: PointerEvent) {
	if (raycastMode.value && !panDrag) {
		raycastHoverPoint.value = svgEventToSectionPoint(e);
	}
	if (!panDrag) return;
	const scaleMm = svgUnitsPerPixel();
	const dxMm = (e.clientX - panDrag.startX) * scaleMm;
	const dyMm = (e.clientY - panDrag.startY) * scaleMm;
	if (Math.abs(e.clientX - panDrag.startX) > 2 || Math.abs(e.clientY - panDrag.startY) > 2) {
		panDrag.moved = true;
	}
	sectionPan.value = {
		x: clampPan(panDrag.origX + dxMm),
		y: clampPan(panDrag.origY + dyMm),
	};
}

function endWorkspacePan() {
	if (!panDrag) return;
	const { pointerId, moved } = panDrag;
	panDrag = null;
	isPanning.value = false;
	if (moved) {
		suppressNextBgClick = true;
		setTimeout(() => {
			suppressNextBgClick = false;
		}, 0);
	}
	window.removeEventListener("pointermove", onCanvasPointerMove);
	window.removeEventListener("pointerup", endWorkspacePan);
	window.removeEventListener("pointercancel", endWorkspacePan);
	if (
		svgEl.value?.releasePointerCapture &&
		pointerId !== undefined &&
		svgEl.value.hasPointerCapture?.(pointerId)
	) {
		try {
			svgEl.value.releasePointerCapture(pointerId);
		} catch {
			// Ignore synthetic pointer events
		}
	}
}

function onBackgroundClick() {
	if (suppressNextBgClick) {
		suppressNextBgClick = false;
		return;
	}
	selectedIndex.value = null;
	emit("select", "");
}

function rotateSelected(deltaDeg: number) {
	const d = selectedDrawn.value;
	if (!d || d.piece.kind !== "profile") return;
	const cur = d.pieceTransform;
	// Mirrored pieces are rendered with effRot = -rotation in SVG.
	// Inverting deltaDeg for mirrored pieces ensures clicking rotate clockwise (+90°)
	// visually rotates the mirrored profile clockwise (+90°) rather than counter-clockwise.
	const effectiveDelta = d.piece.mirrored ? -deltaDeg : deltaDeg;
	const nextRot = (((cur.rotation + effectiveDelta) % 360) + 360) % 360;
	const next: SectionPieceTransform = { ...cur, rotation: nextRot };
	const tag = pieceTags.value[d.index];
	const twinTag = mirrorSync.value && tag ? getTwinTag(tag) : null;
	const twinIdx = twinTag ? pieceTags.value.indexOf(twinTag) : -1;
	const obstacles = placedShapes.value.filter(
		(obs) => obs.index !== d.index && obs.index !== twinIdx
	);
	const resolved = resolvePuzzleDrop(
		d.index,
		d.piece,
		d.baseStart,
		d.baseEnd,
		d.outline,
		next,
		obstacles
	);
	commitTransformForPiece(d.index, d.piece, resolved.transform);
}

function flipSelected(dir: "x" | "y") {
	const d = selectedDrawn.value;
	if (!d || d.piece.kind !== "profile") return;
	const cur = d.pieceTransform;
	const next: SectionPieceTransform = {
		...cur,
		flipX: dir === "x" ? !cur.flipX : cur.flipX,
		flipY: dir === "y" ? !cur.flipY : cur.flipY,
	};
	commitTransformForPiece(d.index, d.piece, next);
}

const savingOrientation = ref(false);

async function saveSelectedAsDefaultOrientation() {
	const d = selectedDrawn.value;
	if (!d || d.piece.kind !== "profile") return;
	const code = d.piece.code;
	// pieceTransform is already expressed relative to the unmirrored profile outline for both
	// mirrored (MFR/MSR/MBR) and unmirrored (OFL/OSL/OBL/M1/T1) instances, because
	// rotateSelected/commitTransformForPiece store canonical rotation and flips in unmirrored space.
	const deltaRot = (((d.pieceTransform.rotation || 0) % 360) + 360) % 360;
	const deltaFlipX = Boolean(d.pieceTransform.flipX);
	const deltaFlipY = Boolean(d.pieceTransform.flipY);

	savingOrientation.value = true;
	try {
		const res = await setProfileOrientation(code, {
			delta: deltaRot,
			delta_flip_x: deltaFlipX,
			delta_flip_y: deltaFlipY,
		});
		const nextMap = { ...activeMap.value };
		const resetEntryOrientation = (key: string) => {
			const existing = nextMap[key];
			if (!existing) return;
			const cleaned: SectionPieceTransform = {
				offsetAlong: existing.offsetAlong ?? 0,
				offsetDepth: existing.offsetDepth ?? 0,
				rotation: 0,
				flipX: false,
				flipY: false,
			};
			// Preserve explicit outer-corner datum (0, 0); drop old center datum so it re-centers on swapped WxD.
			if (existing.originU === 0 && existing.originDepth === 0) {
				cleaned.originU = 0;
				cleaned.originDepth = 0;
			}
			nextMap[key] = cleaned;
		};

		const pieces = section.value?.pieces ?? [];
		for (let i = 0; i < pieces.length; i++) {
			const p = pieces[i];
			if (p.kind !== "profile" || p.code !== code) continue;
			if (!mirrorSync.value && i !== d.index) continue;
			const tag = pieceTags.value[i];
			resetEntryOrientation(instancePieceKey(axis.value, tag ?? i, p));
			resetEntryOrientation(instancePieceKey(axis.value, i, p));
			if (tag) resetEntryOrientation(tag);
			const pPath = pathForPiece(p);
			if (pPath) resetEntryOrientation(pPath);
			if (mirrorSync.value) {
				const otherAxis = axis.value === "h" ? "v" : "h";
				resetEntryOrientation(instancePieceKey(otherAxis, tag ?? i, p));
				resetEntryOrientation(instancePieceKey(otherAxis, i, p));
			}
		}

		if (mirrorSync.value) {
			const canon = canonicalPieceKey(d.piece);
			resetEntryOrientation(canon);
			for (const k in nextMap) {
				if (k.startsWith(canon) || k.endsWith(`:${canon}`) || k.endsWith(canon)) {
					resetEntryOrientation(k);
				}
			}
		}

		localSectionMap.value = nextMap;
		emit("update:section-map", nextMap);
		emit("profile-orientation-updated", code);
		const flipLabels = [
			res.section_flip_x ? "flipped H" : "",
			res.section_flip_y ? "flipped V" : "",
		]
			.filter(Boolean)
			.join(", ");
		const desc = flipLabels
			? `${res.section_rotation}° (${flipLabels})`
			: `${res.section_rotation}°`;
		toast.success(`Default orientation updated to ${desc} for ${code}`);
		await load();
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Could not set default orientation");
	} finally {
		savingOrientation.value = false;
	}
}

function selectedDatum(): "center" | "outer" | null {
	const d = selectedDrawn.value;
	if (!d || d.piece.kind !== "profile") return null;
	const w = d.outline?.width || d.shape.bbox.width;
	const depth = d.outline?.depth || d.depth;
	const u = d.pieceTransform.originU;
	const dep = d.pieceTransform.originDepth;
	if (u == null || dep == null) return "center";
	if (Math.abs(u) < 0.5 && Math.abs(dep) < 0.5) return "outer";
	if (Math.abs(u - w / 2) < 0.5 && Math.abs(dep - depth / 2) < 0.5) return "center";
	return null;
}

function setSelectedOrigin(kind: "center" | "outer") {
	const d = selectedDrawn.value;
	if (!d || d.piece.kind !== "profile") return;
	const w = d.outline?.width || d.shape.bbox.width;
	const depth = d.outline?.depth || d.depth;
	commitTransformForPiece(d.index, d.piece, {
		...d.pieceTransform,
		originU: kind === "center" ? w / 2 : 0,
		originDepth: kind === "center" ? depth / 2 : 0,
	});
	lastSnapNotice.value =
		kind === "center"
			? "Profile datum set to geometric centre"
			: "Profile datum set to outer corner";
}

function resetSelectedPiece() {
	const d = selectedDrawn.value;
	if (!d || d.piece.kind !== "profile") return;
	commitTransformForPiece(d.index, d.piece, defaultTransformForPiece(d.piece, d.outline));
	lastSnapNotice.value = "Reset profile to default datum";
}

async function resetAllPieces() {
	cancelSeating?.();
	localSectionMap.value = {};
	emit("update:section-map", {});
	lastSnapNotice.value = "Reset all profiles to default assembly";
	await nextTick();
	if (section.value) seedDefaultSeats(section.value);
}

function onSectionWheel(e: WheelEvent) {
	if (e.deltaY === 0) return;
	e.preventDefault();
	const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
	const oldZoom = sectionZoom.value;
	const nextZoom = clampZoom(oldZoom * factor);
	if (nextZoom === oldZoom) return;

	updateContainerSize();
	const el = canvasWrapEl.value;
	if (el) {
		const rect = el.getBoundingClientRect();
		const mx = e.clientX - rect.left;
		const my = e.clientY - rect.top;
		const cw = rect.width || containerSize.value.width;
		const ch = rect.height || containerSize.value.height;

		const rx = mx / cw - 0.5;
		const ry = my / ch - 0.5;

		const vb = viewBoxRect.value;
		const dw = vb.w * (1 - oldZoom / nextZoom);
		const dh = vb.h * (1 - oldZoom / nextZoom);

		sectionPan.value = {
			x: clampPan(sectionPan.value.x - rx * dw),
			y: clampPan(sectionPan.value.y - ry * dh),
		};
	}
	sectionZoom.value = nextZoom;
}

function isEditableTarget(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) return false;
	const tag = target.tagName;
	return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

function onKeyDown(e: KeyboardEvent) {
	if (e.key === "Shift" || e.shiftKey) shiftHeld.value = true;
	if (isEditableTarget(e.target)) return;
	if (e.key === "r" || e.key === "R") {
		if (selectedIndex.value !== null) {
			e.preventDefault();
			rotateSelected(e.shiftKey ? -90 : 90);
		}
	} else if (e.key === "+" || e.key === "=") {
		e.preventDefault();
		zoomIn();
	} else if (e.key === "-" || e.key === "_") {
		e.preventDefault();
		zoomOut();
	} else if (e.key === "0") {
		e.preventDefault();
		resetView();
	} else if (e.key === "ArrowLeft") {
		e.preventDefault();
		panBy(PAN_KEY_STEP_MM, 0);
	} else if (e.key === "ArrowRight") {
		e.preventDefault();
		panBy(-PAN_KEY_STEP_MM, 0);
	} else if (e.key === "ArrowUp") {
		e.preventDefault();
		panBy(0, PAN_KEY_STEP_MM);
	} else if (e.key === "ArrowDown") {
		e.preventDefault();
		panBy(0, -PAN_KEY_STEP_MM);
	} else if (e.key === "Escape") {
		if (raycastMode.value) setRaycastMode(false);
		selectedIndex.value = null;
	}
}

function onKeyUp(e: KeyboardEvent) {
	if (e.key === "Shift" || !e.shiftKey) shiftHeld.value = false;
}

function onWindowBlur() {
	shiftHeld.value = false;
}

/** Interactive Glass Domain overlays (shown in Section Templates Studio when editableGlassDomain is true). */
const glassDomainOverlays = computed(() => {
	if (
		!props.editableGlassDomain ||
		!showGlassDomainOverlay.value ||
		!props.glassDomain?.configured
	)
		return [];
	const pieces = section.value?.pieces ?? [];
	const { starts, ends } = compacted.value;
	const glassIndices = pieces.reduce<number[]>((acc, p, idx) => {
		if (p.kind === "glass") acc.push(idx);
		return acc;
	}, []);
	return glassIndices
		.map((pieceIdx, bayIdx) => {
			const piece = pieces[pieceIdx];
			const domain = effectiveGlassDomainForPiece(piece, pieceIdx);
			if (!domain) return null;
			const baseStart = starts[pieceIdx] ?? piece.start;
			const baseEnd = ends[pieceIdx] ?? piece.end;
			const meta = props.gasketMeta ?? paneGasketsFromPiece(piece);
			const ratio = meta ? { outerMm: meta.outer_mm, innerMm: meta.inner_mm } : null;
			const fit = fitGlassInDomain(baseStart, baseEnd, piece.thickness, domain, ratio);
			const r = fit.domainRect;
			return {
				pieceIdx,
				bayIdx,
				bayCount: glassIndices.length,
				baseStart,
				baseEnd,
				baseSpan: Math.max(4, baseEnd - baseStart),
				fit,
				rect: r,
				thickness: piece.thickness > 0 ? piece.thickness : GLASS_REF_THICKNESS_MM,
				depthLabel: `${roundTenth(r.h)} mm`,
			};
		})
		.filter((v): v is NonNullable<typeof v> => v !== null);
});

const domainHandleSize = computed(() =>
	Math.max(1.8, Math.min(4.5, 4.5 / Math.max(0.5, sectionZoom.value)))
);

function initOrToggleGlassDomain() {
	if (!props.glassDomain?.configured) {
		const firstGlass = (section.value?.pieces ?? []).find((p) => p.kind === "glass");
		const suggested = suggestInitialGlassDomain(
			placedShapes.value,
			firstGlass?.thickness || GLASS_REF_THICKNESS_MM
		);
		showGlassDomainOverlay.value = true;
		emit("update:glass-domain", suggested);
		return;
	}
	showGlassDomainOverlay.value = !showGlassDomainOverlay.value;
}

let domainDrag: {
	handle: DomainDragHandle;
	bayIdx: number;
	bayCount: number;
	baseSpan: number;
	startClientX: number;
	startClientY: number;
	orig: SectionGlassDomain;
	scale: number;
} | null = null;

function startDomainDrag(
	e: PointerEvent,
	ov: { bayIdx: number; bayCount: number; baseSpan: number },
	handle: DomainDragHandle
) {
	if (raycastMode.value) return;
	if (!props.editableGlassDomain || !props.glassDomain?.configured) return;
	if (e.button !== 0 && e.button !== undefined) return;
	e.stopPropagation();
	e.preventDefault();
	domainDrag = {
		handle,
		bayIdx: ov.bayIdx,
		bayCount: ov.bayCount,
		baseSpan: ov.baseSpan,
		startClientX: e.clientX,
		startClientY: e.clientY,
		orig: { ...props.glassDomain },
		scale: svgUnitsPerPixel(),
	};
	window.addEventListener("pointermove", onDomainDragMove);
	window.addEventListener("pointerup", endDomainDrag);
	window.addEventListener("pointercancel", endDomainDrag);
}

function onDomainDragMove(e: PointerEvent) {
	if (!domainDrag) return;
	const d = domainDrag;
	const screenDx = (e.clientX - d.startClientX) * d.scale;
	const screenDy = (e.clientY - d.startClientY) * d.scale;
	const dxAlong = axis.value === "v" ? -screenDy : screenDx;
	const dyDepth = axis.value === "v" ? screenDx : screenDy;
	const snapStep = e.altKey ? 0.1 : 0.5;

	if (d.bayCount > 1 && (d.handle.includes("w") || d.handle.includes("e"))) {
		const snap = (v: number) => Math.round(v / snapStep) * snapStep;
		const next: SectionGlassDomain = { ...d.orig, configured: true };
		if (d.handle.includes("n")) {
			next.minY = roundTenth(Math.min(d.orig.maxY - 2, snap(d.orig.minY + dyDepth)));
		}
		if (d.handle.includes("s")) {
			next.maxY = roundTenth(Math.max(d.orig.minY + 2, snap(d.orig.maxY + dyDepth)));
		}
		const origMullion = d.orig.insetMullion != null ? d.orig.insetMullion : d.orig.insetHigh;
		const isLeftBay = d.bayIdx === 0;
		const isRightBay = d.bayIdx === d.bayCount - 1;
		if (d.handle.includes("w")) {
			if (isLeftBay) {
				next.insetLow = roundTenth(snap(d.orig.insetLow + dxAlong));
				if (!mirrorSync.value) next.insetHigh = d.orig.insetHigh;
			} else {
				next.insetMullion = roundTenth(snap(origMullion + dxAlong));
				next.insetHigh = next.insetMullion;
			}
		}
		if (d.handle.includes("e")) {
			if (isRightBay) {
				next.insetLow = roundTenth(snap(d.orig.insetLow - dxAlong));
			} else {
				next.insetMullion = roundTenth(snap(origMullion - dxAlong));
				next.insetHigh = next.insetMullion;
			}
		}
		emit("update:glass-domain", next);
		return;
	}

	const next = applyGlassDomainDrag(
		d.orig,
		d.handle,
		dxAlong,
		dyDepth,
		d.baseSpan,
		mirrorSync.value,
		snapStep
	);
	emit("update:glass-domain", next);
}

function endDomainDrag() {
	if (!domainDrag) return;
	domainDrag = null;
	window.removeEventListener("pointermove", onDomainDragMove);
	window.removeEventListener("pointerup", endDomainDrag);
	window.removeEventListener("pointercancel", endDomainDrag);
}

onUnmounted(endDomainDrag);

function getSectionSnapshot() {
	const pieces = section.value?.pieces ?? [];
	const tags = pieceTags.value;
	const transforms = pieces.map((piece, i) =>
		getTransformForPiece(
			i,
			piece,
			piece.kind === "profile" ? outlines.value[piece.code] ?? null : null
		)
	);
	return {
		axis: axis.value,
		pieces,
		tags,
		transforms,
		sectionMap: { ...activeMap.value },
	};
}

function startRaycastDomain() {
	setRaycastMode(!raycastMode.value);
}

defineExpose({
	sectionZoom,
	sectionPan,
	zoomIn,
	zoomOut,
	resetView,
	panBy,
	getSectionSnapshot,
	reload: load,
	initOrToggleGlassDomain,
	startRaycastDomain,
	raycastMode,
	autoSeatBeadsForDomain,
});
</script>

<template>
	<section
		class="flex h-full w-full min-w-0 flex-1 flex-col bg-white text-gray-900 select-none"
		aria-label="Cross section"
	>
		<!-- Single-Row Responsive Toolbar: Axis Switch + Compact Icon Controls -->
		<div
			data-testid="section-top-toolbar"
			class="section-top-bar flex h-11 shrink-0 items-center justify-between gap-2 border-b border-gray-200 bg-white px-2.5"
		>
			<div class="flex min-w-0 items-center gap-2">
				<div
					class="inline-flex shrink-0 items-center rounded-[6px] border border-[#dcdfe4] bg-[#f7f8fa] p-0.5"
					role="group"
					aria-label="Cut"
				>
					<Tooltip v-for="a in AXES" :key="a.value" :text="a.label">
						<button
							type="button"
							:aria-pressed="axis === a.value"
							class="section-axis-btn inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-[4px] px-2.5 text-xs font-medium transition-colors"
							:class="
								axis === a.value
									? 'bg-white text-[#1a6fd4] shadow-2xs ring-1 ring-[#dcdfe4]/70'
									: 'text-gray-600 hover:text-gray-900'
							"
							@click="pick(a.value)"
						>
							<span
								:class="
									a.value === 'h'
										? 'lucide-square-centerline-dashed-horizontal'
										: 'lucide-square-centerline-dashed-vertical'
								"
								class="size-3.5 shrink-0"
								aria-hidden="true"
							/>
							<span class="section-axis-label">{{ a.label }}</span>
						</button>
					</Tooltip>
				</div>
				<span class="hidden truncate text-[11px] font-medium text-gray-400 2xl:inline">{{
					title
				}}</span>
			</div>

			<div class="flex shrink-0 items-center gap-1">
				<Tooltip
					:text="
						mirrorSync
							? 'Mirror & Sync ON (Opposite sides + B–B ↔ A–A)'
							: 'Mirror & Sync OFF (Edit independently)'
					"
				>
					<button
						type="button"
						data-testid="toggle-mirror-sync"
						aria-label="Mirror & Sync"
						:aria-pressed="mirrorSync"
						class="flex size-8 items-center justify-center rounded-[4px] border transition-colors"
						:class="
							mirrorSync
								? 'border-[#bfd7f5] bg-[#e6effb] text-[#1a6fd4]'
								: 'border-[#dcdfe4] bg-white text-gray-500 hover:bg-gray-50 hover:text-gray-800'
						"
						@click="toggleMirrorSync"
					>
						<span class="lucide-flip-horizontal-2 size-4" aria-hidden="true" />
					</button>
				</Tooltip>

				<Tooltip
					v-if="editableGlassDomain"
					:text="
						raycastMode
							? 'Cancel Raycast Pocket (Esc)'
							: 'Raycast Pocket: Click inside sash/frame pocket to auto-lock Domain, Bead & Gaskets'
					"
				>
					<button
						type="button"
						data-testid="toggle-raycast-pocket"
						aria-label="Raycast Pocket"
						:aria-pressed="raycastMode"
						class="flex size-8 items-center justify-center rounded-[4px] border transition-colors"
						:class="
							raycastMode
								? 'border-sky-400 bg-sky-50 text-sky-700 ring-1 ring-sky-300'
								: 'border-[#dcdfe4] bg-white text-gray-500 hover:bg-gray-50 hover:text-gray-800'
						"
						@click="startRaycastDomain"
					>
						<span class="lucide-crosshair size-4" aria-hidden="true" />
					</button>
				</Tooltip>

				<Tooltip
					v-if="editableGlassDomain"
					:text="
						glassDomain?.configured
							? 'Toggle Glass Domain overlay'
							: 'Set Glass Domain'
					"
				>
					<button
						type="button"
						data-testid="toggle-glass-domain"
						aria-label="Glass Domain"
						:aria-pressed="Boolean(glassDomain?.configured && showGlassDomainOverlay)"
						class="flex size-8 items-center justify-center rounded-[4px] border transition-colors"
						:class="
							glassDomain?.configured && showGlassDomainOverlay
								? 'border-red-300 bg-red-50 text-red-700'
								: 'border-[#dcdfe4] bg-white text-gray-500 hover:bg-gray-50 hover:text-gray-800'
						"
						@click="initOrToggleGlassDomain"
					>
						<span class="lucide-square-dashed size-4" aria-hidden="true" />
					</button>
				</Tooltip>

				<Tooltip
					:text="
						compactGlass
							? '1:1 Profile Focus ON (Compact glass span)'
							: '1:1 Profile Focus OFF (Full cut length)'
					"
				>
					<button
						type="button"
						data-testid="toggle-compact-glass"
						aria-label="1:1 Profile Focus"
						:aria-pressed="compactGlass"
						class="flex size-8 items-center justify-center rounded-[4px] border transition-colors"
						:class="
							compactGlass
								? 'border-[#bfd7f5] bg-[#e6effb] text-[#1a6fd4]'
								: 'border-[#dcdfe4] bg-white text-gray-500 hover:bg-gray-50 hover:text-gray-800'
						"
						@click="toggleCompactGlass"
					>
						<span class="lucide-scan size-4" aria-hidden="true" />
					</button>
				</Tooltip>

				<div class="mx-0.5 h-5 w-px bg-gray-200" />

				<Tooltip text="Reset All profile positions & orientations">
					<button
						type="button"
						data-testid="reset-all-profiles"
						aria-label="Reset All"
						class="flex size-8 items-center justify-center rounded-[4px] border border-[#dcdfe4] bg-white text-gray-600 transition-colors hover:bg-red-50 hover:border-red-200 hover:text-red-600"
						@click="resetAllPieces"
					>
						<span class="lucide-rotate-ccw size-4" aria-hidden="true" />
					</button>
				</Tooltip>
			</div>
		</div>

		<p v-if="error" role="alert" class="p-3 text-sm text-red-600">{{ error }}</p>

		<!-- Main Cross-Section Workspace (Same CAD Grid, Zoom & Drag-to-Pan as WindowCanvas) -->
		<template v-else-if="section">
			<div
				ref="canvasWrapEl"
				class="section-canvas-shell relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-white"
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
					:style="{
						cursor: isPanning
							? 'grabbing'
							: raycastMode
							? 'crosshair'
							: shiftHeld
							? 'grab'
							: 'grab',
					}"
					@wheel="onSectionWheel"
					@pointerdown="onCanvasPointerDown"
					@pointermove="onCanvasPointerMove"
					@pointerup="endWorkspacePan"
					@pointercancel="endWorkspacePan"
					@lostpointercapture="endWorkspacePan"
				>
					<g
						:transform="axis === 'v' ? 'rotate(-90)' : undefined"
						data-testid="section-orientation"
					>
						<defs>
							<!-- Minor 5mm & Major 25mm CAD Grid matching WindowCanvas workspace -->
							<pattern
								id="section-minor-grid"
								width="5"
								height="5"
								patternUnits="userSpaceOnUse"
							>
								<path
									d="M 5 0 L 0 0 0 5"
									fill="none"
									stroke="#E2E8F0"
									stroke-width="0.3"
								/>
							</pattern>
							<pattern
								id="section-major-grid"
								width="25"
								height="25"
								patternUnits="userSpaceOnUse"
							>
								<rect width="25" height="25" fill="url(#section-minor-grid)" />
								<path
									d="M 25 0 L 0 0 0 25"
									fill="none"
									stroke="#CBD5E1"
									stroke-width="0.5"
								/>
							</pattern>
							<pattern
								id="glass-domain-hatch"
								width="8"
								height="8"
								patternUnits="userSpaceOnUse"
								patternTransform="rotate(35)"
							>
								<line
									x1="0"
									y1="0"
									x2="0"
									y2="8"
									stroke="#EF4444"
									stroke-opacity="0.38"
									stroke-width="1.2"
								/>
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
							<!-- Louvers are a panel indication, selected as a whole rather than a profile. -->
							<g
								v-if="d.piece.kind === 'louver'"
								:data-piece="i"
								data-kind="louver"
								class="cursor-pointer"
								@click.stop="onPieceClick(d)"
							>
								<polygon
									v-for="(ring, blade) in d.shape.rings"
									:key="blade"
									:points="ring.map((p) => `${p.x},${p.y}`).join(' ')"
									fill="#CBD5E1"
									:fill-opacity="axis === 'h' ? 0.25 : 0.8"
									:stroke="d.selected ? '#2563EB' : '#64748B'"
									:stroke-dasharray="axis === 'h' ? '4 3' : undefined"
									stroke-width="1.2"
									vector-effect="non-scaling-stroke"
								/>
								<g
									v-if="axis === 'h'"
									data-testid="louver-blade-strips"
									pointer-events="none"
								>
									<line
										v-for="blade in d.piece.blades || 7"
										:key="blade"
										:x1="d.shape.bbox.minX + 1"
										:x2="d.shape.bbox.maxX - 1"
										:y1="
											d.shape.bbox.minY +
											((blade - 0.5) * d.shape.bbox.height) /
												(d.piece.blades || 7)
										"
										:y2="
											d.shape.bbox.minY +
											((blade - 0.5) * d.shape.bbox.height) /
												(d.piece.blades || 7)
										"
										stroke="#94A3B8"
										stroke-opacity="0.4"
										stroke-width="1"
										vector-effect="non-scaling-stroke"
									/>
								</g>
								<text
									:x="d.labelPos.x"
									:y="louverLabelDepth"
									:text-anchor="axis === 'v' ? 'end' : 'middle'"
									font-size="3"
									fill="#475569"
									data-testid="louver-label"
									:transform="
										axis === 'v'
											? `rotate(90 ${d.labelPos.x} ${louverLabelDepth})`
											: undefined
									"
								>
									Louver · {{ d.piece.blades || 7 }} blades
								</text>
							</g>
							<!-- Glass Piece (Moveable Reference) -->
							<g
								v-else-if="d.piece.kind === 'glass'"
								:data-piece-group="i"
								:data-ghost="d.ghost ? 'true' : undefined"
								:opacity="d.ghost ? 0.6 : 1"
								:style="{
									cursor: shiftHeld ? 'grab' : d.moveable ? 'move' : 'default',
								}"
								@pointerdown="onPiecePointerDown($event, d)"
								@pointermove="onPiecePointerMove"
								@pointerup="endPieceDrag"
								@click.stop="onPieceClick(d)"
							>
								<rect
									v-if="!d.piece.cutout"
									:data-piece="i"
									data-kind="glass"
									:data-stationary="d.moveable ? undefined : 'true'"
									:x="d.x"
									:y="d.y"
									:width="d.w"
									:height="d.depth"
									:fill="d.piece.material === 'steel' ? '#A8ADB5' : '#BAE6FD'"
									:fill-opacity="
										d.ghost ? 0.45 : d.piece.material === 'steel' ? 1 : 0.65
									"
									:stroke="
										d.selected
											? '#2563EB'
											: d.piece.material === 'steel'
											? '#4B5563'
											: '#0284C7'
									"
									:stroke-width="d.selected ? 2 : 1"
									:stroke-dasharray="d.ghost ? '3 2' : undefined"
									vector-effect="non-scaling-stroke"
								/>
								<g
									v-if="d.piece.cutout"
									:data-piece="i"
									data-kind="glass"
									data-testid="exhaust-section-cut"
								>
									<polygon
										v-for="(ring, segment) in d.shape.rings"
										:key="segment"
										:points="ring.map((p) => `${p.x},${p.y}`).join(' ')"
										:fill="
											d.piece.material === 'steel' ? '#A8ADB5' : '#BAE6FD'
										"
										:fill-opacity="d.piece.material === 'steel' ? 1 : 0.65"
										:stroke="
											d.selected
												? '#2563EB'
												: d.piece.material === 'steel'
												? '#4B5563'
												: '#0284C7'
										"
										stroke-width="1"
										vector-effect="non-scaling-stroke"
									/>
									<text
										:x="d.x + d.w / 2"
										:y="d.y - 6"
										:font-size="
											(11 * viewBoxRect.w) / Math.max(1, containerSize.width)
										"
										text-anchor="middle"
										fill="#475569"
										:transform="
											axis === 'v'
												? `rotate(90 ${d.x + d.w / 2} ${d.y - 6})`
												: undefined
										"
									>
										{{ d.piece.material === "steel" ? "Steel · " : "" }}Ø{{
											d.piece.cutout.diameter
										}}
										exhaust cut
									</text>
								</g>
								<!-- Center Break Lines on Compacted Glass -->
								<line
									v-if="compactGlass && !d.piece.cutout"
									:x1="d.x + d.w / 2 - 1.5"
									:x2="d.x + d.w / 2 - 0.5"
									:y1="d.y - 2"
									:y2="d.y + d.depth + 2"
									stroke="#0284C7"
									stroke-width="0.9"
									vector-effect="non-scaling-stroke"
								/>
								<line
									v-if="compactGlass && !d.piece.cutout"
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
									v-if="!d.piece.cutout"
									:x="d.labelPos.x"
									:y="d.labelPos.y"
									:transform="
										axis === 'v'
											? `rotate(90 ${d.labelPos.x} ${d.labelPos.y})`
											: undefined
									"
									text-anchor="middle"
									dominant-baseline="middle"
									:font-size="d.fontSize"
									font-weight="600"
									opacity="0.7"
									:fill="d.selected ? '#1D4ED8' : '#0369A1'"
									pointer-events="none"
									:textLength="
										d.piece.code.length > 5 ? d.maxTextWidth : undefined
									"
									lengthAdjust="spacingAndGlyphs"
								>
									{{ d.piece.code }}
								</text>
							</g>

							<!-- Mullion / Transom (Stationary at exact center / design position) or Draggable Profile Piece -->
							<g
								v-else
								:data-piece-group="i"
								:data-ghost="d.ghost ? 'true' : undefined"
								:data-colliding="d.colliding ? 'true' : undefined"
								:opacity="d.ghost ? 0.55 : 1"
								:style="{
									cursor: shiftHeld ? 'grab' : d.moveable ? 'move' : 'pointer',
								}"
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
									:stroke-width="
										d.selected ? 2.5 : d.mirroredTwinSelected ? 2 : 1.35
									"
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
									:transform="
										axis === 'v'
											? `rotate(90 ${d.labelPos.x} ${d.labelPos.y})`
											: undefined
									"
									text-anchor="middle"
									dominant-baseline="middle"
									:font-size="d.fontSize"
									font-weight="700"
									:opacity="d.selected ? 1 : 0.7"
									:fill="d.selected ? '#FFFFFF' : '#334155'"
									pointer-events="none"
									:textLength="
										d.piece.code.length > 5 ? d.maxTextWidth : undefined
									"
									lengthAdjust="spacingAndGlyphs"
								>
									{{ d.piece.code }}
								</text>
							</g>
						</template>

						<!-- Raycast Hover Crosshair + Dynamic Vertical Anchors + Seated EPDM Gaskets -->
						<SectionRaycastOverlay
							:axis="axis"
							:raycast-mode="raycastMode"
							:hover-point="raycastHoverPoint"
							:hover-probe="raycastHoverProbe"
							:show-anchors="
								Boolean(
									editableGlassDomain && showGlassDomainOverlay && !raycastMode
								)
							"
							:dynamic-states="activeDynamicDomainList"
							:gaskets="gasketPlacements"
							:mm-per-px="viewBoxRect.w / Math.max(1, containerSize.width)"
						/>

						<!-- Interactive Glass Domain Overlay (hidden during Raycast Mode so clicks lock cleanly) -->
						<g
							v-if="!raycastMode && glassDomainOverlays.length"
							data-testid="glass-domain-overlay"
						>
							<g v-for="ov in glassDomainOverlays" :key="`domain-${ov.pieceIdx}`">
								<!-- Hatched Domain Boundary Box (drag body to shift vertically) -->
								<rect
									data-testid="glass-domain-rect"
									:x="ov.rect.x"
									:y="ov.rect.y"
									:width="ov.rect.w"
									:height="ov.rect.h"
									fill="url(#glass-domain-hatch)"
									:stroke="ov.fit.exceedsDomain ? '#D97706' : '#DC2626'"
									stroke-width="1.6"
									stroke-dasharray="5 3"
									vector-effect="non-scaling-stroke"
									style="cursor: ns-resize; touch-action: none"
									@pointerdown="startDomainDrag($event, ov, 'move')"
								/>
								<!-- Domain Depth Label -->
								<text
									:x="ov.rect.x + ov.rect.w / 2"
									:y="ov.rect.y - 3"
									text-anchor="middle"
									font-size="3.2"
									font-weight="700"
									:fill="ov.fit.exceedsDomain ? '#B45309' : '#B91C1C'"
									pointer-events="none"
									:transform="
										axis === 'v'
											? `rotate(90 ${ov.rect.x + ov.rect.w / 2} ${
													ov.rect.y - 3
											  })`
											: undefined
									"
								>
									{{
										ov.fit.exceedsDomain
											? `⚠ ${ov.thickness} mm > ${ov.depthLabel} domain`
											: `Glass Domain · ${ov.depthLabel}`
									}}
								</text>
								<!-- 4 Edge Resize Hit Strips -->
								<rect
									data-testid="glass-domain-handle-n"
									:x="ov.rect.x"
									:y="ov.rect.y - domainHandleSize / 2"
									:width="ov.rect.w"
									:height="domainHandleSize"
									fill="transparent"
									style="cursor: ns-resize; touch-action: none"
									@pointerdown="startDomainDrag($event, ov, 'n')"
								/>
								<rect
									data-testid="glass-domain-handle-s"
									:x="ov.rect.x"
									:y="ov.rect.y + ov.rect.h - domainHandleSize / 2"
									:width="ov.rect.w"
									:height="domainHandleSize"
									fill="transparent"
									style="cursor: ns-resize; touch-action: none"
									@pointerdown="startDomainDrag($event, ov, 's')"
								/>
								<rect
									data-testid="glass-domain-handle-w"
									:x="ov.rect.x - domainHandleSize / 2"
									:y="ov.rect.y"
									:width="domainHandleSize"
									:height="ov.rect.h"
									fill="transparent"
									style="cursor: ew-resize; touch-action: none"
									@pointerdown="startDomainDrag($event, ov, 'w')"
								/>
								<rect
									data-testid="glass-domain-handle-e"
									:x="ov.rect.x + ov.rect.w - domainHandleSize / 2"
									:y="ov.rect.y"
									:width="domainHandleSize"
									:height="ov.rect.h"
									fill="transparent"
									style="cursor: ew-resize; touch-action: none"
									@pointerdown="startDomainDrag($event, ov, 'e')"
								/>
								<!-- 4 Corner Resize Handles -->
								<rect
									v-for="corner in [
									{ id: 'nw' as const, cx: ov.rect.x, cy: ov.rect.y, cursor: 'nwse-resize' },
									{ id: 'ne' as const, cx: ov.rect.x + ov.rect.w, cy: ov.rect.y, cursor: 'nesw-resize' },
									{ id: 'sw' as const, cx: ov.rect.x, cy: ov.rect.y + ov.rect.h, cursor: 'nesw-resize' },
									{ id: 'se' as const, cx: ov.rect.x + ov.rect.w, cy: ov.rect.y + ov.rect.h, cursor: 'nwse-resize' },
								]"
									:key="corner.id"
									:data-testid="`glass-domain-handle-${corner.id}`"
									:x="corner.cx - domainHandleSize / 2"
									:y="corner.cy - domainHandleSize / 2"
									:width="domainHandleSize"
									:height="domainHandleSize"
									fill="#FFFFFF"
									:stroke="ov.fit.exceedsDomain ? '#D97706' : '#DC2626'"
									stroke-width="1.4"
									vector-effect="non-scaling-stroke"
									:style="{ cursor: corner.cursor, touchAction: 'none' }"
									@pointerdown="startDomainDrag($event, ov, corner.id)"
								/>
							</g>
						</g>

						<g data-testid="grill-section">
							<g
								v-for="bar in grillSections"
								:key="bar.path"
								:data-grill-path="bar.path"
								style="cursor: move; touch-action: none"
								@pointerdown.stop.prevent="startGrillDrag($event, bar)"
								@click.stop="selectGrill(bar.path)"
								:transform="`translate(${
									bar.x + (grillDrag?.path === bar.path ? grillDrag.along : 0)
								} ${
									bar.y + (grillDrag?.path === bar.path ? grillDrag.depth : 0)
								})`"
							>
								<rect
									:x="0"
									:y="
										-Math.max(
											0,
											(10 * viewBoxRect.w) /
												Math.max(1, containerSize.width) -
												bar.h
										) / 2
									"
									:width="bar.w"
									:height="
										Math.max(
											bar.h,
											(10 * viewBoxRect.w) / Math.max(1, containerSize.width)
										)
									"
									fill="transparent"
									pointer-events="all"
								/>
								<rect
									data-testid="grill-band"
									x="0"
									y="0"
									:width="bar.w"
									:height="bar.h"
									:fill="
										props.selectedPath === `GRILL:${bar.path}`
											? '#93B4E8'
											: '#B8BDC5'
									"
									:stroke="
										props.selectedPath === `GRILL:${bar.path}`
											? '#2563EB'
											: '#424955'
									"
									stroke-width="1"
									vector-effect="non-scaling-stroke"
								/>
								<rect
									v-for="(mark, i) in bar.marks"
									:key="i"
									data-testid="grill-bar-marker"
									:x="mark - Math.min(2, bar.w / (bar.count + 1) / 4) / 2"
									y="0"
									:width="Math.min(2, bar.w / (bar.count + 1) / 4)"
									:height="bar.h"
									fill="#616873"
									pointer-events="none"
								/>
								<text
									x="0"
									y="-5"
									font-size="3.5"
									fill="#303640"
									pointer-events="none"
									:transform="axis === 'v' ? 'rotate(90 0 -5)' : undefined"
								>
									Grill · {{ bar.count }}
									{{ axis === "h" ? "vertical" : "horizontal" }} bars
								</text>
							</g>
						</g>
						<g v-if="grillDrag" data-testid="grill-smart-guides" pointer-events="none">
							<line
								v-for="(guide, i) in grillDrag.guides"
								:key="i"
								:x1="guide.axis === 'x' ? guide.pos : guide.start"
								:y1="guide.axis === 'x' ? guide.start : guide.pos"
								:x2="guide.axis === 'x' ? guide.pos : guide.end"
								:y2="guide.axis === 'x' ? guide.end : guide.pos"
								:stroke="guide.center ? '#D946EF' : '#EF4444'"
								:stroke-dasharray="guide.center ? '5 3' : undefined"
								stroke-width="1.2"
								vector-effect="non-scaling-stroke"
							/>
							<text
								:x="grillDrag.box.x + grillDrag.along"
								:y="grillDrag.box.y + grillDrag.depth - 12"
								font-size="3.5"
								fill="#2563EB"
								:transform="
									axis === 'v'
										? `rotate(90 ${grillDrag.box.x + grillDrag.along} ${
												grillDrag.box.y + grillDrag.depth - 12
										  })`
										: undefined
								"
							>
								Depth
								{{ (grillDrag.config.offset + grillDrag.depth).toFixed(1) }} mm{{
									grillDrag.guides.length ? " · Snapped" : ""
								}}
							</text>
						</g>
						<!-- Smart guides: solid red = edge alignment, dashed magenta = centre / glass plane.
					     Pills show distance in mm; filled red = equal to the opposite gap or a gap elsewhere. -->
						<g
							v-if="activeSmartGuides && ghostDrag"
							data-testid="smart-guides-overlay"
							pointer-events="none"
						>
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
								<g
									:transform="`translate(${s.pill.x}, ${s.pill.y}) scale(${guideScale})`"
								>
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
									>
										{{ s.label }}
									</text>
								</g>
							</g>
						</g>
					</g>
				</svg>

				<!-- Slim Floating Profile Control Bar Positioned Directly Above Selected Profile -->
				<div
					v-if="selectedDrawn && selectedDrawn.piece.kind === 'profile'"
					data-testid="profile-inspector"
					class="absolute z-20 flex flex-col items-center transition-opacity duration-75"
					:class="
						ghostDrag
							? 'pointer-events-none opacity-75'
							: 'pointer-events-auto opacity-100'
					"
					:style="selectedFloatingStyle"
					@pointerdown.stop
					@click.stop
				>
					<div
						class="flex h-13 items-center gap-0.5 rounded-md border border-gray-200 bg-white px-2.5 text-gray-900 shadow-[0_6px_20px_rgba(20,30,50,0.16)]"
					>
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
							<span
								class="text-[11px] font-semibold uppercase tracking-wider text-blue-800"
							>
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
							:class="
								selectedDatum() === 'center'
									? 'bg-blue-50 text-blue-800'
									: 'text-gray-900'
							"
							@click="setSelectedOrigin('center')"
						>
							<svg
								viewBox="0 0 16 16"
								class="size-4.5"
								fill="none"
								stroke="currentColor"
								stroke-width="1.5"
								aria-hidden="true"
							>
								<circle cx="8" cy="8" r="2.2" />
								<path
									d="M8 1.6v2.2M8 12.2v2.2M1.6 8h2.2M12.2 8h2.2"
									stroke-linecap="round"
								/>
							</svg>
						</button>

						<!-- 2. Outer Corner Datum (Pivot at Outer Corner) -->
						<button
							type="button"
							aria-label="Outer datum"
							title="Rotate and flip around profile outer corner"
							class="flex size-9 items-center justify-center rounded hover:bg-gray-100"
							:class="
								selectedDatum() === 'outer'
									? 'bg-blue-50 text-blue-800'
									: 'text-gray-900'
							"
							@click="setSelectedOrigin('outer')"
						>
							<svg
								viewBox="0 0 16 16"
								class="size-4.5"
								fill="none"
								stroke="currentColor"
								stroke-width="1.5"
								aria-hidden="true"
							>
								<path
									d="M4 4v8h8"
									stroke-linecap="round"
									stroke-linejoin="round"
								/>
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
							<svg
								viewBox="0 0 640 640"
								class="size-4.5"
								fill="currentColor"
								aria-hidden="true"
							>
								<path
									d="M88 256L232 256C241.7 256 250.5 250.2 254.2 241.2C257.9 232.2 255.9 221.9 249 215L202.3 168.3C277.6 109.7 386.6 115 455.8 184.2C530.8 259.2 530.8 380.7 455.8 455.7C380.8 530.7 259.3 530.7 184.3 455.7C174.1 445.5 165.3 434.4 157.9 422.7C148.4 407.8 128.6 403.4 113.7 412.9C98.8 422.4 94.4 442.2 103.9 457.1C113.7 472.7 125.4 487.5 139 501C239 601 401 601 501 501C601 401 601 239 501 139C406.8 44.7 257.3 39.3 156.7 122.8L105 71C98.1 64.2 87.8 62.1 78.8 65.8C69.8 69.5 64 78.3 64 88L64 232C64 245.3 74.7 256 88 256z"
								/>
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
							<svg
								viewBox="0 0 640 640"
								class="size-4.5"
								fill="currentColor"
								aria-hidden="true"
							>
								<path
									d="M552 256L408 256C398.3 256 389.5 250.2 385.8 241.2C382.1 232.2 384.1 221.9 391 215L437.7 168.3C362.4 109.7 253.4 115 184.2 184.2C109.2 259.2 109.2 380.7 184.2 455.7C259.2 530.7 380.7 530.7 455.7 455.7C463.9 447.5 471.2 438.8 477.6 429.6C487.7 415.1 507.7 411.6 522.2 421.7C536.7 431.8 540.2 451.8 530.1 466.3C521.6 478.5 511.9 490.1 501 501C401 601 238.9 601 139 501C39.1 401 39 239 139 139C233.3 44.7 382.7 39.4 483.3 122.8L535 71C541.9 64.1 552.2 62.1 561.2 65.8C570.2 69.5 576 78.3 576 88L576 232C576 245.3 565.3 256 552 256z"
								/>
							</svg>
						</button>

						<div class="mx-1.5 h-5.5 w-px bg-gray-200" />

						<!-- Flip directions follow the screen axes of the rotated workspace. -->
						<!-- 5. Flip Horizontally -->
						<button
							type="button"
							aria-label="Flip horizontal"
							title="Flip horizontally"
							class="flex size-9 items-center justify-center rounded hover:bg-gray-100"
							:class="
								(
									axis === 'v'
										? selectedDrawn.pieceTransform.flipY
										: selectedDrawn.pieceTransform.flipX
								)
									? 'bg-blue-50 text-blue-800'
									: 'text-gray-900'
							"
							@click="flipSelected(axis === 'v' ? 'y' : 'x')"
						>
							<svg
								viewBox="0 0 16 16"
								class="size-4.5"
								fill="none"
								stroke="currentColor"
								stroke-width="1.5"
								aria-hidden="true"
							>
								<path d="M8 2.4v11.2" stroke-linecap="round" />
								<path
									d="M5.6 5.4 3.2 8l2.4 2.6M10.4 5.4 12.8 8l-2.4 2.6"
									stroke-linecap="round"
									stroke-linejoin="round"
								/>
							</svg>
						</button>

						<!-- 6. Flip Vertically -->
						<button
							type="button"
							aria-label="Flip vertical"
							title="Flip vertically"
							class="flex size-9 items-center justify-center rounded hover:bg-gray-100"
							:class="
								(
									axis === 'v'
										? selectedDrawn.pieceTransform.flipX
										: selectedDrawn.pieceTransform.flipY
								)
									? 'bg-blue-50 text-blue-800'
									: 'text-gray-900'
							"
							@click="flipSelected(axis === 'v' ? 'x' : 'y')"
						>
							<svg
								viewBox="0 0 16 16"
								class="size-4.5"
								fill="none"
								stroke="currentColor"
								stroke-width="1.5"
								aria-hidden="true"
							>
								<path d="M2.4 8h11.2" stroke-linecap="round" />
								<path
									d="M5.4 5.6 8 3.2l2.6 2.4M5.4 10.4 8 12.8l2.6-2.4"
									stroke-linecap="round"
									stroke-linejoin="round"
								/>
							</svg>
						</button>

						<div class="mx-1.5 h-5.5 w-px bg-gray-200" />

						<!-- 7. Set As Default Orientation (Persists to DocType) -->
						<button
							type="button"
							aria-label="Set as default orientation"
							title="Save current orientation as default for this profile"
							class="flex h-9 items-center rounded px-3 text-[13px] font-medium transition-colors hover:bg-gray-100"
							:class="
								selectedVisualRotation !== 0 ||
								selectedDrawn.pieceTransform.flipX ||
								selectedDrawn.pieceTransform.flipY
									? 'text-blue-800 font-semibold'
									: 'text-gray-900'
							"
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
							<svg
								viewBox="0 0 16 16"
								class="size-4.5"
								fill="none"
								stroke="currentColor"
								stroke-width="1.5"
								aria-hidden="true"
							>
								<path d="M12.6 8a4.6 4.6 0 1 1-1.2-3.1" stroke-linecap="round" />
								<path
									d="M11.2 2.2v3H8.2"
									stroke-linecap="round"
									stroke-linejoin="round"
								/>
							</svg>
						</button>
					</div>

					<!-- Downward Pointer Caret Anchored Above the Profile -->
					<div class="h-1.5 w-3 overflow-hidden">
						<div
							class="mx-auto size-2 -translate-y-1 rotate-45 border-r border-b border-gray-200 bg-white"
						/>
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
					<span
						v-else-if="lastSnapNotice"
						class="font-sans font-medium"
						style="color: #059669"
					>
						{{ lastSnapNotice }}
					</span>
				</div>

				<!-- Bottom-Right Workspace Zoom & Pan Controls (Identical to WindowCanvas) -->
				<div
					class="pointer-events-auto absolute right-3 bottom-3 flex items-center gap-1 rounded-lg border border-gray-200 bg-white/95 px-1.5 py-1 shadow-xs backdrop-blur-xs"
					role="toolbar"
					aria-label="Section workspace controls"
				>
					<span class="section-pan-hint px-1.5 text-[11px] text-gray-500"
						>Drag or Shift + drag to pan</span
					>
					<div class="section-pan-divider h-3.5 w-px bg-gray-200" />
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

			<div
				v-if="missing.length || issues.length"
				class="border-t border-gray-200 bg-gray-50 px-3 py-1.5"
			>
				<p
					v-if="missing.length"
					data-testid="missing-outlines"
					class="text-xs text-gray-500"
				>
					No section outline for {{ missing.join(", ") }}; drawn as boxes.
				</p>
				<p v-for="(iss, i) in issues" :key="i" class="text-xs text-amber-600">
					{{ iss.message }}
				</p>
			</div>
		</template>
		<p v-else class="p-4 text-sm text-gray-400">Cutting...</p>
	</section>
</template>

<style scoped>
.section-top-bar {
	container-type: inline-size;
	container-name: sectionbar;
}

.section-canvas-shell {
	container-type: inline-size;
	container-name: sectioncanvas;
}

@container sectionbar (max-width: 420px) {
	.section-axis-btn {
		padding-left: 7px;
		padding-right: 7px;
	}
	.section-axis-label {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}
}

@container sectioncanvas (max-width: 460px) {
	.section-pan-hint,
	.section-pan-divider {
		display: none;
	}
}
</style>
