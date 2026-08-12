export type AIAnalysisStatus = 'pending' | 'running' | 'completed' | 'failed'
export type AIConfidence = 'low' | 'medium' | 'high'

export interface AIAnalysis {
  id: string
  submission_id: string
  status: AIAnalysisStatus
  failure_reason: string | null
  time_complexity: string | null
  space_complexity: string | null
  suggestions: string[]
  guiding_questions: string[]
  confidence: AIConfidence | null
  cached: boolean
  retry_count: number
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface AIQuota {
  limit: number
  remaining: number
  reset_after_seconds: number
}

export interface AIAnalysisTriggered {
  analysis: AIAnalysis
  quota: AIQuota | null
  reused: boolean
}
