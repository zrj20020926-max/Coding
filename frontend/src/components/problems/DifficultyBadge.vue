<script setup lang="ts">
import { computed } from 'vue'

import type { ProblemDifficulty } from '@/types/problem'

const props = defineProps<{ difficulty: ProblemDifficulty }>()

const label = computed(() => ({ easy: '简单', medium: '中等', hard: '困难' })[props.difficulty])
</script>

<template>
  <span class="difficulty-badge" :class="`difficulty-${difficulty}`">{{ label }}</span>
</template>
