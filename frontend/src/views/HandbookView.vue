<template>
  <section class="handbook-page page-container">
    <header class="problems-heading">
      <div><p class="eyebrow">JAVASCRIPT ACM CHEATSHEET</p><h1>速查手册</h1><p>只记住两套输入输出方式，避免在 V8 与 Node.js 之间混用 API。</p></div>
    </header>
    <div class="training-grid">
      <article class="profile-panel">
        <h2>JavaScript V8</h2>
        <p>逐行调用 <code>readline()</code>；使用 <code>print()</code> 输出。</p>
        <pre><code>const n = Number(readline());
const values = readline().trim().split(/\s+/).map(Number);
print(values.reduce((sum, value) =&gt; sum + value, 0));</code></pre>
        <el-alert type="warning" :closable="false" title="V8 模式不能使用 fs、process、Buffer 或浏览器 DOM API。" />
      </article>
      <article class="profile-panel">
        <h2>Node.js</h2>
        <p>用 <code>fs.readFileSync(0, 'utf8')</code> 一次读取 stdin；使用 console.log 或 process.stdout.write 输出。</p>
        <pre><code>const input = require('fs').readFileSync(0, 'utf8');
const tokens = input.trim().split(/\s+/);
console.log(tokens.length);</code></pre>
        <el-alert type="info" :closable="false" title="Node.js 提供标准 Node API，但不提供 window、document 等 DOM API。" />
      </article>
      <article class="profile-panel">
        <h2>常见边界</h2>
        <ul><li>保留可能有意义的空行，不要盲目 trim 全部输入。</li><li>读取到 EOF 时检查 readline() 是否返回 undefined。</li><li>不要输出提示语、调试日志或多余空格。</li><li>大输入优先一次读取并用游标消费 token。</li></ul>
      </article>
    </div>
  </section>
</template>
