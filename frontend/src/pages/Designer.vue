<script setup lang="ts">
import { Alert, Button, Tooltip, toast, useList } from "frappe-ui";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import {
	copyDesign,
	getDesign,
	getFenestrationDefaults,
	saveDesign,
	type CutAxis,
	type SavedDesign,
} from "@/api";
import PropertiesPanel, { type Meta } from "@/components/PropertiesPanel.vue";
import ResultsBar from "@/components/ResultsBar.vue";
import Approx3DView from "@/components/Approx3DView.vue";
import Window3DView from "@/components/Window3DView.vue";
import WindowCanvas from "@/components/WindowCanvas.vue";
import SectionView from "@/components/SectionView.vue";
import { generateElevationSvg } from "@/design/elevationSvg";
import { EVA_CATALOG, type EvaCatalogItem } from "@/design/evaCatalog";
import { layoutGeom } from "@/design/geometry";
import { TEMPLATES } from "@/design/templates";
import { typology } from "@/design/typology";
import {
	getNode,
	moveSplit,
	newDesign,
	removeSplit,
	setLeaf,
	splitCell,
	splitCellWithCount,
} from "@/design/tree";
import type { Design, LeafNode, SectionPieceTransform, SplitDir } from "@/design/types";
import { printPdfUrl } from "@/print";
import { useDesignerStore } from "@/stores/designer";

interface FinishRow {
	name: string;
	finish_name: string;
	color: string;
	finish_type?: string;
}

interface SeriesVersionRow {
	name: string;
	series: string;
	version_note?: string;
	docstatus?: number;
}

const store = useDesignerStore();
const route = useRoute();
const router = useRouter();
const project = computed(() => String(route.params.project));
const savedName = computed(() => (route.params.name ? String(route.params.name) : null));
const cuttingSheetUrl = computed(() =>
	savedName.value
		? printPdfUrl("Window Design", savedName.value, "Window Cutting Sheet")
		: undefined
);

const meta = ref<Meta>({ ref: "", qty: 1, floor: "", location: "" });
const refError = ref("");
const viewSide = ref<"inside" | "outside">("inside");
const viewMode = ref<"2d" | "3d" | "realistic3d">("2d");
const sashesOpen = ref(false);
const approx3d = ref<InstanceType<typeof Approx3DView> | null>(null);
const realistic3d = ref<InstanceType<typeof Window3DView> | null>(null);
const evaToast = ref("");
let evaToastTimer: ReturnType<typeof setTimeout> | null = null;

function showEvaToast(msg: string) {
	evaToast.value = msg;
	if (evaToastTimer) clearTimeout(evaToastTimer);
	evaToastTimer = setTimeout(() => {
		evaToast.value = "";
	}, 2600);
}

function toggle3DView(target: "3d" | "realistic3d") {
	if (viewMode.value === target) {
		viewMode.value = "2d";
	} else {
		viewMode.value = target;
		activePalette.value = null;
		specPopover.value.open = false;
	}
}

function fitToView() {
	if (viewMode.value === "3d") {
		approx3d.value?.resetCam?.();
	} else if (viewMode.value === "realistic3d") {
		realistic3d.value?.resetCam?.();
	} else {
		canvas.value?.resetView?.();
	}
	showEvaToast("Fit to view");
}

const dimModal = ref<{ open: boolean; axis: "w" | "h"; val: number }>({
	open: false,
	axis: "w",
	val: 1200,
});
function openDimModal(axis: "w" | "h") {
	dimModal.value = {
		open: true,
		axis,
		val: axis === "w" ? store.design.width : store.design.height,
	};
}
function applyDimModal() {
	const v = Math.max(300, Math.min(6000, Number(dimModal.value.val) || 1200));
	const w = dimModal.value.axis === "w" ? v : store.design.width;
	const h = dimModal.value.axis === "h" ? v : store.design.height;
	store.apply((d) => ({ ...d, width: w, height: h }));
	dimModal.value.open = false;
	showEvaToast(`Resized to ${w} × ${h} mm`);
}

const frameConfigLabel = computed(() => {
	if (store.design.frameConfig === "3-side") return "3 SideOuterFrame";
	if (store.design.frameConfig === "3-side-threshold") return "3 Side Outer With Low Threshold";
	return "4 SideOuterFrame";
});

const activePalette = ref<"divider" | "designs" | null>(null);
const palSearch = ref("");
const fabDockRef = ref<HTMLElement | null>(null);
const dividerPaletteRef = ref<HTMLElement | null>(null);
const designsPaletteRef = ref<HTMLElement | null>(null);
function togglePalette(kind: "divider" | "designs") {
	activePalette.value = activePalette.value === kind ? null : kind;
}
function onDocumentPointerDown(e: Event) {
	if (!activePalette.value) return;
	const t = e.target as Node | null;
	if (!t) return;
	if (
		fabDockRef.value?.contains(t) ||
		dividerPaletteRef.value?.contains(t) ||
		designsPaletteRef.value?.contains(t)
	) {
		return;
	}
	activePalette.value = null;
}

const allCells = computed(() => layoutGeom(store.design).cells);

const specPopover = ref<{
	open: boolean;
	kind: "mullion" | "transom" | "custom" | "grid";
	dir: SplitDir;
	count: number;
	eqMode: "mullion" | "glass";
	gridV: number;
	gridH: number;
	gridVEq: "Mullion Equalization" | "Equal Glass";
	gridHEq: "Mullion Equalization" | "Equal Glass";
	gridJunc: "Vertical dividers in full" | "Horizontal dividers in full";
	cellPaths: string[];
}>({
	open: false,
	kind: "mullion",
	dir: "v",
	count: 1,
	eqMode: "mullion",
	gridV: 2,
	gridH: 2,
	gridVEq: "Mullion Equalization",
	gridHEq: "Mullion Equalization",
	gridJunc: "Vertical dividers in full",
	cellPaths: ["F1"],
});

const specHasExistingGrid = computed(() => {
	const cells = layoutGeom(store.design).cells;
	return cells.some(
		(c) => specPopover.value.cellPaths.includes(c.path) && Boolean(c.node.grill)
	);
});

function openSpecPopover(kind: "mullion" | "transom" | "custom" | "grid", targetPath?: string) {
	const cells = layoutGeom(store.design).cells;
	const fallback = (selectedLeaf.value ? activeCellPath.value : cells[0]?.path) || "F1";
	const chosen = targetPath || fallback;
	const existing = cells.find((c) => c.path === chosen)?.node.grill;
	specPopover.value = {
		open: true,
		kind,
		dir: kind === "transom" ? "h" : "v",
		count: 1,
		eqMode: "mullion",
		gridV: existing?.vertical ?? 2,
		gridH: existing?.horizontal ?? 2,
		gridVEq: "Mullion Equalization",
		gridHEq: "Mullion Equalization",
		gridJunc: "Vertical dividers in full",
		cellPaths: [chosen],
	};
	activePalette.value = null;
}

function toggleSpecCell(path: string) {
	const list = specPopover.value.cellPaths;
	if (list.includes(path)) {
		if (list.length > 1) specPopover.value.cellPaths = list.filter((p) => p !== path);
	} else {
		specPopover.value.cellPaths = [...list, path];
	}
}

function removeSpecGrid() {
	const targets = specPopover.value.cellPaths.length
		? specPopover.value.cellPaths
		: [allCells.value[0]?.path || "F1"];
	store.apply((d) => {
		let next = d;
		for (const p of targets) {
			try {
				const n = getNode(next, p);
				if (n.type !== "split") next = setLeaf(next, p, { ...n, grill: undefined });
			} catch {
				// ignore missing path
			}
		}
		return next;
	});
	specPopover.value.open = false;
	showEvaToast("Removed surface grid");
}

function applySpecPopover() {
	const { kind, dir, count, eqMode, gridV, gridH, cellPaths } = specPopover.value;
	const targets = (cellPaths.length ? [...cellPaths] : [allCells.value[0]?.path || "F1"]).sort(
		(a, b) => b.localeCompare(a)
	);
	if (kind === "grid") {
		const nv = Math.max(1, Math.min(6, Number(gridV) || 2));
		const nh = Math.max(1, Math.min(6, Number(gridH) || 2));
		store.apply((d) => {
			let next = d;
			for (const p of targets) {
				try {
					const n = getNode(next, p);
					if (n.type !== "split")
						next = setLeaf(next, p, { ...n, grill: { vertical: nv, horizontal: nh } });
				} catch {
					// ignore missing path
				}
			}
			return next;
		});
		store.select(targets[targets.length - 1] || "F1");
		specPopover.value.open = false;
		showEvaToast(`Applied ${nv} × ${nh} surface grid`);
		return;
	}
	const dividerCount = Math.max(1, Math.min(6, Number(count) || 1));
	const frameCode = store.design.frameProfileId || store.design.profiles?.frame;
	const barCode =
		dir === "v"
			? store.design.mullionProfileId || store.design.profiles?.mullion
			: store.design.profiles?.transom;
	const frameFace = (frameCode && store.seriesInfo?.profile_widths?.[frameCode]) || 42;
	const barFace = (barCode && store.seriesInfo?.profile_widths?.[barCode]) || 40;
	const bottomFace = store.design.frameConfig === "3-side" ? 0 : frameFace;
	store.apply((d) => {
		let next = { ...d, isSliding: false, trackCount: undefined };
		for (const p of targets) {
			try {
				next = splitCellWithCount(
					next,
					p,
					dir,
					dividerCount,
					eqMode,
					frameFace,
					barFace,
					bottomFace
				);
			} catch {
				// skip if parent changed
			}
		}
		return next;
	});
	const firstTarget = targets[targets.length - 1] || "F1";
	store.select(layoutGeom(store.design).cells[0]?.path ?? `${firstTarget}.0`);
	specPopover.value.open = false;
	showEvaToast(
		`Added ${dividerCount} ${dir === "h" ? "Transom" : "Mullion"}${
			dividerCount > 1 ? "s" : ""
		}`
	);
}

function onToolDragStart(kind: string, id: string, e: DragEvent) {
	const payload = JSON.stringify({ kind, id });
	(window as unknown as { __fenDragPayload?: string }).__fenDragPayload = payload;
	if (e.dataTransfer) {
		e.dataTransfer.setData("application/json", payload);
		e.dataTransfer.setData("text/plain", payload);
		e.dataTransfer.effectAllowed = "copy";
	}
}

function clearedDesignBase(d: Design): Design {
	return {
		...newDesign(d.width, d.height),
		series: d.series,
		frameConfig: d.frameConfig,
		colorMode: d.colorMode,
		finish: d.finish,
		finishOutside: d.finishOutside,
	};
}

