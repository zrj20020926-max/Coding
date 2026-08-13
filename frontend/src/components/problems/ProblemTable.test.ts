import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import ProblemTable from '@/components/problems/ProblemTable.vue'
import type { ProblemSummary } from '@/types/problem'

const problem: ProblemSummary = {
  id: 12,
  slug: 'a-plus-b',
  title: 'A+B 问题',
  difficulty: 'easy',
  training_category: 'single-line-multiple-values',
  source: null,
  accepted_count: 80,
  submission_count: 100,
  acceptance_rate: 80,
  tags: [{ id: 1, slug: 'array', name: '数组' }],
  solved: true,
  attempted: true,
  attempt_count: 1,
  favorited: true,
}

describe('ProblemTable', () => {
  it('shows catalog columns, progress and a slug-based detail link', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/problems/:slug', name: 'problem-detail', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(ProblemTable, {
      props: { problems: [problem], authenticated: true },
      global: { plugins: [router] },
    })

    expect(wrapper.text()).toContain('#0012')
    expect(wrapper.text()).toContain('A+B 问题')
    expect(wrapper.text()).toContain('数组')
    expect(wrapper.text()).toContain('80.0%')
    expect(wrapper.text()).toContain('已通过')
    expect(wrapper.get('a').attributes('href')).toBe('/problems/a-plus-b')

    await wrapper.get('button[aria-label="取消收藏 A+B 问题"]').trigger('click')
    expect(wrapper.emitted('favorite')?.[0]).toEqual([problem])
  })
})
