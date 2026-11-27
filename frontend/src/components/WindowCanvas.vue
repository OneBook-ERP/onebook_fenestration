<script lang="ts">
/** Workspace zoom ("pan in / pan out") and pan offset limits. */
export const MIN_ZOOM = 0.4;
export const MAX_ZOOM = 3.0;
export const ZOOM_STEP = 0.15;
export const MAX_PAN_OFFSET = 1200;
export const DEFAULT_FINISH = "#8A8F98";
</script>

<script setup lang="ts">
import { grillMembers } from "@/design/grill";
import { exhaustCut, type ExhaustCut } from "@/design/exhaustCut";
import { computed, onMounted, onUnmounted, ref } from "vue";
import { layoutGeom } from "@/design/geometry";
import { getNode } from "@/design/tree";
import type { BarGeom, CellGeom, Design, SplitNode } from "@/design/types";

const FRAME_FACE_DEFAULT = 42;
const BAR_FACE_DEFAULT = 40;
const SASH_FACE_DEFAULT = 50;
const PAD = 60;
const FONT = "Inter, sans-serif";
const GRID_EXTENT = 2880;

const PAN_KEY_STEP = 40;

const C = {
	glass: "#B3E5F6",
	stroke: "#333333",
	select: "#2563EB",
	selectFill: "#5B9BE8",
	barSelectFill: "#1565D8",
	issue: "#D97706",
	dim: "#444444",
	cut: "#DC2626",
};

const frameFace = computed(() => {
	const widths = props.profileWidths;
	if (!widths) return FRAME_FACE_DEFAULT;
	const overrideCode = props.design.frameProfileId || props.design.profiles?.frame;
	if (overrideCode && widths[overrideCode]) return widths[overrideCode];
	const memberCode = props.members?.find((m) => m.role === "frame")?.profile;
	if (memberCode && widths[memberCode]) return widths[memberCode];
	const defaultCode = props.roleDefaults?.frame;
	if (defaultCode && widths[defaultCode]) return widths[defaultCode];
	return FRAME_FACE_DEFAULT;
});

function sashFaceFor(cell: CellGeom): number {
	const widths = props.profileWidths;
	if (!widths) return SASH_FACE_DEFAULT;
	const node = cell.node;
	if (node.type !== "sash") return SASH_FACE_DEFAULT;
	const overrideCode =
		node.profile ||
		props.design.profiles?.[cell.path] ||
		props.design.sashProfileId ||
		props.design.profiles?.sash;
	if (overrideCode && widths[overrideCode]) return widths[overrideCode];
	const memberCode = props.members?.find(
		(m) => m.role === "sash" && m.path === cell.path
	)?.profile;
	if (memberCode && widths[memberCode]) return widths[memberCode];
	const defaultCode = props.roleDefaults?.sash;
	if (defaultCode && widths[defaultCode]) return widths[defaultCode];
	return SASH_FACE_DEFAULT;
}

function barFaceFor(bar: BarGeom): number {
	if (props.design.isSliding) return 14;
	const widths = props.profileWidths;
	if (!widths) return BAR_FACE_DEFAULT;
	const role = bar.dir === "v" ? "mullion" : "transom";
	const overrideCode =
		props.design.profiles?.[bar.id] ||
		(bar.dir === "v" ? props.design.mullionProfileId : undefined) ||
		props.design.profiles?.[role];
	if (overrideCode && widths[overrideCode]) return widths[overrideCode];
	const memberCode = props.members?.find(
		(m) =>
			(m.panel === bar.id || m.path === bar.id) &&
			(m.role === role || m.role === "mullion" || m.role === "transom")
	)?.profile;
	if (memberCode && widths[memberCode]) return widths[memberCode];
	const defaultCode =
		props.roleDefaults?.[role] ??
		(role === "transom" ? props.roleDefaults?.mullion : undefined);
	if (defaultCode && widths[defaultCode]) return widths[defaultCode];
	return BAR_FACE_DEFAULT;
}

const props = withDefaults(
	defineProps<{
		design: Design;
		selectedPath: string | null;
		issuePaths: string[];
		view: "inside" | "outside";
		viewW?: number;
		viewH?: number;
		finishColor?: string;
		/** Section view on: cut positions in mm (h = height of the B–B cut, v = x of the A–A cut). */
		section?: { axis: "h" | "v"; h: number; v: number } | null;
		/** Optional computed members used to determine corner joints and exact member lengths. */
		members?: {
			role?: string;
			path?: string;
			panel?: string;
			position?: string;
			length?: number;
			profile?: string;
			angles?: unknown;
		}[];
		/** Optional computed glass rows used to display exact glass cut width & height on selection. */
		glass?: {
			path?: string;
			panel?: string;
			glass?: string;
			width?: number;
			height?: number;
		}[];
		/** Optional profile max width lookup (e.g. { E104156: 50, E104160: 60, E104159: 70 }) to dynamically size frame/sash/mullion face widths. */
		profileWidths?: Record<string, number>;
		/** Default profile code per role used immediately before async compute completes. */
		roleDefaults?: Record<string, string>;
	}>(),
	{
		viewW: 640,
		viewH: 760,
		finishColor: "#8A8F98",
		section: null,
		members: undefined,
		glass: undefined,
		profileWidths: undefined,
		roleDefaults: undefined,
	}
);
const emit = defineEmits<{
	select: [path: string];
	"move-split": [payload: { splitPath: string; index: number; pos: number }];
	"drag-start": [];
	"drag-end": [];
	"update:cut": [payload: { axis: "h" | "v"; at: number }];
	"drop-tool": [
		payload: { kind: string; id: string; cellPath: string; replaceDesign?: boolean }
	];
	"edit-dim": [axis: "w" | "h"];
}>();

const dragOverPath = ref<string | null>(null);
const dragOverEmpty = ref(false);
function peekWindowDragKind(): string | null {
	const raw = (window as unknown as { __fenDragPayload?: string }).__fenDragPayload;
	if (!raw) return null;
	try {
		const parsed = JSON.parse(raw);
		return typeof parsed?.kind === "string" ? parsed.kind : null;
	} catch {
		return null;
	}
}
function isPointInBox(pt: { x: number; y: number }, box: Box): boolean {
	return pt.x >= box.x && pt.x <= box.x + box.w && pt.y >= box.y && pt.y <= box.y + box.h;
}
function parseDragPayload(e: DragEvent): { kind: string; id: string } | null {
	const raw =
		e.dataTransfer?.getData("application/json") ||
		e.dataTransfer?.getData("text/plain") ||
		(window as unknown as { __fenDragPayload?: string }).__fenDragPayload;
	if (!raw) return null;
	try {
		const parsed = JSON.parse(raw);
		if (parsed && typeof parsed.kind === "string" && typeof parsed.id === "string")
			return parsed;
	} catch {
		// ignore malformed payload
	}
	return null;
}
function clientToSvgPoint(clientX: number, clientY: number): { x: number; y: number } {
	const el = svg.value;
	const vbW = props.viewW / zoom.value;
	const vbH = props.viewH / zoom.value;
	const vbX = (props.viewW - vbW) / 2 - pan.value.x;
	const vbY = (props.viewH - vbH) / 2 - pan.value.y;
	if (!el) return { x: vbX + vbW / 2, y: vbY + vbH / 2 };
	const r = el.getBoundingClientRect();
	if (!r.width || !r.height) return { x: vbX + vbW / 2, y: vbY + vbH / 2 };
	const meet = Math.min(r.width / vbW, r.height / vbH);
	const renW = vbW * meet;
	const renH = vbH * meet;
	const offX = r.left + (r.width - renW) / 2;
	const offY = r.top + (r.height - renH) / 2;
	return {
		x: vbX + (clientX - offX) / meet,
		y: vbY + (clientY - offY) / meet,
	};
}
function onCellDragOver(cellPath: string, e: DragEvent) {
	e.preventDefault();
	if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
	dragOverPath.value = cellPath;
	dragOverEmpty.value = false;
}
function onCellDrop(cellPath: string, e: DragEvent) {
	e.preventDefault();
	e.stopPropagation();
	dragOverPath.value = null;
	dragOverEmpty.value = false;
	const payload = parseDragPayload(e);
	(window as unknown as { __fenDragPayload?: string }).__fenDragPayload = undefined;
	if (payload) emit("drop-tool", { ...payload, cellPath, replaceDesign: false });
}
function onSvgDragOver(e: DragEvent) {
	e.preventDefault();
	if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
	if (!svg.value) return;
	const r = svg.value.getBoundingClientRect();
	if (!r.width || !r.height) return;
	const pt = clientToSvgPoint(e.clientX, e.clientY);
	const hit = cells.value.find((c) => isPointInBox(pt, c.box));
	if (hit) {
		dragOverPath.value = hit.cell.path;
		dragOverEmpty.value = false;
	} else if (!isPointInBox(pt, frameBox.value)) {
		dragOverPath.value = null;
		dragOverEmpty.value = peekWindowDragKind() !== "info";
	} else {
		dragOverPath.value = null;
		dragOverEmpty.value = false;
	}
}
function onSvgDrop(e: DragEvent) {
	e.preventDefault();
	dragOverPath.value = null;
	dragOverEmpty.value = false;
	const payload = parseDragPayload(e);
	(window as unknown as { __fenDragPayload?: string }).__fenDragPayload = undefined;
	if (!payload) return;
	const r = svg.value?.getBoundingClientRect();
	const hasLayout = Boolean(r && r.width > 0 && r.height > 0);
	const pt = clientToSvgPoint(e.clientX, e.clientY);
	const hit = cells.value.find((c) => isPointInBox(pt, c.box));
	if (hit) {
		emit("drop-tool", { ...payload, cellPath: hit.cell.path, replaceDesign: false });
		return;
	}
	if (hasLayout && !isPointInBox(pt, frameBox.value)) {
		emit("drop-tool", { ...payload, cellPath: "", replaceDesign: true });
		return;
	}
	if (cells.value[0])
		emit("drop-tool", {
			...payload,
			cellPath: cells.value[0].cell.path,
			replaceDesign: false,
		});
}

