<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getApiErrorMessage, getApiValidationIssues } from '@/services/http'
import { useAdminStore } from '@/stores/admin'
import type { CheckerType, TestSetMetadata } from '@/types/admin'

const admin = useAdminStore()
const dialogVisible = ref(false)
const selectedFile = ref<File | null>(null)
const createForm = reactive<{ checker_type: CheckerType; absolute_tolerance: number; relative_tolerance: number }>({ checker_type: 'exact', absolute_tolerance: 0.000001, relative_tolerance: 0.000001 })

function statusLabel(status: string): string {
  return { draft: '草稿', validating: '校验中', ready: '就绪', active: '活动', inactive: '历史', invalid: '无效' }[status] ?? status
}

async function createSet(): Promise<void> {
  try {
    await admin.createTestSet(
      createForm.checker_type,
      createForm.checker_type === 'float' ? createForm.absolute_tolerance : undefined,
      createForm.checker_type === 'float' ? createForm.relative_tolerance : undefined,
    )
    dialogVisible.value = false
    ElMessage.success('已创建新的草稿测试集版本')
  } catch (error) { ElMessage.error(getApiErrorMessage(error, '创建测试集失败')) }
}

function chooseFile(event: Event): void {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

async function upload(set: TestSetMetadata): Promise<void> {
  if (!selectedFile.value) { ElMessage.warning('请先选择 ZIP 测试数据包'); return }
  try {
    await admin.uploadArchive(set.id, selectedFile.value)
    selectedFile.value = null
    ElMessage.success('测试数据上传成功')
  } catch (error) { ElMessage.error(getApiErrorMessage(error, '上传失败')) }
}

async function validate(set: TestSetMetadata): Promise<void> {
  try {
    const result = await admin.validate(set.id)
    ElMessage.success(result.issues.length === 0 ? '测试集校验通过' : '校验完成，请处理问题')
  } catch (error) {
    const issues = getApiValidationIssues(error)
    ElMessage.error(issues.map((item) => item.message).join('；') || getApiErrorMessage(error, '校验失败'))
  }
}

async function activate(set: TestSetMetadata): Promise<void> {
  try {
    await ElMessageBox.confirm(`激活 v${set.version} 后，当前活动版本将转为历史版本。确认继续？`, '激活测试集', { type: 'warning' })
    await admin.activate(set.id)
    ElMessage.success('测试集已激活')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getApiErrorMessage(error, '激活失败'))
  }
}
</script>

<template>
  <section class="admin-panel test-set-manager" aria-labelledby="test-set-title">
    <header class="admin-panel-header">
      <div><h2 id="test-set-title">隐藏测试集版本</h2><p>仅展示受控元数据，不展示隐藏正文、对象键或校验和。</p></div>
      <ElButton @click="dialogVisible = true">创建草稿版本</ElButton>
    </header>
    <ElEmpty v-if="!admin.testSets.length" description="尚无测试集版本" />
    <ElCollapse v-else accordion>
      <ElCollapseItem v-for="set in admin.testSets" :key="set.id" :name="set.id">
        <template #title>
          <div class="test-set-heading"><strong>v{{ set.version }}</strong><ElTag :type="set.status === 'active' ? 'success' : set.status === 'invalid' ? 'danger' : 'info'">{{ statusLabel(set.status) }}</ElTag><span>{{ set.checker_type }} checker</span><span>{{ set.case_count }} 个用例</span><span>引用 {{ set.submission_reference_count }} 次</span></div>
        </template>
        <div v-if="set.status === 'draft' || set.status === 'invalid'" class="test-set-actions">
          <label class="file-picker">选择 ZIP<input type="file" accept=".zip,application/zip" aria-label="选择测试数据 ZIP" @change="chooseFile" /></label>
          <span>{{ selectedFile?.name ?? '未选择文件' }}</span>
          <ElButton :loading="admin.pendingAction === `upload:${set.id}`" @click="upload(set)">上传</ElButton>
          <ElProgress v-if="admin.pendingAction === `upload:${set.id}`" :percentage="admin.uploadProgress" />
          <ElButton :loading="admin.pendingAction === `validate:${set.id}`" @click="validate(set)">执行校验</ElButton>
        </div>
        <div v-if="set.status === 'ready'" class="test-set-actions"><ElButton type="primary" :loading="admin.pendingAction === `activate:${set.id}`" @click="activate(set)">激活此版本</ElButton></div>
        <ElTable v-if="set.cases.length" :data="set.cases" size="small">
          <ElTableColumn prop="sequence" label="序号" width="90" /><ElTableColumn prop="score" label="分值" width="90" />
          <ElTableColumn label="输入大小"><template #default="scope">{{ scope.row.input_size_bytes.toLocaleString() }} B</template></ElTableColumn>
          <ElTableColumn label="输出大小"><template #default="scope">{{ scope.row.output_size_bytes.toLocaleString() }} B</template></ElTableColumn>
          <ElTableColumn label="校验状态"><template #default="scope"><ElTooltip v-if="admin.testSetIssues[set.id]?.some((item) => item.sequence === scope.row.sequence)" :content="admin.testSetIssues[set.id]?.filter((item) => item.sequence === scope.row.sequence).map((item) => item.message).join('；')"><ElTag type="danger" size="small">校验失败</ElTag></ElTooltip><ElTag v-else :type="['ready', 'active', 'inactive'].includes(set.status) ? 'success' : 'info'" size="small">{{ ['ready', 'active', 'inactive'].includes(set.status) ? '校验通过' : '上传校验通过' }}</ElTag></template></ElTableColumn>
        </ElTable>
        <ElAlert v-if="admin.testSetIssues[set.id]?.length" type="error" title="测试集校验发现问题" show-icon class="test-set-issues"><ul><li v-for="issue in admin.testSetIssues[set.id]" :key="`${issue.code}-${issue.sequence}`">{{ issue.message }}<span v-if="issue.sequence !== undefined">（序号 {{ issue.sequence }}）</span></li></ul></ElAlert>
        <ElEmpty v-else description="此版本还没有用例元数据" :image-size="60" />
      </ElCollapseItem>
    </ElCollapse>
    <ElDialog v-model="dialogVisible" title="创建测试集草稿" width="min(92vw, 480px)">
      <ElForm label-position="top">
        <ElFormItem label="Checker"><ElSelect v-model="createForm.checker_type"><ElOption label="精确匹配" value="exact" /><ElOption label="Token 匹配" value="token" /><ElOption label="浮点误差" value="float" /></ElSelect></ElFormItem>
        <template v-if="createForm.checker_type === 'float'"><ElFormItem label="绝对误差"><ElInputNumber v-model="createForm.absolute_tolerance" :min="0" /></ElFormItem><ElFormItem label="相对误差"><ElInputNumber v-model="createForm.relative_tolerance" :min="0" /></ElFormItem></template>
      </ElForm>
      <template #footer><ElButton @click="dialogVisible = false">取消</ElButton><ElButton type="primary" :loading="admin.pendingAction === 'create-test-set'" @click="createSet">创建</ElButton></template>
    </ElDialog>
  </section>
</template>
