<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'

interface RegisterForm {
  nickname: string
  username: string
  email: string
  password: string
  confirmPassword: string
}

const auth = useAuthStore()
const router = useRouter()
const formRef = ref<FormInstance>()
const form = reactive<RegisterForm>({ nickname: '', username: '', email: '', password: '', confirmPassword: '' })
const rules: FormRules<RegisterForm> = {
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度为 3–32 位', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_]+$/, message: '只能包含字母、数字和下划线', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== form.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    await auth.register({ nickname: form.nickname, username: form.username, email: form.email, password: form.password })
    ElMessage.success('账号创建成功')
    await router.push('/profile')
  } catch (error) { ElMessage.error(getApiErrorMessage(error, '注册失败，请稍后重试')) }
}
</script>

<template>
  <section class="auth-page page-container">
    <div class="auth-aside">
      <p class="eyebrow">START PRACTICING</p>
      <h1>为下一场笔试，<br />提前进入状态。</h1>
      <p>从输入输出到复杂度分析，建立一套能在真实环境里稳定发挥的解题习惯。</p>
      <ul class="auth-points"><li>ACM 标准输入输出</li><li>五种主流编程语言</li><li>企业高频题训练路径</li></ul>
    </div>
    <div class="auth-card auth-card-wide">
      <div class="auth-card-heading"><p>创建账号</p><h2>开始训练</h2></div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
        <div class="form-grid">
          <el-form-item label="昵称" prop="nickname"><el-input v-model="form.nickname" size="large" autocomplete="nickname" placeholder="你的展示名称" /></el-form-item>
          <el-form-item label="用户名" prop="username"><el-input v-model="form.username" size="large" autocomplete="username" placeholder="candidate_01" /></el-form-item>
        </div>
        <el-form-item label="邮箱" prop="email"><el-input v-model="form.email" size="large" autocomplete="email" placeholder="candidate@example.com" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" size="large" show-password autocomplete="new-password" placeholder="至少 8 位" /></el-form-item>
          <el-form-item label="确认密码" prop="confirmPassword"><el-input v-model="form.confirmPassword" type="password" size="large" show-password autocomplete="new-password" placeholder="再次输入" @keyup.enter="submit" /></el-form-item>
        </div>
        <el-button class="auth-submit" type="primary" size="large" native-type="submit" :loading="auth.loading">创建账号</el-button>
      </el-form>
      <p class="auth-switch">已有账号？<RouterLink to="/login">直接登录</RouterLink></p>
    </div>
  </section>
</template>

