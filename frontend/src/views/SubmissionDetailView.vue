<script setup lang="ts">
import { computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import AIAnalysisPanel from '@/components/submissions/AIAnalysisPanel.vue'
import SubmissionStatusBadge from '@/components/submissions/SubmissionStatusBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { useEditorStore } from '@/stores/editor'
import { useSubmissionStore } from '@/stores/submissions'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const editorStore = useEditorStore()
const store = useSubmissionStore()
const { detail, detailLoading, detailError } = storeToRefs(store)
const submissionId = computed(() => String(route.params['id'] ?? ''))
const analyzableStatuses = new Set([
  'Wrong Answer',
  'Compile Error',
  'Runtime Error',
  'Time Limit Exceeded',
  'Memory Limit Exceeded',
])

function load(): void {
  if (submissionId.value) void store.loadDetail(submissionId.value)
}

async function useCodeAgain(): Promise<void> {
  if (!detail.value || !auth.user) return
  editorStore.selectedLanguage = detail.value.language.slug
  editorStore.saveDraft(
    auth.user.id,
    detail.value.problem.id,
    detail.value.language.slug,
    detail.value.source_code,
  )
  await router.push(`/problems/${detail.value.problem.slug}`)
}

watch(submissionId, load, { immediate: true })
</script>

<template>
  <section class="submission-detail-page page-container">
    <nav class="problem-breadcrumb">
      <RouterLink to="/submissions">提交记录</RouterLink><span>/</span><span>{{ submissionId.slice(0, 8) }}</span>
    </nav>
    <div v-if="detailLoading" class="detail-skeleton" aria-busy="true">
      <span v-for="index in 7" :key="index" class="skeleton-block detail-line-skeleton"></span>
    </div>
    <section v-else-if="detailError" class="detail-feedback">
      <el-result icon="error" title="提交详情加载失败" :sub-title="detailError">
        <template #extra><el-button type="primary" @click="load">重试</el-button></template>
      </el-result>
    </section>
    <article v-else-if="detail" class="submission-detail-card">
      <header>
        <div>
          <p>{{ detail.mode === 'sample' ? '公开样例运行' : '正式提交' }}</p>
          <h1>{{ detail.problem.title }}</h1>
          <span>{{ detail.language.display_name }} {{ detail.language.version }} · {{ new Date(detail.created_at).toLocaleString('zh-CN') }}</span>
        </div>
        <SubmissionStatusBadge :status="detail.status" />
      </header>
      <div class="submission-detail-metrics">
        <div><span>耗时</span><strong>{{ detail.time_used_ms ?? '—' }} ms</strong></div>
        <div><span>内存</span><strong>{{ detail.memory_used_kb ?? '—' }} KB</strong></div>
        <div><span>通过用例</span><strong>{{ detail.passed_case_count }} / {{ detail.total_case_count }}</strong></div>
        <div><span>得分</span><strong>{{ detail.score }}</strong></div>
      </div>
      <section v-if="detail.compiler_output" class="submission-code-block">
        <h2>编译输出</h2><pre><code>{{ detail.compiler_output }}</code></pre>
      </section>
      <section v-if="detail.error_message" class="submission-code-block">
        <h2>诊断信息</h2><pre><code>{{ detail.error_message }}</code></pre>
      </section>
      <section v-if="detail.mode === 'sample' && detail.sample_output !== null" class="submission-code-block">
        <h2>程序输出</h2><pre><code>{{ detail.sample_output || '（无输出）' }}</code></pre>
      </section>
      <AIAnalysisPanel
        v-if="analyzableStatuses.has(detail.status)"
        :submission-id="detail.id"
      />
      <section class="submission-code-block">
        <div class="submission-code-heading"><h2>提交代码</h2><el-button @click="useCodeAgain">载入编辑器</el-button></div>
        <pre><code>{{ detail.source_code }}</code></pre>
      </section>
    </article>
  </section>
</template>
