import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getApiErrorMessage } from '@/services/http'
import { setProblemFavorite } from '@/services/problems'
import { getFavoriteProblems, getTrainingDashboard } from '@/services/training'
import type { ProblemSummary } from '@/types/problem'
import type { TrainingDashboard } from '@/types/training'

export const useTrainingStore = defineStore('training', () => {
  const dashboard = ref<TrainingDashboard | null>(null)
  const dashboardLoading = ref(false)
  const dashboardError = ref('')
  const favorites = ref<ProblemSummary[]>([])
  const favoritesTotal = ref(0)
  const favoritesLoading = ref(false)
  const favoritesError = ref('')
  const favoritePendingIds = ref<number[]>([])

  const acceptanceRate = computed(() => {
    const counters = dashboard.value?.counters
    if (!counters?.submission_count) return 0
    return (counters.accepted_count / counters.submission_count) * 100
  })

  async function loadDashboard(): Promise<void> {
    dashboardLoading.value = true
    dashboardError.value = ''
    try {
      dashboard.value = await getTrainingDashboard()
    } catch (error) {
      dashboard.value = null
      dashboardError.value = getApiErrorMessage(error, '训练统计加载失败，请稍后重试')
    } finally {
      dashboardLoading.value = false
    }
  }

  async function loadFavorites(page: number, pageSize: number): Promise<void> {
    favoritesLoading.value = true
    favoritesError.value = ''
    try {
      const result = await getFavoriteProblems(page, pageSize)
      favorites.value = result.items
      favoritesTotal.value = result.total
    } catch (error) {
      favorites.value = []
      favoritesTotal.value = 0
      favoritesError.value = getApiErrorMessage(error, '收藏题目加载失败，请稍后重试')
    } finally {
      favoritesLoading.value = false
    }
  }

  async function removeFavorite(problemId: number): Promise<void> {
    if (favoritePendingIds.value.includes(problemId)) return
    favoritePendingIds.value = [...favoritePendingIds.value, problemId]
    try {
      await setProblemFavorite(problemId, false)
      favorites.value = favorites.value.filter((problem) => problem.id !== problemId)
      favoritesTotal.value = Math.max(0, favoritesTotal.value - 1)
    } finally {
      favoritePendingIds.value = favoritePendingIds.value.filter((id) => id !== problemId)
    }
  }

  return {
    dashboard,
    dashboardLoading,
    dashboardError,
    favorites,
    favoritesTotal,
    favoritesLoading,
    favoritesError,
    favoritePendingIds,
    acceptanceRate,
    loadDashboard,
    loadFavorites,
    removeFavorite,
  }
})
