import { ref } from 'vue'
import { defineStore } from 'pinia'

import { getAIAnalysis, requestAIAnalysis } from '@/services/aiAnalyses'
import { getApiErrorCode, getApiErrorMessage } from '@/services/http'
import type { AIAnalysis, AIQuota } from '@/types/aiAnalysis'

const POLL_INTERVAL_MS = 1800
const POLL_TIMEOUT_MS = 90_000

function analysisFailureMessage(code: string | null, fallback: string | null): string {
  if (code === 'AI_PROVIDER_NOT_CONFIGURED') return 'AI 输入输出诊断暂未配置'
  return fallback || 'AI 输入输出诊断暂时不可用，请稍后重试'
}

export const useAIAnalysisStore = defineStore('ai-analysis', () => {
  const analysis = ref<AIAnalysis | null>(null)
  const quota = ref<AIQuota | null>(null)
  const loading = ref(false)
  const requesting = ref(false)
  const error = ref('')
  let timer: ReturnType<typeof setTimeout> | null = null
  let generation = 0

  function stopPolling(): void {
    generation += 1
    if (timer !== null) clearTimeout(timer)
    timer = null
  }

  function startPolling(submissionId: string, startedAt = Date.now()): void {
    stopPolling()
    const currentGeneration = ++generation
    const poll = async (): Promise<void> => {
      if (currentGeneration !== generation) return
      if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
        error.value = 'AI 输入输出诊断等待超时，请稍后刷新重试'
        return
      }
      try {
        const result = await getAIAnalysis(submissionId)
        if (currentGeneration !== generation) return
        analysis.value = result
        error.value = ''
        if (result.status === 'failed') {
          error.value = analysisFailureMessage(result.error_code, result.error_message)
        }
        if (result.status === 'pending' || result.status === 'running') {
          timer = setTimeout(() => void poll(), POLL_INTERVAL_MS)
        }
      } catch (reason) {
        if (currentGeneration !== generation) return
        error.value = getApiErrorMessage(reason, 'AI 输入输出诊断状态加载失败')
        timer = setTimeout(() => void poll(), POLL_INTERVAL_MS * 2)
      }
    }
    void poll()
  }

  async function load(submissionId: string): Promise<void> {
    stopPolling()
    analysis.value = null
    error.value = ''
    loading.value = true
    try {
      analysis.value = await getAIAnalysis(submissionId)
      if (analysis.value.status === 'failed') {
        error.value = analysisFailureMessage(
          analysis.value.error_code,
          analysis.value.error_message,
        )
      }
      if (analysis.value.status === 'pending' || analysis.value.status === 'running') {
        startPolling(submissionId)
      }
    } catch (reason) {
      if (getApiErrorCode(reason) !== 'AI_ANALYSIS_NOT_FOUND') {
        error.value = getApiErrorMessage(reason, 'AI 输入输出诊断加载失败')
      }
    } finally {
      loading.value = false
    }
  }

  async function request(submissionId: string): Promise<void> {
    if (requesting.value) return
    requesting.value = true
    error.value = ''
    try {
      const result = await requestAIAnalysis(submissionId)
      analysis.value = result.analysis
      quota.value = result.quota
      if (analysis.value.status === 'failed') {
        error.value = analysisFailureMessage(
          analysis.value.error_code,
          analysis.value.error_message,
        )
      }
      if (analysis.value.status === 'pending' || analysis.value.status === 'running') {
        startPolling(submissionId)
      }
    } catch (reason) {
      const code = getApiErrorCode(reason)
      error.value = analysisFailureMessage(
        code ?? null,
        getApiErrorMessage(reason, 'AI 输入输出诊断请求失败，请稍后重试'),
      )
      if (code === 'AI_PROVIDER_NOT_CONFIGURED') stopPolling()
    } finally {
      requesting.value = false
    }
  }

  return { analysis, quota, loading, requesting, error, load, request, stopPolling }
})
