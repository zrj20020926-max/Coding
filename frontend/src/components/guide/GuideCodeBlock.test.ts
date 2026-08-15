import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import GuideCodeBlock from '@/components/guide/GuideCodeBlock.vue'
import { useEditorStore } from '@/stores/editor'
import type { GuideCodeExample } from '@/types/guide'

const example: GuideCodeExample = {
  id: 'one-integer-v8',
  title: '一个整数 · JavaScript V8',
  runtime: 'javascript-v8',
  code: 'const n = Number(readline());\nprint(n);',
  targetSlug: 'js-acm-read-one-integer',
}
const clipboardWriteText = vi.fn<(text: string) => Promise<void>>()

async function setup(item: GuideCodeExample = example) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/guide', component: { template: '<div />' } },
      { path: '/problems/:slug', name: 'problem-detail', component: { template: '<div />' } },
    ],
  })
  await router.push('/guide')
  const wrapper = mount(GuideCodeBlock, { props: { example: item }, global: { plugins: [pinia, router] } })
  return { wrapper, router }
}

describe('GuideCodeBlock', () => {
  beforeEach(() => {
    clipboardWriteText.mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: clipboardWriteText },
    })
  })

  it('copies the exact source code', async () => {
    const { wrapper } = await setup()
    await wrapper.get('button[aria-label^="复制"]').trigger('click')

    expect(clipboardWriteText).toHaveBeenCalledWith(example.code)
    expect(wrapper.text()).toContain('已复制')
  })

  it('queues the selected runtime and opens the matching workbench', async () => {
    const { wrapper, router } = await setup()
    await wrapper.get('button[aria-label*="带入训练工作台"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe(`/problems/${example.targetSlug}`)
    expect(useEditorStore().consumeGuideImport(example.targetSlug)).toMatchObject({
      runtime: 'javascript-v8',
      source: example.code,
    })
  })

  it('never offers an incorrect example as a workbench import', async () => {
    const { wrapper } = await setup({ ...example, variant: 'incorrect' })
    expect(wrapper.find('button[aria-label*="带入训练工作台"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label^="复制"]').exists()).toBe(true)
  })
})
