<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { storeToRefs } from 'pinia'

import ProblemListSkeleton from '@/components/problems/ProblemListSkeleton.vue'
import ProblemTable from '@/components/problems/ProblemTable.vue'
import { getApiErrorMessage } from '@/services/http'
import { useTrainingStore } from '@/stores/training'
import type { ProblemSummary } from '@/types/problem'

const training = useTrainingStore()
const {
  favorites,
  favoritesTotal,
  favoritesLoading,
  favoritesError,
  favoritePendingIds,
} = storeToRefs(training)
const page = ref(1)
const pageSize = ref(20)

function load(): void {
  void training.loadFavorites(page.value, pageSize.value)
}

async function removeFavorite(problem: ProblemSummary): Promise<void> {
  try {
    await training.removeFavorite(problem.id)
    ElMessage.success('已取消收藏')
    if (favorites.value.length === 0 && page.value > 1) page.value -= 1
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '取消收藏失败，请稍后重试'))
  }
}

watch([page, pageSize], load, { immediate: true })
</script>

<template>
  <section class="favorites-page page-container">
    <header class="submissions-heading">
      <div>
        <p class="eyebrow">SAVED PRACTICES</p>
        <h1>我的收藏</h1>
      </div>
      <span>共 {{ favoritesTotal }} 项练习</span>
    </header>

    <ProblemListSkeleton v-if="favoritesLoading" />
    <section v-else-if="favoritesError" class="catalog-feedback" aria-live="polite">
      <el-result icon="error" title="收藏加载失败" :sub-title="favoritesError">
        <template #extra><el-button type="primary" @click="load">重新加载</el-button></template>
      </el-result>
    </section>
    <section v-else-if="favorites.length === 0" class="catalog-feedback">
      <el-empty description="还没有收藏练习">
        <RouterLink class="primary-link" to="/problems">浏览训练课程</RouterLink>
      </el-empty>
    </section>
    <template v-else>
      <ProblemTable
        :problems="favorites"
        :authenticated="true"
        :favorite-pending-ids="favoritePendingIds"
        @favorite="removeFavorite"
      />
      <div class="catalog-pagination">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="favoritesTotal"
          @update:current-page="page = $event"
          @update:page-size="pageSize = $event; page = 1"
        />
      </div>
    </template>
  </section>
</template>
