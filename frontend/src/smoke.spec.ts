import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import App from './App.vue'
import { routes } from './router'

describe('smoke', () => {
  it('mounts App', async () => {
    const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
    router.push('/')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('Fenestration')
  })
})
