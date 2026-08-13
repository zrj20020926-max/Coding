<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { getApiErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'

interface LoginForm { account: string; password: string }

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const form = reactive<LoginForm>({ account: '', password: '' })
const rules: FormRules<LoginForm> = {
  account: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位', trigger: 'blur' },
  ],
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    await auth.login(form)
    ElMessage.success('欢迎回来')
    const redirect = typeof route.query['redirect'] === 'string' ? route.query['redirect'] : '/profile'
    await router.push(redirect)
  } catch (error) { ElMessage.error(getApiErrorMessage(error, '登录失败，请检查账号和密码')) }
}
</script>

<template>
  <section class="auth-page page-container">
    <div class="auth-aside">
      <p class="eyebrow">WELCOME BACK</p>
      <h1>继续你的<br />算法训练。</h1>
      <p>每一次提交都会留下可回顾的轨迹。真正的进步，来自稳定而清晰的反馈。</p>
      <div class="auth-quote">stdin → 思考 → stdout</div>
    </div>
    <div class="auth-card">
      <div class="auth-card-heading"><p>账号登录</p><h2>欢迎回来</h2></div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名或邮箱" prop="account">
          <el-input v-model="form.account" size="large" autocomplete="username" placeholder="candidate@example.com" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" size="large" show-password autocomplete="current-password" placeholder="至少 8 位" @keyup.enter="submit" />
        </el-form-item>
        <el-button class="auth-submit" type="primary" size="large" native-type="submit" :loading="auth.loading">登录</el-button>
      </el-form>
      <p class="auth-switch">还没有账号？<RouterLink :to="{ name: 'register', query: route.query }">立即注册</RouterLink></p>
    </div>
  </section>
</template>
