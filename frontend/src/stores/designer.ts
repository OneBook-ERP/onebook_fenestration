import { defineStore } from 'pinia'
import { computeDesign, type ComputeResult, type SeriesInfo } from '@/api'
import { layoutGeom } from '@/design/geometry'
import { getNode, newDesign, setLeaf, validateDesign } from '@/design/tree'
import type {
	Design,
	LeafNode,
	SashNode,
	SectionPieceTransform,
	SectionViewportState,
	SelectionKind,
	SelectionState,
} from '@/design/types'

export const HISTORY_CAP = 50
export const COMPUTE_DEBOUNCE_MS = 300

let timer: ReturnType<typeof setTimeout> | undefined

export function migrateDesignProfiles(design: Design): Design {
	if (!design) return design
	const next = JSON.parse(JSON.stringify(design)) as Design
	if (!next.profiles) next.profiles = {}

	// Migrate frameProfileId <-> profiles.frame
	if (next.frameProfileId && !next.profiles.frame) {
		next.profiles.frame = next.frameProfileId
	} else if (next.profiles.frame && !next.frameProfileId) {
		next.frameProfileId = next.profiles.frame
	}

	// Migrate legacy global profiles.sash to individual sash nodes if not set
	if (next.profiles.sash) {
		const defaultSash = next.profiles.sash
		const cells = layoutGeom(next).cells
		for (const cell of cells) {
			if (cell.node.type === 'sash' && !cell.node.profile) {
				cell.node.profile = defaultSash
				next.profiles[cell.path] = defaultSash
			}
		}
	}

	return next
}

