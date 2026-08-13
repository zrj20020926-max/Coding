<script setup lang="ts">
import { ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { useContentStore } from '@/stores/content'

const content = useContentStore()
const { collections, collectionsTotal, collectionsLoading, collectionsError } =
  storeToRefs(content)
const page = ref(1)
const pageSize = ref(12)

watch([page, pageSize], () => void content.loadCollections(page.value, pageSize.value), {
  immediate: true,
})
</script>

<template>
  <section class="collections-page page-container">
    <header class="submissions-heading">
      <div><p class="eyebrow">CURATED COURSES</p><h1>训练路径</h1></div>
      <span>共 {{ collectionsTotal }} 条公开训练路径</span>
    </header>
    <div v-if="collectionsLoading" class="collection-grid">
      <span v-for="index in 6" :key="index" class="skeleton-block collection-skeleton"></span>
    </div>
    <section v-else-if="collectionsError" class="catalog-feedback">
      <el-result icon="error" title="训练路径加载失败" :sub-title="collectionsError">
        <template #extra><el-button @click="content.loadCollections(page, pageSize)">重试</el-button></template>
      </el-result>
    </section>
    <section v-else-if="collections.length === 0" class="catalog-feedback">
      <el-empty description="暂无公开训练路径" />
    </section>
    <div v-else class="collection-grid">
      <RouterLink
        v-for="item in collections"
        :key="item.id"
        class="collection-card"
        :to="{ name: 'collection-detail', params: { slug: item.slug } }"
      >
        <span>{{ item.company ?? 'CodeArena' }}</span>
        <h2>{{ item.title }}</h2>
        <p>{{ item.description || '按推荐顺序掌握这组输入输出结构。' }}</p>
        <footer>
          <strong>{{ item.problem_count }} 项练习</strong>
          <span v-if="item.solved_count !== undefined">{{ item.solved_count }} 已完成 · {{ item.completion_rate?.toFixed(0) }}%</span>
        </footer>
      </RouterLink>
    </div>
    <div class="catalog-pagination">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :current-page="page"
        :page-size="pageSize"
        :total="collectionsTotal"
        @update:current-page="page = $event"
      />
    </div>
  </section>
</template>
