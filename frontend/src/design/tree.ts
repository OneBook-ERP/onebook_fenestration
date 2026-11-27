import type { Design, DesignNode, LeafNode, SplitDir, SplitNode } from './types'

export const MIN_CELL = 100
const MAX_DEPTH = 32
const LEAF_TYPES = ['sash', 'fixed', 'louver']

// JSON clone, not structuredClone: store state is a Vue reactive proxy, which structuredClone rejects.
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v))

const round1 = (n: number) => Math.round(n * 10) / 10
const ceil1 = (n: number) => Math.ceil(Math.round(n * 1000) / 100) / 10
const floor1 = (n: number) => Math.floor(Math.round(n * 1000) / 100) / 10

export function newDesign(width: number, height: number, root?: DesignNode): Design {
	return { width, height, root: root ?? { type: 'fixed', glass: '6CTG', bead: true } }
}

function indices(path: string): number[] {
	const parts = path.split('.')
	if (parts[0] !== 'F1' || parts.slice(1).some((p) => !/^\d+$/.test(p))) throw new Error(`no node at ${path}`)
	return parts.slice(1).map(Number)
}

function walkTo(root: DesignNode, path: string): DesignNode {
	let node = root
	for (const i of indices(path)) {
		if (node.type !== 'split' || !node.children[i]) throw new Error(`no node at ${path}`)
		node = node.children[i]
	}
	return node
}

export function getNode(design: Design, path: string): DesignNode {
	return walkTo(design.root, path)
}

/** Clone the design and hand the node at `path` to `edit`; its return value replaces that node. */
function replaceAt(design: Design, path: string, edit: (node: DesignNode) => DesignNode): Design {
	const next = clone(design)
	const idx = indices(path)
	if (idx.length === 0) {
		next.root = edit(next.root)
		return next
	}
	const parent = walkTo(next.root, path.slice(0, path.lastIndexOf('.'))) as SplitNode
	const last = idx[idx.length - 1]
	if (!parent.children[last]) throw new Error(`no node at ${path}`)
	parent.children[last] = edit(parent.children[last])
	return next
}

/** Size of the cell at `path`, found by walking down from the design size. */
function cellSize(design: Design, path: string): { w: number; h: number } {
	let w = design.width
	let h = design.height
	let node = design.root
	for (const i of indices(path)) {
		if (node.type !== 'split') throw new Error(`no node at ${path}`)
		const bounds = [0, ...node.at, node.dir === 'v' ? w : h]
		const size = bounds[i + 1] - bounds[i]
		if (node.dir === 'v') w = size
		else h = size
		node = node.children[i]
	}
	return { w, h }
}

export function splitCell(design: Design, path: string, dir: SplitDir, count = 2): Design {
	if (!Number.isInteger(count) || count < 2) throw new Error('count must be an integer >= 2')
	const target = getNode(design, path)
	if (target.type === 'split') throw new Error(`not a leaf: ${path}`)
	const { w, h } = cellSize(design, path)
	const span = dir === 'v' ? w : h
	const at = Array.from({ length: count - 1 }, (_, i) => round1((span * (i + 1)) / count))
	return replaceAt(design, path, (leaf) => ({
		type: 'split',
		dir,
		at,
		children: Array.from({ length: count }, () => clone(leaf)),
	}))
}

/** Move bar `index` of the split at `path`, keeping both neighbours (and their nested splits) valid. */
export function moveSplit(design: Design, path: string, index: number, pos: number): Design {
	if (!Number.isFinite(pos)) return design
	const node = getNode(design, path)
	if (node.type !== 'split' || index < 0 || index >= node.at.length) throw new Error(`no split bar ${index} at ${path}`)
	const { w, h } = cellSize(design, path)
	const v = node.dir === 'v'
	const bounds = [0, ...node.at, v ? w : h]
	const [before, after] = [node.children[index], node.children[index + 1]]
	// Round inward to the 0.1 mm grid so no cell ends up under its minimum.
	const lo = ceil1(bounds[index] + minSpan(before, node.dir))
	const hi = floor1(bounds[index + 2] - minSpan(after, node.dir))
	if (lo > hi) return design
	const bar = round1(Math.min(Math.max(pos, lo), hi))
	return replaceAt(design, path, (n) => {
		const split = n as SplitNode
		const resize = (child: DesignNode, oldSize: number, size: number) =>
			rescale(child, v ? oldSize : w, v ? h : oldSize, v ? size : w, v ? h : size)
		resize(split.children[index], bounds[index + 1] - bounds[index], bar - bounds[index])
		resize(split.children[index + 1], bounds[index + 2] - bounds[index + 1], bounds[index + 2] - bar)
		split.at[index] = bar
		return split
	})
}

