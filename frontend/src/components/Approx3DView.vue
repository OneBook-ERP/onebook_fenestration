<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { layoutGeom } from "@/design/geometry";
import type { Design, SashNode } from "@/design/types";

const props = withDefaults(
	defineProps<{
		design: Design;
		selectedPath: string | null;
		side?: "inside" | "outside";
		sashesOpen?: boolean;
		finishColor?: string;
		outsideFinishColor?: string;
		finishName?: string;
		areaM2?: number;
		weightKg?: number;
		qty?: number;
		profileWidths?: Record<string, number>;
		roleDefaults?: Record<string, string>;
	}>(),
	{
		side: "inside",
		sashesOpen: false,
		finishColor: "#a8b0ba",
		outsideFinishColor: undefined,
		finishName: "",
		areaM2: undefined,
		weightKg: undefined,
		qty: 1,
		profileWidths: undefined,
		roleDefaults: undefined,
	}
);

const emit = defineEmits<{
	select: [path: string];
	"update:side": [side: "inside" | "outside"];
	"drop-tool": [
		payload: { kind: string; id: string; cellPath: string; replaceDesign?: boolean }
	];
}>();

const stageEl = ref<HTMLElement | null>(null);
const cv3d = ref<HTMLCanvasElement | null>(null);
const cv3dHud = ref<HTMLCanvasElement | null>(null);
const webGLSupported = ref(true);

type Vec3 = [number, number, number];
type Vec4 = [number, number, number, number];
type Xform = (p: Vec3) => Vec3;

interface GLState {
	gl: WebGLRenderingContext;
	solidProg: WebGLProgram;
	lineProg: WebGLProgram;
	sLoc: {
		pos: number;
		norm: number;
		col: number;
		mvp: WebGLUniformLocation | null;
		nmat: WebGLUniformLocation | null;
	};
	lLoc: {
		pos: number;
		col: number;
		mv: WebGLUniformLocation | null;
		p: WebGLUniformLocation | null;
	};
	bPos: WebGLBuffer | null;
	bNorm: WebGLBuffer | null;
	bCol: WebGLBuffer | null;
	bLPos: WebGLBuffer | null;
	bLCol: WebGLBuffer | null;
}

let glCtx: GLState | null = null;
let resizeObserver: ResizeObserver | null = null;
let openFrac = props.sashesOpen ? 1 : 0;
let openTarget = props.sashesOpen ? 1 : 0;
let openRaf = 0;

let yaw = props.side === "outside" ? Math.PI - 0.42 : -0.42;
let pitch = 0.16;
let zoom = 1;
let panX = 0;
let panY = 0;
let camAnim: { raf: number } | null = null;
let drag: {
	mode: "orbit" | "pan";
	x: number;
	y: number;
	yaw: number;
	pitch: number;
	panX: number;
	panY: number;
	moved: boolean;
} | null = null;
const isDragging = ref(false);

interface HitRegion {
	path: string;
	pts: [number, number][];
}
let hitRegions: HitRegion[] = [];
let windowHitPolys: [number, number][][] = [];
let lastStageSize = { w: 800, h: 600 };

function hexToRgb01(hex?: string): [number, number, number] {
	let h = String(hex || "#a8b0ba").replace("#", "");
	if (h.length === 3)
		h = h
			.split("")
			.map((ch) => ch + ch)
			.join("");
	if (!/^[0-9a-fA-F]{6}$/.test(h)) h = "a8b0ba";
	return [
		parseInt(h.slice(0, 2), 16) / 255,
		parseInt(h.slice(2, 4), 16) / 255,
		parseInt(h.slice(4, 6), 16) / 255,
	];
}

function mulMat4(a: Float32Array, b: Float32Array): Float32Array {
	const o = new Float32Array(16);
	for (let c = 0; c < 4; c++) {
		for (let r = 0; r < 4; r++) {
			o[c * 4 + r] =
				a[r] * b[c * 4] +
				a[4 + r] * b[c * 4 + 1] +
				a[8 + r] * b[c * 4 + 2] +
				a[12 + r] * b[c * 4 + 3];
		}
	}
	return o;
}

function initWebGL(canvas: HTMLCanvasElement): GLState | null {
	if (glCtx) return glCtx;
	let gl: WebGLRenderingContext | null = null;
	try {
		gl = (canvas.getContext("webgl", { antialias: true, alpha: true }) ||
			canvas.getContext("experimental-webgl", {
				antialias: true,
				alpha: true,
			})) as WebGLRenderingContext | null;
	} catch {
		return null;
	}
	if (!gl) return null;

	const compile = (type: number, src: string) => {
		const sh = gl!.createShader(type)!;
		gl!.shaderSource(sh, src);
		gl!.compileShader(sh);
		if (!gl!.getShaderParameter(sh, gl!.COMPILE_STATUS)) {
			throw new Error(gl!.getShaderInfoLog(sh) || "Shader compile error");
		}
		return sh;
	};
	const link = (vs: string, fs: string) => {
		const pr = gl!.createProgram()!;
		gl!.attachShader(pr, compile(gl!.VERTEX_SHADER, vs));
		gl!.attachShader(pr, compile(gl!.FRAGMENT_SHADER, fs));
		gl!.linkProgram(pr);
		if (!gl!.getProgramParameter(pr, gl!.LINK_STATUS)) {
			throw new Error(gl!.getProgramInfoLog(pr) || "Program link error");
		}
		return pr;
	};

	const solidProg = link(
		`attribute vec3 aPos; attribute vec3 aNorm; attribute vec4 aCol;
		 uniform mat4 uMVP; uniform mat3 uNMat; varying vec4 vCol;
		 void main(){
		   gl_Position = uMVP * vec4(aPos, 1.0);
		   vec3 n = normalize(uNMat * aNorm);
		   vec3 l1 = normalize(vec3(0.36, 0.58, 0.73));
		   vec3 l2 = normalize(vec3(-0.45, -0.25, 0.62));
		   float lit = 0.52 + 0.36 * abs(dot(n, l1)) + 0.14 * abs(dot(n, l2));
		   vCol = vec4(clamp(aCol.rgb * lit, 0.0, 1.0), aCol.a);
		 }`,
		`precision mediump float; varying vec4 vCol; void main(){ gl_FragColor = vCol; }`
	);

	const lineProg = link(
		`attribute vec3 aPos; attribute vec4 aCol; uniform mat4 uMV; uniform mat4 uP; varying vec4 vCol;
		 void main(){
		   vec4 vp = uMV * vec4(aPos, 1.0);
		   vp.z += 1.0;
		   gl_Position = uP * vp;
		   vCol = aCol;
		 }`,
		`precision mediump float; varying vec4 vCol; void main(){ gl_FragColor = vCol; }`
	);

	glCtx = {
		gl,
		solidProg,
		lineProg,
		sLoc: {
			pos: gl.getAttribLocation(solidProg, "aPos"),
			norm: gl.getAttribLocation(solidProg, "aNorm"),
			col: gl.getAttribLocation(solidProg, "aCol"),
			mvp: gl.getUniformLocation(solidProg, "uMVP"),
			nmat: gl.getUniformLocation(solidProg, "uNMat"),
		},
		lLoc: {
			pos: gl.getAttribLocation(lineProg, "aPos"),
			col: gl.getAttribLocation(lineProg, "aCol"),
			mv: gl.getUniformLocation(lineProg, "uMV"),
			p: gl.getUniformLocation(lineProg, "uP"),
		},
		bPos: gl.createBuffer(),
		bNorm: gl.createBuffer(),
		bCol: gl.createBuffer(),
		bLPos: gl.createBuffer(),
		bLCol: gl.createBuffer(),
	};
	return glCtx;
}

function hingePositions(a: number, b: number, count: number): number[] {
	const span = b - a;
	if (count <= 1) return [a + span * 0.5];
	const pad = Math.min(130, span * 0.14);
	const start = a + pad;
	const end = b - pad;
	return Array.from({ length: count }, (_, i) => start + ((end - start) * i) / (count - 1));
}

function cancelCamAnim() {
	if (camAnim) {
		cancelAnimationFrame(camAnim.raf);
		camAnim = null;
	}
}

