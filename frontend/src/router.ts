import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: () => import('@/pages/Home.vue') },
]

export function createAppRouter() {
  return createRouter({ history: createWebHistory('/fenestration'), routes })
}
