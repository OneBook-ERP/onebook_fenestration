export interface GrillBox { x: number; y: number; w: number; h: number }
export interface GrillGuide { axis: 'x'|'y'; pos: number; start: number; end: number; center: boolean }
/** Snap the moving band edges/centre to the visible section geometry in screen-scaled tolerance. */
export function snapGrill(box: GrillBox, dx: number, dy: number, targets: GrillBox[], tolerance: number) {
 const guides: GrillGuide[]=[]
 const deltas={x:dx,y:dy}
 for (const axis of ['x','y'] as const) {
  const size=axis==='x'?'w':'h', other=axis==='x'?'y':'x', otherSize=axis==='x'?'h':'w'
  let best: {distance:number; shift:number; guide:GrillGuide}|undefined
  for(const target of targets) for(const fraction of [0,0.5,1]) for(const targetFraction of [0,0.5,1]) {
   if ((fraction===0.5)!==(targetFraction===0.5)) continue
   const pos=target[axis]+target[size]*targetFraction
   const shift=pos-(box[axis]+deltas[axis]+box[size]*fraction)
   if(Math.abs(shift)>tolerance || (best && Math.abs(shift)>=best.distance)) continue
   best={distance:Math.abs(shift),shift,guide:{axis,pos,start:Math.min(box[other]+deltas[other],target[other])-8,end:Math.max(box[other]+deltas[other]+box[otherSize],target[other]+target[otherSize])+8,center:fraction===0.5}}
  }
  if(best) {deltas[axis]+=best.shift;guides.push(best.guide)}
 }
 return {along:deltas.x,depth:deltas.y,guides}
}
