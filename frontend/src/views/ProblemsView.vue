<script setup lang="ts">
import { ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import ProblemFiltersPanel from '@/components/problems/ProblemFilters.vue'
import ProblemListSkeleton from '@/components/problems/ProblemListSkeleton.vue'
import ProblemTable from '@/components/problems/ProblemTable.vue'
import { useAuthStore } from '@/stores/auth'
import { useProblemStore } from '@/stores/problems'
import {
  parseProblemQuery,
  serializeProblemFilters,
  toProblemListParams,
} from '@/types/problem'
import type { ProblemFilters } from '@/types/problem'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const problemStore = useProblemStore()
const { items, total, listLoading, listError, tags, tagsLoading } = storeToRefs(problemStore)
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
        <p class="eyebrow">PROBLEM CATALOG</p>
        <h1>题库</h1>
        <p>以真实 stdin / stdout 方式训练企业笔试与竞赛算法题。</p>
      </div>
      <div class="catalog-count"><strong>{{ total }}</strong><span>公开题目</span></div>
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
      <el-result icon="error" title="题库加载失败" :sub-title="listError">
        <template #extra><el-button type="primary" @click="fetchProblems">重新加载</el-button></template>
      </el-result>
    </section>
    <section v-else-if="items.length === 0" class="catalog-feedback">
      <el-empty description="没有找到符合条件的题目">
        <el-button @click="syncFilters({ ...filters, q: '', difficulty: '', tag: '', status: '', page: 1 })">
          清除筛选
        </el-button>
      </el-empty>
    </section>
    <template v-else>
      <ProblemTable :problems="items" :authenticated="auth.isAuthenticated" />
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
