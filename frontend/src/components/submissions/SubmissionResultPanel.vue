<script setup lang="ts">
import SubmissionStatusBadge from './SubmissionStatusBadge.vue'
import type { SubmissionDetail, SubmissionSummary } from '@/types/submission'

defineProps<{
  submission: SubmissionSummary | null
  detail: SubmissionDetail | null
  polling: boolean
  timedOut: boolean
  error: string
}>()

defineEmits<{ resume: [] }>()

function memoryLabel(value: number | null): string {
  if (value === null) return '—'
  if (value >= 1024) return `${(value / 1024).toFixed(1)} MB`
  return `${value} KB`
}
</script>

<template>
  <section class="judge-result" aria-live="polite">
    <header class="judge-result-header">
      <div>
        <span>JUDGE RESULT</span>
        <h3>{{ submission?.mode === 'sample' ? '公开样例运行' : '正式提交' }}</h3>
      </div>
      <SubmissionStatusBadge v-if="submission" :status="submission.status" />
      <span v-else class="result-idle">等待运行</span>
    </header>

    <div v-if="submission" class="judge-metrics">
      <div><span>耗时</span><strong>{{ submission.time_used_ms ?? '—' }}<small v-if="submission.time_used_ms !== null"> ms</small></strong></div>
      <div><span>内存</span><strong>{{ memoryLabel(submission.memory_used_kb) }}</strong></div>
      <div><span>通过用例</span><strong>{{ submission.passed_case_count }} / {{ submission.total_case_count || '—' }}</strong></div>
    </div>

    <p v-if="polling" class="judge-progress-copy">判题服务正在处理，页面可安全切换后再返回。</p>
    <div v-if="error" class="judge-poll-error">
      <span>{{ error }}</span>
      <button
        v-if="timedOut || !polling"
        class="judge-resume-button"
        type="button"
        @click="$emit('resume')"
      >继续查询</button>
    </div>

    <div v-if="detail?.compiler_output" class="diagnostic-block">
      <span>编译输出</span><pre><code>{{ detail.compiler_output }}</code></pre>
    </div>
    <div v-if="detail?.error_message" class="diagnostic-block">
      <span>诊断信息</span><pre><code>{{ detail.error_message }}</code></pre>
    </div>
    <div v-if="detail?.mode === 'sample' && detail.sample_output !== null" class="diagnostic-block">
      <span>程序输出</span><pre><code>{{ detail.sample_output || '（无输出）' }}</code></pre>
    </div>
    <RouterLink
      v-if="submission"
      class="submission-detail-link"
      :to="`/submissions/${submission.id}`"
    >查看提交详情 →</RouterLink>
  </section>
</template>
