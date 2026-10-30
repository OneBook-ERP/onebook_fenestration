import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { getSession } from '@/api'
import App from './App.vue'
import { routes } from './router'

const calls = vi.hoisted(() => [] as { doctype: string; filters?: Record<string, unknown> }[])
vi.mock('@/api', () => ({ getSession: vi.fn(), logout: vi.fn(), createProject: vi.fn(), quoteStatus: vi.fn().mockResolvedValue({ quotation: null }) }))
vi.mock('frappe-ui', async (orig) => ({
  ...(await orig<object>()),
  useList: (o: { doctype: string; filters?: Record<string, unknown> }) => {
    calls.push(o)
    return { data: [], reload: () => {} }
  },
}))

const realLocation = window.location
afterEach(() => {
  Object.defineProperty(window, 'location', { value: realLocation, configurable: true })
  calls.length = 0
})

async function mountApp(path: string) {
  const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
  router.push(path)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return { router, wrapper }
}

describe('App', () => {
  it('reloads the workspace when the project changes', async () => {
    vi.mocked(getSession).mockResolvedValue({ user: 'a@b.c', roles: [] })
    const { router } = await mountApp('/projects/FP-A')
    await router.push('/projects/FP-B')
    await flushPromises()
    const designCalls = calls.filter((c) => c.doctype === 'Window Design')
    expect(designCalls.at(-1)?.filters).toEqual({ project: 'FP-B' })
  })

  it('keeps the deep link when redirecting guests to login', async () => {
    vi.mocked(getSession).mockResolvedValue({ user: 'Guest', roles: [] })
    const loc = { href: '', pathname: '/fenestration/projects/FP-A', search: '?x=1' }
    Object.defineProperty(window, 'location', { value: loc, configurable: true })
    await mountApp('/projects/FP-A')
    expect(loc.href).toBe('/login?redirect-to=' + encodeURIComponent('/fenestration/projects/FP-A?x=1'))
  })
  it('shows an alert with a reload button when the session fails to load', async () => {
    vi.mocked(getSession).mockRejectedValue(new Error('417'))
    const reload = vi.fn()
    Object.defineProperty(window, 'location', { value: { ...realLocation, reload }, configurable: true })
    const { wrapper } = await mountApp('/projects')
    expect(wrapper.text()).toContain('Could not load your session. Reload the page.')
    await wrapper.findAll('button').find((b) => b.text() === 'Reload')!.trigger('click')
    expect(reload).toHaveBeenCalled()
  })
})
