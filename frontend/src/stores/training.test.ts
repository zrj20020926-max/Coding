import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { setProblemFavorite } from '@/services/problems'
import { getFavoriteProblems, getTrainingDashboard } from '@/services/training'
import { useTrainingStore } from '@/stores/training'
import type { ProblemSummary } from '@/types/problem'
import type { TrainingDashboard } from '@/types/training'

vi.mock('@/services/problems', () => ({ setProblemFavorite: vi.fn() }))
vi.mock('@/services/training', () => ({
  getFavoriteProblems: vi.fn(),
  getTrainingDashboard: vi.fn(),
}))

const problem: ProblemSummary = {
  id: 7,
  slug: 'a-plus-b',
  title: 'A+B 问题',
  difficulty: 'easy',
  training_category: 'single-line-multiple-values',
  source: null,
  accepted_count: 8,
  submission_count: 10,
  acceptance_rate: 80,
  tags: [],
  solved: true,
  attempted: true,
  attempt_count: 1,
  favorited: true,
}

const dashboard: TrainingDashboard = {
  counters: { solved_count: 1, submission_count: 2, accepted_count: 1 },
  recent_submissions: [],
  solved_problems: [],
  difficulty_stats: [
    { difficulty: 'easy', total_count: 10, attempted_count: 2, solved_count: 1 },
  ],
  tag_stats: [],
}

describe('training store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('loads dashboard counters and calculates acceptance rate', async () => {
    vi.mocked(getTrainingDashboard).mockResolvedValue(dashboard)
    const store = useTrainingStore()

    await store.loadDashboard()

    expect(store.dashboard).toEqual(dashboard)
    expect(store.acceptanceRate).toBe(50)
    expect(store.dashboardError).toBe('')
  })

  it('loads and removes an owned favorite', async () => {
    vi.mocked(getFavoriteProblems).mockResolvedValue({
      items: [problem],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    })
    vi.mocked(setProblemFavorite).mockResolvedValue({ problem_id: 7, favorited: false })
    const store = useTrainingStore()

    await store.loadFavorites(1, 20)
    await store.removeFavorite(7)

    expect(setProblemFavorite).toHaveBeenCalledWith(7, false)
    expect(store.favorites).toEqual([])
    expect(store.favoritesTotal).toBe(0)
    expect(store.favoritePendingIds).toEqual([])
  })
})
