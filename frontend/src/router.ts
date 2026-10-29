import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/projects' },
  { path: '/projects', name: 'Projects', component: () => import('@/pages/Projects.vue') },
  {
    path: '/projects/:project',
    name: 'Project',
    component: () => import('@/pages/ProjectWorkspace.vue'),
    props: true,
  },
  {
    path: '/projects/:project/designs/new',
    name: 'NewDesign',
    component: () => import('@/pages/Designer.vue'),
    meta: { fullscreen: true },
    beforeEnter: (to) => (to.query.series_version ? true : { name: 'Project', params: to.params }),
  },
  {
    path: '/projects/:project/designs/:name',
    name: 'Designer',
    component: () => import('@/pages/Designer.vue'),
    meta: { fullscreen: true },
  },
]

export function createAppRouter() {
  return createRouter({ history: createWebHistory('/fenestration'), routes })
}
