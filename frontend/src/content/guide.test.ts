import { describe, expect, it } from 'vitest'

import { GUIDE_SECTION_BY_SLUG, GUIDE_SECTIONS, searchGuide } from '@/content/guide'

describe('JavaScript ACM guide content', () => {
  it('searches topics, keywords and source templates', () => {
    expect(searchGuide('EOF').some((result) => result.topic.id === 'until-eof')).toBe(true)
    expect(searchGuide('BigInt').length).toBeGreaterThan(1)
    expect(searchGuide('process.stdout.write').some((result) => result.section.slug === 'nodejs'))
      .toBe(true)
    expect(searchGuide('definitely-not-present')).toEqual([])
  })

  it('keeps runnable V8 and Node.js templates in separate runtime blocks', () => {
    const v8Examples = GUIDE_SECTION_BY_SLUG['javascript-v8'].topics
      .flatMap((topic) => topic.examples)
    const nodeExamples = GUIDE_SECTION_BY_SLUG.nodejs.topics
      .flatMap((topic) => topic.examples)

    expect(v8Examples.every((example) => example.runtime === 'javascript-v8')).toBe(true)
    expect(nodeExamples.every((example) => example.runtime === 'nodejs')).toBe(true)
    expect(v8Examples.filter((example) => example.variant !== 'incorrect').every((example) =>
      !/\brequire\s*\(|\bprocess\.|\bBuffer\b/.test(example.code),
    )).toBe(true)
    expect(nodeExamples.every((example) => !/\breadline\s*\(|\bprint\s*\(/.test(example.code)))
      .toBe(true)
  })

  it('contains all required template and error topics with unique anchors', () => {
    const topicIds = GUIDE_SECTIONS.flatMap((section) => section.topics.map((topic) => topic.id))
    expect(new Set(topicIds).size).toBe(topicIds.length)
    for (const id of [
      'one-integer', 'two-integers', 'one-line-array', 'multiple-lines', 'test-cases',
      'until-eof', 'sentinel', 'matrix', 'character-grid', 'mixed-records', 'bigint',
      'large-scanner', 'blind-trim', 'split-space', 'unsafe-number', 'mixed-bigint',
      'array-shift', 'repeat-split', 'array-console', 'debug-output', 'ignore-crlf',
      'empty-line', 'eof-overrun', 'runtime-mixing',
    ]) {
      expect(topicIds).toContain(id)
    }
  })
})
