export type SplitDir = 'v' | 'h'

export interface SplitNode {
	type: 'split'
	dir: SplitDir
	at: number[]
	children: DesignNode[]
}

export interface SashNode {
	type: 'sash'
	glass: string
	opening?: string
	hinge?: string
	ghh?: number
}

export interface FixedNode {
	type: 'fixed'
	glass: string
}

export interface LouverNode {
	type: 'louver'
	glass: string
	blades: number
}

export type LeafNode = SashNode | FixedNode | LouverNode
export type DesignNode = SplitNode | LeafNode

export interface Design {
	width: number
	height: number
	series?: string
	finish?: string
	root: DesignNode
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
