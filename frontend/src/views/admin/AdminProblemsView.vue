<script setup lang="ts">
import { onMounted, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useAdminStore } from '@/stores/admin'
import { useProblemStore } from '@/stores/problems'
import type { AdminProblemQuery } from '@/types/admin'

const admin = useAdminStore()
const catalog = useProblemStore()
const router = useRouter()
const filters = reactive<AdminProblemQuery>({ page: 1, page_size: 20, sort: 'updated_desc' })
let debounce: ReturnType<typeof setTimeout> | undefined

function load(resetPage = false): void {
  if (resetPage) filters.page = 1
  void admin.loadProblems({ ...filters })
}

function search(): void {
  clearTimeout(debounce)
  debounce = setTimeout(() => load(true), 250)
}

function visibilityLabel(value: string): string {
  return { draft: '草稿', public: '已发布', private: '已下线' }[value] ?? value
}

onMounted(() => {
  void catalog.loadTags()
  load()
})

watch(() => [filters.difficulty, filters.status, filters.tag, filters.sort], () => load(true))
</script>

<template>
  <section class="admin-page" aria-labelledby="admin-problems-title">
    <header class="admin-page-header">
      <div><p class="eyebrow">PROBLEM OPERATIONS</p><h1 id="admin-problems-title">题目管理</h1></div>
      <ElButton type="primary" @click="router.push('/admin/problems/new')">创建题目</ElButton>
    </header>

    <div class="admin-filter-bar" role="search">
      <ElInput v-model="filters.q" clearable placeholder="搜索标题或 slug" aria-label="搜索题目" @input="search" />
      <ElSelect v-model="filters.difficulty" clearable placeholder="难度" aria-label="难度筛选">
        <ElOption label="简单" value="easy" /><ElOption label="中等" value="medium" /><ElOption label="困难" value="hard" />
      </ElSelect>
      <ElSelect v-model="filters.status" clearable placeholder="状态" aria-label="状态筛选">
        <ElOption label="草稿" value="draft" /><ElOption label="已发布" value="public" /><ElOption label="已下线" value="private" />
      </ElSelect>
      <ElSelect v-model="filters.tag" clearable filterable placeholder="标签" aria-label="标签筛选">
        <ElOption v-for="tag in catalog.tags" :key="tag.id" :label="tag.name" :value="tag.slug" />
      </ElSelect>
      <ElSelect v-model="filters.sort" aria-label="排序">
        <ElOption label="最近更新" value="updated_desc" /><ElOption label="最早更新" value="updated_asc" />
        <ElOption label="最新创建" value="created_desc" /><ElOption label="最早创建" value="created_asc" />
      </ElSelect>
    </div>

    <ElSkeleton v-if="admin.loading" :rows="8" animated class="admin-loading" />
    <ElAlert v-else-if="admin.error" type="error" :title="admin.error" show-icon>
      <template #default><ElButton size="small" @click="load()">重试</ElButton></template>
    </ElAlert>
    <ElEmpty v-else-if="!admin.problems.length" description="没有符合条件的题目" />
    <div v-else class="admin-table-wrap">
      <ElTable :data="admin.problems" row-key="id">
        <ElTableColumn prop="id" label="题号" width="80" />
        <ElTableColumn label="题目" min-width="240">
          <template #default="scope"><strong>{{ scope.row.title }}</strong><small class="admin-cell-subtitle">{{ scope.row.slug }}</small></template>
        </ElTableColumn>
        <ElTableColumn label="难度" width="90"><template #default="scope">{{ { easy: '简单', medium: '中等', hard: '困难' }[scope.row.difficulty as 'easy'] }}</template></ElTableColumn>
        <ElTableColumn label="标签" min-width="180"><template #default="scope"><ElTag v-for="tag in scope.row.tags" :key="tag.id" size="small">{{ tag.name }}</ElTag></template></ElTableColumn>
        <ElTableColumn label="状态" width="100"><template #default="scope"><ElTag :type="scope.row.visibility === 'public' ? 'success' : 'info'">{{ visibilityLabel(scope.row.visibility) }}</ElTag></template></ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" width="180"><template #default="scope">{{ new Date(scope.row.updated_at).toLocaleString() }}</template></ElTableColumn>
        <ElTableColumn label="操作" width="100" fixed="right"><template #default="scope"><ElButton link type="primary" @click="router.push(`/admin/problems/${scope.row.id}`)">编辑</ElButton></template></ElTableColumn>
      </ElTable>
    </div>
    <ElPagination v-if="admin.pages > 1" v-model:current-page="filters.page" :page-size="filters.page_size" :total="admin.total" layout="prev, pager, next" @current-change="load()" />
  </section>
</template>
