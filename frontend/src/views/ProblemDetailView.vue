<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DiscussionSection from '@/components/content/DiscussionSection.vue'
import DifficultyBadge from '@/components/problems/DifficultyBadge.vue'
import MarkdownContent from '@/components/problems/MarkdownContent.vue'
import ProblemWorkbench from '@/components/problems/ProblemWorkbench.vue'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useCourseStore } from '@/stores/courses'
import { useProblemStore } from '@/stores/problems'
import { TRAINING_CATEGORY_LABELS } from '@/types/problem'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const problemStore = useProblemStore()
const courseStore = useCourseStore()
const { detail, detailLoading, detailError, detailNotFound, favoritePendingIds } =
  storeToRefs(problemStore)
const { exercise, exerciseLoading, exerciseError } = storeToRefs(courseStore)
const slug = computed(() => String(route.params['slug'] ?? ''))

function fetchDetail(): void {
  if (!slug.value) return
  void problemStore.loadProblem(slug.value)
  void courseStore.loadExercise(slug.value)
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
onBeforeUnmount(() => {
  problemStore.clearDetail()
  courseStore.clearExercise()
})
</script>

<template>
  <div class="problem-detail-page page-container">
    <nav class="problem-breadcrumb" aria-label="面包屑">
      <RouterLink to="/problems">训练课程</RouterLink>
      <span>/</span>
      <span v-if="exercise">{{ exercise.course_title }} · {{ exercise.chapter_title }}</span>
      <span v-else>{{ slug }}</span>
    </nav>

    <div v-if="detailLoading" class="detail-skeleton" aria-label="练习加载中" aria-busy="true">
      <span class="skeleton-block detail-title-skeleton"></span>
      <span class="skeleton-block detail-meta-skeleton"></span>
      <span v-for="index in 6" :key="index" class="skeleton-block detail-line-skeleton"></span>
    </div>

    <section v-else-if="detailError" class="detail-feedback">
      <el-result
        :icon="detailNotFound ? 'warning' : 'error'"
        :title="detailNotFound ? '练习不存在' : '加载失败'"
        :sub-title="detailError"
      >
        <template #extra>
          <RouterLink v-if="detailNotFound" class="primary-link" to="/problems">返回训练课程</RouterLink>
          <el-button v-else type="primary" @click="fetchDetail">重试</el-button>
        </template>
      </el-result>
    </section>

    <article v-else-if="detail" class="problem-statement training-statement">
      <header class="statement-header">
        <div>
          <div class="statement-kicker">
            <span>#{{ String(detail.id).padStart(4, '0') }}</span>
            <DifficultyBadge :difficulty="detail.difficulty" />
            <span>{{ TRAINING_CATEGORY_LABELS[detail.training_category] }}</span>
          </div>
          <h1>{{ detail.title }}</h1>
          <p v-if="exercise" class="workbench-position">
            {{ exercise.course_title }} / {{ exercise.chapter_title }} / 第 {{ exercise.sort_order }} 练习
            · 预计 {{ exercise.estimated_minutes }} 分钟
          </p>
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
          <div><dt>结构级别</dt><dd>{{ detail.difficulty === 'easy' ? '基础' : detail.difficulty === 'medium' ? '组合' : '综合' }}</dd></div>
          <div><dt>完成进度</dt><dd>{{ exercise?.progress?.any_runtime_completed ? '已完成' : exercise?.progress?.status === 'attempted' ? '已尝试' : '未开始' }}</dd></div>
        </dl>
      </header>

      <el-alert
        v-if="exerciseError"
        type="warning"
        :closable="false"
        title="课程位置暂时不可用；题面和判题工作台仍可正常使用。"
      />

      <div class="training-workspace-layout">
        <aside class="training-brief" :aria-busy="exerciseLoading">
          <section class="statement-section">
            <h2>练习说明</h2>
            <MarkdownContent :content="detail.description" />
          </section>

          <section class="statement-section">
            <h2>学习目标</h2>
            <MarkdownContent :content="exercise?.learning_objectives ?? '正确读取 stdin，并严格按照要求写入 stdout。'" />
          </section>

          <section class="statement-section compact-statement-section">
            <div><h2>输入格式</h2><MarkdownContent :content="detail.input_description" /></div>
            <div><h2>输出格式</h2><MarkdownContent :content="detail.output_description" /></div>
            <div><h2>数据范围</h2><MarkdownContent :content="detail.data_constraints" /></div>
          </section>

          <section class="statement-section">
            <h2>公开样例</h2>
            <div class="sample-grid single-column-samples">
              <div><span>stdin</span><pre><code>{{ detail.sample_input || '（空输入）' }}</code></pre></div>
              <div><span>expected stdout</span><pre><code>{{ detail.sample_output || '（无输出）' }}</code></pre></div>
            </div>
            <div v-if="detail.sample_explanation" class="sample-explanation">
              <h3>样例解释</h3>
              <MarkdownContent :content="detail.sample_explanation" />
            </div>
          </section>

          <section class="statement-section runtime-notes">
            <h2>V8 / Node.js 差异提示</h2>
            <article>
              <strong>JavaScript V8</strong>
              <MarkdownContent :content="exercise?.v8_notes ?? '使用 `readline()` 逐行读取，使用 `print()` 输出。EOF 返回 `undefined`。'" />
            </article>
            <article>
              <strong>Node.js</strong>
              <MarkdownContent :content="exercise?.nodejs_notes ?? '使用 `fs.readFileSync(0, \'utf8\')` 读取原始 stdin，不要无条件调用 `trim()`。'" />
            </article>
          </section>

          <section class="statement-section common-mistakes">
            <h2>常见错误</h2>
            <ul v-if="exercise?.common_mistakes.length">
              <li v-for="mistake in exercise.common_mistakes" :key="mistake">{{ mistake }}</li>
            </ul>
            <ul v-else>
              <li>混用 V8 的 readline()/print() 与 Node.js 的 fs/process API。</li>
              <li>无条件 trim() 导致空行或原始字符串信息丢失。</li>
              <li>输出调试文本、多余空格或多余空行。</li>
            </ul>
          </section>
        </aside>

        <div v-if="exerciseLoading" class="workbench-loading-card" aria-busy="true">
          <span class="skeleton-block"></span>
          <span class="skeleton-block"></span>
          <span class="skeleton-block"></span>
          <p>正在加载课程模板与运行时说明…</p>
        </div>
        <ProblemWorkbench
          v-else
          :key="`${detail.id}-${exercise?.id ?? 'standalone'}`"
          :problem="detail"
          :exercise="exercise"
        />
      </div>

      <DiscussionSection :problem-id="detail.id" />
    </article>
  </div>
</template>
