<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'

import InputCheatsheet from '@/components/problems/InputCheatsheet.vue'
import SubmissionResultPanel from '@/components/submissions/SubmissionResultPanel.vue'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { starterCodeVersion, useEditorStore } from '@/stores/editor'
import { useSubmissionStore } from '@/stores/submissions'
import { useUiStore } from '@/stores/ui'
import { isTerminalSubmission } from '@/types/submission'
import type { ExerciseDetail } from '@/types/course'
import type { ProblemDetail } from '@/types/problem'
import type { SubmissionMode } from '@/types/submission'

type RuntimeSlug = 'javascript-v8' | 'nodejs'

const props = defineProps<{
  problem: ProblemDetail
  exercise?: ExerciseDetail | null
}>()

const CUSTOM_INPUT_MAX_BYTES = 256 * 1024
const LazyCodeEditor = defineAsyncComponent(() => import('@/components/editor/CodeEditor.vue'))
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
const customInput = ref('')
const templateChanged = ref(false)
const initialized = ref(false)
let saveTimer: ReturnType<typeof setTimeout> | null = null
let inputSaveTimer: ReturnType<typeof setTimeout> | null = null

const draftUserId = computed(() => auth.user?.id ?? 'anonymous')
const exerciseId = computed(() => props.exercise?.id ?? props.problem.id)
const runtime = computed<RuntimeSlug>(() =>
  selectedLanguage.value === 'nodejs' ? 'nodejs' : 'javascript-v8',
)
const language = computed(() => languages.value.find((item) => item.slug === runtime.value))
const monacoLanguage = computed(() => language.value?.monaco_language ?? 'javascript')
const currentStarter = computed(() => starterFor(runtime.value))
const currentStarterVersion = computed(() => starterCodeVersion(currentStarter.value))
const modelId = computed(
  () => `${draftUserId.value}/${exerciseId.value}/${runtime.value}/${currentStarterVersion.value}`,
)
const modeHint = computed(() => runtime.value === 'javascript-v8'
  ? 'JavaScript V8：readline() 每次读取一行，EOF 返回 undefined；print(...args) 以空格连接并换行。require、process、Buffer 不可用。'
  : "Node.js：使用 fs.readFileSync(0, 'utf8') 读取原始 stdin；可用 console.log() 和 process.stdout.write()，无浏览器 DOM。")
const inputBytes = computed(() => new TextEncoder().encode(customInput.value).byteLength)
const inputTooLarge = computed(() => inputBytes.value > CUSTOM_INPUT_MAX_BYTES)
const inputLineCount = computed(() => {
  if (customInput.value === '') return 0
  return customInput.value.split(/\r\n|\r|\n/).length
})
const finalNewlineLabel = computed(() => {
  if (customInput.value === '') return '空输入（0 字节）'
  if (customInput.value.endsWith('\r\n')) return '末尾换行：CRLF'
  if (customInput.value.endsWith('\n')) return '末尾换行：LF'
  if (customInput.value.endsWith('\r')) return '末尾换行：CR'
  return '末尾无换行'
})
const expectedOutput = computed(() =>
  current.value?.mode === 'sample' ? props.problem.sample_output : null,
)

function starterFor(runtimeSlug: RuntimeSlug): string {
  if (runtimeSlug === 'javascript-v8') {
    return props.exercise?.starter_code_v8
      || props.problem.starter_code_v8
      || 'const line = readline();\n// 在这里处理输入\nprint(line);\n'
  }
  return props.exercise?.starter_code_nodejs
    || props.problem.starter_code_nodejs
    || "const fs = require('fs');\n\nconst input = fs.readFileSync(0, 'utf8');\n// 在这里处理输入\nconsole.log(input);\n"
}

function versionFor(runtimeSlug: RuntimeSlug): string {
  return starterCodeVersion(starterFor(runtimeSlug))
}

function saveRuntime(runtimeSlug: RuntimeSlug): void {
  editorStore.saveDraft(
    draftUserId.value,
    exerciseId.value,
    runtimeSlug,
    versionFor(runtimeSlug),
    sourceCode.value,
  )
  editorStore.saveCustomInput(
    draftUserId.value,
    exerciseId.value,
    runtimeSlug,
    versionFor(runtimeSlug),
    customInput.value,
  )
}

