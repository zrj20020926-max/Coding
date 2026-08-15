export type AIAnalysisStatus = 'pending' | 'running' | 'completed' | 'failed'
export type AIConfidence = 'low' | 'medium' | 'high'

export interface AIDiagnosticFinding {
  detected: boolean
  summary: string
}

export interface AIAnalysis {
  id: string
  submission_id: string
  status: AIAnalysisStatus
  runtime_mismatch: AIDiagnosticFinding | null
  input_reading_issue: AIDiagnosticFinding | null
  line_parsing_issue: AIDiagnosticFinding | null
  token_parsing_issue: AIDiagnosticFinding | null
  whitespace_issue: AIDiagnosticFinding | null
  eof_issue: AIDiagnosticFinding | null
  numeric_issue: AIDiagnosticFinding | null
  output_format_issue: AIDiagnosticFinding | null
  performance_issue: AIDiagnosticFinding | null
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
