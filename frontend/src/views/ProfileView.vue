<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import { storeToRefs } from 'pinia'

import DifficultyBadge from '@/components/problems/DifficultyBadge.vue'
import SubmissionStatusBadge from '@/components/submissions/SubmissionStatusBadge.vue'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import type { ProblemDifficulty } from '@/types/problem'

const auth = useAuthStore()
const router = useRouter()
const training = useTrainingStore()
const { dashboard, dashboardLoading, dashboardError, acceptanceRate } = storeToRefs(training)
const saving = reactive({ profile: false, password: false, logoutAll: false })
const form = reactive({ nickname: '', bio: '' })
const passwordForm = reactive({ current_password: '', new_password: '', confirm_password: '' })
const passwordError = ref('')

watch(
  () => auth.user,
  (user) => {
    form.nickname = user?.nickname ?? ''
    form.bio = user?.bio ?? ''
  },
  { immediate: true },
)

const counters = computed(() =>
  dashboard.value?.counters ?? {
    solved_count: auth.user?.solved_count ?? 0,
    submission_count: auth.user?.submission_count ?? 0,
    accepted_count: auth.user?.accepted_count ?? 0,
  },
)

const difficultyNames: Record<ProblemDifficulty, string> = {
  easy: '基础',
  medium: '组合',
  hard: '综合',
}

function percentage(value: number, total: number): number {
  return total > 0 ? Math.min(100, (value / total) * 100) : 0
}

async function saveProfile(): Promise<void> {
  saving.profile = true
  try {
    await auth.updateProfile({ nickname: form.nickname, bio: form.bio })
    ElMessage.success('个人资料已保存')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '保存失败，请稍后重试'))
  } finally {
    saving.profile = false
  }
}

async function changePassword(): Promise<void> {
  passwordError.value = ''
  if (passwordForm.new_password.length < 8) {
    passwordError.value = '新密码至少 8 位'
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }
  saving.password = true
  try {
    await auth.changePassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    ElMessage.success('密码已修改，所有设备均需重新登录')
    await router.push({ name: 'login', query: { redirect: '/profile' } })
  } catch (error) {
    passwordError.value = getApiErrorMessage(error, '密码修改失败')
  } finally {
    saving.password = false
  }
}

async function logoutAllDevices(): Promise<void> {
  try {
    await ElMessageBox.confirm('这会让包括当前设备在内的所有登录会话失效，确认继续？', '退出全部设备', {
      type: 'warning',
    })
    saving.logoutAll = true
    await auth.logoutAll()
    ElMessage.success('已退出全部设备')
    await router.push({ name: 'login' })
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '退出全部设备失败'))
    }
  } finally {
    saving.logoutAll = false
  }
}

onMounted(() => void training.loadDashboard())
</script>