function restoreRuntime(runtimeSlug: RuntimeSlug): void {
  const version = versionFor(runtimeSlug)
  const restored = editorStore.loadDraft(
    draftUserId.value,
    exerciseId.value,
    runtimeSlug,
    version,
    starterFor(runtimeSlug),
  )
  sourceCode.value = restored.source
  templateChanged.value = restored.templateChanged
  customInput.value = editorStore.loadCustomInput(
    draftUserId.value,
    exerciseId.value,
    runtimeSlug,
    version,
    props.problem.sample_input,
  )
}

function saveDraft(showMessage = false): void {
  saveRuntime(runtime.value)
  if (showMessage) ElMessage.success('代码和自定义输入已保存到本地')
}

function useLatestStarter(): void {
  sourceCode.value = editorStore.clearDraft(
    draftUserId.value,
    exerciseId.value,
    runtime.value,
    currentStarterVersion.value,
    currentStarter.value,
  )
  templateChanged.value = false
  ElMessage.success('已切换到最新初始模板')
}

function clearDraft(): void {
  sourceCode.value = editorStore.clearDraft(
    draftUserId.value,
    exerciseId.value,
    runtime.value,
    currentStarterVersion.value,
    currentStarter.value,
  )
  templateChanged.value = false
  ElMessage.success('当前运行模式的草稿已清空')
}

function clearInput(): void {
  customInput.value = editorStore.clearCustomInput(
    draftUserId.value,
    exerciseId.value,
    runtime.value,
    currentStarterVersion.value,
    customInput.value,
  )
}

function copySampleInput(): void {
  editorStore.clearCustomInput(
    draftUserId.value,
    exerciseId.value,
    runtime.value,
    currentStarterVersion.value,
    customInput.value,
  )
  customInput.value = props.problem.sample_input
  editorStore.saveCustomInput(
    draftUserId.value,
    exerciseId.value,
    runtime.value,
    currentStarterVersion.value,
    customInput.value,
  )
}

function restoreInput(): void {
  customInput.value = editorStore.restoreCustomInput(
    draftUserId.value,
    exerciseId.value,
    runtime.value,
    currentStarterVersion.value,
    props.problem.sample_input,
  )
}

async function execute(mode: SubmissionMode): Promise<void> {
  if (!auth.isAuthenticated || !auth.user) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  if (!sourceCode.value.trim() || busy.value) return
  if (mode === 'custom' && inputTooLarge.value) {
    ElMessage.error(`自定义输入不能超过 ${CUSTOM_INPUT_MAX_BYTES / 1024} KiB`)
    return
  }
  saveDraft()
  try {
    const payload = {
      problem_id: props.problem.id,
      language: runtime.value,
      source_code: sourceCode.value,
      mode,
      ...(mode === 'custom' ? { custom_input: customInput.value } : {}),
    }
    await submissionStore.submitAndPoll(payload, auth.user.id)
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
  const previousRuntime: RuntimeSlug = previous === 'nodejs' ? 'nodejs' : 'javascript-v8'
  saveRuntime(previousRuntime)
  restoreRuntime(next === 'nodejs' ? 'nodejs' : 'javascript-v8')
})

watch(sourceCode, () => {
  if (!initialized.value) return
  if (saveTimer !== null) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => saveRuntime(runtime.value), 500)
})

watch(customInput, () => {
  if (!initialized.value) return
  if (inputSaveTimer !== null) clearTimeout(inputSaveTimer)
  inputSaveTimer = setTimeout(() => {
    editorStore.saveCustomInput(
      draftUserId.value,
      exerciseId.value,
      runtime.value,
      currentStarterVersion.value,
      customInput.value,
    )
  }, 300)
})

onMounted(async () => {
  await editorStore.loadLanguages()
  restoreRuntime(runtime.value)
  initialized.value = true
  if (auth.user) submissionStore.resumeActive(auth.user.id, props.problem.id)
  window.addEventListener('online', handleOnline)
  document.addEventListener('visibilitychange', handleVisibility)
})

onBeforeUnmount(() => {
  if (saveTimer !== null) clearTimeout(saveTimer)
  if (inputSaveTimer !== null) clearTimeout(inputSaveTimer)
  if (initialized.value) saveRuntime(runtime.value)
  submissionStore.stopPolling()
  window.removeEventListener('online', handleOnline)
  document.removeEventListener('visibilitychange', handleVisibility)
})
</script>

