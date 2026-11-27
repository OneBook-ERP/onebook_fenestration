import {describe,it,expect} from 'vitest'
import {Mesh,BoxGeometry,MeshBasicMaterial} from 'three'
import {pickWindowHit} from './grillPicking'
const hit=(kind:string,infillMaterial?:string)=>({object:Object.assign(new Mesh(new BoxGeometry(),new MeshBasicMaterial()),{userData:{kind,infillMaterial}})}) as any
describe('grill picking',()=>{
 it('selects the visible grill through glass',()=>{
 const glass=hit('glass','glass'),grill=hit('grill')
 expect(pickWindowHit([glass,grill])).toBe(grill)
 expect(pickWindowHit([grill,glass])).toBe(grill)
 })
 it('does not select through steel or a frame and keeps ordinary glass selectable',()=>{
 const glass=hit('glass','glass'),steel=hit('glass','steel'),frame=hit('frame'),grill=hit('grill')
 expect(pickWindowHit([steel,grill])).toBe(steel)
 expect(pickWindowHit([frame,grill])).toBe(frame)
 expect(pickWindowHit([glass,frame,grill])).toBe(glass)
 expect(pickWindowHit([glass])).toBe(glass)
 })
})
