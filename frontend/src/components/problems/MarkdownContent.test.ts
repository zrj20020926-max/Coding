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

  it('sanitizes discussion and comment payloads with encoded event handlers', () => {
    const wrapper = mount(MarkdownContent, {
      props: {
        content: '<svg><a xlink:href="javascript:alert(1)">讨论</a></svg>\n\n**正常内容**',
      },
    })

    expect(wrapper.find('svg').exists()).toBe(false)
    expect(wrapper.html()).not.toContain('javascript:')
    expect(wrapper.text()).toContain('正常内容')
  })
})
