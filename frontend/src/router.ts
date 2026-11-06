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
  {
    path: '/series-studio',
    name: 'SeriesStudio',
    component: () => import('@/pages/SeriesStudio.vue'),
  },
  {
    path: '/series-studio/series/new',
    name: 'NewProfileSeries',
    component: () => import('@/pages/studio/ProfileSeriesFormPage.vue'),
  },
  {
    path: '/series-studio/series/:name',
    name: 'EditProfileSeries',
    component: () => import('@/pages/studio/ProfileSeriesFormPage.vue'),
    props: true,
  },
  {
    path: '/series-studio/versions/new',
    name: 'NewSeriesVersion',
    component: () => import('@/pages/studio/SeriesVersionFormPage.vue'),
  },
  {
    path: '/series-studio/versions/:name',
    name: 'EditSeriesVersion',
    component: () => import('@/pages/studio/SeriesVersionFormPage.vue'),
    props: true,
  },
  {
    path: '/series-studio/profiles/new',
    name: 'NewFenestrationProfile',
    component: () => import('@/pages/studio/ProfileFormPage.vue'),
  },
  {
    path: '/series-studio/profiles/:name',
    name: 'EditFenestrationProfile',
    component: () => import('@/pages/studio/ProfileFormPage.vue'),
    props: true,
  },
  {
    path: '/series-studio/glass/new',
    name: 'NewFenestrationGlass',
    component: () => import('@/pages/studio/GlassFormPage.vue'),
  },
  {
    path: '/series-studio/glass/:name',
    name: 'EditFenestrationGlass',
    component: () => import('@/pages/studio/GlassFormPage.vue'),
    props: true,
  },
]

export function createAppRouter() {
  return createRouter({ history: createWebHistory('/fenestration'), routes })
}
