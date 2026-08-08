<script setup lang="ts">
import { computed } from 'vue'

import { renderSafeMarkdown } from '@/utils/markdown'

const props = defineProps<{ content: string }>()
const safeHtml = computed(() => renderSafeMarkdown(props.content))
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="markdown-content" v-html="safeHtml"></div>
</template>