/** Mix a #RRGGBB colour towards white by `amount` (0..1). */
function lighten(hex: string, amount: number): string {
	const n = parseInt(hex.slice(1), 16);
	const mix = (shift: number) => {
		const c = (n >> shift) & 255;
		return Math.round(c + (255 - c) * amount);
	};
	return (
		"#" +
		[16, 8, 0]
			.map((s) => mix(s).toString(16).padStart(2, "0"))
			.join("")
			.toUpperCase()
	);
}
/** Finish colours come from a free Color field; anything but #RRGGBB falls back to the default. */
const finish = computed(() =>
	/^#[0-9a-f]{6}$/i.test(props.finishColor) ? props.finishColor : DEFAULT_FINISH
);
const frameFill = finish;
const sashFill = computed(() => lighten(finish.value, 0.1));

const svg = ref<SVGSVGElement | null>(null);
const zoom = ref(1);
const pan = ref({ x: 0, y: 0 });
const shiftHeld = ref(false);
const isPanning = ref(false);
let suppressNextClick = false;

function clampZoom(z: number): number {
	return Math.round(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z)) * 100) / 100;
}

function clampPan(v: number): number {
	return Math.min(MAX_PAN_OFFSET, Math.max(-MAX_PAN_OFFSET, v));
}

function zoomIn() {
	zoom.value = clampZoom(zoom.value + ZOOM_STEP);
}

function zoomOut() {
	zoom.value = clampZoom(zoom.value - ZOOM_STEP);
}

function resetView() {
	zoom.value = 1;
	pan.value = { x: 0, y: 0 };
}

function panBy(dx: number, dy: number) {
	pan.value = { x: clampPan(pan.value.x + dx), y: clampPan(pan.value.y + dy) };
}

const viewBoxStr = computed(() => {
	const w = props.viewW / zoom.value;
	const h = props.viewH / zoom.value;
	const x = (props.viewW - w) / 2 - pan.value.x;
	const y = (props.viewH - h) / 2 - pan.value.y;
	return `${fmt(x)} ${fmt(y)} ${fmt(w)} ${fmt(h)}`;
});

const scale = computed(() =>
	Math.min(
		(props.viewW - 2 * PAD) / props.design.width,
		(props.viewH - 2 * PAD) / props.design.height
	)
);
const originX = computed(() => (props.viewW - props.design.width * scale.value) / 2);
const originY = computed(() => (props.viewH - props.design.height * scale.value) / 2);
const geom = computed(() => layoutGeom(props.design));

const isOutside = computed(() => props.view === "outside");
const px = (mm: number) => originX.value + mm * scale.value;
const pxPoint = (mm: number) => px(isOutside.value ? props.design.width - mm : mm);
const pxSpan = (startMm: number, lenMm: number) => ({
	x: px(isOutside.value ? props.design.width - (startMm + lenMm) : startMm),
	w: lenMm * scale.value,
});
const py = (mm: number) => originY.value + (props.design.height - mm) * scale.value;
const fmt = (n: number) => String(Math.round(n * 100) / 100);

interface Box {
	x: number;
	y: number;
	w: number;
	h: number;
}

const frameConfig = computed(() => props.design.frameConfig ?? "4-side");
const bottomFrameFace = computed(() => {
	if (frameConfig.value === "3-side") return 0;
	if (frameConfig.value === "3-side-threshold") return Math.round(frameFace.value * 0.45);
	return frameFace.value;
});

/** Pixel box of the visible opening of a cell: frame at the outside, half a bar at inner edges. */
function cellBox(c: CellGeom): Box {
	const { width, height } = props.design;
	const ff = frameFace.value;
	const bf = bottomFrameFace.value;
	const innerHalf = (props.design.isSliding ? 14 : BAR_FACE_DEFAULT) / 2;
	const l = c.x === 0 ? ff : innerHalf;
	const r = c.x + c.w === width ? ff : innerHalf;
	const b = c.y === 0 ? bf : innerHalf;
	const t = c.y + c.h === height ? ff : innerHalf;
	const span = pxSpan(c.x + l, c.w - l - r);
	return {
		x: span.x,
		y: py(c.y + c.h - t),
		w: span.w,
		h: (c.h - t - b) * scale.value,
	};
}

function inset(b: Box, mm: number): Box {
	const d = mm * scale.value;
	return { x: b.x + d, y: b.y + d, w: Math.max(0, b.w - 2 * d), h: Math.max(0, b.h - 2 * d) };
}

type HingeSide = "left" | "right" | "top" | "bottom";
type CutAngle = 45 | 90;

interface LineSeg {
	x1: number;
	y1: number;
	x2: number;
	y2: number;
}

interface HandlePos {
	x: number;
	y: number;
	w: number;
	h: number;
}

interface CellView {
	fanCut: ExhaustCut | null;
	cell: CellGeom;
	box: Box;
	glass: Box;
	panelId: string;
	glassNo: number;
	selected: boolean;
	glassSelected: boolean;
	issue: boolean;
	stroke: string;
	strokeWidth: number;
	lines: string[];
	side: HingeSide | null;
	hingeLine: LineSeg | null;
	hingeBlocks: HandlePos[];
	isDoor: boolean;
	corners: LineSeg[];
	cutAngle: CutAngle;
	handle: HandlePos | null;
	hasBead: boolean;
	beadBox: Box;
	sashW: number | null;
	sashH: number | null;
	glassW: number;
	glassH: number;
}

interface BarView {
	bar: BarGeom;
	rect: Box;
	selected: boolean;
	cutLength: number;
	spanLength: number;
	faceWidth: number;
	pos: number;
}

function parseCutAngle(angles: unknown): CutAngle {
	if (Array.isArray(angles)) {
		return angles.some((a) => Number(a) === 90) &&
			!angles.some((a) => Number(a) === 45 || Number(a) === 135)
			? 90
			: 45;
	}
	if (typeof angles === "string") {
		const nums = (angles.match(/\d+/g) ?? []).map(Number);
		if (nums.includes(90) && !nums.includes(45) && !nums.includes(135)) return 90;
	}
	return 45;
}

function roleCutAngle(role: string, path?: string): CutAngle {
	const list = props.members;
	if (!list?.length) return 45;
	const match =
		(path ? list.find((m) => m.role === role && m.path === path) : undefined) ??
		list.find((m) => m.role === role);
	return match ? parseCutAngle(match.angles) : 45;
}

/** 45° corner miter lines or 90° butt joint lines at all 4 corners between outer and inner boxes. */
function cornerLines(outer: Box, inner: Box, angle: CutAngle): LineSeg[] {
	if (angle === 90) {
		return [
			{ x1: outer.x, y1: inner.y, x2: inner.x, y2: inner.y },
			{ x1: inner.x + inner.w, y1: inner.y, x2: outer.x + outer.w, y2: inner.y },
			{ x1: outer.x, y1: inner.y + inner.h, x2: inner.x, y2: inner.y + inner.h },
			{
				x1: inner.x + inner.w,
				y1: inner.y + inner.h,
				x2: outer.x + outer.w,
				y2: inner.y + inner.h,
			},
		];
	}
	return [
		{ x1: outer.x, y1: outer.y, x2: inner.x, y2: inner.y },
		{ x1: outer.x + outer.w, y1: outer.y, x2: inner.x + inner.w, y2: inner.y },
		{ x1: outer.x, y1: outer.y + outer.h, x2: inner.x, y2: inner.y + inner.h },
		{
			x1: outer.x + outer.w,
			y1: outer.y + outer.h,
			x2: inner.x + inner.w,
			y2: inner.y + inner.h,
		},
	];
}

function hingeSide(c: CellGeom): HingeSide | null {
	const node = c.node;
	if (node.type !== "sash" || node.isSliding || !node.hinge) return null;
	if (node.hinge === "top") return "top";
	if (node.hinge === "bottom") return "bottom";
	const h = node.hinge === "right" ? "right" : "left";
	if (props.view === "inside") return h;
	return h === "left" ? "right" : "left";
}