function buildToolAppliedDesign(
	d: Design,
	kind: string,
	id: string,
	path: string,
	gLabel: string
): { next: Design; selectedPath: string; toastMsg: string; promptSash?: boolean } | null {
	let targetNode: LeafNode | null = null;
	try {
		const n = getNode(d, path);
		targetNode = n.type === "split" ? null : n;
	} catch {
		return null;
	}
	if (!targetNode) return null;
	const cells = layoutGeom(d).cells;
	const cellGeom = cells.find((c) => c.path === path);

	if (kind === "divider") {
		let next = d;
		if (id === "item_02" || id === "cross") {
			const base = { ...d, isSliding: false, trackCount: undefined };
			const s1 = splitCell(base, path, "v", 2);
			next = splitCell(splitCell(s1, `${path}.0`, "h", 2), `${path}.1`, "h", 2);
		} else if (id === "item_03") {
			const base = { ...d, isSliding: false, trackCount: undefined };
			const hSplit = splitCell(base, path, "h", 2);
			const pos = Math.round((cellGeom?.h ?? base.height) * 0.38 * 10) / 10;
			const positioned = moveSplit(hSplit, path, 0, pos);
			next = splitCell(positioned, `${path}.1`, "v", 2);
		} else if (id === "item_05") {
			const base = { ...d, isSliding: false, trackCount: undefined };
			const s1 = splitCell(base, path, "h", 2);
			next = splitCell(splitCell(s1, `${path}.0`, "v", 2), `${path}.1`, "v", 2);
		} else if (id === "item_06") {
			const base = { ...d, isSliding: false, trackCount: undefined };
			const vSplit = splitCell(base, path, "v", 2);
			const pos = Math.round((cellGeom?.w ?? base.width) * 0.62 * 10) / 10;
			const positioned = moveSplit(vSplit, path, 0, pos);
			next = splitCell(positioned, `${path}.0`, "h", 2);
		} else if (id === "split-2v") {
			next = splitCell({ ...d, isSliding: false, trackCount: undefined }, path, "v", 2);
		} else if (id === "split-3v") {
			next = splitCellWithCount(
				{ ...d, isSliding: false, trackCount: undefined },
				path,
				"v",
				2,
				"mullion"
			);
		} else if (id === "split-2h") {
			next = splitCell({ ...d, isSliding: false, trackCount: undefined }, path, "h", 2);
		} else {
			return null;
		}
		return {
			next,
			selectedPath: `${path}.0`,
			toastMsg: `Applied divider layout to ${gLabel}`,
		};
	}

	if (kind === "openable") {
		const glass = targetNode.glass;
		const isDoorCfg = (d.frameConfig && d.frameConfig !== "4-side") || id === "door-left";
		if (id === "Fixed Window" || id === "fixed") {
			return {
				next: setLeaf({ ...d, isSliding: false, trackCount: undefined }, path, {
					type: "fixed",
					glass,
					bead: true,
				}),
				selectedPath: path,
				toastMsg: `Applied Fixed Window to ${gLabel}`,
			};
		}
		if (id === "French Openable" || id === "french") {
			const sc = isDoorCfg ? "door" : "window";
			const base = { ...d, isSliding: false, trackCount: undefined };
			const withSplit = splitCell(base, path, "v", 2);
			const sL: LeafNode = {
				type: "sash",
				glass,
				opening: "out",
				hinge: "left",
				sashConfig: sc,
				activeLeaf: sc === "door" ? false : undefined,
				ghh: sc === "door" ? 1050 : 732,
				lock: "multipoint",
				bead: sc === "door",
			};
			const sR: LeafNode = {
				type: "sash",
				glass,
				opening: "out",
				hinge: "right",
				sashConfig: sc,
				activeLeaf: sc === "door" ? true : undefined,
				ghh: sc === "door" ? 1050 : 732,
				lock: "multipoint",
				bead: sc === "door",
			};
			return {
				next: setLeaf(setLeaf(withSplit, `${path}.0`, sL), `${path}.1`, sR),
				selectedPath: `${path}.0`,
				toastMsg: `Applied French Openable to ${gLabel}`,
			};
		}
		const hinge =
			id === "Right Openable" || id === "sash-right"
				? "right"
				: id === "Top Hung" || id === "sash-top"
				? "top"
				: id === "Bottom Hung"
				? "bottom"
				: "left";
		const sc = id === "door-left" ? "door" : "window";
		return {
			next: setLeaf({ ...d, isSliding: false, trackCount: undefined }, path, {
				type: "sash",
				glass,
				opening: "out",
				hinge,
				sashConfig: sc,
				hingeStay:
					sc === "door"
						? "Hinges"
						: hinge === "top" || hinge === "bottom"
						? "Friction stay"
						: undefined,
				activeLeaf: sc === "door" ? true : undefined,
				ghh: sc === "door" ? 1050 : 732,
				lock: "multipoint",
				bead: sc === "door",
			}),
			selectedPath: path,
			toastMsg: `Applied ${id} to ${gLabel}`,
			promptSash: true,
		};
	}

	if (kind === "sliding") {
		const tm = id.match(/(\d+(?:\.\d+)?)\s*Track/i);
		const tracks = tm ? Math.max(2, Math.min(8, Math.round(parseFloat(tm[1])))) : 2;
		const pm = id.match(/(\d+)\s*Panel/i);
		let panels = pm ? Math.max(2, Math.min(12, Number(pm[1]))) : 2;
		let ratios: number[] | null = null;
		if (id.includes("X-X-2X-X-X")) {
			panels = 5;
			ratios = [1, 1, 2, 1, 1];
		} else if (id.includes("X-2X-X")) {
			panels = 3;
			ratios = [1, 2, 1];
		} else if (id.includes("X-X-X")) {
			panels = 3;
		}
		const rr = ratios ?? Array.from({ length: panels }, () => 1);
		const rsum = rr.reduce((a, b) => a + b, 0);
		const glass = targetNode.glass;
		const isBothLeft = /Meeting Both Left/i.test(id);
		const isBothRight = /Meeting Both Right/i.test(id);
		const at: number[] = [];
		let acc = 0;
		for (let i = 0; i < rr.length - 1; i++) {
			acc += rr[i];
			at.push(Math.round(((d.width * acc) / rsum) * 10) / 10);
		}
		const children: LeafNode[] = [];
		for (let i = 0; i < panels; i++) {
			const midFixed =
				(panels === 3 && i === 1 && (id.includes("X-2X-X") || id.includes("X-X-X"))) ||
				(id.includes("X-X-2X-X-X") && i === 2);
			let slideDir: "left" | "right" = i < panels / 2 ? "right" : "left";
			if (isBothLeft) slideDir = "left";
			else if (isBothRight) slideDir = "right";
			let tIdx = i % tracks;
			if (tracks === 2) {
				if (panels === 2) tIdx = i;
				else if (panels === 3) tIdx = i === 1 ? 1 : 0;
				else if (panels === 4) tIdx = i === 1 || i === 2 ? 1 : 0;
				else tIdx = i % 2;
			} else if (panels !== tracks) {
				tIdx = Math.min(i, panels - 1 - i) % tracks;
			}
			children.push({
				type: "sash",
				glass,
				isSliding: true,
				slideFixed: midFixed,
				slideDir,
				trackIdx: tIdx,
				trackCount: tracks,
				handleItem: midFixed ? "None" : "(H349) 34MM AUTO TOUCH LOCK",
				lock: midFixed ? "none" : "singlepoint",
				bead: false,
			});
		}
		return {
			next: {
				...d,
				isSliding: true,
				trackCount: tracks,
				root: { type: "split", dir: "v", at, children, slideRatios: rr },
			},
			selectedPath: "F1.0",
			toastMsg: `Applied ${id}`,
		};
	}

	if (kind === "addon") {
		const low = id.toLowerCase();
		let next = d;
		if (low === "louver") {
			next = setLeaf(d, path, {
				type: "louver",
				glass: targetNode.glass,
				blades: 9,
				grill: targetNode.grill,
			});
		} else if (low === "fan" && targetNode.type !== "louver") {
			next = setLeaf(d, path, { ...targetNode, fan: !targetNode.fan });
		} else if (low === "ac") {
			next = setLeaf(d, path, {
				...targetNode,
				addon: targetNode.addon === "AC" ? undefined : "AC",
			});
		} else if (low === "railing") {
			next = setLeaf(d, path, {
				...targetNode,
				addon: targetNode.addon === "Railing" ? undefined : "Railing",
			});
		} else if (low === "grill" || low === "georgian bar") {
			const bars = low === "georgian bar" ? 2 : 1;
			next = setLeaf(d, path, {
				...targetNode,
				grill: targetNode.grill ? undefined : { vertical: bars, horizontal: bars },
			});
		} else if (low.includes("mesh")) {
			const toggleOff = targetNode.mesh && targetNode.meshType === id;
			next = setLeaf(d, path, {
				...targetNode,
				mesh: !toggleOff,
				meshType: toggleOff ? undefined : id,
			});
		} else if (low === "door panel") {
			const isPanel = targetNode.addon === "Panel" || targetNode.itemType === "Panel";
			next = setLeaf(d, path, {
				...targetNode,
				itemType: isPanel ? "Glass" : "Panel",
				panelItem: isPanel ? undefined : "POWDER COATED ALUMINIUM LOUVER PANEL",
				addon: isPanel ? undefined : "Panel",
				bead: true,
			});
		}
		return { next, selectedPath: path, toastMsg: `Applied ${id} to ${gLabel}` };
	}

	return null;
}

function resolveDividerPopoverKind(
	kind: string,
	id: string
): "mullion" | "transom" | "custom" | "grid" | null {
	if (kind !== "divider") return null;
	const low = id.toLowerCase();
	if (low === "mullion") return "mullion";
	if (low === "transom") return "transom";
	if (id === "item_08" || low === "custom") return "custom";
	if (id === "Grid" || id === "grill") return "grid";
	return null;
}

function warnIfSeriesUnsupportedTool(kind: string, id: string, designAfter: Design) {
	const supported = store.seriesInfo?.supported_products ?? [];
	if (!supported.length) return;
	const isDoor =
		id === "door-left" ||
		id.toLowerCase() === "door panel" ||
		(designAfter.frameConfig != null && designAfter.frameConfig !== "4-side");
	const product =
		kind === "sliding" || designAfter.isSliding
			? isDoor
				? "Sliding Door"
				: "Sliding Window"
			: isDoor
			? "Door"
			: "Window";
	if (!supported.includes(product)) {
		const seriesCode =
			store.design.series || store.seriesVersion.split("-")[0] || "This series";
		toast.warning(
			`Series ${seriesCode} does not contain profiles for ${product} assemblies (supported: ${supported.join(
				", "
			)}).`
		);
	}
}

