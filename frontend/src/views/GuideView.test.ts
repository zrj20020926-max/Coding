import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import GuideView from '@/views/GuideView.vue'

async function setup(path = '/guide') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/guide', component: GuideView },
      {
        path: '/guide/javascript-v8',
        component: GuideView,
        meta: { guideSection: 'javascript-v8' },
      },
      {
        path: '/guide/nodejs',
        component: GuideView,
        meta: { guideSection: 'nodejs' },
      },
      {
        path: '/guide/input-patterns',
        component: GuideView,
        meta: { guideSection: 'input-patterns' },
      },
      {
        path: '/guide/output-patterns',
        component: GuideView,
        meta: { guideSection: 'output-patterns' },
      },
      {
        path: '/guide/common-errors',
        component: GuideView,
        meta: { guideSection: 'common-errors' },
      },
      {
        path: '/guide/performance',
        component: GuideView,
        meta: { guideSection: 'performance' },
      },
      { path: '/problems/:slug', name: 'problem-detail', component: { template: '<div />' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(GuideView, { global: { plugins: [createPinia(), router] } })
  return { wrapper, router }
}

describe('GuideView', () => {
  it('renders a searchable chapter directory and mobile selector', async () => {
    const { wrapper } = await setup('/guide')
    expect(wrapper.find('.guide-sidebar').exists()).toBe(true)
    expect(wrapper.find('.guide-mobile-section-select').exists()).toBe(true)

    await wrapper.get('input[type="search"]').setValue('BigInt')
    expect(wrapper.findAll('.guide-search-results > a').length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('找到')
  })

  it('renders search input as text and never injects executable HTML', async () => {
    const { wrapper } = await setup('/guide')
    await wrapper.get('input[type="search"]').setValue('<img src=x onerror=alert(1)>')
    await flushPromises()

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.html()).not.toContain('<img src=x')
  })

  it('shows V8 examples as V8 blocks and Node.js examples as Node.js blocks', async () => {
    const v8 = await setup('/guide/javascript-v8')
    expect(v8.wrapper.findAll('.runtime-javascript-v8').length).toBeGreaterThan(0)
    expect(v8.wrapper.find('.runtime-nodejs').exists()).toBe(false)

    const node = await setup('/guide/nodejs')
    expect(node.wrapper.findAll('.runtime-nodejs').length).toBeGreaterThan(0)
    expect(node.wrapper.find('.runtime-javascript-v8').exists()).toBe(false)
  })
})
