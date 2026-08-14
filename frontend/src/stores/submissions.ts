import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getApiErrorMessage } from '@/services/http'
import {
  createSubmission,
  getMySubmissions,
  getSubmissionDetail,
  getSubmissionStatus,
} from '@/services/submissions'
import { isTerminalSubmission } from '@/types/submission'
import type {
  CreateSubmissionPayload,
  SubmissionDetail,
  SubmissionHistoryFilters,
  SubmissionSummary,
} from '@/types/submission'

const MAX_POLL_DURATION_MS = 3 * 60 * 1000
const VISIBLE_POLL_INTERVAL_MS = 1200
const HIDDEN_POLL_INTERVAL_MS = 8000

interface ActiveSubmission {
  id: string
  startedAt: number
}

interface PendingRequest {
  requestBody: string
  key: string
}

function randomKey(): string {
  return typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function activeSubmissionKey(userId: string, problemId: number): string {
  return `codearena.active-submission.${userId}.${problemId}`
}

function pendingRequestKey(
  userId: string,
  problemId: number,
  mode: CreateSubmissionPayload['mode'],
): string {
  return `codearena.pending-request.${userId}.${problemId}.${mode}`
}

function parseStored<T>(value: string | null): T | null {
  if (!value) return null
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

export const useSubmissionStore = defineStore('submissions', () => {
  const current = ref<SubmissionSummary | null>(null)
  const currentDetail = ref<SubmissionDetail | null>(null)
  const submitting = ref(false)
  const polling = ref(false)
  const pollTimedOut = ref(false)
  const pollError = ref('')
  const history = ref<SubmissionSummary[]>([])
  const historyTotal = ref(0)
  const historyPages = ref(0)
  const historyLoading = ref(false)
  const historyError = ref('')
  const detail = ref<SubmissionDetail | null>(null)
  const detailLoading = ref(false)
  const detailError = ref('')
  let timer: ReturnType<typeof setTimeout> | null = null
  let pollGeneration = 0
  let historyRequestId = 0

  const busy = computed(() => submitting.value || polling.value)

  function stopPolling(): void {
    pollGeneration += 1
    polling.value = false
    if (timer !== null) clearTimeout(timer)
    timer = null
  }

  function rememberActive(userId: string, problemId: number, value: ActiveSubmission): void {
    localStorage.setItem(activeSubmissionKey(userId, problemId), JSON.stringify(value))
  }

  function forgetActive(userId: string, problemId: number): void {
    localStorage.removeItem(activeSubmissionKey(userId, problemId))
  }

  function schedulePoll(callback: () => void, delay: number): void {
    timer = setTimeout(callback, delay)
  }

  function nextPollDelay(): number {
    return typeof document !== 'undefined' && document.visibilityState === 'hidden'
      ? HIDDEN_POLL_INTERVAL_MS
      : VISIBLE_POLL_INTERVAL_MS
  }

  function startPolling(
    submissionId: string,
    userId: string,
    problemId: number,
    startedAt = Date.now(),
  ): void {
    stopPolling()
    const generation = ++pollGeneration
    polling.value = true
    pollTimedOut.value = false
    pollError.value = ''
    rememberActive(userId, problemId, { id: submissionId, startedAt })

    const poll = async (): Promise<void> => {
      if (generation !== pollGeneration) return
      if (!navigator.onLine) {
        pollError.value = '网络已断开，恢复连接后将继续查询判题状态'
        polling.value = false
        return
      }
      if (Date.now() - startedAt >= MAX_POLL_DURATION_MS) {
        pollTimedOut.value = true
        pollError.value = '等待判题结果超时，可点击继续查询'
        polling.value = false
        return
      }
      try {
        const status = await getSubmissionStatus(submissionId)
        if (generation !== pollGeneration) return
        current.value = status
        pollError.value = ''
        if (isTerminalSubmission(status.status)) {
          currentDetail.value = await getSubmissionDetail(submissionId)
          forgetActive(userId, problemId)
          polling.value = false
          timer = null
          return
        }
        schedulePoll(() => void poll(), nextPollDelay())
      } catch (error) {
        if (generation !== pollGeneration) return
        pollError.value = getApiErrorMessage(error, '判题状态查询失败，稍后自动重试')
        schedulePoll(() => void poll(), 2500)
      }
    }

    void poll()
  }

  async function submitAndPoll(
    payload: CreateSubmissionPayload,
    userId: string,
  ): Promise<void> {
    if (busy.value) return
    submitting.value = true
    pollError.value = ''
    pollTimedOut.value = false
    const storageKey = pendingRequestKey(userId, payload.problem_id, payload.mode)
    const stored = parseStored<PendingRequest>(localStorage.getItem(storageKey))
    const requestBody = JSON.stringify(payload)
    const pending = stored?.requestBody === requestBody
      ? stored
      : { requestBody, key: randomKey() }
    localStorage.setItem(storageKey, JSON.stringify(pending))
    try {
      const created = await createSubmission(payload, pending.key)
      localStorage.removeItem(storageKey)
      current.value = created
      currentDetail.value = null
      startPolling(created.id, userId, payload.problem_id)
    } catch (error) {
      pollError.value = getApiErrorMessage(error, '提交失败，请检查网络后重试')
      throw error
    } finally {
      submitting.value = false
    }
  }

  function resumeActive(userId: string, problemId: number): boolean {
    const active = parseStored<ActiveSubmission>(
      localStorage.getItem(activeSubmissionKey(userId, problemId)),
    )
    if (!active?.id || !Number.isFinite(active.startedAt)) return false
    startPolling(active.id, userId, problemId, active.startedAt)
    return true
  }

  function resumePolling(userId: string, problemId: number): void {
    const active = parseStored<ActiveSubmission>(
      localStorage.getItem(activeSubmissionKey(userId, problemId)),
    )
    if (current.value) {
      const startedAt = active?.id === current.value.id ? active.startedAt : Date.now()
      startPolling(current.value.id, userId, problemId, startedAt)
      return
    }
    resumeActive(userId, problemId)
  }

  async function loadHistory(
    page: number,
    pageSize: number,
    filters: SubmissionHistoryFilters = {},
  ): Promise<void> {
    const requestId = ++historyRequestId
    historyLoading.value = true
    historyError.value = ''
    try {
      const params = {
        page,
        page_size: pageSize,
        ...filters,
      }
      const response = await getMySubmissions(params)
      if (requestId !== historyRequestId) return
      history.value = response.items
      historyTotal.value = response.total
      historyPages.value = response.pages
    } catch (error) {
      if (requestId !== historyRequestId) return
      history.value = []
      historyTotal.value = 0
      historyPages.value = 0
      historyError.value = getApiErrorMessage(error, '提交记录加载失败')
    } finally {
      if (requestId === historyRequestId) historyLoading.value = false
    }
  }

  async function loadDetail(id: string): Promise<void> {
    detailLoading.value = true
    detailError.value = ''
    detail.value = null
    try {
      detail.value = await getSubmissionDetail(id)
    } catch (error) {
      detailError.value = getApiErrorMessage(error, '提交详情加载失败')
    } finally {
      detailLoading.value = false
    }
  }

  return {
    current,
    currentDetail,
    submitting,
    polling,
    pollTimedOut,
    pollError,
    busy,
    history,
    historyTotal,
    historyPages,
    historyLoading,
    historyError,
    detail,
    detailLoading,
    detailError,
    submitAndPoll,
    startPolling,
    stopPolling,
    resumeActive,
    resumePolling,
    loadHistory,
    loadDetail,
  }
})
