import { http } from '@/services/http'
import type {
  CreateSubmissionPayload,
  SubmissionCreated,
  SubmissionDetail,
  SubmissionPage,
  SubmissionListParams,
  SubmissionSummary,
} from '@/types/submission'

export async function createSubmission(
  payload: CreateSubmissionPayload,
  idempotencyKey: string,
): Promise<SubmissionCreated> {
  const { data } = await http.post<SubmissionCreated>('/submissions', payload, {
    headers: { 'Idempotency-Key': idempotencyKey },
  })
  return data
}

export async function getSubmissionStatus(id: string): Promise<SubmissionSummary> {
  const { data } = await http.get<SubmissionSummary>(`/submissions/${id}/status`)
  return data
}

export async function getSubmissionDetail(id: string): Promise<SubmissionDetail> {
  const { data } = await http.get<SubmissionDetail>(`/submissions/${id}`)
  return data
}

export async function getMySubmissions(params: SubmissionListParams): Promise<SubmissionPage> {
  const { data } = await http.get<SubmissionPage>('/submissions', { params })
  return data
}