function animateCam(
	targetYaw: number,
	targetPitch = pitch,
	targetZoom = zoom,
	durMs = 380,
	targetPanX = panX,
	targetPanY = panY
) {
	cancelCamAnim();
	if (typeof requestAnimationFrame !== "function") {
		yaw = targetYaw;
		pitch = targetPitch;
		zoom = targetZoom;
		panX = targetPanX;
		panY = targetPanY;
		draw3D();
		return;
	}
	const sYaw = yaw;
	const sPitch = pitch;
	const sZoom = zoom;
	const sPanX = panX;
	const sPanY = panY;
	let dYaw = targetYaw - sYaw;
	while (dYaw > Math.PI) dYaw -= Math.PI * 2;
	while (dYaw < -Math.PI) dYaw += Math.PI * 2;
	const dPitch = targetPitch - sPitch;
	const dZoom = targetZoom - sZoom;
	const dPanX = targetPanX - sPanX;
	const dPanY = targetPanY - sPanY;
	const t0 = performance.now();
	const anim = { raf: 0 };
	camAnim = anim;
	const step = () => {
		if (camAnim !== anim) return;
		const t = Math.min(1, (performance.now() - t0) / durMs);
		const e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
		yaw = sYaw + dYaw * e;
		pitch = sPitch + dPitch * e;
		zoom = sZoom + dZoom * e;
		panX = sPanX + dPanX * e;
		panY = sPanY + dPanY * e;
		draw3D();
		if (t < 1) anim.raf = requestAnimationFrame(step);
		else camAnim = null;
	};
	anim.raf = requestAnimationFrame(step);
}

let skipNextSideWatch = false;
function resetCam() {
	if (props.side !== "inside") {
		skipNextSideWatch = true;
		emit("update:side", "inside");
	}
	animateCam(0, 0, 1, 360, 0, 0);
}

defineExpose({ resetCam });

