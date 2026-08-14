import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import OutputDiff from '@/components/problems/OutputDiff.vue'
import { normalizeExactOutput, splitVisibleOutput, summarizeOutputDiff } from '@/utils/outputDiff'

describe('output diff', () => {
  it('visualizes spaces, tabs, CRLF, LF, blank lines and a missing final newline', () => {
    const wrapper = mount(OutputDiff, {
      props: { expected: 'a \t\r\n\r\n', actual: 'a\t\n\nextra' },
    })

    expect(wrapper.text()).toContain('·')
    expect(wrapper.text()).toContain('⇥')
    expect(wrapper.text()).toContain('␍␊')
    expect(wrapper.text()).toContain('␊')
    expect(wrapper.text()).toContain('∅ EOL')
    expect(wrapper.text()).toContain('extra')
  })

  it('matches Judge exact normalization while still reporting raw differences', () => {
    const summary = summarizeOutputDiff('value  \r\n', 'value\n')
    expect(summary.rawEqual).toBe(false)
    expect(summary.checkerEquivalent).toBe(true)
    expect(normalizeExactOutput('value  \r\n')).toBe(normalizeExactOutput('value\n'))
  })

  it('keeps middle whitespace semantic and identifies extra debug output', () => {
    expect(summarizeOutputDiff('a b\n', 'a  b\ndebug\n').checkerEquivalent).toBe(false)
    expect(splitVisibleOutput('')).toEqual([
      { content: '', visibleContent: '∅', ending: 'NONE', raw: '' },
    ])
  })
})
