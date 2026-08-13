<script setup lang="ts">
import { onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { useAIAnalysisStore } from '@/stores/aiAnalyses'

const props = defineProps<{ submissionId: string }>()
const store = useAIAnalysisStore()
const { analysis, quota, loading, requesting, error } = storeToRefs(store)

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
        <h2 id="ai-analysis-title">AI 代码分析</h2>
      </div>
      <button
        v-if="!loading && (!analysis || analysis.status === 'failed')"
        class="primary-button ai-analysis-button"
        :disabled="requesting"
        @click="store.request(submissionId)"
      >{{ requesting ? '请求中…' : analysis?.status === 'failed' ? '重新分析' : '开始分析' }}</button>
    </header>

    <div class="ai-analysis-warning" role="alert">
      AI 建议可能不准确，请结合题面、样例和自己的推理判断。
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
      AI 正在分析，失败不会影响本次判题结果…
    </div>
    <div v-else-if="analysis?.status === 'failed'" class="ai-analysis-error" role="alert">
      {{ analysis.error_code === 'AI_PROVIDER_NOT_CONFIGURED'
        ? 'AI 分析暂未配置'
        : (analysis.error_message || 'AI 分析暂时不可用，请稍后重新分析。') }}
    </div>
    <div v-else-if="analysis?.status === 'completed'" class="ai-analysis-result">
      <div class="ai-complexity-grid">
        <div><span>时间复杂度</span><strong>{{ analysis.time_complexity }}</strong></div>
        <div><span>空间复杂度</span><strong>{{ analysis.space_complexity }}</strong></div>
        <div><span>置信度</span><strong>{{ analysis.confidence ?? '—' }}</strong></div>
      </div>
      <section>
        <h3>可能的失败原因</h3>
        <p>{{ analysis.failure_reason }}</p>
      </section>
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
    <p v-else class="ai-analysis-empty">需要时可主动请求分析；源码不会在浏览器中执行。</p>
  </section>
</template>