function draw3D() {
	const stage = stageEl.value;
	const glCanvas = cv3d.value;
	const hudCanvas = cv3dHud.value;
	if (!stage || !glCanvas) return;
	const cw = stage.clientWidth || 800;
	const ch = stage.clientHeight || 600;
	const { width: W, height: H } = props.design;
	const geom = layoutGeom(props.design);
	const widths = props.profileWidths ?? {};
	const defaults = props.roleDefaults ?? {};

	const frameCode =
		props.design.frameProfileId || props.design.profiles?.frame || defaults.frame;
	const ff = (frameCode && widths[frameCode]) || 42;
	const mullCode =
		props.design.mullionProfileId || props.design.profiles?.mullion || defaults.mullion;
	const bf = (mullCode && widths[mullCode]) || 40;
	const sashFaceForCell = (cellPath: string, sashNode: SashNode) => {
		const code =
			sashNode.profile ||
			props.design.profiles?.[cellPath] ||
			props.design.sashProfileId ||
			props.design.profiles?.sash ||
			defaults.sash;
		return (code && widths[code]) || 50;
	};

	const frameCfg = props.design.frameConfig ?? "4-side";
	const hasBottom = frameCfg === "4-side";
	const hasThreshold = frameCfg === "3-side-threshold";
	const bFace = hasBottom ? ff : hasThreshold ? 17 : 0;
	const rawTrackCount = props.design.isSliding ? Math.max(2, props.design.trackCount || 2) : 1;
	const frameD = Math.max(
		frameCfg !== "4-side" ? 70 : 56,
		props.design.isSliding ? rawTrackCount * 24 + 14 : 56
	);

	const inCol = props.design.colorMode === "none" ? "#a8b0ba" : props.finishColor || "#a8b0ba";
	const outCol =
		props.design.colorMode === "none"
			? "#a8b0ba"
			: props.design.colorMode === "dual" && props.outsideFinishColor
			? props.outsideFinishColor
			: inCol;
	const hi = "#5b9be8";
	const sl = props.selectedPath || "";

	// Camera ModelView + Perspective matrices (exact match between WebGL & HUD)
	const cy = Math.cos(yaw);
	const sy = Math.sin(yaw);
	const cp = Math.cos(pitch);
	const sp = Math.sin(pitch);
	const fov = (34 * Math.PI) / 180;
	const aspect = Math.max(0.2, cw / Math.max(1, ch));
	const tY = Math.tan(fov / 2);
	const tX = tY * aspect;
	const camDist = Math.max((H + 340) / (2 * tY), (W + 360) / (2 * tX)) / zoom;
	const mv = new Float32Array([
		cy,
		sy * sp,
		-sy * cp,
		0,
		0,
		cp,
		sp,
		0,
		sy,
		-cy * sp,
		cy * cp,
		0,
		panX,
		panY,
		-camDist,
		1,
	]);
	const nmat = new Float32Array([
		mv[0],
		mv[1],
		mv[2],
		mv[4],
		mv[5],
		mv[6],
		mv[8],
		mv[9],
		mv[10],
	]);
	const boundR = Math.hypot(W, H, frameD) * 0.72;
	const near = Math.max(80, camDist - boundR * 2.4);
	const far = camDist + boundR * 2.8;
	const f = 1 / tY;
	const nf = 1 / (near - far);
	const persp = new Float32Array([
		f / aspect,
		0,
		0,
		0,
		0,
		f,
		0,
		0,
		0,
		0,
		(far + near) * nf,
		-1,
		0,
		0,
		2 * far * near * nf,
		0,
	]);
	const mvp = mulMat4(persp, mv);
	const viewZ = (p: Vec3) => mv[2] * p[0] + mv[6] * p[1] + mv[10] * p[2] + mv[14];
	const proj = (p: Vec3): Vec3 => {
		const x = mvp[0] * p[0] + mvp[4] * p[1] + mvp[8] * p[2] + mvp[12];
		const y = mvp[1] * p[0] + mvp[5] * p[1] + mvp[9] * p[2] + mvp[13];
		const z = mvp[2] * p[0] + mvp[6] * p[1] + mvp[10] * p[2] + mvp[14];
		const w4 = mvp[3] * p[0] + mvp[7] * p[1] + mvp[11] * p[2] + mvp[15] || 1;
		return [((x / w4) * 0.5 + 0.5) * cw, (0.5 - (y / w4) * 0.5) * ch, z / w4];
	};
	const camFacingInside = cy >= 0;

	const opPos: number[] = [];
	const opNorm: number[] = [];
	const opCol: number[] = [];
	const lnPos: number[] = [];
	const lnCol: number[] = [];
	const transGroups: { z: number; p: number[]; n: number[]; c: number[] }[] = [];

	const pushTri = (
		arrP: number[],
		arrN: number[],
		arrC: number[],
		a: Vec3,
		b: Vec3,
		c3: Vec3,
		rgb: [number, number, number],
		alpha: number
	) => {
		const ux = b[0] - a[0],
			uy = b[1] - a[1],
			uz = b[2] - a[2];
		const vx = c3[0] - a[0],
			vy = c3[1] - a[1],
			vz = c3[2] - a[2];
		let nx = uy * vz - uz * vy,
			ny = uz * vx - ux * vz,
			nz = ux * vy - uy * vx;
		const len = Math.hypot(nx, ny, nz) || 1;
		nx /= len;
		ny /= len;
		nz /= len;
		arrP.push(a[0], a[1], a[2], b[0], b[1], b[2], c3[0], c3[1], c3[2]);
		arrN.push(nx, ny, nz, nx, ny, nz, nx, ny, nz);
		arrC.push(
			rgb[0],
			rgb[1],
			rgb[2],
			alpha,
			rgb[0],
			rgb[1],
			rgb[2],
			alpha,
			rgb[0],
			rgb[1],
			rgb[2],
			alpha
		);
	};
	const pushEdge = (a: Vec3, b: Vec3, col: Vec4 = [0.13, 0.16, 0.21, 0.92]) => {
		lnPos.push(a[0], a[1], a[2], b[0], b[1], b[2]);
		lnCol.push(col[0], col[1], col[2], col[3], col[0], col[1], col[2], col[3]);
	};

	interface HexOpts {
		xf?: Xform | null;
		sel?: boolean;
		inCol?: string;
		outCol?: string;
		sideCol?: string;
		alpha?: number;
		edgeCol?: Vec4;
		noEdges?: boolean;
		hasBottom?: boolean;
	}

	const addHex = (V: Vec3[], o: HexOpts = {}) => {
		const xf = o.xf;
		const P3 = xf ? V.map(xf) : V;
		const cIn = hexToRgb01(o.sel ? hi : o.inCol || inCol);
		const cOut = hexToRgb01(o.sel ? hi : o.outCol || outCol);
		const cSide = hexToRgb01(o.sel ? hi : o.sideCol || o.inCol || inCol);
		const al = o.alpha ?? 1;
		const edgeCol: Vec4 = o.edgeCol || [0.14, 0.17, 0.22, 0.88];
		const faces: [number, number, number, number, [number, number, number]][] = [
			[0, 1, 2, 3, cIn],
			[5, 4, 7, 6, cOut],
			[3, 2, 6, 7, cSide],
			[4, 5, 1, 0, cSide],
			[1, 5, 6, 2, cSide],
			[4, 0, 3, 7, cSide],
		];
		if (al < 0.99) {
			const gP: number[] = [];
			const gN: number[] = [];
			const gC: number[] = [];
			let zSum = 0;
			for (let i = 0; i < 8; i++) zSum += viewZ(P3[i]);
			for (const [a, b, c2, d, rgb] of faces) {
				pushTri(gP, gN, gC, P3[a], P3[b], P3[c2], rgb, al);
				pushTri(gP, gN, gC, P3[a], P3[c2], P3[d], rgb, al);
			}
			transGroups.push({ z: zSum / 8, p: gP, n: gN, c: gC });
		} else {
			for (const [a, b, c2, d, rgb] of faces) {
				pushTri(opPos, opNorm, opCol, P3[a], P3[b], P3[c2], rgb, 1);
				pushTri(opPos, opNorm, opCol, P3[a], P3[c2], P3[d], rgb, 1);
			}
		}
		if (!o.noEdges) {
			const E: [number, number][] = [
				[0, 1],
				[1, 2],
				[2, 3],
				[3, 0],
				[4, 5],
				[5, 6],
				[6, 7],
				[7, 4],
				[0, 4],
				[1, 5],
				[2, 6],
				[3, 7],
			];
			for (const [a, b] of E) pushEdge(P3[a], P3[b], edgeCol);
		}
	};

	const addBox = (
		x0: number,
		y0: number,
		z0: number,
		x1: number,
		y1: number,
		z1: number,
		o: HexOpts = {}
	) => {
		addHex(
			[
				[x0, y0, z1],
				[x1, y0, z1],
				[x1, y1, z1],
				[x0, y1, z1],
				[x0, y0, z0],
				[x1, y0, z0],
				[x1, y1, z0],
				[x0, y1, z0],
			],
			o
		);
	};

	const addMiterRing = (
		x0: number,
		y0: number,
		x1: number,
		y1: number,
		fw: number,
		z0: number,
		z1: number,
		o: HexOpts = {}
	) => {
		const hb = o.hasBottom !== false;
		const wEff = Math.min(fw, (x1 - x0) * 0.45, (y1 - y0) * 0.45);
		const ix0 = x0 + wEff,
			ix1 = x1 - wEff,
			iy0 = y0 + wEff,
			iy1 = y1 - wEff;
		const lbY = hb ? iy0 : y0;
		// Top bar (45°/45°)
		addHex(
			[
				[ix0, iy1, z1],
				[ix1, iy1, z1],
				[x1, y1, z1],
				[x0, y1, z1],
				[ix0, iy1, z0],
				[ix1, iy1, z0],
				[x1, y1, z0],
				[x0, y1, z0],
			],
			o
		);
		// Left jamb
		addHex(
			[
				[x0, y0, z1],
				[ix0, lbY, z1],
				[ix0, iy1, z1],
				[x0, y1, z1],
				[x0, y0, z0],
				[ix0, lbY, z0],
				[ix0, iy1, z0],
				[x0, y1, z0],
			],
			o
		);
		// Right jamb
		addHex(
			[
				[ix1, lbY, z1],
				[x1, y0, z1],
				[x1, y1, z1],
				[ix1, iy1, z1],
				[ix1, lbY, z0],
				[x1, y0, z0],
				[x1, y1, z0],
				[ix1, iy1, z0],
			],
			o
		);
		if (hb) {
			// Bottom bar (45°/45°)
			addHex(
				[
					[x0, y0, z1],
					[x1, y0, z1],
					[ix1, iy0, z1],
					[ix0, iy0, z1],
					[x0, y0, z0],
					[x1, y0, z0],
					[ix1, iy0, z0],
					[ix0, iy0, z0],
				],
				o
			);
		}
	};

	const addCylBarrel = (
		cx2: number,
		cy2: number,
		cz2: number,
		r: number,
		len: number,
		axis: "x" | "y" | "z",
		o: HexOpts = {}
	) => {
		const segs = 8;
		const xf = o.xf;
		const rgb = hexToRgb01(o.inCol || "#1e242c");
		const ec: Vec4 = o.edgeCol || [0.06, 0.08, 0.11, 0.9];
		const h2 = len / 2;
		const ringA: Vec3[] = [];
		const ringB: Vec3[] = [];
		for (let i = 0; i < segs; i++) {
			const a = (i / segs) * Math.PI * 2;
			const ca = Math.cos(a) * r;
			const sa = Math.sin(a) * r;
			const pA: Vec3 =
				axis === "y"
					? [cx2 + ca, cy2 - h2, cz2 + sa]
					: axis === "z"
					? [cx2 + ca, cy2 + sa, cz2 - h2]
					: [cx2 - h2, cy2 + ca, cz2 + sa];
			const pB: Vec3 =
				axis === "y"
					? [cx2 + ca, cy2 + h2, cz2 + sa]
					: axis === "z"
					? [cx2 + ca, cy2 + sa, cz2 + h2]
					: [cx2 + h2, cy2 + ca, cz2 + sa];
			ringA.push(xf ? xf(pA) : pA);
			ringB.push(xf ? xf(pB) : pB);
		}
		const cRawA: Vec3 =
			axis === "y"
				? [cx2, cy2 - h2, cz2]
				: axis === "z"
				? [cx2, cy2, cz2 - h2]
				: [cx2 - h2, cy2, cz2];
		const cRawB: Vec3 =
			axis === "y"
				? [cx2, cy2 + h2, cz2]
				: axis === "z"
				? [cx2, cy2, cz2 + h2]
				: [cx2 + h2, cy2, cz2];
		const cA = xf ? xf(cRawA) : cRawA;
		const cB = xf ? xf(cRawB) : cRawB;
		for (let i = 0; i < segs; i++) {
			const j = (i + 1) % segs;
			pushTri(opPos, opNorm, opCol, ringA[i], ringA[j], ringB[j], rgb, 1);
			pushTri(opPos, opNorm, opCol, ringA[i], ringB[j], ringB[i], rgb, 1);
			pushTri(opPos, opNorm, opCol, cA, ringA[j], ringA[i], rgb, 1);
			pushTri(opPos, opNorm, opCol, cB, ringB[i], ringB[j], rgb, 1);
			pushEdge(ringA[i], ringA[j], ec);
			pushEdge(ringB[i], ringB[j], ec);
		}
	};

	const rotY = (p: Vec3, px0: number, pz0: number, ang: number): Vec3 => {
		const dx = p[0] - px0,
			dz = p[2] - pz0,
			ca = Math.cos(ang),
			sa = Math.sin(ang);
		return [px0 + dx * ca + dz * sa, p[1], pz0 - dx * sa + dz * ca];
	};
	const rotX = (p: Vec3, py0: number, pz0: number, ang: number): Vec3 => {
		const dy = p[1] - py0,
			dz = p[2] - pz0,
			ca = Math.cos(ang),
			sa = Math.sin(ang);
		return [p[0], py0 + dy * ca - dz * sa, pz0 + dy * sa + dz * ca];
	};

	// Frappe layoutGeom has y=0 at BOTTOM, y=H at TOP
	const mx = (xMm: number) => xMm - W / 2;
	const my = (yMm: number) => yMm - H / 2;
	const fHalf = frameD / 2;
	const fSel = sl === "FRAME" || (sl === "F1" && props.design.root.type === "split");
	const bxL = mx(0),
		bxR = mx(W),
		byB = my(0),
		byT = my(H);

	interface HudLine {
		a: Vec3;
		b: Vec3;
		stroke: string;
		lw?: number;
		dash?: number[];
		xf?: Xform | null;
		arrow?: boolean;
		bothArrows?: boolean;
	}
	interface HudLabel {
		x: number;
		y: number;
		t: string;
		bg: string;
		fg: string;
		st: string;
		round?: boolean;
	}
	const hudLines: HudLine[] = [];
	const labels: HudLabel[] = [];

	// 1. OUTER FRAME F1 (True 45°/45° miters; 90° bottom cuts on 3-sided frames)
	addMiterRing(bxL, byB, bxR, byT, ff, -fHalf, fHalf, { hasBottom, sel: fSel });
	if (hasThreshold) {
		addBox(bxL + ff, byB, -fHalf + 5, bxR - ff, byB + 17, fHalf - 5, {
			inCol: "#cbd5e1",
			outCol: "#94a3b8",
			sideCol: "#cbd5e1",
			sel: fSel,
		});
	} else if (!hasBottom) {
		hudLines.push({
			a: [bxL, byB, 0],
			b: [bxR, byB, 0],
			stroke: "#64748b",
			lw: 1.6,
			dash: [6, 4],
		});
	}

	// 2. STRUCTURAL DIVIDERS (Mullions & Transoms — omitted for sliding multi-track designs)
	const dHalf = fHalf - 0.6;
	if (!props.design.isSliding) {
		for (const bar of geom.bars) {
			const dSel = sl === bar.id;
			if (bar.dir === "v") {
				const xC = mx(bar.x);
				const yBot = my(bar.y === 0 ? bFace : bar.y + bf / 2);
				const yTop = my(
					Math.abs(bar.y + bar.length - H) < 0.1 ? H - ff : bar.y + bar.length - bf / 2
				);
				addBox(xC - bf / 2, yBot, -dHalf, xC + bf / 2, yTop, dHalf, { sel: dSel });
				const mp = proj([xC, (yBot + yTop) / 2, camFacingInside ? dHalf + 3 : -dHalf - 3]);
				labels.push({ x: mp[0], y: mp[1], t: bar.id, bg: "#fff", fg: "#111", st: "#222" });
			} else {
				const yC = my(bar.y);
				const x0 = mx(bar.x === 0 ? ff : bar.x + bf / 2);
				const x1 = mx(
					Math.abs(bar.x + bar.length - W) < 0.1 ? W - ff : bar.x + bar.length - bf / 2
				);
				addBox(x0, yC - bf / 2, -dHalf, x1, yC + bf / 2, dHalf, { sel: dSel });
				const mp = proj([(x0 + x1) / 2, yC, camFacingInside ? dHalf + 3 : -dHalf - 3]);
				labels.push({ x: mp[0], y: mp[1], t: bar.id, bg: "#fff", fg: "#111", st: "#222" });
			}
		}
	}

	// 3. DISJOINT-Z GLAZING HELPER (Interior 45° Bead + Centered Glass + Exterior 45° Gasket)
	const drawGlazing3D = (
		gx0: number,
		gy0: number,
		gx1: number,
		gy1: number,
		zOuter: number,
		zInner: number,
		node: Design["root"] & { type: "fixed" | "sash" | "louver" },
		isGlSel: boolean,
		xf: Xform | null
	) => {
		const hasBead = node.bead !== false;
		const beadW = hasBead ? 11 : 6;
		const gaskW = 7;
		const availZ = Math.max(10, zInner - zOuter);
		const gtDraw = Math.max(4, Math.min(6, availZ * 0.42));
		const gHalf = gtDraw / 2;
		const zBead0 = gHalf + 0.6;
		const zBead1 = zInner;
		const zGask0 = zOuter;
		const zGask1 = -gHalf - 0.6;

		const beadCol = isGlSel ? hi : hasBead ? inCol : "#252a32";
		const gaskCol = isGlSel ? hi : "#252a32";
		if (zBead1 - zBead0 > 0.5) {
			addMiterRing(gx0, gy0, gx1, gy1, beadW, zBead0, zBead1, {
				hasBottom: true,
				inCol: beadCol,
				outCol: beadCol,
				sideCol: beadCol,
				xf,
			});
		}
		if (zGask1 - zGask0 > 0.5) {
			addMiterRing(gx0, gy0, gx1, gy1, gaskW, zGask0, zGask1, {
				hasBottom: true,
				inCol: gaskCol,
				outCol: gaskCol,
				sideCol: gaskCol,
				xf,
			});
		}

		const px0 = gx0 + beadW - 1;
		const px1 = gx1 - beadW + 1;
		const py0 = gy0 + beadW - 1;
		const py1 = gy1 - beadW + 1;
		const isSteel =
			Boolean(node.fan && node.type !== "louver") ||
			node.itemType === "Panel" ||
			node.addon === "Panel";
		const gn = (node.glass || "").toUpperCase();
		let gCol = "#a8dcf0";
		let gAlpha = 0.34;
		if (isSteel) {
			gCol = "#cbd5e1";
			gAlpha = 1.0;
		} else if (gn.includes("TINT") || gn.includes("GREY")) {
			gCol = "#64748b";
			gAlpha = 0.46;
		} else if (gn.includes("FROST")) {
			gCol = "#dbeafe";
			gAlpha = 0.66;
		}
		addBox(px0, py0, -gHalf, px1, py1, gHalf, {
			inCol: gCol,
			outCol: gCol,
			sideCol: gCol,
			alpha: gAlpha,
			noEdges: !isSteel,
			xf,
		});

		const cx0 = gx0 + beadW,
			cx1 = gx1 - beadW,
			cy0 = gy0 + beadW,
			cy1 = gy1 - beadW;
		const gw = cx1 - cx0,
			gh = cy1 - cy0;
		if (node.type === "louver") {
			const steps = Math.max(4, node.blades || 8);
			for (let i = 1; i < steps; i++) {
				const ly = cy0 + (gh * i) / steps;
				addBox(cx0 + 3, ly - 5, zOuter + 2, cx1 - 3, ly + 5, zInner - 2, {
					inCol: "#64748b",
					outCol: "#475569",
					sideCol: "#475569",
					xf,
				});
			}
		}
		if (node.addon === "AC") {
			addBox(
				cx0 + gw * 0.12,
				cy0 + gh * 0.08,
				zOuter - 12,
				cx1 - gw * 0.12,
				cy0 + gh * 0.42,
				zInner + 14,
				{
					inCol: "#e2e8f0",
					outCol: "#cbd5e1",
					sideCol: "#94a3b8",
					xf,
				}
			);
		}
		if (node.addon === "Railing") {
			const railY = cy0 + gh * 0.42;
			addBox(cx0, railY - 8, zOuter - 16, cx1, railY + 8, zOuter - 4, {
				inCol: "#334155",
				outCol: "#334155",
				sideCol: "#1e293b",
				xf,
			});
			for (let i = 1; i <= 5; i++) {
				const rx = cx0 + (gw * i) / 6;
				addBox(rx - 5, cy0, zOuter - 14, rx + 5, railY, zOuter - 6, {
					inCol: "#475569",
					outCol: "#475569",
					sideCol: "#334155",
					xf,
				});
			}
		}
		if (node.fan) {
			const fcx = (cx0 + cx1) / 2,
				fcy = (cy0 + cy1) / 2,
				r = Math.min(gw, gh) * 0.24;
			addMiterRing(fcx - r, fcy - r, fcx + r, fcy + r, 14, -10, 10, {
				hasBottom: true,
				inCol: "#475569",
				outCol: "#475569",
				sideCol: "#334155",
				xf,
			});
			addBox(fcx - r + 10, fcy - 4, -4, fcx + r - 10, fcy + 4, 4, {
				inCol: "#334155",
				outCol: "#334155",
				xf,
			});
			addBox(fcx - 4, fcy - r + 10, -4, fcx + 4, fcy + r - 10, 4, {
				inCol: "#334155",
				outCol: "#334155",
				xf,
			});
		}
		if (node.grill) {
			const vCnt = Math.max(
				0,
				node.grill.vertical ?? (node.grill as { verticalBars?: number }).verticalBars ?? 2
			);
			const hCnt = Math.max(
				0,
				node.grill.horizontal ??
					(node.grill as { horizontalBars?: number }).horizontalBars ??
					2
			);
			const gp = 14;
			for (let i = 1; i <= vCnt; i++) {
				const vx = cx0 + (gw * i) / (vCnt + 1);
				addBox(vx - gp / 2, cy0, gHalf + 0.6, vx + gp / 2, cy1, gHalf + 6.8, { xf });
			}
			for (let i = 1; i <= hCnt; i++) {
				const hy = cy0 + (gh * i) / (hCnt + 1);
				addBox(cx0, hy - gp / 2, gHalf + 0.6, cx1, hy + gp / 2, gHalf + 6.8, { xf });
			}
		}
		if (node.mesh || node.meshType) {
			addBox(cx0 + 2, cy0 + 2, zInner + 2, cx1 - 2, cy1 - 2, zInner + 5, {
				inCol: "#64748b",
				outCol: "#64748b",
				sideCol: "#64748b",
				alpha: 0.24,
				noEdges: true,
				xf,
			});
		}
	};

	// 4. CELLS (Fixed / Casement Sash / Door Sash + Hardware)
	hitRegions = [];
	lastStageSize = { w: cw, h: ch };
	windowHitPolys = ([-fHalf, fHalf] as const).map((zPlane) =>
		(
			[
				[bxL, byB, zPlane],
				[bxR, byB, zPlane],
				[bxR, byT, zPlane],
				[bxL, byT, zPlane],
			] as Vec3[]
		).map((pt) => {
			const pr = proj(pt);
			return [pr[0], pr[1]] as [number, number];
		})
	);
	let sashCounter = 0;
	geom.cells.forEach((cell, idx) => {
		const n = cell.node;
		const isSlidingCell = n.type === "sash" && Boolean((n as SashNode).isSliding);
		const atLeftEdge = cell.x <= 0.1;
		const atRightEdge = Math.abs(cell.x + cell.w - W) < 0.1;
		const lMm = atLeftEdge ? ff : isSlidingCell ? 0 : bf / 2;
		const rMm = atRightEdge ? ff : isSlidingCell ? 0 : bf / 2;
		const bMm = cell.y === 0 ? bFace : bf / 2;
		const tMm = Math.abs(cell.y + cell.h - H) < 0.1 ? ff : bf / 2;
		const x0 = mx(cell.x + lMm);
		const x1 = mx(cell.x + cell.w - rMm);
		const y0 = my(cell.y + bMm);
		const y1 = my(cell.y + cell.h - tMm);

		const hitPts: [number, number][] = (
			[
				[x0, y0, 0],
				[x1, y0, 0],
				[x1, y1, 0],
				[x0, y1, 0],
			] as Vec3[]
		).map((pt) => {
			const pr = proj(pt);
			return [pr[0], pr[1]];
		});
		hitRegions.push({ path: cell.path, pts: hitPts });

		if (n.type !== "sash") {
			const isGlSel =
				sl === cell.path || sl === `GLASS:${cell.path}` || sl === `BEAD:${cell.path}`;
			drawGlazing3D(x0, y0, x1, y1, -fHalf + 3, fHalf - 3, n, isGlSel, null);
			const cp2 = proj([
				(x0 + x1) / 2,
				y0 + (y1 - y0) * 0.6,
				camFacingInside ? fHalf + 3 : -fHalf - 3,
			]);
			labels.push({
				x: cp2[0],
				y: cp2[1],
				t: String(idx + 1),
				round: true,
				bg: "#fff",
				fg: "#111",
				st: "#111",
			});
			return;
		}

		sashCounter += 1;
		const sId = `S${sashCounter}`;
		const sNode = n as SashNode;
		const sSel = sl === cell.path || sl === `GLASS:${cell.path}` || sl === `BEAD:${cell.path}`;
		const isSlidingSash = Boolean(sNode.isSliding);
		const sfMm = sashFaceForCell(cell.path, sNode);
		const sashInset = isSlidingSash ? 36 : sfMm;
		const interlockHalf = sashInset / 2;
		const sx0 = isSlidingSash ? (atLeftEdge ? x0 - 4 : mx(cell.x) - interlockHalf) : x0 + 2.5;
		const sx1 = isSlidingSash
			? atRightEdge
				? x1 + 4
				: mx(cell.x + cell.w) + interlockHalf
			: x1 - 2.5;
		const sy0 = y0 + 2.5;
		const sy1 = y1 - 2.5;
		const trCount = Math.max(2, sNode.trackCount || props.design.trackCount || 2);
		const trIdx = sNode.trackIdx ?? 0;
		const trackBand = (frameD - 10) / trCount;
		const sashZ0 = isSlidingSash ? -fHalf + 5 + trIdx * trackBand : -fHalf + 2;
		const sashZ1 = isSlidingSash ? sashZ0 + Math.max(14, trackBand - 2) : fHalf - 3;
		const hg = sNode.hinge || "left";
		const isInward = sNode.opening === "in";

		let xf: Xform | null = null;
		if (openFrac > 0) {
			if (isSlidingSash) {
				if (!sNode.slideFixed) {
					const dist =
						(sx1 - sx0) * 0.72 * openFrac * (sNode.slideDir === "left" ? -1 : 1);
					xf = (p) => [p[0] + dist, p[1], p[2]];
				}
			} else {
				const outSign = isInward ? -1 : 1;
				const pivotZ = isInward ? fHalf + 2 : -fHalf - 2;
				if (hg === "left") xf = (p) => rotY(p, sx0, pivotZ, 0.95 * openFrac * outSign);
				else if (hg === "right")
					xf = (p) => rotY(p, sx1, pivotZ, -0.95 * openFrac * outSign);
				else if (hg === "top") xf = (p) => rotX(p, sy1, pivotZ, 0.62 * openFrac * outSign);
				else if (hg === "bottom")
					xf = (p) => rotX(p, sy0, pivotZ, -0.58 * openFrac * outSign);
			}
		}

		addMiterRing(sx0, sy0, sx1, sy1, sashInset, sashZ0, sashZ1, {
			hasBottom: true,
			sel: sSel,
			xf,
		});
		const gx0 = sx0 + sashInset,
			gx1 = sx1 - sashInset,
			gy0 = sy0 + sashInset,
			gy1 = sy1 - sashInset;
		drawGlazing3D(
			gx0,
			gy0,
			gx1,
			gy1,
			sashZ0 + 1.5,
			sashZ1 - 1.5,
			sNode,
			sl === `GLASS:${cell.path}` || sl === `BEAD:${cell.path}`,
			xf
		);

		const lblZ = camFacingInside ? sashZ1 + 4 : sashZ0 - 4;
		const isDoor = sNode.sashConfig === "door";

		// Dashed swing lines (Casement) OR Slide arrow / Fixed + (Sliding)
		if (isSlidingSash) {
			const mY = (gy0 + gy1) / 2;
			const mX = (gx0 + gx1) / 2;
			if (sNode.slideFixed) {
				hudLines.push({
					a: [mX - 45, mY, lblZ],
					b: [mX + 45, mY, lblZ],
					stroke: "#1e293b",
					lw: 1.8,
					xf,
				});
				hudLines.push({
					a: [mX, mY - 45, lblZ],
					b: [mX, mY + 45, lblZ],
					stroke: "#1e293b",
					lw: 1.8,
					xf,
				});
			} else {
				const aX =
					sNode.slideDir === "left"
						? gx0 + (gx1 - gx0) * 0.72
						: gx0 + (gx1 - gx0) * 0.28;
				const bX =
					sNode.slideDir === "left"
						? gx0 + (gx1 - gx0) * 0.28
						: gx0 + (gx1 - gx0) * 0.72;
				hudLines.push({
					a: [aX, mY, lblZ],
					b: [bX, mY, lblZ],
					stroke: "#1e293b",
					lw: 1.8,
					arrow: true,
					xf,
				});
			}
		} else if (hg === "left") {
			hudLines.push({
				a: [gx0, gy1, lblZ],
				b: [gx1, (gy0 + gy1) / 2, lblZ],
				stroke: "#334155",
				lw: 1.2,
				dash: [5, 4],
				xf,
			});
			hudLines.push({
				a: [gx1, (gy0 + gy1) / 2, lblZ],
				b: [gx0, gy0, lblZ],
				stroke: "#334155",
				lw: 1.2,
				dash: [5, 4],
				xf,
			});
		} else if (hg === "right") {
			hudLines.push({
				a: [gx1, gy1, lblZ],
				b: [gx0, (gy0 + gy1) / 2, lblZ],
				stroke: "#334155",
				lw: 1.2,
				dash: [5, 4],
				xf,
			});
			hudLines.push({
				a: [gx0, (gy0 + gy1) / 2, lblZ],
				b: [gx1, gy0, lblZ],
				stroke: "#334155",
				lw: 1.2,
				dash: [5, 4],
				xf,
			});
		} else if (hg === "top") {
			hudLines.push({
				a: [gx0, gy0, lblZ],
				b: [(gx0 + gx1) / 2, gy1, lblZ],
				stroke: "#334155",
				lw: 1.2,
				dash: [5, 4],
				xf,
			});
			hudLines.push({
				a: [(gx0 + gx1) / 2, gy1, lblZ],
				b: [gx1, gy0, lblZ],
				stroke: "#334155",
				lw: 1.2,
				dash: [5, 4],
				xf,
			});
		} else if (hg === "bottom") {
			hudLines.push({
				a: [gx0, gy1, lblZ],
				b: [(gx0 + gx1) / 2, gy0, lblZ],
				stroke: "#334155",
				lw: 1.2,
				dash: [5, 4],
				xf,
			});
			hudLines.push({
				a: [(gx0 + gx1) / 2, gy0, lblZ],
				b: [gx1, gy1, lblZ],
				stroke: "#334155",
				lw: 1.2,
				dash: [5, 4],
				xf,
			});
		}

		// 3-Knuckle Cylindrical Hinges on exterior (-Z) seam (Casement only)
		if (
			!isSlidingSash &&
			(isDoor || sNode.hingeStay === "Hinges" || sNode.hinge_type === "butt")
		) {
			const hc = isDoor
				? cell.h >= 2100
					? 5
					: cell.h >= 1400
					? 4
					: 3
				: cell.h >= 1600
				? 4
				: cell.h >= 1100
				? 3
				: 2;
			const hZ = -fHalf - 5.5;
			if (hg === "left" || hg === "right") {
				const hx = hg === "left" ? sx0 - 1.2 : sx1 + 1.2;
				const wingDir = hg === "left" ? 1 : -1;
				hingePositions(sy0, sy1, hc).forEach((hy) => {
					addCylBarrel(hx, hy - 22, hZ, 7.5, 20, "y", { inCol: "#1e242c", xf });
					addCylBarrel(hx, hy, hZ, 7.5, 22, "y", { inCol: "#2d3540", xf });
					addCylBarrel(hx, hy + 22, hZ, 7.5, 20, "y", { inCol: "#1e242c", xf });
					addBox(
						Math.min(hx, hx + wingDir * 22),
						hy - 32,
						sashZ0 - 3,
						Math.max(hx, hx + wingDir * 22),
						hy + 32,
						sashZ0,
						{ inCol: "#1e242c", outCol: "#1e242c", sideCol: "#111827", xf }
					);
				});
			} else {
				const hy = sy1 + 1.2;
				hingePositions(sx0, sx1, hc).forEach((hx) => {
					addCylBarrel(hx, hy, hZ, 6.5, 48, "x", { inCol: "#1e242c", xf });
				});
			}
		}

		// Handles (Sliding flush pull on lock stile, Window L-handle, Door Active Leaf lever + cylinder)
		const skipApproxHandle =
			sNode.handle === "none" ||
			(isDoor && sNode.activeLeaf === false) ||
			(isSlidingSash && sNode.slideFixed);
		if (!skipApproxHandle) {
			const slideDir = sNode.slideDir || "right";
			const hx = isSlidingSash
				? slideDir === "right"
					? sx0 + sashInset / 2
					: sx1 - sashInset / 2
				: hg === "left"
				? sx1 - sfMm / 2
				: hg === "right"
				? sx0 + sfMm / 2
				: (sx0 + sx1) / 2;
			const hy = !isSlidingSash && hg === "top" ? sy0 + sfMm / 2 : (sy0 + sy1) / 2;
			if (isSlidingSash) {
				addBox(hx - 7, hy - 54, sashZ1, hx + 7, hy + 54, sashZ1 + 6, {
					inCol: "#1e293b",
					outCol: "#1e293b",
					sideCol: "#0f172a",
					xf,
				});
				addBox(hx - 4, hy - 32, sashZ1 + 6, hx + 4, hy + 32, sashZ1 + 9, {
					inCol: "#64748b",
					outCol: "#64748b",
					sideCol: "#334155",
					xf,
				});
			} else if (isDoor) {
				const dirH = hg === "right" ? 1 : -1;
				// Inside lever + escutcheon + cylinder
				addBox(hx - 10, hy - 58, sashZ1, hx + 10, hy + 22, sashZ1 + 7, {
					inCol: "#cbd5e1",
					outCol: "#94a3b8",
					sideCol: "#64748b",
					xf,
				});
				addBox(
					Math.min(hx, hx + dirH * 88),
					hy - 7,
					sashZ1 + 7,
					Math.max(hx, hx + dirH * 88),
					hy + 11,
					sashZ1 + 22,
					{ inCol: "#94a3b8", outCol: "#94a3b8", sideCol: "#64748b", xf }
				);
				addCylBarrel(hx, hy - 36, sashZ1 + 9, 9, 5, "z", { inCol: "#e2e8f0", xf });
				// Outside lever + escutcheon + cylinder
				addBox(hx - 10, hy - 58, sashZ0 - 7, hx + 10, hy + 22, sashZ0, {
					inCol: "#cbd5e1",
					outCol: "#cbd5e1",
					sideCol: "#64748b",
					xf,
				});
				addBox(
					Math.min(hx, hx + dirH * 88),
					hy - 7,
					sashZ0 - 22,
					Math.max(hx, hx + dirH * 88),
					hy + 11,
					sashZ0 - 7,
					{ inCol: "#94a3b8", outCol: "#94a3b8", sideCol: "#64748b", xf }
				);
				addCylBarrel(hx, hy - 36, sashZ0 - 9, 9, 5, "z", { inCol: "#e2e8f0", xf });
			} else {
				addBox(hx - 8, hy - 36, sashZ1, hx + 8, hy + 36, sashZ1 + 8, {
					inCol: "#334155",
					outCol: "#334155",
					sideCol: "#1e293b",
					xf,
				});
				addBox(hx - 5, hy - 80, sashZ1 + 8, hx + 5, hy + 10, sashZ1 + 22, {
					inCol: "#475569",
					outCol: "#475569",
					sideCol: "#334155",
					xf,
				});
			}
		}

		const ghh = sNode.ghh ?? (isDoor ? 1050 : 732);
		const pGhh = proj(
			xf
				? xf([(sx0 + sx1) / 2, sy0 + (sy1 - sy0) * 0.44, lblZ])
				: [(sx0 + sx1) / 2, sy0 + (sy1 - sy0) * 0.44, lblZ]
		);
		const pOut = proj(
			xf
				? xf([(sx0 + sx1) / 2, sy0 + (sy1 - sy0) * 0.32, lblZ])
				: [(sx0 + sx1) / 2, sy0 + (sy1 - sy0) * 0.32, lblZ]
		);
		if (!isSlidingSash && (!isDoor || sNode.activeLeaf !== false)) {
			labels.push({
				x: pGhh[0],
				y: pGhh[1],
				t: `GHH = ${ghh}`,
				bg: "#fff",
				fg: "#222",
				st: "#222",
			});
		}
		if (!isSlidingSash) {
			const dirLabel = isInward
				? camFacingInside
					? "IN"
					: "OUT"
				: camFacingInside
				? "OUT"
				: "IN";
			labels.push({
				x: pOut[0],
				y: pOut[1],
				t: dirLabel,
				bg: "#e4f4fa",
				fg: "#3d8bb0",
				st: "#5aa6c9",
			});
		}

		const pSid = proj(
			xf
				? xf([(sx0 + sx1) / 2, sy1 - sashInset * 0.5, lblZ])
				: [(sx0 + sx1) / 2, sy1 - sashInset * 0.5, lblZ]
		);
		const pNum = proj(
			xf
				? xf([(sx0 + sx1) / 2, sy0 + (sy1 - sy0) * 0.6, lblZ])
				: [(sx0 + sx1) / 2, sy0 + (sy1 - sy0) * 0.6, lblZ]
		);
		labels.push({ x: pSid[0], y: pSid[1], t: sId, bg: "#fff", fg: "#111", st: "#222" });
		labels.push({
			x: pNum[0],
			y: pNum[1],
			t: String(idx + 1),
			round: true,
			bg: "#fff",
			fg: "#111",
			st: "#111",
		});
	});

	// 5. F1 BADGE & 3D PROJECTED DIMENSIONS
	const f1p = proj([
		bxR - ff - 25,
		byB + Math.max(25, bFace + 18),
		camFacingInside ? fHalf + 4 : -fHalf - 4,
	]);
	labels.push({ x: f1p[0], y: f1p[1], t: "F1", bg: "#fff", fg: "#111", st: "#222" });
	hudLines.push({
		a: [bxL - 120, byB, 0],
		b: [bxL - 120, byT, 0],
		stroke: "#777",
		lw: 1.2,
		bothArrows: true,
	});
	hudLines.push({
		a: [bxL, byB - 120, 0],
		b: [bxR, byB - 120, 0],
		stroke: "#777",
		lw: 1.2,
		bothArrows: true,
	});
	const hMid = proj([bxL - 120, (byB + byT) / 2, 0]);
	const wMid = proj([(bxL + bxR) / 2, byB - 120, 0]);
	labels.push({ x: hMid[0], y: hMid[1], t: String(H), bg: "#fff", fg: "#222", st: "#dfe4ec" });
	labels.push({ x: wMid[0], y: wMid[1], t: String(W), bg: "#fff", fg: "#222", st: "#dfe4ec" });
	if (props.design.root.type === "split" && props.design.root.dir === "v") {
		const bounds = [0, ...props.design.root.at, W];
		for (let i = 0; i < bounds.length - 1; i++) {
			const c0 = bounds[i],
				c1 = bounds[i + 1];
			hudLines.push({
				a: [mx(c0), byB - 60, 0],
				b: [mx(c1), byB - 60, 0],
				stroke: "#777",
				lw: 1.1,
				bothArrows: true,
			});
			const pm = proj([mx((c0 + c1) / 2), byB - 60, 0]);
			labels.push({
				x: pm[0],
				y: pm[1],
				t: String(Math.round(c1 - c0)),
				bg: "#fff",
				fg: "#333",
				st: "#dfe4ec",
			});
		}
	}

	// Sort translucent panes strictly back-to-front by viewZ
	transGroups.sort((a, b) => a.z - b.z);
	const trPos: number[] = [];
	const trNorm: number[] = [];
	const trCol: number[] = [];
	for (const g of transGroups) {
		for (let i = 0; i < g.p.length; i++) trPos.push(g.p[i]);
		for (let i = 0; i < g.n.length; i++) trNorm.push(g.n[i]);
		for (let i = 0; i < g.c.length; i++) trCol.push(g.c[i]);
	}

	// 6. HARDWARE Z-BUFFERED WEBGL RENDER PASS
	const dpr = (typeof window !== "undefined" && window.devicePixelRatio) || 1;
	const ctxGL = initWebGL(glCanvas);
	if (!ctxGL) {
		webGLSupported.value = false;
	} else {
		webGLSupported.value = true;
		const { gl, solidProg, lineProg, sLoc, lLoc, bPos, bNorm, bCol, bLPos, bLCol } = ctxGL;
		glCanvas.width = Math.round(cw * dpr);
		glCanvas.height = Math.round(ch * dpr);
		gl.viewport(0, 0, glCanvas.width, glCanvas.height);
		gl.clearColor(0, 0, 0, 0);
		gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
		gl.enable(gl.DEPTH_TEST);
		gl.depthFunc(gl.LEQUAL);

		const drawSolidBuf = (pArr: number[], nArr: number[], cArr: number[]) => {
			if (!pArr.length) return;
			gl.useProgram(solidProg);
			gl.uniformMatrix4fv(sLoc.mvp, false, mvp);
			gl.uniformMatrix3fv(sLoc.nmat, false, nmat);
			gl.bindBuffer(gl.ARRAY_BUFFER, bPos);
			gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(pArr), gl.DYNAMIC_DRAW);
			gl.enableVertexAttribArray(sLoc.pos);
			gl.vertexAttribPointer(sLoc.pos, 3, gl.FLOAT, false, 0, 0);
			gl.bindBuffer(gl.ARRAY_BUFFER, bNorm);
			gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(nArr), gl.DYNAMIC_DRAW);
			gl.enableVertexAttribArray(sLoc.norm);
			gl.vertexAttribPointer(sLoc.norm, 3, gl.FLOAT, false, 0, 0);
			gl.bindBuffer(gl.ARRAY_BUFFER, bCol);
			gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(cArr), gl.DYNAMIC_DRAW);
			gl.enableVertexAttribArray(sLoc.col);
			gl.vertexAttribPointer(sLoc.col, 4, gl.FLOAT, false, 0, 0);
			gl.drawArrays(gl.TRIANGLES, 0, pArr.length / 3);
		};

		// Pass 1: Opaque geometry
		gl.disable(gl.BLEND);
		gl.depthMask(true);
		gl.enable(gl.POLYGON_OFFSET_FILL);
		gl.polygonOffset(1.5, 2.0);
		drawSolidBuf(opPos, opNorm, opCol);

		// Pass 2: Crisp CAD edge lines (view-space +1.0mm bias)
		gl.disable(gl.POLYGON_OFFSET_FILL);
		gl.enable(gl.BLEND);
		gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
		if (lnPos.length) {
			gl.useProgram(lineProg);
			gl.uniformMatrix4fv(lLoc.mv, false, mv);
			gl.uniformMatrix4fv(lLoc.p, false, persp);
			gl.bindBuffer(gl.ARRAY_BUFFER, bLPos);
			gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(lnPos), gl.DYNAMIC_DRAW);
			gl.enableVertexAttribArray(lLoc.pos);
			gl.vertexAttribPointer(lLoc.pos, 3, gl.FLOAT, false, 0, 0);
			gl.bindBuffer(gl.ARRAY_BUFFER, bLCol);
			gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(lnCol), gl.DYNAMIC_DRAW);
			gl.enableVertexAttribArray(lLoc.col);
			gl.vertexAttribPointer(lLoc.col, 4, gl.FLOAT, false, 0, 0);
			gl.drawArrays(gl.LINES, 0, lnPos.length / 3);
		}

		// Pass 3: Translucent glass & mesh
		gl.depthMask(false);
		drawSolidBuf(trPos, trNorm, trCol);
		gl.depthMask(true);
	}

	// 7. CRISP 2D CAD HUD OVERLAY (Dimensions, Swing Lines, Badges)
	if (hudCanvas && typeof hudCanvas.getContext === "function") {
		const hctx = hudCanvas.getContext("2d");
		if (hctx) {
			hudCanvas.width = Math.round(cw * dpr);
			hudCanvas.height = Math.round(ch * dpr);
			hctx.setTransform(dpr, 0, 0, dpr, 0, 0);
			hctx.clearRect(0, 0, cw, ch);
			const drawArrow = (x0: number, y0: number, x1: number, y1: number, col: string) => {
				const ang = Math.atan2(y1 - y0, x1 - x0);
				const sz = 7;
				hctx.fillStyle = col;
				hctx.beginPath();
				hctx.moveTo(x1, y1);
				hctx.lineTo(x1 - sz * Math.cos(ang - 0.45), y1 - sz * Math.sin(ang - 0.45));
				hctx.lineTo(x1 - sz * Math.cos(ang + 0.45), y1 - sz * Math.sin(ang + 0.45));
				hctx.closePath();
				hctx.fill();
			};
			for (const hl of hudLines) {
				const pa = proj(hl.xf ? hl.xf(hl.a) : hl.a);
				const pb = proj(hl.xf ? hl.xf(hl.b) : hl.b);
				hctx.save();
				if (hl.dash) hctx.setLineDash(hl.dash);
				hctx.strokeStyle = hl.stroke;
				hctx.lineWidth = hl.lw || 1.2;
				hctx.beginPath();
				hctx.moveTo(pa[0], pa[1]);
				hctx.lineTo(pb[0], pb[1]);
				hctx.stroke();
				hctx.restore();
				if (hl.arrow) drawArrow(pa[0], pa[1], pb[0], pb[1], hl.stroke);
				if (hl.bothArrows) {
					drawArrow(pa[0], pa[1], pb[0], pb[1], hl.stroke);
					drawArrow(pb[0], pb[1], pa[0], pa[1], hl.stroke);
				}
			}
			hctx.font = '600 12px "Segoe UI", Arial, sans-serif';
			hctx.textAlign = "center";
			hctx.textBaseline = "middle";
			for (const lb of labels) {
				if (lb.round) {
					hctx.beginPath();
					hctx.arc(lb.x, lb.y, 12, 0, Math.PI * 2);
					hctx.fillStyle = lb.bg;
					hctx.fill();
					hctx.lineWidth = 1.2;
					hctx.strokeStyle = lb.st;
					hctx.stroke();
				} else {
					const tw = Math.max(26, hctx.measureText(lb.t).width + 14);
					const th2 = 22;
					hctx.fillStyle = lb.bg;
					hctx.strokeStyle = lb.st;
					hctx.lineWidth = 1.1;
					hctx.fillRect(lb.x - tw / 2, lb.y - th2 / 2, tw, th2);
					hctx.strokeRect(lb.x - tw / 2, lb.y - th2 / 2, tw, th2);
				}
				hctx.fillStyle = lb.fg;
				hctx.fillText(lb.t, lb.x, lb.y + 0.5);
			}
		}
		if (dragOverCell.value) {
			const hit = hitRegions.find((r) => r.path === dragOverCell.value);
			if (hit && hit.pts.length >= 3) {
				hctx.save();
				hctx.beginPath();
				hit.pts.forEach(([x, y], idx) =>
					idx === 0 ? hctx.moveTo(x, y) : hctx.lineTo(x, y)
				);
				hctx.closePath();
				hctx.fillStyle = "rgba(26, 111, 212, 0.16)";
				hctx.fill();
				hctx.strokeStyle = "#1a6fd4";
				hctx.lineWidth = 2.2;
				hctx.setLineDash([6, 4]);
				hctx.stroke();
				hctx.restore();
			}
		}
	}
}

