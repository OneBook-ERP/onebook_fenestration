import type { Intersection, Object3D } from 'three'
/** Allow a visible grill behind transparent glass to be picked, but never through opaque members. */
export function pickWindowHit(hits: Intersection<Object3D>[]) {
 const first=hits[0]
 if (!first || first.object.userData.kind !== 'glass' || first.object.userData.infillMaterial === 'steel') return first
 const solid=hits.find(hit=>hit.object.userData.kind !== 'glass' || hit.object.userData.infillMaterial === 'steel')
 return solid?.object.userData.kind==='grill' ? solid : first
}
