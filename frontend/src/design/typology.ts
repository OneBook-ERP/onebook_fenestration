import type { ComputeResult } from '@/api'
import type { DesignNode, LeafNode } from '@/design/types'

function leaves(node: DesignNode): LeafNode[] {
	return node.type === 'split' ? node.children.flatMap(leaves) : [node]
}

const KIND_LABEL: Record<LeafNode['type'], string> = { sash: 'Casement', fixed: 'fixed', louver: 'louver' }
const KIND_ORDER: LeafNode['type'][] = ['sash', 'fixed', 'louver']

/** Short human description of a design, e.g. "2-sash casement" or "Casement + fixed". */
export function typology(root: DesignNode): string {
	const all = leaves(root)
	const kinds = [...new Set(all.map((l) => l.type))]
	if (kinds.includes('louver')) return 'Ventilator'
	if (kinds.length === 1 && kinds[0] === 'sash') return all.length > 1 ? `${all.length}-sash casement` : 'Casement'
	if (kinds.length === 1) return 'Fixed'
	if (all.length === 3 && all[0].type === 'sash' && all[1].type === 'fixed' && all[2].type === 'sash') {
		return 'Sash · fixed · sash'
	}
	return KIND_ORDER.filter((k) => kinds.includes(k)).map((k) => KIND_LABEL[k]).join(' + ')
}

type PathRows = Pick<ComputeResult, 'members' | 'glass'>

/** Engine panel id for a leaf path; falls back to the path itself. */
export function panelLabel(path: string, result: PathRows | null | undefined): string {
	const row = result?.members.find((m) => m.path === path) ?? result?.glass.find((g) => g.path === path)
	return row?.panel ?? path
}