function applyToolToPath(kind: string, id: string, targetPath?: string, fromDrop = false) {
	if (kind === "info") {
		showEvaToast(`${id} selected (applied at frame join)`);
		activePalette.value = null;
		return;
	}
	const cells = layoutGeom(store.design).cells;
	const path = targetPath || (selectedLeaf.value ? activeCellPath.value : cells[0]?.path);
	if (!path) return;
	const popKind = resolveDividerPopoverKind(kind, id);
	if (popKind) {
		openSpecPopover(popKind, path);
		return;
	}
	const cellIdx = cells.findIndex((c) => c.path === path);
	const gLabel = cellIdx >= 0 ? `G${cellIdx + 1}` : path;
	const applied = buildToolAppliedDesign(store.design, kind, id, path, gLabel);
	if (!applied) return;
	store.apply(() => applied.next);
	activePalette.value = null;
	store.select(applied.selectedPath);
	showEvaToast(applied.toastMsg);
	warnIfSeriesUnsupportedTool(kind, id, applied.next);
	if (applied.promptSash && !fromDrop) {
		propertiesPanel.value?.promptProfilePickers([{ role: "sash", targetKey: path }]);
	}
}

const pendingReplaceDrop = ref<{ kind: string; id: string } | null>(null);

function onDropTool(payload: {
	kind: string;
	id: string;
	cellPath: string;
	replaceDesign?: boolean;
}) {
	if (payload.replaceDesign) {
		if (payload.kind === "info") {
			showEvaToast(`${payload.id} selected (applied at frame join)`);
			return;
		}
		pendingReplaceDrop.value = { kind: payload.kind, id: payload.id };
		return;
	}
	applyToolToPath(payload.kind, payload.id, payload.cellPath, true);
}

function cancelReplaceDrop() {
	pendingReplaceDrop.value = null;
}

function confirmReplaceDrop() {
	const item = pendingReplaceDrop.value;
	pendingReplaceDrop.value = null;
	if (!item) return;
	const popKind = resolveDividerPopoverKind(item.kind, item.id);
	if (popKind) {
		store.apply(clearedDesignBase);
		store.select("F1");
		openSpecPopover(popKind, "F1");
		return;
	}
	let outcome: { selectedPath: string; toastMsg: string } = {
		selectedPath: "F1",
		toastMsg: `Replaced design with ${item.id}`,
	};
	store.apply((d) => {
		const cleared = clearedDesignBase(d);
		const built = buildToolAppliedDesign(cleared, item.kind, item.id, "F1", "G1");
		if (!built) return cleared;
		outcome = { selectedPath: built.selectedPath, toastMsg: built.toastMsg };
		return built.next;
	});
	activePalette.value = null;
	store.select(outcome.selectedPath);
	showEvaToast(outcome.toastMsg);
	warnIfSeriesUnsupportedTool(item.kind, item.id, store.design);
}

const dividerMullions = EVA_CATALOG.filter(
	(c) => c.palette === "Divider" && c.section === "Mullions & Transoms"
);
const dividerJoints = EVA_CATALOG.filter((c) => c.palette === "Divider" && c.section === "Joints");
const designSections = computed(() => {
	const q = palSearch.value.trim().toLowerCase();
	const order = [
		"Openable Designs",
		"Sliding Designs",
		"Add-on Mesh Sash",
		"Pleated & Pull-down Mesh",
		"Add-ons",
	];
	return order
		.map((sec) => ({
			title: sec,
			items: EVA_CATALOG.filter(
				(c) =>
					c.palette === "Designs" &&
					c.section === sec &&
					(!q || c.id.toLowerCase().includes(q) || sec.toLowerCase().includes(q))
			),
		}))
		.filter((g) => g.items.length > 0);
});
function tileAriaLabel(item: EvaCatalogItem): string | undefined {
	if (item.id === "Left Openable") return "Sash";
	if (item.id === "Fixed Window") return "Fixed glass";
	if (item.id === "Louver") return "Louver";
	if (item.id === "Fan") return "Exhaust fan cut";
	if (item.id === "Grill") return "Grill";
	return item.id.replace(/_/g, " ");
}
const filteredPaletteTemplates = computed(() => {
	const q = palSearch.value.trim().toLowerCase();
	if (!q) return sidebarTemplates.value;
	return sidebarTemplates.value.filter(
		(t) => t.label.toLowerCase().includes(q) || t.id.toLowerCase().includes(q)
	);
});
const saving = ref(false);
const justSaved = ref(false);
const showExitButton = computed(() => justSaved.value && !store.dirty);
const loadError = ref("");
const loading = ref(false);
let loadedName: string | null = null;
const lockedBy = ref<{ doctype: string; name: string } | null>(null);
const copying = ref(false);
const blocked = computed(
	() => loading.value || !!loadError.value || saving.value || !!lockedBy.value
);
const lockMessage = computed(() =>
	lockedBy.value
		? `${meta.value.ref} is on ${lockedBy.value.doctype} ${lockedBy.value.name}. Copy the design to change it.`
		: ""
);
const unsupportedProductWarning = computed(() => {
	const issue = (store.result?.issues ?? []).find(
		(i) => i.code === "unsupported_series_product"
	);
	if (!issue) return "";
	return issue.hint ? `${issue.message} — ${issue.hint}` : issue.message;
});
const toolHint = "Select a panel on the drawing to use these tools";
const designType = computed(() => typology(store.design.root));
const canvas = ref<InstanceType<typeof WindowCanvas> | null>(null);

const sectionOn = ref(false);
const cutAxis = computed<CutAxis>({
	get: () => store.design.activeCutAxis ?? "h",
	set: (val: CutAxis) => store.setActiveCutAxis(val),
});
/** The cut the user picked (cell centre, mm), sent to the engine; null lets the engine cut the first cell. */
const cutAt = ref<Record<CutAxis, number | null>>({ h: null, v: null });
/** Where the engine actually cut. Only places the markers; never sent back, so it cannot trigger a fetch. */
const cutSnapped = ref<Record<CutAxis, number | null>>({ h: null, v: null });
/** Marker positions: engine cut, else the picked cut, else the engine's default (centre of the first cell). */
const cutPos = computed(() => {
	const first = layoutGeom(store.design).cells[0];
	const pos = (a: CutAxis, fallback: number) =>
		cutSnapped.value[a] ?? cutAt.value[a] ?? fallback;
	return {
		axis: cutAxis.value,
		h: pos("h", first.y + first.h / 2),
		v: pos("v", first.x + first.w / 2),
	};
});
function pickCut(axis: CutAxis, at: number) {
	cutAt.value = { ...cutAt.value, [axis]: at };
	cutSnapped.value = { ...cutSnapped.value, [axis]: null };
}
function onSnapped(at: number) {
	cutSnapped.value = { ...cutSnapped.value, [cutAxis.value]: at };
}

const finishList = useList<FinishRow>({
	doctype: "Profile Finish",
	fields: ["name", "finish_name", "color", "finish_type"],
	orderBy: "name asc",
	limit: 100,
});
const finishes = computed(() => finishList.data ?? []);
const finishName = computed(() => {
	if (store.design.colorMode === "none") return "Mill Finish";
	return finishes.value.find((f) => f.name === store.finish)?.finish_name || store.finish;
});
const finishColor = computed(() => {
	if (store.design.colorMode === "none") return "#a8b0ba";
	return finishes.value.find((f) => f.name === store.finish)?.color || undefined;
});
const outsideFinishColor = computed(() => {
	if (store.design.colorMode === "none") return "#a8b0ba";
	if (store.design.colorMode === "dual" && store.design.finishOutside) {
		return (
			finishes.value.find((f) => f.name === store.design.finishOutside)?.color ||
			finishColor.value
		);
	}
	return finishColor.value;
});

const leftCollapsed = ref(false);
const splitCount = ref<2 | 3 | 4>(2);
const splitEqMode = ref<"mullion" | "glass">("mullion");

const versionList = useList<SeriesVersionRow>({
	doctype: "Series Version",
	fields: ["name", "series", "version_note", "docstatus"],
	filters: { docstatus: 1 },
	orderBy: "modified desc",
	limit: 100,
});
const seriesVersions = computed(() => versionList.data ?? []);
const profileSeriesOptions = computed(() => {
	const set = new Set<string>();
	for (const sv of seriesVersions.value) {
		if (sv.series) set.add(sv.series);
	}
	set.add("CS400");
	set.add("CS4800");
	return Array.from(set).map((s) => ({ label: s, value: s }));
});

const activeProfileSeries = computed(() => {
	const ver = store.seriesVersion;
	const match = seriesVersions.value.find((sv) => sv.name === ver);
	if (match?.series) return match.series;
	if (ver && ver.toUpperCase().includes("CS4800")) return "CS4800";
	return "CS400";
});

function onSelectProfileSeries(seriesName: string) {
	const target = seriesVersions.value.find((sv) => sv.series === seriesName);
	const nextVer = target?.name || (seriesName === "CS4800" ? "CS4800-v1" : "CS400-v1");
	store.setSeriesVersion(nextVer);
}

const seriesVersionOptions = computed(() => {
	const list = seriesVersions.value;
	const opts = list.map((sv) => ({
		label: `${sv.series} · ${sv.name}`,
		value: sv.name,
	}));
	if (store.seriesVersion && !opts.some((o) => o.value === store.seriesVersion)) {
		opts.unshift({ label: store.seriesVersion, value: store.seriesVersion });
	}
	return opts;
});

const issuePaths = computed(() => (store.result?.issues ?? []).map((i) => i.path));
const activeCellPath = computed(() => store.selectedPath.replace(/^(GLASS|GRILL|BEAD):/, ""));
const selectedLeaf = computed(() => {
	try {
		if (!activeCellPath.value || activeCellPath.value === "FRAME") return null;
		const n = getNode(store.design, activeCellPath.value);
		return n.type === "split" ? null : n;
	} catch {
		return null;
	}
});
const canRemoveSplit = computed(() => {
	const p = activeCellPath.value;
	if (!p || p === "FRAME") return false;
	if (layoutGeom(store.design).bars.some((b) => b.id === p)) return true;
	try {
		const n = getNode(store.design, p);
		return n.type === "split" || p.includes(".");
	} catch {
		return false;
	}
});

const mainEl = ref<HTMLElement | null>(null);
const splitRatio = ref(50);
const resizingSplit = ref(false);
let splitDrag: { startX: number; origRatio: number } | null = null;

function onSplitResizerPointerDown(e: PointerEvent) {
	if (e.button !== 0 && e.button !== undefined) return;
	e.preventDefault();
	splitDrag = { startX: e.clientX, origRatio: splitRatio.value };
	resizingSplit.value = true;
	window.addEventListener("pointermove", onSplitResizerPointerMove);
	window.addEventListener("pointerup", endSplitResize);
	window.addEventListener("pointercancel", endSplitResize);
}

function onSplitResizerPointerMove(e: PointerEvent) {
	if (!splitDrag) return;
	const r = mainEl.value?.getBoundingClientRect();
	const totalW = r && r.width > 0 ? r.width : 1000;
	const deltaPct = ((e.clientX - splitDrag.startX) / totalW) * 100;
	splitRatio.value =
		Math.round(Math.min(80, Math.max(20, splitDrag.origRatio + deltaPct)) * 10) / 10;
}

