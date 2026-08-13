import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createSubmission,
  getMySubmissions,
  getSubmissionDetail,
  getSubmissionStatus,
} from '@/services/submissions'
import { activeSubmissionKey, useSubmissionStore } from '@/stores/submissions'
import type {
  SubmissionCreated,
  SubmissionDetail,
  SubmissionSummary,
} from '@/types/submission'

vi.mock('@/services/submissions')

const pending: SubmissionCreated = {
  id: 'submission-1',
  problem: { id: 7, slug: 'a-plus-b', title: 'A+B' },
  language: { id: 1, slug: 'python', display_name: 'Python', version: '3.12' },
  status: 'Pending',
  mode: 'sample',
  time_used_ms: null,
  memory_used_kb: null,
  passed_case_count: 0,
  total_case_count: 0,
  score: '0.00',
  judged_at: null,
  created_at: '2026-08-09T00:00:00Z',
  updated_at: '2026-08-09T00:00:00Z',
  idempotent_replay: false,
}

const accepted: SubmissionSummary = {
  ...pending,
  status: 'Accepted',
  time_used_ms: 12,
  memory_used_kb: 4096,
  passed_case_count: 1,
  total_case_count: 1,
  judged_at: '2026-08-09T00:00:01Z',
}

const detail: SubmissionDetail = {
  ...accepted,
  source_code: 'print(3)',
  compiler_output: null,
  error_message: null,
  sample_output: '3\n',
}

describe('submission store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(createSubmission).mockReset()
    vi.mocked(getSubmissionStatus).mockReset()
    vi.mocked(getSubmissionDetail).mockReset()
    vi.mocked(getMySubmissions).mockReset()
  })

  it('submits once during duplicate clicks and forwards sample mode', async () => {
    let resolveSubmission!: (value: SubmissionCreated) => void
    vi.mocked(createSubmission).mockImplementation(
      () => new Promise((resolve) => { resolveSubmission = resolve }),
    )
    vi.mocked(getSubmissionStatus).mockResolvedValue(accepted)
    vi.mocked(getSubmissionDetail).mockResolvedValue(detail)
    const store = useSubmissionStore()
    const payload = {
      problem_id: 7,
      language: 'python',
      source_code: 'print(3)',
      mode: 'sample' as const,
    }

    const first = store.submitAndPoll(payload, 'user-1')
    const second = store.submitAndPoll(payload, 'user-1')

    expect(createSubmission).toHaveBeenCalledTimes(1)
    expect(vi.mocked(createSubmission).mock.calls[0]?.[0].mode).toBe('sample')
    expect(vi.mocked(createSubmission).mock.calls[0]?.[1]).toBeTruthy()
    resolveSubmission(pending)
    await Promise.all([first, second])
    await vi.waitFor(() => expect(store.currentDetail).toEqual(detail))
    expect(store.polling).toBe(false)
  })

  it('stops at a terminal status and removes persisted active state', async () => {
    vi.mocked(createSubmission).mockResolvedValue(pending)
    vi.mocked(getSubmissionStatus).mockResolvedValue(accepted)
    vi.mocked(getSubmissionDetail).mockResolvedValue(detail)
    const store = useSubmissionStore()

    await store.submitAndPoll(
      { problem_id: 7, language: 'python', source_code: 'print(3)', mode: 'sample' },
      'user-1',
    )
    await vi.waitFor(() => expect(store.currentDetail).toEqual(detail))

    expect(getSubmissionStatus).toHaveBeenCalledTimes(1)
    expect(store.current?.status).toBe('Accepted')
    expect(store.polling).toBe(false)
    expect(localStorage.getItem(activeSubmissionKey('user-1', 7))).toBeNull()
  })

  it('pauses while offline and resumes the persisted submission', async () => {
    const online = vi.spyOn(navigator, 'onLine', 'get')
    online.mockReturnValue(false)
    const store = useSubmissionStore()
    localStorage.setItem(
      activeSubmissionKey('user-1', 7),
      JSON.stringify({ id: pending.id, startedAt: Date.now() }),
    )

    expect(store.resumeActive('user-1', 7)).toBe(true)
    await vi.waitFor(() => expect(store.polling).toBe(false))
    expect(getSubmissionStatus).not.toHaveBeenCalled()
    expect(store.pollError).not.toBe('')

    online.mockReturnValue(true)
    vi.mocked(getSubmissionStatus).mockResolvedValue(accepted)
    vi.mocked(getSubmissionDetail).mockResolvedValue(detail)
    store.resumePolling('user-1', 7)
    await vi.waitFor(() => expect(store.currentDetail).toEqual(detail))
    expect(store.polling).toBe(false)
  })

  it('loads paginated personal history through the service layer', async () => {
    vi.mocked(getMySubmissions).mockResolvedValue({
      items: [accepted], total: 1, page: 1, page_size: 20, pages: 1,
    })
    const store = useSubmissionStore()

    await store.loadHistory(1, 20, {
      problem_id: 7,
      language: 'python',
      status: 'Accepted',
      mode: 'sample',
    })

    expect(getMySubmissions).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      problem_id: 7,
      language: 'python',
      status: 'Accepted',
      mode: 'sample',
    })
    expect(store.history).toEqual([accepted])
    expect(store.historyLoading).toBe(false)
  })
})
