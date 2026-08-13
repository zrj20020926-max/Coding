import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ProblemForm from '@/components/admin/ProblemForm.vue'

describe('ProblemForm', () => {
  it('renders validation errors and a sanitized Markdown preview', async () => {
    const wrapper = mount(ProblemForm, {
      props: { problem: null, tags: [], saving: false, fieldErrors: { slug: 'slug 已存在' } },
      global: { stubs: { ElForm: { template: '<form><slot /></form>' }, ElFormItem: { props: ['error', 'label'], template: '<label>{{ label }}<slot /><span class="error">{{ error }}</span></label>' }, ElInput: { props: ['modelValue'], template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' }, ElSelect: { template: '<div><slot /></div>' }, ElOption: true, ElInputNumber: true, ElButton: { template: '<button><slot /></button>' } } },
    })
    expect(wrapper.text()).toContain('slug 已存在')
    const descriptions = wrapper.findAll('textarea')
    await descriptions[2]?.setValue('<img src=x onerror=alert(1)> **安全内容**')
    await wrapper.vm.$nextTick()
    expect(wrapper.get('.markdown-preview').html()).not.toContain('onerror')
    expect(wrapper.text()).toContain('安全内容')
  })
})
