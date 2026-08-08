import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MarkdownContent from '@/components/problems/MarkdownContent.vue'

describe('MarkdownContent', () => {
  it('renders markdown while removing executable HTML', () => {
    const wrapper = mount(MarkdownContent, {
      props: {
        content:
          '# 安全题面\n\n<script>alert(1)</script><img src=x onerror="alert(2)">\n\n[危险](javascript:alert(3))',
      },
    })

    expect(wrapper.find('h1').text()).toBe('安全题面')
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.html()).not.toContain('onerror')
    expect(wrapper.html()).not.toContain('javascript:')
  })
})
