<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import MarkdownContent from '@/components/problems/MarkdownContent.vue'
import ProblemTable from '@/components/problems/ProblemTable.vue'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useContentStore } from '@/stores/content'
import { setProblemFavorite } from '@/services/problems'
import type { ProblemSummary } from '@/types/problem'

const route = useRoute()
const auth = useAuthStore()
const content = useContentStore()
const { collection, collectionLoading, collectionError } = storeToRefs(content)
const slug = computed(() => String(route.params['slug'] ?? ''))
const page = ref(1)
const pageSize = 20
const pendingIds = ref<number[]>([])

watch([slug, page], () => void content.loadCollection(slug.value, page.value, pageSize), {
  immediate: true,
})

async function toggleFavorite(problem: ProblemSummary): Promise<void> {
  if (!auth.isAuthenticated) return
  pendingIds.value.push(problem.id)
  try {
    const state = await setProblemFavorite(problem.id, !problem.favorited)
    problem.favorited = state.favorited
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '收藏操作失败'))
  } finally {
    pendingIds.value = pendingIds.value.filter((id) => id !== problem.id)
  }
}
</script>

<template>
  <section class="collection-detail-page page-container">
    <div v-if="collectionLoading" class="detail-skeleton"><span class="skeleton-block detail-title-skeleton"></span></div>
    <el-result v-else-if="collectionError" icon="error" title="题单加载失败" :sub-title="collectionError" />
    <template v-else-if="collection">
      <header class="collection-detail-header">
        <div>
          <p class="eyebrow">{{ collection.company ?? 'CODEARENA TRACK' }}</p>
          <h1>{{ collection.title }}</h1>
          <MarkdownContent :content="collection.description || '按顺序完成题单，建立稳定的知识结构。'" />
        </div>
        <aside>
          <strong>{{ collection.solved_count ?? 0 }} / {{ collection.problem_count }}</strong>
          <span>{{ collection.completion_rate?.toFixed(0) ?? 0 }}% 完成</span>
        </aside>
      </header>
      <ProblemTable
        :problems="collection.problems.map((item) => item.problem)"
        :authenticated="auth.isAuthenticated"
        :favorite-pending-ids="pendingIds"
        @favorite="toggleFavorite"
      />
      <div class="catalog-pagination">
        <el-pagination
          background
          layout="prev, pager, next"
          :current-page="page"
          :page-size="pageSize"
          :total="collection.problem_count"
          @update:current-page="page = $event"
        />
      </div>
    </template>
  </section>
</template>
