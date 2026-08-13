<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import SubmissionStatusBadge from '@/components/submissions/SubmissionStatusBadge.vue'
import { getProblemLanguages, getProblems } from '@/services/problems'
import { useSubmissionStore } from '@/stores/submissions'
import type { JudgeLanguage } from '@/types/editor'
import type { ProblemSummary } from '@/types/problem'
import type { SubmissionHistoryFilters, SubmissionMode, SubmissionStatus } from '@/types/submission'

const route = useRoute()
const router = useRouter()
const store = useSubmissionStore()
const { history, historyTotal, historyLoading, historyError } = storeToRefs(store)
const problems = ref<ProblemSummary[]>([])
const languages = ref<JudgeLanguage[]>([])
const filterOptionsLoading = ref(false)
const pageSize = computed(() => {
  const parsed = Number.parseInt(String(route.query['page_size'] ?? '20'), 10)
  return [10, 20, 50].includes(parsed) ? parsed : 20
})
const page = computed(() => {
  const parsed = Number.parseInt(String(route.query['page'] ?? '1'), 10)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1
})
const filters = computed<SubmissionHistoryFilters>(() => {
  const result: SubmissionHistoryFilters = {}
  const problemId = Number.parseInt(String(route.query['problem_id'] ?? ''), 10)
  if (Number.isSafeInteger(problemId) && problemId > 0) result.problem_id = problemId
  const language = route.query['language']
  if (typeof language === 'string' && language) result.language = language
  const status = route.query['status']
  if (typeof status === 'string' && submissionStatuses.includes(status as SubmissionStatus)) {
    result.status = status as SubmissionStatus
  }
  const mode = route.query['mode']
  if (mode === 'sample' || mode === 'judge') result.mode = mode
  return result
})

const submissionStatuses: SubmissionStatus[] = [
  'Pending', 'Compiling', 'Running', 'Accepted', 'Wrong Answer', 'Compile Error',
  'Runtime Error', 'Time Limit Exceeded', 'Memory Limit Exceeded', 'System Error',
]
const statusLabels: Record<SubmissionStatus, string> = {
  Pending: '等待中', Compiling: '编译中', Running: '运行中', Accepted: '已通过',
  'Wrong Answer': '答案错误', 'Compile Error': '编译错误', 'Runtime Error': '运行错误',
  'Time Limit Exceeded': '超出时间限制', 'Memory Limit Exceeded': '超出内存限制',
  'System Error': '平台错误',
}

function load(): void {
  void store.loadHistory(page.value, pageSize.value, filters.value)
}

function changePage(value: number): void {
  void updateQuery('page', value === 1 ? undefined : String(value), false)
}

function changePageSize(value: number): void {
  void router.replace({
    name: 'submissions',
    query: { ...route.query, page: undefined, page_size: value === 20 ? undefined : String(value) },
  })
}

function updateQuery(key: string, value: string | number | undefined, resetPage = true): void {
  void router.replace({
    name: 'submissions',
    query: {
      ...route.query,
      [key]: value === '' ? undefined : value,
      ...(resetPage ? { page: undefined } : {}),
    },
  })
}

function clearFilters(): void {
  void router.replace({ name: 'submissions' })
}

async function loadFilterOptions(): Promise<void> {
  filterOptionsLoading.value = true
  try {
    const [problemPage, languageItems] = await Promise.all([
      getProblems({ page: 1, page_size: 100, sort: 'newest' }),
      getProblemLanguages(),
    ])
    problems.value = problemPage.items
    languages.value = languageItems
  } finally {
    filterOptionsLoading.value = false
  }
}

watch(() => route.query, load, { immediate: true, deep: true })
onMounted(() => void loadFilterOptions())
</script>

<template>
  <section class="submissions-page page-container">
    <header class="submissions-heading">
      <div><p class="eyebrow">SUBMISSION HISTORY</p><h1>提交记录</h1></div>
      <span>共 {{ historyTotal }} 次运行与提交</span>
    </header>

    <section class="submission-filters" aria-label="筛选提交记录">
      <el-select
        :model-value="filters.problem_id"
        clearable filterable :loading="filterOptionsLoading" placeholder="全部题目"
        aria-label="按题目筛选"
        @update:model-value="updateQuery('problem_id', $event)"
      >
        <el-option v-for="problem in problems" :key="problem.id" :label="`#${problem.id} ${problem.title}`" :value="problem.id" />
      </el-select>
      <el-select
        :model-value="filters.language" clearable :loading="filterOptionsLoading"
        placeholder="全部语言" aria-label="按语言筛选"
        @update:model-value="updateQuery('language', $event)"
      >
        <el-option v-for="item in languages" :key="item.id" :label="`${item.display_name} ${item.version}`" :value="item.slug" />
      </el-select>
      <el-select
        :model-value="filters.status" clearable placeholder="全部状态"
        aria-label="按状态筛选" @update:model-value="updateQuery('status', $event)"
      >
        <el-option v-for="item in submissionStatuses" :key="item" :label="statusLabels[item]" :value="item" />
      </el-select>
      <el-select
        :model-value="filters.mode" clearable placeholder="全部类型"
        aria-label="按提交类型筛选"
        @update:model-value="updateQuery('mode', $event as SubmissionMode)"
      >
        <el-option label="公开样例" value="sample" /><el-option label="正式提交" value="judge" />
      </el-select>
      <el-button @click="clearFilters">清空筛选</el-button>
    </section>

    <div v-if="historyLoading" class="submission-list-loading" aria-busy="true">
      <span v-for="index in 6" :key="index" class="skeleton-block"></span>
    </div>
    <section v-else-if="historyError" class="catalog-feedback">
      <el-result icon="error" title="提交记录加载失败" :sub-title="historyError">
        <template #extra><el-button type="primary" @click="load">重试</el-button></template>
      </el-result>
    </section>
    <el-empty v-else-if="history.length === 0" description="还没有提交记录">
      <RouterLink class="primary-link" to="/problems">开始刷题</RouterLink>
    </el-empty>
    <div v-else class="submission-list">
      <RouterLink
        v-for="item in history"
        :key="item.id"
        class="submission-row"
        :to="`/submissions/${item.id}`"
      >
        <div class="submission-problem">
          <strong>{{ item.problem.title }}</strong>
          <small>#{{ item.problem.id }} · {{ item.mode === 'sample' ? '公开样例' : '正式提交' }}</small>
        </div>
        <span>{{ item.language.display_name }} {{ item.language.version }}</span>
        <SubmissionStatusBadge :status="item.status" />
        <span>{{ item.time_used_ms === null ? '—' : `${item.time_used_ms} ms` }}</span>
        <span>{{ item.memory_used_kb === null ? '—' : `${item.memory_used_kb} KB` }}</span>
        <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time>
      </RouterLink>
    </div>

    <div v-if="historyTotal > 0" class="catalog-pagination">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :total="historyTotal"
        @update:current-page="changePage"
        @update:page-size="changePageSize"
      />
    </div>
  </section>
</template>
