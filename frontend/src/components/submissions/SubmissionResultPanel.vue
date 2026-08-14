<script setup lang="ts">
import OutputDiff from '@/components/problems/OutputDiff.vue'
import SubmissionStatusBadge from './SubmissionStatusBadge.vue'
import type { SubmissionDetail, SubmissionSummary } from '@/types/submission'

defineProps<{
  submission: SubmissionSummary | null
  detail: SubmissionDetail | null
  expectedOutput?: string | null
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

function modeLabel(mode: SubmissionSummary['mode'] | undefined): string {
  if (mode === 'sample') return '公开样例运行'
  if (mode === 'custom') return '自定义输入运行'
  if (mode === 'judge') return '正式提交'
  return '运行结果'
}
</script>

<template>
  <section class="judge-result" aria-live="polite">
    <header class="judge-result-header">
      <div>
        <span>JUDGE RESULT</span>
        <h3>{{ modeLabel(submission?.mode) }}</h3>
      </div>
      <SubmissionStatusBadge v-if="submission" :status="submission.status" />
      <span v-else class="result-idle">等待运行</span>
    </header>

    <div v-if="submission" class="judge-metrics">
      <div><span>耗时</span><strong>{{ submission.time_used_ms ?? '—' }}<small v-if="submission.time_used_ms !== null"> ms</small></strong></div>
      <div><span>内存</span><strong>{{ memoryLabel(submission.memory_used_kb) }}</strong></div>
      <div><span>通过用例</span><strong>{{ submission.passed_case_count }} / {{ submission.total_case_count || '—' }}</strong></div>
    </div>

    <p v-if="polling" class="judge-progress-copy">代码正在独立 Judge 沙箱中运行，切换页面后仍可恢复查询。</p>
    <div v-if="submission?.status === 'System Error'" class="judge-system-error" role="alert">
      平台判题环境暂时异常，不代表你的代码有误。本次结果不会计入训练进度。
    </div>
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
      <span>受控诊断</span><pre><code>{{ detail.error_message }}</code></pre>
    </div>
    <div v-if="detail && detail.mode !== 'judge' && detail.sample_output !== null" class="result-output-grid">
      <div v-if="expectedOutput !== null && expectedOutput !== undefined" class="diagnostic-block">
        <span>期望 stdout</span><pre><code>{{ expectedOutput || '（无输出）' }}</code></pre>
      </div>
      <div class="diagnostic-block">
        <span>实际 stdout</span><pre><code>{{ detail?.sample_output || '（无输出）' }}</code></pre>
      </div>
    </div>
    <OutputDiff
      v-if="detail?.mode === 'sample' && detail.sample_output !== null && expectedOutput !== null && expectedOutput !== undefined"
      :expected="expectedOutput"
      :actual="detail.sample_output"
    />
    <p v-if="detail?.mode === 'judge'" class="hidden-cases-notice">
      正式提交只展示汇总结果；隐藏测试输入和标准输出不会返回浏览器。
    </p>
    <RouterLink
      v-if="submission"
      class="submission-detail-link"
      :to="`/submissions/${submission.id}`"
    >查看提交详情 →</RouterLink>
  </section>
</template>
