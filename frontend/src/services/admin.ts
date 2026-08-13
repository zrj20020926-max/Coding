import { http } from '@/services/http'
import type {
  AdminCollection,
  AdminCollectionPage,
  AdminProblem,
  AdminProblemPage,
  AdminProblemQuery,
  CollectionWritePayload,
  ContentReport,
  ContentReportPage,
  DailyChallengeAdmin,
  DailyChallengePage,
  ModeratedContent,
  ModerationQueuePage,
  ProblemReadiness,
  ProblemWritePayload,
  RejudgeTask,
  RejudgeTaskPage,
  TestSetMetadata,
  TestSetValidation,
} from '@/types/admin'
import type { Discussion } from '@/types/content'

export async function listAdminProblems(query: AdminProblemQuery): Promise<AdminProblemPage> {
  return (await http.get<AdminProblemPage>('/admin/problems', { params: query })).data
}

export async function getAdminProblem(id: number): Promise<AdminProblem> {
  return (await http.get<AdminProblem>(`/admin/problems/${id}`)).data
}

export async function createAdminProblem(payload: ProblemWritePayload): Promise<AdminProblem> {
  return (await http.post<AdminProblem>('/admin/problems', { ...payload, visibility: 'draft' })).data
}

export async function updateAdminProblem(
  id: number,
  payload: Partial<ProblemWritePayload>,
): Promise<AdminProblem> {
  return (await http.patch<AdminProblem>(`/admin/problems/${id}`, payload)).data
}

export async function publishAdminProblem(id: number): Promise<AdminProblem> {
  return (await http.post<AdminProblem>(`/admin/problems/${id}/publish`)).data
}

export async function offlineAdminProblem(id: number): Promise<AdminProblem> {
  return (await http.post<AdminProblem>(`/admin/problems/${id}/offline`)).data
}

export async function getProblemReadiness(id: number): Promise<ProblemReadiness> {
  return (await http.get<ProblemReadiness>(`/admin/problems/${id}/readiness`)).data
}

export async function listProblemTestSets(problemId: number): Promise<TestSetMetadata[]> {
  return (await http.get<TestSetMetadata[]>(`/admin/problems/${problemId}/test-sets`)).data
}

export async function createProblemTestSet(
  problemId: number,
  payload: {
    checker_type: 'exact' | 'token' | 'float'
    absolute_tolerance?: number
    relative_tolerance?: number
  },
): Promise<TestSetMetadata> {
  return (await http.post<TestSetMetadata>(`/admin/problems/${problemId}/test-sets`, payload)).data
}

export async function uploadTestSetArchive(
  testSetId: string,
  file: File,
  onProgress?: (percentage: number) => void,
): Promise<TestSetMetadata> {
  const form = new FormData()
  form.append('archive', file)
  const response = await http.post<{ test_set: TestSetMetadata; uploaded_count: number }>(
    `/admin/problems/test-sets/${testSetId}/cases/upload`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120_000,
      onUploadProgress: (event) => {
        if (event.total) onProgress?.(Math.round((event.loaded * 100) / event.total))
      },
    },
  )
  return response.data.test_set
}

export async function validateTestSet(id: string): Promise<TestSetValidation> {
  return (await http.post<TestSetValidation>(`/admin/problems/test-sets/${id}/validate`)).data
}

export async function activateTestSet(id: string): Promise<TestSetMetadata> {
  return (await http.post<TestSetMetadata>(`/admin/problems/test-sets/${id}/activate`)).data
}

export async function deactivateTestSet(id: string): Promise<TestSetMetadata> {
  return (await http.post<TestSetMetadata>(`/admin/problems/test-sets/${id}/deactivate`)).data
}

export async function listAdminCollections(page: number, pageSize = 20): Promise<AdminCollectionPage> {
  return (
    await http.get<AdminCollectionPage>('/admin/collections', { params: { page, page_size: pageSize } })
  ).data
}

