import {describe,it,expect} from 'vitest'
import {snapGrill} from './grillSnap'
describe('grill snapping',()=>{
 it('snaps a band edge to a profile edge and returns its alignment guide',()=>{
  const r=snapGrill({x:50,y:-36,w:96,h:12},0,10,[{x:0,y:-12,w:42,h:40}],3)
  expect(r.depth).toBe(12)
  expect(r.guides.some(g=>g.axis==='y' && g.pos===-12 && !g.center)).toBe(true)
 })
 it('snaps centres and leaves movement outside the capture distance unchanged',()=>{
  const box={x:50,y:-36,w:96,h:12}, target={x:55,y:30,w:96,h:12}
  const snapped=snapGrill(box,4,0,[target],2)
  expect(snapped.along).toBe(5)
  const free=snapGrill(box,20,20,[target],2)
  expect(free).toMatchObject({along:20,depth:20,guides:[]})
 })
})
