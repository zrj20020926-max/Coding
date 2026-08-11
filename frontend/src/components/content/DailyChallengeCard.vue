<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import DifficultyBadge from '@/components/problems/DifficultyBadge.vue'
import { useContentStore } from '@/stores/content'

const content = useContentStore()
const { daily, dailyLoading } = storeToRefs(content)

onMounted(() => void content.loadDaily())
</script>

<template>
  <section class="daily-card page-container" aria-label="每日一题">
    <div>
      <p class="section-kicker">DAILY CHALLENGE</p>
      <template v-if="dailyLoading">
        <span class="skeleton-block daily-title-skeleton"></span>
      </template>
      <template v-else-if="daily">
        <span class="daily-date">{{ daily.challenge_date }} · {{ daily.timezone }}</span>
        <h2>{{ daily.problem.title }}</h2>
        <div class="daily-meta">
          <DifficultyBadge :difficulty="daily.problem.difficulty" />
          <span>{{ daily.problem.acceptance_rate.toFixed(1) }}% 通过率</span>
          <span v-if="daily.problem.solved">✓ 已解决</span>
        </div>
      </template>
      <template v-else>
        <span class="daily-date">按服务端日期更新</span>
        <h2>今日挑战即将发布</h2>
      </template>
    </div>
    <RouterLink
      v-if="daily"
      class="hero-primary"
      :to="{ name: 'problem-detail', params: { slug: daily.problem.slug } }"
    >
      开始挑战
    </RouterLink>
    <RouterLink v-else class="hero-secondary" to="/problems">浏览题库</RouterLink>
  </section>
</template>
