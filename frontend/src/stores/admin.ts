import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  activateTestSet,
  createAdminProblem,
  createProblemTestSet,
  getAdminProblem,
  getProblemReadiness,
  listAdminProblems,
  listProblemTestSets,
  offlineAdminProblem,
  publishAdminProblem,
  updateAdminProblem,
  uploadTestSetArchive,
  validateTestSet,
} from '@/services/admin'
import { getApiErrorMessage } from '@/services/http'
import type {
  AdminProblem,
  AdminProblemQuery,
  CheckerType,
  ProblemReadiness,
  ProblemWritePayload,
  TestSetMetadata,
  TestSetIssue,
  TestSetValidation,
} from '@/types/admin'

export const useAdminStore = defineStore('admin', () => {
  const problems = ref<AdminProblem[]>([])
  const total = ref(0)
  const pages = ref(0)
  const problem = ref<AdminProblem | null>(null)
  const testSets = ref<TestSetMetadata[]>([])
  const readiness = ref<ProblemReadiness | null>(null)
  const loading = ref(false)
  const detailLoading = ref(false)
  const pendingAction = ref('')
  const error = ref('')
  const uploadProgress = ref(0)
  const testSetIssues = ref<Record<string, TestSetIssue[]>>({})

  async function loadProblems(query: AdminProblemQuery): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const result = await listAdminProblems(query)
      problems.value = result.items
      total.value = result.total
      pages.value = result.pages
    } catch (reason) {
      problems.value = []
      error.value = getApiErrorMessage(reason, '管理题目加载失败')
    } finally {
      loading.value = false
    }
  }

  async function loadProblem(id: number): Promise<void> {
    detailLoading.value = true
    error.value = ''
    try {
      const [loaded, sets, check] = await Promise.all([
        getAdminProblem(id),
        listProblemTestSets(id),
        getProblemReadiness(id),
      ])
      problem.value = loaded
      testSets.value = sets
      readiness.value = check
    } catch (reason) {
      problem.value = null
      error.value = getApiErrorMessage(reason, '题目管理详情加载失败')
    } finally {
      detailLoading.value = false
    }
  }

  async function saveProblem(payload: ProblemWritePayload): Promise<AdminProblem> {
    pendingAction.value = 'save'
    try {
      const saved = problem.value
        ? await updateAdminProblem(problem.value.id, payload)
        : await createAdminProblem(payload)
      problem.value = saved
      return saved
    } finally {
      pendingAction.value = ''
    }
  }

  async function publish(): Promise<void> {
    if (!problem.value) return
    pendingAction.value = 'publish'
    try {
      readiness.value = await getProblemReadiness(problem.value.id)
      if (!readiness.value.ready) return
      problem.value = await publishAdminProblem(problem.value.id)
    } finally {
      pendingAction.value = ''
    }
  }

  async function offline(): Promise<void> {
    if (!problem.value) return
    pendingAction.value = 'offline'
    try {
      problem.value = await offlineAdminProblem(problem.value.id)
    } finally {
      pendingAction.value = ''
    }
  }

  async function createTestSet(
    checkerType: CheckerType,
    absoluteTolerance?: number,
    relativeTolerance?: number,
  ): Promise<void> {
    if (!problem.value) return
    pendingAction.value = 'create-test-set'
    try {
      const checker = checkerType === 'float'
        ? { checker_type: checkerType, absolute_tolerance: absoluteTolerance ?? 0.000001, relative_tolerance: relativeTolerance ?? 0.000001 }
        : { checker_type: checkerType }
      const created = await createProblemTestSet(problem.value.id, checker)
      testSets.value = [created, ...testSets.value]
    } finally {
      pendingAction.value = ''
    }
  }

  async function uploadArchive(testSetId: string, file: File): Promise<void> {
    pendingAction.value = `upload:${testSetId}`
    uploadProgress.value = 0
    try {
      const updated = await uploadTestSetArchive(testSetId, file, (value) => {
        uploadProgress.value = value
      })
      testSets.value = testSets.value.map((item) => (item.id === updated.id ? updated : item))
    } finally {
      pendingAction.value = ''
    }
  }

  async function validate(testSetId: string): Promise<TestSetValidation> {
    pendingAction.value = `validate:${testSetId}`
    try {
      const result = await validateTestSet(testSetId)
      testSetIssues.value = { ...testSetIssues.value, [testSetId]: result.issues }
      testSets.value = testSets.value.map((item) =>
        item.id === result.test_set.id ? result.test_set : item,
      )
      return result
    } finally {
      pendingAction.value = ''
    }
  }

  async function activate(testSetId: string): Promise<void> {
    pendingAction.value = `activate:${testSetId}`
    try {
      await activateTestSet(testSetId)
      if (problem.value) {
        testSets.value = await listProblemTestSets(problem.value.id)
        readiness.value = await getProblemReadiness(problem.value.id)
      }
    } finally {
      pendingAction.value = ''
    }
  }

  function clearDetail(): void {
    problem.value = null
    testSets.value = []
    readiness.value = null
    testSetIssues.value = {}
    error.value = ''
  }

  return {
    problems,
    total,
    pages,
    problem,
    testSets,
    readiness,
    loading,
    detailLoading,
    pendingAction,
    error,
    uploadProgress,
    testSetIssues,
    loadProblems,
    loadProblem,
    saveProblem,
    publish,
    offline,
    createTestSet,
    uploadArchive,
    validate,
    activate,
    clearDetail,
  }
})