/** Smallest span along `dir` that keeps every cell under `node` at least MIN_CELL. */
function minSpan(node: DesignNode, dir: SplitDir): number {
	if (node.type !== 'split') return MIN_CELL
	const spans = node.children.map((c) => minSpan(c, dir))
	return node.dir === dir ? spans.reduce((a, b) => a + b, 0) : Math.max(...spans)
}

export function removeSplit(design: Design, path: string): Design {
	const node = getNode(design, path)
	if (node.type !== 'split') throw new Error(`not a split: ${path}`)
	return replaceAt(design, path, (n) => (n as SplitNode).children[0])
}

export function setLeaf(design: Design, path: string, leaf: LeafNode): Design {
	if (getNode(design, path).type === 'split') throw new Error(`not a leaf: ${path}`)
	return replaceAt(design, path, () => clone(leaf))
}

/** Clamp bar offsets so child i spans at least mins[i]; falls back to equal division when impossible. */
function clampAt(at: number[], span: number, mins: number[]): number[] {
	const n = at.length + 1
	if (span < mins.reduce((a, b) => a + b, 0)) return at.map((_, i) => round1((span * (i + 1)) / n))
	// Round first: bounds below are on the 0.1 mm grid, so clamping keeps the result on it.
	const out = at.map(round1)
	for (let i = 0; i < out.length; i++) out[i] = Math.max(out[i], (i === 0 ? 0 : out[i - 1]) + mins[i])
	for (let i = out.length - 1; i >= 0; i--) out[i] = Math.min(out[i], (i === out.length - 1 ? span : out[i + 1]) - mins[i + 1])
	return out.map(round1)
}

function rescale(node: DesignNode, oldW: number, oldH: number, w: number, h: number): void {
	if (node.type !== 'split') return
	const v = node.dir === 'v'
	const [oldSpan, span] = v ? [oldW, w] : [oldH, h]
	const oldBounds = [0, ...node.at, oldSpan]
	const mins = node.children.map((c) => minSpan(c, node.dir))
	node.at = clampAt(node.at.map((a) => (a * span) / oldSpan), span, mins)
	const bounds = [0, ...node.at, span]
	node.children.forEach((child, i) => {
		const oldSize = oldBounds[i + 1] - oldBounds[i]
		const size = bounds[i + 1] - bounds[i]
		rescale(child, v ? oldSize : oldW, v ? oldH : oldSize, v ? size : w, v ? h : size)
	})
}

export function setSize(design: Design, width: number, height: number): Design {
	if (!isReal(width) || !isReal(height) || width <= 0 || height <= 0) throw new Error('invalid size')
	const next = clone(design)
	rescale(next.root, design.width, design.height, width, height)
	next.width = width
	next.height = height
	return next
}

/** Bounding box (mm) of the cell at `path`. */
function cellBox(design: Design, path: string): { x: number; y: number; w: number; h: number } {
	let x = 0, y = 0, w = design.width, h = design.height
	let node = design.root
	for (const i of indices(path)) {
		if (node.type !== 'split') throw new Error(`no node at ${path}`)
		const bounds = [0, ...node.at, node.dir === 'v' ? w : h]
		const size = bounds[i + 1] - bounds[i]
		if (node.dir === 'v') { x += bounds[i]; w = size }
		else { y += bounds[i]; h = size }
		node = node.children[i]
	}
	return { x, y, w, h }
}

/** Compute split offsets within `path` for either equal centerlines ('mullion') or equal clear glass ('glass'). */
export function equalSplitAt(
	design: Design,
	path: string,
	dir: SplitDir,
	count: number,
	mode: 'mullion' | 'glass' = 'mullion',
	frameFace = 42,
	barFace = 40,
	bottomFace = frameFace,
): number[] {
	const { x, y, w, h } = cellBox(design, path)
	const span = dir === 'v' ? w : h
	if (mode === 'glass') {
		const firstDed = dir === 'v' ? (x === 0 ? frameFace : barFace / 2) : (y === 0 ? frameFace : barFace / 2)
		const lastDed = dir === 'v'
			? (Math.abs(x + w - design.width) < 0.1 ? frameFace : barFace / 2)
			: (Math.abs(y + h - design.height) < 0.1 ? bottomFace : barFace / 2)
		const totalClear = Math.max((count + 1) * (MIN_CELL - barFace), span - firstDed - lastDed - count * barFace)
		const g = totalClear / (count + 1)
		return Array.from({ length: count }, (_, i) => round1(firstDed + (i + 1) * g + (i + 0.5) * barFace))
	}
	return Array.from({ length: count }, (_, i) => round1((span * (i + 1)) / (count + 1)))
}

