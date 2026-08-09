import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import SubmissionResultPanel from '@/components/submissions/SubmissionResultPanel.vue'
import type { SubmissionDetail } from '@/types/submission'

const detail: SubmissionDetail = {
  id: 'safe-id',
  problem: { id: 1, slug: 'a-plus-b', title: 'A+B' },
  language: { id: 1, slug: 'cpp', display_name: 'C++', version: '20' },
  status: 'Compile Error',
  mode: 'judge',
  time_used_ms: 3,
  memory_used_kb: 2048,
  passed_case_count: 0,
  total_case_count: 3,
  score: '0.00',
  judged_at: '2026-08-09T00:00:01Z',
  created_at: '2026-08-09T00:00:00Z',
  updated_at: '2026-08-09T00:00:01Z',
  source_code: 'int main() {}',
  compiler_output: 'error: missing return',
  error_message: 'Compilation failed',
  sample_output: null,
}

describe('SubmissionResultPanel', () => {
  it('renders safe aggregate diagnostics without hidden case data', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/submissions/:id', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(SubmissionResultPanel, {
      props: { submission: detail, detail, polling: false, timedOut: false, error: '' },
      global: { plugins: [router] },
    })

    expect(wrapper.text()).toContain('编译错误')
    expect(wrapper.text()).toContain('3 ms')
    expect(wrapper.text()).toContain('2.0 MB')
    expect(wrapper.text()).toContain('0 / 3')
    expect(wrapper.text()).toContain('error: missing return')
    expect(wrapper.html()).not.toContain('object_key')
    expect(wrapper.html()).not.toContain('expected_output')
  })
})
