<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import SubmissionStatusBadge from '@/components/submissions/SubmissionStatusBadge.vue'
import { useSubmissionStore } from '@/stores/submissions'

const route = useRoute()
const router = useRouter()
const store = useSubmissionStore()
const { history, historyTotal, historyLoading, historyError } = storeToRefs(store)
const pageSize = ref(20)
const page = computed(() => {
  const parsed = Number.parseInt(String(route.query['page'] ?? '1'), 10)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1
})

function load(): void {
  void store.loadHistory(page.value, pageSize.value)
}

function changePage(value: number): void {
  void router.replace({ name: 'submissions', query: value === 1 ? {} : { page: String(value) } })
}

function changePageSize(value: number): void {
  pageSize.value = value
  void router.replace({ name: 'submissions', query: {} })
  load()
}

watch(page, load, { immediate: true })
</script>

<template>
  <section class="submissions-page page-container">
    <header class="submissions-heading">
      <div><p class="eyebrow">SUBMISSION HISTORY</p><h1>提交记录</h1></div>
      <span>共 {{ historyTotal }} 次运行与提交</span>
    </header>

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
