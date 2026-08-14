import type { LocationQuery, LocationQueryRaw } from 'vue-router'

export type ProblemDifficulty = 'easy' | 'medium' | 'hard'
export type TrainingCategory =
  | 'single-value'
  | 'single-line-multiple-values'
  | 'multi-line'
  | 'test-cases'
  | 'read-until-eof'
  | 'sentinel'
  | 'array-input'
  | 'string-input'
  | 'matrix-input'
  | 'mixed-input'
  | 'large-input'
  | 'output-format'
  | 'comprehensive'
export type ProblemProgressStatus = 'solved' | 'attempted' | 'unattempted' | 'favorited'
export type ProblemSort = 'newest' | 'oldest' | 'title' | 'difficulty' | 'acceptance'

export interface ProblemTag {
  id: number
  slug: string
  name: string
}

export interface ProblemSummary {
  id: number
  slug: string
  title: string
  difficulty: ProblemDifficulty
  training_category: TrainingCategory
  source: string | null
  accepted_count: number
  submission_count: number
  acceptance_rate: number
  tags: ProblemTag[]
  solved?: boolean
  attempted?: boolean
  attempt_count?: number
  favorited?: boolean
}

export interface ProblemDetail extends ProblemSummary {
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
}

export interface ProblemPage {
  items: ProblemSummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ProblemFilters {
  q: string
  difficulty: ProblemDifficulty | ''
  tag: string
  category: TrainingCategory | ''
  status: ProblemProgressStatus | ''
  sort: ProblemSort
  page: number
  pageSize: number
}

export interface ProblemListParams {
  page: number
  page_size: number
  sort: ProblemSort
  q?: string
  difficulty?: ProblemDifficulty
  tag?: string
  category?: TrainingCategory
  status?: ProblemProgressStatus
}

export const DEFAULT_PROBLEM_FILTERS: Readonly<ProblemFilters> = {
  q: '',
  difficulty: '',
  tag: '',
  category: '',
  status: '',
  sort: 'newest',
  page: 1,
  pageSize: 20,
}

const difficulties: ProblemDifficulty[] = ['easy', 'medium', 'hard']
export const TRAINING_CATEGORY_LABELS: Readonly<Record<TrainingCategory, string>> = {
  'single-value': '单值输入',
  'single-line-multiple-values': '单行多值',
  'multi-line': '多行输入',
  'test-cases': 'T 组测试数据',
  'read-until-eof': '读取到 EOF',
  sentinel: '哨兵结束输入',
  'array-input': '数组输入',
  'string-input': '字符串输入',
  'matrix-input': '矩阵输入',
  'mixed-input': '混合格式输入',
  'large-input': '大数据量输入',
  'output-format': '常见输出格式',
  comprehensive: '综合输入输出',
}
const categories = Object.keys(TRAINING_CATEGORY_LABELS) as TrainingCategory[]
const statuses: ProblemProgressStatus[] = ['solved', 'attempted', 'unattempted', 'favorited']
const sorts: ProblemSort[] = ['newest', 'oldest', 'title', 'difficulty', 'acceptance']
const pageSizes = [10, 20, 50]

function firstQueryValue(value: LocationQuery[string] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0] ?? undefined
  return value ?? undefined
}

function enumValue<T extends string>(value: string | undefined, values: readonly T[], fallback: T): T {
  return value && values.includes(value as T) ? (value as T) : fallback
}

function positiveInteger(value: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(value ?? '', 10)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback
}

export function parseProblemQuery(query: LocationQuery): ProblemFilters {
  const pageSize = positiveInteger(firstQueryValue(query['page_size']), DEFAULT_PROBLEM_FILTERS.pageSize)
  return {
    q: (firstQueryValue(query['q']) ?? '').trim().slice(0, 200),
    difficulty: enumValue(firstQueryValue(query['difficulty']), difficulties, ''),
    tag: (firstQueryValue(query['tag']) ?? '').trim().slice(0, 50),
    category: enumValue(firstQueryValue(query['category']), categories, ''),
    status: enumValue(firstQueryValue(query['status']), statuses, ''),
    sort: enumValue(firstQueryValue(query['sort']), sorts, DEFAULT_PROBLEM_FILTERS.sort),
    page: positiveInteger(firstQueryValue(query['page']), DEFAULT_PROBLEM_FILTERS.page),
    pageSize: pageSizes.includes(pageSize) ? pageSize : DEFAULT_PROBLEM_FILTERS.pageSize,
  }
}

export function serializeProblemFilters(filters: ProblemFilters): LocationQueryRaw {
  const query: LocationQueryRaw = {}
  if (filters.q.trim()) query['q'] = filters.q.trim()
  if (filters.difficulty) query['difficulty'] = filters.difficulty
  if (filters.tag) query['tag'] = filters.tag
  if (filters.category) query['category'] = filters.category
  if (filters.status) query['status'] = filters.status
  if (filters.sort !== DEFAULT_PROBLEM_FILTERS.sort) query['sort'] = filters.sort
  if (filters.page !== DEFAULT_PROBLEM_FILTERS.page) query['page'] = String(filters.page)
  if (filters.pageSize !== DEFAULT_PROBLEM_FILTERS.pageSize) {
    query['page_size'] = String(filters.pageSize)
  }
  return query
}

export function toProblemListParams(filters: ProblemFilters): ProblemListParams {
  const params: ProblemListParams = {
    page: filters.page,
    page_size: filters.pageSize,
    sort: filters.sort,
  }
  if (filters.q.trim()) params.q = filters.q.trim()
  if (filters.difficulty) params.difficulty = filters.difficulty
  if (filters.tag) params.tag = filters.tag
  if (filters.category) params.category = filters.category
  if (filters.status) params.status = filters.status
  return params
}
