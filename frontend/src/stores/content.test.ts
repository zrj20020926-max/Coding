import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createComment,
  createDiscussion,
  getCollection,
  getCollections,
  getDailyChallenge,
  getDiscussion,
  getDiscussions,
} from '@/services/content'
import { useContentStore } from '@/stores/content'
import type { CollectionDetail, DailyChallenge, Discussion, DiscussionDetail } from '@/types/content'

vi.mock('@/services/content', () => ({
  getCollections: vi.fn(),
  getCollection: vi.fn(),
  getDailyChallenge: vi.fn(),
  getDiscussions: vi.fn(),
  createDiscussion: vi.fn(),
  getDiscussion: vi.fn(),
  createComment: vi.fn(),
  editDiscussion: vi.fn(),
  deleteDiscussion: vi.fn(),
  editComment: vi.fn(),
  deleteComment: vi.fn(),
  reportContent: vi.fn(),
}))

const problem = {
  id: 1,
  slug: 'a-plus-b',
  title: 'A+B',
  difficulty: 'easy' as const,
  source: null,
  accepted_count: 8,
  submission_count: 10,
  acceptance_rate: 80,
  tags: [],
}

const daily: DailyChallenge = {
  challenge_date: '2026-08-10',
  timezone: 'Asia/Shanghai',
  problem,
}

const collection: CollectionDetail = {
  id: 1,
  slug: 'top-list',
  title: 'TOP 题单',
  description: null,
  company: '字节',
  cover_url: null,
  problem_count: 1,
  solved_count: 0,
  completion_rate: 0,
  problems: [{ sequence: 0, problem }],
  page: 1,
  page_size: 20,
  pages: 1,
}

const discussion: Discussion = {
  id: 11,
  problem_id: 1,
  author: { id: 'user', nickname: '用户', avatar_url: null },
  title: '思路',
  content: '**前缀和**',
  is_pinned: false,
  is_locked: false,
  comment_count: 0,
  review_status: 'approved',
  created_at: '2026-08-10T00:00:00Z',
  updated_at: '2026-08-10T00:00:00Z',
  can_edit: true,
}

const detail: DiscussionDetail = {
  discussion,
  comments: { items: [], total: 0, page: 1, page_size: 30, pages: 0 },
}

describe('content store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('loads paginated collections and the server-dated daily challenge', async () => {
    vi.mocked(getCollections).mockResolvedValue({
      items: [collection], total: 1, page: 1, page_size: 12, pages: 1,
    })
    vi.mocked(getCollection).mockResolvedValue(collection)
    vi.mocked(getDailyChallenge).mockResolvedValue(daily)
    const store = useContentStore()

    await store.loadCollections(1, 12)
    await store.loadCollection('top-list', 1, 20)
    await store.loadDaily()

    expect(store.collections[0]?.slug).toBe('top-list')
    expect(store.collection?.problems[0]?.sequence).toBe(0)
    expect(store.daily?.timezone).toBe('Asia/Shanghai')
  })

  it('creates discussions and nested comments through the service layer', async () => {
    vi.mocked(getDiscussions).mockResolvedValue({
      items: [discussion], total: 1, page: 1, page_size: 10, pages: 1,
    })
    vi.mocked(createDiscussion).mockResolvedValue({ ...discussion, id: 12 })
    vi.mocked(getDiscussion).mockResolvedValue(detail)
    vi.mocked(createComment).mockResolvedValue({
      id: 21,
      discussion_id: 11,
      parent_id: null,
      depth: 0,
      author: discussion.author,
      content: 'comment',
      deleted: false,
      review_status: 'approved',
      created_at: discussion.created_at,
      updated_at: discussion.updated_at,
      can_edit: true,
    })
    const store = useContentStore()

    await store.loadDiscussions(1, 1, 10)
    await store.addDiscussion(1, 'new', 'body')
    await store.loadDiscussion(11, 1, 30)
    await store.addComment('comment')

    expect(store.discussionsTotal).toBe(2)
    expect(store.discussionDetail?.comments.total).toBe(1)
    expect(store.discussionDetail?.discussion.comment_count).toBe(1)
  })
})
