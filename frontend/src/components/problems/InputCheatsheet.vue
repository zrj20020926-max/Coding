<script setup lang="ts">
defineProps<{ runtime: 'javascript-v8' | 'nodejs' }>()
</script>

<template>
  <el-collapse class="input-cheatsheet" aria-label="输入解析速查">
    <el-collapse-item title="输入解析速查" name="cheatsheet">
      <div v-if="runtime === 'javascript-v8'" class="cheatsheet-grid">
        <article><strong>单行</strong><code>const line = readline();</code></article>
        <article><strong>多行 / EOF</strong><code>for (let s; (s = readline()) !== undefined;) lines.push(s);</code></article>
        <article><strong>T 组</strong><code>const T = Number(readline()); for (let i = 0; i &lt; T; i++) { /* ... */ }</code></article>
        <article><strong>数组</strong><code>const a = readline().trim().split(/\s+/).map(Number);</code></article>
        <article><strong>矩阵</strong><code>const row = readline().trim().split(/\s+/).map(Number);</code></article>
        <article><strong>BigInt</strong><code>const n = BigInt(readline().trim()); print(n.toString());</code></article>
      </div>
      <div v-else class="cheatsheet-grid">
        <article><strong>原始字符串</strong><code>const raw = fs.readFileSync(0, 'utf8');</code></article>
        <article><strong>trim / trimEnd</strong><code>trim() 去掉两端空白；trimEnd() 只去末尾。</code></article>
        <article><strong>按 token</strong><code>const tokens = raw.trim().split(/\s+/);</code></article>
        <article><strong>按行</strong><code>const lines = raw.split(/\r?\n/);</code></article>
        <article><strong>游标 Scanner</strong><code>let i = 0; const next = () =&gt; tokens[i++];</code></article>
        <article><strong>BigInt / 高性能</strong><code>const n = BigInt(next()); const out = []; process.stdout.write(out.join('\n'));</code></article>
      </div>
    </el-collapse-item>
  </el-collapse>
</template>
