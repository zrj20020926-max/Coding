export type SubmissionMode = 'sample' | 'custom' | 'judge'
export type SubmissionStatus =
  | 'Pending'
  | 'Compiling'
  | 'Running'
  | 'Accepted'
  | 'Wrong Answer'
  | 'Compile Error'
  | 'Runtime Error'
  | 'Time Limit Exceeded'
  | 'Memory Limit Exceeded'
  | 'Output Limit Exceeded'
  | 'System Error'

export interface SubmissionProblem {
  id: number
  slug: string
  title: string
}

export interface SubmissionLanguage {
  id: number
  slug: string
  display_name: string
  version: string
}

export interface SubmissionSummary {
  id: string
  problem: SubmissionProblem
  language: SubmissionLanguage
  status: SubmissionStatus
  mode: SubmissionMode
  time_used_ms: number | null
  memory_used_kb: number | null
  passed_case_count: number
  total_case_count: number
  score: string
  judged_at: string | null
  created_at: string
  updated_at: string
}

export interface SubmissionCreated extends SubmissionSummary {
  idempotent_replay: boolean
}

export interface SubmissionDetail extends SubmissionSummary {
  source_code: string
  compiler_output: string | null
  error_message: string | null
  sample_output: string | null
}

export interface SubmissionPage {
  items: SubmissionSummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface SubmissionHistoryFilters {
  problem_id?: number
  language?: string
  status?: SubmissionStatus
  mode?: SubmissionMode
}

export interface SubmissionListParams extends SubmissionHistoryFilters {
  page: number
  page_size: number
}

export interface CreateSubmissionPayload {
  problem_id: number
  language: string
  source_code: string
  mode: SubmissionMode
  custom_input?: string
}

export const TERMINAL_SUBMISSION_STATUSES: ReadonlySet<SubmissionStatus> = new Set([
  'Accepted',
  'Wrong Answer',
  'Compile Error',
  'Runtime Error',
  'Time Limit Exceeded',
  'Memory Limit Exceeded',
  'Output Limit Exceeded',
  'System Error',
])

export function isTerminalSubmission(status: SubmissionStatus): boolean {
  return TERMINAL_SUBMISSION_STATUSES.has(status)
}
