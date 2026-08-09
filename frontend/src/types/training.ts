import type { ProblemDifficulty, ProblemPage, ProblemTag } from '@/types/problem'
import type { SubmissionSummary } from '@/types/submission'

export interface FavoriteState {
  problem_id: number
  favorited: boolean
}

export interface SolvedProblem {
  id: number
  slug: string
  title: string
  difficulty: ProblemDifficulty
  attempt_count: number
  first_accepted_at: string
}

export interface DifficultyTrainingStat {
  difficulty: ProblemDifficulty
  total_count: number
  attempted_count: number
  solved_count: number
}

export interface TagTrainingStat {
  tag: ProblemTag
  total_count: number
  attempted_count: number
  solved_count: number
}

export interface TrainingCounters {
  solved_count: number
  submission_count: number
  accepted_count: number
}

export interface TrainingDashboard {
  counters: TrainingCounters
  recent_submissions: SubmissionSummary[]
  solved_problems: SolvedProblem[]
  difficulty_stats: DifficultyTrainingStat[]
  tag_stats: TagTrainingStat[]
}

export type FavoriteProblemPage = ProblemPage
