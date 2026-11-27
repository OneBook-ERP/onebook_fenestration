import { buildPlacedShape, seatedDefaultTransform } from './sectionPuzzle'
import type { SeatingEntry } from './sectionSeating'
import type { SectionPieceTransform } from './types'

/** Fit a complete assembly, independent of the order in which its cut pieces were emitted. */
export function fitSectionAssembly(entries: SeatingEntry[]): (SectionPieceTransform | null)[] {
	const transforms = entries.map(entry => ({ ...entry.transform }))
	const fitted: (SectionPieceTransform | null)[] = entries.map(() => null)
	const shapeAt = (index: number) => {
		const entry = entries[index]
		return buildPlacedShape(index, entry.piece, entry.start, entry.end, entry.outline, transforms[index])
	}
	// Both jambs/bars must exist before either sash edge is fitted. Beads are
	// glazing references, not independent targets for seating a sash on its host.
	const hosts = entries.flatMap((entry, index) =>
		['frame', 'mullion', 'transom', 'gasket'].includes(entry.piece.role) ? [shapeAt(index)] : [],
	)
	const groups = new Map<string, number[]>()
	entries.forEach((entry, index) => {
		if (entry.piece.role !== 'sash') return
		const key = `${entry.piece.path || entry.piece.panel}:${entry.piece.code}`
		groups.set(key, [...(groups.get(key) ?? []), index])
	})
	for (const indices of groups.values()) {
		// An existing placement is the reference for its unsaved partner.
		// Otherwise use the low-side member regardless of array ordering.
		const anchorIndex = indices.find(index => !entries[index].needsSeat)
			?? indices.find(index => !entries[index].piece.mirrored) ?? indices[0]
		const anchor = entries[anchorIndex]
		const transform = anchor.needsSeat
			? seatedDefaultTransform(anchorIndex, anchor.piece, anchor.start, anchor.end, anchor.outline, hosts)
			: transforms[anchorIndex]
		for (const index of indices) {
			if (!entries[index].needsSeat) continue
			transforms[index] = {
				...transform,
				offsetAlong: entries[index].piece.mirrored === anchor.piece.mirrored
					? transform.offsetAlong : -transform.offsetAlong,
			}
			fitted[index] = transforms[index]
		}
	}
	// Fit glazing only after all surrounding profiles have their final positions.
	const profiles = entries.flatMap((entry, index) => entry.piece.kind === 'profile' ? [shapeAt(index)] : [])
	entries.forEach((entry, index) => {
		if (entry.piece.kind !== 'glass' || !entry.needsSeat) return
		const owner = entry.piece.path || entry.piece.panel
		const surrounding = profiles.filter(shape => {
			const profileOwner = shape.piece.path || shape.piece.panel
			return ['frame', 'mullion', 'transom'].includes(shape.piece.role) || profileOwner === owner
		})
		const hasRebate = surrounding.some(shape => ['sash', 'bead', 'gasket', 'glass_adaptor'].includes(shape.piece.role))
		if (!hasRebate) return
		fitted[index] = seatedDefaultTransform(index, entry.piece, entry.start, entry.end, entry.outline, surrounding)
	})
	return fitted
}
