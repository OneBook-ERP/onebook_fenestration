/** Coordinates are millimetres from the panel's left and top edges. */
export interface ExhaustCut { diameter: number; centerX: number; centerY: number }
export function exhaustCut(node: { fan?: boolean; fanCut?: Partial<ExhaustCut>; type?: string }, width: number, height: number): ExhaustCut | null {
	if (!node.fan || node.type === 'louver') return null
	const diameter = node.fanCut?.diameter ?? 180
	const centerX = node.fanCut?.centerX ?? width / 2
	const centerY = node.fanCut?.centerY ?? height / 2
	const r = diameter / 2
	if (![diameter, centerX, centerY, width, height].every(Number.isFinite) || diameter <= 0 ||
		centerX - r <= 0 || centerX + r >= width || centerY - r <= 0 || centerY + r >= height) return null
	return { diameter, centerX, centerY }
}

export function steelThickness(node: { steelThickness?: number }): number {
	return Number.isFinite(node.steelThickness) && node.steelThickness! > 0 ? node.steelThickness! : 1.2
}