function endSplitResize() {
	if (!splitDrag) return;
	splitDrag = null;
	resizingSplit.value = false;
	window.removeEventListener("pointermove", onSplitResizerPointerMove);
	window.removeEventListener("pointerup", endSplitResize);
	window.removeEventListener("pointercancel", endSplitResize);
}

const sidebarTemplates = computed(() => {
	const current = activeProfileSeries.value;
	const list = TEMPLATES.filter((t) => t.series === current);
	if (list.length) return list;
	return TEMPLATES.filter((t) => !t.series && t.id !== "blank");
});

function parseJson<T>(v: T | string): T {
	return typeof v === "string" ? JSON.parse(v) : v;
}

async function load(name: string | null) {
	loadError.value = "";
	if (!name) {
		justSaved.value = false;
		loadedName = null;
		lockedBy.value = null;
		meta.value = { ref: "", qty: 1, floor: "", location: "" };
		loading.value = true;
		let defaults = { default_finish: "", default_price_structure: "" };
		try {
			defaults = { ...defaults, ...(await getFenestrationDefaults()) };
			if (savedName.value) return;
			const initialSv = String(
				route.query.series_version || seriesVersions.value[0]?.name || ""
			);
			store.reset(
				(
					TEMPLATES.find((t) => t.id === route.query.template) ??
					TEMPLATES[TEMPLATES.length - 1]
				).build(1200, 1200),
				initialSv,
				defaults.default_finish ?? "",
				defaults.default_price_structure ?? ""
			);
			store.select(layoutGeom(store.design).cells[0]?.path ?? "F1");
		} finally {
			if (!savedName.value) loading.value = false;
		}
		return;
	}
	if (name === loadedName) return;
	justSaved.value = false;
	loading.value = true;
	try {
		const doc: SavedDesign = await getDesign(name);
		if (name !== savedName.value) return;
		meta.value = {
			ref: doc.design_ref,
			qty: doc.qty,
			floor: doc.floor ?? "",
			location: doc.location ?? "",
		};
		store.reset(
			parseJson(doc.design_json),
			doc.series_version,
			doc.finish ?? "",
			doc.price_structure ?? ""
		);
		store.select(layoutGeom(store.design).cells[0]?.path ?? "F1");
		lockedBy.value = doc.locked_by ?? null;
		loadedName = name;
	} catch (e) {
		if (name !== savedName.value) return;
		loadError.value = e instanceof Error ? e.message : "Could not load design";
	} finally {
		if (name === savedName.value) loading.value = false;
	}
}
watch(savedName, load, { immediate: true });
// Sync so load's meta assignment lands before store.reset clears the flag.
watch(meta, () => store.markDirty(), { deep: true, flush: "sync" });
watch(
	() => store.dirty,
	(dirty) => {
		if (dirty) justSaved.value = false;
	},
	{ flush: "sync" }
);

function onBeforeUnload(e: BeforeUnloadEvent) {
	if (!store.dirty) return;
	e.preventDefault();
	e.returnValue = "";
}
function onKeyDown(e: KeyboardEvent) {
	if (e.key === "Escape" && pendingReplaceDrop.value) {
		e.preventDefault();
		cancelReplaceDrop();
		return;
	}
	if (e.key !== "Delete" && e.key !== "Backspace") return;
	const target = e.target as HTMLElement | null;
	if (
		target &&
		(target.tagName === "INPUT" ||
			target.tagName === "TEXTAREA" ||
			target.tagName === "SELECT" ||
			target.isContentEditable)
	) {
		return;
	}
	if (!canDelete.value) return;
	e.preventDefault();
	deleteSelected();
}
onMounted(() => {
	window.addEventListener("beforeunload", onBeforeUnload);
	window.addEventListener("keydown", onKeyDown);
	document.addEventListener("pointerdown", onDocumentPointerDown, true);
	document.addEventListener("mousedown", onDocumentPointerDown, true);
});
onUnmounted(() => {
	endSplitResize();
	window.removeEventListener("beforeunload", onBeforeUnload);
	window.removeEventListener("keydown", onKeyDown);
	document.removeEventListener("pointerdown", onDocumentPointerDown, true);
	document.removeEventListener("mousedown", onDocumentPointerDown, true);
	store.cancelCompute();
});
onBeforeRouteLeave(() => !store.dirty || window.confirm("Discard unsaved changes?"));

function beadPromptTargetKey(cellPath: string): string {
	const beadedCount = layoutGeom(store.design).cells.filter(
		(c) => c.node.type === "fixed" && !c.node.fan && c.node.bead !== false
	).length;
	return beadedCount > 1 ? cellPath : "bead";
}

function split(dir: SplitDir, count = 2) {
	const path = activeCellPath.value;
	const prevBarIds = new Set(layoutGeom(store.design).bars.map((b) => b.id));
	const frameCode = store.design.frameProfileId || store.design.profiles?.frame;
	const barCode =
		dir === "v"
			? store.design.mullionProfileId || store.design.profiles?.mullion
			: store.design.profiles?.transom;
	const frameFace = (frameCode && store.seriesInfo?.profile_widths?.[frameCode]) || 42;
	const barFace = (barCode && store.seriesInfo?.profile_widths?.[barCode]) || 40;
	const bottomFace = store.design.frameConfig === "3-side" ? 0 : frameFace;
	store.apply((d) => {
		const base = { ...d, isSliding: false, trackCount: undefined };
		return count > 2 || splitEqMode.value === "glass"
			? splitCellWithCount(
					base,
					path,
					dir,
					Math.max(1, count - 1),
					splitEqMode.value,
					frameFace,
					barFace,
					bottomFace
			  )
			: splitCell(base, path, dir, 2);
	});
	store.select(`${path}.0`);
	const role = dir === "v" ? "mullion" : "transom";
	const newBar = layoutGeom(store.design).bars.find(
		(b) => b.dir === dir && !prevBarIds.has(b.id)
	);
	propertiesPanel.value?.promptProfilePickers([{ role, targetKey: newBar?.id ?? role }]);
}
function clearDesign() {
	store.apply(clearedDesignBase);
	store.select("F1");
}

const effectiveProfileWidths = computed(() => ({
	...store.catalogProfileWidths,
	...(store.seriesInfo?.profile_widths ?? {}),
}));
const effectiveRoleDefaults = computed(() => ({
	...store.catalogRoleDefaults,
	...(store.seriesInfo?.role_defaults ?? {}),
}));
function convert(kind: "sash" | "fixed" | "louver") {
	const cur = selectedLeaf.value;
	if (!cur) return;
	const path = activeCellPath.value;
	const wasKind = cur.type;
	const glass = cur.glass;
	const leaf: LeafNode =
		kind === "sash"
			? {
					type: "sash",
					glass,
					opening: "out",
					hinge: "left",
					ghh: 732,
					lock: "multipoint",
					bead: true,
					grill: cur.grill,
					fan: cur.fan,
					fanCut: cur.fanCut,
					steelThickness: cur.steelThickness,
			  }
			: kind === "louver"
			? { type: "louver", glass, blades: 9, grill: cur.grill }
			: {
					type: "fixed",
					glass,
					bead: true,
					grill: cur.grill,
					fan: cur.fan,
					fanCut: cur.fanCut,
					steelThickness: cur.steelThickness,
			  };
	store.apply((d) => setLeaf(d, path, leaf));
	store.select(path);
	if (kind === "sash" && wasKind !== "sash") {
		propertiesPanel.value?.promptProfilePickers([{ role: "sash", targetKey: path }]);
	}
}
function toggleGrill() {
	const cur = selectedLeaf.value;
	if (!cur) return;
	store.apply((d) =>
		setLeaf(d, activeCellPath.value, { ...cur, grill: cur.grill ? undefined : {} })
	);
}
function toggleExhaustFan() {
	const cur = selectedLeaf.value;
	if (!cur || cur.type === "louver") return;
	store.apply((d) => setLeaf(d, activeCellPath.value, { ...cur, fan: !cur.fan }));
}
const isBeadOn = computed(() => {
	if (!selectedLeaf.value) return false;
	return selectedLeaf.value.bead !== false;
});
function toggleBead() {
	const cur = selectedLeaf.value;
	if (!cur) return;
	const path = activeCellPath.value;
	const nextBead = cur.bead === false ? true : false;
	store.apply((d) => setLeaf(d, path, { ...cur, bead: nextBead }));
	if (nextBead) {
		propertiesPanel.value?.promptProfilePickers([
			{ role: "bead", targetKey: beadPromptTargetKey(path) },
		]);
	}
}
function unsplitSelected() {
	const p = activeCellPath.value;
	const bar = layoutGeom(store.design).bars.find((b) => b.id === p);
	let target = bar ? bar.splitPath : "";
	if (!target) {
		try {
			target =
				getNode(store.design, p).type === "split"
					? p
					: p.split(".").slice(0, -1).join(".");
		} catch {
			return;
		}
	}
	if (!target) return;
	store.apply((d) => removeSplit(d, target));
	const nextLeaf =
		layoutGeom(store.design).cells.find(
			(c) => c.path === target || c.path.startsWith(`${target}.`)
		)?.path ?? target;
	store.select(nextLeaf);
}

const canDelete = computed(() => {
	const leaf = selectedLeaf.value;
	if (!leaf) return canRemoveSplit.value;
	return (
		(store.selectedPath.startsWith("GRILL:") && Boolean(leaf.grill)) ||
		leaf.type === "sash" ||
		leaf.type === "louver" ||
		Boolean(leaf.fan)
	);
});

const deleteLabel = computed(() => {
	const leaf = selectedLeaf.value;
	if (!leaf && canRemoveSplit.value) return "Merge split";
	if (store.selectedPath.startsWith("GRILL:") && leaf?.grill) return "Delete grill";
	if (leaf?.fan) return "Delete exhaust cut";
	if (leaf?.type === "sash") return "Delete sash";
	if (leaf?.type === "louver") return "Delete louver";
	return "Delete";
});

function deleteSelected() {
	const leaf = selectedLeaf.value;
	if (!leaf) {
		if (canRemoveSplit.value) unsplitSelected();
		return;
	}
	if (store.selectedPath.startsWith("GRILL:") && leaf.grill) {
		store.apply((d) => setLeaf(d, activeCellPath.value, { ...leaf, grill: undefined }));
		store.select(activeCellPath.value);
		return;
	}
	if (leaf.fan) {
		store.apply((d) => setLeaf(d, activeCellPath.value, { ...leaf, fan: false }));
		return;
	}
	if (leaf.type === "sash") {
		store.apply((d) =>
			setLeaf(d, activeCellPath.value, { type: "fixed", glass: leaf.glass, bead: true })
		);
		return;
	}
	if (leaf.type === "louver") {
		store.apply((d) =>
			setLeaf(d, activeCellPath.value, { type: "fixed", glass: leaf.glass, bead: true })
		);
		return;
	}
}

const canResetPanel = computed(() => Boolean(selectedLeaf.value));

