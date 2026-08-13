<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import MarkdownContent from '@/components/problems/MarkdownContent.vue'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useContentStore } from '@/stores/content'
import type { DiscussionComment } from '@/types/content'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const content = useContentStore()
const { discussionDetail, discussionLoading, discussionError } = storeToRefs(content)
const id = computed(() => Number(route.params['id']))
const page = ref(1)
const pageSize = 30
const replyTo = ref<DiscussionComment | null>(null)
const commentText = ref('')
const submitting = ref(false)

watch([id, page], () => void content.loadDiscussion(id.value, page.value, pageSize), {
  immediate: true,
})

async function submitComment(): Promise<void> {
  if (!commentText.value.trim() || submitting.value) return
  submitting.value = true
  try {
    const created = await content.addComment(commentText.value, replyTo.value?.id)
    commentText.value = ''
    replyTo.value = null
    ElMessage.success(created.review_status === 'pending' ? '评论等待审核' : '评论成功')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '评论失败'))
  } finally {
    submitting.value = false
  }
}

async function beginReply(comment: DiscussionComment): Promise<void> {
  if (!auth.isAuthenticated) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  replyTo.value = comment
}

function retryLoad(): void {
  void content.loadDiscussion(id.value, page.value, pageSize)
}

async function editThread(): Promise<void> {
  if (!discussionDetail.value) return
  try {
    const title = await ElMessageBox.prompt('修改标题', '编辑讨论', {
      inputValue: discussionDetail.value.discussion.title,
    })
    const body = await ElMessageBox.prompt('修改 Markdown 内容', '编辑讨论', {
      inputValue: discussionDetail.value.discussion.content,
      inputType: 'textarea',
    })
    await content.updateCurrentDiscussion(title.value, body.value)
    ElMessage.success('讨论已更新')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '更新失败'))
    }
  }
}

async function removeThread(): Promise<void> {
  try {
    await ElMessageBox.confirm('删除后讨论将不再公开，确认继续？', '删除讨论', {
      type: 'warning',
    })
    await content.removeCurrentDiscussion()
    await router.push('/problems')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('删除失败')
  }
}

async function editReply(comment: DiscussionComment): Promise<void> {
  try {
    const result = await ElMessageBox.prompt('修改评论', '编辑评论', {
      inputValue: comment.content,
      inputType: 'textarea',
    })
    await content.updateCurrentComment(comment.id, result.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('编辑失败')
  }
}

async function removeReply(comment: DiscussionComment): Promise<void> {
  try {
    await ElMessageBox.confirm('确认删除这条评论？', '删除评论', { type: 'warning' })
    await content.removeCurrentComment(comment.id)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('删除失败')
  }
}

async function report(target: 'discussion' | 'comment', targetId: number): Promise<void> {
  if (!auth.isAuthenticated) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  try {
    const result = await ElMessageBox.prompt('请简要说明举报原因', '举报内容')
    await content.reportContent(target, targetId, result.value)
    ElMessage.success('举报已提交')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('举报失败')
  }
}
</script>

<template>
  <section class="discussion-detail-page page-container">
    <div v-if="discussionLoading" class="detail-skeleton"><span class="skeleton-block detail-title-skeleton"></span></div>
    <el-result v-else-if="discussionError" icon="error" title="讨论加载失败" :sub-title="discussionError">
      <template #extra><el-button type="primary" @click="retryLoad">重试</el-button></template>
    </el-result>
    <template v-else-if="discussionDetail">
      <article class="discussion-thread">
        <div class="discussion-flags">
          <span v-if="discussionDetail.discussion.is_pinned">置顶</span>
          <span v-if="discussionDetail.discussion.is_locked">已锁定</span>
          <span v-if="discussionDetail.discussion.review_status === 'pending'">审核中</span>
        </div>
        <h1>{{ discussionDetail.discussion.title }}</h1>
        <p class="discussion-byline">{{ discussionDetail.discussion.author?.nickname ?? '已注销用户' }} · {{ new Date(discussionDetail.discussion.created_at).toLocaleString('zh-CN') }}</p>
        <MarkdownContent :content="discussionDetail.discussion.content" />
        <footer>
          <button v-if="discussionDetail.discussion.can_edit" type="button" @click="editThread">编辑</button>
          <button v-if="discussionDetail.discussion.can_edit" type="button" @click="removeThread">删除</button>
          <button type="button" @click="report('discussion', discussionDetail.discussion.id)">举报</button>
        </footer>
      </article>

      <section class="comment-section">
        <header><h2>评论 {{ discussionDetail.comments.total }}</h2></header>
        <div class="comment-list">
          <article
            v-for="comment in discussionDetail.comments.items"
            :key="comment.id"
            class="comment-card"
            :style="{ '--comment-depth': String(comment.depth) }"
          >
            <div><strong>{{ comment.author?.nickname ?? '已注销用户' }}</strong><time>{{ new Date(comment.created_at).toLocaleString('zh-CN') }}</time></div>
            <MarkdownContent :content="comment.content" />
            <footer v-if="!comment.deleted">
              <button v-if="comment.depth < 3 && !discussionDetail.discussion.is_locked" type="button" @click="beginReply(comment)">回复</button>
              <button v-if="comment.can_edit" type="button" @click="editReply(comment)">编辑</button>
              <button v-if="comment.can_edit" type="button" @click="removeReply(comment)">删除</button>
              <button type="button" @click="report('comment', comment.id)">举报</button>
            </footer>
          </article>
        </div>
        <div v-if="discussionDetail.comments.total > pageSize" class="catalog-pagination">
          <el-pagination
            background
            layout="prev, pager, next"
            :current-page="page"
            :page-size="pageSize"
            :total="discussionDetail.comments.total"
            @update:current-page="page = $event"
          />
        </div>
        <el-form v-if="auth.isAuthenticated && !discussionDetail.discussion.is_locked" class="comment-compose" @submit.prevent="submitComment">
          <p v-if="replyTo">回复 {{ replyTo.author?.nickname ?? '已注销用户' }} <button type="button" @click="replyTo = null">取消</button></p>
          <el-input v-model="commentText" type="textarea" :rows="4" maxlength="20000" show-word-limit placeholder="友善讨论，支持 Markdown" />
          <el-button type="primary" native-type="submit" :loading="submitting" :disabled="!commentText.trim()">发表评论</el-button>
        </el-form>
        <p v-else-if="discussionDetail.discussion.is_locked" class="discussion-locked-notice">该讨论已被管理员锁定</p>
        <RouterLink v-else class="primary-link" :to="{ name: 'login', query: { redirect: route.fullPath } }">登录后参与讨论</RouterLink>
      </section>
    </template>
  </section>
</template>
