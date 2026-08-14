import { ref } from 'vue'
import { defineStore } from 'pinia'

import { ExerciseNotFoundError, getExerciseBySlug } from '@/services/courses'
import { getApiErrorMessage } from '@/services/http'
import type { ExerciseDetail } from '@/types/course'

export const useCourseStore = defineStore('courses', () => {
  const exercise = ref<ExerciseDetail | null>(null)
  const exerciseLoading = ref(false)
  const exerciseError = ref('')

  async function loadExercise(slug: string): Promise<void> {
    exerciseLoading.value = true
    exerciseError.value = ''
    exercise.value = null
    try {
      exercise.value = await getExerciseBySlug(slug)
    } catch (error) {
      // Older public problems can still be opened with their problem DTO.
      if (!(error instanceof ExerciseNotFoundError)) {
        exerciseError.value = getApiErrorMessage(error, '课程信息加载失败')
      }
    } finally {
      exerciseLoading.value = false
    }
  }

  function clearExercise(): void {
    exercise.value = null
    exerciseError.value = ''
  }

  return { exercise, exerciseLoading, exerciseError, loadExercise, clearExercise }
})
