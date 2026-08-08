<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <section class="hero page-container">
    <div class="hero-copy">
      <p class="eyebrow">REAL INPUT. REAL OUTPUT. REAL INTERVIEW.</p>
      <h1>把每一次刷题，<br /><span>练成真实笔试。</span></h1>
      <p class="hero-description">
        不写函数签名，不依赖隐藏魔法。直接读取 stdin、输出 stdout，在接近企业笔试与竞赛的环境里训练完整解题能力。
      </p>
      <div class="hero-actions">
        <RouterLink class="hero-primary" :to="auth.isAuthenticated ? '/profile' : '/register'">
          {{ auth.isAuthenticated ? '查看训练档案' : '创建免费账号' }}
        </RouterLink>
        <a class="hero-secondary" href="#workflow">了解判题流程</a>
      </div>
      <div class="language-strip" aria-label="计划支持的语言">
        <span>Python</span><span>C++</span><span>Java</span><span>Go</span><span>Node.js</span>
      </div>
    </div>

    <div class="terminal-card" aria-label="ACM 输入输出代码示例">
      <div class="terminal-titlebar">
        <span class="terminal-dots"><i></i><i></i><i></i></span>
        <span>main.py</span>
        <span class="terminal-status">ACM</span>
      </div>
      <pre><code><span class="code-muted"># 读取标准输入</span>
a, b = map(int, input().split())

<span class="code-muted"># 输出标准答案</span>
print(a + b)</code></pre>
      <div class="terminal-result">
        <span class="result-label">运行结果</span>
        <strong>Accepted</strong>
        <span>8 ms · 6.2 MB</span>
      </div>
    </div>
  </section>

  <section id="workflow" class="workflow-section">
    <div class="page-container">
      <p class="section-kicker">训练闭环</p>
      <h2>从一道题，到一份可信的答案</h2>
      <div class="workflow-grid">
        <article><span>01</span><h3>理解输入输出</h3><p>像真实笔试一样处理多组数据、边界条件与格式细节。</p></article>
        <article><span>02</span><h3>独立编译运行</h3><p>每次提交进入隔离判题环境，严格限制时间与内存。</p></article>
        <article><span>03</span><h3>积累能力画像</h3><p>沉淀通过率、薄弱标签和企业高频题训练进度。</p></article>
      </div>
    </div>
  </section>
</template>

