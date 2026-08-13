<script setup lang="ts">
import { computed } from 'vue'

import type { ProblemDifficulty } from '@/types/problem'

const props = defineProps<{ difficulty: ProblemDifficulty }>()

const label = computed(() => ({ easy: '基础', medium: '组合', hard: '综合' })[props.difficulty])
</script>

<template>
  <span class="difficulty-badge" :class="`difficulty-${difficulty}`">{{ label }}</span>
</template>
