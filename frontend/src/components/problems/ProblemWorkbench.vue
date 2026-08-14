<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'

import SubmissionResultPanel from '@/components/submissions/SubmissionResultPanel.vue'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useEditorStore } from '@/stores/editor'
import { useSubmissionStore } from '@/stores/submissions'
import { useUiStore } from '@/stores/ui'
import { isTerminalSubmission } from '@/types/submission'
import type { ProblemDetail } from '@/types/problem'
import type { SubmissionMode } from '@/types/submission'

const props = defineProps<{ problem: ProblemDetail }>()

const LazyCodeEditor = defineAsyncComponent(
  () => import('@/components/editor/CodeEditor.vue'),
)
const auth = useAuthStore()
const editorStore = useEditorStore()
const submissionStore = useSubmissionStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()
const { languages, languagesLoading, languagesError, selectedLanguage, fontSize } =
  storeToRefs(editorStore)
const { current, currentDetail, submitting, polling, pollTimedOut, pollError, busy } =
  storeToRefs(submissionStore)
const sourceCode = ref('')
const initialized = ref(false)
let saveTimer: ReturnType<typeof setTimeout> | null = null

const draftUserId = computed(() => auth.user?.id ?? 'anonymous')
const language = computed(() =>
  languages.value.find((item) => item.slug === selectedLanguage.value),
)
const monacoLanguage = computed(() => language.value?.monaco_language ?? selectedLanguage.value)
const modelId = computed(
  () => `${draftUserId.value}/${props.problem.id}/${selectedLanguage.value}`,
)
const modeHint = computed(() => selectedLanguage.value === 'javascript-v8'
  ? 'V8 兼容模式：readline() 逐行读取，EOF 返回 undefined；print() 按空格连接并换行。require/process/Buffer 不可用。'
  : 'Node.js 模式：使用 fs.readFileSync(0, \'utf8\') 读取 stdin；没有浏览器 DOM。')

function starterCode(languageSlug: string): string | null {
  return languageSlug === 'javascript-v8'
    ? props.problem.starter_code_v8
    : props.problem.starter_code_nodejs
}

function restoreDraft(): void {
  sourceCode.value = editorStore.loadDraft(
    draftUserId.value,
    props.problem.id,
    selectedLanguage.value,
    starterCode(selectedLanguage.value),
  )
}

function saveDraft(showMessage = false): void {
  editorStore.saveDraft(
    draftUserId.value,
    props.problem.id,
    selectedLanguage.value,
    sourceCode.value,
  )
  if (showMessage) ElMessage.success('草稿已保存到本地')
}

function clearDraft(): void {
  sourceCode.value = editorStore.clearDraft(
    draftUserId.value,
    props.problem.id,
    selectedLanguage.value,
    starterCode(selectedLanguage.value),
  )
  ElMessage.success('当前语言草稿已清空')
}

async function execute(mode: SubmissionMode): Promise<void> {
  if (!auth.isAuthenticated || !auth.user) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  if (!sourceCode.value.trim() || busy.value) return
  saveDraft()
  try {
    await submissionStore.submitAndPoll(
      {
        problem_id: props.problem.id,
        language: selectedLanguage.value,
        source_code: sourceCode.value,
        mode,
      },
      auth.user.id,
    )
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '提交失败，请稍后重试'))
  }
}

function resumePolling(): void {
  if (auth.user) submissionStore.resumePolling(auth.user.id, props.problem.id)
}

function handleOnline(): void {
  if (auth.user) resumePolling()
}

function handleVisibility(): void {
  if (
    document.visibilityState === 'visible'
    && auth.user
    && current.value
    && !isTerminalSubmission(current.value.status)
  ) {
    resumePolling()
  }
}

watch(selectedLanguage, (next, previous) => {
  if (!initialized.value || next === previous) return
  if (previous) {
    editorStore.saveDraft(draftUserId.value, props.problem.id, previous, sourceCode.value)
  }
  restoreDraft()
})

watch(sourceCode, () => {
  if (!initialized.value) return
  if (saveTimer !== null) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => saveDraft(), 500)
})

onMounted(async () => {
  await editorStore.loadLanguages()
  restoreDraft()
  initialized.value = true
  if (auth.user) submissionStore.resumeActive(auth.user.id, props.problem.id)
  window.addEventListener('online', handleOnline)
  document.addEventListener('visibilitychange', handleVisibility)
})

onBeforeUnmount(() => {
  if (saveTimer !== null) clearTimeout(saveTimer)
  if (initialized.value) saveDraft()
  submissionStore.stopPolling()
  window.removeEventListener('online', handleOnline)
  document.removeEventListener('visibilitychange', handleVisibility)
})
</script>

<template>
  <section class="problem-workbench">
    <header class="workbench-toolbar">
      <div class="workbench-selectors">
        <el-select
          v-model="selectedLanguage"
          aria-label="编程语言"
          :loading="languagesLoading"
          :disabled="busy"
        >
          <el-option
            v-for="item in languages"
            :key="item.id"
            :label="`${item.display_name} ${item.version}`"
            :value="item.slug"
          />
        </el-select>
        <el-select v-model="fontSize" aria-label="编辑器字体大小">
          <el-option v-for="size in [12, 14, 16, 18, 20, 22]" :key="size" :label="`${size}px`" :value="size" />
        </el-select>
        <el-select :model-value="ui.theme" aria-label="编辑器主题" @update:model-value="ui.setTheme">
          <el-option label="浅色" value="light" />
          <el-option label="深色" value="dark" />
        </el-select>
      </div>
      <div class="draft-actions">
        <button type="button" @click="saveDraft(true)">保存草稿</button>
        <button type="button" @click="clearDraft">清空</button>
      </div>
    </header>

    <p v-if="languagesError" class="workbench-error">{{ languagesError }}</p>
    <el-alert class="editor-mode-hint" type="info" :closable="false" :title="modeHint" show-icon />
    <div class="editor-frame">
      <Suspense>
        <LazyCodeEditor
          v-if="language"
          v-model="sourceCode"
          :language="monacoLanguage"
          :theme="ui.theme"
          :font-size="fontSize"
          :model-id="modelId"
          @save="saveDraft(true)"
          @run-sample="execute('sample')"
          @submit="execute('judge')"
        />
        <template #fallback>
          <div class="editor-loading" aria-busy="true">正在加载代码编辑器…</div>
        </template>
      </Suspense>
    </div>

    <div class="editor-shortcuts">
      <span><kbd>Ctrl/⌘ S</kbd> 保存草稿</span>
      <span><kbd>Ctrl/⌘ Enter</kbd> 运行样例</span>
      <span><kbd>Ctrl/⌘ Shift Enter</kbd> 正式提交</span>
      <span><kbd>Shift Alt F</kbd> 格式化</span>
    </div>

    <div class="judge-actions">
      <el-button :disabled="busy || !language" :loading="submitting && current?.mode !== 'judge'" @click="execute('sample')">
        运行公开样例
      </el-button>
      <el-button type="primary" :disabled="busy || !language" :loading="submitting && current?.mode === 'judge'" @click="execute('judge')">
        正式提交
      </el-button>
    </div>

    <SubmissionResultPanel
      :submission="current"
      :detail="currentDetail"
      :polling="polling"
      :timed-out="pollTimedOut"
      :error="pollError"
      @resume="resumePolling"
    />
  </section>
</template>
