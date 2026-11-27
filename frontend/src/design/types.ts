export type SplitDir = 'v' | 'h'
export type FrameConfig = '4-side' | '3-side' | '3-side-threshold'
export type SashConfig = 'window' | 'door'
export type ColorMode = 'none' | 'single' | 'dual'

export interface SplitNode {
	type: 'split'
	dir: SplitDir
	at: number[]
	children: DesignNode[]
	slideRatios?: number[]
}

export interface SashNode {
	type: 'sash'
	glass: string
	itemType?: 'Glass' | 'Panel'
	panelItem?: string
	profile?: string
	beadProfileId?: string
	bead?: boolean
	opening?: string
	hinge?: string
	hinge_type?: 'friction' | 'butt'
	hingeStay?: 'none' | 'hinges' | 'friction' | 'None' | 'Hinges' | 'Friction stay'
	sashConfig?: SashConfig
	activeLeaf?: boolean
	handleItem?: string
	hingeItem?: string
	allowEqualization?: boolean
	isSliding?: boolean
	slideFixed?: boolean
	slideDir?: 'left' | 'right'
	trackIdx?: number
	trackCount?: number
	handle?: 'multipoint' | 'single'
	limiter?: boolean
	mesh?: boolean
	meshType?: string
	addon?: 'Railing' | 'AC' | 'Panel'
	ghh?: number
	lock?: string
	grill?: Partial<import('./grill').Grill>
	fan?: boolean
	steelThickness?: number
	fanCut?: Partial<import('./exhaustCut').ExhaustCut>
}

export interface FixedNode {
	type: 'fixed'
	glass: string
	itemType?: 'Glass' | 'Panel'
	panelItem?: string
	beadProfileId?: string
	bead?: boolean
	mesh?: boolean
	meshType?: string
	addon?: 'Railing' | 'AC' | 'Panel'
	grill?: Partial<import('./grill').Grill>
	fan?: boolean
	steelThickness?: number
	fanCut?: Partial<import('./exhaustCut').ExhaustCut>
}

export interface LouverNode {
	type: 'louver'
	glass: string
	itemType?: 'Glass' | 'Panel'
	panelItem?: string
	blades: number
	/** Actual blade chord before tilting, in mm. */
	bladeWidth?: number
	bladeMaterial?: 'glass' | 'metal'
	bead?: boolean
	mesh?: boolean
	meshType?: string
	addon?: 'Railing' | 'AC' | 'Panel'
	grill?: Partial<import('./grill').Grill>
	fan?: boolean
	steelThickness?: number
	fanCut?: Partial<import('./exhaustCut').ExhaustCut>
}

export type LeafNode = SashNode | FixedNode | LouverNode
export type DesignNode = SplitNode | LeafNode

export interface SectionPieceTransform {
	/** Offset along the cut axis (mm): positive moves inward toward the stationary glass reference. */
	offsetAlong: number
	/** Offset in cross-section depth (mm): positive moves down (toward inside), negative moves up (toward outside). */
	offsetDepth: number
	/** Additional rotation in degrees (0, 90, 180, 270). */
	rotation: number
	/** Additional horizontal flip in the cross-section plane. */
	flipX?: boolean
	/** Additional vertical flip in the cross-section plane. */
	flipY?: boolean
	/** Local SVG datum in mm. Rotation and flips occur around this profile point. */
	originU?: number
	originDepth?: number
}

export type SelectionKind = 'frame' | 'sash' | 'bar' | 'glass' | 'bead' | 'grill' | 'none'

export interface SelectionState {
	kind: SelectionKind
	id: string
	memberPath?: string
	panelId?: string
}

export interface SectionViewportState {
	zoom: number
	pan: { x: number; y: number }
}

export interface Design {
	width: number
	height: number
	series?: string
	frameConfig?: FrameConfig
	colorMode?: ColorMode
	finish?: string
	finishOutside?: string
	frameOverridden?: Record<string, boolean>
	sillHeight?: number
	frameProfileId?: string
	sashProfileId?: string
	mullionProfileId?: string
	beadProfileId?: string
	beadJoint?: 'm' | 'b'
	beadOffset?: { along: number; depth: number }
	hinge?: 'auto' | 'left' | 'right' | 'top' | 'bottom'
	isSliding?: boolean
	trackCount?: number
	/** Optional Fenestration Profile overrides keyed by role (`frame`, `sash`, `mullion`, `transom`) or id (`M1`, `F1.0`). */
	profiles?: Record<string, string>
	/** Shared cross-section assembly map (keyed by `role:code` or piece key) used by 2D section editor & 3D extrusion. */
	sectionMap?: Record<string, SectionPieceTransform>
	root: DesignNode

	// Persisted Section-Editor State
	/** Mirror & Sync toggle flag: pure boolean flag, persisted in design (default true). */
	mirrorSync?: boolean
	/** 1:1 Profile Focus toggle flag: persisted in design (default true). */
	compactGlass?: boolean
	/** Active cut axis ('h' for B-B or 'v' for A-A). */
	activeCutAxis?: 'h' | 'v'
	/** Viewport zoom and pan state per cut axis. */
	sectionViewport?: {
		h?: SectionViewportState
		v?: SectionViewportState
	}
}

export interface CellGeom {
	path: string
	x: number
	y: number
	w: number
	h: number
	node: LeafNode
}

export interface BarGeom {
	id: string
	dir: SplitDir
	splitPath: string
	index: number
	x: number
	y: number
	length: number
}