function computeHingeLine(box: Box, side: HingeSide | null): LineSeg | null {
	if (!side) return null;
	if (side === "top") {
		return { x1: box.x, y1: box.y, x2: box.x + box.w, y2: box.y };
	}
	if (side === "bottom") {
		return { x1: box.x, y1: box.y + box.h, x2: box.x + box.w, y2: box.y + box.h };
	}
	const x = side === "left" ? box.x : box.x + box.w;
	return { x1: x, y1: box.y, x2: x, y2: box.y + box.h };
}

/** Swing triangle: the apex sits on the hinged edge. */
function openingLines(b: Box, side: HingeSide): string[] {
	if (side === "top")
		return [`${b.x},${b.y + b.h} ${b.x + b.w / 2},${b.y} ${b.x + b.w},${b.y + b.h}`];
	if (side === "bottom")
		return [`${b.x},${b.y} ${b.x + b.w / 2},${b.y + b.h} ${b.x + b.w},${b.y}`];
	const apexX = side === "left" ? b.x : b.x + b.w;
	const farX = side === "left" ? b.x + b.w : b.x;
	const midY = b.y + b.h / 2;
	return [`${farX},${b.y} ${apexX},${midY} ${farX},${b.y + b.h}`];
}

function effectiveSlideDir(dir?: "left" | "right"): "left" | "right" {
	const d = dir === "left" ? "left" : "right";
	if (!isOutside.value) return d;
	return d === "left" ? "right" : "left";
}

/** Handle placed at the center of each sash on the rail opposite to the hinge (or outer edge for sliding). */
function computeHandlePos(
	cell: CellGeom,
	box: Box,
	glass: Box,
	side: HingeSide | null
): HandlePos | null {
	if (cell.node.type !== "sash") return null;
	if (cell.node.isSliding) {
		if (cell.node.slideFixed) return null;
		const dir = effectiveSlideDir(cell.node.slideDir);
		const railCenterX =
			dir === "right"
				? box.x + (glass.x - box.x) / 2
				: glass.x + glass.w + (box.x + box.w - (glass.x + glass.w)) / 2;
		return { x: railCenterX - 2.5, y: box.y + box.h / 2 - 14, w: 5, h: 28 };
	}
	if (cell.node.sashConfig === "door" && cell.node.activeLeaf === false) return null;
	const hSide = side || "left";
	if (hSide === "top") {
		const railCenterY = glass.y + glass.h + (box.y + box.h - (glass.y + glass.h)) / 2;
		return {
			x: box.x + box.w / 2 - 12,
			y: railCenterY - 2.5,
			w: 24,
			h: 5,
		};
	}
	if (hSide === "bottom") {
		const railCenterY = box.y + (glass.y - box.y) / 2;
		return {
			x: box.x + box.w / 2 - 12,
			y: railCenterY - 2.5,
			w: 24,
			h: 5,
		};
	}
	const handleCenterY = box.y + box.h / 2;
	const railCenterX =
		hSide === "left"
			? glass.x + glass.w + (box.x + box.w - (glass.x + glass.w)) / 2
			: box.x + (glass.x - box.x) / 2;
	return {
		x: railCenterX - 2.5,
		y: handleCenterY - 13,
		w: 5,
		h: 26,
	};
}

function computeHingeBlocks(cell: CellGeom, box: Box, side: HingeSide | null): HandlePos[] {
	if (cell.node.type !== "sash" || cell.node.isSliding || !side) return [];
	const isDoor = cell.node.sashConfig === "door";
	const showHinges =
		isDoor || cell.node.hingeStay === "Hinges" || cell.node.hinge_type === "butt";
	if (!showHinges) return [];
	const h = cell.h;
	const count = isDoor ? (h >= 2100 ? 5 : h >= 1400 ? 4 : 3) : h >= 1600 ? 4 : h >= 1100 ? 3 : 2;
	const blocks: HandlePos[] = [];
	if (side === "top" || side === "bottom") {
		const y = side === "top" ? box.y - 1 : box.y + box.h - 3.5;
		for (let i = 0; i < count; i++) {
			const t = (i + 0.5) / count;
			const x = box.x + box.w * (0.12 + 0.76 * t);
			blocks.push({ x: x - 6, y, w: 12, h: 4.5 });
		}
		return blocks;
	}
	const x = side === "left" ? box.x - 1.5 : box.x + box.w - 3;
	for (let i = 0; i < count; i++) {
		const t = count === 1 ? 0.5 : i / (count - 1);
		const y = box.y + box.h * (0.1 + 0.8 * t);
		blocks.push({ x, y: y - 5.5, w: 4.5, h: 11 });
	}
	return blocks;
}

function round1(n: number): number {
	return Math.round(n * 10) / 10;
}

const grills = computed(() => grillMembers(props.design));
const cells = computed<CellView[]>(() => {
	// Fixed panes show only their glass number; F<n> would clash with the frame id.
	const counts: Record<string, number> = { S: 0, L: 0 };
	const memberList = props.members ?? [];
	const glassList = props.glass ?? [];
	return geom.value.cells.map((cell, i) => {
		const prefix = cell.node.type === "sash" ? "S" : cell.node.type === "louver" ? "L" : "";
		const box = cellBox(cell);
		const isSash = cell.node.type === "sash";
		const selected = cell.path === props.selectedPath;
		const glassSelected = props.selectedPath === `GLASS:${cell.path}`;
		const issue = props.issuePaths.includes(cell.path);
		const side = hingeSide(cell);
		const sf = sashFaceFor(cell);
		const glass = isSash ? inset(box, sf) : box;
		const cutAngle = isSash ? roleCutAngle("sash", cell.path) : 45;

		const sashMembers = isSash
			? memberList.filter((m) => m.role === "sash" && m.path === cell.path)
			: [];
		const wMember = sashMembers.find((m) => m.position === "B" || m.position === "T");
		const hMember = sashMembers.find((m) => m.position === "L" || m.position === "R");
		const openW = round1(box.w / scale.value);
		const openH = round1(box.h / scale.value);
		const sashW = isSash
			? wMember?.length !== undefined
				? round1(Number(wMember.length))
				: openW
			: null;
		const sashH = isSash
			? hMember?.length !== undefined
				? round1(Number(hMember.length))
				: openH
			: null;

		const gRow = glassList.find((g) => g.path === cell.path);
		const geomGlassW = round1(glass.w / scale.value);
		const geomGlassH = round1(glass.h / scale.value);
		const glassW = gRow?.width !== undefined ? round1(Number(gRow.width)) : geomGlassW;
		const glassH = gRow?.height !== undefined ? round1(Number(gRow.height)) : geomGlassH;
		const hasBead =
			(cell.node.type === "fixed" || cell.node.type === "sash") && cell.node.bead !== false;
		const beadInsetMm = Math.min(14, Math.max(4, openW * 0.08), Math.max(4, openH * 0.08));
		const beadBox = inset(glass, beadInsetMm);

		return {
			cell,
			box,
			glass,
			panelId: prefix ? `${prefix}${++counts[prefix]}` : "",
			glassNo: i + 1,
			selected,
			glassSelected,
			issue,
			stroke: selected ? C.select : issue ? C.issue : C.stroke,
			strokeWidth: selected ? 3 : issue ? 2 : 1,
			lines: side ? openingLines(glass, side) : [],
			side,
			hingeLine: isSash ? computeHingeLine(box, side) : null,
			hingeBlocks: computeHingeBlocks(cell, box, side),
			isDoor: isSash && cell.node.sashConfig === "door",
			corners: isSash ? cornerLines(box, glass, cutAngle) : [],
			cutAngle,
			handle: computeHandlePos(cell, box, glass, side),
			hasBead,
			beadBox,
			sashW,
			sashH,
			glassW,
			glassH,
			fanCut: exhaustCut(cell.node, glassW, glassH),
		};
	});
});

function louverYs(v: CellView): number[] {
	const node = v.cell.node;
	if (node.type !== "louver" || node.blades < 1) return [];
	const step = v.box.h / node.blades;
	return Array.from({ length: node.blades - 1 }, (_, k) => v.box.y + step * (k + 1));
}

const ghh = computed(() => {
	const sash = geom.value.cells.find((c) => c.node.type === "sash" && c.node.ghh);
	return sash && sash.node.type === "sash" ? sash.node.ghh : null;
});

function barRect(bar: BarGeom): Box {
	const { width, height } = props.design;
	const ff = frameFace.value;
	const bff = bottomFrameFace.value;
	const bf = barFaceFor(bar);
	if (bar.dir === "v") {
		const b = bar.y === 0 ? bff : bf / 2;
		const t = bar.y + bar.length === height ? ff : bf / 2;
		const span = pxSpan(bar.x - bf / 2, bf);
		return {
			x: span.x,
			y: py(bar.y + bar.length - t),
			w: span.w,
			h: Math.max(0, (bar.length - b - t) * scale.value),
		};
	}
	const l = bar.x === 0 ? ff : bf / 2;
	const r = bar.x + bar.length === width ? ff : bf / 2;
	const span = pxSpan(bar.x + l, Math.max(0, bar.length - l - r));
	return {
		x: span.x,
		y: py(bar.y + bf / 2),
		w: span.w,
		h: bf * scale.value,
	};
}

