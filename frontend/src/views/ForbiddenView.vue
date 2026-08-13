<template>
  <section class="page-container not-found-page" aria-labelledby="forbidden-title">
    <p class="not-found-code">403</p>
    <p class="eyebrow">ACCESS DENIED</p>
    <h1 id="forbidden-title">无权访问管理后台</h1>
    <p>当前账号不具备管理员权限。如权限刚刚变更，请重新登录后再试。</p>
    <div class="not-found-actions">
      <RouterLink class="primary-link" to="/">返回首页</RouterLink>
      <RouterLink class="text-link" to="/login">切换账号</RouterLink>
    </div>
  </section>
</template>