const dragOverCell = ref<string | null>(null);
const dragOverEmpty = ref(false);
const dragOverCellLabel = computed(() => {
	if (!dragOverCell.value) return "";
	const cells = layoutGeom(props.design).cells;
	const idx = cells.findIndex((c) => c.path === dragOverCell.value);
	return idx >= 0 ? `G${idx + 1}` : dragOverCell.value;
});

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

function polyCenter(pts: [number, number][]): [number, number] {
	if (!pts.length) return [0, 0];
	let sx = 0;
	let sy = 0;
	for (const [x, y] of pts) {
		sx += x;
		sy += y;
	}
	return [sx / pts.length, sy / pts.length];
}

function hitDropTarget(
	clientX: number,
	clientY: number
): { cellPath: string; emptySpace: boolean } {
	const rect = (cv3d.value ?? stageEl.value)?.getBoundingClientRect();
	const fallbackCell = hitRegions[0]?.path || layoutGeom(props.design).cells[0]?.path || "F1";
	if (!rect) return { cellPath: fallbackCell, emptySpace: false };
	const scaleX = rect.width > 0 ? lastStageSize.w / rect.width : 1;
	const scaleY = rect.height > 0 ? lastStageSize.h / rect.height : 1;
	const hx = (clientX - rect.left) * scaleX;
	const hy = (clientY - rect.top) * scaleY;
	for (let i = hitRegions.length - 1; i >= 0; i--) {
		if (ptInPoly(hx, hy, hitRegions[i].pts)) {
			return { cellPath: hitRegions[i].path, emptySpace: false };
		}
	}
	if (windowHitPolys.some((poly) => ptInPoly(hx, hy, poly))) {
		let best = fallbackCell;
		let bestDist = Infinity;
		for (const reg of hitRegions) {
			const [cx, cy] = polyCenter(reg.pts);
			const d = Math.hypot(hx - cx, hy - cy);
			if (d < bestDist) {
				bestDist = d;
				best = reg.path;
			}
		}
		return { cellPath: best, emptySpace: false };
	}
	if (hitRegions.length > 0 || windowHitPolys.length > 0) {
		return { cellPath: "", emptySpace: true };
	}
	return { cellPath: fallbackCell, emptySpace: false };
}