const bars = computed<BarView[]>(() => {
	const memberList = props.members ?? [];
	return geom.value.bars.map((bar) => {
		const rect = barRect(bar);
		const selected = props.selectedPath === bar.id;
		const mRow = memberList.find((m) => m.panel === bar.id || m.path === bar.id);
		const geomCut = round1((bar.dir === "v" ? rect.h : rect.w) / scale.value);
		const cutLength = mRow?.length !== undefined ? round1(Number(mRow.length)) : geomCut;
		const bf = barFaceFor(bar);
		return {
			bar,
			rect,
			selected,
			cutLength,
			spanLength: round1(bar.length),
			faceWidth: bf,
			pos: round1(bar.dir === "v" ? bar.x : bar.y),
		};
	});
});

const frameBox = computed<Box>(() => ({
	x: px(0),
	y: py(props.design.height),
	w: props.design.width * scale.value,
	h: props.design.height * scale.value,
}));

const frameInner = computed<Box>(() => {
	const fb = frameBox.value;
	const ffPx = frameFace.value * scale.value;
	const bfPx = bottomFrameFace.value * scale.value;
	return {
		x: fb.x + ffPx,
		y: fb.y + ffPx,
		w: Math.max(0, fb.w - 2 * ffPx),
		h: Math.max(0, fb.h - ffPx - bfPx),
	};
});
const uFramePath = computed(() => {
	const fb = frameBox.value;
	const fi = frameInner.value;
	return `M ${fmt(fb.x)} ${fmt(fb.y + fb.h)} L ${fmt(fb.x)} ${fmt(fb.y)} L ${fmt(
		fb.x + fb.w
	)} ${fmt(fb.y)} L ${fmt(fb.x + fb.w)} ${fmt(fb.y + fb.h)} L ${fmt(fi.x + fi.w)} ${fmt(
		fb.y + fb.h
	)} L ${fmt(fi.x + fi.w)} ${fmt(fi.y)} L ${fmt(fi.x)} ${fmt(fi.y)} L ${fmt(fi.x)} ${fmt(
		fb.y + fb.h
	)} Z`;
});
const thresholdRect = computed<Box | null>(() => {
	if (frameConfig.value !== "3-side-threshold") return null;
	const fb = frameBox.value;
	const fi = frameInner.value;
	const bfPx = bottomFrameFace.value * scale.value;
	return { x: fi.x, y: fb.y + fb.h - bfPx, w: fi.w, h: bfPx };
});
const frameSelected = computed(
	() =>
		props.selectedPath === "FRAME" ||
		(props.selectedPath === "F1" && props.design.root.type === "split")
);
const frameCutAngle = computed<CutAngle>(() => roleCutAngle("frame", "F1"));
const frameCorners = computed<LineSeg[]>(() => {
	const all = cornerLines(frameBox.value, frameInner.value, frameCutAngle.value);
	if (frameConfig.value === "3-side") return all.slice(0, 2);
	if (frameConfig.value === "3-side-threshold") {
		const fb = frameBox.value;
		const fi = frameInner.value;
		return [
			...all.slice(0, 2),
			{ x1: fb.x, y1: fi.y + fi.h, x2: fi.x, y2: fi.y + fi.h },
			{ x1: fi.x + fi.w, y1: fi.y + fi.h, x2: fb.x + fb.w, y2: fi.y + fi.h },
		];
	}
	return all;
});

const gridMinorPath = computed(() => {
	const step = 36;
	const minX = -GRID_EXTENT;
	const maxX = props.viewW + GRID_EXTENT;
	const minY = -GRID_EXTENT;
	const maxY = props.viewH + GRID_EXTENT;
	const parts: string[] = [];
	for (let x = minX; x <= maxX; x += step) {
		parts.push(`M ${x} ${minY} L ${x} ${maxY}`);
	}
	for (let y = minY; y <= maxY; y += step) {
		parts.push(`M ${minX} ${y} L ${maxX} ${y}`);
	}
	return parts.join(" ");
});

const gridMajorPath = computed(() => "");

interface Dim {
	from: number;
	to: number;
	label: string;
}

function segments(total: number, at: number[]): Dim[] {
	const bounds = [0, ...at, total];
	return bounds.slice(1).map((b, i) => ({ from: bounds[i], to: b, label: fmt(b - bounds[i]) }));
}

const root = computed(() => props.design.root);
const cols = computed<Dim[]>(() => {
	const r = root.value;
	return r.type === "split" && r.dir === "v" ? segments(props.design.width, r.at) : [];
});
const rows = computed<Dim[]>(() => {
	const r = root.value;
	return r.type === "split" && r.dir === "h" ? segments(props.design.height, r.at) : [];
});

/** A–A is the vertical cut line, B–B the horizontal one; the badges sit on the frame member at each end. */
const cuts = computed(() => {
	const s = props.section;
	if (!s) return [];
	const f = frameBox.value;
	const face = (frameFace.value / 2) * scale.value;
	const ends = 10;
	const x = pxPoint(s.v);
	const y = py(s.h);
	return [
		{
			axis: "v" as const,
			letter: "A",
			x1: x,
			x2: x,
			y1: f.y - ends,
			y2: f.y + f.h + ends,
			badges: [
				[x, f.y + face],
				[x, f.y + f.h - face],
			],
		},
		{
			axis: "h" as const,
			letter: "B",
			x1: f.x - ends,
			x2: f.x + f.w + ends,
			y1: y,
			y2: y,
			badges: [
				[f.x + face, y],
				[f.x + f.w - face, y],
			],
		},
	].map((c) => ({ ...c, active: c.axis === s.axis }));
});

function onFrameClick(e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false;
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false;
		return;
	}
	emit("select", "FRAME");
}

function onGlassClick(c: CellGeom, e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false;
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false;
		return;
	}
	emit("select", `GLASS:${c.path}`);
	const s = props.section;
	if (s)
		emit("update:cut", { axis: s.axis, at: s.axis === "h" ? c.y + c.h / 2 : c.x + c.w / 2 });
}

function onCellClick(c: CellGeom, e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false;
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false;
		return;
	}
	emit("select", c.path);
	const s = props.section;
	if (s)
		emit("update:cut", { axis: s.axis, at: s.axis === "h" ? c.y + c.h / 2 : c.x + c.w / 2 });
}

let barSelectedOnPointerDown = false;

function onBarClick(bar: BarGeom, e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false;
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false;
		barSelectedOnPointerDown = false;
		return;
	}
	if (barSelectedOnPointerDown) {
		barSelectedOnPointerDown = false;
		return;
	}
	emit("select", bar.id);
	const s = props.section;
	if (s) emit("update:cut", { axis: s.axis, at: s.axis === "h" ? bar.y : bar.x });
}

function onBackgroundClick(e?: MouseEvent) {
	if (e && !e.shiftKey) shiftHeld.value = false;
	if (suppressNextClick || isPanning.value || e?.shiftKey) {
		suppressNextClick = false;
		return;
	}
	emit("select", "");
}

const ariaLabel = computed(
	() =>
		`Window ${fmt(props.design.width)} by ${fmt(props.design.height)} mm, ${
			geom.value.cells.length
		} panels`
);

function screenToViewFactor(): number {
	const r = svg.value?.getBoundingClientRect();
	// preserveAspectRatio "meet" scales both axes by the smaller ratio.
	const meet =
		r && r.width && r.height ? Math.min(r.width / props.viewW, r.height / props.viewH) : 0;
	return (meet ? 1 / meet : 1) / zoom.value;
}

interface Drag {
	bar: BarGeom;
	start: number;
	original: number;
	el: Element;
	pointerId: number;
}
let drag: Drag | null = null;

interface PanDrag {
	startX: number;
	startY: number;
	origX: number;
	origY: number;
	pointerId: number;
	moved: boolean;
	immediate: boolean;
}
let panDrag: PanDrag | null = null;

function onPointerDown(e: PointerEvent, bar: BarGeom) {
	if (e.shiftKey === false) shiftHeld.value = false;
	if (e.shiftKey || shiftHeld.value) return;
	if (e.button !== 0 && e.button !== undefined) return;
	e.preventDefault();
	e.stopPropagation();
	barSelectedOnPointerDown = true;
	emit("select", bar.id);
	const split = getNode(props.design, bar.splitPath) as SplitNode;
	const el = e.currentTarget as Element;
	drag = {
		bar,
		start: bar.dir === "v" ? e.clientX : e.clientY,
		original: split.at[bar.index],
		el,
		pointerId: e.pointerId,
	};
	if (el.setPointerCapture) el.setPointerCapture(e.pointerId);
	// Belt and braces: the up event may miss the bar, so any of these ends the drag.
	window.addEventListener("pointerup", endDrag);
	window.addEventListener("pointercancel", endDrag);
	emit("drag-start");
}

