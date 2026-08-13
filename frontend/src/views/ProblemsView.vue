<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import ProblemFiltersPanel from '@/components/problems/ProblemFilters.vue'
import ProblemListSkeleton from '@/components/problems/ProblemListSkeleton.vue'
import ProblemTable from '@/components/problems/ProblemTable.vue'
import { useAuthStore } from '@/stores/auth'
import { useProblemStore } from '@/stores/problems'
import { getApiErrorMessage } from '@/services/http'
import {
  parseProblemQuery,
  serializeProblemFilters,
  toProblemListParams,
} from '@/types/problem'
import type { ProblemFilters, ProblemSummary } from '@/types/problem'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const problemStore = useProblemStore()
const { items, total, listLoading, listError, tags, tagsLoading, favoritePendingIds } =
  storeToRefs(problemStore)
const filters = ref<ProblemFilters>(parseProblemQuery(route.query))

function fetchProblems(): void {
  void problemStore.loadProblems(toProblemListParams(filters.value))
}

function syncFilters(nextFilters: ProblemFilters): void {
  const normalized = { ...nextFilters }
  if (!auth.isAuthenticated) normalized.status = ''
  void router.replace({ name: 'problems', query: serializeProblemFilters(normalized) })
}

function changePage(page: number): void {
  syncFilters({ ...filters.value, page })
}

function changePageSize(pageSize: number): void {
  syncFilters({ ...filters.value, page: 1, pageSize })
}

async function toggleFavorite(problem: ProblemSummary): Promise<void> {
  if (!auth.isAuthenticated) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  try {
    await problemStore.updateFavorite(problem.id, !problem.favorited)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '收藏操作失败，请稍后重试'))
  }
}

watch(
  () => route.query,
  (query) => {
    const parsed = parseProblemQuery(query)
    if (!auth.isAuthenticated && parsed.status) {
      parsed.status = ''
      void router.replace({ name: 'problems', query: serializeProblemFilters(parsed) })
      return
    }
    filters.value = parsed
    fetchProblems()
  },
  { immediate: true, deep: true },
)

void problemStore.loadTags()
</script>

<template>
  <div class="problems-page page-container">
    <header class="problems-heading">
      <div>
        <p class="eyebrow">JAVASCRIPT I/O TRAINING</p>
        <h1>训练课程</h1>
        <p>按输入输出结构练习 stdin 解析与 stdout 格式，支持 JavaScript V8 和 Node.js。</p>
      </div>
      <div class="catalog-count"><strong>{{ total }}</strong><span>公开练习</span></div>
    </header>

    <ProblemFiltersPanel
      :filters="filters"
      :tags="tags"
      :tags-loading="tagsLoading"
      :status-enabled="auth.isAuthenticated"
      @change="syncFilters"
    />

    <ProblemListSkeleton v-if="listLoading" />
    <section v-else-if="listError" class="catalog-feedback" aria-live="polite">
      <el-result icon="error" title="训练课程加载失败" :sub-title="listError">
        <template #extra><el-button type="primary" @click="fetchProblems">重新加载</el-button></template>
      </el-result>
    </section>
    <section v-else-if="items.length === 0" class="catalog-feedback">
      <el-empty description="没有找到符合条件的练习">
        <el-button @click="syncFilters({ ...filters, q: '', difficulty: '', category: '', tag: '', status: '', page: 1 })">
          清除筛选
        </el-button>
      </el-empty>
    </section>
    <template v-else>
      <ProblemTable
        :problems="items"
        :authenticated="auth.isAuthenticated"
        :favorite-pending-ids="favoritePendingIds"
        @favorite="toggleFavorite"
      />
      <div class="catalog-pagination">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :current-page="filters.page"
          :page-size="filters.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          @update:current-page="changePage"
          @update:page-size="changePageSize"
        />
      </div>
    </template>
  </div>
</template>
