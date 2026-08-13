<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'

import MarkdownContent from '@/components/problems/MarkdownContent.vue'
import type { AdminProblem, ProblemWritePayload } from '@/types/admin'
import { TRAINING_CATEGORY_LABELS, type ProblemTag, type TrainingCategory } from '@/types/problem'

const props = defineProps<{ problem: AdminProblem | null; tags: ProblemTag[]; saving: boolean; fieldErrors?: Record<string, string> }>()
const emit = defineEmits<{ save: [payload: ProblemWritePayload]; dirty: [value: boolean] }>()
const formRef = ref<FormInstance>()
const form = reactive<ProblemWritePayload>({
  slug: '', title: '', description: '', difficulty: 'easy', training_category: 'comprehensive', input_description: '', output_description: '',
  data_constraints: '', sample_input: '', sample_output: '', sample_explanation: '', time_limit_ms: 1000,
  memory_limit_mb: 256, source: null, tag_slugs: [],
})
const original = ref('')
const preview = computed(() => form.description || '在左侧输入 Markdown 题面后，这里会实时显示安全预览。')
const rules: FormRules = {
  slug: [{ required: true, pattern: /^[a-z0-9]+(?:-[a-z0-9]+)*$/, message: '请输入小写英文 slug', trigger: 'blur' }],
  title: [{ required: true, message: '请输入题目标题', trigger: 'blur' }],
  description: [{ required: true, message: '请输入题目描述', trigger: 'blur' }],
  input_description: [{ required: true, message: '请输入输入说明', trigger: 'blur' }],
  output_description: [{ required: true, message: '请输入输出说明', trigger: 'blur' }],
  data_constraints: [{ required: true, message: '请输入数据范围', trigger: 'blur' }],
  sample_explanation: [{ required: true, message: '请输入样例解释', trigger: 'blur' }],
}

function initialize(problem: AdminProblem | null): void {
  if (problem) Object.assign(form, {
    slug: problem.slug, title: problem.title, description: problem.description, difficulty: problem.difficulty,
    training_category: problem.training_category,
    input_description: problem.input_description, output_description: problem.output_description,
    data_constraints: problem.data_constraints, sample_input: problem.sample_input, sample_output: problem.sample_output,
    sample_explanation: problem.sample_explanation, time_limit_ms: problem.time_limit_ms,
    memory_limit_mb: problem.memory_limit_mb, source: problem.source, tag_slugs: problem.tags.map((tag) => tag.slug),
  })
  original.value = JSON.stringify(form)
  emit('dirty', false)
}

watch(() => props.problem, initialize, { immediate: true })
watch(form, () => emit('dirty', JSON.stringify(form) !== original.value), { deep: true })

async function submit(): Promise<void> {
  if (!(await formRef.value?.validate().catch(() => false))) return
  emit('save', { ...form, tag_slugs: [...form.tag_slugs] })
}

defineExpose({ markSaved: () => { original.value = JSON.stringify(form); emit('dirty', false) } })
</script>

<template>
  <ElForm ref="formRef" :model="form" :rules="rules" label-position="top" class="problem-admin-form" @submit.prevent="submit">
    <div class="admin-form-grid">
      <ElFormItem label="英文 slug" prop="slug" :error="fieldErrors?.['slug']"><ElInput v-model="form.slug" maxlength="100" /></ElFormItem>
      <ElFormItem label="中文标题" prop="title" :error="fieldErrors?.['title']"><ElInput v-model="form.title" maxlength="200" /></ElFormItem>
      <ElFormItem label="输入结构层级"><ElSelect v-model="form.difficulty"><ElOption label="基础" value="easy" /><ElOption label="组合" value="medium" /><ElOption label="综合" value="hard" /></ElSelect></ElFormItem>
      <ElFormItem label="训练分类"><ElSelect v-model="form.training_category"><ElOption v-for="(label, value) in TRAINING_CATEGORY_LABELS" :key="value" :label="label" :value="value as TrainingCategory" /></ElSelect></ElFormItem>
      <ElFormItem label="标签"><ElSelect v-model="form.tag_slugs" multiple filterable><ElOption v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.slug" /></ElSelect></ElFormItem>
    </div>
    <div class="markdown-editor-grid">
      <ElFormItem label="题目描述（Markdown）" prop="description" :error="fieldErrors?.['description']"><ElInput v-model="form.description" type="textarea" :rows="18" aria-label="Markdown 题目描述" /></ElFormItem>
      <section class="markdown-preview" aria-live="polite"><h3>实时预览</h3><MarkdownContent :content="preview" /></section>
    </div>
    <div class="admin-form-grid">
      <ElFormItem label="输入说明" prop="input_description" :error="fieldErrors?.['input_description']"><ElInput v-model="form.input_description" type="textarea" :rows="5" /></ElFormItem>
      <ElFormItem label="输出说明" prop="output_description" :error="fieldErrors?.['output_description']"><ElInput v-model="form.output_description" type="textarea" :rows="5" /></ElFormItem>
      <ElFormItem label="数据范围" prop="data_constraints" :error="fieldErrors?.['data_constraints']"><ElInput v-model="form.data_constraints" type="textarea" :rows="5" /></ElFormItem>
      <ElFormItem label="样例解释" prop="sample_explanation" :error="fieldErrors?.['sample_explanation']"><ElInput v-model="form.sample_explanation" type="textarea" :rows="5" /></ElFormItem>
      <ElFormItem label="公开样例输入"><ElInput v-model="form.sample_input" type="textarea" :rows="7" class="mono-input" /></ElFormItem>
      <ElFormItem label="公开样例输出"><ElInput v-model="form.sample_output" type="textarea" :rows="7" class="mono-input" /></ElFormItem>
      <ElFormItem label="时间限制（毫秒）" :error="fieldErrors?.['time_limit_ms']"><ElInputNumber v-model="form.time_limit_ms" :min="100" :max="30000" :step="100" /></ElFormItem>
      <ElFormItem label="内存限制（MB）" :error="fieldErrors?.['memory_limit_mb']"><ElInputNumber v-model="form.memory_limit_mb" :min="16" :max="2048" :step="16" /></ElFormItem>
    </div>
    <ElButton native-type="submit" type="primary" :loading="saving">保存题目</ElButton>
  </ElForm>
</template>
