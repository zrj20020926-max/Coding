<script setup lang="ts">
import DifficultyBadge from '@/components/problems/DifficultyBadge.vue'
import type { ProblemSummary } from '@/types/problem'
import { TRAINING_CATEGORY_LABELS } from '@/types/problem'

defineProps<{
  problems: ProblemSummary[]
  authenticated: boolean
  favoritePendingIds?: number[]
}>()
const emit = defineEmits<{
  favorite: [problem: ProblemSummary]
}>()

function progressLabel(problem: ProblemSummary, authenticated: boolean): string {
  if (!authenticated) return '登录后记录'
  if (problem.solved) return '已通过'
  if (problem.attempted) return `尝试中 · ${problem.attempt_count ?? 0} 次`
  return '未尝试'
}

function progressClass(problem: ProblemSummary): string {
  if (problem.solved) return 'progress-solved'
  if (problem.attempted) return 'progress-attempted'
  return 'progress-unattempted'
}
</script>

<template>
  <div class="problem-table" role="table" aria-label="训练练习列表">
    <div class="problem-table-head" role="row">
      <span role="columnheader">编号</span>
      <span role="columnheader">练习</span>
      <span role="columnheader">结构层级</span>
      <span role="columnheader">标签</span>
      <span role="columnheader">通过率</span>
      <span role="columnheader">进度</span>
      <span role="columnheader">收藏</span>
    </div>
    <div v-for="problem in problems" :key="problem.id" class="problem-row" role="row">
      <span class="problem-number" role="cell">#{{ String(problem.id).padStart(4, '0') }}</span>
      <span class="problem-title-cell" role="cell">
        <RouterLink :to="{ name: 'problem-detail', params: { slug: problem.slug } }">
          <strong>{{ problem.title }}</strong>
          <small>{{ TRAINING_CATEGORY_LABELS[problem.training_category] }} · {{ problem.slug }}</small>
        </RouterLink>
      </span>
      <span role="cell"><DifficultyBadge :difficulty="problem.difficulty" /></span>
      <span class="problem-tags" role="cell">
        <span v-for="tag in problem.tags" :key="tag.id">{{ tag.name }}</span>
        <small v-if="problem.tags.length === 0">暂无标签</small>
      </span>
      <span class="acceptance-cell" role="cell">
        <strong>{{ problem.acceptance_rate.toFixed(1) }}%</strong>
        <small>{{ problem.accepted_count }}/{{ problem.submission_count }}</small>
      </span>
      <span class="problem-progress" :class="progressClass(problem)" role="cell">
        {{ progressLabel(problem, authenticated) }}
      </span>
      <span class="favorite-cell" role="cell">
        <button
          class="favorite-button"
          :class="{ 'is-favorited': problem.favorited }"
          type="button"
          :disabled="favoritePendingIds?.includes(problem.id)"
          :aria-label="problem.favorited ? `取消收藏 ${problem.title}` : `收藏 ${problem.title}`"
          @click="emit('favorite', problem)"
        >
          {{ problem.favorited ? '★' : '☆' }}
        </button>
      </span>
    </div>
  </div>
</template>
