import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: () => import('@/pages/Home.vue') },
  {
    path: '/projects/:project/designs/new',
    name: 'NewDesign',
    component: () => import('@/pages/Designer.vue'),
    beforeEnter: (to) => (to.query.series_version ? true : { name: 'Home' }),
  },
  { path: '/projects/:project/designs/:name', name: 'Designer', component: () => import('@/pages/Designer.vue') },
]

export function createAppRouter() {
  return createRouter({ history: createWebHistory('/fenestration'), routes })
}
