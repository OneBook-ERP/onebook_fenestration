import type { BarGeom, CellGeom, Design, DesignNode } from './types'

interface Walk {
	cells: CellGeom[]
	bars: BarGeom[]
	counters: { v: number; h: number }
}

/** Flatten the tree into leaf cells and bars, numbered in the engine's depth-first order. */
export function layoutGeom(design: Design): { cells: CellGeom[]; bars: BarGeom[] } {
	const out: Walk = { cells: [], bars: [], counters: { v: 0, h: 0 } }
	walk(design.root, 'F1', 0, 0, design.width, design.height, out)
	return { cells: out.cells, bars: out.bars }
}

function walk(node: DesignNode, path: string, x: number, y: number, w: number, h: number, out: Walk): void {
	if (node.type !== 'split') {
		out.cells.push({ path, x, y, w, h, node })
		return
	}
	const v = node.dir === 'v'
	node.at.forEach((a, index) => {
		const n = ++out.counters[node.dir]
		out.bars.push(
			v
				? { id: `M${n}`, dir: 'v', splitPath: path, index, x: x + a, y, length: h }
				: { id: `T${n}`, dir: 'h', splitPath: path, index, x, y: y + a, length: w },
		)
	})
	const bounds = [0, ...node.at, v ? w : h]
	node.children.forEach((child, i) => {
		const start = bounds[i]
		const size = bounds[i + 1] - start
		if (v) walk(child, `${path}.${i}`, x + start, y, size, h, out)
		else walk(child, `${path}.${i}`, x, y + start, w, size, out)
	})
}
