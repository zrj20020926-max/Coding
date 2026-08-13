import { describe, expect, it } from 'vitest'

import { parseProblemQuery, serializeProblemFilters, toProblemListParams } from '@/types/problem'

describe('problem URL query', () => {
  it('parses supported filters and normalizes invalid pagination', () => {
    const filters = parseProblemQuery({
      q: '  shortest path  ',
      difficulty: 'hard',
      tag: 'graph',
      category: 'large-input',
      status: 'attempted',
      sort: 'acceptance',
      page: '3',
      page_size: '999',
    })

    expect(filters).toEqual({
      q: 'shortest path',
      difficulty: 'hard',
      tag: 'graph',
      category: 'large-input',
      status: 'attempted',
      sort: 'acceptance',
      page: 3,
      pageSize: 20,
    })
    expect(toProblemListParams(filters)).toEqual({
      q: 'shortest path',
      difficulty: 'hard',
      tag: 'graph',
      category: 'large-input',
      status: 'attempted',
      sort: 'acceptance',
      page: 3,
      page_size: 20,
    })
  })

  it('omits defaults when serializing shareable query state', () => {
    expect(
      serializeProblemFilters({
        q: ' dp ',
        difficulty: '',
        tag: 'dynamic-programming',
        category: '',
        status: '',
        sort: 'newest',
        page: 1,
        pageSize: 20,
      }),
    ).toEqual({ q: 'dp', tag: 'dynamic-programming' })
  })

  it('keeps the favorite filter in the shareable URL query', () => {
    const filters = parseProblemQuery({ status: 'favorited' })

    expect(filters.status).toBe('favorited')
    expect(serializeProblemFilters(filters)).toEqual({ status: 'favorited' })
  })
})
