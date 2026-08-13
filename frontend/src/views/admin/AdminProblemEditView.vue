<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import ProblemForm from '@/components/admin/ProblemForm.vue'
import TestSetManager from '@/components/admin/TestSetManager.vue'
import { getApiErrorMessage, getApiValidationIssues } from '@/services/http'
import { useAdminStore } from '@/stores/admin'
import { useProblemStore } from '@/stores/problems'
import type { ProblemWritePayload } from '@/types/admin'

const route = useRoute()
const router = useRouter()
const admin = useAdminStore()
const catalog = useProblemStore()
const formRef = ref<InstanceType<typeof ProblemForm>>()
const dirty = ref(false)
const fieldErrors = ref<Record<string, string>>({})
const isNew = computed(() => route.name === 'admin-problem-new')
const problemId = computed(() => Number(route.params['id']))

function beforeUnload(event: BeforeUnloadEvent): void {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(async () => {
  window.addEventListener('beforeunload', beforeUnload)
  await catalog.loadTags()
  if (!isNew.value) await admin.loadProblem(problemId.value)
  else admin.clearDetail()
})
onBeforeUnmount(() => { window.removeEventListener('beforeunload', beforeUnload); admin.clearDetail() })
onBeforeRouteLeave(async () => {
  if (!dirty.value) return true
  try { await ElMessageBox.confirm('当前题目有未保存修改，确认离开？', '未保存提醒', { type: 'warning' }); return true }
  catch { return false }
})

async function save(payload: ProblemWritePayload): Promise<void> {
  fieldErrors.value = {}
  try {
    const saved = await admin.saveProblem(payload)
    formRef.value?.markSaved()
    ElMessage.success('题目已保存')
    if (isNew.value) await router.replace(`/admin/problems/${saved.id}`)
  } catch (error) {
    for (const issue of getApiValidationIssues(error)) {
      const locations = issue.location ?? []
      const field = locations[locations.length - 1]
      if (field !== undefined) fieldErrors.value[field] = issue.message
    }
    ElMessage.error(getApiErrorMessage(error, '保存失败，请检查表单'))
  }
}

async function publish(): Promise<void> {
  try {
    await admin.publish()
    if (admin.readiness?.ready) ElMessage.success('题目已发布')
    else ElMessage.warning('发布门禁未通过，请处理检查项')
  } catch (error) { ElMessage.error(getApiErrorMessage(error, '发布失败')) }
}

async function offline(): Promise<void> {
  try { await admin.offline(); ElMessage.success('题目已下线') }
  catch (error) { ElMessage.error(getApiErrorMessage(error, '下线失败')) }
}
</script>

<template>
  <section class="admin-page" aria-labelledby="problem-edit-title">
    <header class="admin-page-header"><div><p class="eyebrow">PROBLEM EDITOR</p><h1 id="problem-edit-title">{{ isNew ? '创建题目' : admin.problem?.title ?? '题目编辑' }}</h1></div><div v-if="admin.problem" class="admin-header-actions"><ElTag>{{ admin.problem.visibility }}</ElTag><ElButton v-if="admin.problem.visibility === 'public'" :loading="admin.pendingAction === 'offline'" @click="offline">下线</ElButton><ElButton v-else type="success" :loading="admin.pendingAction === 'publish'" @click="publish">发布题目</ElButton></div></header>
    <ElSkeleton v-if="admin.detailLoading" :rows="12" animated class="admin-loading" />
    <ElAlert v-else-if="admin.error" type="error" :title="admin.error" show-icon><template #default><ElButton size="small" @click="admin.loadProblem(problemId)">重试</ElButton></template></ElAlert>
    <template v-else>
      <section v-if="admin.problem && !admin.readiness?.ready" class="readiness-panel" aria-live="polite">
        <h2>发布前检查</h2><p>当前题目尚未满足发布门禁：</p>
        <ul><li v-for="issue in admin.readiness?.issues" :key="`${issue.code}-${issue.sequence}`"><code>{{ issue.code }}</code> {{ issue.message }}<span v-if="issue.sequence !== undefined">（用例 {{ issue.sequence }}）</span></li></ul>
      </section>
      <ProblemForm ref="formRef" :problem="admin.problem" :tags="catalog.tags" :saving="admin.pendingAction === 'save'" :field-errors="fieldErrors" @save="save" @dirty="dirty = $event" />
      <TestSetManager v-if="admin.problem" />
    </template>
  </section>
</template>