function onPointerMove(e: PointerEvent) {
	if (!drag) return;
	const vertical = drag.bar.dir === "v";
	const k = screenToViewFactor();
	const cur = vertical ? e.clientX : e.clientY;
	const delta = ((cur - drag.start) * k) / scale.value;
	const signedDelta = vertical && isOutside.value ? -delta : delta;
	const pos = drag.bar.dir === "v" ? drag.original + signedDelta : drag.original - delta;
	emit("move-split", { splitPath: drag.bar.splitPath, index: drag.bar.index, pos });
}

function endDrag() {
	setTimeout(() => {
		barSelectedOnPointerDown = false;
	}, 0);
	if (!drag) return;
	const { el, pointerId } = drag;
	drag = null;
	window.removeEventListener("pointerup", endDrag);
	window.removeEventListener("pointercancel", endDrag);
	if (el.releasePointerCapture && el.hasPointerCapture?.(pointerId))
		el.releasePointerCapture(pointerId);
	emit("drag-end");
}

function onCanvasPointerDown(e: PointerEvent) {
	if (drag) return;
	if (e.shiftKey === false && e.button === 0) shiftHeld.value = false;
	if (e.button !== 0 && e.button !== 1 && e.button !== undefined) return;
	const immediate = Boolean(e.shiftKey || shiftHeld.value || e.button === 1);
	if (immediate) e.preventDefault();
	panDrag = {
		startX: e.clientX,
		startY: e.clientY,
		origX: pan.value.x,
		origY: pan.value.y,
		pointerId: e.pointerId,
		moved: false,
		immediate,
	};
	if (immediate) {
		isPanning.value = true;
		if (svg.value?.setPointerCapture) svg.value.setPointerCapture(e.pointerId);
	}
	window.addEventListener("pointermove", onCanvasPointerMove);
	window.addEventListener("pointerup", endPan);
	window.addEventListener("pointercancel", endPan);
}

function onCanvasPointerMove(e: PointerEvent) {
	if (!panDrag) return;
	const rawDx = e.clientX - panDrag.startX;
	const rawDy = e.clientY - panDrag.startY;
	const dist = Math.hypot(rawDx, rawDy);
	if (!panDrag.immediate && !panDrag.moved) {
		if (dist < 4) return;
		panDrag.moved = true;
		isPanning.value = true;
		if (svg.value?.setPointerCapture) svg.value.setPointerCapture(panDrag.pointerId);
	} else if (dist > 2) {
		panDrag.moved = true;
	}
	const k = screenToViewFactor();
	const dx = rawDx * k;
	const dy = rawDy * k;
	pan.value = {
		x: clampPan(panDrag.origX + dx),
		y: clampPan(panDrag.origY + dy),
	};
}

function endPan() {
	if (!panDrag) return;
	const { pointerId, moved } = panDrag;
	panDrag = null;
	isPanning.value = false;
	if (moved) {
		suppressNextClick = true;
		setTimeout(() => {
			suppressNextClick = false;
		}, 0);
	}
	window.removeEventListener("pointermove", onCanvasPointerMove);
	window.removeEventListener("pointerup", endPan);
	window.removeEventListener("pointercancel", endPan);
	if (svg.value?.releasePointerCapture && svg.value.hasPointerCapture?.(pointerId)) {
		svg.value.releasePointerCapture(pointerId);
	}
}

function onWheel(e: WheelEvent) {
	if (e.deltaY === 0) return;
	e.preventDefault();
	if (e.deltaY < 0) zoomIn();
	else zoomOut();
}

function isEditableTarget(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) return false;
	const tag = target.tagName;
	return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

function onKeyDown(e: KeyboardEvent) {
	if (e.key === "Shift" || e.shiftKey) shiftHeld.value = true;
	if (isEditableTarget(e.target)) return;
	if (e.key === "+" || e.key === "=") {
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
		panBy(PAN_KEY_STEP, 0);
	} else if (e.key === "ArrowRight") {
		e.preventDefault();
		panBy(-PAN_KEY_STEP, 0);
	} else if (e.key === "ArrowUp") {
		e.preventDefault();
		panBy(0, PAN_KEY_STEP);
	} else if (e.key === "ArrowDown") {
		e.preventDefault();
		panBy(0, -PAN_KEY_STEP);
	}
}

function onKeyUp(e: KeyboardEvent) {
	if (e.key === "Shift" || !e.shiftKey) shiftHeld.value = false;
}

function onWindowBlur() {
	shiftHeld.value = false;
}

onMounted(() => {
	window.addEventListener("keydown", onKeyDown);
	window.addEventListener("keyup", onKeyUp);
	window.addEventListener("blur", onWindowBlur);
});

onUnmounted(() => {
	endDrag();
	endPan();
	window.removeEventListener("keydown", onKeyDown);
	window.removeEventListener("keyup", onKeyUp);
	window.removeEventListener("blur", onWindowBlur);
});

function getSvgMarkup(): string {
	if (!svg.value) return "";
	const clone = svg.value.cloneNode(true) as SVGSVGElement;
	clone.removeAttribute("style");
	clone.querySelectorAll("[data-cut], [data-highlight]").forEach((el) => el.remove());
	clone.setAttribute("viewBox", `0 0 ${props.viewW} ${props.viewH}`);
	clone.setAttribute("width", String(props.viewW));
	clone.setAttribute("height", String(props.viewH));
	const bgRect = clone.querySelector("rect");
	if (bgRect) {
		bgRect.setAttribute("x", "0");
		bgRect.setAttribute("y", "0");
		bgRect.setAttribute("width", String(props.viewW));
		bgRect.setAttribute("height", String(props.viewH));
	}
	clone.querySelectorAll("*").forEach((el) => {
		for (const a of Array.from(el.attributes)) {
			if (a.name.startsWith("data-") || a.name === "style") el.removeAttribute(a.name);
		}
		if (el.classList.contains("hl")) {
			el.setAttribute("stroke", C.stroke);
			el.setAttribute("stroke-width", "1");
			if (
				el.getAttribute("fill") === C.selectFill ||
				el.getAttribute("fill") === C.barSelectFill
			) {
				el.setAttribute("fill", frameFill.value);
			}
			el.removeAttribute("class");
		}
		if (el.classList.contains("hl-badge")) {
			el.setAttribute("fill", "#FFFFFF");
			el.setAttribute("stroke", C.dim);
			el.removeAttribute("class");
		}
		if (el.classList.contains("hl-badge-text")) {
			el.setAttribute("fill", C.dim);
			el.removeAttribute("class");
		}
	});
	return clone.outerHTML;
}
defineExpose({ getSvgMarkup, zoom, pan, zoomIn, zoomOut, resetView, panBy });
</script>

