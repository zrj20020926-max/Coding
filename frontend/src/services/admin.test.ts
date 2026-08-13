import { describe, expect, it, vi } from 'vitest'

import { http } from '@/services/http'
import { listAdminProblems, listProblemTestSets, uploadTestSetArchive } from '@/services/admin'

describe('administrator services', () => {
  it('sends problem filters to the protected management endpoint', async () => {
    const get = vi.spyOn(http, 'get').mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 20, pages: 0 } })
    const query = { page: 1, page_size: 20, sort: 'updated_desc' as const, q: 'graph', status: 'draft' as const }
    await listAdminProblems(query)
    expect(get).toHaveBeenCalledWith('/admin/problems', { params: query })
  })

  it('never requests hidden case bodies or object-storage fields', async () => {
    const safeSet = { id: 'set-1', problem_id: 1, version: 1, status: 'active', checker_type: 'exact', absolute_tolerance: null, relative_tolerance: null, case_count: 1, total_score: '100', created_by: null, created_at: '2026-08-12T00:00:00Z', activated_at: null, submission_reference_count: 2, cases: [{ id: 'case-1', sequence: 1, score: '100', input_size_bytes: 12, output_size_bytes: 2 }] }
    vi.spyOn(http, 'get').mockResolvedValue({ data: [safeSet] })
    const result = await listProblemTestSets(1)
    const serialized = JSON.stringify(result)
    expect(serialized).not.toMatch(/object_key|checksum|hidden_input|hidden_output|standard_answer|reference_solution/)
  })

  it('uploads a ZIP as multipart data and reports progress', async () => {
    const post = vi.spyOn(http, 'post').mockImplementation((_url, body, config) => {
      expect(body).toBeInstanceOf(FormData)
      config?.onUploadProgress?.({ loaded: 50, total: 100 } as never)
      return Promise.resolve({ data: { test_set: { id: 'set-1' }, uploaded_count: 1 } })
    })
    const progress = vi.fn()
    await uploadTestSetArchive('set-1', new File(['zip'], 'cases.zip'), progress)
    expect(post).toHaveBeenCalledOnce()
    expect(progress).toHaveBeenCalledWith(50)
  })
})
