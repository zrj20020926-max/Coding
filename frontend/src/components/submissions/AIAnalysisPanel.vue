<script setup lang="ts">
import { computed, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { useAIAnalysisStore } from '@/stores/aiAnalyses'

const props = defineProps<{ submissionId: string }>()
const store = useAIAnalysisStore()
const { analysis, quota, loading, requesting, error } = storeToRefs(store)
const findings = computed(() => {
  if (!analysis.value) return []
  return [
    ['runtime_mismatch', '运行模式混用', analysis.value.runtime_mismatch],
    ['input_reading_issue', '标准输入读取', analysis.value.input_reading_issue],
    ['line_parsing_issue', '按行解析', analysis.value.line_parsing_issue],
    ['token_parsing_issue', 'Token 解析', analysis.value.token_parsing_issue],
    ['whitespace_issue', '空格与空行', analysis.value.whitespace_issue],
    ['eof_issue', 'EOF 处理', analysis.value.eof_issue],
    ['numeric_issue', 'Number / BigInt', analysis.value.numeric_issue],
    ['output_format_issue', '输出格式', analysis.value.output_format_issue],
    ['performance_issue', '大输入性能', analysis.value.performance_issue],
  ] as const
})

watch(
  () => props.submissionId,
  (id) => { if (id) void store.load(id) },
  { immediate: true },
)
onUnmounted(() => store.stopPolling())
</script>

<template>
  <section class="ai-analysis-panel" aria-labelledby="ai-analysis-title">
    <header>
      <div>
        <p>ADVISORY REVIEW</p>
        <h2 id="ai-analysis-title">AI 输入输出诊断</h2>
      </div>
      <button
        v-if="!loading && (!analysis || analysis.status === 'failed')"
        class="primary-button ai-analysis-button"
        :disabled="requesting"
        @click="store.request(submissionId)"
      >{{ requesting ? '请求中…' : analysis?.status === 'failed' ? '重新分析' : '开始分析' }}</button>
    </header>

    <div class="ai-analysis-warning" role="alert">
      AI 输入输出诊断可能不准确，仅检查 stdin/stdout 使用方式，不参与正式判题。
    </div>
    <p v-if="quota && quota.remaining >= 0" class="ai-quota">
      本周期剩余 {{ quota.remaining }} / {{ quota.limit }} 次
    </p>
    <div v-if="loading" class="ai-analysis-loading">正在检查已有分析…</div>
    <div v-else-if="error" class="ai-analysis-error" role="alert">{{ error }}</div>
    <div
      v-else-if="analysis?.status === 'pending' || analysis?.status === 'running'"
      class="ai-analysis-loading"
    >
      AI 正在诊断输入输出代码，失败不会影响本次判题结果…
    </div>
    <div v-else-if="analysis?.status === 'failed'" class="ai-analysis-error" role="alert">
      {{ analysis.error_code === 'AI_PROVIDER_NOT_CONFIGURED'
        ? 'AI 输入输出诊断暂未配置'
        : (analysis.error_message || 'AI 输入输出诊断暂时不可用，请稍后重试。') }}
    </div>
    <div v-else-if="analysis?.status === 'completed'" class="ai-analysis-result">
      <div class="ai-diagnostic-heading">
        <strong>诊断项目</strong><span>置信度：{{ analysis.confidence ?? '—' }}</span>
      </div>
      <div class="ai-diagnostic-grid">
        <article v-for="[key, label, finding] in findings" :key="key" :class="{ detected: finding?.detected }">
          <header><strong>{{ label }}</strong><span>{{ finding?.detected ? '需关注' : '未发现' }}</span></header>
          <p>{{ finding?.summary ?? '当前分析没有返回该项目。' }}</p>
        </article>
      </div>
      <section>
        <h3>改进建议</h3>
        <ol><li v-for="item in analysis.suggestions" :key="item">{{ item }}</li></ol>
      </section>
      <section>
        <h3>引导问题</h3>
        <ul><li v-for="item in analysis.guiding_questions" :key="item">{{ item }}</li></ul>
      </section>
      <p v-if="analysis.cached" class="ai-cache-note">本结果命中相同提交缓存，未再次调用模型。</p>
    </div>
    <p v-else class="ai-analysis-empty">需要时可主动请求输入输出诊断；该功能不执行源码，也不读取隐藏测试。</p>
  </section>
</template>
