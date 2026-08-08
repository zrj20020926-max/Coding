<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const saving = reactive({ profile: false })
const form = reactive({ nickname: '', bio: '' })

watch(() => auth.user, (user) => {
  form.nickname = user?.nickname ?? ''
  form.bio = user?.bio ?? ''
}, { immediate: true })

const acceptanceRate = computed(() => {
  const user = auth.user
  if (!user || user.submission_count === 0) return '0.0%'
  return `${((user.accepted_count / user.submission_count) * 100).toFixed(1)}%`
})

async function saveProfile(): Promise<void> {
  saving.profile = true
  try {
    await auth.updateProfile({ nickname: form.nickname, bio: form.bio })
    ElMessage.success('个人资料已保存')
  } catch (error) { ElMessage.error(getApiErrorMessage(error, '保存失败，请稍后重试')) }
  finally { saving.profile = false }
}
</script>

<template>
  <section v-if="auth.user" class="profile-page page-container">
    <div class="profile-heading">
      <div class="avatar-placeholder" aria-hidden="true">{{ auth.user.nickname.slice(0, 1).toUpperCase() }}</div>
      <div>
        <p class="eyebrow">TRAINING PROFILE</p><h1>{{ auth.user.nickname }}</h1>
        <p>@{{ auth.user.username }} · 加入于 {{ new Date(auth.user.created_at).toLocaleDateString('zh-CN') }}</p>
      </div>
    </div>
    <div class="stats-grid">
      <article><span>已解决</span><strong>{{ auth.user.solved_count }}</strong><small>道题</small></article>
      <article><span>提交次数</span><strong>{{ auth.user.submission_count }}</strong><small>次</small></article>
      <article><span>通过次数</span><strong>{{ auth.user.accepted_count }}</strong><small>次</small></article>
      <article><span>通过率</span><strong>{{ acceptanceRate }}</strong><small>Accepted</small></article>
    </div>
    <div class="profile-content">
      <section class="profile-panel">
        <div class="panel-heading"><div><p>PROFILE</p><h2>个人资料</h2></div><span>公开信息</span></div>
        <el-form label-position="top" @submit.prevent="saveProfile">
          <el-form-item label="昵称"><el-input v-model="form.nickname" maxlength="50" size="large" /></el-form-item>
          <el-form-item label="个人简介"><el-input v-model="form.bio" type="textarea" maxlength="300" show-word-limit :rows="4" placeholder="写下你的目标，例如：三个月完成动态规划 TOP 100" /></el-form-item>
          <el-button type="primary" native-type="submit" :loading="saving.profile">保存修改</el-button>
        </el-form>
      </section>
      <aside class="next-sprint-panel">
        <span>UP NEXT</span><h2>题库与训练记录</h2><p>下一迭代会接入题目搜索、难度/标签筛选，以及真实的做题进度。</p>
        <div class="progress-preview"><i></i><i></i><i></i><i></i><i></i></div>
      </aside>
    </div>
  </section>
</template>