function onDragOver(e: DragEvent) {
	e.preventDefault();
	if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
	const target = hitDropTarget(e.clientX, e.clientY);
	const nextCell = target.emptySpace ? null : target.cellPath;
	const nextEmpty = target.emptySpace && peekWindowDragKind() !== "info";
	const changed = dragOverCell.value !== nextCell || dragOverEmpty.value !== nextEmpty;
	dragOverCell.value = nextCell;
	dragOverEmpty.value = nextEmpty;
	if (changed) draw3D();
}

function onDragLeave(e: DragEvent) {
	const nextTarget = e.relatedTarget as Node | null;
	if (nextTarget && stageEl.value?.contains(nextTarget)) return;
	if (dragOverCell.value !== null || dragOverEmpty.value) {
		dragOverCell.value = null;
		dragOverEmpty.value = false;
		draw3D();
	}
}

function onDrop(e: DragEvent) {
	e.preventDefault();
	e.stopPropagation();
	const target = hitDropTarget(e.clientX, e.clientY);
	dragOverCell.value = null;
	dragOverEmpty.value = false;
	draw3D();
	const payload = parseDragPayload(e);
	(window as unknown as { __fenDragPayload?: string }).__fenDragPayload = undefined;
	if (payload)
		emit("drop-tool", {
			...payload,
			cellPath: target.cellPath,
			replaceDesign: target.emptySpace,
		});
}

