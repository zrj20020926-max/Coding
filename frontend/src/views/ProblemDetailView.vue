<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DifficultyBadge from '@/components/problems/DifficultyBadge.vue'
import MarkdownContent from '@/components/problems/MarkdownContent.vue'
import ProblemWorkbench from '@/components/problems/ProblemWorkbench.vue'
import DiscussionSection from '@/components/content/DiscussionSection.vue'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useProblemStore } from '@/stores/problems'
import { TRAINING_CATEGORY_LABELS } from '@/types/problem'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const problemStore = useProblemStore()
const { detail, detailLoading, detailError, detailNotFound, favoritePendingIds } =
  storeToRefs(problemStore)
const slug = computed(() => String(route.params['slug'] ?? ''))

function fetchDetail(): void {
  if (slug.value) void problemStore.loadProblem(slug.value)
}

async function toggleFavorite(): Promise<void> {
  if (!detail.value) return
  if (!auth.isAuthenticated) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  try {
    await problemStore.updateFavorite(detail.value.id, !detail.value.favorited)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '收藏操作失败，请稍后重试'))
  }
}

watch(slug, fetchDetail, { immediate: true })
onBeforeUnmount(() => problemStore.clearDetail())
</script>

<template>
  <div class="problem-detail-page page-container">
    <nav class="problem-breadcrumb" aria-label="面包屑">
      <RouterLink to="/problems">训练课程</RouterLink><span>/</span><span>{{ slug }}</span>
    </nav>

    <div v-if="detailLoading" class="detail-skeleton" aria-label="题目加载中" aria-busy="true">
      <span class="skeleton-block detail-title-skeleton"></span>
      <span class="skeleton-block detail-meta-skeleton"></span>
      <span v-for="index in 6" :key="index" class="skeleton-block detail-line-skeleton"></span>
    </div>

    <section v-else-if="detailError" class="detail-feedback">
      <el-result
        :icon="detailNotFound ? 'warning' : 'error'"
        :title="detailNotFound ? '题目不存在' : '加载失败'"
        :sub-title="detailError"
      >
        <template #extra>
          <RouterLink v-if="detailNotFound" class="primary-link" to="/problems">返回训练课程</RouterLink>
          <el-button v-else type="primary" @click="fetchDetail">重试</el-button>
        </template>
      </el-result>
    </section>

    <article v-else-if="detail" class="problem-statement">
      <header class="statement-header">
        <div>
          <div class="statement-kicker">
            <span>#{{ String(detail.id).padStart(4, '0') }}</span>
            <DifficultyBadge :difficulty="detail.difficulty" />
            <span>{{ TRAINING_CATEGORY_LABELS[detail.training_category] }}</span>
          </div>
          <h1>{{ detail.title }}</h1>
          <div class="statement-tags">
            <span v-for="tag in detail.tags" :key="tag.id">{{ tag.name }}</span>
          </div>
          <button
            class="detail-favorite-button"
            type="button"
            :disabled="favoritePendingIds.includes(detail.id)"
            @click="toggleFavorite"
          >
            {{ detail.favorited ? '★ 已收藏' : '☆ 收藏练习' }}
          </button>
        </div>
        <dl class="statement-limits">
          <div><dt>时间限制</dt><dd>{{ detail.time_limit_ms }} ms</dd></div>
          <div><dt>内存限制</dt><dd>{{ detail.memory_limit_mb }} MB</dd></div>
          <div><dt>通过率</dt><dd>{{ detail.acceptance_rate.toFixed(1) }}%</dd></div>
          <div v-if="detail.source"><dt>来源</dt><dd>{{ detail.source }}</dd></div>
        </dl>
      </header>

      <section class="statement-section">
        <h2>题目描述</h2>
        <MarkdownContent :content="detail.description" />
      </section>
      <section class="statement-section statement-columns">
        <div><h2>输入说明</h2><MarkdownContent :content="detail.input_description" /></div>
        <div><h2>输出说明</h2><MarkdownContent :content="detail.output_description" /></div>
        <div><h2>数据范围</h2><MarkdownContent :content="detail.data_constraints" /></div>
      </section>
      <section class="statement-section">
        <h2>样例</h2>
        <div class="sample-grid">
          <div><span>输入</span><pre><code>{{ detail.sample_input || '（空）' }}</code></pre></div>
          <div><span>输出</span><pre><code>{{ detail.sample_output || '（空）' }}</code></pre></div>
        </div>
        <div><h2>样例解释</h2><MarkdownContent :content="detail.sample_explanation" /></div>
      </section>
      <aside class="editor-notice">
        <strong>JavaScript ACM 输入输出说明</strong>
        <p>V8 模式只使用 readline()/print()；Node.js 模式使用 fs 读取 stdin。两种模式都在独立 Judge 沙箱运行，浏览器与 API 不执行代码。</p>
      </aside>
      <ProblemWorkbench :problem="detail" />
      <DiscussionSection :problem-id="detail.id" />
    </article>
  </div>
</template>
