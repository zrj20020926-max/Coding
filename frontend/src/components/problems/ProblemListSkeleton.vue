<template>
  <div class="problem-skeleton" aria-label="训练课程加载中" aria-busy="true">
    <div v-for="index in 6" :key="index" class="skeleton-row">
      <span class="skeleton-block skeleton-number"></span>
      <span class="skeleton-block skeleton-title"></span>
      <span class="skeleton-block skeleton-small"></span>
      <span class="skeleton-block skeleton-tags"></span>
      <span class="skeleton-block skeleton-small"></span>
    </div>
  </div>
</template>