<template>
  <section class="problem-workbench" aria-label="JavaScript ACM 训练工作台">
    <header class="runtime-switcher">
      <div>
        <span>运行模式</span>
        <strong>{{ language?.display_name ?? 'JavaScript' }}</strong>
      </div>
      <el-radio-group v-model="selectedLanguage" :disabled="busy" aria-label="切换 JavaScript 运行模式">
        <el-radio-button value="javascript-v8">JavaScript V8</el-radio-button>
        <el-radio-button value="nodejs">Node.js</el-radio-button>
      </el-radio-group>
    </header>

    <el-alert v-if="languagesError" type="error" :closable="false" :title="languagesError" show-icon />
    <p v-if="languagesLoading" class="workbench-error" aria-live="polite">正在加载可用运行模式…</p>
    <el-alert class="editor-mode-hint" type="info" :closable="false" :title="modeHint" show-icon />
    <el-alert
      v-if="templateChanged"
      class="template-update-alert"
      type="warning"
      :closable="false"
      title="初始模板已更新；当前仍保留旧版本草稿，没有自动覆盖。"
      show-icon
    >
      <template #default><el-button size="small" @click="useLatestStarter">改用最新模板</el-button></template>
    </el-alert>

    <div class="workbench-toolbar">
      <div class="runtime-api-summary">
        <span>输入 API <code>{{ language?.input_api ?? (runtime === 'javascript-v8' ? 'readline()' : "fs.readFileSync(0, 'utf8')") }}</code></span>
        <span>输出 API <code>{{ language?.output_api ?? (runtime === 'javascript-v8' ? 'print(...args)' : 'console.log / process.stdout.write') }}</code></span>
      </div>
      <div class="workbench-selectors">
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
        <button type="button" @click="clearDraft">清空代码</button>
      </div>
    </div>

    <div class="editor-frame">
      <Suspense>
        <LazyCodeEditor
          v-if="language"
          :key="modelId"
          v-model="sourceCode"
          :language="monacoLanguage"
          :runtime="runtime"
          :theme="ui.theme"
          :font-size="fontSize"
          :model-id="modelId"
          @save="saveDraft(true)"
          @run-sample="execute('sample')"
          @run-custom="execute('custom')"
          @submit="execute('judge')"
        />
        <template #fallback>
          <div class="editor-loading" aria-busy="true">正在按需加载 Monaco Editor…</div>
        </template>
      </Suspense>
    </div>

    <div class="editor-shortcuts" aria-label="键盘快捷键">
      <span><kbd>Ctrl/⌘ S</kbd> 保存</span>
      <span><kbd>Ctrl/⌘ Enter</kbd> 运行样例</span>
      <span><kbd>Ctrl/⌘ Alt Enter</kbd> 自定义输入</span>
      <span><kbd>Ctrl/⌘ Shift Enter</kbd> 正式提交</span>
      <span><kbd>Shift Alt F</kbd> 格式化</span>
    </div>

    <section class="custom-input-panel">
      <header>
        <div><strong>自定义 stdin</strong><span>内容原样送入 Judge，不自动 trim，也不保存为隐藏测试。</span></div>
        <div class="custom-input-actions">
          <button type="button" @click="copySampleInput">复制公开样例</button>
          <button type="button" @click="clearInput">清空</button>
          <button type="button" @click="restoreInput">恢复</button>
        </div>
      </header>
      <el-input
        v-model="customInput"
        type="textarea"
        :rows="7"
        resize="vertical"
        aria-label="自定义标准输入"
        spellcheck="false"
        placeholder="可以留空；空行和末尾换行都会被保留"
      />
      <footer :class="{ 'is-over-limit': inputTooLarge }">
        <span>{{ inputLineCount }} 行 · {{ inputBytes }} / {{ CUSTOM_INPUT_MAX_BYTES }} 字节</span>
        <span>{{ finalNewlineLabel }}</span>
      </footer>
    </section>

    <InputCheatsheet :runtime="runtime" />

    <div class="judge-actions">
      <el-button :disabled="busy || !language" :loading="submitting && current?.mode === 'sample'" @click="execute('sample')">
        运行公开样例
      </el-button>
      <el-button :disabled="busy || !language || inputTooLarge" :loading="submitting && current?.mode === 'custom'" @click="execute('custom')">
        运行自定义输入
      </el-button>
      <el-button type="primary" :disabled="busy || !language" :loading="submitting && current?.mode === 'judge'" @click="execute('judge')">
        正式提交
      </el-button>
    </div>

    <SubmissionResultPanel
      :submission="current"
      :detail="currentDetail"
      :expected-output="expectedOutput"
      :polling="polling"
      :timed-out="pollTimedOut"
      :error="pollError"
      @resume="resumePolling"
    />
  </section>
</template>
