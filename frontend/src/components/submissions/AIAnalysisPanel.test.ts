import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AIAnalysisPanel from '@/components/submissions/AIAnalysisPanel.vue'
import { getAIAnalysis } from '@/services/aiAnalyses'

vi.mock('@/services/aiAnalyses')

describe('AIAnalysisPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('always shows the accuracy warning and renders only structured fields', async () => {
    vi.mocked(getAIAnalysis).mockResolvedValue({
      id: 'analysis-1',
      submission_id: 'submission-1',
      status: 'completed',
      failure_reason: '可能存在边界错误',
      time_complexity: 'O(n)',
      space_complexity: 'O(1)',
      suggestions: ['检查下标范围'],
      guiding_questions: ['空输入如何处理？'],
      confidence: 'low',
      cached: false,
      retry_count: 0,
      error_code: null,
      error_message: null,
      created_at: '2026-08-12T00:00:00Z',
      updated_at: '2026-08-12T00:00:01Z',
      completed_at: '2026-08-12T00:00:01Z',
    })
    const wrapper = mount(AIAnalysisPanel, {
      props: { submissionId: 'submission-1' },
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('可能存在边界错误'))
    expect(wrapper.text()).toContain('AI 建议可能不准确')
    expect(wrapper.text()).toContain('O(n)')
    expect(wrapper.text()).toContain('检查下标范围')
    expect(wrapper.html()).not.toContain('object_key')
    expect(wrapper.html()).not.toContain('hidden_input')
  })
})
