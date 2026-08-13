<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { DEFAULT_PROBLEM_FILTERS, TRAINING_CATEGORY_LABELS } from '@/types/problem'
import type {
  ProblemDifficulty,
  ProblemFilters,
  ProblemProgressStatus,
  ProblemSort,
  ProblemTag,
  TrainingCategory,
} from '@/types/problem'

const props = defineProps<{
  filters: ProblemFilters
  tags: ProblemTag[]
  tagsLoading: boolean
  statusEnabled: boolean
}>()
const emit = defineEmits<{
  change: [filters: ProblemFilters]
}>()

const keyword = ref(props.filters.q)
watch(
  () => props.filters.q,
  (value) => {
    keyword.value = value
  },
)

function patchFilters(patch: Partial<ProblemFilters>): void {
  emit('change', { ...props.filters, ...patch, page: 1 })
}

const difficulty = computed<ProblemDifficulty | ''>({
  get: () => props.filters.difficulty,
  set: (value) => patchFilters({ difficulty: value }),
})
const tag = computed({
  get: () => props.filters.tag,
  set: (value: string) => patchFilters({ tag: value }),
})
const category = computed<TrainingCategory | ''>({
  get: () => props.filters.category,
  set: (value) => patchFilters({ category: value }),
})
const progressStatus = computed<ProblemProgressStatus | ''>({
  get: () => props.filters.status,
  set: (value) => patchFilters({ status: value }),
})
const sort = computed<ProblemSort>({
  get: () => props.filters.sort,
  set: (value) => patchFilters({ sort: value }),
})

function search(): void {
  patchFilters({ q: keyword.value.trim() })
}

function reset(): void {
  keyword.value = ''
  emit('change', { ...DEFAULT_PROBLEM_FILTERS, pageSize: props.filters.pageSize })
}
</script>

<template>
  <section class="problem-filters" aria-label="训练课程筛选">
    <div class="filter-search">
      <el-input
        v-model="keyword"
        clearable
        maxlength="200"
        placeholder="搜索练习标题或 slug"
        aria-label="练习关键词"
        @clear="search"
        @keyup.enter="search"
      />
      <el-button type="primary" @click="search">搜索</el-button>
    </div>
    <el-select v-model="category" aria-label="输入输出分类筛选" placeholder="全部输入输出分类">
      <el-option label="全部输入输出分类" value="" />
      <el-option v-for="(label, value) in TRAINING_CATEGORY_LABELS" :key="value" :label="label" :value="value" />
    </el-select>
    <el-select v-model="difficulty" aria-label="结构层级筛选" placeholder="全部结构层级">
      <el-option label="全部结构层级" value="" />
      <el-option label="基础" value="easy" />
      <el-option label="组合" value="medium" />
      <el-option label="综合" value="hard" />
    </el-select>
    <el-select
      v-model="tag"
      :loading="tagsLoading"
      filterable
      aria-label="标签筛选"
      placeholder="全部标签"
    >
      <el-option label="全部标签" value="" />
      <el-option v-for="item in tags" :key="item.id" :label="item.name" :value="item.slug" />
    </el-select>
    <el-tooltip :disabled="statusEnabled" content="登录后可按个人完成状态筛选">
      <el-select
        v-model="progressStatus"
        :disabled="!statusEnabled"
        aria-label="完成状态筛选"
        placeholder="完成状态"
      >
        <el-option label="全部状态" value="" />
        <el-option label="已通过" value="solved" />
        <el-option label="尝试中" value="attempted" />
        <el-option label="未尝试" value="unattempted" />
        <el-option label="已收藏" value="favorited" />
      </el-select>
    </el-tooltip>
    <el-select v-model="sort" aria-label="题目排序" placeholder="排序">
      <el-option label="最新发布" value="newest" />
      <el-option label="最早发布" value="oldest" />
      <el-option label="标题排序" value="title" />
      <el-option label="结构层级排序" value="difficulty" />
      <el-option label="通过率最高" value="acceptance" />
    </el-select>
    <el-button class="filter-reset" text @click="reset">重置</el-button>
  </section>
</template>
