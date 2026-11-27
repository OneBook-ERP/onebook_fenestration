import { describe, it, expect } from 'vitest'
import { grillConfig, grillMembers } from './grill'
import type { Design } from './types'
describe('panel grills', () => {
 it('adds a surround and grid only to the chosen panel and survives JSON storage', () => {
  const design: Design = { width:1200,height:1200,root:{type:'split',dir:'v',at:[600],children:[{type:'fixed',glass:'6CTG',grill:{}},{type:'fixed',glass:'6CTG'}]}}
  const bars=grillMembers(design)
  expect(bars).toHaveLength(9)
  expect(bars.every(b=>b.path==='F1.0' && b.x>=42 && b.x+b.w<=558 && b.y>=42 && b.y+b.h<=1158)).toBe(true)
  expect(grillMembers(JSON.parse(JSON.stringify(design)))).toEqual(bars)
  if(design.root.type==='split' && design.root.children[0].type!=='split') delete design.root.children[0].grill
  expect(grillMembers(design)).toHaveLength(0)
 })
 it('bounds counts and sizes and omits panels too small to fit', () => {
  expect(grillConfig({vertical:Infinity,horizontal:1000,width:-5})).toMatchObject({vertical:3,horizontal:40,width:2})
  expect(grillMembers({width:50,height:50,root:{type:'fixed',glass:'6CTG',grill:{}}})).toEqual([])
 })
})
