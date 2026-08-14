import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'

import AdminProblemEditView from '@/views/admin/AdminProblemEditView.vue'
import { useAdminStore } from '@/stores/admin'

vi.mock('@/services/problems', () => ({ getProblemTags: vi.fn().mockResolvedValue([]) }))

describe('administrator publish gate', () => {
  it('shows structured readiness issues without hidden fields', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/admin/problems/:id', name: 'admin-problem-edit', component: AdminProblemEditView }] })
    await router.push('/admin/problems/1'); await router.isReady()
    const pinia = createPinia(); const store = useAdminStore(pinia)
    store.problem = { id: 1, title: '测试题', slug: 'test', difficulty: 'easy', training_category: 'comprehensive', source: null, accepted_count: 0, submission_count: 0, acceptance_rate: 0, tags: [], description: 'd', input_description: 'i', output_description: 'o', data_constraints: 'n', sample_input: '', sample_output: '', sample_explanation: 'e', starter_code_v8: null, starter_code_nodejs: null, time_limit_ms: 1000, memory_limit_mb: 256, created_at: '', updated_at: '', visibility: 'draft', created_by: null }
    store.readiness = { ready: false, issues: [{ code: 'CHECKSUM_MISMATCH', message: '测试数据校验失败', sequence: 2 }] }
    store.loadProblem = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(AdminProblemEditView, { global: { plugins: [pinia, router], stubs: { ProblemForm: true, TestSetManager: true, ElButton: true, ElTag: true, ElSkeleton: true, ElAlert: true } } })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('CHECKSUM_MISMATCH')
    expect(wrapper.text()).toContain('测试数据校验失败')
    expect(wrapper.html()).not.toMatch(/object_key|checksum原文|hidden_input|standard_answer/)
  })
})