function resetPanel() {
	const leaf = selectedLeaf.value;
	if (!leaf) return;
	const defaultGlass = leaf.glass || store.seriesInfo?.glasses?.[0] || "6CTG";
	store.apply((d) =>
		setLeaf(d, activeCellPath.value, { type: "fixed", glass: defaultGlass, bead: true })
	);
}

const isInvalidSelection = computed(() => {
	const sel = activeCellPath.value;
	if (!sel || sel === "FRAME" || /^[MT]\d+$/.test(sel)) return false;
	return !selectedLeaf.value;
});

const editSelectionChipLabel = computed(() => {
	const leaf = selectedLeaf.value;
	if (leaf) {
		const name = activeCellPath.value.toUpperCase();
		if (store.selectedPath.startsWith("GRILL:")) return `Grill ${name} selected`;
		if (leaf.type === "sash") return `Sash ${name} selected`;
		if (leaf.type === "louver") return `Louver ${name} selected`;
		return `Panel ${name} selected`;
	}
	if (canRemoveSplit.value) {
		return `Split ${activeCellPath.value.toUpperCase()} selected`;
	}
	return "Nothing selected";
});

const deleteBaseStyle = {
	minHeight: "36px",
	padding: "6px 10px",
	borderRadius: "7px",
	background: "#ffffff",
	fontSize: "12.5px",
	fontWeight: "600",
	lineHeight: "1.25",
	display: "flex",
	alignItems: "center",
	justifyContent: "space-between",
	gap: "6px",
	textAlign: "left" as const,
	boxSizing: "border-box" as const,
	width: "100%",
};

const deleteActiveStyle = {
	...deleteBaseStyle,
	border: "1px solid #e8a9a2",
	cursor: "pointer",
	color: "#b42318",
};

const deleteDisabledStyle = {
	...deleteBaseStyle,
	border: "1px solid #d7dbe0",
	cursor: "not-allowed",
	opacity: "0.45",
	color: "#5b6472",
};

const editBtnBaseStyle = {
	minHeight: "36px",
	padding: "6px 10px",
	border: "1px solid #d7dbe0",
	borderRadius: "7px",
	background: "#ffffff",
	fontSize: "12.5px",
	lineHeight: "1.25",
	display: "flex",
	alignItems: "center",
	gap: "8px",
	textAlign: "left" as const,
	boxSizing: "border-box" as const,
	width: "100%",
};

const editBtnStyle = {
	...editBtnBaseStyle,
	cursor: "pointer",
	color: "#14171c",
};

const editBtnDisabledStyle = {
	...editBtnBaseStyle,
	cursor: "not-allowed",
	opacity: "0.45",
	color: "#5b6472",
};

const buildBtnStyle = {
	height: "36px",
	padding: "0 12px",
	border: "1px solid #d7dbe0",
	borderRadius: "7px",
	background: "#ffffff",
	fontSize: "13px",
	fontWeight: "500",
	display: "flex",
	alignItems: "center",
	justifyContent: "flex-start",
	gap: "10px",
	cursor: "pointer",
	color: "#14171c",
	boxSizing: "border-box" as const,
	width: "100%",
};

const buildBtnDisabledStyle = {
	height: "36px",
	padding: "0 12px",
	border: "1px solid #d7dbe0",
	borderRadius: "7px",
	background: "#ffffff",
	fontSize: "13px",
	fontWeight: "500",
	display: "flex",
	alignItems: "center",
	justifyContent: "flex-start",
	gap: "10px",
	cursor: "not-allowed",
	opacity: "0.45",
	color: "#5b6472",
	boxSizing: "border-box" as const,
	width: "100%",
};

const buildBtnActiveStyle = {
	height: "36px",
	padding: "0 12px",
	border: "1px solid #b8d5fb",
	borderRadius: "7px",
	background: "#eef4ff",
	fontSize: "13px",
	fontWeight: "500",
	display: "flex",
	alignItems: "center",
	justifyContent: "flex-start",
	gap: "10px",
	cursor: "pointer",
	color: "#1b5fb8",
	boxSizing: "border-box" as const,
	width: "100%",
};
function applyTemplate(tplId: string) {
	const tpl = TEMPLATES.find((t) => t.id === tplId);
	if (!tpl) return;
	const prevGeom = layoutGeom(store.design);
	const prevHasMullion = prevGeom.bars.some((b) => b.dir === "v");
	const prevHasTransom = prevGeom.bars.some((b) => b.dir === "h");
	const prevHasSash = prevGeom.cells.some((c) => c.node.type === "sash");
	const width = tpl.defaultW ?? store.design.width;
	const height = tpl.defaultH ?? store.design.height;
	store.apply(() => tpl.build(width, height));
	store.select(layoutGeom(store.design).cells[0]?.path ?? "F1");
	const afterGeom = layoutGeom(store.design);
	const prompts: { role: "mullion" | "transom" | "sash"; targetKey: string }[] = [];
	if (
		!prevHasMullion &&
		afterGeom.bars.some((b) => b.dir === "v") &&
		!store.design.mullionProfileId &&
		!store.design.profiles?.mullion
	) {
		prompts.push({ role: "mullion", targetKey: "mullion" });
	}
	if (
		!prevHasTransom &&
		afterGeom.bars.some((b) => b.dir === "h") &&
		!store.design.profiles?.transom
	) {
		prompts.push({ role: "transom", targetKey: "transom" });
	}
	if (
		!prevHasSash &&
		afterGeom.cells.some((c) => c.node.type === "sash") &&
		!store.design.sashProfileId &&
		!store.design.profiles?.sash
	) {
		prompts.push({ role: "sash", targetKey: "sash" });
	}
	if (prompts.length) {
		propertiesPanel.value?.promptProfilePickers(prompts);
	}
}
function onMoveSplit(p: { splitPath: string; index: number; pos: number }) {
	store.dragTo((d) => moveSplit(d, p.splitPath, p.index, p.pos));
}
function onUpdateGrill(path: string, grill: import("@/design/grill").Grill) {
	store.apply((d) => {
		const node = getNode(d, path);
		return node.type === "split" ? d : setLeaf(d, path, { ...node, grill });
	});
}
function onUpdateSectionMap(sectionMap: Record<string, SectionPieceTransform>) {
	store.apply((d) => ({ ...d, sectionMap }));
}

async function save() {
	refError.value = "";
	if (blocked.value) {
		toast.error("Cannot save while design is loading or locked");
		return;
	}
	if (!meta.value.ref.trim()) {
		refError.value = "Design ref is required";
		toast.error("Design ref is required (please enter a ref like W-01)");
		return;
	}
	saving.value = true;
	try {
		const res = await saveDesign({
			project: project.value,
			design_ref: meta.value.ref.trim(),
			series_version: store.seriesVersion,
			design: store.design,
			svg:
				canvas.value?.getSvgMarkup() ||
				generateElevationSvg(store.design, finishColor.value),
			qty: meta.value.qty,
			floor: meta.value.floor ?? "",
			location: meta.value.location,
			name: savedName.value,
			finish: store.finish || null,
			price_structure: store.priceStructure || null,
		});
		if (res.ok) {
			toast.success("Design saved");
			store.markSaved();
			loadedName = res.name;
			justSaved.value = true;
			await router.replace({
				name: "Designer",
				params: { project: project.value, name: res.name },
			});
		} else {
			toast.error(res.message);
		}
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Save failed");
	} finally {
		saving.value = false;
	}
}

function exitDesigner() {
	router.push({ name: "Project", params: { project: project.value } });
}

async function copy() {
	if (!savedName.value || copying.value) return;
	copying.value = true;
	try {
		const copyName = await copyDesign(savedName.value);
		await router.push({
			name: "Designer",
			params: { project: project.value, name: copyName },
		});
	} catch (e) {
		toast.error(e instanceof Error ? e.message : "Copy failed");
	} finally {
		copying.value = false;
	}
}

const propertiesPanel = ref<InstanceType<typeof PropertiesPanel> | null>(null);

function onSectionOpenProfilePicker(piece: { role?: string; panel?: string }) {
	const role =
		piece.role === "mullion"
			? "mullion"
			: piece.role === "transom"
			? "transom"
			: piece.role === "sash" || piece.role === "door_sash"
			? "sash"
			: piece.role === "bead"
			? "bead"
			: "frame";
	const key = piece.role === "frame" ? "frame" : piece.panel || role;
	propertiesPanel.value?.openProfilePicker(role, key);
}
</script>

