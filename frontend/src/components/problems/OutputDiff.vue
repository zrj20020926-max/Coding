<script setup lang="ts">
import { computed } from 'vue'

import { splitVisibleOutput, summarizeOutputDiff } from '@/utils/outputDiff'

const props = defineProps<{
  expected: string
  actual: string
}>()

const expectedLines = computed(() => splitVisibleOutput(props.expected))
const actualLines = computed(() => splitVisibleOutput(props.actual))
const summary = computed(() => summarizeOutputDiff(props.expected, props.actual))
const rowCount = computed(() => Math.max(expectedLines.value.length, actualLines.value.length))

function endingMarker(ending: 'LF' | 'CRLF' | 'CR' | 'NONE'): string {
  if (ending === 'CRLF') return '␍␊'
  if (ending === 'CR') return '␍'
  if (ending === 'LF') return '␊'
  return '∅ EOL'
}
</script>

<template>
  <section class="output-diff" data-testid="output-diff">
    <header>
      <strong>输出差异</strong>
      <span
        :class="summary.rawEqual ? 'is-match' : summary.checkerEquivalent ? 'is-equivalent' : 'is-mismatch'"
      >{{ summary.message }}</span>
    </header>
    <p class="output-diff-legend">可视符号：空格 <code>·</code> · Tab <code>⇥</code> · LF <code>␊</code> · CRLF <code>␍␊</code></p>
    <div class="output-diff-grid" role="table" aria-label="期望输出与实际输出逐行对比">
      <div class="output-diff-heading" role="columnheader">期望输出</div>
      <div class="output-diff-heading" role="columnheader">实际输出</div>
      <template v-for="index in rowCount" :key="index">
        <pre
          :class="{ 'is-missing': !expectedLines[index - 1], 'is-different': expectedLines[index - 1]?.raw !== actualLines[index - 1]?.raw }"
          role="cell"
        ><code>{{ expectedLines[index - 1]?.visibleContent ?? '⊘ 缺少此行' }}<b v-if="expectedLines[index - 1]">{{ endingMarker(expectedLines[index - 1]!.ending) }}</b></code></pre>
        <pre
          :class="{ 'is-missing': !actualLines[index - 1], 'is-different': expectedLines[index - 1]?.raw !== actualLines[index - 1]?.raw }"
          role="cell"
        ><code>{{ actualLines[index - 1]?.visibleContent ?? '⊘ 缺少此行' }}<b v-if="actualLines[index - 1]">{{ endingMarker(actualLines[index - 1]!.ending) }}</b></code></pre>
      </template>
    </div>
  </section>
</template>
