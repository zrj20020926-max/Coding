<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'

import { useEditorStore } from '@/stores/editor'
import type { GuideCodeExample } from '@/types/guide'
import { copyText } from '@/utils/clipboard'

const props = defineProps<{ example: GuideCodeExample }>()
const router = useRouter()
const editorStore = useEditorStore()
const copied = ref(false)
let copiedTimer: ReturnType<typeof setTimeout> | null = null

async function handleCopy(): Promise<void> {
  try {
    await copyText(props.example.code)
    copied.value = true
    if (copiedTimer !== null) clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => { copied.value = false }, 1800)
  } catch {
    ElMessage.error('复制失败，请选中代码后手动复制')
  }
}

async function openWorkbench(): Promise<void> {
  if (props.example.variant === 'incorrect') return
  editorStore.queueGuideImport(
    props.example.targetSlug,
    props.example.runtime,
    props.example.code,
  )
  await router.push({ name: 'problem-detail', params: { slug: props.example.targetSlug } })
}

onBeforeUnmount(() => {
  if (copiedTimer !== null) clearTimeout(copiedTimer)
})
</script>

<template>
  <section
    class="guide-code-card"
    :class="{ 'is-incorrect': example.variant === 'incorrect' }"
    :aria-label="example.title"
  >
    <header>
      <div>
        <span class="guide-runtime-badge" :class="`runtime-${example.runtime}`">
          {{ example.runtime === 'javascript-v8' ? 'JavaScript V8' : 'Node.js' }}
        </span>
        <strong>{{ example.title }}</strong>
      </div>
      <div class="guide-code-actions">
        <button type="button" :aria-label="`复制 ${example.title} 代码`" @click="handleCopy">
          {{ copied ? '已复制' : '复制' }}
        </button>
        <button
          v-if="example.variant !== 'incorrect'"
          type="button"
          :aria-label="`将 ${example.title} 带入训练工作台`"
          @click="openWorkbench"
        >
          带入工作台
        </button>
      </div>
    </header>
    <pre><code>{{ example.code }}</code></pre>
    <p v-if="example.note" class="guide-code-note">{{ example.note }}</p>
  </section>
</template>