function ptInPoly(px: number, py: number, pts: [number, number][]): boolean {
	let inside = false;
	for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
		const [xi, yi] = pts[i];
		const [xj, yj] = pts[j];
		if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi || 1e-6) + xi) {
			inside = !inside;
		}
	}
	return inside;
}

function onPointerDown(e: PointerEvent) {
	cancelCamAnim();
	const isPan =
		e.button === 1 ||
		e.button === 2 ||
		(e.button === 0 && (e.shiftKey || e.ctrlKey || e.metaKey));
	drag = {
		mode: isPan ? "pan" : "orbit",
		x: e.clientX,
		y: e.clientY,
		yaw,
		pitch,
		panX,
		panY,
		moved: false,
	};
	isDragging.value = true;
}

function onPointerMove(e: PointerEvent) {
	if (!drag) return;
	const dx = e.clientX - drag.x;
	const dy = e.clientY - drag.y;
	if (!drag.moved && Math.hypot(dx, dy) < 4) return;
	drag.moved = true;
	if (drag.mode === "pan") {
		const cw = stageEl.value?.clientWidth || 800;
		const ch = stageEl.value?.clientHeight || 600;
		const { width: W, height: H } = props.design;
		const fov = (34 * Math.PI) / 180;
		const aspect = Math.max(0.2, cw / Math.max(1, ch));
		const tY = Math.tan(fov / 2);
		const tX = tY * aspect;
		const camDist = Math.max((H + 340) / (2 * tY), (W + 360) / (2 * tX)) / zoom;
		const mmPerPx = (2 * camDist * tY) / Math.max(1, ch);
		panX = drag.panX + dx * mmPerPx;
		panY = drag.panY - dy * mmPerPx;
		draw3D();
		return;
	}
	yaw = drag.yaw - dx * 0.008;
	pitch = Math.max(-1.05, Math.min(1.05, drag.pitch + dy * 0.006));
	const nextSide: "inside" | "outside" = Math.cos(yaw) < 0 ? "outside" : "inside";
	if (nextSide !== props.side) emit("update:side", nextSide);
	draw3D();
}

