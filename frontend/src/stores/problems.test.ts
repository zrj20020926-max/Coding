import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProblemNotFoundError } from '@/services/problems'
import {
  getProblemBySlug,
  getProblems,
  getProblemTags,
  setProblemFavorite,
} from '@/services/problems'
import { useProblemStore } from '@/stores/problems'
import type { ProblemDetail, ProblemPage } from '@/types/problem'

vi.mock('@/services/problems', async (importOriginal) => {
  const original = await importOriginal<Record<string, unknown>>()
  return {
    ...original,
    getProblems: vi.fn(),
    getProblemTags: vi.fn(),
    getProblemBySlug: vi.fn(),
    setProblemFavorite: vi.fn(),
  }
})

const summary = {
  id: 1,
  slug: 'a-plus-b',
  title: 'A+B 问题',
  difficulty: 'easy' as const,
  training_category: 'single-line-multiple-values' as const,
  source: 'CodeArena',
  accepted_count: 80,
  submission_count: 100,
  acceptance_rate: 80,
  tags: [{ id: 1, slug: 'array', name: '数组' }],
  solved: true,
  attempted: true,
  attempt_count: 1,
  favorited: false,
}

const page: ProblemPage = {
  items: [summary],
  total: 1,
  page: 1,
  page_size: 20,
  pages: 1,
}

const detail: ProblemDetail = {
  ...summary,
  description: '描述',
  input_description: '输入',
  output_description: '输出',
  data_constraints: '1 <= n <= 10',
  sample_input: '1 2\n',
  sample_output: '3\n',
  sample_explanation: '一加二等于三。',
  time_limit_ms: 1000,
  memory_limit_mb: 128,
  created_at: '2026-08-08T00:00:00Z',
  updated_at: '2026-08-08T00:00:00Z',
}

describe('problem store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads paginated problems and tags through the service layer', async () => {
    vi.mocked(getProblems).mockResolvedValue(page)
    vi.mocked(getProblemTags).mockResolvedValue(summary.tags)
    const store = useProblemStore()

    await store.loadProblems({ page: 1, page_size: 20, sort: 'newest' })
    await store.loadTags()

    expect(store.items).toEqual([summary])
    expect(store.total).toBe(1)
    expect(store.tags).toEqual(summary.tags)
    expect(store.listLoading).toBe(false)
  })

  it('exposes retryable list errors and a distinct missing-detail state', async () => {
    vi.mocked(getProblems).mockRejectedValue(new Error('network down'))
    vi.mocked(getProblemBySlug).mockRejectedValue(new ProblemNotFoundError('missing'))
    const store = useProblemStore()

    await store.loadProblems({ page: 1, page_size: 20, sort: 'newest' })
    await store.loadProblem('missing')

    expect(store.listError).toBe('训练课程加载失败，请稍后重试')
    expect(store.detailNotFound).toBe(true)
    expect(store.detailError).toContain('missing')
  })

  it('loads a problem detail by slug', async () => {
    vi.mocked(getProblemBySlug).mockResolvedValue(detail)
    const store = useProblemStore()

    await store.loadProblem('a-plus-b')

    expect(store.detail).toEqual(detail)
    expect(store.detailLoading).toBe(false)
  })

  it('updates favorite state in both list and detail', async () => {
    vi.mocked(getProblems).mockResolvedValue(page)
    vi.mocked(getProblemBySlug).mockResolvedValue(detail)
    vi.mocked(setProblemFavorite).mockResolvedValue({ problem_id: 1, favorited: true })
    const store = useProblemStore()

    await store.loadProblems({ page: 1, page_size: 20, sort: 'newest' })
    await store.loadProblem('a-plus-b')
    await store.updateFavorite(1, true)

    expect(setProblemFavorite).toHaveBeenCalledWith(1, true)
    expect(store.items[0]?.favorited).toBe(true)
    expect(store.detail?.favorited).toBe(true)
    expect(store.favoritePendingIds).toEqual([])
  })
})
