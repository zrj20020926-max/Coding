import type { Discussion, DiscussionComment, ReviewStatus } from '@/types/content'
import type { ProblemDifficulty, ProblemSummary, ProblemTag, TrainingCategory } from '@/types/problem'

export type ProblemVisibility = 'draft' | 'public' | 'private'
export type AdminProblemSort = 'created_desc' | 'created_asc' | 'updated_desc' | 'updated_asc'
export type CheckerType = 'exact' | 'token' | 'float'
export type TestSetStatus = 'draft' | 'validating' | 'ready' | 'active' | 'inactive' | 'invalid'

export interface AdminProblem extends ProblemSummary {
  description: string
  input_description: string
  output_description: string
  data_constraints: string
  sample_input: string
  sample_output: string
  sample_explanation: string
  starter_code_v8: string | null
  starter_code_nodejs: string | null
  time_limit_ms: number
  memory_limit_mb: number
  created_at: string
  updated_at: string
  visibility: ProblemVisibility
  created_by: string | null
}

export interface AdminProblemPage {
  items: AdminProblem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface AdminProblemQuery {
  q?: string
  difficulty?: ProblemDifficulty
  status?: ProblemVisibility
  tag?: string
  page: number
  page_size: number
  sort: AdminProblemSort
}

export interface ProblemWritePayload {
  slug: string
  title: string
  description: string
  difficulty: ProblemDifficulty
  training_category: TrainingCategory
  input_description: string
  output_description: string
  data_constraints: string
  sample_input: string
  sample_output: string
  sample_explanation: string
  starter_code_v8: string | null
  starter_code_nodejs: string | null
  time_limit_ms: number
  memory_limit_mb: number
  source: string | null
  tag_slugs: string[]
}

export interface TestCaseMetadata {
  id: string
  sequence: number
  score: string
  input_size_bytes: number
  output_size_bytes: number
}

export interface TestSetMetadata {
  id: string
  problem_id: number
  version: number
  status: TestSetStatus
  checker_type: CheckerType
  absolute_tolerance: string | null
  relative_tolerance: string | null
  case_count: number
  total_score: string
  created_by: string | null
  created_at: string
  activated_at: string | null
  submission_reference_count: number
  cases: TestCaseMetadata[]
}

export interface TestSetIssue {
  code: string
  message: string
  sequence?: number
}

export interface TestSetValidation {
  test_set: TestSetMetadata
  issues: TestSetIssue[]
}

export interface ProblemReadiness {
  ready: boolean
  active_test_set?: TestSetMetadata | null
  issues: TestSetIssue[]
}

export interface AdminCollectionSummary {
  id: number
  slug: string
  title: string
  description: string | null
  company: string | null
  cover_url: string | null
  problem_count: number
  is_public: boolean
}

export interface AdminCollection extends AdminCollectionSummary {
  problems: Array<{ sequence: number; problem: ProblemSummary }>
  page: number
  page_size: number
  pages: number
}

export interface AdminCollectionPage {
  items: AdminCollectionSummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface CollectionWritePayload {
  slug: string
  title: string
  description: string | null
  company: string | null
  cover_url: string | null
  problem_ids: number[]
}

export interface DailyChallengeAdmin {
  challenge_date: string
  timezone: string
  problem: ProblemSummary
}

export interface DailyChallengePage {
  items: DailyChallengeAdmin[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ModerationQueueItem {
  target_type: 'discussion' | 'comment'
  target_id: number
  discussion_id: number
  problem_id: number
  author: { id: string; nickname: string; avatar_url: string | null } | null
  title: string | null
  content: string
  review_status: ReviewStatus
  is_pinned: boolean
  is_locked: boolean
  created_at: string
}

export interface ModerationQueuePage {
  items: ModerationQueueItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ContentReport {
  id: number
  reporter_id: string | null
  discussion_id: number | null
  comment_id: number | null
  reason: string
  status: 'pending' | 'resolved' | 'dismissed'
  created_at: string
}

export interface ContentReportPage {
  items: ContentReport[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface RejudgeTask {
  id: string
  mode: 'single' | 'batch'
  problem_id: number
  test_set_id: string
  status: 'queued' | 'running' | 'completed' | 'completed_with_errors'
  total_count: number
  queued_count: number
  running_count: number
  success_count: number
  failed_count: number
  created_at: string
}

export interface RejudgeTaskPage {
  items: RejudgeTask[]
  total: number
  page: number
  page_size: number
  pages: number
}

export type ModeratedContent = Discussion | DiscussionComment

export interface AdminReferenceData {
  tags: ProblemTag[]
}
