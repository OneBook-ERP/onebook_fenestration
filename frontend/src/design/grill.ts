import { layoutGeom } from './geometry'
import type { Design } from './types'

export interface Grill { vertical: number; horizontal: number; width: number; depth: number; offset: number; inset: number; shiftX: number; shiftY: number }
export const DEFAULT_GRILL: Grill = { vertical: 3, horizontal: 2, width: 12, depth: 12, offset: -30, inset: 42, shiftX: 0, shiftY: 0 }
export function grillConfig(value: Partial<Grill>): Grill {
 const number = (key: keyof Grill, low: number, high: number) => Math.max(low, Math.min(high, Number.isFinite(value[key]) ? value[key]! : DEFAULT_GRILL[key]))
 return { vertical: Math.round(number('vertical', 0, 40)), horizontal: Math.round(number('horizontal', 0, 40)), width: number('width', 2, 100), depth: number('depth', 2, 100), offset: number('offset', -500, 500), inset: number('inset', 0, 200), shiftX: number('shiftX', -500, 500), shiftY: number('shiftY', -500, 500) }
}
export interface GrillMember { path: string; x: number; y: number; w: number; h: number; depth: number; offset: number }
/** Fixed to the panel surround, including when its sash opens. Coordinates are window millimetres. */
export function grillMembers(design: Design): GrillMember[] {
 return layoutGeom(design).cells.flatMap(cell => {
  if (!cell.node.grill) return []
  const g = grillConfig(cell.node.grill)
  const x = cell.x + g.inset + g.shiftX, y = cell.y + g.inset + g.shiftY, w = cell.w - 2*g.inset, h = cell.h - 2*g.inset
  if (w <= 2*g.width || h <= 2*g.width) return []
  const t = Math.min(g.width, w/(g.vertical+2), h/(g.horizontal+2))
  const rect = (x: number, y: number, w: number, h: number): GrillMember => ({ path: cell.path, x, y, w, h, depth:g.depth, offset:g.offset })
  const bars = [rect(x,y,t,h), rect(x+w-t,y,t,h), rect(x+t,y,w-2*t,t), rect(x+t,y+h-t,w-2*t,t)]
  for(let i=1;i<=g.vertical;i++) bars.push(rect(x+t+(w-2*t)*i/(g.vertical+1)-t/2,y+t,t,h-2*t))
  for(let i=1;i<=g.horizontal;i++) bars.push(rect(x+t,y+t+(h-2*t)*i/(g.horizontal+1)-t/2,w-2*t,t))
  return bars
 })
}
