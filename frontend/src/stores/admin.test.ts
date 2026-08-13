import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as service from '@/services/admin'
import { useAdminStore } from '@/stores/admin'
import type { AdminProblem, ProblemReadiness } from '@/types/admin'

vi.mock('@/services/admin')

const problem: AdminProblem = {
  id: 1, slug: 'admin-problem', title: '管理题', difficulty: 'easy', training_category: 'comprehensive', source: null,
  accepted_count: 0, submission_count: 0, acceptance_rate: 0, tags: [], description: '描述',
  input_description: '输入', output_description: '输出', data_constraints: 'n <= 10',
  sample_input: '1', sample_output: '1', sample_explanation: '解释', time_limit_ms: 1000,
  memory_limit_mb: 256, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z',
  visibility: 'draft', created_by: null,
}
const blocked: ProblemReadiness = { ready: false, issues: [{ code: 'NO_ACTIVE_TEST_SET', message: '缺少活动测试集' }] }

describe('admin store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('loads list and detail data through services', async () => {
    vi.mocked(service.listAdminProblems).mockResolvedValue({ items: [problem], total: 1, page: 1, page_size: 20, pages: 1 })
    vi.mocked(service.getAdminProblem).mockResolvedValue(problem)
    vi.mocked(service.listProblemTestSets).mockResolvedValue([])
    vi.mocked(service.getProblemReadiness).mockResolvedValue(blocked)
    const store = useAdminStore()
    await store.loadProblems({ page: 1, page_size: 20, sort: 'updated_desc' })
    await store.loadProblem(1)
    expect(store.problems).toEqual([problem])
    expect(store.problem).toEqual(problem)
    expect(store.readiness?.issues[0]?.code).toBe('NO_ACTIVE_TEST_SET')
  })

  it('does not call publish when the server readiness gate is blocked', async () => {
    vi.mocked(service.getAdminProblem).mockResolvedValue(problem)
    vi.mocked(service.listProblemTestSets).mockResolvedValue([])
    vi.mocked(service.getProblemReadiness).mockResolvedValue(blocked)
    const store = useAdminStore()
    await store.loadProblem(1)
    await store.publish()
    expect(service.publishAdminProblem).not.toHaveBeenCalled()
  })

  it('stores per-case validation issues without hidden test data', async () => {
    const store = useAdminStore()
    const testSet = { id: 'set-1', problem_id: 1, version: 1, status: 'invalid' as const, checker_type: 'exact' as const, absolute_tolerance: null, relative_tolerance: null, case_count: 1, total_score: '100', created_by: null, created_at: '', activated_at: null, submission_reference_count: 0, cases: [] }
    vi.mocked(service.validateTestSet).mockResolvedValue({ test_set: testSet, issues: [{ code: 'CHECKSUM_MISMATCH', message: '测试数据校验失败', sequence: 1 }] })
    await store.validate('set-1')
    expect(store.testSetIssues['set-1']?.[0]).toEqual({ code: 'CHECKSUM_MISMATCH', message: '测试数据校验失败', sequence: 1 })
    expect(JSON.stringify(store.testSetIssues)).not.toContain('object_key')
  })
})