<template>
	<div
		class="flex min-h-screen flex-col bg-white text-[#2b2f36] md:h-screen"
		style="font-family: 'Segoe UI', Inter, Arial, sans-serif"
		@pointerdown.capture="onDocumentPointerDown"
		@mousedown.capture="onDocumentPointerDown"
	>
		<!-- ─── PROTOTYPE-EXACT HEADER (48px) + FRAPPE PRODUCTION ACTIONS ── -->
		<header
			class="z-20 flex min-h-[48px] flex-wrap items-center justify-between gap-2 border-b border-[#dcdfe4] bg-white px-3 py-1"
		>
			<!-- Left: Sidebar Toggle + Title / Project / Location / Series -->
			<div class="flex min-w-0 flex-1 items-center gap-3">
				<button
					type="button"
					:aria-label="leftCollapsed ? 'Show tools' : 'Hide tools'"
					:title="leftCollapsed ? 'Show left panel' : 'Hide left panel'"
					class="hidden size-8 shrink-0 items-center justify-center rounded-[4px] text-[#2b2f36] hover:bg-[#f0f1f3] md:inline-flex"
					@click="leftCollapsed = !leftCollapsed"
				>
					<span class="lucide-panel-left size-4.5" aria-hidden="true" />
				</button>
				<div class="min-w-0 leading-tight">
					<div
						class="flex items-center gap-1.5 text-[13px] font-semibold text-[#2b2f36]"
					>
						<span class="truncate"
							>{{ meta.ref || "Untitled" }} · {{ designType }}</span
						>
					</div>
					<div class="flex flex-wrap items-center gap-1.5 text-[11px] text-[#6b7280]">
						<nav aria-label="Breadcrumb" class="inline-flex items-center">
							<RouterLink
								:to="`/projects/${project}`"
								class="hover:text-[#1a6fd4] hover:underline"
							>
								Projects / {{ project }}
							</RouterLink>
						</nav>
						<span>·</span>
						<span>Location: {{ meta.location || "—" }}</span>
						<template v-if="store.seriesVersion">
							<span>·</span>
							<span>{{ store.seriesVersion }} - {{ frameConfigLabel }}</span>
						</template>
					</div>
				</div>
			</div>

			<!-- Center: Undo, Redo, Clear, Fit to view -->
			<div class="flex items-center gap-0.5 text-[13px] text-[#2b2f36]">
				<button
					type="button"
					aria-label="Undo"
					:disabled="!store.past.length"
					class="inline-flex h-8 items-center gap-1.5 rounded-[4px] px-2.5 font-medium hover:bg-[#f0f1f3] disabled:cursor-not-allowed disabled:opacity-40"
					@click="store.undo()"
				>
					<span class="lucide-undo-2 size-4" aria-hidden="true" />
					<span class="hidden sm:inline">Undo</span>
				</button>
				<button
					type="button"
					aria-label="Redo"
					:disabled="!store.future.length"
					class="inline-flex h-8 items-center gap-1.5 rounded-[4px] px-2.5 font-medium hover:bg-[#f0f1f3] disabled:cursor-not-allowed disabled:opacity-40"
					@click="store.redo()"
				>
					<span class="lucide-redo-2 size-4" aria-hidden="true" />
					<span class="hidden sm:inline">Redo</span>
				</button>
				<button
					type="button"
					aria-label="Clear"
					class="inline-flex h-8 items-center gap-1.5 rounded-[4px] px-2.5 font-medium hover:bg-[#f0f1f3]"
					@click="
						clearDesign();
						showEvaToast('Cleared canvas');
					"
				>
					<span class="lucide-rotate-ccw size-4" aria-hidden="true" />
					<span class="hidden sm:inline">Clear</span>
				</button>
				<button
					type="button"
					aria-label="Fit to view"
					class="inline-flex h-8 items-center gap-1.5 rounded-[4px] px-2.5 font-medium hover:bg-[#f0f1f3]"
					@click="fitToView"
				>
					<span class="lucide-maximize size-4" aria-hidden="true" />
					<span class="hidden sm:inline">Fit to view</span>
				</button>
			</div>

			<!-- Right: Frappe Section, Cutting Sheet PDF, Save Design (blue primary) -->
			<div class="flex flex-1 items-center justify-end gap-2">
				<button
					type="button"
					aria-label="Section"
					:aria-pressed="sectionOn"
					class="inline-flex h-8 items-center gap-1.5 rounded-[3px] px-3 text-[13px] font-medium transition"
					:class="
						sectionOn
							? 'bg-[#e6effb] text-[#1a6fd4]'
							: 'bg-[#f0f1f3] text-[#2b2f36] hover:bg-[#e4e6ea]'
					"
					@click="sectionOn = !sectionOn"
				>
					<span>Section</span>
				</button>
				<Tooltip
					:text="
						savedName
							? 'Open Cutting Sheet PDF'
							: 'Save design first to download Cutting Sheet PDF'
					"
				>
					<Button
						icon-left="lucide-file-text"
						label="Cutting sheet"
						aria-label="Cutting sheet"
						data-testid="designer-cutting-sheet"
						variant="outline"
						class="h-8 rounded-[3px] border-[#dcdfe4] bg-[#f0f1f3] text-[13px] font-medium text-[#2b2f36] hover:bg-[#e4e6ea]"
						:href="cuttingSheetUrl"
						:disabled="!cuttingSheetUrl"
						target="_blank"
					/>
				</Tooltip>
				<button
					type="button"
					:aria-label="showExitButton ? 'Exit' : 'Save'"
					:disabled="showExitButton ? false : blocked"
					class="inline-flex h-8 items-center gap-1.5 rounded-[3px] px-3.5 text-[13px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50"
					:class="
						showExitButton
							? 'border border-[#cfd4da] bg-white text-[#2b2f36] hover:bg-[#f0f1f3]'
							: 'bg-[#1a6fd4] text-white hover:bg-[#155db3]'
					"
					@click="showExitButton ? exitDesigner() : save()"
				>
					<span v-if="!showExitButton" class="lucide-save size-3.5" aria-hidden="true" />
					<span>{{ showExitButton ? "Exit" : "Save Design" }}</span>
				</button>
			</div>
		</header>
		<Alert v-if="loadError" role="alert" theme="red" :title="loadError" />
		<Alert v-if="lockedBy" role="status" theme="yellow" :title="lockMessage">
			<template #actions>
				<Button
					label="Copy design"
					aria-label="Copy design"
					:loading="copying"
					@click="copy"
				/>
			</template>
		</Alert>
		<Alert
			v-if="unsupportedProductWarning"
			role="alert"
			theme="yellow"
			data-testid="unsupported-series-product-alert"
			:title="unsupportedProductWarning"
		/>

		<div class="flex min-h-0 flex-1 flex-col md:flex-row">
			<!-- DOCKED LEFT ACCORDION RAIL (.left) + DOCKED SECONDARY DRAWER (.fly) -->
			<PropertiesPanel
				v-show="!leftCollapsed"
				ref="propertiesPanel"
				v-model:meta="meta"
				:finishes="finishes"
				:series-versions="seriesVersions"
				:ref-error="refError"
				:ref-readonly="!!savedName"
			/>

			<main
				ref="mainEl"
				class="relative flex min-h-[50vh] min-w-0 flex-1 items-stretch bg-[#f7f8fa] md:min-h-0"
				:class="
					sectionOn
						? 'flex-col overflow-hidden md:flex-row'
						: 'flex-col items-center justify-center overflow-hidden'
				"
			>
				<p v-if="loading" class="m-auto text-sm text-gray-500">Loading design...</p>
				<template v-else-if="!loadError">
					<!-- TOP-LEFT EVA FLOATING FAB DOCK (3 crisp Eva FAB buttons: Divider, Designs, Trash) -->
					<div
						ref="fabDockRef"
						data-testid="eva-fab-dock"
						class="absolute top-3.5 left-3 z-20 flex flex-col gap-1 rounded-[4px] bg-white p-1.5 shadow-[0_1px_6px_rgba(0,0,0,0.2)]"
					>
						<Tooltip text="Divider (Mullions, Transoms & Grids)">
							<button
								type="button"
								aria-label="Divider tools"
								class="flex size-10 items-center justify-center rounded-[4px] transition"
								:class="
									activePalette === 'divider'
										? 'bg-[#1a6fd4] text-white'
										: 'text-[#2d4a7a] hover:bg-[#f0f4fa]'
								"
								@click="togglePalette('divider')"
							>
								<span class="lucide-columns-2 size-5" aria-hidden="true" />
							</button>
						</Tooltip>
						<Tooltip text="Designs & Add-ons (Drag & Drop)">
							<button
								type="button"
								aria-label="Designs & Templates"
								class="flex size-10 items-center justify-center rounded-[4px] transition"
								:class="
									activePalette === 'designs'
										? 'bg-[#1a6fd4] text-white'
										: 'text-[#2d4a7a] hover:bg-[#f0f4fa]'
								"
								@click="togglePalette('designs')"
							>
								<span class="lucide-panel-right-open size-5" aria-hidden="true" />
							</button>
						</Tooltip>
						<div
							data-testid="edit-group-card"
							class="flex flex-col gap-1 border-t border-[#f0f1f3] pt-1"
						>
							<span
								:title="editSelectionChipLabel"
								style="white-space: nowrap"
								class="hidden"
								>{{ editSelectionChipLabel }}</span
							>
							<Tooltip :text="deleteLabel">
								<button
									type="button"
									aria-label="Delete"
									:aria-disabled="!canDelete"
									class="flex size-10 items-center justify-center rounded-[4px] transition"
									:class="
										canDelete
											? 'text-[#2d4a7a] hover:bg-red-50 hover:text-red-600'
											: 'cursor-not-allowed text-gray-400 opacity-45'
									"
									@click="canDelete && deleteSelected()"
								>
									<span class="lucide-trash-2 size-5" aria-hidden="true" />
									<span class="sr-only">{{ deleteLabel }}</span>
								</button>
							</Tooltip>
							<button
								type="button"
								aria-label="Reset panel"
								:aria-disabled="!canResetPanel"
								class="sr-only"
								@click="canResetPanel && resetPanel()"
							>
								Reset panel
							</button>
							<button
								type="button"
								aria-label="Merge split"
								:aria-disabled="!canRemoveSplit"
								class="sr-only"
								@click="canRemoveSplit && unsplitSelected()"
							>
								Merge split
							</button>
						</div>
					</div>

					<!-- FLOATING DIVIDER PALETTE (EXACT EVA SVGs + 5-COL TILE GRID + DRAG-AND-DROP) -->
					<div
						v-show="activePalette === 'divider'"
						ref="dividerPaletteRef"
						data-testid="eva-divider-palette"
						class="absolute top-3.5 left-[70px] z-30 flex max-h-[calc(100%-36px)] w-[348px] flex-col overflow-hidden rounded-[4px] border border-[#dcdfe4] bg-white shadow-[0_4px_18px_rgba(0,0,0,0.18)]"
					>
						<div
							class="flex items-center justify-between border-b border-[#f0f1f3] px-3 py-2.5"
						>
							<span class="text-[15px] font-semibold text-[#2b2f36]">Divider</span>
							<button
								type="button"
								class="rounded p-1 text-[#555] hover:bg-[#f0f1f3]"
								@click="activePalette = null"
							>
								✕
							</button>
						</div>
						<div class="flex flex-col gap-2.5 overflow-y-auto p-3 text-xs">
							<div
								class="rounded-[3px] border border-[#e4e9f0] bg-[#f6f8fb] px-2.5 py-1.5 text-[11px] text-[#5f6b7a]"
							>
								Drag any divider/grid onto a cell (1, 2...) or click to configure.
							</div>
							<div class="text-[13px] font-semibold text-[#2b2f36]">
								Mullions &amp; Transoms
							</div>
							<div class="grid grid-cols-5 gap-2">
								<button
									v-for="item in dividerMullions"
									:key="item.id"
									type="button"
									draggable="true"
									:title="item.id.replace(/_/g, ' ')"
									:aria-label="tileAriaLabel(item)"
									class="flex h-12 items-center justify-center rounded-[4px] border border-transparent bg-white p-1 transition hover:border-[#bfd7f5] hover:bg-[#e6effb] cursor-grab active:cursor-grabbing"
									@dragstart="onToolDragStart(item.kind, item.id, $event)"
									@click="applyToolToPath(item.kind, item.id)"
								>
									<img
										:src="item.src"
										:alt="item.id"
										class="pointer-events-none select-none object-contain"
										:style="{
											width: `${item.width}px`,
											height: `${item.height}px`,
											transform: item.transform || undefined,
										}"
									/>
								</button>
							</div>
							<div class="text-[13px] font-semibold text-[#2b2f36]">Joints</div>
							<div class="grid grid-cols-5 gap-2">
								<button
									v-for="item in dividerJoints"
									:key="item.id"
									type="button"
									draggable="true"
									:title="item.id"
									class="flex h-12 items-center justify-center rounded-[4px] border border-transparent bg-white p-1 transition hover:border-[#bfd7f5] hover:bg-[#e6effb] cursor-grab active:cursor-grabbing"
									@dragstart="onToolDragStart(item.kind, item.id, $event)"
									@click="applyToolToPath(item.kind, item.id)"
								>
									<img
										:src="item.src"
										:alt="item.id"
										class="pointer-events-none select-none object-contain"
										:style="{
											width: `${item.width}px`,
											height: `${item.height}px`,
										}"
									/>
								</button>
							</div>
							<div class="flex items-center gap-1.5 border-t border-[#f0f1f3] pt-2">
								<button
									type="button"
									aria-label="Split vertical"
									:disabled="!selectedLeaf"
									class="flex-1 rounded-[3px] border border-[#dcdfe4] bg-[#f6f7f9] py-1.5 text-[11px] font-medium text-[#2b2f36] hover:bg-[#e7e9ed] disabled:opacity-40"
									@click="split('v')"
								>
									Quick 2V Split
								</button>
								<button
									type="button"
									aria-label="Split horizontal"
									:disabled="!selectedLeaf"
									class="flex-1 rounded-[3px] border border-[#dcdfe4] bg-[#f6f7f9] py-1.5 text-[11px] font-medium text-[#2b2f36] hover:bg-[#e7e9ed] disabled:opacity-40"
									@click="split('h')"
								>
									Quick 2H Split
								</button>
							</div>
						</div>
					</div>

					<!-- FLOATING DESIGNS PALETTE (EXACT EVA SVGs + SEARCH + DRAG-AND-DROP) -->
					<div
						v-show="activePalette === 'designs'"
						ref="designsPaletteRef"
						data-testid="eva-designs-palette"
						class="absolute top-3.5 left-[70px] z-30 flex max-h-[calc(100%-36px)] w-[348px] flex-col overflow-hidden rounded-[4px] border border-[#dcdfe4] bg-white shadow-[0_4px_18px_rgba(0,0,0,0.18)]"
					>
						<div
							class="flex items-center justify-between border-b border-[#f0f1f3] px-3 py-2.5"
						>
							<span class="text-[15px] font-semibold text-[#2b2f36]">Designs</span>
							<button
								type="button"
								class="rounded p-1 text-[#555] hover:bg-[#f0f1f3]"
								@click="activePalette = null"
							>
								✕
							</button>
						</div>
						<div class="border-b border-[#f0f1f3] px-3 py-2">
							<div
								class="flex h-[34px] items-center gap-1.5 rounded-[3px] border border-[#cfd4da] bg-white px-2 text-[#777]"
							>
								<span class="lucide-search size-3.5 shrink-0" aria-hidden="true" />
								<input
									v-model="palSearch"
									type="text"
									placeholder="Search..."
									class="w-full border-0 bg-transparent text-[13px] text-[#2b2f36] outline-none"
								/>
							</div>
						</div>
						<div class="flex flex-col gap-3 overflow-y-auto p-3 text-xs">
							<div
								class="rounded-[3px] border border-[#e4e9f0] bg-[#f6f8fb] px-2.5 py-1.5 text-[11px] text-[#5f6b7a]"
							>
								Drag Openable / Add-ons onto any cell, or click a design tile.
							</div>

							<div
								v-for="sec in designSections"
								:key="sec.title"
								class="space-y-1.5"
							>
								<div class="text-[13px] font-semibold text-[#2b2f36]">
									{{ sec.title }}
								</div>
								<div class="grid grid-cols-5 gap-2">
									<button
										v-for="item in sec.items"
										:key="item.id"
										type="button"
										draggable="true"
										:title="item.id"
										:aria-label="tileAriaLabel(item)"
										:disabled="
											isInvalidSelection &&
											(item.kind === 'openable' || item.kind === 'addon')
										"
										class="flex h-12 items-center justify-center rounded-[4px] border border-transparent bg-white p-1 transition hover:border-[#bfd7f5] hover:bg-[#e6effb] cursor-grab active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-45"
										@dragstart="onToolDragStart(item.kind, item.id, $event)"
										@click="applyToolToPath(item.kind, item.id)"
									>
										<img
											:src="item.src"
											:alt="item.id"
											class="pointer-events-none select-none object-contain"
											:style="{
												width: `${item.width}px`,
												height: `${item.height}px`,
												transform: item.transform || undefined,
											}"
										/>
									</button>
								</div>
							</div>
						</div>
					</div>

					<div
						data-testid="designer-left-pane"
						class="relative flex h-full min-h-0 min-w-0 items-stretch justify-center overflow-hidden"
						:class="sectionOn && store.seriesVersion ? 'w-full md:shrink-0' : 'flex-1'"
						:style="
							sectionOn && store.seriesVersion
								? { width: `${splitRatio}%` }
								: undefined
						"
					>
						<!-- RIGHT-SIDE EVA SPEC TOASTER (.rtoast) FOR MULLION / TRANSOM / CUSTOM DIVIDER / GRID -->
						<div
							v-if="specPopover.open"
							data-testid="eva-divider-spec-popover"
							class="absolute top-4 right-16 z-30 flex w-[300px] flex-col gap-3 rounded-[4px] border border-[#dcdfe4] bg-white p-3.5 shadow-[0_4px_18px_rgba(0,0,0,0.18)]"
						>
							<div
								class="flex items-center justify-between border-b border-[#f0f1f3] pb-2"
							>
								<span class="text-[14px] font-semibold text-[#2b2f36]">
									{{
										specPopover.kind === "grid"
											? "Grid Specifications"
											: specPopover.kind === "transom"
											? "Transom Specification"
											: specPopover.kind === "mullion"
											? "Mullion Specification"
											: "Custom Divider Specification"
									}}
								</span>
								<button
									type="button"
									class="rounded p-0.5 text-[#555] hover:bg-[#f0f1f3]"
									@click="specPopover.open = false"
								>
									✕
								</button>
							</div>
							<template v-if="specPopover.kind === 'grid'">
								<div
									class="rounded-[4px] border border-[#e3e7ee] bg-[#f7f8fa] px-2.5 py-2 text-[11.5px] text-[#4b5563]"
								>
									<div class="font-semibold text-[#2b2f36]">
										Surface Glazing Grid
									</div>
									Sits on top of the selected glass/sash — glass stays 1 uncut
									pane.
								</div>
								<div class="space-y-1">
									<label class="block text-[12px] font-medium text-[#2b2f36]"
										>No. of Vertical Divisions
										<span class="text-red-500">*</span></label
									>
									<input
										v-model.number="specPopover.gridV"
										type="number"
										min="1"
										max="6"
										class="h-[36px] w-full rounded-[3px] border border-[#cfd4da] bg-white px-2.5 text-[13px] font-medium"
									/>
								</div>
								<div class="space-y-1">
									<label class="block text-[12px] font-medium text-[#2b2f36]"
										>No. of Horizontal Divisions
										<span class="text-red-500">*</span></label
									>
									<input
										v-model.number="specPopover.gridH"
										type="number"
										min="1"
										max="6"
										class="h-[36px] w-full rounded-[3px] border border-[#cfd4da] bg-white px-2.5 text-[13px] font-medium"
									/>
								</div>
								<div class="space-y-1">
									<label class="block text-[12px] font-medium text-[#2b2f36]"
										>Junction Arrangement</label
									>
									<select
										v-model="specPopover.gridJunc"
										class="h-[36px] w-full rounded-[3px] border border-[#cfd4da] bg-white px-2.5 text-[13px]"
									>
										<option value="Vertical dividers in full">
											Vertical dividers in full
										</option>
										<option value="Horizontal dividers in full">
											Horizontal dividers in full
										</option>
									</select>
								</div>
								<button
									v-if="specHasExistingGrid"
									type="button"
									class="text-left text-[12px] font-medium text-red-600 hover:underline"
									@click="removeSpecGrid"
								>
									Remove Grid from selected cells
								</button>
							</template>
							<template v-else>
								<div v-if="specPopover.kind === 'custom'" class="space-y-1">
									<span class="text-[12px] font-medium text-[#2b2f36]"
										>Direction</span
									>
									<div
										class="grid grid-cols-2 gap-1 rounded-[4px] bg-[#f0f1f3] p-0.5 text-xs"
									>
										<button
											type="button"
											class="rounded-[3px] py-1.5 font-medium"
											:class="
												specPopover.dir === 'v'
													? 'bg-white text-[#1a6fd4] shadow-2xs'
													: 'text-[#555]'
											"
											@click="specPopover.dir = 'v'"
										>
											Vertical (Mullion)
										</button>
										<button
											type="button"
											class="rounded-[3px] py-1.5 font-medium"
											:class="
												specPopover.dir === 'h'
													? 'bg-white text-[#1a6fd4] shadow-2xs'
													: 'text-[#555]'
											"
											@click="specPopover.dir = 'h'"
										>
											Horizontal (Transom)
										</button>
									</div>
								</div>
								<div class="space-y-1">
									<label class="block text-[12px] font-medium text-[#2b2f36]"
										>No. of
										{{
											specPopover.dir === "h" ? "Transoms" : "Mullions"
										}}</label
									>
									<input
										v-model.number="specPopover.count"
										type="number"
										min="1"
										max="6"
										class="h-[36px] w-full rounded-[3px] border border-[#cfd4da] bg-white px-2.5 text-[13px] font-medium"
									/>
								</div>
								<div class="space-y-1">
									<span class="text-[12px] font-medium text-[#2b2f36]"
										>Equalization Mode</span
									>
									<div
										class="grid grid-cols-2 gap-1 rounded-[4px] bg-[#f0f1f3] p-0.5 text-xs"
									>
										<button
											type="button"
											class="rounded-[3px] py-1.5 font-medium"
											:class="
												specPopover.eqMode === 'mullion'
													? 'bg-white text-[#1a6fd4] shadow-2xs'
													: 'text-[#555]'
											"
											@click="specPopover.eqMode = 'mullion'"
										>
											Mullion Eq.
										</button>
										<button
											type="button"
											class="rounded-[3px] py-1.5 font-medium"
											:class="
												specPopover.eqMode === 'glass'
													? 'bg-white text-[#1a6fd4] shadow-2xs'
													: 'text-[#555]'
											"
											@click="specPopover.eqMode = 'glass'"
										>
											Equal Glass
										</button>
									</div>
								</div>
							</template>
							<div v-if="allCells.length > 1" class="space-y-1">
								<span class="text-[12px] font-medium text-[#2b2f36]"
									>Apply to cells</span
								>
								<div class="flex flex-wrap gap-1.5">
									<button
										v-for="(c, idx) in allCells"
										:key="c.path"
										type="button"
										class="rounded-[3px] border px-2 py-0.5 text-xs font-semibold transition"
										:class="
											specPopover.cellPaths.includes(c.path)
												? 'border-[#1a6fd4] bg-[#e6effb] text-[#1a6fd4]'
												: 'border-[#cfd4da] bg-white text-[#555]'
										"
										@click="toggleSpecCell(c.path)"
									>
										G{{ idx + 1 }}
									</button>
								</div>
							</div>
							<div class="flex justify-end gap-2 border-t border-[#f0f1f3] pt-2.5">
								<button
									type="button"
									class="rounded-[3px] px-3 py-1.5 text-[13px] font-medium text-[#444] hover:bg-[#f0f1f3]"
									@click="specPopover.open = false"
								>
									Cancel
								</button>
								<button
									type="button"
									class="rounded-[3px] bg-[#1a6fd4] px-3.5 py-1.5 text-[13px] font-semibold text-white hover:bg-[#155db3]"
									@click="applySpecPopover"
								>
									Confirm
								</button>
							</div>
						</div>

						<!-- TOP-RIGHT CIRCULAR .vbar BUTTONS (Approx 3D, Open Sashes, Realistic 3D DXF) -->
						<div
							data-testid="eva-3d-fabs"
							class="absolute top-3.5 right-3.5 z-20 flex flex-col gap-2"
						>
							<Tooltip
								:text="
									viewMode === '3d' ? 'Back to 2D Elevation' : 'Approx 3D View'
								"
							>
								<button
									type="button"
									aria-label="3D"
									class="flex size-10 items-center justify-center rounded-full border shadow-[0_2px_8px_rgba(0,0,0,0.12)] transition"
									:class="
										viewMode === '3d'
											? 'border-[#1a6fd4] bg-[#e6effb] text-[#1a6fd4]'
											: 'border-[#dcdfe4] bg-white text-[#2d4a7a] hover:bg-[#f0f4fa]'
									"
									@click="toggle3DView('3d')"
								>
									<span class="lucide-box size-5" aria-hidden="true" />
									<span class="sr-only">3D</span>
								</button>
							</Tooltip>
							<Tooltip
								v-if="viewMode === '3d'"
								:text="sashesOpen ? 'Close Sashes' : 'Open Sashes'"
							>
								<button
									type="button"
									aria-label="Open sashes"
									class="flex size-10 items-center justify-center rounded-full border shadow-[0_2px_8px_rgba(0,0,0,0.12)] transition"
									:class="
										sashesOpen
											? 'border-[#1a6fd4] bg-[#e6effb] text-[#1a6fd4]'
											: 'border-[#dcdfe4] bg-white text-[#2d4a7a] hover:bg-[#f0f4fa]'
									"
									@click="sashesOpen = !sashesOpen"
								>
									<span class="lucide-door-open size-5" aria-hidden="true" />
								</button>
							</Tooltip>
							<Tooltip
								:text="
									viewMode === 'realistic3d'
										? 'Back to 2D Elevation'
										: 'Realistic 3D View (DXF Profiles)'
								"
							>
								<button
									type="button"
									aria-label="Realistic 3D"
									class="flex size-10 items-center justify-center rounded-full border shadow-[0_2px_8px_rgba(0,0,0,0.12)] transition"
									:class="
										viewMode === 'realistic3d'
											? 'border-[#1a6fd4] bg-[#e6effb] text-[#1a6fd4]'
											: 'border-[#dcdfe4] bg-white text-[#2d4a7a] hover:bg-[#f0f4fa]'
									"
									@click="toggle3DView('realistic3d')"
								>
									<span class="lucide-layers size-5" aria-hidden="true" />
								</button>
							</Tooltip>
						</div>

						<!-- BOTTOM TOAST (Prototype dark pill, e.g. 'Applied Right Openable to G2') -->
						<div
							v-if="evaToast"
							class="pointer-events-none absolute bottom-3.5 left-1/2 z-30 -translate-x-1/2 rounded-[4px] bg-[#1e293b] px-3.5 py-1.5 text-[12px] font-medium text-white shadow-lg"
						>
							{{ evaToast }}
						</div>

						<!-- BOTTOM-LEFT BOXY INSIDE | OUTSIDE SWITCH (aligned with left FAB dock) -->
						<div
							data-testid="eva-side-pill"
							role="group"
							aria-label="View"
							class="absolute bottom-3.5 left-3 z-20 flex rounded-[4px] border border-[#dcdfe4] bg-white p-1 shadow-[0_1px_6px_rgba(0,0,0,0.16)]"
						>
							<span
								aria-hidden="true"
								class="pointer-events-none absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-[3px] bg-[#1a6fd4] transition-[left] duration-200 ease-out"
								:style="{ left: viewSide === 'inside' ? '4px' : 'calc(50%)' }"
							/>
							<button
								type="button"
								:aria-pressed="viewSide === 'inside'"
								class="relative z-10 min-w-[68px] rounded-[3px] px-3 py-1 text-[12px] font-medium transition-colors duration-150"
								:class="
									viewSide === 'inside'
										? 'text-white'
										: 'text-[#2d4a7a] hover:bg-[#f0f4fa]'
								"
								@click="viewSide = 'inside'"
							>
								Inside
							</button>
							<button
								type="button"
								:aria-pressed="viewSide === 'outside'"
								class="relative z-10 min-w-[68px] rounded-[3px] px-3 py-1 text-[12px] font-medium transition-colors duration-150"
								:class="
									viewSide === 'outside'
										? 'text-white'
										: 'text-[#2d4a7a] hover:bg-[#f0f4fa]'
								"
								@click="viewSide = 'outside'"
							>
								Outside
							</button>
						</div>

						<Approx3DView
							v-if="viewMode === '3d'"
							ref="approx3d"
							:design="store.design"
							:selected-path="store.selectedPath"
							:side="viewSide"
							:sashes-open="sashesOpen"
							:finish-color="finishColor"
							:outside-finish-color="outsideFinishColor"
							:finish-name="finishName"
							:area-m2="store.result?.area_m2"
							:weight-kg="store.result?.window_kg"
							:qty="meta.qty"
							:profile-widths="effectiveProfileWidths"
							:role-defaults="effectiveRoleDefaults"
							@select="store.select"
							@update:side="viewSide = $event"
							@drop-tool="onDropTool"
						/>
						<Window3DView
							v-else-if="viewMode === 'realistic3d'"
							ref="realistic3d"
							:design="store.design"
							:selected-path="store.selectedPath"
							:side="viewSide"
							:sashes-open="sashesOpen"
							:finish-color="finishColor"
							:outside-finish-color="outsideFinishColor"
							:finish-name="finishName"
							@select="store.select"
							@update:side="viewSide = $event"
							@drop-tool="onDropTool"
						/>
						<WindowCanvas
							v-show="viewMode === '2d'"
							ref="canvas"
							:design="store.design"
							:selected-path="store.selectedPath"
							:issue-paths="issuePaths"
							:view="viewSide"
							:finish-color="
								viewSide === 'outside' ? outsideFinishColor : finishColor
							"
							:section="sectionOn ? cutPos : null"
							:members="store.result?.members"
							:glass="store.result?.glass"
							:profile-widths="effectiveProfileWidths"
							:role-defaults="effectiveRoleDefaults"
							@select="store.select"
							@move-split="onMoveSplit"
							@drag-start="store.beginDrag()"
							@drag-end="store.endDrag()"
							@update:cut="(c) => pickCut(c.axis, c.at)"
							@drop-tool="onDropTool"
							@edit-dim="openDimModal"
						/>
					</div>

					<!-- Draggable Split Workspace Resizer Separator -->
					<div
						v-if="sectionOn && store.seriesVersion"
						data-testid="workspace-resizer"
						role="separator"
						aria-orientation="vertical"
						aria-label="Resize workspace split"
						:aria-valuenow="Math.round(splitRatio)"
						title="Drag left or right to resize Window Designer and Cross-Section workspaces (double-click to reset)"
						class="group relative z-10 flex h-2 w-full shrink-0 cursor-row-resize items-center justify-center bg-gray-200 transition-colors hover:bg-blue-500 md:h-full md:w-2 md:cursor-col-resize"
						:class="resizingSplit ? 'bg-blue-600' : ''"
						@pointerdown="onSplitResizerPointerDown"
						@pointermove="onSplitResizerPointerMove"
						@pointerup="endSplitResize"
						@dblclick="splitRatio = 50"
					>
						<div
							class="h-1 w-8 rounded-full bg-gray-400 transition-colors group-hover:bg-white md:h-8 md:w-1"
							:class="resizingSplit ? 'bg-white' : ''"
						/>
					</div>

					<div
						v-if="sectionOn && store.seriesVersion"
						data-testid="section-split-pane"
						class="flex h-full min-h-[42vh] min-w-0 flex-1 overflow-hidden md:min-h-0"
					>
						<SectionView
							v-model:axis="cutAxis"
							class="h-full w-full flex-1"
							:design="store.design"
							:series-version="store.seriesVersion"
							:at="cutAt[cutAxis]"
							:selected-path="store.selectedPath"
							@cut="onSnapped"
							@update:section-map="onUpdateSectionMap"
							@update:grill="onUpdateGrill"
							@update:mirror-sync="store.setMirrorSync"
							@update:compact-glass="store.setCompactGlass"
							@update:section-viewport="(ax, vp) => store.setSectionViewport(ax, vp)"
							@open-profile-picker="onSectionOpenProfilePicker"
							@profile-orientation-updated="
								propertiesPanel?.refreshProfileCatalog?.()
							"
							@select="store.select"
						/>
					</div>
				</template>
			</main>
		</div>
		<div
			v-if="pendingReplaceDrop"
			data-testid="replace-design-confirm-modal"
			role="dialog"
			aria-modal="true"
			aria-labelledby="replace-design-title"
			class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/35 px-4 backdrop-blur-[2px]"
			@click.self="cancelReplaceDrop"
		>
			<div
				class="w-full max-w-[400px] overflow-hidden rounded-[8px] border border-[#dcdfe4] bg-white shadow-[0_14px_36px_rgba(15,23,42,0.18)]"
			>
				<div class="flex items-start gap-3 px-5 pt-5 pb-4">
					<div
						class="flex size-9 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-600"
					>
						<span class="lucide-alert-triangle size-5" aria-hidden="true" />
					</div>
					<div class="min-w-0 flex-1">
						<h3
							id="replace-design-title"
							class="text-[15px] font-semibold text-[#1f2937]"
						>
							Replace current design?
						</h3>
						<p class="mt-1.5 text-[13px] leading-relaxed text-[#4b5563]">
							Dropping
							<span class="font-semibold text-[#1f2937]">{{
								pendingReplaceDrop.id
							}}</span>
							onto empty space will completely clear your current design and replace
							it with this one.
						</p>
					</div>
				</div>
				<div
					class="flex items-center justify-end gap-2 border-t border-[#f0f1f3] bg-[#f8fafc] px-5 py-3"
				>
					<button
						type="button"
						class="h-8 rounded-[4px] border border-[#d1d5db] bg-white px-3.5 text-[13px] font-medium text-[#374151] hover:bg-[#f3f4f6]"
						@click="cancelReplaceDrop"
					>
						Cancel
					</button>
					<button
						type="button"
						data-testid="confirm-replace-design-btn"
						class="h-8 rounded-[4px] bg-[#1a6fd4] px-3.5 text-[13px] font-semibold text-white hover:bg-[#155db3]"
						@click="confirmReplaceDrop"
					>
						Replace Design
					</button>
				</div>
			</div>
		</div>
		<ResultsBar />
	</div>
</template>
