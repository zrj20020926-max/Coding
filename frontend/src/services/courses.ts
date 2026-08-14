import { http } from '@/services/http'
import type { ExerciseDetail } from '@/types/course'

export class ExerciseNotFoundError extends Error {
  constructor(slug: string) {
    super(`练习 ${slug} 尚未加入公开课程`)
    this.name = 'ExerciseNotFoundError'
  }
}

export async function getExerciseBySlug(slug: string): Promise<ExerciseDetail> {
  try {
    const { data } = await http.get<ExerciseDetail>(`/exercises/${encodeURIComponent(slug)}`)
    return data
  } catch (error) {
    if ((error as { response?: { status?: number } }).response?.status === 404) {
      throw new ExerciseNotFoundError(slug)
    }
    throw error
  }
}