export async function getAdminCollection(id: number): Promise<AdminCollection> {
  return (await http.get<AdminCollection>(`/admin/collections/${id}`)).data
}

export async function createAdminCollection(payload: CollectionWritePayload): Promise<AdminCollection> {
  return (await http.post<AdminCollection>('/admin/collections', payload)).data
}

export async function updateAdminCollection(
  id: number,
  payload: Partial<Omit<CollectionWritePayload, 'problem_ids'>>,
): Promise<AdminCollection> {
  return (await http.patch<AdminCollection>(`/admin/collections/${id}`, payload)).data
}

export async function reorderAdminCollection(id: number, problemIds: number[]): Promise<AdminCollection> {
  return (await http.put<AdminCollection>(`/admin/collections/${id}/problems`, { problem_ids: problemIds })).data
}

export async function setAdminCollectionPublished(id: number, published: boolean): Promise<AdminCollection> {
  const action = published ? 'publish' : 'offline'
  return (await http.post<AdminCollection>(`/admin/collections/${id}/${action}`)).data
}

export async function listDailyChallenges(
  startDate: string,
  endDate: string,
  page = 1,
  pageSize = 100,
): Promise<DailyChallengePage> {
  return (
    await http.get<DailyChallengePage>('/admin/daily-challenges', {
      params: { start_date: startDate, end_date: endDate, page, page_size: pageSize },
    })
  ).data
}

export async function setDailyChallenge(date: string, problemId: number): Promise<DailyChallengeAdmin> {
  return (await http.put<DailyChallengeAdmin>(`/admin/daily-challenges/${date}`, { problem_id: problemId })).data
}

export async function deleteDailyChallenge(date: string): Promise<void> {
  await http.delete(`/admin/daily-challenges/${date}`)
}

export async function listModerationQueue(
  page: number,
  targetType?: 'discussion' | 'comment',
): Promise<ModerationQueuePage> {
  return (
    await http.get<ModerationQueuePage>('/admin/moderation', {
      params: { page, page_size: 20, target_type: targetType },
    })
  ).data
}

export async function moderateContent(
  type: 'discussion' | 'comment',
  id: number,
  reviewStatus: 'approved' | 'rejected',
  reason?: string,
): Promise<ModeratedContent> {
  const resource = type === 'discussion' ? 'discussions' : 'comments'
  return (
    await http.patch<ModeratedContent>(`/admin/${resource}/${id}/moderation`, {
      review_status: reviewStatus,
      reason: reason || null,
    })
  ).data
}

export async function controlDiscussion(
  id: number,
  payload: { is_pinned?: boolean; is_locked?: boolean },
): Promise<Discussion> {
  return (await http.patch<Discussion>(`/admin/discussions/${id}/controls`, payload)).data
}

export async function listContentReports(
  page: number,
  status?: 'pending' | 'resolved' | 'dismissed',
): Promise<ContentReportPage> {
  return (
    await http.get<ContentReportPage>('/admin/content-reports', {
      params: { page, page_size: 20, report_status: status },
    })
  ).data
}

export async function handleContentReport(
  id: number,
  status: 'resolved' | 'dismissed',
  reason?: string,
): Promise<ContentReport> {
  return (
    await http.patch<ContentReport>(`/admin/content-reports/${id}`, {
      status,
      reason: reason || null,
    })
  ).data
}

export async function listRejudgeTasks(page = 1): Promise<RejudgeTaskPage> {
  return (
    await http.get<RejudgeTaskPage>('/admin/rejudge', { params: { page, page_size: 20 } })
  ).data
}

export async function rejudgeSubmission(submissionId: string): Promise<RejudgeTask> {
  return (await http.post<RejudgeTask>('/admin/rejudge/submissions', { submission_id: submissionId })).data
}

export async function rejudgeProblemBatch(problemId: number, testSetId: string): Promise<RejudgeTask> {
  return (
    await http.post<RejudgeTask>('/admin/rejudge/batch', {
      problem_id: problemId,
      test_set_id: testSetId,
    })
  ).data
}
