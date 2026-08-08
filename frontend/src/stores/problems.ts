import { ref } from 'vue'
import { defineStore } from 'pinia'

import { getApiErrorMessage } from '@/services/http'
import {
  getProblemBySlug,
  getProblems,
  getProblemTags,
  ProblemNotFoundError,
} from '@/services/problems'
import type { ProblemDetail, ProblemListParams, ProblemSummary, ProblemTag } from '@/types/problem'

export const useProblemStore = defineStore('problems', () => {
  const items = ref<ProblemSummary[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const pages = ref(0)
  const tags = ref<ProblemTag[]>([])
  const listLoading = ref(false)
  const listError = ref('')
  const tagsLoading = ref(false)
  const detail = ref<ProblemDetail | null>(null)
  const detailLoading = ref(false)
  const detailError = ref('')
  const detailNotFound = ref(false)
  let listRequestId = 0
  let detailRequestId = 0

  async function loadProblems(params: ProblemListParams): Promise<void> {
    const requestId = ++listRequestId
    listLoading.value = true
    listError.value = ''
    try {
      const result = await getProblems(params)
      if (requestId !== listRequestId) return
      items.value = result.items
      total.value = result.total
      page.value = result.page
      pageSize.value = result.page_size
      pages.value = result.pages
    } catch (error) {
      if (requestId !== listRequestId) return
      items.value = []
      total.value = 0
      pages.value = 0
      listError.value = getApiErrorMessage(error, '题库加载失败，请稍后重试')
    } finally {
      if (requestId === listRequestId) listLoading.value = false
    }
  }

  async function loadTags(): Promise<void> {
    if (tags.value.length || tagsLoading.value) return
    tagsLoading.value = true
    try {
      tags.value = await getProblemTags()
    } catch {
      tags.value = []
    } finally {
      tagsLoading.value = false
    }
  }

  async function loadProblem(slug: string): Promise<void> {
    const requestId = ++detailRequestId
    detailLoading.value = true
    detailError.value = ''
    detailNotFound.value = false
    detail.value = null
    try {
      const result = await getProblemBySlug(slug)
      if (requestId === detailRequestId) detail.value = result
    } catch (error) {
      if (requestId !== detailRequestId) return
      const notFound = error instanceof ProblemNotFoundError
      detailNotFound.value = notFound
      detailError.value = notFound
        ? error.message
        : getApiErrorMessage(error, '题目详情加载失败，请稍后重试')
    } finally {
      if (requestId === detailRequestId) detailLoading.value = false
    }
  }

  function clearDetail(): void {
    detailRequestId += 1
    detail.value = null
    detailError.value = ''
    detailNotFound.value = false
    detailLoading.value = false
  }

  return {
    items,
    total,
    page,
    pageSize,
    pages,
    tags,
    listLoading,
    listError,
    tagsLoading,
    detail,
    detailLoading,
    detailError,
    detailNotFound,
    loadProblems,
    loadTags,
    loadProblem,
    clearDetail,
  }
})