export const useDesignerStore = defineStore('designer', {
	state: () => ({
		design: newDesign(915, 1220) as Design,
		selectedPath: 'F1' as string,
		past: [] as Design[],
		future: [] as Design[],
		result: null as ComputeResult | null,
		seriesInfo: null as SeriesInfo | null,
		seriesVersion: '',
		finish: '' as string,
		priceStructure: '' as string,
		error: null as string | null,
		computing: false,
		requestSeq: 0,
		dirty: false,
		dragOrigin: null as Design | null,
	}),
	getters: {
		selection(state): SelectionState {
			const sel = state.selectedPath
			if (!sel) return { kind: 'none', id: '' }
			if (sel.startsWith('BEAD:')) {
				const memberPath = sel.replace(/^BEAD:/, '')
				return { kind: 'bead', id: sel, memberPath }
			}
			if (sel === 'FRAME' || sel === 'F1') {
				// If root is a split, F1 is the outer frame context in designer
				return { kind: 'frame', id: 'FRAME', panelId: 'F1' }
			}
			if (sel.startsWith('GLASS:')) {
				const cellPath = sel.replace(/^GLASS:/, '')
				return { kind: 'glass', id: sel, memberPath: cellPath }
			}
			if (/^[MT]\d+$/.test(sel)) {
				return { kind: 'bar', id: sel, panelId: sel }
			}
			return { kind: 'sash', id: sel, memberPath: sel }
		},
	},
	actions: {
		apply(fn: (d: Design) => Design) {
			const next = fn(this.design)
			if (next === this.design) return
			this.pushHistory(this.design)
			this.setDesign(next)
		},
		/** Start a drag: later dragTo calls skip history and endDrag records one undo step. */
		beginDrag() {
			this.dragOrigin = JSON.parse(JSON.stringify(this.design))
		},
		dragTo(fn: (d: Design) => Design) {
			if (!this.dragOrigin) return this.apply(fn)
			const next = fn(this.design)
			if (next !== this.design) this.setDesign(next)
		},
		endDrag() {
			const origin = this.dragOrigin
			this.dragOrigin = null
			if (origin && JSON.stringify(origin) !== JSON.stringify(this.design)) this.pushHistory(origin)
		},
		markDirty() {
			this.dirty = true
		},
		markSaved() {
			this.dirty = false
		},
		pushHistory(design: Design) {
			this.past.push(design)
			if (this.past.length > HISTORY_CAP) this.past.shift()
			this.future = []
		},
		setDesign(design: Design) {
			this.design = design
			this.dirty = true
			this.scheduleCompute()
		},
		undo() {
			const prev = this.past.pop()
			if (!prev) return
			this.future.push(this.design)
			this.setDesign(prev)
			this.keepSelection()
		},
		redo() {
			const next = this.future.pop()
			if (!next) return
			this.past.push(this.design)
			this.setDesign(next)
			this.keepSelection()
		},
		/** After undo/redo the selected node may be gone: select its nearest existing ancestor. */
		keepSelection() {
			let path = this.selectedPath
			if (!path) return
			if (/^[MT]\d+$/.test(path)) {
				const exists = layoutGeom(this.design).bars.some((b) => b.id === path)
				if (!exists) this.selectedPath = 'F1'
				return
			}
			while (path.includes('.') && !hasNode(this.design, path)) path = path.slice(0, path.lastIndexOf('.'))
			this.selectedPath = path
		},
		select(target: string | SelectionState) {
			if (!target) {
				this.selectedPath = ''
				return
			}
			if (typeof target === 'string') {
				this.selectedPath = target
				return
			}
			if (target.kind === 'none') {
				this.selectedPath = ''
			} else if (target.kind === 'frame') {
				this.selectedPath = 'FRAME'
			} else if (target.kind === 'glass') {
				this.selectedPath = target.id.startsWith('GLASS:') ? target.id : `GLASS:${target.id}`
			} else {
				this.selectedPath = target.id
			}
		},
		setProfile(
			kind: 'frame' | 'sash' | 'bar' | 'bead',
			id: string,
			profileCode: string | undefined,
			roleTag?: string,
		) {
			const cleanCode = profileCode && profileCode !== 'NONE' ? profileCode.trim() : undefined
			// Role validation
			if (roleTag && cleanCode) {
				const tag = roleTag.toLowerCase()
				if (kind === 'frame' && tag !== 'frame') {
					throw new Error(`Cannot assign role '${roleTag}' to outer frame`)
				}
				if (kind === 'sash' && tag !== 'sash') {
					throw new Error(`Cannot assign role '${roleTag}' to sash`)
				}
				if (kind === 'bar' && tag !== 'mullion' && tag !== 'transom') {
					throw new Error(`Cannot assign role '${roleTag}' to bar`)
				}
				if (kind === 'bead' && tag !== 'bead') {
					throw new Error(`Cannot assign role '${roleTag}' to bead`)
				}
			}

			this.apply((d) => {
				const nextProfiles = { ...(d.profiles ?? {}) }

				if (kind === 'frame') {
					if (cleanCode) {
						nextProfiles.frame = cleanCode
					} else {
						delete nextProfiles.frame
					}
					return {
						...d,
						frameProfileId: cleanCode,
						profiles: Object.keys(nextProfiles).length ? nextProfiles : undefined,
					}
				}

				if (kind === 'sash') {
					if (id === 'sash' || id === 'global') {
						if (cleanCode) {
							nextProfiles.sash = cleanCode
						} else {
							delete nextProfiles.sash
						}
						return {
							...d,
							sashProfileId: cleanCode,
							profiles: Object.keys(nextProfiles).length ? nextProfiles : undefined,
						}
					}
					const targetNode = getNode(d, id)
					if (targetNode.type !== 'sash') return d
					const updatedSash: SashNode = {
						...targetNode,
						profile: cleanCode,
					}
					if (cleanCode) {
						nextProfiles[id] = cleanCode
					} else {
						delete nextProfiles[id]
					}
					const withLeaf = setLeaf(d, id, updatedSash)
					return {
						...withLeaf,
						profiles: Object.keys(nextProfiles).length ? nextProfiles : undefined,
					}
				}

				if (kind === 'bar') {
					if (id === 'mullion' || id === 'transom' || id === 'bar' || id === 'global') {
						if (cleanCode) {
							nextProfiles.mullion = cleanCode
							nextProfiles.transom = cleanCode
						} else {
							delete nextProfiles.mullion
							delete nextProfiles.transom
						}
						return {
							...d,
							mullionProfileId: cleanCode,
							profiles: Object.keys(nextProfiles).length ? nextProfiles : undefined,
						}
					}
					if (cleanCode) {
						nextProfiles[id] = cleanCode
					} else {
						delete nextProfiles[id]
					}
					return {
						...d,
						profiles: Object.keys(nextProfiles).length ? nextProfiles : undefined,
					}
				}

				if (kind === 'bead') {
					if (id === 'bead' || id === 'global') {
						if (cleanCode) {
							nextProfiles.bead = cleanCode
						} else {
							delete nextProfiles.bead
						}
						return {
							...d,
							beadProfileId: cleanCode,
							profiles: Object.keys(nextProfiles).length ? nextProfiles : undefined,
						}
					}
					try {
						const targetNode = getNode(d, id)
						if (targetNode.type === 'sash' || targetNode.type === 'fixed') {
							const updatedNode = {
								...targetNode,
								beadProfileId: cleanCode,
							}
							if (cleanCode) {
								nextProfiles[`${id}:bead`] = cleanCode
							} else {
								delete nextProfiles[`${id}:bead`]
							}
							const withLeaf = setLeaf(d, id, updatedNode as LeafNode)
							return {
								...withLeaf,
								profiles: Object.keys(nextProfiles).length ? nextProfiles : undefined,
							}
						}
					} catch {
						// fallback if node not found
					}
					return d
				}

				return d
			})
		},
		setFinish(finish: string) {
			if (finish === this.finish) return
			this.finish = finish
			this.dirty = true
			this.scheduleCompute()
		},
		setSeriesVersion(seriesVersion: string) {
			if (!seriesVersion || seriesVersion === this.seriesVersion) return
			this.seriesVersion = seriesVersion
			this.dirty = true
			this.scheduleCompute()
		},
		setMirrorSync(val: boolean) {
			if (this.design.mirrorSync === val) return
			this.design = { ...this.design, mirrorSync: val }
			this.dirty = true
		},
		setCompactGlass(val: boolean) {
			if (this.design.compactGlass === val) return
			this.design = { ...this.design, compactGlass: val }
			this.dirty = true
		},
		setActiveCutAxis(axis: 'h' | 'v') {
			if (this.design.activeCutAxis === axis) return
			this.design = { ...this.design, activeCutAxis: axis }
			this.dirty = true
		},
		setSectionViewport(axis: 'h' | 'v', vp: SectionViewportState) {
			const current = this.design.sectionViewport ?? {}
			this.design = {
				...this.design,
				sectionViewport: { ...current, [axis]: vp },
			}
			this.dirty = true
		},
		setSectionMap(map: Record<string, SectionPieceTransform>) {
			this.apply((d) => ({ ...d, sectionMap: map }))
		},
		reset(design: Design, seriesVersion: string, finish = '', priceStructure = '') {
			const migrated = migrateDesignProfiles(design)
			this.$patch({
				design: migrated,
				seriesVersion,
				finish,
				priceStructure,
				selectedPath: 'F1',
				past: [],
				future: [],
				result: null,
				seriesInfo: null,
				error: null,
				dirty: false,
				dragOrigin: null,
			})
			this.scheduleCompute()
		},
		cancelCompute() {
			clearTimeout(timer)
			this.requestSeq += 1
			this.computing = false
		},
		scheduleCompute() {
			clearTimeout(timer)
			this.requestSeq += 1
			const invalid = validateDesign(this.design)
			if (invalid) {
				this.error = invalid
				this.computing = false
				return
			}
			timer = setTimeout(() => this.runCompute(), COMPUTE_DEBOUNCE_MS)
		},
		async runCompute() {
			const seq = this.requestSeq
			this.computing = true
			let res
			try {
				res = await computeDesign(this.design, this.seriesVersion, this.finish, this.priceStructure)
			} catch (e) {
				res = { ok: false as const, message: e instanceof Error ? e.message : String(e) }
			}
			if (seq !== this.requestSeq) return
			this.computing = false
			if (res.ok) {
				this.result = res.result
				this.seriesInfo = res.series ?? null
				this.error = null
			} else {
				this.error = res.message
			}
		},
	},
})

function hasNode(design: Design, path: string): boolean {
	try {
		getNode(design, path)
		return true
	} catch {
		return false
	}
}
