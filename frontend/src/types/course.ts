import type { ProblemDifficulty, TrainingCategory } from '@/types/problem'

export interface ExerciseProgress {
  status: 'not_started' | 'attempted' | 'completed'
  selected_runtime: string | null
  attempt_count: number
  v8_attempt_count: number
  nodejs_attempt_count: number
  v8_completed: boolean
  nodejs_completed: boolean
  any_runtime_completed: boolean
  both_runtimes_completed: boolean
  first_completed_at: string | null
  last_attempted_at: string | null
}

export interface ExerciseDetail {
  id: number
  problem_id: number
  slug: string
  title: string
  difficulty: ProblemDifficulty
  training_category: TrainingCategory
  chapter_slug: string
  chapter_title: string
  course_slug: string
  course_title: string
  sort_order: number
  estimated_minutes: number
  prerequisite_slugs: string[]
  progress?: ExerciseProgress
  learning_objectives: string
  v8_notes: string
  nodejs_notes: string
  common_mistakes: string[]
  starter_code_v8: string
  starter_code_nodejs: string
  description: string
  input_description: string
  output_description: string
  data_constraints: string
  sample_input: string
  sample_output: string
  sample_explanation: string
  time_limit_ms: number
  memory_limit_mb: number
}
