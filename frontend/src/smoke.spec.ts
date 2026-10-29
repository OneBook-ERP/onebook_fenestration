import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import App from './App.vue'
import { routes } from './router'

vi.mock('@/api', () => ({
  getSession: vi.fn().mockResolvedValue({ user: 'a@b.c', roles: ['Sales User'] }),
  logout: vi.fn(),
  createProject: vi.fn(),
}))
vi.mock('frappe-ui', async (orig) => ({ ...(await orig<object>()), useList: (await import('@/test-utils')).fakeUseList({}) }))

describe('smoke', () => {
  it('mounts App with the shell and the projects page', async () => {
    const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
    router.push('/')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/projects')
    expect(wrapper.text()).toContain('All projects')
    expect(wrapper.text()).toContain('New project')
  })
})
