import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAIAnalysis, requestAIAnalysis } from '@/services/aiAnalyses'
import { useAIAnalysisStore } from '@/stores/aiAnalyses'
import type { AIAnalysis } from '@/types/aiAnalysis'

vi.mock('@/services/aiAnalyses')

const pending: AIAnalysis = {
  id: 'analysis-1',
  submission_id: 'submission-1',
  status: 'pending',
  failure_reason: null,
  time_complexity: null,
  space_complexity: null,
  suggestions: [],
  guiding_questions: [],
  confidence: null,
  cached: false,
  retry_count: 0,
  error_code: null,
  error_message: null,
  created_at: '2026-08-12T00:00:00Z',
  updated_at: '2026-08-12T00:00:00Z',
  completed_at: null,
}

const completed: AIAnalysis = {
  ...pending,
  status: 'completed',
  failure_reason: '循环边界可能少处理一个元素',
  time_complexity: 'O(n)',
  space_complexity: 'O(1)',
  suggestions: ['检查循环终止条件'],
  guiding_questions: ['n=1 时会发生什么？'],
  confidence: 'medium',
  completed_at: '2026-08-12T00:00:03Z',
}

describe('AI analysis store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(getAIAnalysis).mockReset()
    vi.mocked(requestAIAnalysis).mockReset()
  })

  it('actively requests and polls until a terminal result', async () => {
    vi.mocked(requestAIAnalysis).mockResolvedValue({
      analysis: pending,
      quota: { limit: 5, remaining: 4, reset_after_seconds: 60 },
      reused: false,
    })
    vi.mocked(getAIAnalysis).mockResolvedValue(completed)
    const store = useAIAnalysisStore()

    await store.request('submission-1')
    await vi.waitFor(() => expect(store.analysis).toEqual(completed))

    expect(requestAIAnalysis).toHaveBeenCalledTimes(1)
    expect(getAIAnalysis).toHaveBeenCalledWith('submission-1')
    expect(store.quota?.remaining).toBe(4)
  })

  it('treats no existing analysis as an empty initial state', async () => {
    vi.mocked(getAIAnalysis).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: { code: 'AI_ANALYSIS_NOT_FOUND' } } },
    })
    const store = useAIAnalysisStore()

    await store.load('submission-1')

    expect(store.analysis).toBeNull()
    expect(store.error).toBe('')
  })

  it('shows an explicit safe message when the provider is not configured', async () => {
    vi.mocked(getAIAnalysis).mockResolvedValue({
      ...pending,
      status: 'failed',
      error_code: 'AI_PROVIDER_NOT_CONFIGURED',
      error_message: 'AI analysis is not configured',
    })
    const store = useAIAnalysisStore()

    await store.load('submission-1')

    expect(store.error).toBe('AI 分析暂未配置')
  })
})