/** Split cell `path` by inserting `count` dividers (`count + 1` bays), flattening same-dir parent splits cleanly. */
export function splitCellWithCount(
	design: Design,
	path: string,
	dir: SplitDir,
	count: number,
	mode: 'mullion' | 'glass' = 'mullion',
	frameFace = 42,
	barFace = 40,
	bottomFace = frameFace,
): Design {
	const parts = count + 1
	if (parts < 2) return design
	const leaf = walkTo(design.root, path) as LeafNode
	const makeChildren = (base: LeafNode, n: number): DesignNode[] =>
		Array.from({ length: n }, (_, i) =>
			i === 0 ? clone(base) : (base.type === 'fixed' ? clone(base) : { type: 'fixed', glass: base.glass }),
		)

	if (path !== 'F1') {
		const parentPath = path.slice(0, path.lastIndexOf('.'))
		const idx = Number(path.slice(path.lastIndexOf('.') + 1))
		const parent = walkTo(design.root, parentPath)
		if (parent.type === 'split' && parent.dir === dir) {
			const next = clone(design)
			const nextParent = walkTo(next.root, parentPath) as SplitNode
			const newChildren = makeChildren(leaf, parts)
			if (mode === 'glass') {
				nextParent.children.splice(idx, 1, ...newChildren)
				nextParent.at = equalSplitAt(next, parentPath, dir, nextParent.children.length - 1, 'glass', frameFace, barFace, bottomFace)
			} else {
				const { w: pw, h: ph } = cellBox(next, parentPath)
				const pSpan = dir === 'v' ? pw : ph
				const b = [0, ...nextParent.at, pSpan]
				const start = b[idx]
				const localAt = equalSplitAt(next, path, dir, count, 'mullion', frameFace, barFace, bottomFace)
				nextParent.at.splice(idx, 0, ...localAt.map((v) => round1(start + v)))
				nextParent.children.splice(idx, 1, ...newChildren)
			}
			return next
		}
	}
	const at = equalSplitAt(design, path, dir, count, mode, frameFace, barFace, bottomFace)
	return replaceAt(design, path, () => ({ type: 'split', dir, at, children: makeChildren(leaf, parts) }))
}

function isReal(v: unknown): v is number {
	return typeof v === 'number' && Number.isFinite(v)
}

export function validateDesign(design: Design): string | null {
	if (!isReal(design?.width) || !isReal(design?.height) || design.width <= 0 || design.height <= 0)
		return `F1: width and height must be positive numbers, got ${design?.width} x ${design?.height}`
	if (!design.root) return 'F1: design has no root node'
	return validateNode(design.root, 'F1', 1, design.width, design.height)
}

function validateNode(node: DesignNode, path: string, depth: number, w: number, h: number): string | null {
	if (depth > MAX_DEPTH) return `${path}: design tree depth exceeds ${MAX_DEPTH}`
	if (!node || typeof node !== 'object') return `${path}: node must be an object`
	if (LEAF_TYPES.includes(node.type)) {
		const glass = (node as LeafNode).glass
		return glass !== undefined && glass !== null && typeof glass !== 'string' ? `${path}: glass must be a string code` : null
	}
	if (node.type !== 'split') return `${path}: unknown node type ${JSON.stringify((node as { type?: unknown }).type)}`
	if (node.dir !== 'v' && node.dir !== 'h') return `${path}: split dir must be 'v' or 'h'`
	const { at, children } = node
	if (!Array.isArray(at) || !at.every(isReal)) return `${path}: split at must be a list of finite numbers`
	if (!Array.isArray(children) || children.length < 2 || at.length !== children.length - 1)
		return `${path}: split needs at least 2 children and len(at) == children - 1`
	const span = node.dir === 'v' ? w : h
	const bounds = [0, ...at, span]
	if (bounds.some((b, i) => i > 0 && !(bounds[i - 1] < b))) return `${path}: split positions must increase strictly inside (0, ${span})`
	for (let i = 0; i < children.length; i++) {
		const size = bounds[i + 1] - bounds[i]
		const err = validateNode(children[i], `${path}.${i}`, depth + 1, node.dir === 'v' ? size : w, node.dir === 'v' ? h : size)
		if (err) return err
	}
	return null
}
