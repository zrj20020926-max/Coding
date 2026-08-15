<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import GuideCodeBlock from '@/components/guide/GuideCodeBlock.vue'
import MarkdownContent from '@/components/problems/MarkdownContent.vue'
import {
  GUIDE_SECTIONS,
  GUIDE_SECTION_BY_SLUG,
  searchGuide,
} from '@/content/guide'
import type { GuideSectionSlug } from '@/types/guide'

const route = useRoute()
const router = useRouter()
const query = ref('')

const sectionSlug = computed(() => route.meta['guideSection'] as GuideSectionSlug | undefined)
const currentSection = computed(() => (
  sectionSlug.value ? GUIDE_SECTION_BY_SLUG[sectionSlug.value] : null
))
const searchResults = computed(() => searchGuide(query.value))
const isSearching = computed(() => query.value.trim().length > 0)

function sectionPath(slug: GuideSectionSlug): string {
  return `/guide/${slug}`
}

function handleSectionSelect(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  void router.push(value)
}
</script>

<template>
  <section class="guide-page page-container">
    <header class="guide-hero">
      <div>
        <p class="eyebrow">JAVASCRIPT ACM REFERENCE</p>
        <h1>stdin / stdout<br>速查手册</h1>
        <p>在 V8 与 Node.js 两种运行模式中，快速找到可复制、可直接练习的输入输出模板。</p>
      </div>
      <label class="guide-search">
        <span>搜索手册</span>
        <input
          v-model="query"
          type="search"
          placeholder="例如：EOF、空行、BigInt、Scanner"
          autocomplete="off"
          aria-label="搜索 JavaScript ACM 速查手册"
        >
        <small v-if="isSearching" aria-live="polite">找到 {{ searchResults.length }} 个主题</small>
      </label>
    </header>

    <label class="guide-mobile-section-select">
      <span>当前章节</span>
      <select :value="route.path" aria-label="选择速查手册章节" @change="handleSectionSelect">
        <option value="/guide">手册首页</option>
        <option v-for="section in GUIDE_SECTIONS" :key="section.slug" :value="sectionPath(section.slug)">
          {{ section.title }}
        </option>
      </select>
    </label>

    <div class="guide-layout">
      <aside class="guide-sidebar" aria-label="速查手册章节目录">
        <RouterLink to="/guide">手册首页</RouterLink>
        <RouterLink v-for="section in GUIDE_SECTIONS" :key="section.slug" :to="sectionPath(section.slug)">
          <span>{{ section.eyebrow }}</span>{{ section.title }}
        </RouterLink>
        <nav v-if="currentSection && !isSearching" class="guide-topic-nav" aria-label="当前章节目录">
          <a v-for="topic in currentSection.topics" :key="topic.id" :href="`#${topic.id}`">
            {{ topic.title }}
          </a>
        </nav>
      </aside>

      <main class="guide-main">
        <template v-if="isSearching">
          <header class="guide-section-heading">
            <p class="eyebrow">SEARCH RESULTS</p>
            <h2>“{{ query.trim() }}”</h2>
            <p>搜索范围包括章节说明、关键词和全部代码模板。</p>
          </header>
          <div v-if="searchResults.length" class="guide-search-results">
            <RouterLink
              v-for="result in searchResults"
              :key="`${result.section.slug}-${result.topic.id}`"
              :to="{ path: sectionPath(result.section.slug), hash: `#${result.topic.id}` }"
            >
              <span>{{ result.section.title }}</span>
              <strong>{{ result.topic.title }}</strong>
              <MarkdownContent :content="result.topic.summary" />
            </RouterLink>
          </div>
          <el-empty v-else description="没有找到匹配内容，请尝试 EOF、空行、BigInt 或输出缓冲" />
        </template>

        <template v-else-if="currentSection">
          <header class="guide-section-heading">
            <p class="eyebrow">{{ currentSection.eyebrow }}</p>
            <h2>{{ currentSection.title }}</h2>
            <MarkdownContent :content="currentSection.description" />
          </header>
          <article
            v-for="topic in currentSection.topics"
            :id="topic.id"
            :key="topic.id"
            class="guide-topic"
          >
            <header>
              <h3>{{ topic.title }}</h3>
              <MarkdownContent :content="topic.summary" />
            </header>
            <div class="guide-code-grid" :class="{ 'is-pair': topic.examples.length > 1 }">
              <GuideCodeBlock v-for="example in topic.examples" :key="example.id" :example="example" />
            </div>
          </article>
        </template>

        <template v-else>
          <header class="guide-section-heading guide-overview-heading">
            <p class="eyebrow">CHOOSE YOUR RUNTIME</p>
            <h2>两套 API，清楚分开</h2>
            <p>JavaScript V8 使用 readline()/print()；Node.js 使用 fs 和 stdout。先选运行模式，再选输入结构。</p>
          </header>
          <div class="guide-section-cards">
            <RouterLink v-for="section in GUIDE_SECTIONS" :key="section.slug" :to="sectionPath(section.slug)">
              <span>{{ section.eyebrow }}</span>
              <h3>{{ section.title }}</h3>
              <p>{{ section.description.replace(/`/g, '') }}</p>
              <strong>{{ section.topics.length }} 个主题 →</strong>
            </RouterLink>
          </div>
          <el-alert
            class="guide-safety-note"
            type="info"
            :closable="false"
            title="所有 Markdown 说明均经过安全清理；代码以纯文本展示，不会在浏览器执行。"
            show-icon
          />
        </template>
      </main>
    </div>
  </section>
</template>
