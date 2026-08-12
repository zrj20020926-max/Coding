import { http } from '@/services/http'
import type { AIAnalysis, AIAnalysisTriggered } from '@/types/aiAnalysis'

export async function requestAIAnalysis(submissionId: string): Promise<AIAnalysisTriggered> {
  const { data } = await http.post<AIAnalysisTriggered>(
    `/submissions/${submissionId}/ai-analysis`,
  )
  return data
}

export async function getAIAnalysis(submissionId: string): Promise<AIAnalysis> {
  const { data } = await http.get<AIAnalysis>(`/submissions/${submissionId}/ai-analysis`)
  return data
}
