<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  createAdminCollection,
  getAdminCollection,
  listAdminCollections,
  reorderAdminCollection,
  setAdminCollectionPublished,
  updateAdminCollection,
} from '@/services/admin'
import { getApiErrorMessage } from '@/services/http'
import { getProblems } from '@/services/problems'
import type { AdminCollection, AdminCollectionSummary, CollectionWritePayload } from '@/types/admin'
import type { ProblemSummary } from '@/types/problem'

const items = ref<AdminCollectionSummary[]>([])
const loading = ref(false)
const error = ref('')
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref<AdminCollection | null>(null)
const candidates = ref<ProblemSummary[]>([])
const candidateQuery = ref('')
const form = reactive<CollectionWritePayload>({ slug: '', title: '', description: null, company: null, cover_url: null, problem_ids: [] })
const selectedProblems = computed(() => form.problem_ids.map((id) => candidates.value.find((item) => item.id === id) ?? editing.value?.problems.find((item) => item.problem.id === id)?.problem).filter(Boolean) as ProblemSummary[])

async function load(): Promise<void> {
  loading.value = true; error.value = ''
  try { items.value = (await listAdminCollections(1, 100)).items }
  catch (reason) { error.value = getApiErrorMessage(reason, '题单加载失败') }
  finally { loading.value = false }
}

function resetForm(): void { Object.assign(form, { slug: '', title: '', description: null, company: null, cover_url: null, problem_ids: [] }) }
async function openCreate(): Promise<void> { editing.value = null; resetForm(); dialogVisible.value = true; await searchProblems() }
async function openEdit(id: number): Promise<void> {
  try {
    editing.value = await getAdminCollection(id)
    Object.assign(form, { slug: editing.value.slug, title: editing.value.title, description: editing.value.description, company: editing.value.company, cover_url: editing.value.cover_url, problem_ids: editing.value.problems.map((item) => item.problem.id) })
    candidates.value = editing.value.problems.map((item) => item.problem)
    dialogVisible.value = true
  } catch (reason) { ElMessage.error(getApiErrorMessage(reason, '题单详情加载失败')) }
}

async function searchProblems(): Promise<void> {
  try {
    const result = await getProblems({ ...(candidateQuery.value ? { q: candidateQuery.value } : {}), page: 1, page_size: 50, sort: 'newest' })
    const current = editing.value?.problems.map((item) => item.problem) ?? []
    candidates.value = [...new Map([...current, ...result.items].map((item) => [item.id, item])).values()]
  } catch { candidates.value = [] }
}

function move(id: number, delta: number): void {
  const index = form.problem_ids.indexOf(id); const target = index + delta
  if (index < 0 || target < 0 || target >= form.problem_ids.length) return
  const next = [...form.problem_ids]; [next[index], next[target]] = [next[target]!, next[index]!]; form.problem_ids = next
}
function remove(id: number): void { form.problem_ids = form.problem_ids.filter((item) => item !== id) }

async function save(): Promise<void> {
  if (!form.slug || !form.title) { ElMessage.warning('请填写 slug 和标题'); return }
  saving.value = true
  try {
    if (editing.value) {
      await updateAdminCollection(editing.value.id, { slug: form.slug, title: form.title, description: form.description, company: form.company, cover_url: form.cover_url })
      await reorderAdminCollection(editing.value.id, form.problem_ids)
    } else await createAdminCollection({ ...form, problem_ids: [...form.problem_ids] })
    dialogVisible.value = false; ElMessage.success('题单已保存'); await load()
  } catch (reason) { ElMessage.error(getApiErrorMessage(reason, '题单保存失败')) }
  finally { saving.value = false }
}

async function toggle(item: AdminCollectionSummary): Promise<void> {
  try { await setAdminCollectionPublished(item.id, !item.is_public); ElMessage.success(item.is_public ? '题单已下线' : '题单已发布'); await load() }
  catch (reason) { ElMessage.error(getApiErrorMessage(reason, '状态更新失败')) }
}

onMounted(load)
</script>

<template>
  <section class="admin-page" aria-labelledby="collections-admin-title">
    <header class="admin-page-header"><div><p class="eyebrow">CONTENT OPERATIONS</p><h1 id="collections-admin-title">题单运营</h1></div><ElButton type="primary" @click="openCreate">创建题单</ElButton></header>
    <ElSkeleton v-if="loading" :rows="7" animated class="admin-loading" /><ElAlert v-else-if="error" type="error" :title="error" show-icon><template #default><ElButton @click="load">重试</ElButton></template></ElAlert><ElEmpty v-else-if="!items.length" description="暂无题单" />
    <ElTable v-else :data="items"><ElTableColumn prop="title" label="标题" min-width="180" /><ElTableColumn prop="slug" label="slug" min-width="180" /><ElTableColumn prop="problem_count" label="题目数" width="90" /><ElTableColumn label="状态" width="100"><template #default="scope"><ElTag :type="scope.row.is_public ? 'success' : 'info'">{{ scope.row.is_public ? '已发布' : '草稿' }}</ElTag></template></ElTableColumn><ElTableColumn label="操作" width="190"><template #default="scope"><ElButton link type="primary" @click="openEdit(scope.row.id)">编辑</ElButton><ElButton link @click="toggle(scope.row)">{{ scope.row.is_public ? '下线' : '发布' }}</ElButton></template></ElTableColumn></ElTable>
    <ElDialog v-model="dialogVisible" :title="editing ? '编辑题单' : '创建题单'" width="min(94vw, 860px)" destroy-on-close>
      <ElForm label-position="top"><div class="admin-form-grid"><ElFormItem label="slug" required><ElInput v-model="form.slug" /></ElFormItem><ElFormItem label="标题" required><ElInput v-model="form.title" /></ElFormItem><ElFormItem label="公司"><ElInput v-model="form.company" /></ElFormItem><ElFormItem label="封面 URL"><ElInput v-model="form.cover_url" /></ElFormItem></div><ElFormItem label="描述"><ElInput v-model="form.description" type="textarea" :rows="3" /></ElFormItem><ElFormItem label="搜索并添加公开题目"><ElInput v-model="candidateQuery" placeholder="输入关键词后回车" @keyup.enter="searchProblems"><template #append><ElButton @click="searchProblems">搜索</ElButton></template></ElInput></ElFormItem><ElSelect v-model="form.problem_ids" multiple filterable placeholder="选择题目" class="admin-wide-select"><ElOption v-for="problem in candidates" :key="problem.id" :label="`${problem.id}. ${problem.title}`" :value="problem.id" /></ElSelect>
        <div class="collection-order-list" aria-label="题目固定顺序"><article v-for="(problem, index) in selectedProblems" :key="problem.id"><span>{{ index + 1 }}. {{ problem.title }}</span><div><ElButton text :disabled="index === 0" :aria-label="`上移 ${problem.title}`" @click="move(problem.id, -1)">↑</ElButton><ElButton text :disabled="index === selectedProblems.length - 1" :aria-label="`下移 ${problem.title}`" @click="move(problem.id, 1)">↓</ElButton><ElButton text type="danger" @click="remove(problem.id)">移除</ElButton></div></article></div>
      </ElForm><template #footer><ElButton @click="dialogVisible = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">保存</ElButton></template>
    </ElDialog>
  </section>
</template>
