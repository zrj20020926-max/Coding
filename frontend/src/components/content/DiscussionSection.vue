<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import MarkdownContent from '@/components/problems/MarkdownContent.vue'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useContentStore } from '@/stores/content'

const props = defineProps<{ problemId: number }>()
const route = useRoute()
const auth = useAuthStore()
const content = useContentStore()
const { discussions, discussionsTotal, discussionsLoading, discussionsError } =
  storeToRefs(content)
const page = ref(1)
const pageSize = 10
const composing = ref(false)
const submitting = ref(false)
const form = reactive({ title: '', content: '' })
const formRef = ref<FormInstance>()
const rules: FormRules = {
  title: [
    { required: true, message: '请输入讨论标题', trigger: 'blur' },
    { min: 2, max: 200, message: '标题长度为 2–200 个字符', trigger: 'blur' },
  ],
  content: [
    { required: true, message: '请输入讨论内容', trigger: 'blur' },
    { min: 2, max: 50000, message: '内容长度为 2–50000 个字符', trigger: 'blur' },
  ],
}

watch(
  [() => props.problemId, page],
  () => void content.loadDiscussions(props.problemId, page.value, pageSize),
  { immediate: true },
)

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || submitting.value) return
  submitting.value = true
  try {
    const created = await content.addDiscussion(props.problemId, form.title, form.content)
    form.title = ''
    form.content = ''
    composing.value = false
    ElMessage.success(
      created.review_status === 'pending' ? '讨论已提交，等待审核' : '讨论发布成功',
    )
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '讨论发布失败'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="discussion-section">
    <header>
      <div><p class="section-kicker">COMMUNITY</p><h2>练习讨论</h2></div>
      <el-button v-if="auth.isAuthenticated" type="primary" @click="composing = !composing">
        {{ composing ? '取消' : '发起讨论' }}
      </el-button>
      <RouterLink v-else class="primary-link" :to="{ name: 'login', query: { redirect: route.fullPath } }">登录后讨论</RouterLink>
    </header>
    <el-form v-if="composing" ref="formRef" :model="form" :rules="rules" class="discussion-compose" label-position="top" @submit.prevent="submit">
      <el-form-item label="标题" prop="title"><el-input v-model="form.title" maxlength="200" show-word-limit /></el-form-item>
      <el-form-item label="内容（支持 Markdown）" prop="content"><el-input v-model="form.content" type="textarea" :rows="5" maxlength="50000" show-word-limit /></el-form-item>
      <el-button type="primary" native-type="submit" :loading="submitting">发布讨论</el-button>
    </el-form>
    <div v-if="discussionsLoading" class="discussion-loading"><span v-for="i in 3" :key="i" class="skeleton-block"></span></div>
    <el-result v-else-if="discussionsError" icon="error" title="讨论加载失败" :sub-title="discussionsError">
      <template #extra><el-button type="primary" @click="content.loadDiscussions(problemId, page, pageSize)">重试</el-button></template>
    </el-result>
    <el-empty v-else-if="discussions.length === 0" description="还没有讨论，来分享第一个思路吧" />
    <div v-else class="discussion-list">
      <article v-for="item in discussions" :key="item.id">
        <div class="discussion-flags">
          <span v-if="item.is_pinned">置顶</span><span v-if="item.is_locked">已锁定</span>
          <span v-if="item.review_status === 'pending'">审核中</span>
        </div>
        <RouterLink :to="{ name: 'discussion-detail', params: { id: item.id } }">
          <h3>{{ item.title }}</h3>
        </RouterLink>
        <MarkdownContent :content="item.content" />
        <footer>
          <span>{{ item.author?.nickname ?? '已注销用户' }}</span>
          <time>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time>
          <span>{{ item.comment_count }} 条评论</span>
        </footer>
      </article>
    </div>
    <div v-if="discussionsTotal > pageSize" class="catalog-pagination">
      <el-pagination
        background
        layout="prev, pager, next"
        :current-page="page"
        :page-size="pageSize"
        :total="discussionsTotal"
        @update:current-page="page = $event"
      />
    </div>
  </section>
</template>
