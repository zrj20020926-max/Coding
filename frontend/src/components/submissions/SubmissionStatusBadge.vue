<script setup lang="ts">
import { computed } from 'vue'
import type { SubmissionStatus } from '@/types/submission'

const props = defineProps<{ status: SubmissionStatus }>()

const labels: Record<SubmissionStatus, string> = {
  Pending: '等待判题',
  Compiling: '编译中',
  Running: '运行中',
  Accepted: '通过',
  'Wrong Answer': '答案错误',
  'Compile Error': '编译错误',
  'Runtime Error': '运行错误',
  'Time Limit Exceeded': '超出时间限制',
  'Memory Limit Exceeded': '超出内存限制',
  'System Error': '系统错误',
}

const tone = computed(() => {
  if (props.status === 'Accepted') return 'success'
  if (['Pending', 'Compiling', 'Running'].includes(props.status)) return 'progress'
  if (props.status === 'System Error') return 'system'
  return 'failure'
})
</script>

<template>
  <span class="submission-status" :class="`submission-status-${tone}`">
    <i v-if="tone === 'progress'" aria-hidden="true"></i>{{ labels[status] }}
  </span>
</template>