function onPointerUp(e: PointerEvent) {
	if (!drag) return;
	const d = drag;
	drag = null;
	isDragging.value = false;
	if (!d.moved && cv3d.value) {
		const r = cv3d.value.getBoundingClientRect();
		const hx = e.clientX - r.left;
		const hy = e.clientY - r.top;
		let hit: HitRegion | null = null;
		for (let i = hitRegions.length - 1; i >= 0; i--) {
			if (ptInPoly(hx, hy, hitRegions[i].pts)) {
				hit = hitRegions[i];
				break;
			}
		}
		emit("select", hit ? hit.path : "FRAME");
	}
}

function onWheel(e: WheelEvent) {
	e.preventDefault();
	cancelCamAnim();
	const f = e.deltaY < 0 ? 1.1 : 0.91;
	zoom = Math.max(0.55, Math.min(2.2, zoom * f));
	draw3D();
}

watch(
	() => props.side,
	(nextSide) => {
		if (skipNextSideWatch) {
			skipNextSideWatch = false;
			return;
		}
		animateCam(nextSide === "outside" ? Math.PI : 0, 0, zoom, 380);
	}
);

watch(
	() => props.sashesOpen,
	(open) => {
		openTarget = open ? 1 : 0;
		if (typeof requestAnimationFrame !== "function") {
			openFrac = openTarget;
			draw3D();
			return;
		}
		if (openRaf) cancelAnimationFrame(openRaf);
		const step = () => {
			const diff = openTarget - openFrac;
			if (Math.abs(diff) < 0.012) {
				openFrac = openTarget;
				openRaf = 0;
				draw3D();
				return;
			}
			openFrac += diff * 0.18;
			draw3D();
			openRaf = requestAnimationFrame(step);
		};
		openRaf = requestAnimationFrame(step);
	}
);