<template>
	<div
		class="relative flex h-full w-full flex-1 items-center justify-center overflow-hidden bg-[#f7f8fa] select-none"
	>
		<div
			v-if="dragOverEmpty"
			class="pointer-events-none absolute inset-3 z-20 rounded-lg border-2 border-dashed border-[#1a6fd4]/55 bg-[#1a6fd4]/[0.03]"
		/>
		<div
			v-if="dragOverEmpty"
			data-testid="window-canvas-drop-badge"
			class="pointer-events-none absolute top-4 left-1/2 z-30 -translate-x-1/2 rounded-full border border-[#1a6fd4]/40 bg-[#e6effb]/95 px-3.5 py-1 text-xs font-semibold text-[#1a6fd4] shadow-sm backdrop-blur-sm"
		>
			Drop in empty space to replace design
		</div>
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
			:style="{ cursor: isPanning ? 'grabbing' : 'grab' }"
			@wheel="onWheel"
			@pointerdown="onCanvasPointerDown"
			@pointermove="onCanvasPointerMove"
			@dragover="onSvgDragOver"
			@dragleave="
				dragOverPath = null;
				dragOverEmpty = false;
			"
			@drop="onSvgDrop"
			@pointerup="endPan"
			@pointercancel="endPan"
			@lostpointercapture="endPan"
		>
			<title data-view-label="true">
				{{ view === "inside" ? "View from inside" : "View from outside" }}
			</title>
			<defs>
				<marker
					id="eva-dim-arrow"
					markerWidth="7"
					markerHeight="7"
					refX="6"
					refY="3.5"
					orient="auto-start-reverse"
				>
					<path d="M0 0L7 3.5 0 7z" fill="#666666" />
				</marker>
				<marker
					id="eva-slide-arrow"
					markerWidth="8"
					markerHeight="8"
					refX="7"
					refY="4"
					orient="auto"
				>
					<path d="M0 1L8 4 0 7z" fill="#1E293B" />
				</marker>
				<pattern id="eva-mesh-pat" width="8" height="8" patternUnits="userSpaceOnUse">
					<path
						d="M0 4L4 0L8 4L4 8Z"
						fill="none"
						stroke="#475569"
						stroke-width="0.6"
						opacity="0.45"
					/>
				</pattern>
			</defs>
			<rect
				data-workspace-bg="true"
				:x="-GRID_EXTENT"
				:y="-GRID_EXTENT"
				:width="viewW + GRID_EXTENT * 2"
				:height="viewH + GRID_EXTENT * 2"
				fill="#F7F8FA"
				@click="onBackgroundClick($event)"
			/>
			<g pointer-events="none">
				<path
					:d="gridMinorPath"
					fill="none"
					stroke="#E2E5EA"
					stroke-width="1"
					vector-effect="non-scaling-stroke"
				/>
			</g>
			<rect
				data-frame="FRAME"
				:x="frameBox.x"
				:y="frameBox.y"
				:width="frameBox.w"
				:height="frameBox.h"
				:fill="
					frameConfig === '4-side'
						? frameSelected
							? C.selectFill
							: frameFill
						: 'transparent'
				"
				:stroke="frameConfig === '4-side' ? C.stroke : 'none'"
				:stroke-width="1"
				:class="{ hl: frameSelected }"
				style="cursor: pointer"
				@click="onFrameClick($event)"
			/>
			<path
				v-if="frameConfig !== '4-side'"
				data-frame-u="true"
				:d="uFramePath"
				:fill="frameSelected ? C.selectFill : frameFill"
				:stroke="C.stroke"
				stroke-width="1"
				:class="{ hl: frameSelected }"
				pointer-events="none"
			/>
			<g v-if="thresholdRect" pointer-events="none">
				<rect
					data-threshold="true"
					:x="thresholdRect.x"
					:y="thresholdRect.y"
					:width="thresholdRect.w"
					:height="thresholdRect.h"
					fill="#CBD5E1"
					stroke="#1E293B"
					stroke-width="1"
				/>
				<line
					:x1="thresholdRect.x"
					:y1="thresholdRect.y + thresholdRect.h / 2"
					:x2="thresholdRect.x + thresholdRect.w"
					:y2="thresholdRect.y + thresholdRect.h / 2"
					stroke="#475569"
					stroke-width="0.9"
				/>
			</g>
			<g v-if="frameConfig === '3-side'" pointer-events="none">
				<line
					:x1="frameBox.x"
					:y1="frameBox.y + frameBox.h"
					:x2="frameBox.x + frameBox.w"
					:y2="frameBox.y + frameBox.h"
					stroke="#64748B"
					stroke-dasharray="5 3"
					stroke-width="1.3"
				/>
				<text
					:x="frameBox.x + frameBox.w / 2"
					:y="frameBox.y + frameBox.h + 12"
					text-anchor="middle"
					font-size="10"
					fill="#64748B"
				>
					Open Bottom (3 Side Frame)
				</text>
			</g>
			<rect
				:x="frameInner.x"
				:y="frameInner.y"
				:width="frameInner.w"
				:height="frameInner.h"
				fill="none"
				:stroke="C.stroke"
				stroke-width="1"
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
					:fill="
						v.cell.node.type === 'sash'
							? v.selected
								? C.selectFill
								: sashFill
							: v.cell.node.fan
							? '#A8ADB5'
							: v.cell.node.itemType === 'Panel' || v.cell.node.addon === 'Panel'
							? '#CBD5E1'
							: C.glass
					"
					:stroke="dragOverPath === v.cell.path ? C.select : v.stroke"
					:stroke-width="dragOverPath === v.cell.path ? 3 : v.strokeWidth"
					:class="{
						hl: v.stroke !== C.stroke || (v.selected && v.cell.node.type === 'sash'),
					}"
					style="cursor: pointer"
					@click="onCellClick(v.cell, $event)"
					@dragover="onCellDragOver(v.cell.path, $event)"
					@drop="onCellDrop(v.cell.path, $event)"
				/>
				<rect
					v-if="dragOverPath === v.cell.path"
					:x="v.box.x + 2"
					:y="v.box.y + 2"
					:width="Math.max(0, v.box.w - 4)"
					:height="Math.max(0, v.box.h - 4)"
					fill="#1A6FD4"
					fill-opacity="0.14"
					stroke="#1A6FD4"
					stroke-width="2"
					stroke-dasharray="6 4"
					pointer-events="none"
				/>
				<rect
					v-if="v.cell.node.type === 'sash'"
					:data-glass="v.cell.path"
					:x="v.glass.x"
					:y="v.glass.y"
					:width="v.glass.w"
					:height="v.glass.h"
					:fill="
						v.cell.node.fan
							? '#A8ADB5'
							: v.cell.node.itemType === 'Panel' || v.cell.node.addon === 'Panel'
							? '#CBD5E1'
							: C.glass
					"
					:stroke="v.glassSelected ? '#1A6FD4' : '#6B8A99'"
					:stroke-width="v.glassSelected ? 2.5 : 1"
					:class="{ hl: v.glassSelected }"
					style="cursor: pointer"
					@click.stop="onGlassClick(v.cell, $event)"
					@dragover="onCellDragOver(v.cell.path, $event)"
					@drop="onCellDrop(v.cell.path, $event)"
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
					stroke-width="1.1"
					stroke-linecap="square"
					vector-effect="non-scaling-stroke"
					pointer-events="none"
				/>
				<polyline
					v-for="(pts, i) in v.lines"
					:key="i"
					:points="pts"
					fill="none"
					stroke="#444444"
					stroke-dasharray="4 4"
					stroke-width="1.2"
					pointer-events="none"
				/>
				<!-- Sliding Shutter Direction Arrow or Fixed Cross (+) -->
				<g
					v-if="v.cell.node.type === 'sash' && v.cell.node.isSliding"
					data-sliding-symbol="true"
					pointer-events="none"
				>
					<template v-if="v.cell.node.slideFixed">
						<line
							:x1="v.glass.x + v.glass.w / 2 - 11"
							:y1="v.glass.y + v.glass.h * 0.54"
							:x2="v.glass.x + v.glass.w / 2 + 11"
							:y2="v.glass.y + v.glass.h * 0.54"
							stroke="#1E293B"
							stroke-width="1.6"
						/>
						<line
							:x1="v.glass.x + v.glass.w / 2"
							:y1="v.glass.y + v.glass.h * 0.54 - 11"
							:x2="v.glass.x + v.glass.w / 2"
							:y2="v.glass.y + v.glass.h * 0.54 + 11"
							stroke="#1E293B"
							stroke-width="1.6"
						/>
					</template>
					<line
						v-else
						:x1="
							effectiveSlideDir(v.cell.node.slideDir) === 'left'
								? v.glass.x + v.glass.w * 0.72
								: v.glass.x + v.glass.w * 0.28
						"
						:y1="v.glass.y + v.glass.h * 0.54"
						:x2="
							effectiveSlideDir(v.cell.node.slideDir) === 'left'
								? v.glass.x + v.glass.w * 0.28
								: v.glass.x + v.glass.w * 0.72
						"
						:y2="v.glass.y + v.glass.h * 0.54"
						stroke="#1E293B"
						stroke-width="1.8"
						marker-end="url(#eva-slide-arrow)"
					/>
				</g>
				<!-- Mesh Crosshatch Overlay -->
				<rect
					v-if="v.cell.node.mesh || v.cell.node.meshType"
					data-mesh-overlay="true"
					:x="v.glass.x"
					:y="v.glass.y"
					:width="v.glass.w"
					:height="v.glass.h"
					fill="url(#eva-mesh-pat)"
					pointer-events="none"
				/>
				<!-- Railing Add-on Overlay -->
				<g
					v-if="v.cell.node.addon === 'Railing'"
					data-addon-railing="true"
					pointer-events="none"
				>
					<line
						:x1="v.glass.x + 2"
						:y1="v.glass.y + v.glass.h * 0.58"
						:x2="v.glass.x + v.glass.w - 2"
						:y2="v.glass.y + v.glass.h * 0.58"
						stroke="#334155"
						stroke-width="3"
					/>
					<line
						v-for="ri in 5"
						:key="`rl${ri}`"
						:x1="v.glass.x + (v.glass.w * ri) / 6"
						:y1="v.glass.y + v.glass.h * 0.58"
						:x2="v.glass.x + (v.glass.w * ri) / 6"
						:y2="v.glass.y + v.glass.h - 2"
						stroke="#475569"
						stroke-width="1.5"
					/>
				</g>
				<!-- AC Unit Add-on Overlay -->
				<g v-if="v.cell.node.addon === 'AC'" data-addon-ac="true" pointer-events="none">
					<rect
						:x="v.glass.x + v.glass.w * 0.14"
						:y="v.glass.y + v.glass.h * 0.58"
						:width="v.glass.w * 0.72"
						:height="v.glass.h * 0.34"
						rx="3"
						fill="#E2E8F0"
						stroke="#334155"
						stroke-width="1.4"
					/>
					<line
						v-for="ai in 4"
						:key="`ac${ai}`"
						:x1="v.glass.x + v.glass.w * 0.2"
						:y1="v.glass.y + v.glass.h * (0.63 + ai * 0.055)"
						:x2="v.glass.x + v.glass.w * 0.62"
						:y2="v.glass.y + v.glass.h * (0.63 + ai * 0.055)"
						stroke="#475569"
						stroke-width="1.2"
					/>
					<circle
						:cx="v.glass.x + v.glass.w * 0.74"
						:cy="v.glass.y + v.glass.h * 0.75"
						r="5"
						fill="#94A3B8"
						stroke="#334155"
						stroke-width="1"
					/>
				</g>
				<line
					v-for="(y, i) in louverYs(v)"
					:key="`l${i}`"
					:x1="v.box.x"
					:x2="v.box.x + v.box.w"
					:y1="y"
					:y2="y"
					stroke="#475569"
					stroke-width="1.6"
					pointer-events="none"
				/>
				<!-- Physical hole, scaled from its glass-relative millimetre coordinates. -->
				<g
					v-if="v.fanCut"
					pointer-events="none"
					data-testid="exhaust-cut"
					:transform="`translate(${
						v.glass.x +
						((isOutside ? v.glassW - v.fanCut.centerX : v.fanCut.centerX) *
							v.glass.w) /
							v.glassW
					}, ${v.glass.y + (v.fanCut.centerY * v.glass.h) / v.glassH})`"
				>
					<ellipse
						:rx="((v.fanCut.diameter / 2) * v.glass.w) / v.glassW"
						:ry="((v.fanCut.diameter / 2) * v.glass.h) / v.glassH"
						fill="white"
						:stroke="C.dim"
						stroke-width="1.4"
					/>
					<path d="M-6 0 H6 M0 -6 V6" :stroke="C.dim" stroke-width="0.8" />
					<text
						:y="((-v.fanCut.diameter / 2) * v.glass.h) / v.glassH - 5"
						text-anchor="middle"
						font-size="10"
						:fill="C.dim"
					>
						Ø{{ v.fanCut.diameter }} cut
					</text>
				</g>
				<g data-testid="grill-elevation">
					<rect
						v-for="(bar, index) in grills.filter((b) => b.path === v.cell.path)"
						:key="index"
						:x="pxSpan(bar.x, bar.w).x"
						:y="py(bar.y + bar.h)"
						:width="bar.w * scale"
						:height="bar.h * scale"
						:fill="v.selected ? '#3B5998' : '#616873'"
						stroke="#424955"
						stroke-width="0.5"
						@click.stop="onCellClick(v.cell, $event)"
					/>
				</g>
				<!-- Casement Handle & Hinge Barrels -->
				<rect
					v-for="(hb, hi) in v.hingeBlocks"
					:key="`hb${hi}`"
					data-hinge-block="true"
					:x="hb.x"
					:y="hb.y"
					:width="hb.w"
					:height="hb.h"
					rx="1"
					:fill="view === 'outside' ? '#1E293B' : '#FFFFFF'"
					stroke="#1E293B"
					stroke-width="1"
					pointer-events="none"
				/>
				<g v-if="v.handle" pointer-events="none">
					<template v-if="v.isDoor">
						<!-- Centered Euro door backplate -->
						<rect
							data-handle="true"
							:x="v.handle.x + v.handle.w / 2 - 3.5"
							:y="v.handle.y + v.handle.h / 2 - 15"
							width="7"
							height="30"
							rx="2"
							fill="#334155"
							stroke="#1E293B"
							stroke-width="0.9"
						/>
						<!-- Lever points inward over the sash glass (opposite hinge side) -->
						<rect
							data-handle-lever="true"
							:x="
								v.side === 'right'
									? v.handle.x + v.handle.w / 2 - 1.5
									: v.side === 'left'
									? v.handle.x + v.handle.w / 2 - 12.5
									: v.handle.x + v.handle.w / 2 - 7
							"
							:y="v.handle.y + v.handle.h / 2 - 7"
							width="14"
							height="4"
							rx="1.8"
							fill="#1E293B"
							stroke="#0F172A"
							stroke-width="0.6"
						/>
						<!-- Euro lock cylinder keyhole -->
						<circle
							:cx="v.handle.x + v.handle.w / 2"
							:cy="v.handle.y + v.handle.h / 2 + 5.5"
							r="2.1"
							fill="#FFFFFF"
							stroke="#1E293B"
							stroke-width="0.8"
						/>
						<rect
							:x="v.handle.x + v.handle.w / 2 - 0.85"
							:y="v.handle.y + v.handle.h / 2 + 7"
							width="1.7"
							height="3.4"
							rx="0.5"
							fill="#FFFFFF"
						/>
					</template>
					<template v-else>
						<rect
							data-handle="true"
							:x="v.handle.x"
							:y="v.handle.y"
							:width="v.handle.w"
							:height="v.handle.h"
							rx="1.5"
							fill="#475569"
							stroke="#1E293B"
							stroke-width="0.9"
						/>
						<circle
							:cx="v.handle.x + v.handle.w / 2"
							:cy="v.handle.y + v.handle.h / 2"
							r="1.4"
							fill="#CBD5E1"
						/>
					</template>
				</g>
				<!-- Centered Top-Rail Sash / Louver Tag Badge (S1 / S2 / L1 — Exact Prototype Placement) -->
				<g
					v-if="v.panelId"
					:data-panel-badge="v.cell.path"
					style="cursor: pointer"
					@click.stop="onCellClick(v.cell, $event)"
				>
					<rect
						:x="v.box.x + v.box.w / 2 - 15"
						:y="v.box.y + 4"
						width="30"
						height="18"
						rx="2"
						fill="#FFFFFF"
						stroke="#222222"
						stroke-width="1.1"
					/>
					<text
						:x="v.box.x + v.box.w / 2"
						:y="v.box.y + 17"
						text-anchor="middle"
						font-size="11.5"
						font-weight="600"
						fill="#222222"
					>
						{{ v.panelId }}
					</text>
				</g>
				<!-- Prototype Centered GHH Pill inside Active Casement Sash -->
				<g
					v-if="
						v.cell.node.type === 'sash' &&
						!v.cell.node.isSliding &&
						v.cell.node.ghh &&
						(!v.isDoor || v.cell.node.activeLeaf !== false)
					"
					pointer-events="none"
				>
					<rect
						:x="v.box.x + v.box.w / 2 - 34"
						:y="v.box.y + v.box.h * 0.56 - 9"
						width="68"
						height="18"
						rx="2"
						fill="#FFFFFF"
						stroke="#222222"
						stroke-width="1.1"
					/>
					<text
						:x="v.box.x + v.box.w / 2"
						:y="v.box.y + v.box.h * 0.56 + 4"
						text-anchor="middle"
						font-size="10.5"
						font-weight="600"
						fill="#222222"
					>
						GHH = {{ fmt(v.cell.node.ghh) }}
					</text>
				</g>
				<!-- Prototype Light-Blue OUT / IN Pill inside Casement Sash -->
				<g
					v-if="
						v.cell.node.type === 'sash' &&
						!v.cell.node.isSliding &&
						v.cell.node.opening
					"
					pointer-events="none"
				>
					<rect
						:x="v.box.x + v.box.w / 2 - 19"
						:y="v.box.y + v.box.h * 0.68 - 9.5"
						width="38"
						height="19"
						rx="2"
						fill="#E4F4FA"
						stroke="#5AA6C9"
						stroke-width="1.1"
					/>
					<text
						:x="v.box.x + v.box.w / 2"
						:y="v.box.y + v.box.h * 0.68 + 4"
						text-anchor="middle"
						font-size="11"
						font-weight="600"
						fill="#3D8BB0"
					>
						{{ v.cell.node.opening === "out" ? "OUT" : "IN" }}
					</text>
				</g>
				<!-- Prototype Circled Pane Number (1, 2...) -->
				<g
					:data-glass-badge="v.cell.path"
					style="cursor: pointer"
					@click.stop="onGlassClick(v.cell, $event)"
				>
					<circle
						:cx="v.box.x + v.box.w / 2"
						:cy="v.box.y + v.box.h * 0.4"
						r="12"
						:fill="v.glassSelected ? '#1A6FD4' : '#FFFFFF'"
						:stroke="v.glassSelected ? '#1A6FD4' : '#111111'"
						stroke-width="1.2"
						:class="{ 'hl-badge': v.glassSelected }"
					/>
					<text
						:x="v.box.x + v.box.w / 2"
						:y="v.box.y + v.box.h * 0.4 + 4"
						text-anchor="middle"
						font-size="12"
						font-weight="600"
						:fill="v.glassSelected ? '#FFFFFF' : '#111111'"
						:class="{ 'hl-badge-text': v.glassSelected }"
					>
						{{ v.glassNo }}
					</text>
				</g>
			</g>

			<!-- Mitres sit above the glass fill so the joint stays a true 45° line. -->
			<g pointer-events="none" :stroke="C.stroke" stroke-width="1.2" stroke-linecap="square">
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

			<!-- Dividers (Mullions / Transoms) with Prototype Centered Tag Badge (M1 / T1) -->
			<g v-for="b in bars" :key="b.bar.id">
				<rect
					:data-bar="b.bar.id"
					:x="b.rect.x"
					:y="b.rect.y"
					:width="b.rect.w"
					:height="b.rect.h"
					:fill="b.selected ? C.barSelectFill : frameFill"
					:stroke="b.selected ? C.select : C.stroke"
					:stroke-width="b.selected ? 2 : 1"
					:class="{ hl: b.selected }"
					:style="{
						cursor: b.bar.dir === 'v' ? 'ew-resize' : 'ns-resize',
						touchAction: 'none',
					}"
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
						:x="b.rect.x + b.rect.w / 2 - 13"
						:y="b.rect.y + b.rect.h / 2 - 9"
						width="26"
						height="18"
						rx="2"
						fill="#FFFFFF"
						stroke="#222222"
						stroke-width="1.1"
					/>
					<text
						:x="b.rect.x + b.rect.w / 2"
						:y="b.rect.y + b.rect.h / 2 + 4"
						text-anchor="middle"
						font-size="11"
						font-weight="600"
						fill="#222222"
					>
						{{ b.bar.id }}
					</text>
				</g>
			</g>

			<!-- Prototype F1 Outer Frame Corner Tag Badge -->
			<g data-frame-badge="FRAME" style="cursor: pointer" @click="onFrameClick($event)">
				<rect
					:x="frameBox.x + frameBox.w - frameFace * scale - 28"
					:y="frameBox.y + frameBox.h - bottomFrameFace * scale - 24"
					width="28"
					height="20"
					rx="2"
					fill="#FFFFFF"
					stroke="#222222"
					stroke-width="1.1"
				/>
				<text
					:x="frameBox.x + frameBox.w - frameFace * scale - 14"
					:y="frameBox.y + frameBox.h - bottomFrameFace * scale - 10"
					text-anchor="middle"
					font-size="11.5"
					font-weight="600"
					fill="#222222"
				>
					F1
				</text>
			</g>

			<!-- Subtle Issue Outlines & Hinge Side Indicator Lines -->
			<g pointer-events="none">
				<template v-for="v in cells" :key="`ov-${v.cell.path}`">
					<rect
						v-if="v.issue"
						data-highlight="true"
						:x="v.box.x"
						:y="v.box.y"
						:width="v.box.w"
						:height="v.box.h"
						fill="none"
						:stroke="C.issue"
						stroke-width="2"
					/>
					<line
						v-if="v.hingeLine"
						data-hinge-line="true"
						:x1="v.hingeLine.x1"
						:y1="v.hingeLine.y1"
						:x2="v.hingeLine.x2"
						:y2="v.hingeLine.y2"
						:stroke="C.cut"
						stroke-width="1.5"
						stroke-opacity="0.7"
						stroke-linecap="round"
					/>
				</template>
			</g>

			<!-- Section Cut Markers -->
			<g
				v-for="c in cuts"
				:key="c.axis"
				:data-cut="c.axis"
				:opacity="c.active ? 1 : 0.35"
				pointer-events="none"
			>
				<line
					:x1="c.x1"
					:x2="c.x2"
					:y1="c.y1"
					:y2="c.y2"
					:stroke="C.cut"
					:stroke-width="c.active ? 2 : 1"
					stroke-dasharray="12 4 3 4"
				/>
				<g v-for="([bx, by], i) in c.badges" :key="i">
					<circle :cx="bx" :cy="by" r="9" fill="#FFFFFF" :stroke="C.cut" />
					<text
						:x="bx"
						:y="by + 4"
						text-anchor="middle"
						font-size="12"
						font-weight="700"
						:fill="C.cut"
					>
						{{ c.letter }}
					</text>
				</g>
			</g>

			<!-- Prototype Always-On CAD Dimension Chains (Bay Widths + Total Width + Total Height) -->
			<g stroke="#777777" fill="#222222" font-size="12">
				<!-- Bay Widths -->
				<g v-for="(d, i) in cols" :key="`c${i}`">
					<line
						:x1="Math.min(pxPoint(d.from), pxPoint(d.to))"
						:x2="Math.max(pxPoint(d.from), pxPoint(d.to))"
						:y1="frameBox.y + frameBox.h + 24"
						:y2="frameBox.y + frameBox.h + 24"
						marker-start="url(#eva-dim-arrow)"
						marker-end="url(#eva-dim-arrow)"
					/>
					<rect
						:x="(pxPoint(d.from) + pxPoint(d.to)) / 2 - 24"
						:y="frameBox.y + frameBox.h + 14"
						width="48"
						height="20"
						rx="2"
						fill="#FFFFFF"
						stroke="#DFE4EC"
						stroke-width="1"
					/>
					<text
						:x="(pxPoint(d.from) + pxPoint(d.to)) / 2"
						:y="frameBox.y + frameBox.h + 28"
						text-anchor="middle"
						font-size="11.5"
						font-weight="600"
						stroke="none"
					>
						{{ d.label }}
					</text>
				</g>
				<!-- Total Width (clickable to edit) -->
				<line
					:x1="frameBox.x"
					:x2="frameBox.x + frameBox.w"
					:y1="frameBox.y + frameBox.h + (cols.length ? 52 : 28)"
					:y2="frameBox.y + frameBox.h + (cols.length ? 52 : 28)"
					marker-start="url(#eva-dim-arrow)"
					marker-end="url(#eva-dim-arrow)"
				/>
				<g style="cursor: pointer" @click="emit('edit-dim', 'w')">
					<rect
						:x="frameBox.x + frameBox.w / 2 - 30"
						:y="frameBox.y + frameBox.h + (cols.length ? 41 : 17)"
						width="60"
						height="22"
						rx="2"
						fill="#FFFFFF"
						stroke="#DFE4EC"
						stroke-width="1"
					/>
					<text
						:x="frameBox.x + frameBox.w / 2"
						:y="frameBox.y + frameBox.h + (cols.length ? 56 : 32)"
						text-anchor="middle"
						font-size="13"
						font-weight="600"
						stroke="none"
					>
						{{ fmt(design.width) }}
					</text>
				</g>

				<!-- Row Heights -->
				<g v-for="(d, i) in rows" :key="`r${i}`">
					<line
						:x1="frameBox.x - 20"
						:x2="frameBox.x - 20"
						:y1="py(d.from)"
						:y2="py(d.to)"
						marker-start="url(#eva-dim-arrow)"
						marker-end="url(#eva-dim-arrow)"
					/>
					<g
						:transform="`translate(${frameBox.x - 20} ${
							(py(d.from) + py(d.to)) / 2
						}) rotate(-90)`"
					>
						<rect
							x="-24"
							y="-10"
							width="48"
							height="20"
							rx="2"
							fill="#FFFFFF"
							stroke="#DFE4EC"
							stroke-width="1"
						/>
						<text
							x="0"
							y="4"
							text-anchor="middle"
							font-size="11.5"
							font-weight="600"
							stroke="none"
						>
							{{ d.label }}
						</text>
					</g>
				</g>
				<!-- Total Height (clickable to edit) -->
				<line
					:x1="frameBox.x - (rows.length ? 48 : 34)"
					:x2="frameBox.x - (rows.length ? 48 : 34)"
					:y1="frameBox.y"
					:y2="frameBox.y + frameBox.h"
					marker-start="url(#eva-dim-arrow)"
					marker-end="url(#eva-dim-arrow)"
				/>
				<g
					style="cursor: pointer"
					:transform="`translate(${frameBox.x - (rows.length ? 48 : 34)} ${
						frameBox.y + frameBox.h / 2
					}) rotate(-90)`"
					@click="emit('edit-dim', 'h')"
				>
					<rect
						x="-28"
						y="-11"
						width="56"
						height="22"
						rx="2"
						fill="#FFFFFF"
						stroke="#DFE4EC"
						stroke-width="1"
					/>
					<text
						x="0"
						y="4.5"
						text-anchor="middle"
						font-size="13"
						font-weight="600"
						stroke="none"
					>
						{{ fmt(design.height) }}
					</text>
				</g>
			</g>
		</svg>

		<!-- Compact Bottom-Right Zoom Controls -->
		<div
			class="pointer-events-auto absolute right-3 bottom-3 flex items-center gap-0.5 rounded-[4px] border border-[#dcdfe4] bg-white/95 px-1 py-0.5 shadow-xs"
			role="toolbar"
			aria-label="Workspace controls"
		>
			<button
				type="button"
				aria-label="Zoom out"
				title="Zoom out (-)"
				:disabled="zoom <= MIN_ZOOM"
				class="flex h-6 w-6 items-center justify-center rounded text-sm font-semibold text-[#444] hover:bg-[#f0f1f3] disabled:opacity-40"
				@click="zoomOut"
			>
				−
			</button>
			<button
				type="button"
				aria-label="Reset zoom"
				title="Reset view (0)"
				class="min-w-11 rounded px-1 py-0.5 text-center font-mono text-[11px] font-medium text-[#444] hover:bg-[#f0f1f3]"
				@click="resetView"
			>
				{{ Math.round(zoom * 100) }}%
			</button>
			<button
				type="button"
				aria-label="Zoom in"
				title="Zoom in (+)"
				:disabled="zoom >= MAX_ZOOM"
				class="flex h-6 w-6 items-center justify-center rounded text-sm font-semibold text-[#444] hover:bg-[#f0f1f3] disabled:opacity-40"
				@click="zoomIn"
			>
				+
			</button>
		</div>
	</div>
</template>
