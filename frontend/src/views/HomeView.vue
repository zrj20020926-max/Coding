<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import DailyChallengeCard from '@/components/content/DailyChallengeCard.vue'

const auth = useAuthStore()
</script>

<template>
  <section class="hero page-container">
    <div class="hero-copy">
      <p class="eyebrow">JAVASCRIPT · STDIN · STDOUT</p>
      <h1>JavaScript ACM<br /><span>输入输出专项训练。</span></h1>
      <p class="hero-description">
        不把复杂算法当作门槛，专注练会 stdin 输入解析与 stdout 输出格式，覆盖常见输入结构和边界情况。
      </p>
      <div class="hero-actions">
        <RouterLink class="hero-primary" :to="auth.isAuthenticated ? '/profile' : '/register'">
          {{ auth.isAuthenticated ? '查看训练档案' : '创建免费账号' }}
        </RouterLink>
        <a class="hero-secondary" href="#workflow">了解判题流程</a>
      </div>
      <div class="language-strip" aria-label="判题语言支持状态">
        <span class="language-current">JavaScript V8 · 当前支持</span>
        <span class="language-current">Node.js 22 · 当前支持</span>
      </div>
    </div>

    <div class="terminal-card" aria-label="ACM 输入输出代码示例">
      <div class="terminal-titlebar">
        <span class="terminal-dots"><i></i><i></i><i></i></span>
        <span>main.js</span>
        <span class="terminal-status">V8</span>
      </div>
      <pre><code><span class="code-muted">// V8：逐行读取标准输入</span>
const [a, b] = readline().trim().split(/\s+/).map(Number);

<span class="code-muted">// 输出到 stdout</span>
print(a + b);</code></pre>
      <div class="terminal-result">
        <span class="result-label">运行结果</span>
        <strong>Accepted</strong>
        <span>8 ms · 6.2 MB</span>
      </div>
    </div>
  </section>

  <DailyChallengeCard />

  <section id="workflow" class="workflow-section">
    <div class="page-container">
      <p class="section-kicker">训练闭环</p>
      <h2>从看懂输入，到稳定输出</h2>
      <div class="workflow-grid">
        <article><span>01</span><h3>识别输入结构</h3><p>练习单值、多行、T 组、EOF、哨兵、矩阵与混合格式。</p></article>
        <article><span>02</span><h3>分清两种模式</h3><p>V8 使用 readline/print；Node.js 使用 fs 与标准输出 API。</p></article>
        <article><span>03</span><h3>消灭格式错误</h3><p>通过真实 Judge 检查空行、分隔符、多余输出和边界解析。</p></article>
      </div>
    </div>
  </section>
</template>