watch(
	() => [
		props.design,
		props.selectedPath,
		props.finishColor,
		props.outsideFinishColor,
		props.profileWidths,
		props.roleDefaults,
	],
	() => draw3D(),
	{ deep: true }
);

onMounted(() => {
	window.addEventListener("pointermove", onPointerMove);
	window.addEventListener("pointerup", onPointerUp);
	if (stageEl.value && typeof ResizeObserver !== "undefined") {
		resizeObserver = new ResizeObserver(() => draw3D());
		resizeObserver.observe(stageEl.value);
	}
	draw3D();
});

onUnmounted(() => {
	cancelCamAnim();
	if (openRaf) cancelAnimationFrame(openRaf);
	resizeObserver?.disconnect();
	window.removeEventListener("pointermove", onPointerMove);
	window.removeEventListener("pointerup", onPointerUp);
	glCtx = null;
});
</script>

<template>
	<div
		ref="stageEl"
		data-testid="approx-3d-view"
		class="relative h-full w-full overflow-hidden bg-[#f8fafc] select-none"
		@dragover="onDragOver"
		@dragleave="onDragLeave"
		@drop="onDrop"
	>
		<canvas
			ref="cv3d"
			class="absolute inset-0 block h-full w-full"
			:class="isDragging ? 'cursor-grabbing' : 'cursor-grab'"
			@pointerdown="onPointerDown"
			@wheel="onWheel"
			@contextmenu.prevent
		/>
		<canvas ref="cv3dHud" class="pointer-events-none absolute inset-0 block h-full w-full" />
		<div
			v-if="dragOverEmpty"
			class="pointer-events-none absolute inset-3 z-20 rounded-lg border-2 border-dashed border-[#1a6fd4]/55 bg-[#1a6fd4]/[0.03]"
		/>
		<div
			v-if="dragOverEmpty || dragOverCell"
			data-testid="approx-3d-drop-badge"
			class="pointer-events-none absolute top-4 left-1/2 z-30 -translate-x-1/2 rounded-full border border-[#1a6fd4]/40 bg-[#e6effb]/95 px-3.5 py-1 text-xs font-semibold text-[#1a6fd4] shadow-sm backdrop-blur-sm"
		>
			{{
				dragOverEmpty
					? "Drop in empty space to replace design"
					: `Drop onto cell ${dragOverCellLabel}`
			}}
		</div>
		<div
			v-if="!webGLSupported"
			class="absolute inset-0 flex items-center justify-center text-xs text-gray-500"
		>
			3D preview requires WebGL.
		</div>
	</div>
</template>