<template>
  <section v-if="auth.user" class="profile-page page-container">
    <div class="profile-heading">
      <div class="avatar-placeholder" aria-hidden="true">
        {{ auth.user.nickname.slice(0, 1).toUpperCase() }}
      </div>
      <div>
        <p class="eyebrow">TRAINING PROFILE</p>
        <h1>{{ auth.user.nickname }}</h1>
        <p>@{{ auth.user.username }} · 加入于 {{ new Date(auth.user.created_at).toLocaleDateString('zh-CN') }}</p>
      </div>
    </div>

    <div v-if="dashboardLoading && !dashboard" class="profile-loading" aria-label="训练统计加载中">
      <span v-for="index in 4" :key="index" class="skeleton-block"></span>
    </div>
    <section v-else-if="dashboardError" class="profile-dashboard-error" aria-live="polite">
      <span>{{ dashboardError }}</span>
      <el-button text @click="training.loadDashboard">重试</el-button>
    </section>

    <div class="stats-grid">
      <article><span>已完成</span><strong>{{ counters.solved_count }}</strong><small>项练习</small></article>
      <article><span>提交次数</span><strong>{{ counters.submission_count }}</strong><small>次</small></article>
      <article><span>通过次数</span><strong>{{ counters.accepted_count }}</strong><small>次</small></article>
      <article><span>通过率</span><strong>{{ acceptanceRate.toFixed(1) }}%</strong><small>Accepted</small></article>
    </div>

    <div class="training-grid">
      <section class="profile-panel">
        <div class="panel-heading"><div><p>STRUCTURE</p><h2>输入结构层级</h2></div><span>已完成 / 公开练习</span></div>
        <div class="difficulty-progress-list">
          <article v-for="item in dashboard?.difficulty_stats ?? []" :key="item.difficulty">
            <div>
              <DifficultyBadge :difficulty="item.difficulty" />
              <span>{{ difficultyNames[item.difficulty] }}</span>
              <strong>{{ item.solved_count }} / {{ item.total_count }}</strong>
            </div>
            <div class="training-progress-track"><i :style="{ width: `${percentage(item.solved_count, item.total_count)}%` }"></i></div>
            <small>已尝试 {{ item.attempted_count }} 道</small>
          </article>
        </div>
      </section>
      <section class="profile-panel account-security-panel">
        <div class="panel-heading"><div><p>SECURITY</p><h2>账户安全</h2></div><span>所有设备</span></div>
        <el-form label-position="top" @submit.prevent="changePassword">
          <el-form-item label="当前密码"><el-input v-model="passwordForm.current_password" type="password" show-password autocomplete="current-password" /></el-form-item>
          <el-form-item label="新密码"><el-input v-model="passwordForm.new_password" type="password" show-password autocomplete="new-password" /></el-form-item>
          <el-form-item label="确认新密码"><el-input v-model="passwordForm.confirm_password" type="password" show-password autocomplete="new-password" /></el-form-item>
          <p v-if="passwordError" class="form-error" role="alert">{{ passwordError }}</p>
          <el-button type="primary" native-type="submit" :loading="saving.password">修改密码</el-button>
        </el-form>
        <el-divider />
        <p>如怀疑账号泄漏，可撤销全部 Refresh Token 和 Access Token 会话。</p>
        <el-button type="danger" plain :loading="saving.logoutAll" @click="logoutAllDevices">退出全部设备</el-button>
      </section>

      <section class="profile-panel">
        <div class="panel-heading"><div><p>INPUT PATTERNS</p><h2>输入输出分类统计</h2></div><span>待练习项优先</span></div>
        <div v-if="dashboard?.tag_stats.length" class="tag-stat-list">
          <article v-for="item in dashboard.tag_stats" :key="item.tag.id">
            <div><strong>{{ item.tag.name }}</strong><span>{{ item.solved_count }} / {{ item.total_count }}</span></div>
            <div class="training-progress-track"><i :style="{ width: `${percentage(item.solved_count, item.total_count)}%` }"></i></div>
            <small>尝试 {{ item.attempted_count }} 道</small>
          </article>
        </div>
        <el-empty v-else description="暂无标签统计" :image-size="70" />
      </section>
    </div>

    <div class="training-grid">
      <section class="profile-panel">
        <div class="panel-heading"><div><p>RECENT</p><h2>最近提交</h2></div><RouterLink to="/submissions">查看全部</RouterLink></div>
        <div v-if="dashboard?.recent_submissions.length" class="profile-submission-list">
          <RouterLink
            v-for="submission in dashboard.recent_submissions"
            :key="submission.id"
            :to="{ name: 'submission-detail', params: { id: submission.id } }"
          >
            <span><strong>{{ submission.problem.title }}</strong><small>{{ submission.language.display_name }} · {{ submission.mode === 'judge' ? '正式提交' : '公开样例' }}</small></span>
            <SubmissionStatusBadge :status="submission.status" />
          </RouterLink>
        </div>
        <el-empty v-else description="还没有提交记录" :image-size="70" />
      </section>

      <section class="profile-panel">
        <div class="panel-heading"><div><p>COMPLETED</p><h2>已完成练习</h2></div><span>最近 30 项</span></div>
        <div v-if="dashboard?.solved_problems.length" class="solved-problem-list">
          <RouterLink
            v-for="problem in dashboard.solved_problems"
            :key="problem.id"
            :to="{ name: 'problem-detail', params: { slug: problem.slug } }"
          >
            <span><strong>{{ problem.title }}</strong><small>尝试 {{ problem.attempt_count }} 次</small></span>
            <DifficultyBadge :difficulty="problem.difficulty" />
          </RouterLink>
        </div>
        <el-empty v-else description="完成第一项输入输出练习后会显示在这里" :image-size="70" />
      </section>
    </div>

    <div class="profile-content">
      <section class="profile-panel">
        <div class="panel-heading"><div><p>PROFILE</p><h2>个人资料</h2></div><span>公开信息</span></div>
        <el-form label-position="top" @submit.prevent="saveProfile">
          <el-form-item label="昵称"><el-input v-model="form.nickname" maxlength="50" size="large" /></el-form-item>
          <el-form-item label="个人简介"><el-input v-model="form.bio" type="textarea" maxlength="300" show-word-limit :rows="4" placeholder="写下你的训练目标" /></el-form-item>
          <el-button type="primary" native-type="submit" :loading="saving.profile">保存修改</el-button>
        </el-form>
      </section>
      <aside class="next-sprint-panel">
        <span>JAVASCRIPT I/O</span><h2>继续保持手感</h2><p>从收藏练习继续训练，或回顾 V8 与 Node.js 的输入解析错误。</p>
        <RouterLink class="profile-submissions-link" to="/favorites">查看我的收藏 →</RouterLink>
        <br />
        <RouterLink class="profile-submissions-link" to="/submissions">查看提交记录 →</RouterLink>
      </aside>
    </div>
  </section>
</template>
