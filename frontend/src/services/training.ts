import { http } from '@/services/http'
import type { FavoriteProblemPage, TrainingDashboard } from '@/types/training'

export async function getFavoriteProblems(
  page: number,
  pageSize: number,
): Promise<FavoriteProblemPage> {
  const { data } = await http.get<FavoriteProblemPage>('/favorites', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function getTrainingDashboard(): Promise<TrainingDashboard> {
  const { data } = await http.get<TrainingDashboard>('/users/me/training')
  return data
}
